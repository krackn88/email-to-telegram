#!/usr/bin/env python3
"""
Single entry point for the email-to-telegram forwarder.
Usage:
  email-to-telegram auth     - one-time Gmail OAuth (browser)
  email-to-telegram bot      - run bot: she gets link on demand via Telegram menu /link
  email-to-telegram forward  - run forward once (push link to her)
  email-to-telegram run      - run forward every N min (optional)
"""
import argparse
import sys
import time

from env_loader import load_dotenv

# Load .env before importing modules that read os.environ
load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Forward Gmail (e.g. Claude) to Telegram.",
        prog="email-to-telegram",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="bot",
        choices=("auth", "bot", "forward", "run"),
        help="auth = Gmail sign-in; bot = she gets link on demand (default); forward = push once; run = interval",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        metavar="SEC",
        help="Seconds between runs when using 'run' (default: 300)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With 'forward': fetch and show extracted magic-link URL only (no send, no mark read)",
    )
    args = parser.parse_args()

    if args.command == "auth":
        from auth_gmail import main as auth_main
        return auth_main()

    if args.command == "bot":
        from telegram_bot import run_bot
        run_bot()
        return 0

    if args.command == "forward":
        print("Running forward...", flush=True)
        try:
            from forward import run as forward_run
            forward_run(dry_run=args.dry_run)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
            return 1
        return 0

    if args.command == "run":
        from forward import run as forward_run
        interval = max(60, args.interval)
        print(f"Running forwarder every {interval}s. Ctrl+C to stop.")
        while True:
            try:
                forward_run()
            except KeyboardInterrupt:
                print("\nStopped.")
                return 0
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
            time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main() or 0)
