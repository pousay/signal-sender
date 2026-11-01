# Telegram Premium Signal Bot — Implementation Specification

## 1. Role and objective

Act as a senior Python engineer. Build a production-minded Telegram bot from scratch using **Kurigram**, **MTProto**, **asyncio**, and **Pydantic**.

The bot manages a Persian trading-signal channel. It publishes each signal as the caption of a randomly selected photo, hides the `Sell limit` value behind a clickable `مشاهده` link, and delivers the real signal details to users with an active premium subscription.

The implementation must be professional, modular, typed, testable, secure, and maintainable. Prefer mature, well-maintained packages over hand-rolled infrastructure. Do not overengineer, but do not put the entire application in one file.

**Every user-facing bot message and every inline-button label must be in Persian.** Code identifiers, internal logs, exception details, and developer documentation may be in English.

## 2. Required technology

- Python 3.11+ (use the project's selected supported version consistently).
- Kurigram for Telegram integration, including MTProto functionality needed to read channel history.
- `asyncio` throughout; do not introduce synchronous network operations into async handlers.
- Pydantic v2 for configuration and validation.
- `pydantic-settings` for `.env` configuration.
- JSON files for persistent application data; do not introduce a database.
- `pytest` and `pytest-asyncio` for tests.
- A standard Python logging setup with terminal output and admin notifications for warnings and errors.
- Use professional, actively maintained packages where they provide real value. Pin compatible dependency ranges in `pyproject.toml` or the chosen dependency manager's configuration.
- Use a formatter/linter such as Ruff and add type hints throughout.

Before coding, verify Kurigram's current API and MTProto capabilities from its installed/current documentation. Do not invent methods or assume the ordinary Bot API can enumerate arbitrary historical channel messages. Use Kurigram's MTProto client correctly to retrieve the source channel's history and photos. Clearly document any required account/session setup.

## 3. Environment configuration

Provide `.env.example` and validate configuration at startup with Pydantic Settings.

Required settings:

```dotenv
BOT_TOKEN=
API_ID=
API_HASH=

CHANNEL_ID=
SOURCE_CHANNEL_ID=

ADMIN_IDS=
CONTACT_ADMIN_ID=
```

Requirements:

- `BOT_TOKEN`: bot token.
- `API_ID` and `API_HASH`: MTProto API credentials.
- `CHANNEL_ID`: target channel where public signal posts are published.
- `SOURCE_CHANNEL_ID`: channel whose entire available history is scanned for photos.
- `ADMIN_IDS`: list of Telegram numeric user IDs allowed to administer the bot. Support a documented, unambiguous environment syntax (for example, comma-separated IDs) and parse it into a typed collection.
- `CONTACT_ADMIN_ID`: support username used in the non-premium message. Normalize/validate the expected username form and build a safe Telegram link without accidentally displaying a raw numeric ID as a username.

Never commit `.env`, bot tokens, API hashes, or MTProto session files. Add them to `.gitignore`. Do not print secrets in logs or include them in user-visible errors.

## 4. Project structure

Use a clean structure along these lines; adjust only where a clear engineering reason exists:

```text
telegram-signal-bot/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── admin_menu.py
│   │   ├── photos.py
│   │   ├── publish.py
│   │   ├── subscriptions.py
│   │   ├── signals.py
│   │   └── backup.py
│   ├── keyboards/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   └── common.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── photo.py
│   │   ├── signal.py
│   │   ├── subscription.py
│   │   └── state.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── photo_service.py
│   │   ├── signal_service.py
│   │   ├── subscription_service.py
│   │   ├── publication_service.py
│   │   ├── backup_service.py
│   │   └── admin_notifier.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── json_store.py
│   │   └── repositories.py
│   └── utils/
│       ├── __init__.py
│       └── formatting.py
├── data/
│   └── .gitkeep
├── tests/
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
└── ...
```

Use Kurigram's appropriate handler/state mechanism or a well-integrated state-management approach for multi-step admin flows. Do not create a parallel, fragile conversation-state system if the framework already provides a suitable one.

## 5. Main admin menu and authorization

When an admin opens the bot in a private chat with `/start`, display a Persian welcome/instructions message and these three inline buttons:

- `📨 ارسال پست`
- `🖼 بروزرسانی عکس‌ها`
- `⭐ ارسال اشتراک ویژه`

The main menu must remain limited to these three options. Do not add subscription-management buttons.

All IDs in `ADMIN_IDS` have the same permissions.

Security requirements:

- Allow admin workflows only in private chats.
- Verify the sender's numeric Telegram ID against `ADMIN_IDS` on **every** sensitive handler and callback. Never rely on hidden buttons or UI visibility for authorization.
- Validate callback payloads and user input server-side.
- A non-admin must not be able to invoke administrative actions by constructing callback data manually.
- Provide an inline `❌ لغو` button at every step of each multi-step workflow. This is a button, not merely a `/cancel` command.
- Cancelling must safely clear that user's pending flow and remove or invalidate obsolete workflow controls.
- Prevent one admin's workflow state from interfering with another admin's state.
- Give ordinary users a Persian welcome/instructions response, including how to obtain a subscription and contact support.
- Handle unexpected exceptions without exposing tracebacks, secrets, file paths, or internal details to users.

## 6. Photo-channel synchronization

The bot has two distinct channels:

1. `SOURCE_CHANNEL_ID`: source of photos only.
2. `CHANNEL_ID`: destination for published signal posts.

When an admin presses `🖼 بروزرسانی عکس‌ها`:

1. Use Kurigram's MTProto functionality to retrieve the source channel's entire available message history, handling pagination correctly.
2. Extract Telegram photo messages only. Ignore text-only messages and other media types. Do not treat document-uploaded images as photos unless Telegram represents them as photo messages.
3. Collect reusable Telegram `file_id` values (or the appropriate reusable identifiers exposed by Kurigram). Persist only what is required to send the photos again; do not store downloaded image bytes unless technically necessary.
4. Deduplicate photos if the same underlying photo is encountered more than once, using a stable identifier when available.
5. Replace the existing photo collection **entirely** with the newly collected collection. This is intentional: photos removed from the source channel should no longer remain available for random selection.
6. If synchronization succeeds with zero photos, report the result and leave the application in a safe state that prevents publishing without a photo. Do not silently continue using stale photos.
7. If synchronization fails partway through, do not overwrite a valid stored collection with a partial result. Report failure and retain the last known-good collection.
8. Log start, completion, counts, duration, and errors. Send an appropriate Persian report to admins, including the number of photos found and stored.

Use the supported Kurigram MTProto/session setup required for reading history. Document it in the README. Keep bot-token operation and any user-authorized MTProto session requirements clear; never attempt to bypass Telegram authorization.

## 7. Signal submission and preview workflow

When an admin selects `📨 ارسال پست`:

1. Ask the admin in Persian to send/paste the signal text. Include the inline `❌ لغو` button.
2. Accept a text message only. The bot must publish exactly one photo per signal; media-group publishing is not required.
3. Parse the signal and extract the numeric value belonging to the `Sell limit` field.
4. If `Sell limit` is missing, ambiguous, or cannot be safely extracted, reject the draft with a Persian error. Do not publish anything.
5. Select one photo randomly from the current synchronized photo collection. Every stored photo should have an equal chance; repeated use of the same photo on consecutive posts is allowed.
6. Construct a public caption by changing **only the value of the `Sell limit` field** to the clickable text `مشاهده`. Preserve all other user-provided content and formatting as closely as Telegram permits:
   - Persian and English text
   - Line breaks and spacing
   - Emojis and hashtags
   - Other numeric values
   - All other text and punctuation
7. The `مشاهده` text must link to the bot's deep link for this exact signal. Disable link previews for the relevant messages.
8. Prepare the complete draft and show the admin a preview of the photo plus the modified caption, with inline buttons:
   - `✅ تأیید و انتشار`
   - `❌ لغو`
9. Do not publish to the target channel until the admin explicitly approves.
10. On approval, publish **one photo with the modified caption and inline keyboard attached to that same post**. Do not send the button as a separate message.
11. The exact button label under the published post must be:
    `📝 برای مشاهده مشخصات پـوزیشن کلیک کنید`
12. The post caption must contain the modified `Sell limit` link and the button must use the same access logic.
13. If publication fails, retain the draft and offer a Persian retry action rather than forcing the admin to compose it again.
14. Prevent accidental duplicate publication caused by repeated approval callbacks or Telegram retries. Track draft/publication status and make handlers idempotent where possible.
15. On success, report the published message ID and status to the admin in Persian, and log the publication.

### Preserve formatting safely

Do not perform a global text replacement. Identify only the `Sell limit` value and replace only that value with a link entity, preserving the rest of the caption.

Use Telegram's supported entity/formatting mechanisms correctly. If the incoming text has Telegram entities, preserve and adjust entity offsets as needed, or use a robust formatter that produces an equivalent caption. Do not assume Markdown/HTML parsing will preserve arbitrary original formatting. If exact formatting cannot be preserved safely, reject the draft with a clear Persian explanation rather than silently corrupting the caption.

Telegram photo captions have length limits. Validate the final caption against Telegram's applicable limit before preview/publication and report an understandable Persian error if it is too long.

## 8. Signal identifiers and deep links

Each draft/signal must have a unique, stable identifier. Persist the signal data before generating links that refer to it.

Use a bot deep link of this form:

```text
https://t.me/{BOT_USERNAME}?start=175
```

Here, `175` is an example signal identifier, not a fixed value. Determine the bot's username using the appropriate Telegram method at startup; do not add a separate required `BOT_USERNAME` environment variable unless the framework makes that unavoidable.

When a user opens the link:

1. Parse and validate the start parameter.
2. Load the exact signal by identifier.
3. If it does not exist, return a Persian message saying the signal is unavailable.
4. Check the user's subscription against the current time.
5. If premium is active, send the real position details in a private chat.
6. Otherwise, send the configured non-premium message and support link.

The link on `مشاهده` and the inline button under the post must both identify the same signal and enforce the same subscription check. Do not trust signal IDs supplied by users without validation.

## 9. Premium access and signal details

If the user has an active subscription and requests a signal, send the relevant actual values in Persian. For the example sell signal:

```text
🔹 Sell limit: 77950
🔹 Stop loss: 78650
🔹 Target: 76900
```

Extract and store the `Sell limit` value from the original admin-submitted signal. Preserve the original values needed for the private response. The public caption must never reveal the original `Sell limit` value.

If the user does not have an active subscription, send this Persian message, with the support username from `CONTACT_ADMIN_ID` rendered as a clickable Telegram link:

```text
⚠️ برای مشاهده مشخصات پوزیشن،
جهت تهیه اشتراک به ادمین کانال پیام دهید:

🆔 : @support_username
```

Replace `@support_username` with the configured value. Do not expose a placeholder in production.

Access must be checked on every request; do not cache premium status indefinitely. The private response should be sent only in the user's private chat. Handle the case where the user has not started the bot or the bot cannot message them with a suitable admin-visible error.

## 10. Premium subscription workflow

When an admin selects `⭐ ارسال اشتراک ویژه`:

1. Ask for the user's **numeric Telegram user ID**, not a username.
2. Validate that the input is a valid positive integer. Do not accept `@username` as a substitute.
3. Ask the admin to enter the duration in days. The duration is custom, so the admin enters a positive integer. Include `❌ لغو` at each step.
4. Set the user's expiration to `now + duration`. **Replace**, rather than extend, any existing subscription expiration. Example: replacing a 20-day subscription with 30 days results in 30 days from activation time.
5. Persist the change safely before reporting success.
6. Send the user this activation message in Persian:

```text
اشتراک شما با موفقیت فعال شد.✅

از همراهی شما سپاسگزاریم.🌹
```

Include the expiration date/time in Persian if this can be added without changing the required message's wording; otherwise keep the required message exactly and send the expiration separately only if useful.
7. Confirm the activation to the admin in Persian.
8. If the bot cannot message the user (for example, the user has not started the bot), do not undo the subscription silently. Explain to the admin that the subscription was saved but the notification could not be delivered, and ask them to tell the user to start the bot.
9. Validate that the duration is within a reasonable configurable safety bound, or clearly document the chosen maximum. Reject zero, negative, malformed, or unreasonably large values.

Do not add user-management, status-checking, or revocation buttons to the main admin menu.

## 11. Expiration and reminders

- Check subscriptions periodically using an asynchronous background task.
- Also check expiration synchronously at the point of premium-content access.
- Send an expiration reminder 24 hours before expiry.
- Send the expiration message when the subscription expires:

```text
اشتراک شما به پایان رسید.

از همراهی شما سپاسگزاریم.🌹
```

- Use timezone-aware UTC timestamps internally. Format displayed dates in a consistent, user-friendly way; document the timezone used for Persian date/time display.
- Track reminder and expiration-notification delivery state so bot restarts do not send duplicate notifications.
- If the bot is offline at a scheduled time, reconcile due reminders and expired subscriptions after restart. Do not spam users with repeated overdue notifications; define and test the catch-up policy.
- If a subscription is replaced before an old reminder is due, cancel or invalidate the old reminder and schedule against the new expiration.
- Handle Telegram delivery failures with logging and a retry policy that does not create notification loops.

## 12. JSON persistence and data safety

Use JSON as requested, with separate files, for example:

```text
data/
├── photos.json
├── signals.json
├── subscriptions.json
├── drafts.json
└── metadata.json
```

Use Pydantic models to validate both loaded and newly written data. Define explicit schemas, versions, and serialization rules.

Requirements:

- Atomic writes: write to a temporary file in the same directory, flush/close it safely, then replace the destination atomically.
- Create a backup before important data mutations.
- Validate files on startup and produce clear logs if malformed or incompatible.
- Never silently reset corrupted data or overwrite it with empty defaults. Preserve the corrupt file, report the issue, and use a safe recovery procedure.
- Protect concurrent writes with a central async storage/repository layer and appropriate locking. Do not allow independent handlers to race while writing the same JSON file.
- Store UTC timestamps in a consistent ISO 8601 format.
- Keep data schemas typed and versioned so future migrations can be performed.
- Document that JSON storage is suitable for a single running bot instance; do not run multiple writers against the same data directory.
- Do not claim absolute data-loss prevention. Implement recoverable writes, backups, and clear failure behavior.

## 13. Hidden `/backup` command

Implement `/backup` as a hidden command, not a main-menu button.

- Only users whose numeric IDs are in `ADMIN_IDS` may invoke it.
- It must work only in private chats.
- Create a consistent backup containing application settings files and JSON data files.
- Include `.env` only if explicitly enabled by a clearly documented configuration option; the safe default is **exclude `.env` and all secrets**. The request to back up settings files must not accidentally leak `BOT_TOKEN`, `API_HASH`, or MTProto session credentials to Telegram.
- Prefer a ZIP archive with a timestamped filename.
- Exclude logs, virtual environments, caches, temporary files, Git metadata, and secrets.
- Validate archive paths and prevent path traversal.
- Send the archive to the requesting authorized admin and clean up temporary artifacts.
- Log the backup operation and notify admins if it fails.
- If including any sensitive configuration is ever enabled explicitly, warn about the exposure risk and require deliberate opt-in. Never include MTProto session files or tokens by default.

## 14. Logging and admin notifications

Implement a complete logging system.

- Terminal logs for DEBUG, INFO, WARNING, ERROR, and CRITICAL, with timestamps, severity, module/logger name, and useful context.
- Use a rotating file log if appropriate, without allowing logs to grow without bound. Keep logs out of backup archives unless explicitly requested.
- Send `WARNING`, `ERROR`, and `CRITICAL` notifications to configured admins. INFO and DEBUG remain in terminal/file logs only.
- Admin notifications must be in Persian, concise, actionable, and avoid secrets or excessive tracebacks.
- Full exception traceback and technical context belong in terminal/file logs, not Telegram.
- Avoid recursive notification loops when Telegram is unavailable or notification delivery fails.
- Batch/rate-limit repeated identical notifications and handle Telegram rate limits.
- Include useful context such as operation, admin/user/signal ID when safe, and correlation ID where practical.
- Ensure logging failures never crash the main bot process.

## 15. Welcome, cancel, and error messages

Every message shown to users or admins must be Persian. Use a centralized message/constants module to keep copy consistent.

At minimum, define Persian messages for:

- Ordinary user welcome and instructions.
- Admin welcome and instructions.
- Unauthorized access.
- Prompt to submit a signal.
- Prompt for numeric user ID.
- Prompt for duration in days.
- Invalid input.
- Missing or invalid `Sell limit`.
- No photos available.
- Preview and approval.
- Publication success/failure and retry.
- Photo synchronization progress/result/failure.
- Subscription activation and expiration.
- Expiration reminder.
- Signal not found.
- Premium-required/support contact.
- Cancellation at every workflow stage.
- Backup success/failure.
- Unexpected error.

Use the exact specified messages and button labels where provided. Do not translate Persian copy into English in the implementation.

## 16. Suggested Pydantic data models

Design models with clear validation and schema versions. These are suggested fields, not a requirement to copy blindly.

### Photo record
- Stable photo identifier.
- Reusable Telegram photo `file_id`/identifier.
- Optional source message ID.
- Synchronization timestamp.

### Signal record
- Unique signal ID used by deep links.
- Original signal text and, where necessary, original Telegram entities.
- Public caption or enough safe data to reconstruct it.
- Extracted `Sell limit` value.
- Other private fields required to respond to a premium user.
- Selected photo reference.
- Target channel ID and published message ID.
- Created/published timestamps.
- Draft/publication status and idempotency information.

### Subscription record
- Numeric Telegram user ID.
- UTC expiration timestamp.
- Activation/update timestamp.
- Last duration applied if useful.
- Last reminder and expiration-notification status.

### Draft record
- Draft ID.
- Admin ID who created it.
- Original text and parsed fields.
- Selected photo.
- Preview/publication status.
- Creation timestamp and expiry/cleanup policy.

### Metadata
- Schema version.
- Next signal ID or another safe ID-generation mechanism.
- Last successful photo synchronization timestamp.
- Other minimal operational metadata.

Do not persist redundant or unnecessary fields. Validate identifiers and timestamps, and avoid serializing secrets.

## 17. Reliability, lifecycle, and security

- Start and stop Kurigram clients cleanly.
- Register handlers and background jobs deterministically.
- Handle SIGINT/SIGTERM and close clients/files cleanly.
- Avoid duplicate background schedulers.
- Ensure only one instance writes to the JSON data directory; use a single-instance lock if practical.
- Never trust callback data, start parameters, or user-supplied values.
- Escape or safely represent untrusted text where applicable.
- Do not execute shell commands based on user input.
- Use a secure, minimal `.gitignore`.
- Do not log tokens, API hashes, session strings, or full `.env` contents.
- Handle Telegram flood waits/rate limits according to Kurigram's supported mechanisms.
- Ensure failures in optional admin notifications do not terminate the bot.
- Add clear startup validation and fail fast for missing or invalid configuration.
- Use no `systemd` deployment requirement; the user explicitly does not want it included.

## 18. Tests and acceptance criteria

Create automated tests for at least:

1. Pydantic configuration parsing and invalid configuration.
2. Admin authorization, including unauthorized callback attempts.
3. Parsing valid `Sell limit` values.
4. Rejecting missing, malformed, or ambiguous `Sell limit`.
5. Replacing only the `Sell limit` value while preserving the rest of the text/entities.
6. Correct signal deep-link generation and parsing.
7. Premium access before expiry and denial at/after expiry.
8. Replacing an existing subscription duration instead of extending it.
9. Reminder scheduling and duplicate-notification prevention.
10. JSON atomic persistence and recovery behavior.
11. Photo synchronization replacing the full collection on success and preserving the previous collection on failure.
12. Refusing publication when no valid photo exists.
13. Preview/approval flow and cancellation.
14. Preventing duplicate publication on repeated approval callbacks.
15. Hidden `/backup` authorization and secret/session-file exclusion.
16. Logging notification failure without crashing the bot.

Use mocked Telegram clients for most tests; tests must not require real Telegram credentials or publish to real channels.

### Definition of done

The project is complete when:

- A fresh installation can be configured using `.env.example` and documented setup steps.
- All required features work through Kurigram with async handlers.
- The MTProto photo-history reader is implemented using verified Kurigram APIs.
- All user-facing copy and inline buttons are Persian.
- The target channel receives one photo with the modified signal caption and the correct inline button.
- Only the `Sell limit` value is hidden publicly; premium users receive the real values privately.
- Both the caption link and inline button use the same subscription check.
- Custom-duration subscriptions replace prior expiry and generate activation, reminder, and expiration notifications.
- JSON state survives restarts and has atomic writes, backups, validation, and safe corruption handling.
- The hidden `/backup` command is admin-only and excludes secrets by default.
- Logs appear in the terminal and WARNING/ERROR/CRITICAL notifications are sent to admins without leaking secrets.
- Automated tests pass.
- README explains installation, environment variables, MTProto session setup, running the bot, data files, backups, logging, limitations, and troubleshooting.

## 19. Instructions to the coding agent

1. Inspect the current working directory before making changes. The project is new, but do not overwrite unrelated files blindly.
2. Verify the current Kurigram package/version and read its API documentation for the exact MTProto history and photo identifier methods. Do not invent APIs.
3. Implement the complete working project, not just a plan or illustrative snippets.
4. Use Pydantic models and settings rather than unvalidated dictionaries throughout the application.
5. Keep functions small, typed, and focused; separate Telegram handlers from business logic and persistence.
6. Add tests as features are implemented and run them before finishing.
7. Do not leave placeholder implementations, TODOs for required features, fake success responses, or unimplemented handlers.
8. If Telegram/Kurigram imposes a real limitation, document it accurately and implement the best supported solution rather than pretending it works.
9. Provide a concise final report listing the implemented features, setup/run commands, test results, and any remaining limitations.
