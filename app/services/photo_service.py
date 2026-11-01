"""Service managing MTProto photo channel synchronization and selection."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from pyrogram import Client

from app.config import Settings
from app.models.photo import PhotoCollection, PhotoRecord
from app.storage.repositories import StorageManager
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class PhotoSyncResult:
    """Outcome of a photo channel synchronization process."""

    success: bool
    count: int = 0
    duration_seconds: float = 0.0
    error: str | None = None


class PhotoService:
    """Orchestrates MTProto channel message retrieval, deduplication, and persistence."""

    def __init__(
        self,
        client: Client,
        settings: Settings,
        storage: StorageManager,
        user_client: Client | None = None,
    ) -> None:
        self.client = client
        self.bot_client = client
        self.user_client = user_client
        self.settings = settings
        self.storage = storage

    async def _scan_via_user_client(
        self, source_channel: int | str, limit: int = 0
    ) -> list[PhotoRecord]:
        """Scan channel history using MTProto user client with get_chat_history."""
        if not self.user_client:
            raise RuntimeError("User client is not configured")

        collected_photos: list[PhotoRecord] = []
        seen_unique_ids: set[str] = set()

        async for message in self.user_client.get_chat_history(
            chat_id=source_channel, limit=limit
        ):
            if message and not getattr(message, "empty", False) and message.photo:
                photo = message.photo
                unique_id = photo.file_unique_id
                if unique_id and unique_id not in seen_unique_ids:
                    seen_unique_ids.add(unique_id)
                    collected_photos.append(
                        PhotoRecord(
                            file_id=photo.file_id,
                            file_unique_id=unique_id,
                            message_id=message.id,
                            synced_at=utc_now(),
                        )
                    )

        return collected_photos

    async def _scan_via_history(
        self, client: Client, source_channel: int | str, limit: int = 0
    ) -> list[PhotoRecord]:
        """Scan channel history using provided client's get_chat_history."""
        collected_photos: list[PhotoRecord] = []
        seen_unique_ids: set[str] = set()

        async for message in client.get_chat_history(
            chat_id=source_channel, limit=limit
        ):
            if message and not getattr(message, "empty", False) and message.photo:
                photo = message.photo
                unique_id = photo.file_unique_id
                if unique_id and unique_id not in seen_unique_ids:
                    seen_unique_ids.add(unique_id)
                    collected_photos.append(
                        PhotoRecord(
                            file_id=photo.file_id,
                            file_unique_id=unique_id,
                            message_id=message.id,
                            synced_at=utc_now(),
                        )
                    )

        return collected_photos

    async def _scan_via_bot_client(
        self, source_channel: int | str, limit: int = 0
    ) -> list[PhotoRecord]:
        """Scan channel messages using batch get_messages for bot accounts.

        Bots cannot invoke MTProto messages.GetHistory, but can fetch batches
        of messages by identifier up to 200 at a time using channels.GetMessages.
        """
        chat = await self.client.get_chat(source_channel)
        raw_chat = getattr(chat, "raw", None)

        max_id = (
            getattr(raw_chat, "read_inbox_max_id", 0)
            or getattr(raw_chat, "read_outbox_max_id", 0)
            or 0
        )
        pinned_id = getattr(raw_chat, "pinned_msg_id", 0) or 0
        min_id = getattr(raw_chat, "available_min_id", 1) or 1
        if min_id <= 0:
            min_id = 1
        max_id = max(max_id, pinned_id)

        # If max_id is 0, probe test IDs to determine range
        if max_id == 0:
            probe_steps = [1, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
            try:
                probe_msgs = await self.client.get_messages(
                    chat_id=source_channel, message_ids=probe_steps
                )
                if not isinstance(probe_msgs, list):
                    probe_msgs = [probe_msgs] if probe_msgs else []
                valid_probes = [
                    m.id for m in probe_msgs if m and not getattr(m, "empty", False)
                ]
                if valid_probes:
                    max_id = max(valid_probes) + 200
                else:
                    max_id = 200
            except Exception:
                max_id = 200

        collected_photos: list[PhotoRecord] = []
        seen_unique_ids: set[str] = set()
        consecutive_empty = 0
        batch_size = 200
        current_id = min_id

        while current_id <= max_id:
            batch_ids = list(range(current_id, min(current_id + batch_size, max_id + 1)))
            if not batch_ids:
                break

            messages = await self.client.get_messages(
                chat_id=source_channel, message_ids=batch_ids
            )
            if not isinstance(messages, list):
                messages = [messages] if messages else []

            valid_in_batch = 0
            for msg in messages:
                if msg and not getattr(msg, "empty", False):
                    valid_in_batch += 1
                    if msg.photo:
                        photo = msg.photo
                        unique_id = photo.file_unique_id
                        if unique_id and unique_id not in seen_unique_ids:
                            seen_unique_ids.add(unique_id)
                            collected_photos.append(
                                PhotoRecord(
                                    file_id=photo.file_id,
                                    file_unique_id=unique_id,
                                    message_id=msg.id,
                                    synced_at=utc_now(),
                                )
                            )
                            if limit > 0 and len(collected_photos) >= limit:
                                return collected_photos

            if valid_in_batch == 0:
                consecutive_empty += 1
                if consecutive_empty >= 5:
                    break
            else:
                consecutive_empty = 0

            current_id += batch_size

        return collected_photos

    async def sync_channel_photos(self, limit: int = 0) -> PhotoSyncResult:
        """Scan SOURCE_CHANNEL_ID history, deduplicate photos, and atomically replace collection.

        If scanning fails at any point, the existing collection is retained untouched.
        """
        start_time = time.perf_counter()
        source_channel = self.settings.SOURCE_CHANNEL_ID
        logger.info("Starting photo synchronization from channel: %s", source_channel)

        try:
            if self.user_client is not None and bool(
                getattr(self.user_client, "is_connected", False)
            ):
                collected_photos = await self._scan_via_user_client(source_channel, limit=limit)
            elif isinstance(getattr(self.client, "bot_token", None), str):
                collected_photos = await self._scan_via_bot_client(source_channel, limit=limit)
            else:
                collected_photos = await self._scan_via_history(
                    self.client, source_channel, limit=limit
                )

            duration = round(time.perf_counter() - start_time, 2)
            count = len(collected_photos)

            # Atomic replacement of the entire photo collection
            new_collection = PhotoCollection(
                photos=collected_photos,
                updated_at=utc_now(),
            )
            await self.storage.photos.save(new_collection, make_backup=True)

            # Record timestamp in metadata
            now = utc_now()

            def _update_meta(meta):
                meta.last_photo_sync_at = now

            await self.storage.metadata.mutate(_update_meta, make_backup=False)

            logger.info(
                "Photo synchronization succeeded: %d photos synced in %.2f seconds",
                count,
                duration,
            )
            return PhotoSyncResult(
                success=True,
                count=count,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = round(time.perf_counter() - start_time, 2)
            error_raw = str(e)
            if "BOT_METHOD_INVALID" in error_raw or "messages.GetHistory" in error_raw:
                friendly_error = Messages.PHOTO_SYNC_BOT_RESTRICTION
            elif "CHAT_ADMIN_REQUIRED" in error_raw or "CHANNEL_PRIVATE" in error_raw:
                friendly_error = Messages.PHOTO_SYNC_NO_ACCESS
            else:
                friendly_error = error_raw

            logger.error(
                "Photo synchronization failed after %.2f seconds: %s. Previous photos retained.",
                duration,
                e,
                exc_info=True,
            )
            return PhotoSyncResult(
                success=False,
                count=0,
                duration_seconds=duration,
                error=friendly_error,
            )

    async def get_random_photo(self) -> PhotoRecord | None:
        """Select a random photo uniformly from stored collection."""
        collection = await self.storage.photos.load()
        return collection.select_random()

    async def get_photos_count(self) -> int:
        """Return the current number of available synchronized photos."""
        collection = await self.storage.photos.load()
        return collection.count
