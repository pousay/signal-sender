"""Tests for sanitized backup archive creation and /backup command."""

import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.types import Message, User

from app.config import Settings
from app.handlers.backup import register_backup_handlers
from app.services.backup_service import BackupService
from app.utils.messages import Messages


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Seed mock data and secret files
    (data_dir / "photos.json").write_text('{"version": 1, "photos": []}', encoding="utf-8")
    (data_dir / "signals.json").write_text('{"version": 1, "signals": {}}', encoding="utf-8")
    (data_dir / "sessions").mkdir(parents=True, exist_ok=True)
    (data_dir / "sessions" / "bot.session").write_text("SENSITIVE_SESSION_DATA", encoding="utf-8")

    return Settings(
        BOT_TOKEN="123456:SECRET_BOT_TOKEN_XYZ",
        API_ID=1234567,
        API_HASH="SECRET_API_HASH_XYZ",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100",
        CONTACT_ADMIN_ID="support_guru",
        DATA_DIR=data_dir,
        BACKUP_INCLUDE_ENV=False,
    )


@pytest.mark.asyncio
async def test_backup_archive_excludes_secrets_and_sessions(test_settings: Settings):
    """Verify archive packages json data but excludes session files and .env by default."""
    backup_service = BackupService(test_settings)
    archive_path = await backup_service.create_backup_archive()

    assert archive_path.exists()
    assert archive_path.suffix == ".zip"

    with zipfile.ZipFile(archive_path, "r") as zf:
        namelist = zf.namelist()

        # Data files are present
        assert "data/photos.json" in namelist
        assert "data/signals.json" in namelist

        # Secrets and sessions are strictly EXCLUDED
        assert ".env" not in namelist
        for name in namelist:
            assert not name.endswith(".session")
            assert not name.endswith(".session-journal")
            assert "logs" not in name

    # Cleanup
    archive_path.unlink()
    archive_path.parent.rmdir()


@pytest.mark.asyncio
async def test_backup_command_handler_authorization(test_settings: Settings):
    """Verify /backup handler sends document to authorized admin and rejects non-admin."""
    mock_app = MagicMock(spec=Client)
    captured_handler = None

    def capture_on_message(*args, **kwargs):
        def decorator(f):
            nonlocal captured_handler
            captured_handler = f
            return f

        return decorator

    mock_app.on_message = capture_on_message
    mock_app.send_document = AsyncMock()

    service = BackupService(test_settings)
    register_backup_handlers(mock_app, test_settings, service)

    # 1. Admin invokes /backup
    admin_msg = MagicMock(spec=Message)
    admin_msg.text = "/backup"
    admin_msg.from_user = MagicMock(spec=User)
    admin_msg.from_user.id = 100
    admin_msg.chat = MagicMock()
    admin_msg.chat.type = ChatType.PRIVATE

    status_msg = MagicMock(spec=Message)
    status_msg.delete = AsyncMock()
    admin_msg.reply_text = AsyncMock(return_value=status_msg)

    await captured_handler(mock_app, admin_msg)

    mock_app.send_document.assert_called_once()
    assert mock_app.send_document.call_args[1]["chat_id"] == 100
    assert mock_app.send_document.call_args[1]["caption"] == Messages.BACKUP_SUCCESS

    # 2. Non-admin invokes /backup
    user_msg = MagicMock(spec=Message)
    user_msg.text = "/backup"
    user_msg.from_user = MagicMock(spec=User)
    user_msg.from_user.id = 999  # unauthorized
    user_msg.chat = MagicMock()
    user_msg.chat.type = ChatType.PRIVATE
    user_msg.reply_text = AsyncMock()

    mock_app.send_document.reset_mock()
    await captured_handler(mock_app, user_msg)

    mock_app.send_document.assert_not_called()
    user_msg.reply_text.assert_called_once_with(Messages.UNAUTHORIZED)
