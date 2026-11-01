"""Handlers for signal intake, preview confirmation, and channel publication."""

import logging

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from app.config import Settings
from app.keyboards.admin import (
    get_cancel_keyboard,
    get_preview_keyboard,
    get_retry_publish_keyboard,
)
from app.models.state import AdminStep, StateManager
from app.services.publication_service import (
    DraftNotFoundError,
    NoPhotosAvailableError,
    PublicationError,
    PublicationService,
    SignalAlreadyPublishedError,
)
from app.utils.auth import create_admin_private_filter, require_admin_private
from app.utils.formatting import CaptionTooLongError, SignalParseError
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_publish_handlers(
    app: Client,
    settings: Settings,
    state_manager: StateManager,
    publication_service: PublicationService,
) -> None:
    """Register message and callback handlers for signal publication."""

    admin_filter = create_admin_private_filter(settings)

    @app.on_message(admin_filter & filters.text & ~filters.command(["start", "backup"]))
    async def handle_signal_text_input(client: Client, message: Message) -> None:
        user_id = message.from_user.id
        state = await state_manager.get_state(user_id)

        if state.step != AdminStep.AWAITING_SIGNAL_TEXT:
            return

        signal_text = message.text or ""

        try:
            draft, signal_id = await publication_service.create_draft(user_id, signal_text)
        except SignalParseError as err:
            logger.warning("Signal parsing failed for admin %s: %s", user_id, err)
            await message.reply_text(
                text=Messages.SIGNAL_PARSE_ERROR,
                reply_markup=get_cancel_keyboard(),
            )
            return
        except CaptionTooLongError as err:
            logger.warning("Caption length exceeded for admin %s: %s", user_id, err)
            await message.reply_text(
                text=Messages.CAPTION_TOO_LONG,
                reply_markup=get_cancel_keyboard(),
            )
            return
        except NoPhotosAvailableError as err:
            logger.warning("No photos available for draft creation by admin %s: %s", user_id, err)
            await message.reply_text(
                text=Messages.NO_PHOTOS_AVAILABLE,
                reply_markup=get_cancel_keyboard(),
            )
            return
        except Exception as e:
            logger.error("Unexpected error creating signal draft: %s", e, exc_info=True)
            await message.reply_text(
                text=Messages.UNEXPECTED_ERROR,
                reply_markup=get_cancel_keyboard(),
            )
            return

        preview_caption = f"{Messages.PREVIEW_TITLE}\n\n{draft.public_caption}"

        try:
            preview_msg = await message.reply_photo(
                photo=draft.photo_file_id,
                caption=preview_caption,
                reply_markup=get_preview_keyboard(draft.draft_id),
            )

            # Update draft with bot-owned Telegram file_id if available
            if getattr(preview_msg, "photo", None) and getattr(preview_msg.photo, "file_id", None):
                new_fid = preview_msg.photo.file_id

                def _update_draft_fid(col):
                    d = col.get_draft(draft.draft_id)
                    if d:
                        d.photo_file_id = new_fid

                await publication_service.storage.signals.mutate(
                    _update_draft_fid, make_backup=False
                )

            await state_manager.set_state(
                user_id=user_id,
                step=AdminStep.AWAITING_CONFIRMATION,
                data={"draft_id": draft.draft_id, "preview_id": preview_msg.id},
            )
            logger.info("Sent preview for draft %s to admin %s", draft.draft_id, user_id)
        except Exception as e:
            logger.error("Failed to send preview photo to admin %s: %s", user_id, e)
            await message.reply_text(
                text=Messages.UNEXPECTED_ERROR,
                reply_markup=get_cancel_keyboard(),
            )

    @app.on_callback_query(filters.regex(r"^publish:approve:(.+)$"))
    @require_admin_private(settings)
    async def approve_publication_callback(client: Client, callback_query: CallbackQuery) -> None:
        user_id = callback_query.from_user.id
        await callback_query.answer()

        match = callback_query.matches[0]
        draft_id = match.group(1)

        try:
            record = await publication_service.publish_draft(draft_id)
            await state_manager.clear_state(user_id)

            success_text = Messages.PUBLISH_SUCCESS.format(message_id=record.published_message_id)
            if callback_query.message:
                await callback_query.message.reply_text(success_text)
            logger.info("Admin %s approved publication for signal #%d", user_id, record.id)

        except SignalAlreadyPublishedError:
            await state_manager.clear_state(user_id)
            await callback_query.message.reply_text(Messages.PUBLISH_ALREADY_DONE)

        except DraftNotFoundError:
            await state_manager.clear_state(user_id)
            await callback_query.message.reply_text(Messages.SIGNAL_NOT_FOUND)

        except PublicationError as e:
            logger.error("Publication failed for draft %s: %s", draft_id, e)
            error_report = Messages.PUBLISH_FAILED.format(error=str(e))
            await callback_query.message.reply_text(
                text=error_report,
                reply_markup=get_retry_publish_keyboard(draft_id),
            )
