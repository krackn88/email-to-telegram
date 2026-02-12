#!/usr/bin/env python3
"""
One-time Gmail OAuth: opens your browser to sign in with Google and saves token.json.
After this, forward.py will use token.json instead of an App Password.
"""

from env_loader import get_base_dir, load_dotenv

load_dotenv()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://mail.google.com/"]
DIR = get_base_dir()
CREDENTIALS_FILE = DIR / "credentials.json"
TOKEN_FILE = DIR / "token.json"


def main():
    if not CREDENTIALS_FILE.exists():
        print("Missing credentials.json")
        print()
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create or select a project → APIs & Services → Credentials")
        print("3. Create credentials → OAuth client ID")
        print("4. Application type: Desktop app")
        print("5. Download JSON and save as credentials.json in this folder")
        print("   ", CREDENTIALS_FILE)
        return 1

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    print("Gmail OAuth done. token.json saved.")
    print("You can run forward.py now; it will use this token instead of a password.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
