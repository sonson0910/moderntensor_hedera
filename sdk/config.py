"""
ModernTensor Configuration Loader

Loads settings from config.yaml with environment variable fallback.
Provides typed accessors for protocol, validator, miner, and API config.

Usage:
    from sdk.config import load_config, get_protocol_config, get_validator_id

    cfg = load_config()                    # Load from config.yaml
    protocol = get_protocol_config(cfg)    # -> ProtocolConfig
    vid = get_validator_id(cfg)            # -> str
"""

import os
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# YAML Loader (with graceful fallback if pyyaml not installed)
# ──────────────────────────────────────────────────────────────

try:
    import yaml

    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

# Cache
_cached_config: dict | None = None


def load_config(path: str | Path | None = None, *, force_reload: bool = False) -> dict:
    """
    Load configuration from YAML file.

    Priority:
        1. Explicit `path` argument
        2. Environment variable `MDT_CONFIG_PATH`
        3. Default `config.yaml` at project root

    Returns:
        Merged config dict.  Always returns at least an empty dict.
    """
    global _cached_config
    if _cached_config is not None and not force_reload:
        return _cached_config

    if path is None:
        path = os.environ.get("MDT_CONFIG_PATH", str(_DEFAULT_CONFIG_PATH))

    config_path = Path(path)
    config: dict[str, Any] = {}

    if config_path.exists() and _HAS_YAML:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config = loaded
                    logger.info("Config loaded from %s", config_path)
                else:
                    logger.warning("Config file %s did not contain a dict, using defaults", config_path)
        except Exception as e:
            logger.warning("Failed to load config from %s: %s — using defaults", config_path, e)
    elif not config_path.exists():
        logger.info("Config file %s not found — using env vars / defaults", config_path)
    elif not _HAS_YAML:
        logger.warning("pyyaml not installed — config.yaml ignored, using env vars / defaults")

    _cached_config = config
    return config


def get_protocol_config(config: dict | None = None) -> "ProtocolConfig":
    """
    Build a ProtocolConfig from loaded config, with env var fallback.
    """
    from sdk.protocol import ProtocolConfig

    if config is None:
        config = load_config()

    proto = config.get("protocol", {})

    return ProtocolConfig(
        protocol_fee_rate=float(proto.get(
            "protocol_fee_rate",
            os.environ.get("MDT_FEE_RATE", 0.05),
        )),
        min_stake_amount=float(proto.get(
            "min_stake_amount",
            os.environ.get("MDT_MIN_STAKE", 100.0),
        )),
        max_miners_per_task=int(proto.get(
            "max_miners_per_task",
            os.environ.get("MDT_MAX_MINERS", 5),
        )),
        emission_rate=float(proto.get("emission_rate", 1.0)),
        epoch_length=int(proto.get("epoch_length", 100)),
        min_validators=int(proto.get("min_validators", 1)),
    )


def get_validator_id(config: dict | None = None) -> str:
    """
    Return validator ID from config.yaml or env var VALIDATOR_ID.
    """
    if config is None:
        config = load_config()

    val_section = config.get("validator", {})
    vid = val_section.get("validator_id") or os.environ.get("VALIDATOR_ID", "")
    return str(vid)


def get_miner_config(config: dict | None = None) -> dict:
    """
    Return miner configuration as a dict.
    """
    if config is None:
        config = load_config()

    miner = config.get("miner", {})
    return {
        "miner_id": str(miner.get("miner_id") or os.environ.get("MINER_ID", "0.0.1001")),
        "stake": float(miner.get("stake", os.environ.get("MDT_STAKE_AMOUNT", 500.0))),
        "port": int(miner.get("port", os.environ.get("MINER_PORT", 8091))),
        "subnets": miner.get("subnets", [0]),
        "capabilities": miner.get("capabilities", []),
    }


def get_api_config(config: dict | None = None) -> dict:
    """
    Return API configuration (ports, etc.).
    """
    if config is None:
        config = load_config()

    api = config.get("api", {})
    return {
        "ws_port": int(api.get("ws_port", os.environ.get("MDT_WS_PORT", 8765))),
        "metrics_port": int(api.get("metrics_port", os.environ.get("MDT_METRICS_PORT", 9090))),
        "api_port": int(api.get("api_port", os.environ.get("MDT_API_PORT", 8000))),
    }


def get_logging_config(config: dict | None = None) -> dict:
    """
    Return logging configuration.
    """
    if config is None:
        config = load_config()

    log = config.get("logging", {})
    return {
        "level": str(log.get("level", os.environ.get("MDT_LOG_LEVEL", "INFO"))),
        "json_format": bool(log.get("json_format", True)),
        "log_file": str(log.get("log_file", "")),
    }
