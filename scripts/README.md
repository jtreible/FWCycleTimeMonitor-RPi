# GPIO Fix Scripts for Debian 13

These scripts fix RPi.GPIO compatibility issues on Debian 13 (Trixie) for the FW Cycle Monitor.

## The Problem

Debian 13 uses a modern GPIO character device interface (`/dev/gpiochip*`) that's incompatible with the older RPi.GPIO library. The PyPI version (0.7.1) and even Debian's python3-rpi.gpio package (0.7.1a4) don't work properly with the newer kernels.

**Solution**: Use `python3-rpi-lgpio` - a compatibility shim that implements the RPi.GPIO API but uses the modern lgpio backend underneath.

**Symptom**: `RuntimeError: Failed to add edge detection` when the service tries to start.

## Quick Start

### Option 1: One-Time Manual Fix

Run this on each Pi to fix the issue immediately:

```bash
cd /opt/fw-cycle-monitor
sudo bash scripts/fix-rpi-gpio-debian13.sh --set-gpio-22
```

### Option 2: Auto-Fix on Every Boot (Recommended)

Install a systemd service that automatically applies the fix on boot:

```bash
cd /opt/fw-cycle-monitor
sudo bash scripts/install-auto-fix.sh
```

This ensures the fix is applied even after updates that might reinstall the incompatible version.

## Deployment to Multiple Pis

### Using SSH Loop

Deploy to all 44 Pis at once:

```bash
#!/bin/bash
# Save this as deploy-fix.sh on your control machine

# List of Pi IP addresses
PIS=(
    "192.168.0.169"
    "192.168.0.170"
    # ... add all 44 IPs
)

for IP in "${PIS[@]}"; do
    echo "=========================================="
    echo "Fixing Pi at $IP"
    echo "=========================================="

    # Copy the fix script
    scp scripts/fix-rpi-gpio-debian13.sh fstre@$IP:/tmp/

    # Run the fix
    ssh fstre@$IP "sudo bash /tmp/fix-rpi-gpio-debian13.sh --set-gpio-22"

    # Optional: Install auto-fix service
    # scp scripts/install-auto-fix.sh fstre@$IP:/tmp/
    # ssh fstre@$IP "cd /opt/fw-cycle-monitor && sudo bash /tmp/install-auto-fix.sh"

    echo "✓ Fixed $IP"
    echo ""
done

echo "All Pis fixed!"
```

### Using Ansible

Create `fix-gpio.yml`:

```yaml
---
- name: Fix RPi.GPIO on Debian 13
  hosts: fw_monitors
  become: yes
  tasks:
    - name: Install system RPi.GPIO package
      apt:
        name: python3-rpi.gpio
        state: present
        update_cache: yes

    - name: Remove RPi.GPIO from venv
      pip:
        name: RPi.GPIO
        state: absent
        virtualenv: /opt/fw-cycle-monitor/.venv

    - name: Create system-packages.pth
      copy:
        content: "/usr/lib/python3/dist-packages\n"
        dest: /opt/fw-cycle-monitor/.venv/lib/python3.13/site-packages/system-packages.pth

    - name: Set GPIO pin to 22
      lineinfile:
        path: /home/fstre/.config/fw_cycle_monitor/config.json
        regexp: '  "gpio_pin":'
        line: '  "gpio_pin": 22,'

    - name: Restart fw-cycle-monitor service
      systemd:
        name: fw-cycle-monitor
        state: restarted
```

Run with: `ansible-playbook -i inventory fix-gpio.yml`

## Scripts Description

### fix-rpi-gpio-debian13.sh

The main fix script that:
1. Installs system RPi.GPIO 0.7.2 package
2. Removes incompatible RPi.GPIO 0.7.1 from venv
3. Configures venv to use system packages
4. Optionally sets GPIO pin to 22
5. Restarts the service

**Usage**:
```bash
sudo bash fix-rpi-gpio-debian13.sh              # Fix only
sudo bash fix-rpi-gpio-debian13.sh --set-gpio-22 # Fix + set GPIO to 22
```

### install-auto-fix.sh

Installs the fix as a systemd service that runs on every boot, before fw-cycle-monitor starts.

**Usage**:
```bash
sudo bash install-auto-fix.sh
```

## Verification

After running the fix, verify it worked:

```bash
# Check service status
systemctl status fw-cycle-monitor.service

# Check RPi.GPIO version
/opt/fw-cycle-monitor/.venv/bin/python -c "import RPi.GPIO; print(RPi.GPIO.VERSION)"
# Should output: 0.7.2

# Test GPIO event logging
# Touch GPIO 22 (physical pin 15) to 3.3V
# Then check:
tail -5 /home/fstre/FWCycle/CM_*.csv
# Should show new timestamp entries
```

## Troubleshooting

**Service still failing after fix**:
```bash
# Check detailed logs
sudo journalctl -u fw-cycle-monitor.service -n 100

# Verify venv is using system RPi.GPIO
/opt/fw-cycle-monitor/.venv/bin/python -c "import RPi.GPIO; print(RPi.GPIO.__file__)"
# Should output: /usr/lib/python3/dist-packages/RPi/GPIO/__init__.py
```

**No events logging**:
- Verify GPIO pin number in config: `cat ~/.config/fw_cycle_monitor/config.json`
- Test with wire: Connect GPIO 22 (pin 15) to 3.3V (pin 1)
- Check logs for "Cycle logged" messages

## Technical Details

**Why this happens**:
- Debian 13 uses the modern GPIO character device API (`/dev/gpiochip*`)
- RPi.GPIO 0.7.1 (PyPI) and python3-rpi.gpio (Debian) don't work with edge detection on modern kernels
- python3-rpi-lgpio is a compatibility shim that implements RPi.GPIO API using the modern lgpio backend
- Virtual environments isolate packages, preventing access to system version

**The fix**:
- Installs python3-rpi-lgpio system package (compatibility shim)
- Removes any RPi.GPIO from venv
- Adds system site-packages to venv search path
- Python finds and uses the lgpio-based compatibility shim

**Why auto-fix on boot**:
- Some update processes might reinstall the PyPI version
- Ensures consistency across reboots
- Runs before monitor service, preventing startup failures
