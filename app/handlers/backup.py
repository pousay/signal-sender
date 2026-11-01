"""Hidden /backup command handler for authorized administrators."""

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from app.config import Settings
from app.services.backup_service import BackupService
from app.utils.auth import require_admin_private
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_backup_handlers(
    app: Client,
    settings: Settings,
    backup_service: BackupService,
) -> None:
    """Register hidden /backup command handler."""

    @app.on_message(filters.command("backup") & filters.private)
    @require_admin_private(settings)
    async def backup_command_handler(client: Client, message: Message) -> None:
        user_id = message.from_user.id
        status_msg = await message.reply_text(Messages.BACKUP_CREATING)
        logger.info("Admin %s invoked hidden /backup command", user_id)

        try:
            archive_path = await backup_service.create_backup_archive()
            try:
                await client.send_document(
                    chat_id=user_id,
                    document=str(archive_path),
                    caption=Messages.BACKUP_SUCCESS,
                )
                await status_msg.delete()
            finally:
                # Clean up temporary archive file and directory
                try:
                    if archive_path.exists():
                        archive_path.unlink()
                    if archive_path.parent.exists():
                        archive_path.parent.rmdir()
                except Exception as clean_err:
                    logger.warning("Failed to clean up temp backup archive: %s", clean_err)

            logger.info("Backup successfully dispatched to admin %s", user_id)

        except Exception as e:
            logger.error("Failed to generate backup archive: %s", e, exc_info=True)
            error_report = Messages.BACKUP_FAILED.format(error=str(e))
            try:
                await status_msg.edit_text(error_report)
            except Exception:
                await message.reply_text(error_report)
