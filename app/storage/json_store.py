"""Atomic JSON persistence layer with async concurrency locking and backups."""

import asyncio
import inspect
import json
import logging
import os
import shutil
import uuid
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StorageError(Exception):
    """Base exception for storage errors."""


class CorruptedDataError(StorageError):
    """Raised when existing storage file contains invalid or corrupted JSON."""


class JsonStore(Generic[T]):
    """Async-safe, atomic JSON storage engine for Pydantic models."""

    def __init__(
        self,
        path: Path | str,
        model_cls: type[T],
        default_factory: Callable[[], T] | None = None,
        backup_dir: Path | str | None = None,
        max_backups: int = 10,
    ) -> None:
        self.path = Path(path).resolve()
        self.model_cls = model_cls
        self.default_factory = default_factory
        self.backup_dir = (
            Path(backup_dir).resolve()
            if backup_dir
            else self.path.parent / "backups"
        )
        self.max_backups = max_backups
        self._lock = asyncio.Lock()

    async def load(self) -> T:
        """Load and validate data from JSON file or return default.

        Acquires async lock to guarantee consistent reads.
        """
        async with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> T:
        """Load data from disk without locking (internal use)."""
        if not self.path.exists():
            if self.default_factory is not None:
                default_data = self.default_factory()
                self._save_unlocked(default_data, make_backup=False)
                return default_data
            raise FileNotFoundError(f"Storage file not found: {self.path}")

        try:
            content = self.path.read_text(encoding="utf-8")
            if not content.strip():
                raise ValueError("Storage file is empty")
            return self.model_cls.model_validate_json(content)
        except (json.JSONDecodeError, ValidationError, ValueError) as err:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            quarantine_path = self.path.with_name(f"{self.path.stem}.corrupt_{timestamp}.json")
            try:
                shutil.copy2(self.path, quarantine_path)
                logger.error(
                    "Corrupted storage file quarantined to %s: %s",
                    quarantine_path,
                    err,
                )
            except Exception as copy_err:
                logger.critical("Failed to quarantine corrupted storage file: %s", copy_err)

            raise CorruptedDataError(
                f"Storage file {self.path} is corrupted and was quarantined "
                f"to {quarantine_path}: {err}"
            ) from err

    async def save(self, data: T, make_backup: bool = True) -> None:
        """Atomically persist data to disk under lock."""
        async with self._lock:
            self._save_unlocked(data, make_backup=make_backup)

    def _save_unlocked(self, data: T, make_backup: bool = True) -> None:
        """Persist data atomically without locking (internal use)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-mutation backup
        if make_backup and self.path.exists():
            self._create_backup_unlocked()

        # Temporary file write in the same directory for atomic rename
        temp_name = f".{self.path.stem}_{uuid.uuid4().hex}.tmp"
        temp_path = self.path.parent / temp_name

        try:
            serialized = data.model_dump_json(indent=2)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace
            os.replace(temp_path, self.path)
        except Exception as e:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            logger.error("Failed atomic write to %s: %s", self.path, e)
            raise StorageError(f"Failed to persist {self.path}: {e}") from e

    def _create_backup_unlocked(self) -> None:
        """Copy current file into backups directory and rotate old backups."""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            backup_file = self.backup_dir / f"{self.path.stem}_{timestamp}.bak.json"
            shutil.copy2(self.path, backup_file)
            self._rotate_backups_unlocked()
        except Exception as e:
            logger.warning("Could not create backup for %s: %s", self.path, e)

    def _rotate_backups_unlocked(self) -> None:
        """Rotate backups keeping only up to max_backups files."""
        try:
            prefix = f"{self.path.stem}_"
            backups = sorted(
                [f for f in self.backup_dir.glob(f"{prefix}*.bak.json") if f.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for old_backup in backups[self.max_backups :]:
                try:
                    old_backup.unlink()
                except OSError:
                    pass
        except Exception as e:
            logger.warning("Failed to rotate backups in %s: %s", self.backup_dir, e)

    async def mutate(
        self,
        func: Callable[[T], None | Coroutine[Any, Any, None]],
        make_backup: bool = True,
    ) -> T:
        """Load data, apply mutation function, and atomically persist under the same lock."""
        async with self._lock:
            data = self._load_unlocked()
            result = func(data)
            if inspect.isawaitable(result):
                await result
            self._save_unlocked(data, make_backup=make_backup)
            return data
