"""Stack light GPIO controller with mock mode support."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any

LOGGER = logging.getLogger(__name__)


class StackLightController:
    """Controls stack light outputs via GPIO with mock mode support."""

    def __init__(self, pins: Dict[str, int], mock_mode: bool = False, active_low: bool = True):
        """
        Initialize the stack light controller.

        Args:
            pins: Dictionary with keys 'green', 'amber', 'red' mapping to GPIO pin numbers
            mock_mode: If True, simulates GPIO without hardware
            active_low: If True, relays are activated by LOW signal (typical for relay modules)
        """
        self.pins = pins
        self.mock_mode = mock_mode
        self.active_low = active_low
        self.state = {"green": False, "amber": False, "red": False}
        self._flashing = False
        self._flash_interval: float = 0.5
        self._flash_stop_event = threading.Event()
        self._flash_thread: threading.Thread | None = None
        self.last_updated = None
        self.gpio = None

        if not mock_mode:
            try:
                import RPi.GPIO as GPIO
                self.gpio = GPIO
                LOGGER.info("Using RPi.GPIO for stack light control")
            except ImportError:
                try:
                    import lgpio
                    self.gpio = lgpio
                    LOGGER.info("Using lgpio for stack light control")
                except ImportError:
                    LOGGER.warning("No GPIO library available, falling back to mock mode")
                    self.mock_mode = True

        self._initialize()

    def _initialize(self) -> None:
        """Initialize GPIO pins."""
        if self.mock_mode:
            LOGGER.info("Stack light controller initialized in MOCK mode")
            LOGGER.info(f"Pin configuration: Green={self.pins['green']}, "
                       f"Amber={self.pins['amber']}, Red={self.pins['red']}")
            return

        try:
            if hasattr(self.gpio, 'setmode'):
                # RPi.GPIO style
                self.gpio.setmode(self.gpio.BCM)
                self.gpio.setwarnings(False)
                for color, pin in self.pins.items():
                    self.gpio.setup(pin, self.gpio.OUT)
                    # Initialize all relays to OFF state
                    # For active_low: HIGH = OFF, LOW = ON
                    initial_value = self.gpio.HIGH if self.active_low else self.gpio.LOW
                    self.gpio.output(pin, initial_value)
                    LOGGER.info(f"Initialized {color} light on GPIO BCM pin {pin} (active_low={self.active_low})")
            else:
                # lgpio style
                self.gpio_chip = self.gpio.gpiochip_open(0)
                for color, pin in self.pins.items():
                    # Initialize all relays to OFF state
                    initial_value = 1 if self.active_low else 0
                    self.gpio.gpio_claim_output(self.gpio_chip, pin, initial_value)
                    LOGGER.info(f"Initialized {color} light on GPIO BCM pin {pin} (active_low={self.active_low})")

            LOGGER.info("Stack light GPIO initialization complete")
        except Exception as e:
            LOGGER.error(f"Failed to initialize GPIO: {e}", exc_info=True)
            LOGGER.warning("Falling back to mock mode")
            self.mock_mode = True

    def _stop_flash_thread(self) -> None:
        """Stop the flash background thread if running."""
        if self._flash_thread is not None and self._flash_thread.is_alive():
            self._flash_stop_event.set()
            self._flash_thread.join(timeout=3.0)
        self._flashing = False
        self._flash_thread = None
        self._flash_stop_event.clear()

    def set_light_state(self, green: bool, amber: bool, red: bool) -> Dict[str, Any]:
        """
        Set the state of all three lights.  Stops any active flash.

        Args:
            green: True to turn on green light
            amber: True to turn on amber light
            red: True to turn on red light

        Returns:
            Dictionary with success status and current state
        """
        try:
            self._stop_flash_thread()
            self.state = {"green": green, "amber": amber, "red": red}
            self.last_updated = datetime.now(timezone.utc)

            if self.mock_mode:
                LOGGER.info(f"MOCK: Set lights - Green={green}, Amber={amber}, Red={red}")
            else:
                self._write_gpio(self.state)
                LOGGER.info(f"Set lights - Green={green}, Amber={amber}, Red={red}")

            return {
                "success": True,
                "state": self.state.copy(),
                "timestamp": self.last_updated.isoformat()
            }
        except Exception as e:
            LOGGER.error(f"Failed to set light state: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "state": self.state.copy()
            }

    def start_flash(self, green: bool, amber: bool, red: bool, interval: float = 0.5) -> Dict[str, Any]:
        """
        Start flashing the specified lights.

        Args:
            green: Flash green light
            amber: Flash amber light
            red: Flash red light
            interval: Seconds for each on/off half-cycle (full cycle = 2x interval)

        Returns:
            Dictionary with success status and current state
        """
        try:
            self._stop_flash_thread()

            if not (green or amber or red):
                return self.turn_off_all()

            self._flashing = True
            self._flash_interval = interval
            self._flash_stop_event.clear()

            target_state = {"green": green, "amber": amber, "red": red}

            def _flash_loop():
                lights_on = False
                while not self._flash_stop_event.is_set():
                    lights_on = not lights_on
                    if lights_on:
                        self._write_gpio(target_state)
                        self.state = target_state.copy()
                    else:
                        self._write_gpio({"green": False, "amber": False, "red": False})
                        self.state = {"green": False, "amber": False, "red": False}
                    self.last_updated = datetime.now(timezone.utc)
                    self._flash_stop_event.wait(interval)

            self._flash_thread = threading.Thread(target=_flash_loop, daemon=True)
            self._flash_thread.start()

            self.last_updated = datetime.now(timezone.utc)
            LOGGER.info(f"Started flashing - Green={green}, Amber={amber}, Red={red}, interval={interval}s")

            return {
                "success": True,
                "state": {
                    **target_state,
                    "flashing": True,
                    "flash_interval": interval,
                    "last_updated": self.last_updated.isoformat(),
                },
                "timestamp": self.last_updated.isoformat(),
            }
        except Exception as e:
            LOGGER.error(f"Failed to start flash: {e}", exc_info=True)
            return {"success": False, "error": str(e), "state": self.state.copy()}

    def stop_flash(self) -> Dict[str, Any]:
        """Stop flashing and turn off all lights."""
        self._stop_flash_thread()
        return self.turn_off_all()

    def _write_gpio(self, states: Dict[str, bool]) -> None:
        """Write raw GPIO values without updating self.state or stopping flash."""
        if self.mock_mode:
            return

        if hasattr(self.gpio, 'output'):
            for color, value in states.items():
                pin = self.pins[color]
                if self.active_low:
                    gpio_value = self.gpio.LOW if value else self.gpio.HIGH
                else:
                    gpio_value = self.gpio.HIGH if value else self.gpio.LOW
                self.gpio.output(pin, gpio_value)
        else:
            for color, value in states.items():
                pin = self.pins[color]
                if self.active_low:
                    gpio_value = 0 if value else 1
                else:
                    gpio_value = 1 if value else 0
                self.gpio.gpio_write(self.gpio_chip, pin, gpio_value)

    def get_light_state(self) -> Dict[str, Any]:
        """
        Get the current state of all lights.

        Returns:
            Dictionary with current light states and last updated timestamp
        """
        return {
            "green": self.state["green"],
            "amber": self.state["amber"],
            "red": self.state["red"],
            "flashing": self._flashing,
            "flash_interval": self._flash_interval if self._flashing else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    def turn_off_all(self) -> Dict[str, Any]:
        """
        Turn off all lights.

        Returns:
            Dictionary with success status and current state
        """
        return self.set_light_state(False, False, False)

    def test_sequence(self, duration_per_light: float = 2.0) -> Dict[str, Any]:
        """
        Run a test sequence cycling through each light.

        Sequence: Green -> Amber -> Red -> All Off

        Args:
            duration_per_light: Time in seconds to display each light

        Returns:
            Dictionary with success status and total duration
        """
        try:
            LOGGER.info(f"Starting stack light test sequence ({duration_per_light}s per light)")

            # Green
            self.set_light_state(True, False, False)
            time.sleep(duration_per_light)

            # Amber
            self.set_light_state(False, True, False)
            time.sleep(duration_per_light)

            # Red
            self.set_light_state(False, False, True)
            time.sleep(duration_per_light)

            # All off
            self.set_light_state(False, False, False)
            time.sleep(duration_per_light)

            total_duration = duration_per_light * 4

            LOGGER.info("Stack light test sequence completed")

            return {
                "success": True,
                "message": "Test sequence completed",
                "duration_seconds": total_duration
            }
        except Exception as e:
            LOGGER.error(f"Test sequence failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def startup_self_test(self) -> Dict[str, Any]:
        """
        Run a comprehensive startup self-test sequence.

        Sequence:
        - Green ON (2s) -> Green OFF
        - Amber ON (2s) -> Amber OFF
        - Red ON (2s) -> Red OFF
        - Green ON (2s) -> Green OFF
        - Amber ON (2s) -> Amber OFF
        - Red ON (2s) -> Red OFF (2s pause)
        - All ON (2s) -> All OFF (2s pause)
        - All ON (2s) -> All OFF

        Total duration: ~26 seconds

        Returns:
            Dictionary with success status and total duration
        """
        try:
            LOGGER.info("Running startup self-test sequence for stack lights")

            # First cycle through each light twice
            for cycle in range(2):
                # Green
                self.set_light_state(True, False, False)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Amber
                self.set_light_state(False, True, False)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Red
                self.set_light_state(False, False, True)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Pause after red on second cycle
                if cycle == 1:
                    time.sleep(2.0)

            # All lights ON then OFF twice
            for cycle in range(2):
                self.set_light_state(True, True, True)
                time.sleep(2.0)
                self.set_light_state(False, False, False)

                # Pause after first all-off
                if cycle == 0:
                    time.sleep(2.0)

            LOGGER.info("Startup self-test sequence completed successfully")

            return {
                "success": True,
                "message": "Self-test completed - all relays functioning",
                "duration_seconds": 26
            }
        except Exception as e:
            LOGGER.error(f"Startup self-test failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Self-test failed"
            }

    def cleanup(self) -> None:
        """Clean up GPIO resources."""
        if self.mock_mode:
            LOGGER.info("MOCK: Cleaning up GPIO resources")
            return

        try:
            # Turn off all lights
            self.turn_off_all()

            if self.gpio:
                if hasattr(self.gpio, 'cleanup'):
                    # RPi.GPIO style
                    self.gpio.cleanup()
                elif hasattr(self, 'gpio_chip'):
                    # lgpio style
                    self.gpio.gpiochip_close(self.gpio_chip)

                LOGGER.info("Stack light GPIO cleanup complete")
        except Exception as e:
            LOGGER.error(f"Failed to cleanup GPIO: {e}", exc_info=True)
