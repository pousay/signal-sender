"""Inline keyboards for admin interactions."""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.utils.messages import Messages


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Generate the main admin menu strictly containing the 3 required inline buttons."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(Messages.BTN_POST_SIGNAL, callback_data="admin:post_signal")],
            [InlineKeyboardButton(Messages.BTN_UPDATE_PHOTOS, callback_data="admin:update_photos")],
            [InlineKeyboardButton(Messages.BTN_SEND_PREMIUM, callback_data="admin:send_premium")],
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Generate an inline keyboard containing only the cancel button."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="flow:cancel")],
        ]
    )


def get_preview_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for signal draft preview."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    Messages.BTN_APPROVE_AND_PUBLISH,
                    callback_data=f"publish:approve:{draft_id}",
                )
            ],
            [InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="flow:cancel")],
        ]
    )


def get_retry_publish_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    """Generate inline keyboard for retry after failed publication."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    Messages.BTN_RETRY_PUBLISH,
                    callback_data=f"publish:approve:{draft_id}",
                )
            ],
            [InlineKeyboardButton(Messages.BTN_CANCEL, callback_data="flow:cancel")],
        ]
    )


def get_channel_post_keyboard(bot_username: str, signal_id: int) -> InlineKeyboardMarkup:
    """Generate inline button attached directly under the published channel post."""
    url = f"https://t.me/{bot_username}?start={signal_id}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(Messages.BTN_VIEW_POSITION, url=url)],
        ]
    )
