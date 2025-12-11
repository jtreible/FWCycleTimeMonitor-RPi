# PoE Switch Integration - IIS Deployment Guide

## Overview
This guide covers deploying the FW Cycle Dashboard with PoE switch control to your IIS server and testing the remote power cycling functionality.

---

## Prerequisites

### On IIS Server
Verify these are installed:
```powershell
# Check git
git --version

# Check .NET 9 SDK
dotnet --version
```

If missing, install:
- **Git for Windows**: https://git-scm.com/download/win
- **.NET 9 SDK**: https://dotnet.microsoft.com/download/dotnet/9.0

### Network Requirements
Ensure IIS server can reach:
- All Raspberry Pis on port **8443** (HTTPS)
- Both PoE switches on port **22** (SSH)

---

## Part 1: Deploy to IIS Server

### Step 1: Pull Latest Code
```powershell
cd C:\Users\Operation1\Documents\GitHub\FWCycleTimeMonitor-RPi
git pull origin main
```

### Step 2: Configure PoE Switch Credentials
Edit the configuration file:
```powershell
notepad FWCycleDashboard\appsettings.json
```

Update with your PoE switch password:
```json
{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.AspNetCore": "Warning"
    }
  },
  "AllowedHosts": "*",
  "PoESwitch": {
    "Username": "admin",
    "Password": "YOUR_SWITCH_PASSWORD_HERE",
    "SshPort": "22",
    "CommandTimeoutSeconds": "30"
  }
}
```

**Important:** Replace `YOUR_SWITCH_PASSWORD_HERE` with the actual admin password for your TP-Link switches.

### Step 3: Build and Publish
```powershell
cd FWCycleDashboard
dotnet publish -c Release -o "C:\inetpub\wwwroot\FWCycleDashboard"
```

**Note:** Adjust `C:\inetpub\wwwroot\FWCycleDashboard` to match your actual IIS site directory.

### Step 4: Restart IIS Application Pool

**Option A - PowerShell:**
```powershell
Import-Module WebAdministration
Restart-WebAppPool -Name "FWCycleDashboard"
```
*(Replace "FWCycleDashboard" with your actual application pool name)*

**Option B - IIS Manager GUI:**
1. Open IIS Manager
2. Go to Application Pools
3. Right-click your application pool
4. Select "Recycle"

---

## Part 2: Configure PoE Switch Integration

### Switch Information
You have two TP-Link JetStream switches:
- **TL-SG2218P**: 16-port PoE switch (150W)
- **TL-SG3452P**: 48-port PoE switch (384W)

### Step 1: Enable SSH on Switches (if not already enabled)
1. Log into switch web interface
2. Navigate to: **System Tools → User Config**
3. Ensure SSH is enabled (should be on by default)
4. Set/verify admin password

### Step 2: Note Switch Details
Document the following for each switch:
- **Switch IP Address**: _________________
- **Admin Password**: _________________
- **Which Raspberry Pis are connected**: _________________

### Step 3: Configure Machines in Dashboard

1. **Open the dashboard:**
   - Navigate to `http://your-iis-server/machines`

2. **Edit each machine:**
   - Click "Edit" button for a machine
   - Scroll to "PoE Switch Configuration" section
   - Fill in:
     - **PoE Switch IP Address**: The IP of the switch (e.g., `192.168.1.100`)
     - **PoE Switch Port Number**: Physical port number (1-16 for TL-SG2218P, 1-48 for TL-SG3452P)
   - Click "Save"

3. **Repeat for all Raspberry Pis connected to PoE switches**

---

## Part 3: Testing PoE Control

### Test 1: Single Machine Power Cycle

1. **Go to dashboard home:**
   - Navigate to `http://your-iis-server/`

2. **Find a configured machine:**
   - Look for a machine card that shows the "Power Cycle (PoE)" button
   - This button only appears if PoE switch IP and port are configured

3. **Click "Power Cycle (PoE)":**
   - Confirm the action in the dialog
   - Watch for:
     - Raspberry Pi should go offline within seconds
     - After 3 seconds, power should restore
     - Pi should boot back up (~30-60 seconds)
     - Dashboard should show it back online

4. **Check command history:**
   - Navigate to `/history` page
   - Verify the power cycle command was logged
   - Check for any errors

### Test 2: Verify Logs

If power cycle fails, check logs:

**Dashboard Logs (on IIS server):**
```powershell
# View recent logs
Get-Content "C:\inetpub\wwwroot\FWCycleDashboard\logs\*.log" -Tail 50
```

