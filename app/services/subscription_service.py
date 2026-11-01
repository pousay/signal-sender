"""Subscription management service with background expiration and reminder processing."""

import asyncio
import logging
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.errors import RPCError

from app.config import Settings
from app.models.subscription import SubscriptionRecord
from app.storage.repositories import StorageManager
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class SubscriptionServiceError(Exception):
    """Base exception for subscription operations."""


class SubscriptionService:
    """Manages subscription creation, access checks, and background notifications."""

    def __init__(
        self,
        client: Client,
        settings: Settings,
        storage: StorageManager,
    ) -> None:
        self.client = client
        self.settings = settings
        self.storage = storage
        self._worker_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def set_subscription(
        self,
        user_id: int,
        duration_days: int,
    ) -> tuple[SubscriptionRecord, bool]:
        """Activate or replace a user's subscription duration.

        Replaces prior subscription completely with now + duration_days.
        Attempts to deliver an activation message to the user. Returns (record, user_notified).
        """
        if user_id <= 0:
            raise ValueError(f"Invalid user ID: {user_id}. Must be positive integer.")
        if duration_days <= 0 or duration_days > self.settings.MAX_SUBSCRIPTION_DAYS:
            raise ValueError(
                f"Duration {duration_days} outside permitted range "
                f"(1..{self.settings.MAX_SUBSCRIPTION_DAYS})"
            )

        now = utc_now()
        record: SubscriptionRecord | None = None

        def _mutate(col):
            nonlocal record
            record = col.set_subscription(user_id=user_id, duration_days=duration_days, now=now)

        await self.storage.subscriptions.mutate(_mutate, make_backup=True)
        assert record is not None

        # Attempt to deliver activation message to user
        user_notified = False
        try:
            await self.client.send_message(
                chat_id=user_id,
                text=Messages.SUBSCRIPTION_ACTIVATED_USER,
            )
            user_notified = True
            logger.info("Sent subscription activation message to user %d", user_id)
        except RPCError as e:
            logger.warning(
                "Could not send activation message to user %d (user may not have started bot): %s",
                user_id,
                e,
            )
        except Exception as e:
            logger.error("Unexpected error notifying user %d: %s", user_id, e)

        return record, user_notified

    async def is_premium_active(self, user_id: int, now: datetime | None = None) -> bool:
        """Check synchronously whether a user holds an active premium subscription."""
        collection = await self.storage.subscriptions.load()
        sub = collection.get(user_id)
        if not sub:
            return False
        return sub.is_active(now or utc_now())

    async def process_expirations_and_reminders(
        self, now: datetime | None = None
    ) -> tuple[int, int]:
        """Scan all subscriptions to deliver 24h reminders and expiration notices.

        Tracks notification status in storage to prevent duplicate alerts upon restart.
        Returns (reminders_sent, expirations_sent).
        """
        current_time = now or utc_now()
        reminders_sent = 0
        expirations_sent = 0

        async def _check_and_notify(col):
            nonlocal reminders_sent, expirations_sent
            for sub in col.subscriptions.values():
                # 1. 24-hour expiration reminder
                if sub.is_due_for_24h_reminder(current_time):
                    try:
                        reminder_text = Messages.SUBSCRIPTION_REMINDER_24H.format(
                            support_link=f"@{self.settings.CONTACT_ADMIN_ID}"
                        )
                        await self.client.send_message(
                            chat_id=sub.user_id,
                            text=reminder_text,
                        )
                        sub.reminder_24h_sent = True
                        reminders_sent += 1
                        logger.info("Delivered 24h expiration reminder to user %d", sub.user_id)
                    except RPCError as e:
                        logger.warning(
                            "Failed to deliver reminder to user %d: %s", sub.user_id, e
                        )
                    except Exception as e:
                        logger.error("Error sending reminder to %d: %s", sub.user_id, e)

                # 2. Expiration notification
                if sub.is_expired(current_time) and not sub.expired_notified:
                    try:
                        await self.client.send_message(
                            chat_id=sub.user_id,
                            text=Messages.SUBSCRIPTION_EXPIRED_USER,
                        )
                        sub.expired_notified = True
                        expirations_sent += 1
                        logger.info("Delivered expiration notice to user %d", sub.user_id)
                    except RPCError as e:
                        logger.warning(
                            "Failed to deliver expiration notice to user %d: %s", sub.user_id, e
                        )
                        sub.expired_notified = True  # Prevent tight error retry loops
                    except Exception as e:
                        logger.error("Error sending expiration notice to %d: %s", sub.user_id, e)
                        sub.expired_notified = True

        await self.storage.subscriptions.mutate(_check_and_notify, make_backup=False)
        return reminders_sent, expirations_sent

    async def start_reminder_worker(self, interval_seconds: int = 60) -> None:
        """Launch background task checking periodically for expirations and reminders."""
        self._stop_event.clear()

        async def _loop():
            logger.info("Subscription expiration/reminder worker started")
            while not self._stop_event.is_set():
                try:
                    await self.process_expirations_and_reminders()
                except Exception as e:
                    logger.error("Error in reminder worker iteration: %s", e)

                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval_seconds)
                except asyncio.TimeoutError:
                    pass

        self._worker_task = asyncio.create_task(_loop())

    async def stop_reminder_worker(self) -> None:
        """Signal and await background worker termination."""
        self._stop_event.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
            logger.info("Subscription expiration/reminder worker stopped cleanly")
