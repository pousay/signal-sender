"""Handlers package."""

from pyrogram import Client

from app.config import Settings
from app.handlers.admin_menu import register_admin_menu_handlers
from app.handlers.photos import register_photo_handlers
from app.handlers.publish import register_publish_handlers
from app.handlers.start import register_start_handler
from app.models.state import StateManager
from app.services.photo_service import PhotoService
from app.services.publication_service import PublicationService
from app.storage.repositories import StorageManager


def register_all_handlers(
    app: Client,
    settings: Settings,
    storage: StorageManager,
    state_manager: StateManager,
    photo_service: PhotoService | None = None,
    publication_service: PublicationService | None = None,
) -> None:
    """Register all bot message and callback handlers."""
    register_start_handler(app, settings, state_manager)
    register_admin_menu_handlers(app, settings, state_manager)
    if photo_service is not None:
        register_photo_handlers(app, settings, photo_service)
    if publication_service is not None:
        register_publish_handlers(app, settings, state_manager, publication_service)
