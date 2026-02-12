#!/usr/bin/env python3
"""
Forward emails matching a filter (e.g. subject contains "Claude") to a Telegram chat.
Run on a schedule (cron/systemd) to auto-forward new messages to the recipient.
"""

# Load .env from base dir (script dir or exe dir when frozen)
from env_loader import get_base_dir, load_dotenv

load_dotenv()

import base64
import email
import json
import os
import re
import sys
from datetime import date
from email.header import decode_header
from pathlib import Path

import imapclient
import requests

# --- Config from environment ---
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
IMAP_FOLDER = os.environ.get("IMAP_FOLDER", "INBOX")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Only forward emails whose subject contains this (case-insensitive). Empty = forward all new.
SUBJECT_FILTER = os.environ.get("SUBJECT_FILTER", "Claude").strip()

# Max length per Telegram message (leave a bit of margin)
TELEGRAM_MAX_LENGTH = 4050

STATE_FILE = get_base_dir() / "state.json"
TOKEN_FILE = get_base_dir() / "token.json"
GMAIL_OAUTH_SCOPES = ["https://mail.google.com/"]


def get_imap_oauth_token():
    """Load token.json, refresh if needed, return access token for IMAP XOAUTH2."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_FILE.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_OAUTH_SCOPES)
    if not creds:
        return None
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        return None
    return creds.token


def imap_connect_with_oauth(client, email_address, access_token):
    """Authenticate IMAP connection using XOAUTH2."""
    # Raw SASL string; imaplib will base64-encode it before sending (do not pre-encode).
    raw = ("user=" + email_address + "\x01auth=Bearer " + access_token + "\x01\x01").encode("utf-8")

    def authobject(response):
        if response is not None and response.strip():
            return b""
        return raw

    client._imap.authenticate("XOAUTH2", authobject)


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"last_uid": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def decode_mime_header(header):
    if header is None:
        return ""
    parts = decode_header(header)
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(part or "")
    return " ".join(result).strip()


# Match Claude magic-link URL anywhere in email (button link)
CLAUDE_MAGIC_LINK_RE = re.compile(
    rb"https://claude\.ai/magic-link#[^\s\"'<>)\]\s]+",
    re.IGNORECASE,
)


def extract_claude_magic_link(msg) -> str | None:
    """Extract the Claude.ai magic-link URL from email (any part)."""
    def scan(payload: bytes | None) -> str | None:
        if not payload:
            return None
        m = CLAUDE_MAGIC_LINK_RE.search(payload)
        if m:
            url = m.group(0).decode("utf-8", errors="replace").rstrip("'\">)]")
            return url if url.startswith("http") else None
        return None

    if msg.is_multipart():
        for part in msg.walk():
            try:
                payload = part.get_payload(decode=True)
                u = scan(payload)
                if u:
                    return u
            except Exception:
                pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            return scan(payload)
        except Exception:
            pass
    return None


def get_body(msg):
    """Extract plain text body from email message."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(
                            part.get_content_charset() or "utf-8", errors="replace"
                        )
                        break
                except Exception:
                    pass
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            raw = payload.decode(
                                part.get_content_charset() or "utf-8", errors="replace"
                            )
                            body = re.sub(r"<[^>]+>", " ", raw)
                            body = re.sub(r"\s+", " ", body).strip()
                            break
                    except Exception:
                        pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(
                    msg.get_content_charset() or "utf-8", errors="replace"
                )
        except Exception:
            pass
    return body.strip() or "(no body)"


def send_telegram(text: str, chat_id: str | None = None) -> tuple[bool, str | None]:
    """Send text to Telegram. chat_id defaults to TELEGRAM_CHAT_ID. Returns (success, error_message)."""
    cid = chat_id or TELEGRAM_CHAT_ID
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for i in range(0, len(text), TELEGRAM_MAX_LENGTH):
        chunk = text[i : i + TELEGRAM_MAX_LENGTH]
        payload = {"chat_id": cid, "text": chunk, "parse_mode": "HTML"}
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code != 200:
                r = requests.post(url, data={"chat_id": cid, "text": chunk}, timeout=30)
            if r.status_code != 200:
                data = r.json() if r.text else {}
                desc = data.get("description", r.text or str(r.status_code))
                if r.status_code == 403 and "can't initiate conversation" in desc.lower():
                    return False, "Telegram 403: The recipient must message the bot first (e.g. send 'hi' to the bot), then run again."
                return False, f"Telegram API error: {r.status_code} {desc}"
        except requests.RequestException as e:
            return False, f"Telegram request failed: {e}"
    return True, None


