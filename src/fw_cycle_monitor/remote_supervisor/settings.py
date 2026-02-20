"""Configuration helpers for the remote supervisor agent."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import List, Optional

from ..config import CONFIG_DIR, ensure_config_dir

LOGGER = logging.getLogger(__name__)

SETTINGS_PATH = CONFIG_DIR / "remote_supervisor.json"
_SETTINGS_CACHE: RemoteSupervisorSettings | None = None
_SETTINGS_LOCK = RLock()


@dataclass
class StackLightSettings:
    """Stack light configuration.

    Default pins are for Waveshare 3-channel relay HAT:
    - BCM 26 (Relay 1) → Green
    - BCM 20 (Relay 2) → Amber
    - BCM 21 (Relay 3) → Red

    Note: Waveshare relay board is active LOW (LOW=ON, HIGH=OFF)
    """

    enabled: bool = True
    mock_mode: bool = False
    active_low: bool = True
    startup_self_test: bool = True
    green_pin: int = 26
    amber_pin: int = 20
    red_pin: int = 21


@dataclass
class RemoteSupervisorSettings:
    """Runtime options for the remote supervisor API."""

    host: str = "0.0.0.0"
    port: int = 8443
    unit_name: str = "fw-cycle-monitor.service"
    api_keys: List[str] = field(default_factory=list)
    certfile: Optional[Path] = None
    keyfile: Optional[Path] = None
    ca_bundle: Optional[Path] = None
    metrics_enabled: bool = True
    dashboard_url: Optional[str] = "http://192.168.0.248:8085"
    stacklight: StackLightSettings = field(default_factory=StackLightSettings)

    def __post_init__(self) -> None:
        if isinstance(self.certfile, str):
            self.certfile = Path(self.certfile)
        if isinstance(self.keyfile, str):
            self.keyfile = Path(self.keyfile)
        if isinstance(self.ca_bundle, str):
            self.ca_bundle = Path(self.ca_bundle)
        self.host = self.host or "0.0.0.0"
        try:
            self.port = int(self.port)
        except (TypeError, ValueError):
            self.port = 8443
        if self.port <= 0 or self.port > 65535:
            self.port = 8443
        self.unit_name = self.unit_name or "fw-cycle-monitor.service"
        if isinstance(self.api_keys, (str, bytes)):
            self.api_keys = [str(self.api_keys)]
        else:
            self.api_keys = [str(key) for key in self.api_keys]

    @property
    def require_auth(self) -> bool:
        return bool(self.api_keys)


def load_settings() -> RemoteSupervisorSettings:
    """Load supervisor settings from disk and environment."""

    ensure_config_dir()
    payload: dict[str, object]
    if SETTINGS_PATH.exists():
        try:
            payload = json.loads(SETTINGS_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            payload = {}
    else:
        payload = {}

    env_host = os.getenv("FW_REMOTE_SUPERVISOR_HOST")
    if env_host:
        payload["host"] = env_host

    env_port = os.getenv("FW_REMOTE_SUPERVISOR_PORT")
    if env_port:
        payload["port"] = env_port

    env_unit = os.getenv("FW_REMOTE_SUPERVISOR_UNIT")
    if env_unit:
        payload["unit_name"] = env_unit

    api_key = os.getenv("FW_REMOTE_SUPERVISOR_API_KEY")
    if api_key:
        keys = payload.get("api_keys")
        if isinstance(keys, list):
            keys = [str(k) for k in keys]
        else:
            keys = []
        keys.append(api_key)
        payload["api_keys"] = keys

    certfile = os.getenv("FW_REMOTE_SUPERVISOR_CERTFILE")
    if certfile:
        payload["certfile"] = certfile

    keyfile = os.getenv("FW_REMOTE_SUPERVISOR_KEYFILE")
    if keyfile:
        payload["keyfile"] = keyfile

    ca_bundle = os.getenv("FW_REMOTE_SUPERVISOR_CA_BUNDLE")
    if ca_bundle:
        payload["ca_bundle"] = ca_bundle

    metrics_enabled = os.getenv("FW_REMOTE_SUPERVISOR_METRICS_ENABLED")
    if metrics_enabled is not None:
        payload["metrics_enabled"] = metrics_enabled.lower() not in {"0", "false", "no"}

    dashboard_url = os.getenv("FW_REMOTE_SUPERVISOR_DASHBOARD_URL")
    if dashboard_url:
        payload["dashboard_url"] = dashboard_url

    # Handle stacklight settings
    if "stacklight" in payload and isinstance(payload["stacklight"], dict):
        stacklight_data = payload["stacklight"]
        payload["stacklight"] = StackLightSettings(
            enabled=stacklight_data.get("enabled", True),
            mock_mode=stacklight_data.get("mock_mode", False),
            active_low=stacklight_data.get("active_low", True),
            startup_self_test=stacklight_data.get("startup_self_test", True),
            green_pin=stacklight_data.get("pins", {}).get("green", 26),
            amber_pin=stacklight_data.get("pins", {}).get("amber", 20),
            red_pin=stacklight_data.get("pins", {}).get("red", 21),
        )

    return RemoteSupervisorSettings(**payload)


def get_settings() -> RemoteSupervisorSettings:
    """Return cached settings, reloading on demand."""

    global _SETTINGS_CACHE
    with _SETTINGS_LOCK:
        if _SETTINGS_CACHE is None:
            _SETTINGS_CACHE = load_settings()
        return _SETTINGS_CACHE


def refresh_settings() -> RemoteSupervisorSettings:
    """Refresh and return the cached supervisor settings."""

    global _SETTINGS_CACHE
    with _SETTINGS_LOCK:
        _SETTINGS_CACHE = load_settings()
        return _SETTINGS_CACHE


def fix_supervisor_config() -> bool:
    """Patch remote_supervisor.json on disk to fix common misconfigurations.

    Fixes applied:
    - ``host`` set to a specific IP instead of ``0.0.0.0`` (causes bind
      failures when the IP changes).

    Returns True if changes were written, False otherwise.
    """
    if not SETTINGS_PATH.exists():
        return False

    try:
        data = json.loads(SETTINGS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return False

    changed = False

    # Fix host: should always be 0.0.0.0 to bind on all interfaces
    host = data.get("host", "0.0.0.0")
    if host not in ("0.0.0.0", "127.0.0.1", "localhost", "::"):
        LOGGER.info("Fixing bind address in config: %s -> 0.0.0.0", host)
        data["host"] = "0.0.0.0"
        changed = True

    if changed:
        try:
            SETTINGS_PATH.write_text(json.dumps(data, indent=2))
            LOGGER.info("Updated %s", SETTINGS_PATH)
        except OSError as exc:
            LOGGER.warning("Failed to write config fix: %s", exc)
            return False

    return changed
