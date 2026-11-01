"""Photo synchronization admin callback handler."""

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from app.config import Settings
from app.services.photo_service import PhotoService
from app.utils.auth import require_admin_private
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_photo_handlers(
    app: Client,
    settings: Settings,
    photo_service: PhotoService,
) -> None:
    """Register photo management callback handlers."""

    @app.on_callback_query(filters.regex(r"^admin:update_photos$"))
    @require_admin_private(settings)
    async def update_photos_callback(client: Client, callback_query: CallbackQuery) -> None:
        user_id = callback_query.from_user.id
        await callback_query.answer()

        status_msg = await callback_query.message.reply_text(Messages.PHOTO_SYNC_STARTING)
        logger.info("Admin %s initiated photo sync from channel", user_id)

        result = await photo_service.sync_channel_photos()

        if result.success:
            if result.count > 0:
                report = Messages.PHOTO_SYNC_SUCCESS.format(count=result.count)
            else:
                report = Messages.PHOTO_SYNC_ZERO
        else:
            report = Messages.PHOTO_SYNC_FAILED.format(error=result.error or "Unknown error")

        try:
            await status_msg.edit_text(report)
        except Exception as e:
            logger.warning("Could not edit photo sync status message: %s", e)
            await callback_query.message.reply_text(report)
