"""
Unit tests for sdk.protocol.dendrite — Validator HTTP Client

Tests DendriteResult, Dendrite.send_task, broadcast, and check_health
without requiring a real miner Axon server (mocked HTTP layer).
"""

import json
import time
import hashlib
import hmac as hmac_mod
import unittest
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sdk.protocol.dendrite import Dendrite, DendriteResult


# ── DendriteResult unit tests ──────────────────────────────


class TestDendriteResult(unittest.TestCase):
    """Pure data-object tests — no I/O."""

    def test_success_true_when_response_present(self):
        r = DendriteResult(
            miner_id="0.0.1",
            endpoint="http://localhost",
            response={"output": {"score": 0.9}},
        )
        self.assertTrue(r.success)
        self.assertIsNone(r.error)

    def test_success_false_when_error(self):
        r = DendriteResult(
            miner_id="0.0.1",
            endpoint="http://localhost",
            error="timeout",
        )
        self.assertFalse(r.success)
        self.assertIsNone(r.output)

    def test_success_false_when_no_response(self):
        r = DendriteResult(miner_id="0.0.1", endpoint="http://x")
        self.assertFalse(r.success)

    def test_output_property(self):
        r = DendriteResult(
            miner_id="m1",
            endpoint="http://x",
            response={"output": {"key": "val"}},
        )
        self.assertEqual(r.output, {"key": "val"})

    def test_output_none_when_missing_key(self):
        r = DendriteResult(
            miner_id="m1", endpoint="http://x", response={"other": 1}
        )
        self.assertIsNone(r.output)

    def test_to_dict_serialization(self):
        r = DendriteResult(
            miner_id="0.0.1",
            endpoint="http://x:8091",
            response={"output": {"ok": True}},
            latency=0.1234,
        )
        d = r.to_dict()
        self.assertEqual(d["miner_id"], "0.0.1")
        self.assertTrue(d["success"])
        self.assertEqual(d["latency"], 0.123)  # rounded to 3 dp
        self.assertEqual(d["output"], {"ok": True})
        self.assertIsNone(d["error"])

    def test_to_dict_error_case(self):
        r = DendriteResult(
            miner_id="0.0.2",
            endpoint="http://x",
            error="HTTP 500: Internal",
            latency=2.5678,
        )
        d = r.to_dict()
        self.assertFalse(d["success"])
        self.assertEqual(d["error"], "HTTP 500: Internal")


# ── Fake Axon server for integration-style tests ───────────


class _FakeAxonHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler mimicking an Axon."""

    def log_message(self, fmt, *args):
        pass  # silence

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "online"})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/task":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            self._json(
                200,
                {
                    "task_id": body.get("task_id"),
                    "output": {"result": "fake_analysis"},
                    "status": "completed",
                },
            )
        else:
            self._json(404, {"error": "Not found"})

    def _json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestDendriteSendTask(unittest.TestCase):
    """Tests Dendrite.send_task against a real (fake) HTTP server."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _FakeAxonHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_send_task_success(self):
        d = Dendrite(validator_id="0.0.9999", timeout=5)
        result = d.send_task(
            endpoint=self.endpoint,
            miner_id="0.0.1001",
            task_id="task-abc",
            task_type="code_review",
            payload={"code": "print('hi')"},
        )
        self.assertTrue(result.success)
        self.assertEqual(result.miner_id, "0.0.1001")
        self.assertEqual(result.output, {"result": "fake_analysis"})
        self.assertGreater(result.latency, 0)

    def test_send_task_updates_stats(self):
        d = Dendrite(validator_id="0.0.9999")
        self.assertEqual(d._total_requests, 0)

        d.send_task(
            endpoint=self.endpoint,
            miner_id="m1",
            task_id="t1",
            task_type="x",
            payload={},
        )
        self.assertEqual(d._total_requests, 1)
        self.assertEqual(d._total_errors, 0)

    def test_send_task_connection_error(self):
        d = Dendrite(validator_id="v1", timeout=1)
        result = d.send_task(
            endpoint="http://127.0.0.1:1",  # port 1 should refuse
            miner_id="bad",
            task_id="t",
            task_type="x",
            payload={},
        )
        self.assertFalse(result.success)
        self.assertIn("Connection failed", result.error)
        self.assertEqual(d._total_errors, 1)

    def test_check_health_returns_true(self):
        d = Dendrite()
        self.assertTrue(d.check_health(self.endpoint))

    def test_check_health_returns_false_on_bad_endpoint(self):
        d = Dendrite()
        self.assertFalse(d.check_health("http://127.0.0.1:1"))


class TestDendriteBroadcast(unittest.TestCase):
    """Tests parallel broadcast to multiple miners."""

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _FakeAxonHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.endpoint = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_broadcast_all_succeed(self):
        d = Dendrite(validator_id="v1", max_workers=4)
        miners = [
            {"miner_id": f"m{i}", "endpoint": self.endpoint} for i in range(3)
        ]
        results = d.broadcast(
            miners=miners, task_id="bc1", task_type="gen", payload={"x": 1}
        )
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))

    def test_broadcast_skips_empty_endpoint(self):
        d = Dendrite()
        miners = [
            {"miner_id": "m1", "endpoint": self.endpoint},
            {"miner_id": "m2", "endpoint": ""},  # no endpoint
        ]
        results = d.broadcast(
            miners=miners, task_id="bc2", task_type="gen", payload={}
        )
        self.assertEqual(len(results), 2)
        # One success, one error
        errors = [r for r in results if not r.success]
        self.assertEqual(len(errors), 1)
        self.assertIn("No endpoint", errors[0].error)


class TestDendriteGetStats(unittest.TestCase):
    def test_stats_default(self):
        d = Dendrite(validator_id="0.0.5", timeout=15)
        s = d.get_stats()
        self.assertEqual(s["validator_id"], "0.0.5")
        self.assertEqual(s["total_requests"], 0)
        self.assertEqual(s["total_errors"], 0)
        # (0 - 0) / max(1, 0) = 0.0 when no requests made
        self.assertEqual(s["success_rate"], 0.0)
        self.assertEqual(s["timeout"], 15)


if __name__ == "__main__":
    unittest.main()
