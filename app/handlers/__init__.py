"""Handlers package."""

from pyrogram import Client

from app.config import Settings
from app.handlers.admin_menu import register_admin_menu_handlers
from app.handlers.start import register_start_handler
from app.models.state import StateManager
from app.storage.repositories import StorageManager


def register_all_handlers(
    app: Client,
    settings: Settings,
    storage: StorageManager,
    state_manager: StateManager,
) -> None:
    """Register all bot message and callback handlers."""
    register_start_handler(app, settings, state_manager)
    register_admin_menu_handlers(app, settings, state_manager)
