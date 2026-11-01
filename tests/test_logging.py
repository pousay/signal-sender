"""Tests for custom admin alert logging handler."""

import asyncio
import logging
from pathlib import Path

import pytest

from app.config import Settings
from app.logging_config import AdminAlertHandler


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        BOT_TOKEN="123456:SECRET_BOT_TOKEN_123",
        API_ID=1234567,
        API_HASH="SECRET_API_HASH_456",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="100",
        CONTACT_ADMIN_ID="support_guru",
        DATA_DIR=tmp_path / "data",
    )


@pytest.mark.asyncio
async def test_admin_alert_handler_filtering_and_redaction(test_settings: Settings):
    """Verify handler captures WARNING+, redacts secrets, and deduplicates within 60s."""
    queue = asyncio.Queue()
    handler = AdminAlertHandler(test_settings, queue)

    # 1. INFO record -> Ignored
    info_record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="",
        lineno=1,
        msg="Normal informational log",
        args=(),
        exc_info=None,
    )
    handler.emit(info_record)
    assert queue.empty()

    # 2. WARNING record with secret -> Captured and redacted
    warn_record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname="",
        lineno=1,
        msg=f"Warning occurred with token {test_settings.BOT_TOKEN}",
        args=(),
        exc_info=None,
    )
    handler.emit(warn_record)
    assert not queue.empty()
    alert = queue.get_nowait()
    assert "[REDACTED_BOT_TOKEN]" in alert
    assert test_settings.BOT_TOKEN not in alert
    assert "⚠️ هشدار" in alert

    # 3. Duplicate WARNING immediately after -> Rate-limited (not added to queue)
    handler.emit(warn_record)
    assert queue.empty()

    # 4. Third-party library records -> Ignored to prevent recursive loops
    pyrogram_record = logging.LogRecord(
        name="pyrogram.client",
        level=logging.ERROR,
        pathname="",
        lineno=1,
        msg="Telegram network issue",
        args=(),
        exc_info=None,
    )
    handler.emit(pyrogram_record)
    assert queue.empty()
