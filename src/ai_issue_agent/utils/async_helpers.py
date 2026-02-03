"""Async utility functions for resilient API calls.

This module provides:
- Retry decorators with exponential backoff
- Rate limiting with token bucket algorithm
- Timeout wrappers for async operations
- Custom exceptions for error handling

See docs/ARCHITECTURE.md for error handling strategy.
"""

from __future__ import annotations

import asyncio
import builtins
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx
import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()

P = ParamSpec("P")
T = TypeVar("T")


# =============================================================================
# Custom Exceptions
# =============================================================================


class AgentError(Exception):
    """Base exception for all agent errors."""


class TracebackParseError(AgentError):
    """Failed to parse traceback from message."""


class IssueSearchError(AgentError):
    """Failed to search for existing issues."""


class IssueCreateError(AgentError):
    """Failed to create new issue."""


class LLMAnalysisError(AgentError):
    """LLM analysis failed."""


class RateLimitError(AgentError):
    """Rate limit exceeded.

    Attributes:
        retry_after: Number of seconds to wait before retrying, if known.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class SecurityError(AgentError):
    """Security violation detected."""


class TimeoutError(AgentError):
    """Operation timed out."""


# =============================================================================
# Retry Decorator
# =============================================================================


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts for debugging."""
    if retry_state.outcome is None:
        return

    exception = retry_state.outcome.exception()
    if exception:
        log.warning(
            "retrying_operation",
            attempt=retry_state.attempt_number,
            exception_type=type(exception).__name__,
            exception_message=str(exception),
            wait_time=retry_state.next_action.sleep if retry_state.next_action else 0,
        )


# Default retry decorator for API calls
api_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    before_sleep=_log_retry,
    reraise=True,
)


def create_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    retry_on: tuple[type[Exception], ...] = (httpx.TimeoutException, httpx.NetworkError),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Create a customized retry decorator.

    Args:
        max_attempts: Maximum number of retry attempts.
        min_wait: Minimum wait time between retries (seconds).
        max_wait: Maximum wait time between retries (seconds).
        retry_on: Tuple of exception types to retry on.

    Returns:
        A retry decorator configured with the given parameters.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retry_on),
        before_sleep=_log_retry,
        reraise=True,
    )


# =============================================================================
# Rate Limiter
# =============================================================================


class RateLimiter:
    """Token bucket rate limiter for async operations.

    This implementation uses the token bucket algorithm to limit the rate of
    operations. Tokens are added to the bucket at a fixed rate, and each
    operation consumes one token. If no tokens are available, the operation
    waits until a token becomes available.

    Example:
        limiter = RateLimiter(rate=10, capacity=20)

        async with limiter:
            await some_api_call()

        # Or use acquire directly
        await limiter.acquire()
        await some_api_call()
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        """Initialize the rate limiter.

        Args:
            rate: Number of operations allowed per second.
            capacity: Maximum number of tokens in the bucket (burst capacity).
                     Defaults to rate (no bursting beyond 1 second).
        """
        self._rate = rate
        self._capacity = capacity if capacity is not None else rate
        self._tokens = self._capacity
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    @property
    def rate(self) -> float:
        """Return the configured rate limit (operations per second)."""
        return self._rate

    @property
    def capacity(self) -> float:
        """Return the bucket capacity (maximum burst size)."""
        return self._capacity

    @property
    def available_tokens(self) -> float:
        """Return the current number of available tokens."""
        self._refill()
        return self._tokens

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_update = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Acquire tokens from the bucket, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire.

        Raises:
            ValueError: If tokens exceeds capacity.
        """
        if tokens > self._capacity:
            msg = f"Cannot acquire {tokens} tokens; capacity is {self._capacity}"
            raise ValueError(msg)

        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return

            # Calculate wait time
            deficit = tokens - self._tokens
            wait_time = deficit / self._rate

            log.debug("rate_limiter_waiting", wait_time=wait_time, deficit=deficit)
            await asyncio.sleep(wait_time)

            self._refill()
            self._tokens -= tokens

    async def try_acquire(self, tokens: float = 1.0) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire.

        Returns:
            True if tokens were acquired, False otherwise.
        """
        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def __aenter__(self) -> RateLimiter:
        """Context manager entry - acquire one token."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - no cleanup needed."""
        pass


