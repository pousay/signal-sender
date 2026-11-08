"""Signal access and deep-link resolution handlers."""

import logging

from pyrogram import Client, ContinuePropagation, filters
from pyrogram.types import CallbackQuery, LinkPreviewOptions, Message

from app.config import Settings
from app.keyboards.common import get_support_keyboard
from app.services.subscription_service import SubscriptionService
from app.storage.repositories import StorageManager
from app.utils.formatting import format_premium_signal_details
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


async def deliver_signal_details(
    user_id: int,
    signal_id: int,
    settings: Settings,
    storage: StorageManager,
    subscription_service: SubscriptionService,
    reply_target: Message | CallbackQuery,
) -> None:
    """Validate signal presence and user subscription, sending real details or support link."""
    signals_col = await storage.signals.load()
    signal = signals_col.get_signal(signal_id)

    if not signal:
        logger.info("Signal #%d requested by user %d not found", signal_id, user_id)
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer(Messages.SIGNAL_NOT_FOUND, show_alert=True)
        else:
            await reply_target.reply_text(Messages.SIGNAL_NOT_FOUND)
        return

    is_premium = await subscription_service.is_premium_active(user_id)

    if is_premium:
        details = format_premium_signal_details(
            order_type=getattr(signal, "order_type", "Sell limit"),
            entry_price=getattr(signal, "entry_price", signal.sell_limit),
            stop_loss=signal.stop_loss,
            target=signal.target,
            targets=getattr(signal, "targets", None),
            value=getattr(signal, "value", None),
            sell_limit=signal.sell_limit,
        )
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer()
            if reply_target.message:
                await reply_target.message.reply_text(details)
        else:
            await reply_target.reply_text(details)
        logger.info("Delivered premium details for signal #%d to user %d", signal_id, user_id)

    else:
        support_text = Messages.NON_PREMIUM_MESSAGE.format(
            support_username=f"@{settings.CONTACT_ADMIN_ID}"
        )
        keyboard = get_support_keyboard(settings.CONTACT_ADMIN_ID)
        preview_opts = LinkPreviewOptions(is_disabled=True)
        if isinstance(reply_target, CallbackQuery):
            await reply_target.answer()
            if reply_target.message:
                await reply_target.message.reply_text(
                    text=support_text,
                    reply_markup=keyboard,
                    link_preview_options=preview_opts,
                )
        else:
            await reply_target.reply_text(
                text=support_text,
                reply_markup=keyboard,
                link_preview_options=preview_opts,
            )
        logger.info(
            "Non-premium user %d prompted for support link on signal #%d",
            user_id,
            signal_id,
        )


def register_signal_handlers(
    app: Client,
    settings: Settings,
    storage: StorageManager,
    subscription_service: SubscriptionService,
) -> None:
    """Register deep-link and button callback handlers for signal access."""

    @app.on_message(filters.command("start") & filters.private)
    async def deep_link_start_handler(client: Client, message: Message) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not user_id:
            return

        parts = (message.text or "").split(maxsplit=1)
        if len(parts) <= 1 or not parts[1].strip():
            # Ordinary /start without payload; handled by start router
            raise ContinuePropagation

        raw_arg = parts[1].strip()
        if not raw_arg.isdigit():
            await message.reply_text(Messages.SIGNAL_NOT_FOUND)
            return

        signal_id = int(raw_arg)
        await deliver_signal_details(
            user_id=user_id,
            signal_id=signal_id,
            settings=settings,
            storage=storage,
            subscription_service=subscription_service,
            reply_target=message,
        )
