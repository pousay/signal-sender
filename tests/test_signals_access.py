"""Tests for deep-link signal resolution and premium access control."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import Message, User

from app.config import Settings
from app.handlers.signals import register_signal_handlers
from app.models.signal import SignalRecord, SignalStatus
from app.services.subscription_service import SubscriptionService
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
        CONTACT_ADMIN_ID="elite_support",
        DATA_DIR=tmp_path / "data",
    )


@pytest.fixture
async def test_storage(test_settings: Settings) -> StorageManager:
    manager = StorageManager(data_dir=test_settings.DATA_DIR)
    await manager.initialize()

    # Seed a published signal
    record = SignalRecord(
        id=42,
        original_text="Sell limit: 77950\nStop loss: 78650\nTarget: 76900",
        sell_limit="77950",
        stop_loss="78650",
        target="76900",
        public_caption="Sell limit: [مشاهده](...) #XAUUSD",
        photo_file_id="photo_xyz",
        channel_id=test_settings.CHANNEL_ID,
        published_message_id=123,
        status=SignalStatus.PUBLISHED,
    )

    def _seed(col):
        col.add_signal(record)

    await manager.signals.mutate(_seed, make_backup=False)
    return manager


@pytest.mark.asyncio
async def test_deep_link_premium_user_receives_details(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify user with active subscription receives real signal values."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message

    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    # Give user 888 an active subscription
    await sub_service.set_subscription(user_id=888, duration_days=30)

    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 42"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 888
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    reply = msg.reply_text.call_args[0][0]
    assert "Sell limit: `77950`" in reply
    assert "Stop loss: `78650`" in reply
    assert "Target: `76900`" in reply


@pytest.mark.asyncio
async def test_deep_link_non_premium_user_receives_support_message(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify user without active subscription receives support prompt with link."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message

    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 42"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 999  # No subscription
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    kwargs = msg.reply_text.call_args[1]
    assert "@elite_support" in kwargs["text"]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_deep_link_signal_not_found(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify non-existent signal ID receives signal not found message."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message

    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 99999"  # Non-existent
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 100
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once_with(Messages.SIGNAL_NOT_FOUND)


@pytest.mark.asyncio
async def test_deep_link_premium_user_receives_copiable_value(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify premium subscriber receives copiable monospace details and value."""
    # Seed a published signal with value and multi targets
    record = SignalRecord(
        id=77,
        original_text="Buy limit: 0.81630\nStop loss: 94646\nvalue: 0.17لات",
        order_type="Buy limit",
        entry_price="0.81630",
        stop_loss="94646",
        targets=[("Target 1", "94646"), ("Target 2", "31551")],
        value="0.17لات",
        public_caption="Buy limit: [مشاهده](...)",
        photo_file_id="photo_xyz",
        channel_id=test_settings.CHANNEL_ID,
        published_message_id=456,
        status=SignalStatus.PUBLISHED,
    )

    def _seed(col):
        col.add_signal(record)

    await test_storage.signals.mutate(_seed, make_backup=False)

    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    await sub_service.set_subscription(user_id=777, duration_days=30)
    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 77"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 777
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    reply = msg.reply_text.call_args[0][0]
    assert "🔵 Buy limit: `0.81630`" in reply
    assert "⚫️ Stop loss: `94646`" in reply
    assert "🟢 Target 1: `94646`" in reply
    assert "🟢 Target 2: `31551`" in reply
    assert "🗻 value: `0.17`لات" in reply


@pytest.mark.asyncio
async def test_deep_link_premium_user_receives_details_with_fallback_reparsing(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify fallback reparsing guarantees full parameters when signal had None in fields."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message

    # Seed signal #99 with None in stop_loss and targets, but valid original_text
    record = SignalRecord(
        id=99,
        original_text=(
            "🔵 Buy limit: 0.81630\n"
            "⚫️ Stop loss: 0.81200\n"
            "🟢 Target 1: 0.81900\n"
            "🟢 Target 2: 0.82200"
        ),
        sell_limit="0.81630",
        order_type="Buy limit",
        entry_price="0.81630",
        stop_loss=None,  # Old or missing field
        target=None,
        targets=[],
        public_caption="caption",
        photo_file_id="photo",
        channel_id=test_settings.CHANNEL_ID,
        published_message_id=999,
        status=SignalStatus.PUBLISHED,
    )

    def _seed(col):
        col.add_signal(record)

    await test_storage.signals.mutate(_seed, make_backup=False)

    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    await sub_service.set_subscription(user_id=777, duration_days=30)
    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 99"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 777
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    reply = msg.reply_text.call_args[0][0]
    assert "🔵 Buy limit: `0.81630`" in reply
    assert "⚫️ Stop loss: `0.81200`" in reply
    assert "🟢 Target 1: `0.81900`" in reply
    assert "🟢 Target 2: `0.82200`" in reply


@pytest.mark.asyncio
async def test_deep_link_premium_user_receives_pip_notes(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify subscriber receives full target parameter text including pip notes."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message

    record = SignalRecord(
        id=85,
        original_text=(
            "🔵 Buy limit: 52.500\n"
            "⚫️ Stop loss: 51.500 (50 pip)\n"
            "🟢 Target 1: 53.500 (100 پیپ)\n"
            "🟢 Target 2: 54.000 (150 پیپ)"
        ),
        sell_limit="52.500",
        order_type="Buy limit",
        entry_price="52.500",
        stop_loss="51.500 (50 pip)",
        target="53.500 (100 پیپ)",
        targets=[
            ("Target 1", "53.500 (100 پیپ)"),
            ("Target 2", "54.000 (150 پیپ)"),
        ],
        public_caption="caption",
        photo_file_id="photo_silver",
        channel_id=test_settings.CHANNEL_ID,
        published_message_id=850,
        status=SignalStatus.PUBLISHED,
    )

    def _seed(col):
        col.add_signal(record)

    await test_storage.signals.mutate(_seed, make_backup=False)

    sub_service = SubscriptionService(mock_app, test_settings, test_storage)
    await sub_service.set_subscription(user_id=555, duration_days=30)
    register_signal_handlers(mock_app, test_settings, test_storage, sub_service)

    msg = MagicMock(spec=Message)
    msg.text = "/start 85"
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 555
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    reply = msg.reply_text.call_args[0][0]
    assert "🔵 Buy limit: `52.500`" in reply
    assert "⚫️ Stop loss: `51.500` (50 pip)" in reply
    assert "🟢 Target 1: `53.500` (100 پیپ)" in reply
    assert "🟢 Target 2: `54.000` (150 پیپ)" in reply


