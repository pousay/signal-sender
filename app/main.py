"""Application entrypoint coordinating startup, lifecycle, and graceful shutdown."""

import asyncio
import fcntl
import logging
import signal
import sys
from contextlib import suppress

from pyrogram import Client

from app.config import Settings
from app.handlers import register_all_handlers
from app.logging_config import AdminNotifierService, setup_logging
from app.models.state import StateManager
from app.services import (
    BackupService,
    PhotoService,
    PublicationService,
    SubscriptionService,
)
from app.storage.repositories import StorageManager

logger = logging.getLogger(__name__)


class Application:
    """Master application coordinator managing services and lifecycle."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.storage = StorageManager(self.settings.DATA_DIR)
        self.state_manager = StateManager()

        # MTProto Bot Client session directory
        session_dir = self.settings.DATA_DIR / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)

        self.client = Client(
            name="signal_bot",
            api_id=self.settings.API_ID,
            api_hash=self.settings.API_HASH,
            bot_token=self.settings.BOT_TOKEN,
            workdir=str(session_dir),
        )

        self.photo_service = PhotoService(self.client, self.settings, self.storage)
        self.publication_service = PublicationService(
            self.client, self.settings, self.storage, self.photo_service
        )
        self.subscription_service = SubscriptionService(
            self.client, self.settings, self.storage
        )
        self.backup_service = BackupService(self.settings)
        self.notifier_service = AdminNotifierService(self.client, self.settings)

        self._lock_file = None
        self._shutdown_event = asyncio.Event()

    def acquire_single_instance_lock(self) -> None:
        """Prevent multiple concurrent writers from corrupting JSON data storage."""
        lock_path = self.settings.DATA_DIR / ".bot.lock"
        self.settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

        try:
            self._lock_file = open(lock_path, "w")
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_file.write(str(sys.platform))
            self._lock_file.flush()
        except (BlockingIOError, OSError) as err:
            logger.critical("Another bot instance is already active and holds the data lock.")
            raise RuntimeError(
                f"Cannot acquire storage lock on {lock_path}. Is another bot instance running?"
            ) from err

    def release_single_instance_lock(self) -> None:
        """Release the file lock upon shutdown."""
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                self._lock_file.close()
            except Exception as e:
                logger.warning("Error releasing single instance lock: %s", e)
            self._lock_file = None

    async def start(self) -> None:
        """Bootstrap storage, register handlers, and start background workers."""
        self.acquire_single_instance_lock()
        await self.storage.initialize()

        register_all_handlers(
            app=self.client,
            settings=self.settings,
            storage=self.storage,
            state_manager=self.state_manager,
            photo_service=self.photo_service,
            publication_service=self.publication_service,
            subscription_service=self.subscription_service,
            backup_service=self.backup_service,
        )

        logger.info("Connecting MTProto bot client...")
        await self.client.start()

        # Discover bot username dynamically
        me = await self.client.get_me()
        self.settings.BOT_USERNAME = me.username or "bot"
        logger.info("Bot authenticated successfully as @%s (ID: %d)", me.username, me.id)

        # Launch background workers
        await self.subscription_service.start_reminder_worker(interval_seconds=60)
        await self.notifier_service.start()

        logger.info("Bot is active and listening for interactions.")

    async def stop(self) -> None:
        """Execute graceful shutdown of workers, clients, and resource locks."""
        logger.info("Initiating graceful shutdown...")

        with suppress(Exception):
            await self.subscription_service.stop_reminder_worker()

        with suppress(Exception):
            await self.notifier_service.stop()

        if self.client.is_connected:
            with suppress(Exception):
                await self.client.stop()

        self.release_single_instance_lock()
        logger.info("Shutdown completed successfully.")

    async def run(self) -> None:
        """Run application until interrupted by termination signal."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                pass

        try:
            await self.start()
            # Wait for shutdown signal or idle
            await self._shutdown_event.wait()
        finally:
            await self.stop()


def main() -> None:
    """CLI entrypoint."""
    setup_logging()
    app = Application()
    try:
        asyncio.run(app.run())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.critical("Fatal error starting bot: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
