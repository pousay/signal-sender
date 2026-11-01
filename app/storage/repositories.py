"""Repository managers providing domain-specific access to persisted entities."""

from pathlib import Path

from app.models.metadata import StorageMetadata
from app.models.photo import PhotoCollection
from app.models.signal import SignalsCollection
from app.models.subscription import SubscriptionCollection
from app.storage.json_store import JsonStore


class StorageManager:
    """Central storage coordinator holding stores for each entity type."""

    def __init__(self, data_dir: Path | str = "data") -> None:
        self.data_dir = Path(data_dir).resolve()
        self.backup_dir = self.data_dir / "backups"

        self.photos: JsonStore[PhotoCollection] = JsonStore(
            path=self.data_dir / "photos.json",
            model_cls=PhotoCollection,
            default_factory=PhotoCollection,
            backup_dir=self.backup_dir,
        )

        self.signals: JsonStore[SignalsCollection] = JsonStore(
            path=self.data_dir / "signals.json",
            model_cls=SignalsCollection,
            default_factory=SignalsCollection,
            backup_dir=self.backup_dir,
        )

        self.subscriptions: JsonStore[SubscriptionCollection] = JsonStore(
            path=self.data_dir / "subscriptions.json",
            model_cls=SubscriptionCollection,
            default_factory=SubscriptionCollection,
            backup_dir=self.backup_dir,
        )

        self.metadata: JsonStore[StorageMetadata] = JsonStore(
            path=self.data_dir / "metadata.json",
            model_cls=StorageMetadata,
            default_factory=StorageMetadata,
            backup_dir=self.backup_dir,
        )

    async def initialize(self) -> None:
        """Verify or create initial state for all storage files."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        await self.metadata.load()
        await self.photos.load()
        await self.signals.load()
        await self.subscriptions.load()
