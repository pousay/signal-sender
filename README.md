# Telegram Premium Signal Bot

A production-grade, typed, and resilient Persian Telegram trading signal bot built with **Kurigram**, **MTProto**, **asyncio**, and **Pydantic v2**.

The bot publishes trading signals to a public Telegram channel as captions over randomly selected photos, selectively hides the numeric `Sell limit` behind a clickable deep link (`مشاهده`), and delivers full position details privately to users with an active premium subscription.

---

## Features

- **Strict Persian User Experience**: All user-facing copy, prompts, alerts, and inline buttons are in Persian.
- **MTProto Photo Synchronization**: Retrieves complete source channel message history via Kurigram's MTProto API, extracts reusable Telegram photo identifiers (`file_id`), deduplicates using stable `file_unique_id`, and atomically replaces the stored photo pool.
- **Selective Value Concealment**: Replaces strictly the numeric digits of the `Sell limit` with a deep-linked `[مشاهده](...)` link while preserving all other Persian text, line breaks, emojis, hashtags, and formatting.
- **Attached Channel Actions**: Publishes one photo with the modified caption and an attached inline action button:
  `📝 برای مشاهده مشخصات پـوزیشن کلیک کنید`
- **Real-Time Subscription Gate**: Synchronous verification at access time and deep-link routing. Active subscribers receive full position parameters; non-subscribers receive instructions and a support username link.
- **Custom-Duration Subscriptions**: Admin wizard allowing arbitrary day durations (`now + days`), which replace rather than extend prior expiries.
- **Proactive Background Notifications**:
  - Activation notice upon subscription grant.
  - 24-hour expiration reminder.
  - Expiry notice upon completion.
  - Persistent delivery tracking to prevent duplicate alerts upon restart.
- **Atomic JSON Storage**: Concurrency-safe JSON storage engine utilizing temporary files (`.tmp` + `os.replace`), async locks, pre-mutation backup rotation, and automatic quarantine of corrupted files.
- **Hidden `/backup` Command**: Private-chat administrative command generating a sanitized ZIP archive of data files, strictly excluding `.env`, secrets, MTProto session files, and logs.
- **Dual-Layer Logging**: Terminal and rotating file logs, plus an asynchronous alert sink delivering `WARNING`, `ERROR`, and `CRITICAL` alerts to administrators in Persian without recursion.

---

## Tech Stack

- **Python**: `>=3.10`
- **Telegram & MTProto**: `kurigram>=2.2.0`, `tgcrypto>=1.2.0`
- **Configuration & Validation**: `pydantic>=2.7.0`, `pydantic-settings>=2.2.0`
- **Testing**: `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`
- **Linter & Formatter**: `ruff>=0.4.0`

---

## Project Structure

```text
telegram-signal-bot/
├── app/
│   ├── config.py                 # Pydantic Settings & environment validation
│   ├── logging_config.py         # Terminal logs & async Persian admin alert sink
│   ├── main.py                   # Application entrypoint & lifecycle management
│   ├── handlers/
│   │   ├── admin_menu.py         # Menu actions & cancellation flow
│   │   ├── backup.py             # Hidden /backup command handler
│   │   ├── photos.py             # Photo sync callback handler
│   │   ├── publish.py            # Signal submission & preview approval
│   │   ├── signals.py            # Deep-link access & subscription routing
│   │   ├── start.py              # /start router (admin menu vs. user welcome)
│   │   └── subscriptions.py      # Admin subscription creation wizard
│   ├── keyboards/
│   │   ├── admin.py              # Main menu, cancel, preview, and channel keyboards
│   │   └── common.py             # Support link keyboard
│   ├── models/
│   │   ├── metadata.py           # Storage metadata & ID allocation
│   │   ├── photo.py              # PhotoRecord & PhotoCollection schemas
│   │   ├── signal.py             # SignalRecord, SignalDraft, SignalsCollection
│   │   ├── state.py              # In-memory admin conversation state machine
│   │   └── subscription.py       # SubscriptionRecord & SubscriptionCollection
│   ├── services/
│   │   ├── backup_service.py     # Sanitized ZIP archive generator
│   │   ├── photo_service.py      # MTProto channel scanner & deduplication
│   │   ├── publication_service.py# Draft lifecycle & channel publication
│   │   └── subscription_service.py # Expiration checks & background worker
│   ├── storage/
│   │   ├── json_store.py         # Concurrency-safe atomic JSON engine
│   │   └── repositories.py       # Typed entity storage manager
│   └── utils/
│       ├── auth.py               # Private-chat filters & authorization decorator
│       ├── formatting.py         # Regex parsing & span-based caption generator
│       └── messages.py           # Centralized Persian copy constants
├── data/                         # Persistent JSON storage & backups (gitignored)
├── tests/                        # Automated unit & integration tests
├── .env.example                  # Environment configuration template
├── pyproject.toml                # Project metadata & build settings
├── main.py                       # Root execution wrapper
└── README.md
```

---

## Installation & Setup

### 1. Clone & Create Virtual Environment

