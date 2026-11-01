---
name: tg-notify
description: Send Telegram notifications about task progress, completion, failures, and important updates using the project's tg-notify CLI.
compatibility: opencode
---

# Telegram Notifications

Use the `tg-notify` CLI to notify the user about important task progress.

## Commands

- `tg-notify start "description"` — notify when starting a substantial task.
- `tg-notify finish "summary"` — notify when the task is successfully completed.
- `tg-notify fail "reason"` — notify when the task fails or cannot be completed.
- `tg-notify msg "message"` — send a raw message without a status prefix.

## Rules

1. For substantial tasks, send `start` before beginning work.
2. Send `finish` after successfully completing the task. Summarize the result briefly.
3. Send `fail` if the task fails or cannot be completed. State the reason briefly.
4. Use `msg` for important updates that do not fit the other categories.
5. Do not send unnecessary notifications for trivial questions or small conversational replies.
6. Never claim a notification was sent unless the command succeeds.
7. Do not expose the bot token or configuration contents.
8. Execute the command directly through the shell. Quote message arguments safely.
9. If the command is unavailable or fails, report that to the user instead of repeatedly retrying.
EOF