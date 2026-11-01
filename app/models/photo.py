"""Photo models for synchronized channel media."""

import random
from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class PhotoRecord(BaseModel):
    """Represents a synchronized Telegram photo from the source channel."""

    file_id: str = Field(..., description="Reusable Telegram photo file_id")
    file_unique_id: str = Field(
        ..., description="Stable Telegram unique identifier for deduplication"
    )
    local_path: str | None = Field(default=None, description="Local cached photo path")
    message_id: int | None = Field(default=None, description="Original channel message ID")
    chat_id: int | str | None = Field(default=None, description="Source channel identifier")
    synced_at: datetime = Field(default_factory=utc_now, description="Sync UTC timestamp")


class PhotoCollection(BaseModel):
    """Collection of synchronized photos available for random selection."""

    version: int = Field(default=1, description="Schema version")
    updated_at: datetime = Field(default_factory=utc_now, description="Last update timestamp")
    photos: list[PhotoRecord] = Field(
        default_factory=list, description="List of unique photo records"
    )

    @property
    def is_empty(self) -> bool:
        """Return True if collection has no photos."""
        return len(self.photos) == 0

    @property
    def count(self) -> int:
        """Return total number of photos."""
        return len(self.photos)

    def select_random(self) -> PhotoRecord | None:
        """Select a random photo with equal probability."""
        if not self.photos:
            return None
        return random.choice(self.photos)

    def contains_unique_id(self, unique_id: str) -> bool:
        """Check if a photo with the given unique_id exists."""
        return any(p.file_unique_id == unique_id for p in self.photos)
