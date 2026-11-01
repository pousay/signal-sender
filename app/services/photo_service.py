"""Service managing MTProto photo channel synchronization and selection."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from pyrogram import Client

from app.config import Settings
from app.models.photo import PhotoCollection, PhotoRecord
from app.storage.repositories import StorageManager

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
    ) -> None:
        self.client = client
        self.settings = settings
        self.storage = storage

    async def sync_channel_photos(self, limit: int = 0) -> PhotoSyncResult:
        """Scan SOURCE_CHANNEL_ID history, deduplicate photos, and atomically replace collection.

        If scanning fails at any point, the existing collection is retained untouched.
        """
        start_time = time.perf_counter()
        source_channel = self.settings.SOURCE_CHANNEL_ID
        logger.info("Starting photo synchronization from channel: %s", source_channel)

        collected_photos: list[PhotoRecord] = []
        seen_unique_ids: set[str] = set()

        try:
            # Kurigram's get_chat_history returns an async generator handling MTProto pagination
            async for message in self.client.get_chat_history(chat_id=source_channel, limit=limit):
                if message and message.photo:
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
                error=str(e),
            )

    async def get_random_photo(self) -> PhotoRecord | None:
        """Select a random photo uniformly from stored collection."""
        collection = await self.storage.photos.load()
        return collection.select_random()

    async def get_photos_count(self) -> int:
        """Return the current number of available synchronized photos."""
        collection = await self.storage.photos.load()
        return collection.count