def get_latest_claude_link_from_gmail() -> tuple[str | None, str | None]:
    """
    Fetch the most recent Claude login email from today and return its magic-link URL.
    Returns (link, None) on success, or (None, error_message) if no link or error.
    Does not require the email to be unread.
    """
    if not IMAP_USER:
        return None, "IMAP_USER not set"
    use_oauth = TOKEN_FILE.exists() and not os.environ.get("IMAP_PASSWORD")
    if not use_oauth and not IMAP_PASSWORD:
        return None, "Run 'python main.py auth' or set IMAP_PASSWORD"

    with imapclient.IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=True, timeout=30) as client:
        if use_oauth:
            access_token = get_imap_oauth_token()
            if not access_token:
                return None, "OAuth expired. Run 'python main.py auth' again."
            imap_connect_with_oauth(client, IMAP_USER, access_token)
        else:
            client.login(IMAP_USER, IMAP_PASSWORD)
        client.select_folder(IMAP_FOLDER, readonly=True)
        t = date.today()
        today_str = f"{t.day:02d}-{('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')[t.month-1]}-{t.year}"
        try:
            uids = client.search(["SUBJECT", "Secure link", "ON", today_str])
        except Exception as e:
            return None, f"IMAP search failed: {e}"
        if not uids:
            return None, "No Claude login email from today."
        uid = max(uids)
        try:
            data = client.fetch([uid], ["RFC822"])
            if uid not in data:
                return None, "Fetch failed"
            msg = email.message_from_bytes(data[uid][b"RFC822"])
        except Exception as e:
            return None, f"Fetch failed: {e}"
        subject = decode_mime_header(msg.get("Subject"))
        if "secure link" not in subject.lower() or "claude" not in subject.lower():
            return None, "No Claude login email from today."
        link = extract_claude_magic_link(msg)
        if not link:
            return None, "No magic-link URL in today's Claude email."
        return link, None


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def run(dry_run=False):
    def out(msg, err=False):
        f = sys.stderr if err else sys.stdout
        print(msg, file=f, flush=True)

    out("Starting...")
    if not IMAP_USER:
        out("Set IMAP_USER (e.g. your_email@gmail.com).", err=True)
        sys.exit(1)
    use_oauth = TOKEN_FILE.exists() and not os.environ.get("IMAP_PASSWORD")
    if not use_oauth and not IMAP_PASSWORD:
        out("Use either: (1) Gmail OAuth: run 'python main.py auth' once, or (2) set IMAP_PASSWORD.", err=True)
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        out("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env", err=True)
        sys.exit(1)
    out("Connecting to Gmail...")
    state = load_state()

    # 30s timeout so we don't hang forever on auth/read
    with imapclient.IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=True, timeout=30) as client:
        if use_oauth:
            access_token = get_imap_oauth_token()
            if not access_token:
                out("OAuth token missing or expired. Run 'python main.py auth' again.", err=True)
                sys.exit(1)
            out("OAuth OK, authenticating with Gmail IMAP (XOAUTH2)...")
            imap_connect_with_oauth(client, IMAP_USER, access_token)
            out("Authenticated.")
        else:
            client.login(IMAP_USER, IMAP_PASSWORD)
        out("Selecting INBOX...")
        client.select_folder(IMAP_FOLDER, readonly=False)

        # Only Anthropic login emails from today: subject "Secure link..." and ON today
        t = date.today()
        today_str = f"{t.day:02d}-{('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec')[t.month-1]}-{t.year}"
        try:
            uids = client.search(["UNSEEN", "SUBJECT", "Secure link", "ON", today_str])
        except Exception as e:
            out(f"IMAP search failed: {e}", err=True)
            return
        uids = sorted(uids) if uids else []
        out(f"[1] Found {len(uids)} unread Claude login email(s) from today ({today_str}).")
        if not uids:
            out("No unread Claude login emails. Mark the 'Secure link to log in to Claude.ai' email as unread and run again.")
            return

        for uid in uids:
            try:
                data = client.fetch([uid], ["RFC822", "INTERNALDATE"])
                if uid not in data:
                    out(f"[2] Fetch failed for uid {uid}.", err=True)
                    continue
                msg = email.message_from_bytes(data[uid][b"RFC822"])
            except Exception as e:
                out(f"[2] Fetch uid {uid}: {e}", err=True)
                continue

            subject = decode_mime_header(msg.get("Subject"))
            if "secure link" not in subject.lower() or "claude" not in subject.lower():
                continue
            out(f"[3] Claude login email: {subject[:60]}...")

            magic_link = extract_claude_magic_link(msg)
            if not magic_link:
                out("[4] No magic-link URL found in this email.", err=True)
                continue
            out(f"[4] Extracted link: {magic_link[:60]}...")

            if dry_run:
                out("(dry-run) Would send to Telegram: " + magic_link)
                continue

            out("[5] Sending to Telegram...")
            ok, err_msg = send_telegram(magic_link)
            if ok:
                client.set_flags([uid], [b"\\Seen"])
                out("[5] Sent to Telegram.")
            else:
                if err_msg:
                    out(err_msg, err=True)
                else:
                    out("[5] Telegram send failed.", err=True)


if __name__ == "__main__":
    run()
