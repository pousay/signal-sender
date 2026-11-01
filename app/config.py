"""Application configuration module using Pydantic Settings."""

import re
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MTProto and Bot credentials
    BOT_TOKEN: str = Field(..., description="Telegram Bot API token")
    API_ID: int = Field(..., description="Telegram MTProto API ID")
    API_HASH: str = Field(..., description="Telegram MTProto API Hash")

    # Channels
    CHANNEL_ID: int | str = Field(..., description="Target channel ID or @username")
    SOURCE_CHANNEL_ID: int | str = Field(
        ..., description="Source channel ID or @username for photos"
    )

    # Administration
    ADMIN_IDS: set[int] = Field(
        ...,
        description="Set of Telegram numeric user IDs with administrator rights",
    )
    CONTACT_ADMIN_ID: str = Field(
        ...,
        description="Support Telegram username without @",
    )

    # Operational paths and options
    DATA_DIR: Path = Field(
        default=Path("data"),
        description="Directory for atomic JSON data storage",
    )
    BACKUP_INCLUDE_ENV: bool = Field(
        default=False,
        description="Whether hidden /backup includes .env (defaults to False for security)",
    )
    MAX_SUBSCRIPTION_DAYS: int = Field(
        default=3650,
        description="Maximum allowed duration in days when creating subscriptions",
    )
    BOT_USERNAME: str | None = Field(
        default=None,
        description="Telegram bot username without @ (auto-discovered on startup if None)",
    )

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v: Any) -> set[int]:
        """Parse comma-separated string or iterable into a set of numeric Telegram IDs."""
        if isinstance(v, (set, list, tuple)):
            parsed = {int(x) for x in v}
        elif isinstance(v, str):
            items = [item.strip() for item in v.split(",") if item.strip()]
            if not items:
                raise ValueError("ADMIN_IDS must contain at least one numeric user ID")
            parsed = {int(x) for x in items}
        elif isinstance(v, int):
            parsed = {v}
        else:
            raise TypeError("ADMIN_IDS must be a comma-separated string or collection of ints")

        if not parsed:
            raise ValueError("ADMIN_IDS cannot be empty")
        for admin_id in parsed:
            if admin_id <= 0:
                raise ValueError(f"Admin ID must be a positive integer, got: {admin_id}")
        return parsed

    @field_validator("CHANNEL_ID", "SOURCE_CHANNEL_ID", mode="before")
    @classmethod
    def parse_channel_id(cls, v: Any) -> int | str:
        """Parse channel ID into int if numeric string, or preserve string username."""
        if isinstance(v, str):
            clean = v.strip()
            if clean.startswith("-") and clean[1:].isdigit():
                return int(clean)
            if clean.isdigit():
                return int(clean)
            return clean
        return v

    @field_validator("CONTACT_ADMIN_ID", mode="before")
    @classmethod
    def normalize_support_username(cls, v: Any) -> str:
        """Normalize support username, stripping @ and validating username format."""
        if not isinstance(v, str):
            raise TypeError("CONTACT_ADMIN_ID must be a string username")
        username = v.strip().lstrip("@")
        if not username:
            raise ValueError("CONTACT_ADMIN_ID cannot be empty")
        # Telegram usernames are 5-32 characters, letters, digits, and underscores
        if not re.match(r"^[a-zA-Z0-9_]{4,32}$", username):
            raise ValueError(
                f"Invalid Telegram username '{username}'. "
                "Must be 4-32 characters (letters, digits, _)"
            )
        return username

    @property
    def support_link(self) -> str:
        """Return the clickable Telegram link for the support username."""
        return f"https://t.me/{self.CONTACT_ADMIN_ID}"

    def is_admin(self, user_id: int) -> bool:
        """Check if a numeric user ID is authorized as an administrator."""
        return user_id in self.ADMIN_IDS
