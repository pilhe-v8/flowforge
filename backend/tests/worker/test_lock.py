"""Tests for SessionLock — distributed Redis lock with Lua-based release."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from flowforge.worker.lock import SessionLock


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    return r


@pytest.mark.asyncio
async def test_lock_acquired_when_set_returns_true(mock_redis):
    """__aenter__ should mark lock as acquired when Redis SET NX succeeds."""
    mock_redis.set = AsyncMock(return_value=True)
    lock = SessionLock(mock_redis, "session-123", ttl=60)

    async with lock as l:
        assert l.acquired is True

    mock_redis.set.assert_awaited_once_with(
        "flowforge:lock:session-123", lock.token, nx=True, ex=60
    )


@pytest.mark.asyncio
async def test_lock_not_acquired_when_set_returns_none(mock_redis):
    """__aenter__ should mark lock as not acquired when Redis SET NX fails (key exists)."""
    mock_redis.set = AsyncMock(return_value=None)
    lock = SessionLock(mock_redis, "session-456", ttl=60)

    async with lock as l:
        assert l.acquired is False


@pytest.mark.asyncio
async def test_exit_runs_lua_when_acquired(mock_redis):
    """__aexit__ should run the Lua script to safely release the lock when acquired."""
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.eval = AsyncMock(return_value=1)
    lock = SessionLock(mock_redis, "session-789", ttl=120)

    async with lock:
        pass

    # Lua script should have been called with the correct key and token
    mock_redis.eval.assert_awaited_once()
    call_args = mock_redis.eval.call_args
    assert call_args[0][1] == 1  # numkeys
    assert call_args[0][2] == "flowforge:lock:session-789"
    assert call_args[0][3] == lock.token


@pytest.mark.asyncio
async def test_exit_skips_lua_when_not_acquired(mock_redis):
    """__aexit__ should NOT run the Lua script when the lock was not acquired."""
    mock_redis.set = AsyncMock(return_value=None)
    mock_redis.eval = AsyncMock()
    lock = SessionLock(mock_redis, "session-000", ttl=120)

    async with lock:
        pass

    mock_redis.eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_lock_key_format(mock_redis):
    """Lock key should follow the flowforge:lock:{session_id} pattern."""
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.eval = AsyncMock(return_value=1)
    lock = SessionLock(mock_redis, "my-session", ttl=30)

    async with lock:
        assert lock.key == "flowforge:lock:my-session"


@pytest.mark.asyncio
async def test_lock_token_is_unique():
    """Each SessionLock instance should have a unique token."""
    r = AsyncMock()
    lock1 = SessionLock(r, "s1")
    lock2 = SessionLock(r, "s2")
    assert lock1.token != lock2.token
