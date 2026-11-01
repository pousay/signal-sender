"""Tests for MTProto photo channel synchronization and fallback retention."""

from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message, Photo

from app.config import Settings
from app.handlers.photos import register_photo_handlers
from app.models.photo import PhotoCollection, PhotoRecord
from app.services.photo_service import PhotoService
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
    )


@pytest.fixture
async def test_storage(test_settings: Settings) -> StorageManager:
    manager = StorageManager(data_dir=test_settings.DATA_DIR)
    await manager.initialize()
    return manager


def create_mock_photo_message(msg_id: int, file_id: str, unique_id: str) -> Message:
    msg = MagicMock(spec=Message)
    msg.id = msg_id
    photo = MagicMock(spec=Photo)
    photo.file_id = file_id
    photo.file_unique_id = unique_id
    msg.photo = photo
    return msg


def create_mock_text_message(msg_id: int) -> Message:
    msg = MagicMock(spec=Message)
    msg.id = msg_id
    msg.photo = None
    return msg


@pytest.mark.asyncio
async def test_sync_photos_success_and_deduplication(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify photo messages are filtered, deduplicated by unique_id, and saved."""
    mock_messages = [
        create_mock_photo_message(1, "fid_1", "uid_1"),
        create_mock_text_message(2),  # Ignored text message
        create_mock_photo_message(3, "fid_2", "uid_2"),
        create_mock_photo_message(4, "fid_1_dup", "uid_1"),  # Duplicate photo
    ]

    async def mock_history(*args, **kwargs) -> AsyncGenerator[Message, None]:
        for m in mock_messages:
            yield m

    mock_client = MagicMock(spec=Client)
    mock_client.get_chat_history = mock_history

    service = PhotoService(mock_client, test_settings, test_storage)
    result = await service.sync_channel_photos()

    assert result.success is True
    assert result.count == 2
    assert result.error is None

    stored = await test_storage.photos.load()
    assert stored.count == 2
    assert stored.photos[0].file_unique_id == "uid_1"
    assert stored.photos[1].file_unique_id == "uid_2"

    meta = await test_storage.metadata.load()
    assert meta.last_photo_sync_at is not None

    random_photo = await service.get_random_photo()
    assert random_photo is not None
    assert random_photo.file_unique_id in ("uid_1", "uid_2")


@pytest.mark.asyncio
async def test_sync_photos_full_replacement(test_settings: Settings, test_storage: StorageManager):
    """Verify successful sync completely replaces previous collection."""
    # Pre-populate with old photo
    old_collection = PhotoCollection(
        photos=[PhotoRecord(file_id="old_fid", file_unique_id="old_uid", message_id=99)]
    )
    await test_storage.photos.save(old_collection, make_backup=False)

    # Sync new channel state
    new_messages = [create_mock_photo_message(10, "new_fid", "new_uid")]

    async def mock_history(*args, **kwargs) -> AsyncGenerator[Message, None]:
        for m in new_messages:
            yield m

    mock_client = MagicMock(spec=Client)
    mock_client.get_chat_history = mock_history

    service = PhotoService(mock_client, test_settings, test_storage)
    result = await service.sync_channel_photos()

    assert result.success is True
    assert result.count == 1

    stored = await test_storage.photos.load()
    assert stored.count == 1
    assert stored.photos[0].file_unique_id == "new_uid"
    assert stored.contains_unique_id("old_uid") is False


@pytest.mark.asyncio
async def test_sync_photos_failure_preserves_previous(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify sync failure leaves existing collection intact."""
    # Pre-populate valid collection
    initial_collection = PhotoCollection(
        photos=[PhotoRecord(file_id="initial_fid", file_unique_id="initial_uid", message_id=5)]
    )
    await test_storage.photos.save(initial_collection, make_backup=False)

    # Failing generator
    async def failing_history(*args, **kwargs) -> AsyncGenerator[Message, None]:
        yield create_mock_photo_message(1, "partial_fid", "partial_uid")
        raise RuntimeError("MTProto network disconnect")

    mock_client = MagicMock(spec=Client)
    mock_client.get_chat_history = failing_history

    service = PhotoService(mock_client, test_settings, test_storage)
    result = await service.sync_channel_photos()

    assert result.success is False
    assert "MTProto network disconnect" in (result.error or "")

    # Check preserved collection
    stored = await test_storage.photos.load()
    assert stored.count == 1
    assert stored.photos[0].file_unique_id == "initial_uid"


@pytest.mark.asyncio
async def test_update_photos_callback_handler(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify admin callback executes sync and edits message with Persian summary."""
    mock_app = MagicMock(spec=Client)
    captured_callback = None

    def capture_on_callback(*args, **kwargs):
        def decorator(f):
            nonlocal captured_callback
            captured_callback = f
            return f

        return decorator

    mock_app.on_callback_query = capture_on_callback

    mock_service = AsyncMock(spec=PhotoService)
    from app.services.photo_service import PhotoSyncResult

    mock_service.sync_channel_photos.return_value = PhotoSyncResult(success=True, count=5)

    register_photo_handlers(mock_app, test_settings, mock_service)

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = MagicMock()
    cb.from_user.id = 100
    cb.answer = AsyncMock()

    status_msg = MagicMock(spec=Message)
    status_msg.edit_text = AsyncMock()

    cb.message = MagicMock(spec=Message)
    cb.message.chat = MagicMock()
    cb.message.chat.type = ChatType.PRIVATE
    cb.message.reply_text = AsyncMock(return_value=status_msg)

    await captured_callback(mock_app, cb)

    cb.answer.assert_called_once()
    mock_service.sync_channel_photos.assert_called_once()
    status_msg.edit_text.assert_called_once_with(Messages.PHOTO_SYNC_SUCCESS.format(count=5))


@pytest.mark.asyncio
async def test_sync_photos_via_user_client(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify user_client get_chat_history is preferred when configured."""
    mock_messages = [
        create_mock_photo_message(10, "user_fid_1", "user_uid_1"),
        create_mock_photo_message(20, "user_fid_2", "user_uid_2"),
    ]

    async def mock_history(*args, **kwargs) -> AsyncGenerator[Message, None]:
        for m in mock_messages:
            yield m

    mock_bot_client = MagicMock(spec=Client)
    mock_user_client = MagicMock(spec=Client)
    mock_user_client.is_connected = True
    mock_user_client.get_chat_history = mock_history

    service = PhotoService(
        client=mock_bot_client,
        settings=test_settings,
        storage=test_storage,
        user_client=mock_user_client,
    )
    result = await service.sync_channel_photos()

    assert result.success is True
    assert result.count == 2
    stored = await test_storage.photos.load()
    assert stored.count == 2
    assert stored.photos[0].file_unique_id == "user_uid_1"


@pytest.mark.asyncio
async def test_sync_photos_disconnected_user_client_falls_back_to_bot(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify disconnected user_client falls back to bot get_messages batch scan."""
    mock_bot = MagicMock(spec=Client)
    mock_bot.bot_token = "123456:mock_token_string"

    mock_chat = MagicMock()
    mock_raw = MagicMock()
    mock_raw.read_inbox_max_id = 2
    mock_raw.available_min_id = 1
    mock_raw.pinned_msg_id = 0
    mock_chat.raw = mock_raw
    mock_bot.get_chat = AsyncMock(return_value=mock_chat)

    batch_messages = [
        create_mock_photo_message(1, "fallback_fid_1", "fallback_uid_1"),
    ]
    mock_bot.get_messages = AsyncMock(return_value=batch_messages)

    mock_user_client = MagicMock(spec=Client)
    mock_user_client.is_connected = False

    service = PhotoService(
        client=mock_bot,
        settings=test_settings,
        storage=test_storage,
        user_client=mock_user_client,
    )
    result = await service.sync_channel_photos()

    assert result.success is True
    assert result.count == 1
    assert mock_bot.get_chat.called
    assert mock_bot.get_messages.called


@pytest.mark.asyncio
async def test_sync_photos_via_bot_batch_messages(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify bot client scans via get_chat and batch get_messages."""
    mock_bot = MagicMock(spec=Client)
    mock_bot.bot_token = "123456:mock_token_string"

    mock_chat = MagicMock()
    mock_raw = MagicMock()
    mock_raw.read_inbox_max_id = 4
    mock_raw.available_min_id = 1
    mock_raw.pinned_msg_id = 0
    mock_chat.raw = mock_raw
    mock_bot.get_chat = AsyncMock(return_value=mock_chat)

    batch_messages = [
        create_mock_photo_message(1, "bot_fid_1", "bot_uid_1"),
        create_mock_text_message(2),
        create_mock_photo_message(3, "bot_fid_2", "bot_uid_2"),
        create_mock_photo_message(4, "bot_fid_1_dup", "bot_uid_1"),
    ]
    mock_bot.get_messages = AsyncMock(return_value=batch_messages)

    service = PhotoService(client=mock_bot, settings=test_settings, storage=test_storage)
    result = await service.sync_channel_photos()

    assert result.success is True
    assert result.count == 2
    assert mock_bot.get_chat.called
    assert mock_bot.get_messages.called

    stored = await test_storage.photos.load()
    assert stored.count == 2
    assert stored.photos[0].file_unique_id == "bot_uid_1"
    assert stored.photos[1].file_unique_id == "bot_uid_2"


@pytest.mark.asyncio
async def test_sync_photos_bot_method_invalid_error_handling(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify Telegram 400 BOT_METHOD_INVALID maps to Persian explanation."""
    mock_bot = MagicMock(spec=Client)
    mock_bot.bot_token = "123456:mock_token_string"
    mock_bot.get_chat = AsyncMock(
        side_effect=RuntimeError(
            "Telegram says: [400 BOT_METHOD_INVALID] - The specified method "
            "cannot be used by bots. (caused by 'messages.GetHistory')"
        )
    )

    service = PhotoService(client=mock_bot, settings=test_settings, storage=test_storage)
    result = await service.sync_channel_photos()

    assert result.success is False
    assert result.error == Messages.PHOTO_SYNC_BOT_RESTRICTION


@pytest.mark.asyncio
async def test_sync_photos_chat_admin_required_error_handling(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify CHAT_ADMIN_REQUIRED maps to Persian explanation."""
    mock_bot = MagicMock(spec=Client)
    mock_bot.bot_token = "123456:mock_token_string"
    mock_bot.get_chat = AsyncMock(
        side_effect=RuntimeError("Telegram says: [400 CHAT_ADMIN_REQUIRED]")
    )

    service = PhotoService(client=mock_bot, settings=test_settings, storage=test_storage)
    result = await service.sync_channel_photos()

    assert result.success is False
    assert result.error == Messages.PHOTO_SYNC_NO_ACCESS
