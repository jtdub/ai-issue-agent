"""Tests for the metrics collection module."""

import time

import pytest

from ai_issue_agent.utils.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    MetricType,
    Timer,
    get_metrics,
)


class TestCounter:
    """Tests for Counter metric."""

    def test_counter_initial_value(self) -> None:
        """Test counter starts at zero."""
        counter = Counter("test_counter", "Test counter")
        assert counter.get() == 0

    def test_counter_increment_by_one(self) -> None:
        """Test counter increment by default value."""
        counter = Counter("test_counter")
        counter.inc()
        assert counter.get() == 1

    def test_counter_increment_by_value(self) -> None:
        """Test counter increment by specific value."""
        counter = Counter("test_counter")
        counter.inc(5)
        assert counter.get() == 5

    def test_counter_multiple_increments(self) -> None:
        """Test multiple counter increments."""
        counter = Counter("test_counter")
        counter.inc()
        counter.inc(3)
        counter.inc(2)
        assert counter.get() == 6

    def test_counter_with_labels(self) -> None:
        """Test counter with labels."""
        counter = Counter("test_counter")
        counter.inc(labels={"type": "success"})
        counter.inc(labels={"type": "error"})
        counter.inc(labels={"type": "success"})

        assert counter.get(labels={"type": "success"}) == 2
        assert counter.get(labels={"type": "error"}) == 1
        assert counter.get(labels={"type": "unknown"}) == 0

    def test_counter_cannot_decrease(self) -> None:
        """Test that counter rejects negative values."""
        counter = Counter("test_counter")
        with pytest.raises(ValueError, match="can only increase"):
            counter.inc(-1)

    def test_counter_get_all(self) -> None:
        """Test getting all counter values."""
        counter = Counter("test_counter", "Help text")
        counter.inc(labels={"a": "1"})
        counter.inc(2, labels={"a": "2"})

        values = counter.get_all()
        assert len(values) == 2
        assert all(v.type == MetricType.COUNTER for v in values)


class TestGauge:
    """Tests for Gauge metric."""

    def test_gauge_initial_value(self) -> None:
        """Test gauge starts at zero."""
        gauge = Gauge("test_gauge", "Test gauge")
        assert gauge.get() == 0

    def test_gauge_set_value(self) -> None:
        """Test setting gauge value."""
        gauge = Gauge("test_gauge")
        gauge.set(42)
        assert gauge.get() == 42

    def test_gauge_increment(self) -> None:
        """Test gauge increment."""
        gauge = Gauge("test_gauge")
        gauge.set(10)
        gauge.inc()
        assert gauge.get() == 11

    def test_gauge_decrement(self) -> None:
        """Test gauge decrement."""
        gauge = Gauge("test_gauge")
        gauge.set(10)
        gauge.dec()
        assert gauge.get() == 9

    def test_gauge_can_be_negative(self) -> None:
        """Test gauge can have negative values."""
        gauge = Gauge("test_gauge")
        gauge.set(-5)
        assert gauge.get() == -5

    def test_gauge_with_labels(self) -> None:
        """Test gauge with labels."""
        gauge = Gauge("test_gauge")
        gauge.set(10, labels={"host": "server1"})
        gauge.set(20, labels={"host": "server2"})

        assert gauge.get(labels={"host": "server1"}) == 10
        assert gauge.get(labels={"host": "server2"}) == 20


class TestHistogram:
    """Tests for Histogram metric."""

    def test_histogram_observe(self) -> None:
        """Test histogram observation."""
        histogram = Histogram("test_histogram")
        histogram.observe(0.5)
        histogram.observe(1.0)
        histogram.observe(1.5)

        stats = histogram.get_stats()
        assert stats["count"] == 3
        assert stats["sum"] == 3.0
        assert stats["min"] == 0.5
        assert stats["max"] == 1.5

    def test_histogram_empty(self) -> None:
        """Test histogram with no observations."""
        histogram = Histogram("test_histogram")
        stats = histogram.get_stats()
        assert stats["count"] == 0
        assert stats["sum"] == 0

    def test_histogram_mean(self) -> None:
        """Test histogram mean calculation."""
        histogram = Histogram("test_histogram")
        histogram.observe(1.0)
        histogram.observe(2.0)
        histogram.observe(3.0)

        stats = histogram.get_stats()
        assert stats["mean"] == 2.0

    def test_histogram_buckets(self) -> None:
        """Test histogram bucket counts."""
        histogram = Histogram("test_histogram", buckets=(1.0, 5.0, 10.0, float("inf")))
        histogram.observe(0.5)  # <= 1.0
        histogram.observe(3.0)  # <= 5.0
        histogram.observe(7.0)  # <= 10.0
        histogram.observe(15.0)  # <= inf

        buckets = histogram.get_buckets()
        assert buckets[1.0] == 1
        assert buckets[5.0] == 1
        assert buckets[10.0] == 1
        assert buckets[float("inf")] == 1

    def test_histogram_with_labels(self) -> None:
        """Test histogram with labels."""
        histogram = Histogram("test_histogram")
        histogram.observe(1.0, labels={"operation": "read"})
        histogram.observe(2.0, labels={"operation": "write"})

        read_stats = histogram.get_stats(labels={"operation": "read"})
        assert read_stats["count"] == 1
        assert read_stats["sum"] == 1.0


