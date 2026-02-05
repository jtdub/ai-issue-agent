"""Metrics collection for observability.

This module provides application metrics for monitoring:
- Message processing counters
- Issue creation/linking counters
- Processing duration histograms
- Error rates
- Cache statistics

Metrics are designed to be compatible with Prometheus-style monitoring
but can be exported in various formats.

See docs/admin-guide/monitoring.md for operational guidance.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any

import structlog

log = structlog.get_logger()


class MetricType(StrEnum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class MetricValue:
    """A single metric value with metadata."""

    name: str
    type: MetricType
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    help_text: str = ""


class Counter:
    """A monotonically increasing counter.

    Example:
        counter = Counter("messages_processed", "Total messages processed")
        counter.inc()  # Increment by 1
        counter.inc(5)  # Increment by 5
        counter.inc(labels={"channel": "errors"})  # With labels
    """

    def __init__(self, name: str, help_text: str = "") -> None:
        """Initialize counter.

        Args:
            name: Metric name
            help_text: Description of the metric
        """
        self.name = name
        self.help_text = help_text
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = Lock()

    def inc(self, value: float = 1, labels: dict[str, str] | None = None) -> None:
        """Increment the counter.

        Args:
            value: Amount to increment (default 1)
            labels: Optional labels for this observation
        """
        if value < 0:
            raise ValueError("Counter can only increase")

        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._values[label_key] += value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current counter value.

        Args:
            labels: Labels to filter by

        Returns:
            Current counter value
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            return self._values.get(label_key, 0)

    def get_all(self) -> list[MetricValue]:
        """Get all counter values with their labels.

        Returns:
            List of MetricValue objects
        """
        with self._lock:
            return [
                MetricValue(
                    name=self.name,
                    type=MetricType.COUNTER,
                    value=value,
                    labels=dict(label_key),
                    help_text=self.help_text,
                )
                for label_key, value in self._values.items()
            ]


class Gauge:
    """A metric that can go up or down.

    Example:
        gauge = Gauge("active_tasks", "Number of active tasks")
        gauge.set(5)
        gauge.inc()  # Now 6
        gauge.dec()  # Now 5
    """

    def __init__(self, name: str, help_text: str = "") -> None:
        """Initialize gauge.

        Args:
            name: Metric name
            help_text: Description of the metric
        """
        self.name = name
        self.help_text = help_text
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = Lock()

    def set(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Set the gauge value.

        Args:
            value: Value to set
            labels: Optional labels
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._values[label_key] = value

    def inc(self, value: float = 1, labels: dict[str, str] | None = None) -> None:
        """Increment the gauge.

        Args:
            value: Amount to increment
            labels: Optional labels
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._values[label_key] += value

    def dec(self, value: float = 1, labels: dict[str, str] | None = None) -> None:
        """Decrement the gauge.

        Args:
            value: Amount to decrement
            labels: Optional labels
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._values[label_key] -= value

    def get(self, labels: dict[str, str] | None = None) -> float:
        """Get current gauge value.

        Args:
            labels: Labels to filter by

        Returns:
            Current gauge value
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            return self._values.get(label_key, 0)

    def get_all(self) -> list[MetricValue]:
        """Get all gauge values with their labels.

        Returns:
            List of MetricValue objects
        """
        with self._lock:
            return [
                MetricValue(
                    name=self.name,
                    type=MetricType.GAUGE,
                    value=value,
                    labels=dict(label_key),
                    help_text=self.help_text,
                )
                for label_key, value in self._values.items()
            ]


