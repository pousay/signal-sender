"""Tests for configuration parsing and validation."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_valid_configuration():
    """Verify valid environment settings produce expected parsed values."""
    settings = Settings(
        BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        API_ID=1234567,
        API_HASH="0123456789abcdef0123456789abcdef",
        CHANNEL_ID="-1001234567890",
        SOURCE_CHANNEL_ID=-1009876543210,
        ADMIN_IDS="111111, 222222",
        CONTACT_ADMIN_ID="@my_support_bot",
    )
    assert settings.BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert settings.API_ID == 1234567
    assert settings.CHANNEL_ID == -1001234567890
    assert settings.SOURCE_CHANNEL_ID == -1009876543210
    assert settings.ADMIN_IDS == {111111, 222222}
    assert settings.CONTACT_ADMIN_ID == "my_support_bot"
    assert settings.support_link == "https://t.me/my_support_bot"
    assert settings.is_admin(111111) is True
    assert settings.is_admin(999999) is False


def test_invalid_admin_ids():
    """Verify malformed admin IDs fail validation."""
    with pytest.raises(ValidationError):
        Settings(
            BOT_TOKEN="token",
            API_ID=123,
            API_HASH="hash",
            CHANNEL_ID=123,
            SOURCE_CHANNEL_ID=456,
            ADMIN_IDS="not_an_int, 456",
            CONTACT_ADMIN_ID="support",
        )

    with pytest.raises(ValidationError):
        Settings(
            BOT_TOKEN="token",
            API_ID=123,
            API_HASH="hash",
            CHANNEL_ID=123,
            SOURCE_CHANNEL_ID=456,
            ADMIN_IDS="-5",  # negative ID
            CONTACT_ADMIN_ID="support",
        )


def test_invalid_contact_admin_username():
    """Verify invalid telegram username fails validation."""
    with pytest.raises(ValidationError):
        Settings(
            BOT_TOKEN="token",
            API_ID=123,
            API_HASH="hash",
            CHANNEL_ID=123,
            SOURCE_CHANNEL_ID=456,
            ADMIN_IDS="123",
            CONTACT_ADMIN_ID="@",  # empty after strip
        )


def test_dotenv_source_parsing_admin_ids(tmp_path):
    """Verify DotEnvSettingsSource parses comma-separated string without SettingsError."""
    env_content = (
        "BOT_TOKEN=123456:ABC\n"
        "API_ID=1234567\n"
        "API_HASH=0123456789abcdef\n"
        "CHANNEL_ID=-1001234567890\n"
        "SOURCE_CHANNEL_ID=-1009876543210\n"
        "ADMIN_IDS=123456789, 987654321\n"
        "CONTACT_ADMIN_ID=support_guru\n"
    )
    env_file = tmp_path / ".env"
    env_file.write_text(env_content, encoding="utf-8")

    settings = Settings(_env_file=env_file)
    assert settings.ADMIN_IDS == {123456789, 987654321}
    assert settings.CHANNEL_ID == -1001234567890
