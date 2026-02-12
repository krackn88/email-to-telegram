#!/usr/bin/env python3
"""
On-demand Telegram bot: the user taps the menu or sends /link and gets the Claude sign-in link.
No interval — runs when they ask. Run with: python main.py bot
"""

from env_loader import load_dotenv
load_dotenv()

import sys
import requests

# Import after .env is loaded
from forward import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    get_latest_claude_link_from_gmail,
    send_telegram,
)

BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def set_bot_commands():
    """Register /link so it shows in the bot menu."""
    r = requests.post(
        BASE + "/setMyCommands",
        json={
            "commands": [
                {"command": "link", "description": "Get Claude sign-in link"},
                {"command": "start", "description": "Start"},
            ]
        },
        timeout=10,
    )
    if r.status_code != 200:
        print(f"Warning: setMyCommands failed: {r.status_code} {r.text}", file=sys.stderr)


def set_menu_button():
    """Show the menu button (with commands) in the chat."""
    r = requests.post(
        BASE + "/setChatMenuButton",
        json={"menu_button": {"type": "commands"}},
        timeout=10,
    )
    if r.status_code != 200:
        print(f"Warning: setChatMenuButton failed: {r.status_code} {r.text}", file=sys.stderr)


def reply(chat_id: int | str, text: str):
    """Send a message to the given chat."""
    send_telegram(text, chat_id=str(chat_id))


def handle_update(update: dict) -> bool:
    """Process one update. Return True if we consumed it."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return False
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip().lower()
    if not text:
        return False
    # Only respond to the configured user (recipient)
    if str(chat_id) != str(TELEGRAM_CHAT_ID):
        return False
    if text not in ("/link", "link", "/getlink", "get link", "/start", "start"):
        return False

    if text in ("/start", "start"):
        reply(chat_id, "Hi! Use /link to get the latest Claude sign-in link from today's email.")
        return True

    reply(chat_id, "Checking your email…")
    link, err = get_latest_claude_link_from_gmail()
    if link:
        reply(chat_id, link)
    else:
        reply(chat_id, err or "No link found.")
    return True


def run_bot():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env", file=sys.stderr)
        sys.exit(1)
    set_bot_commands()
    set_menu_button()
    print("Bot running. The recipient can open the bot and tap Menu → Get Claude sign-in link (or send /link). Ctrl+C to stop.")
    offset = None
    while True:
        try:
            r = requests.get(
                BASE + "/getUpdates",
                params={"timeout": 60, "offset": offset},
                timeout=70,
            )
            if r.status_code != 200:
                print(f"getUpdates error: {r.status_code}", file=sys.stderr)
                continue
            data = r.json()
            if not data.get("ok"):
                continue
            for u in data.get("result", []):
                offset = u["update_id"] + 1
                handle_update(u)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    run_bot()