class Histogram:
    """A histogram metric for tracking value distributions.

    Example:
        histogram = Histogram("processing_duration_seconds", "Processing duration")
        histogram.observe(0.5)  # Record an observation
        histogram.observe(1.2, labels={"operation": "analyze"})
    """

    # Default buckets for timing (in seconds)
    DEFAULT_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf"))

    def __init__(
        self,
        name: str,
        help_text: str = "",
        buckets: tuple[float, ...] | None = None,
    ) -> None:
        """Initialize histogram.

        Args:
            name: Metric name
            help_text: Description of the metric
            buckets: Bucket boundaries (defaults to timing buckets)
        """
        self.name = name
        self.help_text = help_text
        self._buckets = buckets or self.DEFAULT_BUCKETS
        self._observations: dict[tuple[tuple[str, str], ...], list[float]] = defaultdict(list)
        self._lock = Lock()

    def observe(self, value: float, labels: dict[str, str] | None = None) -> None:
        """Record an observation.

        Args:
            value: Value to record
            labels: Optional labels
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            self._observations[label_key].append(value)

    def get_stats(self, labels: dict[str, str] | None = None) -> dict[str, float]:
        """Get histogram statistics.

        Args:
            labels: Labels to filter by

        Returns:
            Dictionary with count, sum, min, max, mean
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            values = self._observations.get(label_key, [])

        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "mean": 0}

        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }

    def get_buckets(self, labels: dict[str, str] | None = None) -> dict[float, int]:
        """Get bucket counts.

        Args:
            labels: Labels to filter by

        Returns:
            Dictionary mapping bucket boundary to count
        """
        label_key = tuple(sorted(labels.items())) if labels else ()
        with self._lock:
            values = self._observations.get(label_key, [])

        bucket_counts: dict[float, int] = dict.fromkeys(self._buckets, 0)
        for value in values:
            for bucket in self._buckets:
                if value <= bucket:
                    bucket_counts[bucket] += 1
                    break

        return bucket_counts


