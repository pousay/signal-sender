"""Metadata model for storage tracking."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class StorageMetadata(BaseModel):
    """Metadata tracking schema version and global counters."""

    version: int = Field(default=1, description="Storage schema version")
    next_signal_id: int = Field(default=1, description="Next incremental signal ID")
    last_photo_sync_at: datetime | None = Field(
        default=None, description="UTC timestamp of last photo synchronization"
    )
    total_signals_published: int = Field(
        default=0, description="Total count of successfully published signals"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Last update UTC timestamp"
    )

    def allocate_signal_id(self) -> int:
        """Increment and return the next unique signal ID."""
        allocated = self.next_signal_id
        self.next_signal_id += 1
        self.updated_at = utc_now()
        return allocated
