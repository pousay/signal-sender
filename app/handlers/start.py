"""Start command router distinguishing administrators and regular users."""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from app.config import Settings
from app.keyboards.admin import get_admin_main_menu
from app.keyboards.common import get_support_keyboard
from app.models.state import StateManager
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_start_handler(
    app: Client,
    settings: Settings,
    state_manager: StateManager,
) -> None:
    """Register the /start command handler."""

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not user_id:
            return

        # Check if /start was invoked with a deep-link payload (e.g., /start 123)
        parts = message.text.split(maxsplit=1) if message.text else []
        if len(parts) > 1 and parts[1].strip():
            # Deep link handling is deferred to signal handler
            logger.debug("Received deep-link start query with argument: %s", parts[1])
            return

        if settings.is_admin(user_id):
            # Admin welcome menu
            await state_manager.clear_state(user_id)
            await message.reply_text(
                text=Messages.ADMIN_WELCOME,
                reply_markup=get_admin_main_menu(),
            )
            logger.info("Admin %s accessed main menu via /start", user_id)
        else:
            # Regular user welcome with instructions and support link
            welcome_text = Messages.USER_WELCOME.format(
                support_link=f"@{settings.CONTACT_ADMIN_ID}"
            )
            await message.reply_text(
                text=welcome_text,
                reply_markup=get_support_keyboard(settings.CONTACT_ADMIN_ID),
                disable_web_page_preview=True,
            )
            logger.info("User %s welcomed via /start", user_id)
