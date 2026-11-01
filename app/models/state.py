"""Admin conversation state models and in-memory session manager."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class AdminStep(str, Enum):
    """Enumeration of active conversation steps for multi-step admin workflows."""

    IDLE = "idle"
    AWAITING_SIGNAL_TEXT = "awaiting_signal_text"
    AWAITING_USER_ID = "awaiting_user_id"
    AWAITING_DURATION_DAYS = "awaiting_duration_days"
    AWAITING_CONFIRMATION = "awaiting_confirmation"


class AdminState(BaseModel):
    """Current state for a specific admin user."""

    user_id: int = Field(..., description="Telegram numeric user ID")
    step: AdminStep = Field(default=AdminStep.IDLE, description="Current workflow step")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Temporary workflow context data"
    )
    prompt_message_id: int | None = Field(
        default=None, description="Message ID of the active prompt sent to admin"
    )
    updated_at: datetime = Field(
        default_factory=utc_now, description="Timestamp of last state modification"
    )


class StateManager:
    """Async-safe in-memory state manager guaranteeing isolation between admins."""

    def __init__(self) -> None:
        self._states: dict[int, AdminState] = {}
        self._lock = asyncio.Lock()

    async def get_state(self, user_id: int) -> AdminState:
        """Retrieve current state for user, initializing to IDLE if none exists."""
        async with self._lock:
            if user_id not in self._states:
                self._states[user_id] = AdminState(user_id=user_id)
            return self._states[user_id]

    async def set_state(
        self,
        user_id: int,
        step: AdminStep,
        data: dict[str, Any] | None = None,
        prompt_message_id: int | None = None,
    ) -> AdminState:
        """Update user step and merge context data."""
        async with self._lock:
            existing = self._states.get(user_id)
            new_data = data if data is not None else (existing.data if existing else {})
            state = AdminState(
                user_id=user_id,
                step=step,
                data=new_data,
                prompt_message_id=prompt_message_id,
                updated_at=utc_now(),
            )
            self._states[user_id] = state
            return state

    async def clear_state(self, user_id: int) -> None:
        """Reset user state to IDLE and clear context data."""
        async with self._lock:
            self._states[user_id] = AdminState(user_id=user_id, step=AdminStep.IDLE)
