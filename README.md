# Email → Telegram: Claude sign-in link (and more)

Forward Gmail to Telegram: get important links (e.g. Claude sign-in magic links) on demand via a Telegram bot. Self-hosted, OAuth (no App Password), single binary.

**On-demand bot (recommended):** The recipient opens the bot in Telegram, taps the **menu** (or sends `/link`), and gets today's Claude sign-in link. No interval — it runs when they ask.

**Optional:** You can still push the link on a schedule with `forward` / `run`.

## Gmail: sign in with Google (OAuth, no App Password)

1. **Get OAuth credentials (one-time)**  
   - Go to [Google Cloud Console](https://console.cloud.google.com/)  
   - Create or select a project → **APIs & Services** → **Credentials**  
   - **Create credentials** → **OAuth client ID**  
   - If asked, configure the OAuth consent screen (External, add your email as test user)  
   - Application type: **Desktop app**  
   - Download the JSON and save it as **`credentials.json`** in this folder  

   **Detailed: Creating Google OAuth credentials**  
   - Open [Google Cloud Console](https://console.cloud.google.com/) and sign in.  
   - **Create or select a project:** top bar → select project or "New project" (e.g. "email-to-telegram").  
   - **OAuth consent screen (required first time):** Left menu → **APIs & Services** → **OAuth consent screen**.  
     - User type: **External** → Create.  
     - App name (e.g. "Email to Telegram"), User support email, Developer contact email → Save and Continue.  
     - Scopes → Save and Continue (or add `https://mail.google.com/` if you add scopes).  
     - Test users → **Add users** → add the Gmail address you will use (e.g. your@gmail.com) → Save and Continue.  
   - **Create OAuth client ID:** Left menu → **APIs & Services** → **Credentials** → **Create credentials** → **OAuth client ID**.  
     - Application type: **Desktop app**.  
     - Name (e.g. "Email to Telegram desktop").  
     - Create → download the JSON.  
   - Rename the downloaded file to **`credentials.json`** and put it in this project folder (same folder as `main.py`).

2. **Sign in once**  
   ```bash
   pip install -r requirements.txt
   python main.py auth
   ```  
   A browser opens; sign in with your Gmail.  
   After that, **`token.json`** is saved and the forwarder will use it (no password in `.env`).

3. **Optional: use App Password instead**  
   If you prefer not to use OAuth, leave out `credentials.json` and `token.json`, and set **`IMAP_PASSWORD`** in `.env` to a [Gmail App Password](https://myaccount.google.com/apppasswords).

## Telegram

1. Create a bot: message [@BotFather](https://t.me/BotFather), send `/newbot`, copy the **token**.
2. Get the recipient's **chat_id**: they must **message the bot first** (e.g. send "hi" or tap **Start**) — Telegram does not allow bots to message a user until that user has opened a chat with the bot. Then open:
   ```text
   https://api.telegram.org/bot<PASTE_TOKEN_HERE>/getUpdates
   ```
   In the JSON, find `"chat":{"id": 123456789}` — that number is **TELEGRAM_CHAT_ID**.

## Run

1. Copy `.env.example` to `.env` and set:
   - **IMAP_USER** = your Gmail
   - **TELEGRAM_BOT_TOKEN** and **TELEGRAM_CHAT_ID** (recipient's chat_id)
   - Do **not** set IMAP_PASSWORD if you use OAuth.

2. **One-time:** `python main.py auth` (browser sign-in).

3. **On-demand bot (recommended):**
   ```bash
   python main.py bot
   ```
   Keep this running (e.g. on your machine or VPS). The recipient must have **messaged the bot at least once** (e.g. "hi" or **Start**) before the bot can reply; then they open the bot — the **menu button** shows "Get Claude sign-in link" (or they send `/link`). The bot fetches today's Claude login email from your Gmail and sends the magic link. No interval; it only runs when they ask.

4. **Optional — push once:** `python main.py forward` (finds today's unread Claude login email and sends the link once).

5. **Optional — push on a schedule:** `python main.py run` (or cron with `python main.py forward`).

---

## Build a single executable (for VPS)

Builds one binary you can copy to your VPS — no Python or pip needed there.

1. **Build** (on your machine, same OS as the VPS — e.g. build on Linux for a Linux VPS):
   ```bash
   cd email-to-telegram
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt pyinstaller
   ./build.sh
   ```
   Output: **`dist/email-to-telegram`** (Linux) or **`dist/email-to-telegram.exe`** (Windows).

2. **Transfer to VPS**  
   Copy to the VPS in one folder:
   - `email-to-telegram` (the binary)
   - `.env` (with IMAP_USER, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
   - `token.json` (if you use OAuth — run `./email-to-telegram auth` once on a machine with a browser, then copy `token.json` to the VPS)

3. **Run on VPS**
   ```bash
   chmod +x email-to-telegram
   ./email-to-telegram bot       # on-demand: recipient gets link via menu /link (recommended)
   # or
   ./email-to-telegram forward  # push once
   ./email-to-telegram run      # push every 5 min
   ```

4. **Keep the bot running** (systemd example for on-demand bot):
   ```ini
   [Unit]
   Description=Claude link Telegram bot
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/path/to/folder/with/binary/and/env
   ExecStart=/path/to/email-to-telegram bot
   Restart=on-failure
   RestartSec=60

   [Install]
   WantedBy=multi-user.target
   ```
   Then: `sudo systemctl daemon-reload && sudo systemctl enable --now email-to-telegram`.
