"""Tests for async utility functions."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from ai_issue_agent.utils.async_helpers import (
    AgentError,
    CancellationToken,
    ChannelRateLimiter,
    IssueCreateError,
    IssueSearchError,
    LLMAnalysisError,
    RateLimiter,
    RateLimitError,
    SecurityError,
    TimeoutError,
    TracebackParseError,
    api_retry,
    create_retry,
    timeout_decorator,
    with_timeout,
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_agent_error_base(self) -> None:
        """Test AgentError is the base exception."""
        error = AgentError("base error")
        assert str(error) == "base error"
        assert isinstance(error, Exception)

    def test_traceback_parse_error(self) -> None:
        """Test TracebackParseError inherits from AgentError."""
        error = TracebackParseError("parse failed")
        assert isinstance(error, AgentError)

    def test_issue_search_error(self) -> None:
        """Test IssueSearchError inherits from AgentError."""
        error = IssueSearchError("search failed")
        assert isinstance(error, AgentError)

    def test_issue_create_error(self) -> None:
        """Test IssueCreateError inherits from AgentError."""
        error = IssueCreateError("create failed")
        assert isinstance(error, AgentError)

    def test_llm_analysis_error(self) -> None:
        """Test LLMAnalysisError inherits from AgentError."""
        error = LLMAnalysisError("analysis failed")
        assert isinstance(error, AgentError)

    def test_rate_limit_error_with_retry_after(self) -> None:
        """Test RateLimitError with retry_after attribute."""
        error = RateLimitError("rate limited", retry_after=60)
        assert str(error) == "rate limited"
        assert error.retry_after == 60

    def test_rate_limit_error_without_retry_after(self) -> None:
        """Test RateLimitError without retry_after."""
        error = RateLimitError("rate limited")
        assert error.retry_after is None

    def test_security_error(self) -> None:
        """Test SecurityError inherits from AgentError."""
        error = SecurityError("security violation")
        assert isinstance(error, AgentError)

    def test_timeout_error(self) -> None:
        """Test TimeoutError inherits from AgentError."""
        error = TimeoutError("timed out")
        assert isinstance(error, AgentError)


class TestRetryDecorator:
    """Test retry decorator functionality."""

    async def test_api_retry_succeeds_first_try(self) -> None:
        """Test that successful calls don't trigger retry."""
        call_count = 0

        @api_retry
        async def successful_call() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_call()
        assert result == "success"
        assert call_count == 1

    async def test_api_retry_retries_on_timeout(self) -> None:
        """Test retry on httpx.TimeoutException."""
        call_count = 0

        @api_retry
        async def flaky_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return "success"

        result = await flaky_call()
        assert result == "success"
        assert call_count == 3

    async def test_api_retry_retries_on_network_error(self) -> None:
        """Test retry on httpx.NetworkError."""
        call_count = 0

        @api_retry
        async def flaky_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.NetworkError("network error")
            return "success"

        result = await flaky_call()
        assert result == "success"
        assert call_count == 2

    async def test_api_retry_gives_up_after_max_attempts(self) -> None:
        """Test that retry stops after max attempts."""

        @api_retry
        async def always_fails() -> str:
            raise httpx.TimeoutException("always timeout")

        with pytest.raises(httpx.TimeoutException):
            await always_fails()

    async def test_api_retry_does_not_retry_other_exceptions(self) -> None:
        """Test that non-retryable exceptions are not retried."""
        call_count = 0

        @api_retry
        async def raises_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await raises_value_error()

        assert call_count == 1

    async def test_create_retry_custom_config(self) -> None:
        """Test creating a custom retry decorator."""
        call_count = 0

        custom_retry = create_retry(
            max_attempts=2,
            min_wait=0.01,
            max_wait=0.1,
            retry_on=(ValueError,),
        )

        @custom_retry
        async def custom_flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry me")
            return "success"

        result = await custom_flaky()
        assert result == "success"
        assert call_count == 2


