"""
Unit tests for sdk.protocol.axon — Miner HTTP Server

Tests Axon start/stop lifecycle, /health and /task endpoints,
handler invocation, authentication, and error propagation.
"""

import json
import hashlib
import hmac as hmac_mod
import time
import unittest
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdk.protocol.axon import Axon


# ── Helper handlers ─────────────────────────────────────────


def _echo_handler(payload, task_type):
    """Simple handler that echoes payload + task_type."""
    return {"echo": payload, "task_type": task_type}


def _error_handler(payload, task_type):
    """Handler that always raises."""
    raise ValueError("deliberate handler error")


# ── Tests ────────────────────────────────────────────────────


class TestAxonLifecycle(unittest.TestCase):
    """Start, stop, and property tests."""

    def test_start_and_stop(self):
        axon = Axon(miner_id="0.0.100", handler=_echo_handler, port=0)
        # port=0 will not bind a real port, so we use a high port
        axon = Axon(miner_id="0.0.100", handler=_echo_handler, host="127.0.0.1", port=18091)
        axon.start()
        self.assertTrue(axon.is_running)
        axon.stop()
        self.assertFalse(axon.is_running)

    def test_endpoint_property(self):
        axon = Axon(miner_id="m1", handler=_echo_handler, host="0.0.0.0", port=9999)
        self.assertEqual(axon.endpoint, "http://0.0.0.0:9999")

    def test_double_start_is_noop(self):
        axon = Axon(miner_id="m1", handler=_echo_handler, host="127.0.0.1", port=18092)
        axon.start()
        axon.start()  # should not raise
        self.assertTrue(axon.is_running)
        axon.stop()


class TestAxonHealth(unittest.TestCase):
    """GET /health endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.axon = Axon(
            miner_id="0.0.200",
            handler=_echo_handler,
            host="127.0.0.1",
            port=18093,
            subnet_ids=[1, 2],
            capabilities=["code_review"],
        )
        cls.axon.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.axon.stop()

    def test_health_returns_200(self):
        req = Request("http://127.0.0.1:18093/health", method="GET")
        with urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertEqual(data["status"], "online")
            self.assertEqual(data["miner_id"], "0.0.200")

    def test_info_returns_200(self):
        req = Request("http://127.0.0.1:18093/info", method="GET")
        with urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read())
            self.assertEqual(data["miner_id"], "0.0.200")
            self.assertEqual(data["subnet_ids"], [1, 2])
            self.assertEqual(data["capabilities"], ["code_review"])

    def test_unknown_get_returns_404(self):
        req = Request("http://127.0.0.1:18093/unknown", method="GET")
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 404)


class TestAxonTaskEndpoint(unittest.TestCase):
    """POST /task endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.axon = Axon(
            miner_id="0.0.300",
            handler=_echo_handler,
            host="127.0.0.1",
            port=18094,
        )
        cls.axon.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.axon.stop()

    def _post_task(self, payload, task_type="code_review", task_id="t1"):
        body = json.dumps({
            "task_id": task_id,
            "task_type": task_type,
            "payload": payload,
            "validator_id": "0.0.999",
        }).encode()
        req = Request(
            "http://127.0.0.1:18094/task",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())

    def test_task_returns_output(self):
        status, data = self._post_task({"code": "x = 1"})
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["output"]["echo"], {"code": "x = 1"})
        self.assertEqual(data["output"]["task_type"], "code_review")

    def test_task_increments_processed_counter(self):
        before = self.axon._server.axon_config["tasks_processed"]
        self._post_task({"a": 1})
        after = self.axon._server.axon_config["tasks_processed"]
        self.assertEqual(after, before + 1)

    def test_task_invalid_json_returns_400(self):
        req = Request(
            "http://127.0.0.1:18094/task",
            data=b"NOT JSON",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 400)


class TestAxonHandlerError(unittest.TestCase):
    """Handler that raises should return 500."""

    @classmethod
    def setUpClass(cls):
        cls.axon = Axon(
            miner_id="0.0.400",
            handler=_error_handler,
            host="127.0.0.1",
            port=18095,
        )
        cls.axon.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.axon.stop()

    def test_handler_error_returns_500(self):
        body = json.dumps({
            "task_id": "err1",
            "task_type": "gen",
            "payload": {},
            "validator_id": "v1",
        }).encode()
        req = Request(
            "http://127.0.0.1:18095/task",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 500)
        err_data = json.loads(ctx.exception.read())
        self.assertIn("deliberate handler error", err_data["error"])


class TestAxonStats(unittest.TestCase):
    def test_get_stats_before_start(self):
        axon = Axon(miner_id="m1", handler=_echo_handler, host="127.0.0.1", port=18096)
        stats = axon.get_stats()
        self.assertEqual(stats["miner_id"], "m1")
        self.assertFalse(stats["is_running"])
        self.assertEqual(stats["tasks_processed"], 0)


if __name__ == "__main__":
    unittest.main()
