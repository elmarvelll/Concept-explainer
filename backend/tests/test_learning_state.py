"""Integration tests use the real dev database (a throwaway test user,
cleaned up after) since there's no lightweight in-memory substitute for the
MySQL-specific schema Prisma owns — consistent with how test_problem_finder.py
uses the real Qdrant collection rather than a mock.
"""

import pytest
from sqlalchemy import delete, select

from db import async_session
from learning_state import load_active_state, upsert_state
from models import LearningState, User

pytestmark = pytest.mark.anyio

TEST_USER_ID = "test-learning-state-user"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def _fresh_engine_per_test():
    # db.py's engine/connection pool is a module-level singleton bound to
    # whichever event loop first used it — anyio gives each test its own
    # loop, so a pooled connection from a previous test's (now-closed) loop
    # would blow up here. Disposing forces a fresh connection on next use.
    from db import engine

    yield
    await engine.dispose()


@pytest.fixture
async def test_user():
    async with async_session() as db:
        db.add(User(id=TEST_USER_ID, email="learningstatetest@example.com", name="Test", passwordHash="x"))
        await db.commit()
    yield TEST_USER_ID
    async with async_session() as db:
        await db.execute(delete(User).where(User.id == TEST_USER_ID))
        await db.commit()


async def test_upsert_creates_then_partially_updates(test_user):
    async with async_session() as db:
        state = await upsert_state(
            db, test_user, "Fourier Transform", current_section="18.1", concepts_covered_add=["time domain"]
        )
        assert state.topic == "Fourier Transform"
        assert state.currentSection == "18.1"
        assert state.conceptsCovered == ["time domain"]
        assert state.isActive is True

    # A second call only touching some fields shouldn't clobber the others.
    async with async_session() as db:
        state = await upsert_state(db, test_user, "Fourier Transform", concepts_covered_add=["frequency domain"])
        assert state.currentSection == "18.1"  # untouched, still there
        assert state.conceptsCovered == ["time domain", "frequency domain"]


async def test_understanding_resolves_not_understood(test_user):
    async with async_session() as db:
        await upsert_state(db, test_user, "Fourier Transform", concepts_not_understood_add=["frequency domain"])
    async with async_session() as db:
        state = await upsert_state(db, test_user, "Fourier Transform", concepts_understood_add=["frequency domain"])
        assert "frequency domain" in state.conceptsUnderstood
        assert "frequency domain" not in state.conceptsNotUnderstood


async def test_topic_switch_deactivates_without_erasing(test_user):
    async with async_session() as db:
        await upsert_state(db, test_user, "Fourier Transform", concepts_covered_add=["time domain"])
    async with async_session() as db:
        await upsert_state(db, test_user, "Laplace Transform")

    async with async_session() as db:
        active = await load_active_state(db, test_user)
        assert active.topic == "Laplace Transform"

    # Switch back — Fourier's progress should still be there, not merged
    # with Laplace's and not wiped.
    async with async_session() as db:
        await upsert_state(db, test_user, "Fourier Transform")

    async with async_session() as db:
        active = await load_active_state(db, test_user)
        assert active.topic == "Fourier Transform"
        assert active.conceptsCovered == ["time domain"]

        result = await db.execute(
            select(LearningState).where(LearningState.userId == test_user, LearningState.topic == "Laplace Transform")
        )
        laplace = result.scalar_one()
        assert laplace.isActive is False
