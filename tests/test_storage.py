"""Tests for atomic JSON storage, concurrency locking, and backups."""

import asyncio
from pathlib import Path

import pytest

from app.models.metadata import StorageMetadata
from app.models.photo import PhotoCollection, PhotoRecord
from app.storage.json_store import CorruptedDataError, JsonStore
from app.storage.repositories import StorageManager


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Fixture providing an isolated temporary storage directory."""
    storage_dir = tmp_path / "test_data"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.mark.asyncio
async def test_store_initial_load_with_default(temp_storage_dir: Path):
    """Verify loading a missing file initializes it with default_factory."""
    file_path = temp_storage_dir / "meta.json"
    store = JsonStore(
        path=file_path,
        model_cls=StorageMetadata,
        default_factory=StorageMetadata,
    )

    data = await store.load()
    assert data.next_signal_id == 1
    assert file_path.exists()


@pytest.mark.asyncio
async def test_store_atomic_save_and_backup(temp_storage_dir: Path):
    """Verify save creates pre-mutation backups."""
    file_path = temp_storage_dir / "photos.json"
    backup_dir = temp_storage_dir / "backups"
    store = JsonStore(
        path=file_path,
        model_cls=PhotoCollection,
        default_factory=PhotoCollection,
        backup_dir=backup_dir,
    )

    # Initial load and save
    collection = await store.load()
    collection.photos.append(
        PhotoRecord(file_id="fid_1", file_unique_id="uid_1", message_id=1)
    )
    await store.save(collection, make_backup=True)

    # Subsequent save should trigger backup of prior content
    collection.photos.append(
        PhotoRecord(file_id="fid_2", file_unique_id="uid_2", message_id=2)
    )
    await store.save(collection, make_backup=True)

    backups = list(backup_dir.glob("photos_*.bak.json"))
    assert len(backups) >= 1

    loaded = await store.load()
    assert loaded.count == 2


@pytest.mark.asyncio
async def test_corrupted_file_quarantine(temp_storage_dir: Path):
    """Verify corrupted JSON is quarantined and raises CorruptedDataError."""
    file_path = temp_storage_dir / "corrupted.json"
    file_path.write_text("NOT_JSON_DATA{{{", encoding="utf-8")

    store = JsonStore(
        path=file_path,
        model_cls=StorageMetadata,
        default_factory=StorageMetadata,
    )

    with pytest.raises(CorruptedDataError) as exc_info:
        await store.load()

    assert "is corrupted and was quarantined" in str(exc_info.value)
    # Check that a quarantine file was created
    quarantined = list(temp_storage_dir.glob("corrupted.corrupt_*.json"))
    assert len(quarantined) == 1


@pytest.mark.asyncio
async def test_concurrent_mutations_safety(temp_storage_dir: Path):
    """Verify atomic mutate under concurrency prevents lost updates."""
    file_path = temp_storage_dir / "meta_concurrent.json"
    store = JsonStore(
        path=file_path,
        model_cls=StorageMetadata,
        default_factory=StorageMetadata,
    )
    await store.load()

    async def increment_task():
        def _mutator(data: StorageMetadata):
            data.allocate_signal_id()

        await store.mutate(_mutator, make_backup=False)

    # Run 20 concurrent increments
    await asyncio.gather(*[increment_task() for _ in range(20)])

    final_data = await store.load()
    # Started at next_signal_id=1, after 20 increments it should be 21
    assert final_data.next_signal_id == 21


@pytest.mark.asyncio
async def test_storage_manager_initialization(temp_storage_dir: Path):
    """Verify StorageManager initializes all entity files properly."""
    manager = StorageManager(data_dir=temp_storage_dir)
    await manager.initialize()

    assert (temp_storage_dir / "metadata.json").exists()
    assert (temp_storage_dir / "photos.json").exists()
    assert (temp_storage_dir / "signals.json").exists()
    assert (temp_storage_dir / "subscriptions.json").exists()
