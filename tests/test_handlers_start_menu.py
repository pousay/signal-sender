"""Tests for start and admin menu handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from app.config import Settings
from app.handlers.admin_menu import register_admin_menu_handlers
from app.handlers.start import register_start_handler
from app.models.state import AdminStep, StateManager
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
