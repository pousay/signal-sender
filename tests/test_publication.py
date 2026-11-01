"""Tests for signal drafting, previewing, and channel publication."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message, User

from app.config import Settings
from app.handlers.publish import register_publish_handlers
from app.models.photo import PhotoCollection, PhotoRecord
from app.models.signal import SignalStatus
from app.models.state import AdminStep, StateManager
from app.services.photo_service import PhotoService
from app.services.publication_service import (
    DraftNotFoundError,
    NoPhotosAvailableError,
    PublicationService,
)
from app.storage.repositories import StorageManager
from app.utils.messages import Messages


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        API_ID=1234567,
        API_HASH="0123456789abcdef0123456789abcdef",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100",
        CONTACT_ADMIN_ID="support_guru",
        DATA_DIR=tmp_path / "data",
        BOT_USERNAME="my_test_bot",
    )


@pytest.fixture
async def test_storage(test_settings: Settings) -> StorageManager:
    manager = StorageManager(data_dir=test_settings.DATA_DIR)
    await manager.initialize()
    return manager


@pytest.fixture
async def seeded_photo_service(
    test_settings: Settings, test_storage: StorageManager
) -> PhotoService:
    # Seed storage with a photo
    collection = PhotoCollection(
        photos=[PhotoRecord(file_id="photo_123", file_unique_id="uid_123", message_id=10)]
    )
    await test_storage.photos.save(collection, make_backup=False)
    client = MagicMock(spec=Client)
    return PhotoService(client, test_settings, test_storage)


@pytest.mark.asyncio
async def test_create_draft_success(
    test_settings: Settings, test_storage: StorageManager, seeded_photo_service: PhotoService
):
    """Verify draft creation parses Sell limit, picks photo, and generates deep link."""
    mock_client = MagicMock(spec=Client)
    pub_service = PublicationService(
        mock_client, test_settings, test_storage, seeded_photo_service
    )

    signal_text = "Sell limit: 50000\nSL: 51000"
    draft, signal_id = await pub_service.create_draft(admin_id=100, original_text=signal_text)

    assert signal_id == 1
    assert draft.sell_limit == "50000"
    assert draft.photo_file_id == "photo_123"
    assert "[مشاهده](https://t.me/my_test_bot?start=1)" in draft.public_caption

    # Check stored in signals container
    col = await test_storage.signals.load()
    assert col.get_draft(draft.draft_id) is not None


@pytest.mark.asyncio
async def test_create_draft_no_photos_error(test_settings: Settings, test_storage: StorageManager):
    """Verify draft creation raises NoPhotosAvailableError when zero photos stored."""
    empty_photo_service = PhotoService(MagicMock(spec=Client), test_settings, test_storage)
    pub_service = PublicationService(
        MagicMock(spec=Client), test_settings, test_storage, empty_photo_service
    )

    with pytest.raises(NoPhotosAvailableError):
        await pub_service.create_draft(admin_id=100, original_text="Sell limit: 1234")


@pytest.mark.asyncio
async def test_publish_draft_success_and_idempotency(
    test_settings: Settings, test_storage: StorageManager, seeded_photo_service: PhotoService
):
    """Verify draft is published to channel post with attached inline keyboard."""
    mock_client = MagicMock(spec=Client)
    published_post = MagicMock(spec=Message)
    published_post.id = 9999
    mock_client.send_photo = AsyncMock(return_value=published_post)

    pub_service = PublicationService(
        mock_client, test_settings, test_storage, seeded_photo_service
    )

    draft, signal_id = await pub_service.create_draft(100, "Sell limit: 75000")
    record = await pub_service.publish_draft(draft.draft_id)

    assert record.id == signal_id
    assert record.published_message_id == 9999
    assert record.status == SignalStatus.PUBLISHED

    # Channel send_photo was called with attached inline button
    mock_client.send_photo.assert_called_once()
    call_kwargs = mock_client.send_photo.call_args[1]
    assert call_kwargs["chat_id"] == test_settings.CHANNEL_ID
    assert call_kwargs["reply_markup"] is not None

    # Draft removed, signal saved
    col = await test_storage.signals.load()
    assert col.get_draft(draft.draft_id) is None
    assert col.get_signal(signal_id) is not None

    # Repeated publish attempt raises DraftNotFoundError
    with pytest.raises(DraftNotFoundError):
        await pub_service.publish_draft(draft.draft_id)


@pytest.mark.asyncio
async def test_publish_handlers_preview_and_approval(
    test_settings: Settings, test_storage: StorageManager, seeded_photo_service: PhotoService
):
    """Verify end-to-end interactive submission, preview, and approval callback."""
    mock_app = MagicMock(spec=Client)
    captured_message_handler = None
    captured_callback_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_message_handler
            captured_message_handler = f
            return f

        return decorator

    def capture_on_callback(*args, **kwargs):
        def decorator(f):
            nonlocal captured_callback_handler
            captured_callback_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    mock_app.on_callback_query = capture_on_callback

    # Setup publication service
    published_post = MagicMock(spec=Message)
    published_post.id = 555
    mock_app.send_photo = AsyncMock(return_value=published_post)

    pub_service = PublicationService(mock_app, test_settings, test_storage, seeded_photo_service)
    state_manager = StateManager()

    register_publish_handlers(mock_app, test_settings, state_manager, pub_service)

    # 1. Admin sends signal text while in AWAITING_SIGNAL_TEXT step
    await state_manager.set_state(100, AdminStep.AWAITING_SIGNAL_TEXT)

    msg = MagicMock(spec=Message)
    msg.text = "Sell limit: 80000"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 100
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE

    preview_msg = MagicMock(spec=Message)
    preview_msg.id = 777
    msg.reply_photo = AsyncMock(return_value=preview_msg)

    await captured_message_handler(mock_app, msg)

    msg.reply_photo.assert_called_once()
    state = await state_manager.get_state(100)
    assert state.step == AdminStep.AWAITING_CONFIRMATION
    draft_id = state.data["draft_id"]

    # 2. Admin approves publication via callback
    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = 100
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.chat = MagicMock()
    cb.message.chat.type = ChatType.PRIVATE
    cb.message.reply_text = AsyncMock()

    # Match group for regex
    mock_match = MagicMock()
    mock_match.group.return_value = draft_id
    cb.matches = [mock_match]

    await captured_callback_handler(mock_app, cb)

    cb.answer.assert_called_once()
    cb.message.reply_text.assert_called_once()
    assert (
        Messages.PUBLISH_SUCCESS.format(message_id=555)
        in cb.message.reply_text.call_args[0][0]
    )

    # State cleared after publication
    final_state = await state_manager.get_state(100)
    assert final_state.step == AdminStep.IDLE
