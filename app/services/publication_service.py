"""Service managing signal draft lifecycle and channel publication."""

import logging
import uuid
from datetime import datetime, timezone

from pyrogram import Client
from pyrogram.enums import ParseMode

from app.config import Settings
from app.keyboards.admin import get_channel_post_keyboard
from app.models.signal import SignalDraft, SignalRecord, SignalStatus
from app.services.photo_service import PhotoService
from app.storage.repositories import StorageManager
from app.utils.formatting import generate_public_caption, parse_signal_text

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class PublicationError(Exception):
    """Base exception for signal draft and publication errors."""


class NoPhotosAvailableError(PublicationError):
    """Raised when no synchronized photos exist to attach to a signal."""


class DraftNotFoundError(PublicationError):
    """Raised when the specified draft ID cannot be found."""


class SignalAlreadyPublishedError(PublicationError):
    """Raised to prevent duplicate publication of an already processed signal."""


class PublicationService:
    """Coordinates signal parsing, draft preview preparation, and channel posting."""

    def __init__(
        self,
        client: Client,
        settings: Settings,
        storage: StorageManager,
        photo_service: PhotoService,
    ) -> None:
        self.client = client
        self.settings = settings
        self.storage = storage
        self.photo_service = photo_service

    async def get_bot_username(self) -> str:
        """Resolve and cache bot username dynamically via MTProto/Bot API."""
        if self.settings.BOT_USERNAME:
            return self.settings.BOT_USERNAME
        me = await self.client.get_me()
        username = me.username or "bot"
        self.settings.BOT_USERNAME = username
        return username

    async def create_draft(self, admin_id: int, original_text: str) -> tuple[SignalDraft, int]:
        """Validate signal text, pick a random photo, and persist a pending draft."""
        photo_count = await self.photo_service.get_photos_count()
        if photo_count == 0:
            raise NoPhotosAvailableError(
                "No synchronized photos available in storage to attach to signal"
            )

        parsed = parse_signal_text(original_text)

        # Allocate unique incremental signal ID and daily tracking code
        signal_id: int = 0
        daily_code: str = ""

        def _alloc(meta):
            nonlocal signal_id, daily_code
            signal_id = meta.allocate_signal_id()
            daily_code = meta.allocate_daily_signal_code()

        await self.storage.metadata.mutate(_alloc, make_backup=False)

        photo = await self.photo_service.get_random_photo()
        if not photo:
            raise NoPhotosAvailableError("Failed to select random photo from collection")

        photo_media = await self.photo_service.ensure_photo_file(photo)

        bot_username = await self.get_bot_username()
        public_caption = generate_public_caption(
            original_text=original_text,
            parsed=parsed,
            bot_username=bot_username,
            signal_id=signal_id,
            daily_code=daily_code,
        )

        draft_id = f"draft_{signal_id}_{uuid.uuid4().hex[:8]}"
        draft = SignalDraft(
            draft_id=draft_id,
            admin_id=admin_id,
            original_text=original_text,
            order_type=parsed.order_type,
            entry_price=parsed.entry_price,
            sell_limit=parsed.entry_price,
            stop_loss=parsed.stop_loss,
            target=parsed.target,
            targets=parsed.targets,
            daily_code=daily_code,
            value=parsed.value,
            public_caption=public_caption,
            photo_file_id=photo_media,
            source_message_id=photo.message_id,
            source_chat_id=photo.chat_id or self.settings.SOURCE_CHANNEL_ID,
            created_at=utc_now(),
        )

        def _save_draft(signals):
            signals.save_draft(draft)

        await self.storage.signals.mutate(_save_draft, make_backup=True)
        logger.info("Admin %s created signal draft %s (signal #%d)", admin_id, draft_id, signal_id)
        return draft, signal_id

    async def get_draft(self, draft_id: str) -> SignalDraft | None:
        """Retrieve draft by identifier."""
        signals_col = await self.storage.signals.load()
        return signals_col.get_draft(draft_id)

    async def publish_draft(self, draft_id: str) -> SignalRecord:
        """Publish approved draft to target channel with attached action button.

        Guarantees idempotency to prevent duplicate publication.
        """
        signals_col = await self.storage.signals.load()
        draft = signals_col.get_draft(draft_id)
        if not draft:
            raise DraftNotFoundError(f"Draft '{draft_id}' was not found or was already published")

        # Extract signal ID from draft_id: draft_<id>_<token>
        parts = draft.draft_id.split("_")
        try:
            signal_id = int(parts[1])
        except (IndexError, ValueError) as err:
            raise PublicationError(f"Malformed draft ID format: {draft.draft_id}") from err

        # Idempotency check: verify this signal has not already been published
        existing_signal = signals_col.get_signal(signal_id)
        if existing_signal and existing_signal.status == SignalStatus.PUBLISHED:
            raise SignalAlreadyPublishedError(f"Signal #{signal_id} has already been published")

        bot_username = await self.get_bot_username()
        keyboard = get_channel_post_keyboard(bot_username, signal_id)

        published_msg = None
        # 1. Primary approach: copy_message directly from source channel by message ID
        if (
            draft.source_message_id
            and draft.source_chat_id
            and hasattr(self.client, "copy_message")
        ):
            try:
                published_msg = await self.client.copy_message(
                    chat_id=self.settings.CHANNEL_ID,
                    from_chat_id=draft.source_chat_id,
                    message_id=draft.source_message_id,
                    caption=draft.public_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception as copy_err:
                logger.warning(
                    "copy_message failed for channel publication: %s. Falling back to send_photo.",
                    copy_err,
                )

        # 2. Fallback: send_photo using draft.photo_file_id
        if not published_msg:
            try:
                published_msg = await self.client.send_photo(
                    chat_id=self.settings.CHANNEL_ID,
                    photo=draft.photo_file_id,
                    caption=draft.public_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.error("Failed to publish signal #%d to channel: %s", signal_id, e)
                raise PublicationError(f"Telegram publication failed: {e}") from e

        # Construct published record
        record = SignalRecord(
            id=signal_id,
            original_text=draft.original_text,
            order_type=draft.order_type,
            entry_price=draft.entry_price,
            sell_limit=draft.sell_limit,
            stop_loss=draft.stop_loss,
            target=draft.target,
            targets=getattr(draft, "targets", []),
            daily_code=getattr(draft, "daily_code", None),
            value=getattr(draft, "value", None),
            public_caption=draft.public_caption,
            photo_file_id=draft.photo_file_id,
            channel_id=self.settings.CHANNEL_ID,
            published_message_id=published_msg.id,
            status=SignalStatus.PUBLISHED,
            created_at=draft.created_at,
            published_at=utc_now(),
            idempotency_key=draft_id,
        )

        def _commit_signal(col):
            col.add_signal(record)
            col.remove_draft(draft_id)

        await self.storage.signals.mutate(_commit_signal, make_backup=True)

        def _increment_total(meta):
            meta.total_signals_published += 1

        await self.storage.metadata.mutate(_increment_total, make_backup=False)

        logger.info(
            "Signal #%d successfully published to channel %s (message ID: %s)",
            signal_id,
            self.settings.CHANNEL_ID,
            published_msg.id,
        )
        return record
