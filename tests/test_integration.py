"""Tests for single instance locking and application lifecycle."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.types import User

from app.config import Settings
from app.main import Application


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


def test_single_instance_lock_prevention(test_settings: Settings):
    """Verify second application instance cannot acquire lock on same data dir."""
    app1 = Application(test_settings)
    app1.acquire_single_instance_lock()

    app2 = Application(test_settings)
    with pytest.raises(RuntimeError) as exc_info:
        app2.acquire_single_instance_lock()

    assert "Cannot acquire storage lock" in str(exc_info.value)

    # Releasing app1 allows app2 to acquire
    app1.release_single_instance_lock()
    app2.acquire_single_instance_lock()
    app2.release_single_instance_lock()


@pytest.mark.asyncio
async def test_application_start_and_stop_lifecycle(test_settings: Settings):
    """Verify application boots, initializes storage/workers, and stops cleanly."""
    app = Application(test_settings)

    mock_client = MagicMock(spec=Client)
    mock_client.is_connected = True
    mock_client.start = AsyncMock()
    mock_client.stop = AsyncMock()

    bot_user = MagicMock(spec=User)
    bot_user.id = 12345
    bot_user.username = "test_signal_bot"
    mock_client.get_me = AsyncMock(return_value=bot_user)

    mock_user_client = MagicMock(spec=Client)
    mock_user_client.is_connected = True
    mock_user_client.start = AsyncMock()
    mock_user_client.stop = AsyncMock()

    user_account = MagicMock(spec=User)
    user_account.id = 54321
    user_account.first_name = "UserMTProto"
    mock_user_client.get_me = AsyncMock(return_value=user_account)

    app.client = mock_client
    app.user_client = mock_user_client
    app.publication_service.client = mock_client
    app.subscription_service.client = mock_client
    app.photo_service.client = mock_client
    app.photo_service.user_client = mock_user_client

    # Test start
    await app.start()
    assert mock_client.start.called
    assert mock_user_client.start.called
    assert app.settings.BOT_USERNAME == "test_signal_bot"
    assert app.subscription_service._worker_task is not None

    # Test stop
    await app.stop()
    assert mock_client.stop.called
    assert mock_user_client.stop.called
    assert app.subscription_service._worker_task is None
