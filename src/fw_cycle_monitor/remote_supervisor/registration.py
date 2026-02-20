"""Dashboard registration for automatic IP discovery on boot."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Optional

import httpx

from ..config import load_config
from .settings import get_settings

LOGGER = logging.getLogger(__name__)

_MAX_RETRIES = 3
_INITIAL_BACKOFF_SECONDS = 5
_REQUEST_TIMEOUT_SECONDS = 10


def detect_local_ip() -> Optional[str]:
    """Detect the RPi's IP address by opening a UDP socket.

    No data is sent -- the OS selects the appropriate outbound interface
    and binds a local IP address.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        LOGGER.warning("Could not detect local IP via UDP probe")

    # Fallback: hostname resolution
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    LOGGER.error("Failed to detect local IP address")
    return None


async def register_with_dashboard() -> bool:
    """POST this RPi's IP/port/machine_id to the dashboard.

    Returns True on success, False on failure.
    """
    settings = get_settings()

    if not settings.dashboard_url:
        LOGGER.debug("No dashboard_url configured; skipping registration")
        return False

    config = load_config()
    local_ip = detect_local_ip()

    if not local_ip:
        LOGGER.error("Cannot register: failed to detect local IP")
        return False

    api_key = settings.api_keys[0] if settings.api_keys else ""

    registration_url = f"{settings.dashboard_url.rstrip('/')}/api/machines/register"
    payload = {
        "machineId": config.machine_id,
        "ipAddress": local_ip,
        "port": settings.port,
        "apiKey": api_key,
    }

    LOGGER.info(
        "Registering with dashboard at %s as %s (%s:%s)",
        registration_url, config.machine_id, local_ip, settings.port,
    )

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(verify=False, timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(registration_url, json=payload)

            if response.status_code == 200:
                LOGGER.info("Successfully registered with dashboard: %s", response.json())
                return True
            elif response.status_code == 404:
                LOGGER.warning(
                    "Dashboard returned 404 - machine '%s' not found. "
                    "Add this machine to the dashboard first.",
                    config.machine_id,
                )
                return False
            elif response.status_code == 403:
                LOGGER.warning(
                    "Dashboard rejected API key for machine '%s'. "
                    "Verify the API key matches on both sides.",
                    config.machine_id,
                )
                return False
            else:
                LOGGER.warning(
                    "Dashboard registration attempt %d/%d returned HTTP %d: %s",
                    attempt, _MAX_RETRIES, response.status_code, response.text,
                )
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as exc:
            LOGGER.warning(
                "Dashboard registration attempt %d/%d failed: %s",
                attempt, _MAX_RETRIES, exc,
            )

        if attempt < _MAX_RETRIES:
            backoff = _INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1))
            LOGGER.info("Retrying registration in %d seconds...", backoff)
            await asyncio.sleep(backoff)

    LOGGER.error("Failed to register with dashboard after %d attempts", _MAX_RETRIES)
    return False


async def register_in_background() -> None:
    """Run registration as a fire-and-forget background task."""
    try:
        await register_with_dashboard()
    except Exception:
        LOGGER.exception("Unexpected error during dashboard registration")
