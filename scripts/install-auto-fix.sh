#!/bin/bash
# Install automatic GPIO fix that runs on boot
# This creates a systemd oneshot service that runs before fw-cycle-monitor starts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIX_SCRIPT="/usr/local/bin/fw-cycle-gpio-fix.sh"
SERVICE_FILE="/etc/systemd/system/fw-cycle-gpio-fix.service"

echo "Installing automatic GPIO fix service..."
echo ""

# Copy the fix script to system location
echo "[1/3] Installing fix script to $FIX_SCRIPT..."
sudo cp "$SCRIPT_DIR/fix-rpi-gpio-debian13.sh" "$FIX_SCRIPT"
sudo chmod +x "$FIX_SCRIPT"
echo "✓ Fix script installed"

# Create systemd service
echo ""
echo "[2/3] Creating systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null << 'EOF'
[Unit]
Description=FW Cycle Monitor - Auto-fix RPi.GPIO on Debian 13
Before=fw-cycle-monitor.service
After=network.target
ConditionPathExists=/opt/fw-cycle-monitor/.venv

[Service]
Type=oneshot
ExecStart=/usr/local/bin/fw-cycle-gpio-fix.sh --set-gpio-22
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Service file created"

# Enable the service
echo ""
echo "[3/3] Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable fw-cycle-gpio-fix.service
echo "✓ Service enabled"

echo ""
echo "=========================================="
echo "✓ Auto-fix service installed!"
echo "=========================================="
echo ""
echo "The fix will now run automatically on every boot before"
echo "the fw-cycle-monitor service starts."
echo ""
echo "To manually trigger the fix now:"
echo "  sudo systemctl start fw-cycle-gpio-fix.service"
echo ""
echo "To check fix status:"
echo "  systemctl status fw-cycle-gpio-fix.service"
echo ""
echo "To disable auto-fix:"
echo "  sudo systemctl disable fw-cycle-gpio-fix.service"
echo ""

# Run it once now
read -p "Run the fix now? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    sudo systemctl start fw-cycle-gpio-fix.service
    echo ""
    systemctl status fw-cycle-gpio-fix.service --no-pager
fi

exit 0
