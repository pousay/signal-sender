"""Tests for Pydantic models."""

from datetime import datetime, timedelta, timezone

from app.models.metadata import StorageMetadata
from app.models.photo import PhotoCollection, PhotoRecord
from app.models.subscription import SubscriptionCollection


def test_photo_collection_operations():
    collection = PhotoCollection()
    assert collection.is_empty is True
    assert collection.select_random() is None

    p1 = PhotoRecord(file_id="fid_1", file_unique_id="uid_1", message_id=10)
    p2 = PhotoRecord(file_id="fid_2", file_unique_id="uid_2", message_id=11)
    collection.photos.extend([p1, p2])

    assert collection.count == 2
    assert collection.is_empty is False
    assert collection.contains_unique_id("uid_1") is True
    assert collection.contains_unique_id("uid_unknown") is False

    chosen = collection.select_random()
    assert chosen in (p1, p2)


def test_subscription_lifecycle():
    now = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    collection = SubscriptionCollection()

    # Create 30 days subscription
    sub = collection.set_subscription(user_id=12345, duration_days=30, now=now)
    assert sub.user_id == 12345
    assert sub.last_duration_days == 30
    assert sub.expires_at == now + timedelta(days=30)
    assert sub.is_active(now) is True
    assert sub.is_expired(now) is False
    assert sub.is_due_for_24h_reminder(now) is False

    # 29 days later (24h before expiry)
    near_expiry = now + timedelta(days=29, hours=1)
    assert sub.is_active(near_expiry) is True
    assert sub.is_due_for_24h_reminder(near_expiry) is True

    # Replacement duration (must replace rather than extend)
    sub2 = collection.set_subscription(user_id=12345, duration_days=5, now=now)
    assert sub2.expires_at == now + timedelta(days=5)
    assert sub2.last_duration_days == 5


def test_storage_metadata_allocation():
    meta = StorageMetadata()
    assert meta.next_signal_id == 1
    id1 = meta.allocate_signal_id()
    assert id1 == 1
    assert meta.next_signal_id == 2
    id2 = meta.allocate_signal_id()
    assert id2 == 2
    assert meta.next_signal_id == 3
