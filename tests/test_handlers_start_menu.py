"""Tests for start and admin menu handlers."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client, ContinuePropagation
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from app.config import Settings
from app.handlers.admin_menu import register_admin_menu_handlers
from app.handlers.publish import register_publish_handlers
from app.handlers.start import register_start_handler
from app.handlers.subscriptions import register_subscription_handlers
from app.models.signal import SignalRecord, SignalStatus
from app.models.state import AdminStep, StateManager
from app.services.photo_service import PhotoService
from app.services.publication_service import PublicationService
from app.services.subscription_service import SubscriptionService
from app.storage.repositories import StorageManager
from app.utils.messages import Messages


@pytest.fixture
def settings() -> Settings:
    return Settings(
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        API_ID=1234567,
        API_HASH="0123456789abcdef0123456789abcdef",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100, 200",
        CONTACT_ADMIN_ID="support_guru",
    )


@pytest.fixture
def state_manager() -> StateManager:
    return StateManager()


@pytest.fixture
def mock_app() -> Client:
    app = MagicMock(spec=Client)
    # Mock decorator methods to simply store or return handler
    app.on_message = lambda *args, **kwargs: lambda f: f
    app.on_callback_query = lambda *args, **kwargs: lambda f: f
    return app


@pytest.mark.asyncio
async def test_admin_start_routing(
    mock_app: Client, settings: Settings, state_manager: StateManager
):
    """Verify admin /start receives admin welcome with 3-button menu and resets state."""
    # Capture registered handler
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    register_start_handler(mock_app, settings, state_manager)

    # Pre-populate state to check clearing
    await state_manager.set_state(100, AdminStep.AWAITING_SIGNAL_TEXT)

    msg = MagicMock(spec=Message)
    msg.text = "/start"
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.from_user = MagicMock()
    msg.from_user.id = 100
    msg.reply_text = AsyncMock()

    await captured_handler(mock_app, msg)

    msg.reply_text.assert_called_once()
    assert msg.reply_text.call_args[1]["text"] == Messages.ADMIN_WELCOME
    assert len(msg.reply_text.call_args[1]["reply_markup"].inline_keyboard) == 3

    state = await state_manager.get_state(100)
    assert state.step == AdminStep.IDLE


@pytest.mark.asyncio
async def test_user_start_routing(
    mock_app: Client, settings: Settings, state_manager: StateManager
):
    """Verify ordinary user receives Persian instructions and support link."""
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    register_start_handler(mock_app, settings, state_manager)

    user_msg = MagicMock(spec=Message)
    user_msg.text = "/start"
    user_msg.chat = MagicMock()
    user_msg.chat.type = ChatType.PRIVATE
    user_msg.from_user = MagicMock()
    user_msg.from_user.id = 999  # non-admin
    user_msg.reply_text = AsyncMock()

    await captured_handler(mock_app, user_msg)

    user_msg.reply_text.assert_called_once()
    assert "@support_guru" in user_msg.reply_text.call_args[1]["text"]
    assert user_msg.reply_text.call_args[1]["link_preview_options"].is_disabled is True


@pytest.mark.asyncio
async def test_cancel_callback_clears_state(
    mock_app: Client, settings: Settings, state_manager: StateManager
):
    """Verify cancel callback clears admin state and edits message to remove controls."""
    captured_callbacks = []

    def capture_on_callback(*args, **kwargs):
        def decorator(f):
            captured_callbacks.append(f)
            return f

        return decorator

    mock_app.on_callback_query = capture_on_callback
    register_admin_menu_handlers(mock_app, settings, state_manager)

    cancel_handler = captured_callbacks[0]

    # Pre-populate state
    await state_manager.set_state(100, AdminStep.AWAITING_SIGNAL_TEXT, data={"draft": "test"})

    cb = MagicMock(spec=CallbackQuery)
    cb.from_user = MagicMock()
    cb.from_user.id = 100
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.chat = MagicMock()
    cb.message.chat.type = ChatType.PRIVATE
    cb.message.edit_text = AsyncMock()

    await cancel_handler(mock_app, cb)

    cb.answer.assert_called_once()
    cb.message.edit_text.assert_called_once_with(
        text=Messages.OPERATION_CANCELLED,
        reply_markup=None,
    )
    state = await state_manager.get_state(100)
    assert state.step == AdminStep.IDLE
    assert state.data == {}


@pytest.mark.asyncio
async def test_user_start_deep_link_routing(tmp_path: Path, settings: Settings):
    """Verify /start <signal_id> directly delivers signal details via start router."""
    storage = StorageManager(data_dir=tmp_path / "data")
    await storage.initialize()

    record = SignalRecord(
        id=77,
        original_text="Buy limit: 2200\nStop loss: 2150",
        order_type="Buy limit",
        entry_price="2200",
        stop_loss="2150",
        target=None,
        public_caption="Buy limit: 2200\nStop loss: [مشاهده](...)",
        photo_file_id="photo_xyz",
        channel_id=settings.CHANNEL_ID,
        status=SignalStatus.PUBLISHED,
    )

    def _seed(col):
        col.add_signal(record)

    await storage.signals.mutate(_seed, make_backup=False)

    mock_client = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_client.on_message = capture_on_message

    sub_service = SubscriptionService(mock_client, settings, storage)
    # Grant premium to user 555
    await sub_service.set_subscription(user_id=555, duration_days=30)

    state_mgr = StateManager()
    register_start_handler(
        mock_client,
        settings,
        state_mgr,
        storage=storage,
        subscription_service=sub_service,
    )

    # 1. Premium user clicks deep link /start 77
    msg_prem = MagicMock(spec=Message)
    msg_prem.text = "/start 77"
    msg_prem.chat = MagicMock()
    msg_prem.chat.type = ChatType.PRIVATE
    msg_prem.from_user = MagicMock()
    msg_prem.from_user.id = 555
    msg_prem.reply_text = AsyncMock()

    await captured_handler(mock_client, msg_prem)
    msg_prem.reply_text.assert_called_once()
    assert "2200" in msg_prem.reply_text.call_args[0][0]
    assert "2150" in msg_prem.reply_text.call_args[0][0]

    # 2. Non-premium user clicks deep link /start 77
    msg_non = MagicMock(spec=Message)
    msg_non.text = "/start 77"
    msg_non.chat = MagicMock()
    msg_non.chat.type = ChatType.PRIVATE
    msg_non.from_user = MagicMock()
    msg_non.from_user.id = 666
    msg_non.reply_text = AsyncMock()

    await captured_handler(mock_client, msg_non)
    msg_non.reply_text.assert_called_once()
    assert "@support_guru" in msg_non.reply_text.call_args[1]["text"]
    assert msg_non.reply_text.call_args[1]["link_preview_options"].is_disabled is True


@pytest.mark.asyncio
async def test_admin_text_handlers_propagation(tmp_path: Path, settings: Settings):
    """Verify publish handler propagates so subscription wizard receives numeric user ID."""
    storage = StorageManager(data_dir=tmp_path / "data")
    await storage.initialize()

    mock_client = MagicMock(spec=Client)
    message_handlers = []

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            message_handlers.append(f)
            return f

        return decorator

    mock_client.on_message = capture_on_message
    mock_client.on_callback_query = MagicMock()

    state_mgr = StateManager()
    photo_svc = PhotoService(mock_client, settings, storage)
    pub_svc = PublicationService(mock_client, settings, storage, photo_svc)
    sub_svc = SubscriptionService(mock_client, settings, storage)

    # Register in same order as register_all_handlers: publish first, subscription second
    register_publish_handlers(mock_client, settings, state_mgr, pub_svc)
    register_subscription_handlers(mock_client, settings, state_mgr, sub_svc)

    publish_handler = message_handlers[0]
    sub_handler = message_handlers[1]

    # Admin is in AWAITING_USER_ID step
    await state_mgr.set_state(100, AdminStep.AWAITING_USER_ID)

    admin_msg = MagicMock(spec=Message)
    admin_msg.text = "12345678"
    admin_msg.chat = MagicMock()
    admin_msg.chat.type = ChatType.PRIVATE
    admin_msg.from_user = MagicMock()
    admin_msg.from_user.id = 100
    admin_msg.reply_text = AsyncMock()

    # Step A: publish handler receives the message -> raises ContinuePropagation
    with pytest.raises(ContinuePropagation):
        await publish_handler(mock_client, admin_msg)

    # Step B: dispatcher continues to subscription handler -> processes user ID
    await sub_handler(mock_client, admin_msg)

    admin_msg.reply_text.assert_called_once_with(
        text=Messages.PROMPT_DURATION_DAYS,
        reply_markup=admin_msg.reply_text.call_args[1]["reply_markup"],
    )
    new_state = await state_mgr.get_state(100)
    assert new_state.step == AdminStep.AWAITING_DURATION_DAYS
    assert new_state.data["target_user_id"] == 12345678
