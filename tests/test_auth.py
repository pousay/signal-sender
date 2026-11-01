"""Tests for authentication and authorization security guards."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from app.config import Settings
from app.utils.auth import (
    create_admin_private_filter,
    get_update_user_id,
    is_private_chat,
    require_admin_private,
)
from app.utils.messages import Messages


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        API_ID=1234567,
        API_HASH="0123456789abcdef0123456789abcdef",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100, 200",
        CONTACT_ADMIN_ID="support_bot",
    )


def test_is_private_chat_and_user_id():
    msg = MagicMock(spec=Message)
    msg.chat = MagicMock()
    msg.chat.type = ChatType.PRIVATE
    msg.from_user = MagicMock()
    msg.from_user.id = 100

    assert is_private_chat(msg) is True
    assert get_update_user_id(msg) == 100

    # Group chat
    msg.chat.type = ChatType.GROUP
    assert is_private_chat(msg) is False


@pytest.mark.asyncio
async def test_admin_private_filter(test_settings: Settings):
    filter_fn = create_admin_private_filter(test_settings)

    # Authorized admin in private chat
    admin_msg = MagicMock(spec=Message)
    admin_msg.chat = MagicMock()
    admin_msg.chat.type = ChatType.PRIVATE
    admin_msg.from_user = MagicMock()
    admin_msg.from_user.id = 100
    assert await filter_fn(None, admin_msg) is True

    # Unauthorized user in private chat
    user_msg = MagicMock(spec=Message)
    user_msg.chat = MagicMock()
    user_msg.chat.type = ChatType.PRIVATE
    user_msg.from_user = MagicMock()
    user_msg.from_user.id = 999
    assert await filter_fn(None, user_msg) is False

    # Authorized admin in public group
    group_msg = MagicMock(spec=Message)
    group_msg.chat = MagicMock()
    group_msg.chat.type = ChatType.SUPERGROUP
    group_msg.from_user = MagicMock()
    group_msg.from_user.id = 100
    assert await filter_fn(None, group_msg) is False


@pytest.mark.asyncio
async def test_require_admin_private_decorator(test_settings: Settings):
    handler = AsyncMock(return_value="executed")
    guarded_handler = require_admin_private(test_settings)(handler)

    # 1. Successful execution for admin in private chat
    admin_msg = MagicMock(spec=Message)
    admin_msg.chat = MagicMock()
    admin_msg.chat.type = ChatType.PRIVATE
    admin_msg.from_user = MagicMock()
    admin_msg.from_user.id = 100
    admin_msg.reply_text = AsyncMock()

    result = await guarded_handler(None, admin_msg)
    assert result == "executed"
    handler.assert_called_once()
    admin_msg.reply_text.assert_not_called()

    # 2. Rejection for non-admin in private chat
    handler.reset_mock()
    user_msg = MagicMock(spec=Message)
    user_msg.chat = MagicMock()
    user_msg.chat.type = ChatType.PRIVATE
    user_msg.from_user = MagicMock()
    user_msg.from_user.id = 999
    user_msg.reply_text = AsyncMock()

    result_unauth = await guarded_handler(None, user_msg)
    assert result_unauth is None
    handler.assert_not_called()
    user_msg.reply_text.assert_called_once_with(Messages.UNAUTHORIZED)

    # 3. Rejection for callback query from non-admin
    cb_query = MagicMock(spec=CallbackQuery)
    cb_query.message = MagicMock(spec=Message)
    cb_query.message.chat = MagicMock()
    cb_query.message.chat.type = ChatType.PRIVATE
    cb_query.from_user = MagicMock()
    cb_query.from_user.id = 999
    cb_query.answer = AsyncMock()

    result_cb = await guarded_handler(None, cb_query)
    assert result_cb is None
    cb_query.answer.assert_called_once_with(Messages.UNAUTHORIZED, show_alert=True)