class MetricsRegistry:
    """Registry for all application metrics.

    This is a singleton that holds all metrics and provides
    methods for exporting them.

    Example:
        registry = MetricsRegistry.get_instance()
        registry.messages_processed.inc()
        metrics = registry.get_all_metrics()
    """

    _instance: MetricsRegistry | None = None
    _lock = Lock()

    def __init__(self) -> None:
        """Initialize the metrics registry."""
        # Message processing
        self.messages_received = Counter(
            "ai_issue_agent_messages_received_total",
            "Total messages received from chat",
        )
        self.messages_processed = Counter(
            "ai_issue_agent_messages_processed_total",
            "Total messages successfully processed",
        )
        self.messages_errors = Counter(
            "ai_issue_agent_messages_errors_total",
            "Total message processing errors",
        )

        # Traceback detection
        self.tracebacks_detected = Counter(
            "ai_issue_agent_tracebacks_detected_total",
            "Total tracebacks detected in messages",
        )

        # Issue operations
        self.issues_created = Counter(
            "ai_issue_agent_issues_created_total",
            "Total issues created on VCS",
        )
        self.issues_linked = Counter(
            "ai_issue_agent_issues_linked_total",
            "Total times linked to existing issues",
        )
        self.issue_searches = Counter(
            "ai_issue_agent_issue_searches_total",
            "Total issue searches performed",
        )

        # LLM operations
        self.llm_requests = Counter(
            "ai_issue_agent_llm_requests_total",
            "Total LLM API requests",
        )
        self.llm_errors = Counter(
            "ai_issue_agent_llm_errors_total",
            "Total LLM API errors",
        )
        self.llm_tokens_used = Counter(
            "ai_issue_agent_llm_tokens_total",
            "Total LLM tokens used",
        )

        # Durations
        self.processing_duration = Histogram(
            "ai_issue_agent_processing_duration_seconds",
            "Message processing duration in seconds",
        )
        self.llm_request_duration = Histogram(
            "ai_issue_agent_llm_request_duration_seconds",
            "LLM request duration in seconds",
        )
        self.issue_search_duration = Histogram(
            "ai_issue_agent_issue_search_duration_seconds",
            "Issue search duration in seconds",
        )

        # Cache
        self.cache_hits = Counter(
            "ai_issue_agent_cache_hits_total",
            "Total cache hits",
        )
        self.cache_misses = Counter(
            "ai_issue_agent_cache_misses_total",
            "Total cache misses",
        )

        # Rate limits
        self.rate_limits_hit = Counter(
            "ai_issue_agent_rate_limits_hit_total",
            "Total rate limits encountered",
        )

        # Security
        self.secrets_redacted = Counter(
            "ai_issue_agent_secrets_redacted_total",
            "Total secrets redacted from content",
        )
        self.security_rejections = Counter(
            "ai_issue_agent_security_rejections_total",
            "Total requests rejected for security reasons",
        )

        # Active tasks gauge
        self.active_tasks = Gauge(
            "ai_issue_agent_active_tasks",
            "Number of currently processing tasks",
        )

        # Uptime
        self._start_time = time.time()

    @classmethod
    def get_instance(cls) -> MetricsRegistry:
        """Get the singleton metrics registry instance.

        Returns:
            The global MetricsRegistry instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_uptime_seconds(self) -> float:
        """Get agent uptime in seconds.

        Returns:
            Uptime in seconds
        """
        return time.time() - self._start_time

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics as a dictionary.

        Returns:
            Dictionary of all metrics
        """
        return {
            "uptime_seconds": self.get_uptime_seconds(),
            "messages": {
                "received": self.messages_received.get(),
                "processed": self.messages_processed.get(),
                "errors": self.messages_errors.get(),
            },
            "tracebacks": {
                "detected": self.tracebacks_detected.get(),
            },
            "issues": {
                "created": self.issues_created.get(),
                "linked": self.issues_linked.get(),
                "searches": self.issue_searches.get(),
            },
            "llm": {
                "requests": self.llm_requests.get(),
                "errors": self.llm_errors.get(),
                "tokens_used": self.llm_tokens_used.get(),
            },
            "cache": {
                "hits": self.cache_hits.get(),
                "misses": self.cache_misses.get(),
            },
            "rate_limits": {
                "hit": self.rate_limits_hit.get(),
            },
            "security": {
                "secrets_redacted": self.secrets_redacted.get(),
                "rejections": self.security_rejections.get(),
            },
            "processing": {
                "active_tasks": self.active_tasks.get(),
                "duration_stats": self.processing_duration.get_stats(),
            },
        }

    def to_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format.

        Returns:
            Prometheus-compatible metrics string
        """
        lines: list[str] = []

        # Add all counters
        for counter in [
            self.messages_received,
            self.messages_processed,
            self.messages_errors,
            self.tracebacks_detected,
            self.issues_created,
            self.issues_linked,
            self.issue_searches,
            self.llm_requests,
            self.llm_errors,
            self.llm_tokens_used,
            self.cache_hits,
            self.cache_misses,
            self.rate_limits_hit,
            self.secrets_redacted,
            self.security_rejections,
        ]:
            if counter.help_text:
                lines.append(f"# HELP {counter.name} {counter.help_text}")
            lines.append(f"# TYPE {counter.name} counter")
            for metric in counter.get_all():
                if metric.labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                    lines.append(f"{counter.name}{{{label_str}}} {metric.value}")
                else:
                    lines.append(f"{counter.name} {metric.value}")

        # Add gauges
        for gauge in [self.active_tasks]:
            if gauge.help_text:
                lines.append(f"# HELP {gauge.name} {gauge.help_text}")
            lines.append(f"# TYPE {gauge.name} gauge")
            for metric in gauge.get_all():
                if metric.labels:
                    label_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                    lines.append(f"{gauge.name}{{{label_str}}} {metric.value}")
                else:
                    lines.append(f"{gauge.name} {metric.value}")

        # Add uptime
        lines.append("# HELP ai_issue_agent_uptime_seconds Agent uptime in seconds")
        lines.append("# TYPE ai_issue_agent_uptime_seconds gauge")
        lines.append(f"ai_issue_agent_uptime_seconds {self.get_uptime_seconds()}")

        return "\n".join(lines)


# Convenience function to get the global registry
def get_metrics() -> MetricsRegistry:
    """Get the global metrics registry.

    Returns:
        The MetricsRegistry singleton
    """
    return MetricsRegistry.get_instance()


class Timer:
    """Context manager for timing operations.

    Example:
        with Timer(metrics.processing_duration, labels={"operation": "parse"}):
            parse_traceback(text)
    """

    def __init__(
        self,
        histogram: Histogram,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Initialize timer.

        Args:
            histogram: Histogram to record to
            labels: Optional labels for the observation
        """
        self._histogram = histogram
        self._labels = labels
        self._start: float | None = None

    def __enter__(self) -> Timer:
        """Start timing."""
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        """Stop timing and record."""
        if self._start is not None:
            duration = time.perf_counter() - self._start
            self._histogram.observe(duration, labels=self._labels)
