"""Subscription data models and state management."""

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class SubscriptionRecord(BaseModel):
    """User premium subscription record."""

    user_id: int = Field(..., description="Numeric Telegram user ID")
    expires_at: datetime = Field(..., description="UTC expiration timestamp")
    activated_at: datetime = Field(default_factory=utc_now, description="UTC activation timestamp")
    last_duration_days: int = Field(..., description="Duration applied in days")
    reminder_24h_sent: bool = Field(
        default=False, description="Flag indicating 24h expiration reminder was sent"
    )
    expired_notified: bool = Field(
        default=False, description="Flag indicating expiration notice was sent"
    )

    def is_active(self, now: datetime | None = None) -> bool:
        """Check whether subscription is currently active."""
        current = now or utc_now()
        return current < self.expires_at

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check whether subscription has expired."""
        current = now or utc_now()
        return current >= self.expires_at

    def is_due_for_24h_reminder(self, now: datetime | None = None) -> bool:
        """Return True if within 24h of expiration and reminder has not yet been delivered."""
        if self.reminder_24h_sent:
            return False
        current = now or utc_now()
        if current >= self.expires_at:
            return False
        return (self.expires_at - current) <= timedelta(hours=24)


class SubscriptionCollection(BaseModel):
    """Container for active and past subscriptions keyed by numeric user ID."""

    version: int = Field(default=1, description="Schema version")
    subscriptions: dict[int, SubscriptionRecord] = Field(
        default_factory=dict, description="Map of user_id to subscription"
    )

    def get(self, user_id: int) -> SubscriptionRecord | None:
        """Retrieve user subscription if exists."""
        return self.subscriptions.get(user_id)

    def set_subscription(
        self, user_id: int, duration_days: int, now: datetime | None = None
    ) -> SubscriptionRecord:
        """Create or replace a subscription with now + duration_days.

        Replaces prior subscription completely rather than extending.
        Resets notification delivery flags.
        """
        current = now or utc_now()
        expires_at = current + timedelta(days=duration_days)
        record = SubscriptionRecord(
            user_id=user_id,
            expires_at=expires_at,
            activated_at=current,
            last_duration_days=duration_days,
            reminder_24h_sent=False,
            expired_notified=False,
        )
        self.subscriptions[user_id] = record
        return record
