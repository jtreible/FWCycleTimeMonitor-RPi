#!/bin/bash
# Deploy GPIO fix to all Raspberry Pis
# Edit the PIS array below with your Pi IP addresses or hostnames

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USERNAME="fstre"
INSTALL_AUTO_FIX=true  # Set to false to only run fix once

# ========================================
# EDIT THIS: Add all your Pi IP addresses
# ========================================
PIS=(
    "192.168.0.169"  # M402 - Example
    # "192.168.0.170"
    # "192.168.0.171"
    # Add all 44 Pi IP addresses here...
)

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS_COUNT=0
FAIL_COUNT=0
FAILED_PIS=()

echo "=========================================="
echo "FW Cycle Monitor - Mass GPIO Fix Deployment"
echo "=========================================="
echo ""
echo "Will deploy to ${#PIS[@]} Raspberry Pis"
echo "Auto-fix on boot: $INSTALL_AUTO_FIX"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi
echo ""

for IP in "${PIS[@]}"; do
    echo "=========================================="
    echo "Processing: $IP"
    echo "=========================================="

    # Check if Pi is reachable
    if ! ping -c 1 -W 2 "$IP" > /dev/null 2>&1; then
        echo -e "${RED}✗ Pi at $IP is not reachable${NC}"
        FAILED_PIS+=("$IP (unreachable)")
        ((FAIL_COUNT++))
        echo ""
        continue
    fi

    # Copy fix script
    echo "[1/4] Copying fix script to $IP..."
    if ! scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
         "$SCRIPT_DIR/fix-rpi-gpio-debian13.sh" \
         "$USERNAME@$IP:/tmp/" > /dev/null 2>&1; then
        echo -e "${RED}✗ Failed to copy script to $IP${NC}"
        FAILED_PIS+=("$IP (copy failed)")
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    echo -e "${GREEN}✓ Script copied${NC}"

    # Run the fix
    echo "[2/4] Running fix on $IP..."
    if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
         "$USERNAME@$IP" \
         "sudo bash /tmp/fix-rpi-gpio-debian13.sh --set-gpio-22" 2>&1 | \
         grep -q "Fix completed successfully"; then
        echo -e "${YELLOW}⚠ Fix may have failed on $IP (check manually)${NC}"
        FAILED_PIS+=("$IP (fix execution)")
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    echo -e "${GREEN}✓ Fix applied${NC}"

    # Optionally install auto-fix service
    if [ "$INSTALL_AUTO_FIX" = true ]; then
        echo "[3/4] Installing auto-fix service on $IP..."
        scp -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
            "$SCRIPT_DIR/install-auto-fix.sh" \
            "$USERNAME@$IP:/tmp/" > /dev/null 2>&1

        # Run with auto-yes
        if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
           "$USERNAME@$IP" \
           "cd /opt/fw-cycle-monitor && echo 'y' | sudo bash /tmp/install-auto-fix.sh" \
           > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Auto-fix service installed${NC}"
        else
            echo -e "${YELLOW}⚠ Auto-fix service installation may have failed${NC}"
        fi
    else
        echo "[3/4] Skipping auto-fix service installation"
    fi

    # Verify service is running
    echo "[4/4] Verifying service on $IP..."
    if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
       "$USERNAME@$IP" \
       "systemctl is-active --quiet fw-cycle-monitor.service"; then
        echo -e "${GREEN}✓ Service is running${NC}"
        ((SUCCESS_COUNT++))
    else
        echo -e "${RED}✗ Service is not running${NC}"
        FAILED_PIS+=("$IP (service not running)")
        ((FAIL_COUNT++))
    fi

    echo ""
done

# Summary
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo -e "Total Pis:      ${#PIS[@]}"
echo -e "${GREEN}Successful:     $SUCCESS_COUNT${NC}"
echo -e "${RED}Failed:         $FAIL_COUNT${NC}"
echo ""

if [ ${#FAILED_PIS[@]} -gt 0 ]; then
    echo "Failed Pis:"
    for FAIL in "${FAILED_PIS[@]}"; do
        echo -e "  ${RED}✗${NC} $FAIL"
    done
    echo ""
    exit 1
else
    echo -e "${GREEN}✓ All Pis successfully updated!${NC}"
    exit 0
fi
