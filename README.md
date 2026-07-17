# Personal Task Agent

A local agent that watches your **Google Calendar** and **Google Classroom**,
and reminds you about meetings and tests/assignments via **Telegram**,
**WhatsApp**, and **Email**. Runs entirely on your own machine — Windows,
macOS, or Linux, auto-detected — no VPS or cloud server required.

## What it does
- Every few minutes, checks your calendar + classroom for anything coming up.
- Fires reminders at whatever offsets you set (e.g. 1 day / 1 hour / 15 min before).
- Never repeats a reminder (tracked in a local SQLite file).
- Telegram doubles as a two-way chat, and it treats you differently from
  everyone else who messages the bot:
  - **You** (TELEGRAM_CHAT_ID) get: `/today` (full agenda), `/addmeeting`
    (guided flow to add something to your calendar), `/ping`.
  - **Anyone else** who messages the bot gets an automatic reply, and can
    use `/book` to see your real open slots (checked against free/busy
    only — guests never see your event titles) and book one. It's created
    directly on your calendar, and you get pinged on Telegram when it happens.

### Upgrading from an earlier version of this project
If you set this up before and are pulling this update: Google Calendar
access changed from read-only to read+write (needed for /addmeeting and
bookings). **Delete `token.json`** and run `python main.py` again — it'll
send you through the Google login one more time to grant the wider access.

## One important limitation, up front
Telegram and Email work fully two-way, locally, no public server needed.
**WhatsApp is outbound-only here** — sending reminders works great from your
machine, but WhatsApp's platform requires a public webhook URL to *receive*
messages, which conflicts with "runs only on my system." If you later want
two-way WhatsApp, that's the point where you'd add a tunnel (ngrok/Cloudflare
Tunnel) or a small always-on server.

---

## 1. Install dependencies

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

## 2. Set up Google Calendar + Classroom access
1. Go to the [Google Cloud Console](https://console.cloud.google.com/), create a project.
2. Enable the **Google Calendar API** and **Google Classroom API** for it.
3. Go to "Credentials" → "Create Credentials" → "OAuth client ID" → choose **Desktop app**.
4. Download the JSON file, rename it `credentials.json`, and put it in the project root.
5. On first run, a browser window will open asking you to log in and approve access — that's expected, it only happens once. It caches a `token.json` afterward.

## 3. Set up Telegram
1. Message **@BotFather** on Telegram, send `/newbot`, follow the prompts.
2. Copy the token it gives you into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Message your new bot once (anything), then message **@userinfobot** to get your numeric chat ID, or visit `https://api.telegram.org/bot<TOKEN>/getUpdates` after messaging your bot to find your `chat.id`.
4. Put that into `.env` as `TELEGRAM_CHAT_ID`.

## 4. Set up WhatsApp (optional)
1. Create a Meta developer account and a WhatsApp Business app at [developers.facebook.com](https://developers.facebook.com/).
2. Get a phone number ID and a permanent access token.
3. In Meta Business Manager, create and get approval for a message template (needed for `WHATSAPP_SEND_MODE=template`), e.g. a simple template with one text variable.
4. Fill in `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TO_NUMBER` (your own number, with country code, no `+`) in `.env`.

## 5. Set up Email (optional)
1. For Gmail: turn on 2-Factor Authentication, then create an **App Password**.
2. Fill in `EMAIL_USER`, `EMAIL_PASS` (the app password, not your real one), and `EMAIL_TO` in `.env`.

## 6. Configure `.env`
Copy `.env.example` to `.env` and fill in the values above, plus toggle which
channels/sources you want (`ENABLE_TELEGRAM`, `ENABLE_WHATSAPP`, `ENABLE_EMAIL`,
`ENABLE_GOOGLE_CALENDAR`, `ENABLE_GOOGLE_CLASSROOM`), adjust
`REMINDER_OFFSETS_MINUTES` to taste, and set `LOCAL_TIMEZONE` to your IANA
timezone (e.g. `Asia/Kolkata`) so times shown to you and to guests are correct.

## 7. Run it manually first (to test + do the Google login)

```bash
python main.py
```

Try messaging your Telegram bot `/today` to confirm it can see your calendar/classroom.
Press Ctrl+C to stop.

## 8. Deploy it to run automatically in the background

```bash
python install/install.py
```

This detects your OS and sets it up to start automatically:
- **Windows** → a launcher dropped in your Startup folder, running silently
  via `pythonw.exe` (no console window). If anything goes wrong while
  running this way, check `agent.log` in the project folder - that's
  where output goes since there's no console to print to.
- **macOS** → a `launchd` user agent (auto-restarts if it crashes)
- **Linux** → a `systemd --user` service (auto-restarts if it crashes)

To remove it later: `python install/install.py --uninstall`

---

## Troubleshooting
- **"Something went wrong on my end, sorry" right after entering a date/time
  (Windows only):** Windows doesn't ship the IANA timezone database that
  Python needs for `LOCAL_TIMEZONE`. Fix: `pip install tzdata` (already in
  `requirements.txt` as of this version - if you're on an older copy,
  just run that command).
- **`/addmeeting` rejects a date you think looks right:** it needs both
  date and time in one message, e.g. `2026-07-22 10:00`, not just `2026-07-22`.

## Project structure
```
task-agent/
├── main.py                    # entry point
├── config.py                  # loads .env, validates setup
├── connectors/
│   ├── google_auth.py         # shared Google OAuth
│   ├── calendar_source.py     # Google Calendar → events
│   ├── classroom_source.py    # Google Classroom → coursework
│   ├── telegram_channel.py    # send + receive (two-way)
│   ├── whatsapp_channel.py    # send only (Meta Cloud API)
│   └── email_channel.py       # send only (SMTP)
├── core/
│   ├── storage.py             # SQLite dedupe of sent reminders
│   └── reminder_engine.py     # gathers items, decides, dispatches
└── install/
    └── install.py             # cross-platform autostart installer
```

## Extending it later
- Add more Telegram commands in `main.py` (`handle_*` functions).
- Add more sources (e.g. Outlook, Notion) by writing a new file in
  `connectors/` that returns the same normalized item shape used by
  `calendar_source.py`.
- Swap the reminder message wording in `core/reminder_engine.py::_format_message`.
