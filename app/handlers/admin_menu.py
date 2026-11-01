"""Admin main menu and workflow cancellation callbacks."""

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from app.config import Settings
from app.keyboards.admin import get_cancel_keyboard
from app.models.state import AdminStep, StateManager
from app.utils.auth import require_admin_private
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_admin_menu_handlers(
    app: Client,
    settings: Settings,
    state_manager: StateManager,
) -> None:
    """Register menu action callbacks and cancellation handlers."""

    @app.on_callback_query(filters.regex(r"^flow:cancel$"))
    @require_admin_private(settings)
    async def cancel_callback(client: Client, callback_query: CallbackQuery) -> None:
        user_id = callback_query.from_user.id
        state = await state_manager.get_state(user_id)
        await state_manager.clear_state(user_id)
        await callback_query.answer()

        # If rejecting the post preview message, delete the message in admin PV
        if state.step == AdminStep.AWAITING_CONFIRMATION or (
            callback_query.message and getattr(callback_query.message, "photo", None)
        ):
            if callback_query.message:
                try:
                    await callback_query.message.delete()
                except Exception as del_err:
                    logger.warning(
                        "Could not delete post message on cancel for admin %s: %s",
                        user_id,
                        del_err,
                    )
            await client.send_message(chat_id=user_id, text=Messages.OPERATION_CANCELLED)
        else:
            try:
                # Edit ordinary text prompts (e.g. prompt for signal text or user ID)
                if callback_query.message:
                    await callback_query.message.edit_text(
                        text=Messages.OPERATION_CANCELLED,
                        reply_markup=None,
                    )
            except Exception as e:
                logger.warning("Could not edit prompt on cancel for admin %s: %s", user_id, e)
                await callback_query.message.reply_text(Messages.OPERATION_CANCELLED)

        logger.info("Admin %s cancelled active workflow", user_id)

    @app.on_callback_query(filters.regex(r"^admin:post_signal$"))
    @require_admin_private(settings)
    async def post_signal_menu_callback(client: Client, callback_query: CallbackQuery) -> None:
        user_id = callback_query.from_user.id
        await callback_query.answer()

        sent = await callback_query.message.reply_text(
            text=Messages.PROMPT_SIGNAL_TEXT,
            reply_markup=get_cancel_keyboard(),
        )
        await state_manager.set_state(
            user_id=user_id,
            step=AdminStep.AWAITING_SIGNAL_TEXT,
            prompt_message_id=sent.id,
        )
        logger.info("Admin %s initiated post signal flow", user_id)

    @app.on_callback_query(filters.regex(r"^admin:send_premium$"))
    @require_admin_private(settings)
    async def send_premium_menu_callback(client: Client, callback_query: CallbackQuery) -> None:
        user_id = callback_query.from_user.id
        await callback_query.answer()

        sent = await callback_query.message.reply_text(
            text=Messages.PROMPT_USER_ID,
            reply_markup=get_cancel_keyboard(),
        )
        await state_manager.set_state(
            user_id=user_id,
            step=AdminStep.AWAITING_USER_ID,
            prompt_message_id=sent.id,
        )
        logger.info("Admin %s initiated send premium flow", user_id)
