"""Signal and draft data models."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class SignalStatus(str, Enum):
    """Lifecycle status of a signal."""

    DRAFT = "draft"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SignalRecord(BaseModel):
    """Persisted signal entity."""

    id: int = Field(..., description="Unique integer signal ID")
    original_text: str = Field(..., description="Original raw text submitted by admin")
    order_type: str = Field(
        default="Sell limit",
        description="Extracted order type (Buy limit, Sell limit, etc.)",
    )
    entry_price: str | None = Field(default=None, description="Extracted entry price value")
    sell_limit: str | None = Field(
        default=None, description="Legacy sell limit alias for backward compatibility"
    )
    stop_loss: str | None = Field(default=None, description="Extracted Stop loss value")
    target: str | None = Field(default=None, description="Extracted Target value if parsed")
    public_caption: str = Field(..., description="Generated public caption with deep link")
    photo_file_id: str = Field(..., description="Telegram photo file_id used for publication")
    channel_id: int | str = Field(..., description="Target channel identifier")
    published_message_id: int | None = Field(
        default=None, description="Telegram message ID in target channel"
    )
    status: SignalStatus = Field(default=SignalStatus.PUBLISHED, description="Publication status")
    created_at: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    idempotency_key: str | None = Field(
        default=None, description="Unique key preventing duplicate publications"
    )

    @model_validator(mode="after")
    def _sync_price_fields(self) -> "SignalRecord":
        if not self.entry_price and self.sell_limit:
            self.entry_price = self.sell_limit
        elif not self.sell_limit and self.entry_price:
            self.sell_limit = self.entry_price
        return self


class SignalDraft(BaseModel):
    """In-flight draft awaiting admin approval before channel publication."""

    draft_id: str = Field(..., description="Unique draft identifier")
    admin_id: int = Field(..., description="Admin who created the draft")
    original_text: str = Field(..., description="Original signal text")
    order_type: str = Field(
        default="Sell limit",
        description="Extracted order type (Buy limit, Sell limit, etc.)",
    )
    entry_price: str | None = Field(default=None, description="Extracted entry price value")
    sell_limit: str | None = Field(
        default=None, description="Legacy sell limit alias for backward compatibility"
    )
    stop_loss: str | None = Field(default=None, description="Extracted Stop loss value")
    target: str | None = Field(default=None, description="Extracted Target value")
    public_caption: str = Field(..., description="Prepared public caption")
    photo_file_id: str = Field(..., description="Selected photo file_id or local path")
    source_message_id: int | None = Field(
        default=None, description="Original channel message ID for copy_message"
    )
    source_chat_id: int | str | None = Field(
        default=None, description="Source channel identifier for copy_message"
    )
    created_at: datetime = Field(default_factory=utc_now, description="Draft creation timestamp")

    @model_validator(mode="after")
    def _sync_price_fields(self) -> "SignalDraft":
        if not self.entry_price and self.sell_limit:
            self.entry_price = self.sell_limit
        elif not self.sell_limit and self.entry_price:
            self.sell_limit = self.entry_price
        return self


class SignalsCollection(BaseModel):
    """Container for stored signals and active drafts."""

    version: int = Field(default=1, description="Schema version")
    signals: dict[int, SignalRecord] = Field(
        default_factory=dict, description="Map of signal_id to SignalRecord"
    )
    drafts: dict[str, SignalDraft] = Field(
        default_factory=dict, description="Map of draft_id to SignalDraft"
    )

    def get_signal(self, signal_id: int) -> SignalRecord | None:
        """Retrieve signal by ID."""
        return self.signals.get(signal_id)

    def add_signal(self, signal: SignalRecord) -> None:
        """Store published signal."""
        self.signals[signal.id] = signal

    def get_draft(self, draft_id: str) -> SignalDraft | None:
        """Retrieve draft by ID."""
        return self.drafts.get(draft_id)

    def save_draft(self, draft: SignalDraft) -> None:
        """Save or update draft."""
        self.drafts[draft.draft_id] = draft

    def remove_draft(self, draft_id: str) -> SignalDraft | None:
        """Delete draft if exists."""
        return self.drafts.pop(draft_id, None)
