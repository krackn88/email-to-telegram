#!/usr/bin/env python3
"""Fetch latest Claude email from inbox and print extracted magic-link URL."""
import email
import sys

from env_loader import load_dotenv
load_dotenv()

import imapclient
from forward import (
    IMAP_HOST,
    IMAP_PORT,
    IMAP_USER,
    SUBJECT_FILTER,
    TOKEN_FILE,
    decode_mime_header,
    extract_claude_magic_link,
    get_imap_oauth_token,
    imap_connect_with_oauth,
)

def main():
    if not IMAP_USER:
        print("Set IMAP_USER in .env", file=sys.stderr)
        return 1
    if not TOKEN_FILE.exists():
        print("Run 'python main.py auth' first", file=sys.stderr)
        return 1

    access_token = get_imap_oauth_token()
    if not access_token:
        print("OAuth token missing or expired. Run 'python main.py auth' again.", file=sys.stderr)
        return 1

    with imapclient.IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=True) as client:
        imap_connect_with_oauth(client, IMAP_USER, access_token)
        client.select_folder("INBOX", readonly=True)

        # Search for emails with Claude in subject (any, not just unread)
        uids = client.search(['SUBJECT', 'Claude'])
        if not uids:
            print("No email with 'Claude' in subject found in INBOX.")
            return 0

        # Get the most recent (highest UID)
        uid = max(uids)
        data = client.fetch([uid], ["RFC822"])
        if uid not in data:
            print("Fetch failed for uid", uid, file=sys.stderr)
            return 1

        msg = email.message_from_bytes(data[uid][b"RFC822"])
        subject = decode_mime_header(msg.get("Subject"))
        from_addr = decode_mime_header(msg.get("From"))

        print("Subject:", subject)
        print("From:", from_addr)
        print()

        magic_link = extract_claude_magic_link(msg)
        if magic_link:
            print("Extracted magic-link URL:")
            print(magic_link)
        else:
            print("No Claude magic-link URL found in this email.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
