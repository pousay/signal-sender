"""Handlers package."""

from pyrogram import Client

from app.config import Settings
from app.handlers.admin_menu import register_admin_menu_handlers
from app.handlers.backup import register_backup_handlers
from app.handlers.photos import register_photo_handlers
from app.handlers.publish import register_publish_handlers
from app.handlers.signals import register_signal_handlers
from app.handlers.start import register_start_handler
from app.handlers.subscriptions import register_subscription_handlers
from app.models.state import StateManager
from app.services.backup_service import BackupService
from app.services.photo_service import PhotoService
from app.services.publication_service import PublicationService
from app.services.subscription_service import SubscriptionService
from app.storage.repositories import StorageManager


def register_all_handlers(
    app: Client,
    settings: Settings,
    storage: StorageManager,
    state_manager: StateManager,
    photo_service: PhotoService | None = None,
    publication_service: PublicationService | None = None,
    subscription_service: SubscriptionService | None = None,
    backup_service: BackupService | None = None,
) -> None:
    """Register all bot message and callback handlers."""
    register_start_handler(app, settings, state_manager)
    register_admin_menu_handlers(app, settings, state_manager)
    if photo_service is not None:
        register_photo_handlers(app, settings, photo_service)
    if publication_service is not None:
        register_publish_handlers(app, settings, state_manager, publication_service)
    if subscription_service is not None:
        register_subscription_handlers(app, settings, state_manager, subscription_service)
        register_signal_handlers(app, settings, storage, subscription_service)
    if backup_service is not None:
        register_backup_handlers(app, settings, backup_service)
