"""
Tests for sdk/config.py — YAML config loader with env var fallback.
"""

import os
import tempfile
import pytest


def test_load_config_from_file(tmp_path):
    """Load config from a YAML file."""
    from sdk.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "protocol:\n  protocol_fee_rate: 0.10\n  min_stake_amount: 200.0\n"
        "validator:\n  validator_id: '0.0.5555'\n"
    )

    cfg = load_config(str(config_file), force_reload=True)
    assert cfg["protocol"]["protocol_fee_rate"] == 0.10
    assert cfg["protocol"]["min_stake_amount"] == 200.0
    assert cfg["validator"]["validator_id"] == "0.0.5555"


def test_load_config_missing_file():
    """Returns empty dict when file doesn't exist."""
    from sdk.config import load_config

    cfg = load_config("/nonexistent/path/config.yaml", force_reload=True)
    assert cfg == {}


def test_get_validator_id_from_config(tmp_path):
    """get_validator_id reads from YAML."""
    from sdk.config import load_config, get_validator_id

    config_file = tmp_path / "config.yaml"
    config_file.write_text("validator:\n  validator_id: '0.0.7777'\n")

    cfg = load_config(str(config_file), force_reload=True)
    assert get_validator_id(cfg) == "0.0.7777"


def test_get_validator_id_env_fallback(monkeypatch):
    """get_validator_id falls back to env var."""
    from sdk.config import get_validator_id

    monkeypatch.setenv("VALIDATOR_ID", "0.0.9999")
    vid = get_validator_id({})
    assert vid == "0.0.9999"


def test_get_miner_config_defaults():
    """get_miner_config returns sensible defaults."""
    from sdk.config import get_miner_config

    mc = get_miner_config({})
    assert mc["port"] == 8091
    assert mc["stake"] == 500.0


def test_get_api_config_defaults():
    """get_api_config returns sensible defaults."""
    from sdk.config import get_api_config

    ac = get_api_config({})
    assert ac["ws_port"] == 8765
    assert ac["metrics_port"] == 9090


def test_get_logging_config_defaults():
    """get_logging_config returns sensible defaults."""
    from sdk.config import get_logging_config

    lc = get_logging_config({})
    assert lc["level"] == "INFO"
    assert lc["json_format"] is True
