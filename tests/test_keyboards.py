"""Tests for inline keyboards."""

from app.keyboards.admin import (
    get_admin_main_menu,
    get_cancel_keyboard,
    get_channel_post_keyboard,
    get_preview_keyboard,
)
from app.keyboards.common import get_support_keyboard
from app.utils.messages import Messages


def test_admin_main_menu_exact_structure():
    """Verify admin menu has strictly 2 buttons in 2 rows with exact Persian labels."""
    kb = get_admin_main_menu()
    assert len(kb.inline_keyboard) == 2

    row1 = kb.inline_keyboard[0]
    assert len(row1) == 1
    assert row1[0].text == Messages.BTN_UPDATE_PHOTOS
    assert row1[0].callback_data == "admin:update_photos"

    row2 = kb.inline_keyboard[1]
    assert len(row2) == 1
    assert row2[0].text == Messages.BTN_SEND_PREMIUM
    assert row2[0].callback_data == "admin:send_premium"


def test_cancel_keyboard():
    """Verify cancel keyboard contains the cancel button."""
    kb = get_cancel_keyboard()
    assert len(kb.inline_keyboard) == 1
    btn = kb.inline_keyboard[0][0]
    assert btn.text == Messages.BTN_CANCEL
    assert btn.callback_data == "flow:cancel"


def test_preview_keyboard():
    """Verify preview keyboard contains approve and cancel buttons."""
    kb = get_preview_keyboard(draft_id="draft_123")
    assert len(kb.inline_keyboard) == 2
    approve_btn = kb.inline_keyboard[0][0]
    cancel_btn = kb.inline_keyboard[1][0]

    assert approve_btn.text == Messages.BTN_APPROVE_AND_PUBLISH
    assert approve_btn.callback_data == "publish:approve:draft_123"
    assert cancel_btn.text == Messages.BTN_CANCEL
    assert cancel_btn.callback_data == "flow:cancel"


def test_channel_post_keyboard():
    """Verify channel post keyboard attaches deep link button."""
    kb = get_channel_post_keyboard(bot_username="signals_bot", signal_id=42)
    assert len(kb.inline_keyboard) == 1
    btn = kb.inline_keyboard[0][0]
    assert btn.text == Messages.BTN_VIEW_POSITION
    assert btn.url == "https://t.me/signals_bot?start=42"


def test_support_keyboard():
    """Verify support keyboard button text is Persian without parentheses and with emoji."""
    kb = get_support_keyboard("support_guru")
    assert len(kb.inline_keyboard) == 1
    btn = kb.inline_keyboard[0][0]
    assert btn.text == "💬 ارتباط با پشتیبانی"
    assert btn.url == "https://t.me/support_guru"
