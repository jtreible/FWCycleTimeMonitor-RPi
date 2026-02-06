#!/bin/bash
# Fix RPi.GPIO compatibility on Debian 13 (Trixie) for FW Cycle Monitor
# This script:
# 1. Removes incompatible RPi.GPIO 0.7.1 from venv
# 2. Ensures system RPi.GPIO 0.7.2 is available
# 3. Optionally sets GPIO pin to 22 in config

set -e  # Exit on error

VENV_PATH="/opt/fw-cycle-monitor/.venv"
CONFIG_DIR="/home/fstre/.config/fw_cycle_monitor"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=========================================="
echo "FW Cycle Monitor - Debian 13 GPIO Fix"
echo "=========================================="
echo ""

# Check if running on Debian 13
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$VERSION_CODENAME" != "trixie" ]]; then
        echo "Warning: This script is designed for Debian 13 (trixie)"
        echo "Detected: $PRETTY_NAME"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Step 1: Install system rpi-lgpio compatibility shim
echo "[1/4] Checking system rpi-lgpio package..."
# Ensure python3-rpi.gpio is NOT installed (it's incompatible)
if dpkg -l | grep -q "python3-rpi.gpio"; then
    echo "Removing incompatible python3-rpi.gpio package..."
    sudo apt-get remove -y python3-rpi.gpio
fi

# Install the lgpio-based compatibility shim
if ! dpkg -l | grep -q "python3-rpi-lgpio"; then
    echo "Installing python3-rpi-lgpio compatibility shim..."
    sudo apt-get update
    sudo apt-get install -y python3-rpi-lgpio python3-lgpio
else
    echo "✓ System rpi-lgpio package already installed"
fi

# Step 2: Remove RPi.GPIO from venv
echo ""
echo "[2/4] Removing RPi.GPIO from venv..."
if [ -d "$VENV_PATH" ]; then
    if $VENV_PATH/bin/pip show RPi.GPIO >/dev/null 2>&1; then
        echo "Uninstalling RPi.GPIO 0.7.1 from venv..."
        $VENV_PATH/bin/pip uninstall -y RPi.GPIO
        echo "✓ Removed incompatible RPi.GPIO from venv"
    else
        echo "✓ RPi.GPIO not installed in venv (already fixed)"
    fi
else
    echo "Warning: Venv not found at $VENV_PATH"
    echo "Skipping venv cleanup"
fi

# Step 3: Create system-packages.pth for venv access
echo ""
echo "[3/4] Configuring venv to access system packages..."
if [ -d "$VENV_PATH" ]; then
    PTH_FILE="$VENV_PATH/lib/python3.13/site-packages/system-packages.pth"
    echo "/usr/lib/python3/dist-packages" > "$PTH_FILE"
    echo "✓ Created system-packages.pth"

    # Verify the fix
    if $VENV_PATH/bin/python -c "import RPi.GPIO; print(f'Using RPi.GPIO {RPi.GPIO.VERSION} from {RPi.GPIO.__file__}')" 2>/dev/null | grep -q "dist-packages"; then
        echo "✓ Venv now using system RPi.GPIO package"
    else
        echo "Warning: Could not verify system RPi.GPIO in venv"
    fi
fi

# Step 4: Set GPIO pin to 22 in config (optional)
echo ""
echo "[4/4] Configuring GPIO pin..."
if [ "$1" == "--set-gpio-22" ] || [ "$1" == "-g" ]; then
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Creating default config with GPIO pin 22..."
        mkdir -p "$CONFIG_DIR"
        cat > "$CONFIG_FILE" << 'EOF'
{
  "machine_id": "M",
  "gpio_pin": 22,
  "csv_directory": "/home/fstre/FWCycle",
  "reset_hour": 4
}
EOF
        chown fstre:fstre "$CONFIG_FILE"
        echo "✓ Created config with GPIO pin 22"
    else
        # Update existing config
        if command -v jq >/dev/null 2>&1; then
            TMP_FILE=$(mktemp)
            jq '.gpio_pin = 22' "$CONFIG_FILE" > "$TMP_FILE"
            mv "$TMP_FILE" "$CONFIG_FILE"
            chown fstre:fstre "$CONFIG_FILE"
            echo "✓ Updated GPIO pin to 22 in config"
        else
            echo "Warning: jq not installed, cannot auto-update config"
            echo "Please manually set gpio_pin to 22 in $CONFIG_FILE"
        fi
    fi
else
    echo "Skipping GPIO pin configuration (use --set-gpio-22 to enable)"
fi

# Step 5: Restart services
echo ""
echo "[5/5] Restarting services..."
if systemctl is-active --quiet fw-cycle-monitor.service; then
    echo "Restarting fw-cycle-monitor service..."
    sudo systemctl restart fw-cycle-monitor.service
    sleep 2
    if systemctl is-active --quiet fw-cycle-monitor.service; then
        echo "✓ Service restarted successfully"
    else
        echo "✗ Service failed to start. Check: sudo journalctl -u fw-cycle-monitor.service -n 50"
        exit 1
    fi
else
    echo "Note: fw-cycle-monitor.service not running, skipping restart"
fi

echo ""
echo "=========================================="
echo "✓ Fix completed successfully!"
echo "=========================================="
echo ""
echo "System RPi.GPIO version: $(python3 -c 'import RPi.GPIO; print(RPi.GPIO.VERSION)' 2>/dev/null || echo 'Not available')"
if [ -d "$VENV_PATH" ]; then
    echo "Venv RPi.GPIO version:   $($VENV_PATH/bin/python -c 'import RPi.GPIO; print(RPi.GPIO.VERSION)' 2>/dev/null || echo 'Not available')"
fi
echo ""
echo "Service status:"
systemctl status fw-cycle-monitor.service --no-pager -l | head -10

exit 0
