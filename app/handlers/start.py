"""Start command router distinguishing administrators and regular users."""

import logging
from typing import TYPE_CHECKING

from pyrogram import Client, ContinuePropagation, filters
from pyrogram.types import LinkPreviewOptions, Message

from app.config import Settings
from app.keyboards.admin import get_admin_main_menu
from app.keyboards.common import get_support_keyboard
from app.models.state import StateManager
from app.utils.messages import Messages

if TYPE_CHECKING:
    from app.services.subscription_service import SubscriptionService
    from app.storage.repositories import StorageManager

logger = logging.getLogger(__name__)


def register_start_handler(
    app: Client,
    settings: Settings,
    state_manager: StateManager,
    storage: "StorageManager | None" = None,
    subscription_service: "SubscriptionService | None" = None,
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
            raw_arg = parts[1].strip()
            logger.debug("Received deep-link start query with argument: %s", raw_arg)

            if storage is not None and subscription_service is not None:
                from app.handlers.signals import deliver_signal_details

                if not raw_arg.isdigit():
                    await message.reply_text(Messages.SIGNAL_NOT_FOUND)
                    return

                signal_id = int(raw_arg)
                await deliver_signal_details(
                    user_id=user_id,
                    signal_id=signal_id,
                    settings=settings,
                    storage=storage,
                    subscription_service=subscription_service,
                    reply_target=message,
                )
                return

            raise ContinuePropagation

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
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            logger.info("User %s welcomed via /start", user_id)