class TestRateLimiter:
    """Test rate limiter functionality."""

    async def test_rate_limiter_allows_within_rate(self) -> None:
        """Test that operations within rate limit proceed immediately."""
        limiter = RateLimiter(rate=100, capacity=10)

        start = time.monotonic()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should complete almost immediately
        assert elapsed < 0.1

    async def test_rate_limiter_throttles_when_exceeded(self) -> None:
        """Test that operations exceeding rate are throttled."""
        limiter = RateLimiter(rate=10, capacity=2)

        # Consume initial capacity
        await limiter.acquire(2)

        # This should wait
        start = time.monotonic()
        await limiter.acquire(1)
        elapsed = time.monotonic() - start

        # Should have waited approximately 0.1 seconds (1 token / 10 rate)
        assert elapsed >= 0.09

    async def test_rate_limiter_properties(self) -> None:
        """Test rate limiter property accessors."""
        limiter = RateLimiter(rate=10, capacity=20)

        assert limiter.rate == 10
        assert limiter.capacity == 20
        assert limiter.available_tokens <= 20

    async def test_rate_limiter_context_manager(self) -> None:
        """Test using rate limiter as context manager."""
        limiter = RateLimiter(rate=100, capacity=10)

        async with limiter:
            pass  # Should complete without error

    async def test_rate_limiter_try_acquire_success(self) -> None:
        """Test try_acquire when tokens available."""
        limiter = RateLimiter(rate=100, capacity=10)

        result = await limiter.try_acquire()
        assert result is True

    async def test_rate_limiter_try_acquire_failure(self) -> None:
        """Test try_acquire when tokens not available."""
        limiter = RateLimiter(rate=1, capacity=1)

        # Consume the only token
        await limiter.acquire()

        # Try to acquire immediately should fail
        result = await limiter.try_acquire()
        assert result is False

    async def test_rate_limiter_acquire_exceeds_capacity(self) -> None:
        """Test acquiring more tokens than capacity raises error."""
        limiter = RateLimiter(rate=10, capacity=5)

        with pytest.raises(ValueError, match="Cannot acquire"):
            await limiter.acquire(10)


class TestChannelRateLimiter:
    """Test channel-aware rate limiter."""

    async def test_channel_limiter_per_channel(self) -> None:
        """Test that each channel has its own limit."""
        limiter = ChannelRateLimiter(per_channel_rate=100, per_channel_capacity=5)

        # Each channel should have its own pool
        for _ in range(5):
            await limiter.acquire("#channel-1")
            await limiter.acquire("#channel-2")

    async def test_channel_limiter_with_global_limit(self) -> None:
        """Test global limit across all channels."""
        limiter = ChannelRateLimiter(
            per_channel_rate=100,
            global_rate=100,
            per_channel_capacity=10,
            global_capacity=10,
        )

        # Acquire tokens from different channels
        for _ in range(5):
            await limiter.acquire("#channel-1")

        # Global limit should still allow more
        await limiter.acquire("#channel-2")


class TestTimeoutUtilities:
    """Test timeout utility functions."""

    async def test_with_timeout_succeeds(self) -> None:
        """Test with_timeout when operation completes in time."""

        async def fast_operation() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await with_timeout(fast_operation(), timeout=1.0)
        assert result == "done"

    async def test_with_timeout_times_out(self) -> None:
        """Test with_timeout when operation exceeds timeout."""

        async def slow_operation() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError):
            await with_timeout(slow_operation(), timeout=0.01)

    async def test_with_timeout_custom_message(self) -> None:
        """Test with_timeout with custom error message."""

        async def slow_operation() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError, match="custom timeout"):
            await with_timeout(
                slow_operation(),
                timeout=0.01,
                error_message="custom timeout message",
            )

    async def test_timeout_decorator(self) -> None:
        """Test timeout_decorator on async function."""

        @timeout_decorator(1.0)
        async def fast_func() -> str:
            await asyncio.sleep(0.01)
            return "done"

        result = await fast_func()
        assert result == "done"

    async def test_timeout_decorator_times_out(self) -> None:
        """Test timeout_decorator when function exceeds timeout."""

        @timeout_decorator(0.01)
        async def slow_func() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(TimeoutError):
            await slow_func()


class TestCancellationToken:
    """Test cancellation token functionality."""

    def test_initial_state(self) -> None:
        """Test cancellation token initial state."""
        token = CancellationToken()
        assert not token.is_cancelled

    def test_cancel(self) -> None:
        """Test cancelling the token."""
        token = CancellationToken()
        token.cancel()
        assert token.is_cancelled

    async def test_wait_completes_on_cancel(self) -> None:
        """Test that wait() completes when token is cancelled."""
        token = CancellationToken()

        async def cancel_after_delay() -> None:
            await asyncio.sleep(0.01)
            token.cancel()

        _task = asyncio.create_task(cancel_after_delay())
        await token.wait()
        _ = _task  # Silence RUF006
        assert token.is_cancelled

    def test_raise_if_cancelled_not_cancelled(self) -> None:
        """Test raise_if_cancelled when not cancelled."""
        token = CancellationToken()
        token.raise_if_cancelled()  # Should not raise

    def test_raise_if_cancelled_when_cancelled(self) -> None:
        """Test raise_if_cancelled when cancelled."""
        token = CancellationToken()
        token.cancel()

        with pytest.raises(asyncio.CancelledError):
            token.raise_if_cancelled()

    async def test_cooperative_cancellation(self) -> None:
        """Test using cancellation token for cooperative cancellation."""
        token = CancellationToken()
        iterations = 0

        async def worker() -> int:
            nonlocal iterations
            while not token.is_cancelled:
                iterations += 1
                await asyncio.sleep(0.001)
            return iterations

        # Start worker
        task = asyncio.create_task(worker())

        # Let it run a bit
        await asyncio.sleep(0.01)
        token.cancel()

        result = await task
        assert result > 0
        assert token.is_cancelled