class TestMetricsRegistry:
    """Tests for MetricsRegistry singleton."""

    def test_singleton_instance(self) -> None:
        """Test that get_instance returns singleton."""
        instance1 = MetricsRegistry.get_instance()
        instance2 = MetricsRegistry.get_instance()
        assert instance1 is instance2

    def test_get_metrics_function(self) -> None:
        """Test get_metrics convenience function."""
        registry = get_metrics()
        assert isinstance(registry, MetricsRegistry)

    def test_registry_has_expected_metrics(self) -> None:
        """Test that registry has expected metrics."""
        registry = get_metrics()

        assert hasattr(registry, "messages_received")
        assert hasattr(registry, "messages_processed")
        assert hasattr(registry, "issues_created")
        assert hasattr(registry, "issues_linked")
        assert hasattr(registry, "llm_requests")
        assert hasattr(registry, "processing_duration")
        assert hasattr(registry, "cache_hits")
        assert hasattr(registry, "active_tasks")

    def test_registry_get_all_metrics(self) -> None:
        """Test getting all metrics as dictionary."""
        registry = get_metrics()
        metrics = registry.get_all_metrics()

        assert "uptime_seconds" in metrics
        assert "messages" in metrics
        assert "issues" in metrics
        assert "llm" in metrics
        assert "cache" in metrics

    def test_registry_uptime(self) -> None:
        """Test uptime tracking."""
        registry = get_metrics()
        uptime = registry.get_uptime_seconds()
        assert uptime >= 0

    def test_registry_prometheus_format(self) -> None:
        """Test Prometheus format export."""
        registry = get_metrics()
        output = registry.to_prometheus_format()

        assert "# TYPE" in output
        assert "ai_issue_agent_" in output
        assert "counter" in output
        assert "gauge" in output


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_records_duration(self) -> None:
        """Test that timer records duration."""
        histogram = Histogram("test_timer")

        with Timer(histogram):
            time.sleep(0.01)  # Sleep 10ms

        stats = histogram.get_stats()
        assert stats["count"] == 1
        assert stats["sum"] >= 0.01

    def test_timer_with_labels(self) -> None:
        """Test timer with labels."""
        histogram = Histogram("test_timer")

        with Timer(histogram, labels={"operation": "test"}):
            pass

        stats = histogram.get_stats(labels={"operation": "test"})
        assert stats["count"] == 1

    def test_timer_records_on_exception(self) -> None:
        """Test that timer records even if exception is raised."""
        histogram = Histogram("test_timer")

        with pytest.raises(ValueError), Timer(histogram):
            raise ValueError("test error")

        stats = histogram.get_stats()
        assert stats["count"] == 1


class TestMetricIntegration:
    """Integration tests for metrics."""

    def test_message_processing_workflow(self) -> None:
        """Test typical message processing workflow."""
        # Create fresh registry for this test
        registry = MetricsRegistry()

        # Simulate receiving a message
        registry.messages_received.inc()
        registry.active_tasks.inc()

        # Simulate traceback detection
        registry.tracebacks_detected.inc()

        # Simulate issue search
        registry.issue_searches.inc()
        registry.cache_misses.inc()

        # Simulate LLM request
        registry.llm_requests.inc()
        registry.llm_tokens_used.inc(500)

        # Simulate issue creation
        registry.issues_created.inc()

        # Complete processing
        registry.messages_processed.inc()
        registry.active_tasks.dec()

        # Verify metrics
        assert registry.messages_received.get() == 1
        assert registry.messages_processed.get() == 1
        assert registry.issues_created.get() == 1
        assert registry.llm_tokens_used.get() == 500
        assert registry.active_tasks.get() == 0

    def test_error_handling_workflow(self) -> None:
        """Test error handling workflow."""
        registry = MetricsRegistry()

        # Simulate receiving a message
        registry.messages_received.inc()
        registry.active_tasks.inc()

        # Simulate error
        registry.messages_errors.inc()
        registry.active_tasks.dec()

        # Verify metrics
        assert registry.messages_received.get() == 1
        assert registry.messages_errors.get() == 1
        assert registry.messages_processed.get() == 0
