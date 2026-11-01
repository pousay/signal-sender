"""Tests for subscription management, duration replacement, and expiration reminders."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import UserIsBlocked
from pyrogram.types import Message, User

from app.config import Settings
from app.handlers.subscriptions import register_subscription_handlers
from app.models.state import AdminStep, StateManager
from app.services.subscription_service import SubscriptionService
from app.storage.repositories import StorageManager
from app.utils.messages import Messages


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        API_ID=1234567,
        API_HASH="0123456789abcdef0123456789abcdef",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100",
        CONTACT_ADMIN_ID="support_guru",
        DATA_DIR=tmp_path / "data",
    )


@pytest.fixture
async def test_storage(test_settings: Settings) -> StorageManager:
    manager = StorageManager(data_dir=test_settings.DATA_DIR)
    await manager.initialize()
    return manager


@pytest.mark.asyncio
async def test_set_subscription_replaces_prior_expiration(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify new subscription duration replaces existing expiration rather than extending."""
    mock_client = MagicMock(spec=Client)
    mock_client.send_message = AsyncMock()

    service = SubscriptionService(mock_client, test_settings, test_storage)

    # 1. Set initial 20-day subscription
    rec1, notified1 = await service.set_subscription(user_id=123, duration_days=20)
    assert notified1 is True
    assert rec1.last_duration_days == 20

    # 2. Set new 30-day subscription (replaces prior expiration)
    now = datetime.now(timezone.utc)
    rec2, notified2 = await service.set_subscription(user_id=123, duration_days=30)
    assert notified2 is True
    assert rec2.last_duration_days == 30

    expected_expiry = now + timedelta(days=30)
    # Expiration is within 2 seconds of now + 30 days, NOT now + 50 days!
    assert abs((rec2.expires_at - expected_expiry).total_seconds()) < 2


@pytest.mark.asyncio
async def test_set_subscription_user_not_started_graceful(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify subscription is saved even if activation message cannot be sent to user."""
    mock_client = MagicMock(spec=Client)
    mock_client.send_message = AsyncMock(side_effect=UserIsBlocked(None))

    service = SubscriptionService(mock_client, test_settings, test_storage)
    record, notified = await service.set_subscription(user_id=456, duration_days=10)

    assert record.user_id == 456
    assert notified is False  # Flag indicates user could not be messaged

    # Subscription is still active in storage
    is_active = await service.is_premium_active(456)
    assert is_active is True


@pytest.mark.asyncio
async def test_reminders_and_expiration_notifications(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify 24h reminder and expiry notices are sent once without duplication."""
    mock_client = MagicMock(spec=Client)
    mock_client.send_message = AsyncMock()

    service = SubscriptionService(mock_client, test_settings, test_storage)
    now = datetime.now(timezone.utc)

    # User 1: Expires in 12 hours (due for 24h reminder)
    sub1, _ = await service.set_subscription(user_id=1001, duration_days=1)
    # Adjust expiration manually in storage to 12 hours from now
    async def _adjust1(col):
        col.subscriptions[1001].expires_at = now + timedelta(hours=12)
    await test_storage.subscriptions.mutate(_adjust1, make_backup=False)

    # User 2: Already expired 1 hour ago
    sub2, _ = await service.set_subscription(user_id=1002, duration_days=1)
    async def _adjust2(col):
        col.subscriptions[1002].expires_at = now - timedelta(hours=1)
    await test_storage.subscriptions.mutate(_adjust2, make_backup=False)

    reminders, expiries = await service.process_expirations_and_reminders(now=now)
    assert reminders == 1
    assert expiries == 1

    # Second run immediately: should NOT resend duplicate notifications
    reminders_2, expiries_2 = await service.process_expirations_and_reminders(now=now)
    assert reminders_2 == 0
    assert expiries_2 == 0


@pytest.mark.asyncio
async def test_admin_subscription_wizard_flow(
    test_settings: Settings, test_storage: StorageManager
):
    """Verify multi-step admin input for numeric user ID and duration."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    mock_app.send_message = AsyncMock()

    service = SubscriptionService(mock_app, test_settings, test_storage)
    state_manager = StateManager()

    register_subscription_handlers(mock_app, test_settings, state_manager, service)

    # Step 1: Admin in AWAITING_USER_ID enters an invalid non-digit
    await state_manager.set_state(100, AdminStep.AWAITING_USER_ID)
    msg1 = MagicMock(spec=Message)
    msg1.text = "@some_username"  # Must be rejected!
    msg1.from_user = MagicMock(spec=User)
    msg1.from_user.id = 100
    msg1.chat = MagicMock()
    msg1.chat.type = ChatType.PRIVATE
    msg1.reply_text = AsyncMock()

    await captured_handler(mock_app, msg1)
    msg1.reply_text.assert_called_once_with(
        text=Messages.INVALID_USER_ID,
        reply_markup=msg1.reply_text.call_args[1]["reply_markup"],
    )

    # Step 1 valid: Admin enters numeric user ID
    msg1.reply_text.reset_mock()
    msg1.text = "778899"
    await captured_handler(mock_app, msg1)

    state = await state_manager.get_state(100)
    assert state.step == AdminStep.AWAITING_DURATION_DAYS
    assert state.data["target_user_id"] == 778899

    # Step 2: Admin enters duration in days
    msg2 = MagicMock(spec=Message)
    msg2.text = "45"
    msg2.from_user = MagicMock(spec=User)
    msg2.from_user.id = 100
    msg2.chat = MagicMock()
    msg2.chat.type = ChatType.PRIVATE
    msg2.reply_text = AsyncMock()

    await captured_handler(mock_app, msg2)

    msg2.reply_text.assert_called_once()
    assert "778899" in msg2.reply_text.call_args[0][0]
    assert "45" in msg2.reply_text.call_args[0][0]

    final_state = await state_manager.get_state(100)
    assert final_state.step == AdminStep.IDLE
