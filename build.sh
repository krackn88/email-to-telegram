#!/usr/bin/env bash
# Build a single executable for the current OS (Linux binary on Linux, .exe on Windows).
# Output: dist/email-to-telegram (or email-to-telegram.exe on Windows)
set -e
cd "$(dirname "$0")"

# Prefer venv if present
if [ -d .venv ]; then
  PIP=.venv/bin/pip
  PYINSTALLER=.venv/bin/pyinstaller
else
  PIP=pip
  PYINSTALLER=pyinstaller
fi

if ! command -v $PYINSTALLER &>/dev/null; then
  echo "Installing PyInstaller..."
  $PIP install pyinstaller
fi

$PIP install -r requirements.txt

$PYINSTALLER \
  --onefile \
  --name email-to-telegram \
  --clean \
  --noconfirm \
  --hidden-import=google.oauth2.credentials \
  --hidden-import=google.auth.transport.requests \
  --hidden-import=google_auth_oauthlib.flow \
  --hidden-import=google.auth \
  --hidden-import=imapclient \
  --hidden-import=requests \
  main.py

echo ""
echo "Built: dist/email-to-telegram"
echo ""
echo "To run on your VPS:"
echo "  1. Copy to VPS: dist/email-to-telegram plus .env (and token.json if using OAuth)"
echo "  2. Put all in one folder; .env must be next to the binary"
echo "  3. chmod +x email-to-telegram"
echo "  4. Run once:  ./email-to-telegram forward"
echo "  5. Run as daemon:  ./email-to-telegram run   (checks every 5 min; use nohup or systemd to keep it running)"
