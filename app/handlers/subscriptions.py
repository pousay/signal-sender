"""Admin multi-step subscription workflow handlers."""

import logging

from pyrogram import Client, ContinuePropagation, filters
from pyrogram.types import Message

from app.config import Settings
from app.keyboards.admin import get_cancel_keyboard
from app.models.state import AdminStep, StateManager
from app.services.subscription_service import SubscriptionService
from app.utils.auth import create_admin_private_filter
from app.utils.messages import Messages

logger = logging.getLogger(__name__)


def register_subscription_handlers(
    app: Client,
    settings: Settings,
    state_manager: StateManager,
    subscription_service: SubscriptionService,
) -> None:
    """Register handlers managing admin creation of user subscriptions."""

    admin_filter = create_admin_private_filter(settings)

    @app.on_message(admin_filter & filters.text & ~filters.command(["start", "backup"]))
    async def handle_subscription_step_input(client: Client, message: Message) -> None:
        user_id = message.from_user.id
        state = await state_manager.get_state(user_id)

        if state.step not in (AdminStep.AWAITING_USER_ID, AdminStep.AWAITING_DURATION_DAYS):
            raise ContinuePropagation

        raw_text = (message.text or "").strip()

        # Step 1: Receiving numeric user ID
        if state.step == AdminStep.AWAITING_USER_ID:
            if not raw_text.isdigit() or int(raw_text) <= 0:
                logger.warning("Admin %s provided invalid user ID: %s", user_id, raw_text)
                await message.reply_text(
                    text=Messages.INVALID_USER_ID,
                    reply_markup=get_cancel_keyboard(),
                )
                return

            target_user_id = int(raw_text)
            await state_manager.set_state(
                user_id=user_id,
                step=AdminStep.AWAITING_DURATION_DAYS,
                data={"target_user_id": target_user_id},
            )
            await message.reply_text(
                text=Messages.PROMPT_DURATION_DAYS,
                reply_markup=get_cancel_keyboard(),
            )
            logger.info("Admin %s input target user ID: %d", user_id, target_user_id)
            return

        # Step 2: Receiving duration in days
        if state.step == AdminStep.AWAITING_DURATION_DAYS:
            max_days = settings.MAX_SUBSCRIPTION_DAYS
            if not raw_text.isdigit() or int(raw_text) <= 0 or int(raw_text) > max_days:
                logger.warning("Admin %s provided invalid duration days: %s", user_id, raw_text)
                await message.reply_text(
                    text=Messages.INVALID_DURATION_DAYS.format(max_days=max_days),
                    reply_markup=get_cancel_keyboard(),
                )
                return

            duration_days = int(raw_text)
            target_user_id = state.data.get("target_user_id")
            if not target_user_id:
                logger.error("Lost target_user_id in state for admin %s", user_id)
                await state_manager.clear_state(user_id)
                await message.reply_text(Messages.UNEXPECTED_ERROR)
                return

            try:
                record, notified = await subscription_service.set_subscription(
                    user_id=target_user_id,
                    duration_days=duration_days,
                )
                await state_manager.clear_state(user_id)

                expires_str = record.expires_at.strftime("%Y-%m-%d %H:%M:%S")
                confirm_text = Messages.SUBSCRIPTION_CONFIRM_ADMIN.format(
                    user_id=target_user_id,
                    days=duration_days,
                    expires_at=expires_str,
                )

                if not notified:
                    confirm_text += f"\n\n{Messages.SUBSCRIPTION_USER_NOT_STARTED}"

                await message.reply_text(confirm_text)
                logger.info(
                    "Admin %s registered subscription for user %d (%d days, notified=%s)",
                    user_id,
                    target_user_id,
                    duration_days,
                    notified,
                )

            except Exception as e:
                logger.error("Failed to set subscription: %s", e, exc_info=True)
                await message.reply_text(
                    text=Messages.UNEXPECTED_ERROR,
                    reply_markup=get_cancel_keyboard(),
                )
