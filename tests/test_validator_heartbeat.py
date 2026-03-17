"""
Tests for sdk/protocol/validator_heartbeat.py — Validator liveness + miner tracking
"""

import time
import pytest
from sdk.protocol.validator_heartbeat import ValidatorHeartbeat


def test_heartbeat_init():
    hb = ValidatorHeartbeat(validator_id="0.0.100", interval_seconds=10)
    assert hb.validator_id == "0.0.100"
    assert hb.is_running is False


def test_miner_liveness_tracking():
    hb = ValidatorHeartbeat(miner_timeout=2.0)

    hb.record_miner_seen("m1")
    hb.record_miner_seen("m2")

    live = hb.get_live_miners()
    assert "m1" in live
    assert "m2" in live
    assert hb.get_dead_miners() == []


def test_miner_timeout():
    hb = ValidatorHeartbeat(miner_timeout=0.1)  # 100ms timeout

    hb.record_miner_seen("m1")
    time.sleep(0.2)

    assert "m1" in hb.get_dead_miners()
    assert "m1" not in hb.get_live_miners()


def test_miner_status_info():
    hb = ValidatorHeartbeat(miner_timeout=60.0)
    hb.record_miner_seen("m1")

    status = hb.get_miner_status()
    assert "m1" in status
    assert status["m1"]["alive"] is True
    assert "age_seconds" in status["m1"]


def test_start_stop():
    hb = ValidatorHeartbeat(
        validator_id="0.0.100",
        interval_seconds=60,  # Long interval — won't actually send
    )
    hb.start()
    assert hb.is_running is True
    hb.stop()
    assert hb.is_running is False
