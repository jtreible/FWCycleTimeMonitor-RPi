"""Auto-fix RPi.GPIO compatibility on Debian 13 (Trixie)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

LOGGER = logging.getLogger(__name__)

__all__ = ["ensure_gpio_compatibility"]


def _is_debian_trixie() -> bool:
    """Check if running on Debian 13 (Trixie)."""
    try:
        with open("/etc/os-release") as f:
            content = f.read()
            return "trixie" in content.lower()
    except FileNotFoundError:
        return False


def _is_package_installed(package: str) -> bool:
    """Check if a Debian package is installed."""
    try:
        result = subprocess.run(
            ["dpkg", "-l", package],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and package in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _install_system_package(package: str) -> bool:
    """Install a system package using apt-get."""
    try:
        LOGGER.info("Installing system package: %s", package)
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", package],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )
        if result.returncode != 0:
            LOGGER.warning("Failed to install %s: %s", package, result.stderr)
            return False
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        LOGGER.warning("Failed to install %s: %s", package, exc)
        return False


def _remove_system_package(package: str) -> bool:
    """Remove a system package using apt-get."""
    try:
        LOGGER.info("Removing incompatible package: %s", package)
        result = subprocess.run(
            ["sudo", "apt-get", "remove", "-y", package],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _remove_venv_rpi_gpio(venv_path: Path) -> bool:
    """Remove RPi.GPIO from virtual environment."""
    pip_path = venv_path / "bin" / "pip"
    if not pip_path.exists():
        return True

    try:
        # Check if RPi.GPIO is installed in venv
        result = subprocess.run(
            [str(pip_path), "show", "RPi.GPIO"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Not installed, nothing to do
            return True

        LOGGER.info("Removing incompatible RPi.GPIO from venv")
        result = subprocess.run(
            [str(pip_path), "uninstall", "-y", "RPi.GPIO"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            LOGGER.info("Removed RPi.GPIO from venv")
            return True
        else:
            LOGGER.warning("Failed to remove RPi.GPIO: %s", result.stderr)
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        LOGGER.warning("Error removing RPi.GPIO from venv: %s", exc)
        return False


def _create_system_packages_pth(venv_path: Path) -> bool:
    """Create .pth file to allow venv access to system packages."""
    try:
        # Find the site-packages directory
        site_packages = list(venv_path.glob("lib/python*/site-packages"))
        if not site_packages:
            LOGGER.warning("Could not find site-packages in venv")
            return False

        pth_file = site_packages[0] / "system-packages.pth"
        pth_file.write_text("/usr/lib/python3/dist-packages\n")
        LOGGER.info("Created system-packages.pth for venv")
        return True
    except OSError as exc:
        LOGGER.warning("Failed to create system-packages.pth: %s", exc)
        return False


def ensure_gpio_compatibility(venv_path: Optional[Path] = None) -> bool:
    """
    Ensure GPIO compatibility on Debian 13.

    This function:
    1. Checks if running on Debian 13 (Trixie)
    2. Ensures python3-rpi-lgpio is installed (removes python3-rpi.gpio if present)
    3. Removes RPi.GPIO from venv
    4. Creates .pth file to access system packages

    Returns:
        True if the fix was applied successfully or not needed, False on error.
    """

    # Only run on Debian 13
    if not _is_debian_trixie():
        LOGGER.debug("Not running on Debian 13, skipping GPIO compatibility fix")
        return True

    LOGGER.info("Applying GPIO compatibility fix for Debian 13...")

    # Remove incompatible python3-rpi.gpio if installed
    if _is_package_installed("python3-rpi.gpio"):
        if not _remove_system_package("python3-rpi.gpio"):
            LOGGER.warning("Failed to remove python3-rpi.gpio, continuing anyway")

    # Install python3-rpi-lgpio compatibility shim
    if not _is_package_installed("python3-rpi-lgpio"):
        if not _install_system_package("python3-rpi-lgpio"):
            LOGGER.error("Failed to install python3-rpi-lgpio")
            return False
    else:
        LOGGER.debug("python3-rpi-lgpio already installed")

    # Install lgpio dependency
    if not _is_package_installed("python3-lgpio"):
        _install_system_package("python3-lgpio")

    # Handle venv if provided
    if venv_path and venv_path.exists():
        _remove_venv_rpi_gpio(venv_path)
        _create_system_packages_pth(venv_path)

    LOGGER.info("GPIO compatibility fix applied successfully")
    return True


def main() -> int:
    """CLI entry point for testing."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    venv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/fw-cycle-monitor/.venv")

    if ensure_gpio_compatibility(venv):
        print("✓ GPIO compatibility ensured")
        return 0
    else:
        print("✗ GPIO compatibility fix failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
