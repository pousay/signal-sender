"""Tests for admin state manager."""

import pytest

from app.models.state import AdminStep, StateManager


@pytest.mark.asyncio
async def test_state_isolation_between_admins():
    """Verify state operations for one admin do not contaminate another admin."""
    sm = StateManager()

    admin_1 = 111
    admin_2 = 222

    # Set state for admin 1
    await sm.set_state(
        user_id=admin_1,
        step=AdminStep.AWAITING_SIGNAL_TEXT,
        data={"draft_text": "Sample signal"},
    )

    state_1 = await sm.get_state(admin_1)
    state_2 = await sm.get_state(admin_2)

    assert state_1.step == AdminStep.AWAITING_SIGNAL_TEXT
    assert state_1.data["draft_text"] == "Sample signal"

    # Admin 2 remains IDLE with empty data
    assert state_2.step == AdminStep.IDLE
    assert state_2.data == {}

    # Clear admin 1 state
    await sm.clear_state(admin_1)
    cleared_1 = await sm.get_state(admin_1)
    assert cleared_1.step == AdminStep.IDLE
    assert cleared_1.data == {}


@pytest.mark.asyncio
async def test_state_step_transitions():
    sm = StateManager()
    uid = 999

    await sm.set_state(uid, AdminStep.AWAITING_USER_ID, data={"target": "sub"})
    st = await sm.get_state(uid)
    assert st.step == AdminStep.AWAITING_USER_ID

    # Advance to next step, preserving previous data
    await sm.set_state(uid, AdminStep.AWAITING_DURATION_DAYS)
    st2 = await sm.get_state(uid)
    assert st2.step == AdminStep.AWAITING_DURATION_DAYS
    assert st2.data["target"] == "sub"