class ChannelRateLimiter:
    """Rate limiter with per-channel and global limits.

    This class manages rate limits for multiple channels, ensuring both
    per-channel and global rate limits are respected.

    Example:
        limiter = ChannelRateLimiter(
            per_channel_rate=5,
            global_rate=50,
        )

        await limiter.acquire("#channel-1")
        await some_api_call()
    """

    def __init__(
        self,
        per_channel_rate: float,
        global_rate: float | None = None,
        per_channel_capacity: float | None = None,
        global_capacity: float | None = None,
    ) -> None:
        """Initialize the channel rate limiter.

        Args:
            per_channel_rate: Rate limit per channel (ops/second).
            global_rate: Global rate limit across all channels (ops/second).
                        Defaults to None (no global limit).
            per_channel_capacity: Burst capacity per channel.
            global_capacity: Burst capacity for global limit.
        """
        self._per_channel_rate = per_channel_rate
        self._per_channel_capacity = per_channel_capacity
        self._channel_limiters: dict[str, RateLimiter] = {}
        self._global_limiter = RateLimiter(global_rate, global_capacity) if global_rate else None
        self._lock = asyncio.Lock()

    def _get_channel_limiter(self, channel: str) -> RateLimiter:
        """Get or create a rate limiter for a channel."""
        if channel not in self._channel_limiters:
            self._channel_limiters[channel] = RateLimiter(
                self._per_channel_rate,
                self._per_channel_capacity,
            )
        return self._channel_limiters[channel]

    async def acquire(self, channel: str, tokens: float = 1.0) -> None:
        """Acquire tokens for a specific channel.

        This method ensures both the channel limit and global limit (if set)
        are respected.

        Args:
            channel: The channel identifier.
            tokens: Number of tokens to acquire.
        """
        async with self._lock:
            channel_limiter = self._get_channel_limiter(channel)

        # Acquire from both limiters
        await channel_limiter.acquire(tokens)
        if self._global_limiter:
            await self._global_limiter.acquire(tokens)


# =============================================================================
# Timeout Utilities
# =============================================================================


async def with_timeout(
    coro: Awaitable[T],
    timeout: float,
    error_message: str | None = None,
) -> T:
    """Execute an awaitable with a timeout.

    Args:
        coro: The coroutine to execute.
        timeout: Timeout in seconds.
        error_message: Custom error message for timeout.

    Returns:
        The result of the coroutine.

    Raises:
        TimeoutError: If the operation times out.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except builtins.TimeoutError as e:
        msg = error_message or f"Operation timed out after {timeout}s"
        log.warning("operation_timeout", timeout=timeout)
        raise TimeoutError(msg) from e


def timeout_decorator(
    timeout: float,
    error_message: str | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator to add timeout to async functions.

    Args:
        timeout: Timeout in seconds.
        error_message: Custom error message for timeout.

    Returns:
        A decorator that adds timeout behavior.

    Example:
        @timeout_decorator(30.0)
        async def slow_operation():
            ...
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await with_timeout(func(*args, **kwargs), timeout, error_message)

        return wrapper

    return decorator


# =============================================================================
# Cancellation Utilities
# =============================================================================


class CancellationToken:
    """Token for cooperative cancellation of async operations.

    Example:
        token = CancellationToken()

        async def worker(token: CancellationToken):
            while not token.is_cancelled:
                await do_work()

        # Cancel from elsewhere
        token.cancel()
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation."""
        self._cancelled = True
        self._event.set()

    async def wait(self) -> None:
        """Wait until cancellation is requested."""
        await self._event.wait()

    def raise_if_cancelled(self) -> None:
        """Raise asyncio.CancelledError if cancelled.

        Use this to create cancellation points in long-running operations.
        """
        if self._cancelled:
            raise asyncio.CancelledError("Operation was cancelled")
