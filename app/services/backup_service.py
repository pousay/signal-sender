"""Sanitized backup service packaging data files without leaking credentials."""

import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class BackupService:
    """Creates sanitized ZIP backups excluding secrets, session files, and logs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_backup_archive(self) -> Path:
        """Create a timestamped ZIP archive containing data and safe settings.

        Excludes:
            - .env (unless BACKUP_INCLUDE_ENV is True, default False)
            - *.session and *.session-journal (MTProto credentials)
            - logs, virtual environments, .git, and __pycache__
        """
        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        temp_dir = Path(tempfile.mkdtemp(prefix="bot_backup_"))
        archive_path = temp_dir / f"backup_{timestamp}.zip"

        logger.info("Generating sanitized backup archive at: %s", archive_path)

        data_dir = self.settings.DATA_DIR.resolve()

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Package data/*.json files
            if data_dir.exists():
                for file_path in data_dir.glob("*.json"):
                    if file_path.is_file():
                        # Prevent path traversal: use relative archive name
                        archive_name = f"data/{file_path.name}"
                        zf.write(file_path, arcname=archive_name)
                        logger.debug("Added to backup: %s", archive_name)

            # 2. Package .env ONLY if explicitly configured
            if self.settings.BACKUP_INCLUDE_ENV:
                env_file = Path(".env").resolve()
                if env_file.exists():
                    logger.warning("Including .env in backup due to BACKUP_INCLUDE_ENV=True!")
                    zf.write(env_file, arcname=".env")

            # 3. Include .env.example and pyproject.toml as safe project metadata
            for safe_meta in [Path(".env.example"), Path("pyproject.toml")]:
                if safe_meta.exists():
                    zf.write(safe_meta, arcname=safe_meta.name)

        archive_size = os.path.getsize(archive_path)
        logger.info(
            "Backup archive successfully created (%d bytes, path: %s)",
            archive_size,
            archive_path,
        )
        return archive_path
