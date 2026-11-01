"""Logging configuration with rotating file logs and async Persian admin alerts."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pyrogram import Client
from pyrogram.errors import RPCError

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_logging(
    level: str = "INFO",
    log_dir: Path | str = "logs",
) -> None:
    """Configure terminal output and bounded rotating file logging."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_target = log_path / "app.log"

    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # 1. Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)

    # 2. Bounded rotating file handler (5 MB max, 3 rotations)
    file_handler = RotatingFileHandler(
        filename=file_target,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Quiet noisy third-party libraries
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


class AdminAlertHandler(logging.Handler):
    """Custom log handler capturing WARNING+ records and queueing Persian Telegram alerts."""

    def __init__(self, settings: Settings, alert_queue: asyncio.Queue) -> None:
        super().__init__(level=logging.WARNING)
        self.settings = settings
        self.alert_queue = alert_queue
        self._recent_signatures: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.WARNING:
            return

        # Prevent recursive notification loops
        if record.name.startswith(("pyrogram", "urllib3", "app.logging_config")):
            return

        message = record.getMessage()

        # Redact known secrets from alerts
        if self.settings.BOT_TOKEN in message:
            message = message.replace(self.settings.BOT_TOKEN, "[REDACTED_BOT_TOKEN]")
        if self.settings.API_HASH in message:
            message = message.replace(self.settings.API_HASH, "[REDACTED_API_HASH]")

        # Rate-limit duplicate alerts within 60s window
        now_ts = datetime.now(timezone.utc).timestamp()
        sig = f"{record.name}:{record.levelno}:{message}"
        last_seen = self._recent_signatures.get(sig, 0)
        if (now_ts - last_seen) < 60:
            return
        self._recent_signatures[sig] = now_ts

        # Prune old cache signatures periodically
        if len(self._recent_signatures) > 1000:
            self._recent_signatures = {
                k: v for k, v in self._recent_signatures.items() if (now_ts - v) < 60
            }

        persian_level = {
            "WARNING": "⚠️ هشدار",
            "ERROR": "❌ خطا",
            "CRITICAL": "🚨 خطای بحرانی",
        }.get(record.levelname, record.levelname)

        alert_text = (
            f"{persian_level}\n"
            f"ماژول: `{record.name}`\n"
            f"پیام: {message[:300]}"
        )

        try:
            self.alert_queue.put_nowait(alert_text)
        except Exception:
            pass


class AdminNotifierService:
    """Dispatches queued log alerts asynchronously to configured administrators."""

    def __init__(self, client: Client, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self.handler: AdminAlertHandler | None = None
        self._drain_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def attach_handler(self) -> None:
        """Attach logging handler to the root logger."""
        self.handler = AdminAlertHandler(self.settings, self.alert_queue)
        logging.getLogger().addHandler(self.handler)

    def detach_handler(self) -> None:
        """Detach logging handler from the root logger."""
        if self.handler:
            logging.getLogger().removeHandler(self.handler)
            self.handler = None

    async def start(self) -> None:
        """Start background queue processor delivering alerts to admins."""
        self.attach_handler()
        self._stop_event.clear()

        async def _drain():
            while not self._stop_event.is_set():
                try:
                    alert = await asyncio.wait_for(self.alert_queue.get(), timeout=1.0)
                    for admin_id in self.settings.ADMIN_IDS:
                        try:
                            await self.client.send_message(chat_id=admin_id, text=alert)
                        except RPCError as e:
                            # Avoid recursive logging: write to sys.stderr or drop quietly
                            sys.stderr.write(
                                f"Failed to deliver log alert to admin {admin_id}: {e}\n"
                            )
                        except Exception as e:
                            sys.stderr.write(f"Unexpected error in alert delivery: {e}\n")
                    self.alert_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    sys.stderr.write(f"Notifier worker exception: {e}\n")

        self._drain_task = asyncio.create_task(_drain())

    async def stop(self) -> None:
        """Stop background worker and detach handler."""
        self._stop_event.set()
        if self._drain_task:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
            self._drain_task = None
        self.detach_handler()