```bash
git clone git@github.com:pousay/signal-sender.git
cd signal-sender

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```dotenv
# Telegram Bot and MTProto credentials
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
API_ID=1234567
API_HASH=0123456789abcdef0123456789abcdef

# Optional: MTProto user session string for unrestricted channel history scanning
# Generate using: python3 scripts/generate_session.py
# If omitted, bot uses batch message scanning (requires bot to be channel admin)
USER_SESSION_STRING=

# Target channel for signal posts and source channel for photo sync
# Can be numeric ID (e.g., -1001234567890) or @username
CHANNEL_ID=-1001234567890
SOURCE_CHANNEL_ID=-1009876543210

# Comma-separated Telegram numeric user IDs with administrator rights
ADMIN_IDS=123456789,987654321

# Telegram username for support inquiries (without @)
CONTACT_ADMIN_ID=support_admin
```

> [!IMPORTANT]
> - `BOT_TOKEN`: Obtained from [@BotFather](https://t.me/BotFather).
> - `API_ID` & `API_HASH`: Obtained from [my.telegram.org](https://my.telegram.org).
> - The bot must be an **Administrator** in both `CHANNEL_ID` and `SOURCE_CHANNEL_ID` with post/read message permissions.
> - Never commit `.env` or session files to version control.

---

## Running the Bot

Run directly using Python:

```bash
python3 main.py
```

Or via module invocation:

```bash
python3 -m app.main
```

### Single-Instance Lock
The application automatically maintains a file lock (`data/.bot.lock`). If another instance is already running against the same data directory, startup will safely abort to prevent data corruption.

---

## Administrative Workflows

When an administrator (`ADMIN_IDS`) sends `/start` in a private chat, the bot displays the 3-button Persian control panel:

### 1. 📨 ارسال پست (Send Signal)
1. Prompts admin for raw signal text (includes inline `❌ لغو`).
2. Extracts numeric `Sell limit` value (e.g. `Sell limit: 77950`).
3. Selects a random photo from the synchronized collection.
4. Generates public caption replacing only the numeric value with `[مشاهده](...)`.
5. Displays preview photo + caption with inline approval controls:
   - `✅ تأیید و انتشار`
   - `❌ لغو`
6. Upon approval, posts one photo with modified caption and attached button to `CHANNEL_ID`:
   `📝 برای مشاهده مشخصات پـوزیشن کلیک کنید`

### 2. 🖼 بروزرسانی عکس‌ها (Update Photos)
1. Scans `SOURCE_CHANNEL_ID` history:
   - **Mode A (Automatic User Client Session — Default & Recommended)**: If `USER_SESSION_STRING` is not provided in `.env`, the bot automatically initializes a persistent user client session (`data/sessions/user_client.session`). On first run, Kurigram prompts in the terminal for your phone number and Telegram confirmation code. Future runs authenticate seamlessly without prompting.
   - **Mode B (In-Memory Session String)**: If `USER_SESSION_STRING` is set in `.env`, the bot loads the user session directly into memory without creating `.session` files.
   - **Mode C (Bot Admin Batch Fallback)**: If the user client is not authenticated or fails to connect, the bot falls back to batch message scanning via `get_messages()` (requiring the bot to be an **Administrator** in `SOURCE_CHANNEL_ID`).
2. Filters photo messages only (ignores text, voice, documents).
3. Deduplicates photos using `file_unique_id`.
4. Completely replaces stored photo pool on success; retains previous collection on failure.
5. Reports total count and status to administrator in Persian.

#### Optional: Generating a User Session String
If you prefer storing your session entirely in `.env` as a string rather than a `.session` file:
```bash
python3 scripts/generate_session.py
```
Follow the interactive prompts to enter your `API_ID`, `API_HASH`, phone number, and login code. Copy the printed `USER_SESSION_STRING="..."` into `.env`.

### 3. ⭐ ارسال اشتراک ویژه (Send Premium Subscription)
1. Prompts for numeric Telegram user ID (strictly rejects `@username`).
2. Prompts for custom duration in days (1..3650 days).
3. Sets expiration to `now + duration_days` (**replaces** prior expiry).
4. Delivers activation message to user (`اشتراک شما با موفقیت فعال شد.✅`).
5. Alerts admin if the user has not yet started the bot.

### 4. Hidden `/backup` Command
Sending `/backup` in a private chat as an administrator generates and sends a sanitized `.zip` archive containing all JSON data files, strictly excluding `.env` and MTProto credentials.

---

## Testing

Run the automated test suite with pytest:

```bash
pytest -v
```

Run code formatting and lint checks:

```bash
ruff check app tests
```

Verify Python compilation:

```bash
python3 -m compileall -q app tests
```

---

## Security & Data Safety

- **Atomic Writes**: All JSON mutations are written to a unique `.tmp` file in the same directory, flushed, and renamed atomically via `os.replace`.
- **Pre-Mutation Backups**: Backups are rotated automatically in `data/backups/`.
- **Quarantine on Corruption**: Malformed or unparseable JSON files are renamed to `.corrupt_<timestamp>.json` and quarantined rather than silently overwritten.
- **Zero Secret Leakage**: Admin logging alerts redact `BOT_TOKEN` and `API_HASH` automatically.
