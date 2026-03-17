"""
Prometheus Metrics Endpoint

Exposes key protocol metrics via /metrics (Prometheus format):
  - Task counts by status
  - Miner response latencies
  - Circuit breaker states
  - Active miners / validators

Usage:
    from sdk.metrics import MetricsCollector, start_metrics_server

    metrics = MetricsCollector()
    start_metrics_server(port=9090)

    metrics.record_task_completed(duration_ms=350)
    metrics.record_miner_call("0.0.1001", success=True, duration_ms=200)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        start_http_server,
    )

    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class MetricsCollector:
    """
    Centralised metrics collector using prometheus_client.

    If prometheus_client is not installed, all methods become no-ops.
    """

    def __init__(self, namespace: str = "moderntensor"):
        self._enabled = _HAS_PROMETHEUS
        if not self._enabled:
            logger.warning("prometheus_client not installed — metrics disabled")
            return

        self.namespace = namespace

        # ── Counters ────────────────────────────────────────
        self.tasks_created = Counter(
            f"{namespace}_tasks_created_total",
            "Total tasks created",
            ["subnet_id"],
        )
        self.tasks_completed = Counter(
            f"{namespace}_tasks_completed_total",
            "Total tasks completed",
            ["subnet_id"],
        )
        self.tasks_failed = Counter(
            f"{namespace}_tasks_failed_total",
            "Total tasks failed",
            ["subnet_id"],
        )
        self.miner_calls = Counter(
            f"{namespace}_miner_calls_total",
            "Total calls to miners",
            ["miner_id", "status"],
        )

        # ── Histograms ──────────────────────────────────────
        self.task_duration = Histogram(
            f"{namespace}_task_duration_ms",
            "Task processing duration in ms",
            ["subnet_id"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000, 10000],
        )
        self.miner_latency = Histogram(
            f"{namespace}_miner_latency_ms",
            "Miner call latency in ms",
            ["miner_id"],
            buckets=[50, 100, 250, 500, 1000, 2500, 5000],
        )

        # ── Gauges ──────────────────────────────────────────
        self.active_miners = Gauge(
            f"{namespace}_active_miners",
            "Number of active miners",
            ["subnet_id"],
        )
        self.active_validators = Gauge(
            f"{namespace}_active_validators",
            "Number of active validators",
        )
        self.circuit_breaker_state = Gauge(
            f"{namespace}_circuit_breaker_open",
            "Circuit breaker state (1=open, 0=closed)",
            ["miner_id"],
        )

        # ── Info ────────────────────────────────────────────
        self.build_info = Info(
            f"{namespace}_build",
            "Build information",
        )
        self.build_info.info({"version": "1.0.0", "network": "testnet"})

    # ── Recording methods ───────────────────────────────────

    def record_task_created(self, subnet_id: int = 0) -> None:
        if self._enabled:
            self.tasks_created.labels(subnet_id=str(subnet_id)).inc()

    def record_task_completed(self, subnet_id: int = 0, duration_ms: float = 0) -> None:
        if self._enabled:
            self.tasks_completed.labels(subnet_id=str(subnet_id)).inc()
            self.task_duration.labels(subnet_id=str(subnet_id)).observe(duration_ms)

    def record_task_failed(self, subnet_id: int = 0) -> None:
        if self._enabled:
            self.tasks_failed.labels(subnet_id=str(subnet_id)).inc()

    def record_miner_call(
        self, miner_id: str, *, success: bool = True, duration_ms: float = 0
    ) -> None:
        if self._enabled:
            status = "success" if success else "failure"
            self.miner_calls.labels(miner_id=miner_id, status=status).inc()
            self.miner_latency.labels(miner_id=miner_id).observe(duration_ms)

    def set_active_miners(self, count: int, subnet_id: int = 0) -> None:
        if self._enabled:
            self.active_miners.labels(subnet_id=str(subnet_id)).set(count)

    def set_active_validators(self, count: int) -> None:
        if self._enabled:
            self.active_validators.set(count)

    def set_circuit_state(self, miner_id: str, is_open: bool) -> None:
        if self._enabled:
            self.circuit_breaker_state.labels(miner_id=miner_id).set(1 if is_open else 0)


def start_metrics_server(port: int = 9090) -> Optional[threading.Thread]:
    """
    Start a background HTTP server serving Prometheus metrics.

    Returns the server thread, or None if prometheus_client is unavailable.
    """
    if not _HAS_PROMETHEUS:
        logger.warning("prometheus_client not installed — metrics server not started")
        return None

    start_http_server(port)
    logger.info("Prometheus metrics server started on :%d/metrics", port)
    return None  # start_http_server manages its own thread
