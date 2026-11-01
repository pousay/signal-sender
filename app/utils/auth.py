"""Authentication, authorization guards, and custom Kurigram filters."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

from app.config import Settings
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def is_private_chat(update: Any) -> bool:
    """Return True if update occurred within a private chat."""
    if isinstance(update, CallbackQuery):
        msg = update.message
        return bool(msg and msg.chat and msg.chat.type == ChatType.PRIVATE)
    if isinstance(update, Message):
        return bool(update.chat and update.chat.type == ChatType.PRIVATE)

    # Generic or mock fallback (check message.chat before update.chat for callback queries)
    if hasattr(update, "message") and getattr(update, "message", None) is not None:
        chat = getattr(update.message, "chat", None)
        if chat is not None:
            return getattr(chat, "type", None) == ChatType.PRIVATE

    chat = getattr(update, "chat", None)
    if chat is not None:
        return getattr(chat, "type", None) == ChatType.PRIVATE

    return False


def get_update_user_id(update: Any) -> int | None:
    """Safely extract Telegram numeric user ID from Message or CallbackQuery."""
    from_user = getattr(update, "from_user", None)
    if from_user is not None:
        return getattr(from_user, "id", None)
    return None


def create_admin_private_filter(settings: Settings):
    """Build a Kurigram filter matching only authorized administrators in private chat."""

    async def _filter(_, __, update: Any) -> bool:
        if not is_private_chat(update):
            return False
        user_id = get_update_user_id(update)
        return bool(user_id is not None and settings.is_admin(user_id))

    return filters.create(_filter, "AdminPrivateFilter")


def _is_telegram_update(obj: Any) -> bool:
    """Check if an object is a Telegram update (Message, CallbackQuery, or mock)."""
    return isinstance(obj, (Message, CallbackQuery)) or (
        hasattr(obj, "from_user") and (hasattr(obj, "chat") or hasattr(obj, "message"))
    )


def _is_callback(update: Any) -> bool:
    """Check if update behaves like a CallbackQuery."""
    return isinstance(update, CallbackQuery) or (
        hasattr(update, "answer") and not hasattr(update, "reply_text")
    )


def require_admin_private(settings: Settings) -> Callable:
    """Security decorator ensuring the handler only executes for admins in private chats.

    Provides defense-in-depth even if filter logic is bypassed or misconfigured.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            update = None
            for arg in args:
                if _is_telegram_update(arg):
                    update = arg
                    break

            if update is None:
                return await func(*args, **kwargs)

            if not is_private_chat(update):
                logger.warning("Rejected non-private interaction from %s", update.from_user)
                if _is_callback(update):
                    await update.answer(Messages.PRIVATE_ONLY, show_alert=True)
                elif isinstance(update, Message) or hasattr(update, "reply_text"):
                    await update.reply_text(Messages.PRIVATE_ONLY)
                return None

            user_id = get_update_user_id(update)
            if user_id is None or not settings.is_admin(user_id):
                logger.warning("Unauthorized access attempt from user_id: %s", user_id)
                if _is_callback(update):
                    await update.answer(Messages.UNAUTHORIZED, show_alert=True)
                elif isinstance(update, Message) or hasattr(update, "reply_text"):
                    await update.reply_text(Messages.UNAUTHORIZED)
                return None

            return await func(*args, **kwargs)

        return wrapper

    return decorator
