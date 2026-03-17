"""
Validator Heartbeat

Extends the concept from MinerHeartbeat.
Sends periodic heartbeat pings from the validator to an HCS topic,
proving that the validator node is alive and responsive.

Also tracks last-seen timestamps for connected miners (liveness check).
"""

import time
import json
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ValidatorHeartbeat:
    """
    Background heartbeat service for validators.

    Sends periodic 'validator_heartbeat' messages to HCS
    and tracks miner liveness based on received heartbeats.
    """

    def __init__(
        self,
        client: "HederaClient | None" = None,
        topic_id: str = "",
        validator_id: str = "",
        interval_seconds: float = 30.0,
        miner_timeout: float = 120.0,
    ):
        self.client = client
        self.topic_id = topic_id
        self.validator_id = validator_id
        self.interval = interval_seconds
        self.miner_timeout = miner_timeout

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._counter = 0

        # Track miner liveness: {miner_id: last_seen_timestamp}
        self._miner_last_seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the validator heartbeat loop in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="validator-heartbeat")
        self._thread.start()
        logger.info("ValidatorHeartbeat started (id=%s, interval=%.0fs)", self.validator_id, self.interval)

    def stop(self) -> None:
        """Stop the heartbeat loop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("ValidatorHeartbeat stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Miner liveness tracking ─────────────────────────────

    def record_miner_seen(self, miner_id: str) -> None:
        """Record that a miner was observed (e.g., it responded to a task or heartbeat)."""
        with self._lock:
            self._miner_last_seen[miner_id] = time.time()

    def get_live_miners(self) -> list[str]:
        """Return miner IDs seen within the timeout window."""
        cutoff = time.time() - self.miner_timeout
        with self._lock:
            return [mid for mid, ts in self._miner_last_seen.items() if ts >= cutoff]

    def get_dead_miners(self) -> list[str]:
        """Return miner IDs NOT seen within the timeout window."""
        cutoff = time.time() - self.miner_timeout
        with self._lock:
            return [mid for mid, ts in self._miner_last_seen.items() if ts < cutoff]

    def get_miner_status(self) -> dict[str, dict]:
        """Return status info for all tracked miners."""
        now = time.time()
        with self._lock:
            return {
                mid: {
                    "last_seen": ts,
                    "age_seconds": round(now - ts, 1),
                    "alive": (now - ts) < self.miner_timeout,
                }
                for mid, ts in self._miner_last_seen.items()
            }

    # ── Internal loop ────────────────────────────────────────

    def _run_loop(self) -> None:
        while self._running:
            try:
                self._send_beat()
            except Exception as e:
                logger.error("Validator heartbeat error: %s", e)

            # Sleep in 1-second chunks for fast shutdown
            for _ in range(int(self.interval)):
                if not self._running:
                    break
                time.sleep(1.0)

    def _send_beat(self) -> None:
        self._counter += 1

        payload = {
            "type": "validator_heartbeat",
            "validator_id": self.validator_id,
            "timestamp": time.time(),
            "seq": self._counter,
            "status": "ONLINE",
            "live_miners": len(self.get_live_miners()),
            "version": "1.0.0",
        }

        # Send to HCS if client is available
        if self.client and self.topic_id:
            try:
                self.client.submit_message(
                    topic_id=self.topic_id,
                    message=json.dumps(payload),
                )
                logger.debug("Validator heartbeat sent (seq=%d, live_miners=%d)", self._counter, payload["live_miners"])
            except Exception as e:
                logger.warning("Failed to send validator heartbeat: %s", e)
        else:
            logger.debug("Validator heartbeat (seq=%d) — no HCS client, local only", self._counter)