**Common Issues:**
- **"SSH password not configured"**: Update appsettings.json with correct password
- **"Failed to establish SSH connection"**:
  - Verify switch IP address is correct
  - Verify SSH is enabled on switch
  - Check firewall between IIS server and switch
- **"Authentication failed"**: Wrong username/password in appsettings.json
- **Port number errors**: Verify correct physical port number (1-based, not 0-based)

### Test 3: Group Power Cycle (Advanced)

1. **Create a machine group** (if not already done):
   - Navigate to `/groups`
   - Add a group (e.g., "Production Floor")
   - Assign machines to the group

2. **Use group controls on dashboard:**
   - On the home page, find the group tile
   - Group controls include "Reboot All Pi" button
   - **Note:** Group power cycle via PoE would need to be implemented if desired

---

## Part 4: SSH Command Reference

### Manual SSH Testing (Optional)

If you want to test SSH commands manually to troubleshoot:

```bash
# SSH into switch
ssh admin@192.168.1.100

# Enter privileged mode
enable

# Enter configuration mode
config

# Select port interface
interface gigabitEthernet 1/0/8

# Disable PoE on port 8
power inline supply disable

# Re-enable PoE on port 8
power inline supply enable

# Exit interface config
exit

# Exit config mode
exit

# Check PoE status
show power inline interface gigabitEthernet 1/0/8
```

---

## Configuration Summary

### appsettings.json
```json
{
  "PoESwitch": {
    "Username": "admin",
    "Password": "your-switch-password",
    "SshPort": "22",
    "CommandTimeoutSeconds": "30"
  }
}
```

### Per-Machine Settings (in Dashboard UI)
- **PoE Switch IP Address**: Switch IP (e.g., `192.168.1.100`)
- **PoE Switch Port Number**: Physical port (1-48)

---

## Troubleshooting

### Dashboard doesn't load after deployment
1. Check IIS application pool is started
2. Verify .NET 9 runtime is installed on IIS server
3. Check Windows Event Viewer for errors

### "Power Cycle (PoE)" button doesn't appear
- Machine must have both PoE Switch IP and Port configured
- Edit machine and verify both fields are filled in

### Power cycle fails with SSH errors
1. **Test SSH manually** from IIS server:
   ```powershell
   ssh admin@192.168.1.100
   ```
2. If prompted about host key, type "yes" to accept
3. This stores the host key for future connections

### Raspberry Pi doesn't come back online
1. Check physical PoE connection
2. Verify correct port number (physical port, not port index)
3. Try manual power cycle by unplugging
4. Check Pi SD card for boot issues

### Permission denied errors
- Ensure IIS application pool identity has read/write access to:
  - Database file: `fwcycle.db`
  - Log directory
  - Application directory

---

## Next Steps After Testing

Once PoE control is working:

1. **Document your switch port mappings:**
   - Create a spreadsheet showing which Pi is on which port
   - Keep updated as you add/move machines

2. **Consider automation:**
   - Schedule regular reboots during off-hours
   - Set up alerts for offline machines
   - Implement automatic power cycle for unresponsive Pis

3. **Security hardening:**
   - Change default switch passwords
   - Consider SSH key authentication instead of passwords
   - Restrict SSH access to IIS server IP only

---

## Support & Documentation

- **TP-Link TL-SG2218P Manual**: https://www.tp-link.com/us/support/download/tl-sg2218p/
- **TP-Link TL-SG3452P Manual**: https://www.tp-link.com/us/support/download/tl-sg3452p/
- **SSH.NET Documentation**: https://github.com/sshnet/SSH.NET
- **Project Repository**: https://github.com/jtreible/FWCycleTimeMonitor-RPi

---

## Quick Reference Commands

### Redeploy After Code Changes
```powershell
cd C:\Users\Operation1\Documents\GitHub\FWCycleTimeMonitor-RPi
git pull origin main
cd FWCycleDashboard
dotnet publish -c Release -o "C:\inetpub\wwwroot\FWCycleDashboard"
Restart-WebAppPool -Name "FWCycleDashboard"
```

### Check Dashboard Status
```powershell
# Test if site is responding
Invoke-WebRequest -Uri "http://localhost/" -UseBasicParsing

# Check application pool status
Get-WebAppPoolState -Name "FWCycleDashboard"
```

### View Recent Logs
```powershell
Get-Content "C:\inetpub\wwwroot\FWCycleDashboard\logs\*.log" -Tail 100
```

---

*Document created: 2025-12-11*
*Last updated: Initial deployment guide*
