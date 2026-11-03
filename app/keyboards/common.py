"""Common inline keyboards."""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_support_keyboard(support_username: str) -> InlineKeyboardMarkup:
    """Generate keyboard with a link button to support admin."""
    clean_username = support_username.lstrip("@")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 ارتباط با پشتیبانی",
                    url=f"https://t.me/{clean_username}",
                )
            ]
        ]
    )
