# FW Cycle Monitor Dashboard - IIS Deployment Checklist

This checklist will help you deploy the dashboard to your Windows Server with IIS.

## Pre-Deployment

- [ ] .NET 9.0 SDK installed on development machine
- [ ] Windows Server ready with IIS installed
- [ ] ASP.NET Core 9.0 Hosting Bundle downloaded
- [ ] Network connectivity verified between server and Raspberry Pis
- [ ] Machine information collected (IPs, ports, API keys)

## Step 1: Build and Publish

On your development machine:

- [ ] Navigate to FWCycleDashboard folder
- [ ] Run build: `dotnet build`
- [ ] Verify build succeeds with no errors
- [ ] Run publish: `dotnet publish -c Release -o C:\inetpub\wwwroot\FWCycleDashboard`
- [ ] Verify web.config was included in published files
- [ ] Copy published files to server if not publishing directly

## Step 2: Server Prerequisites

On your Windows Server:

- [ ] Install ASP.NET Core 9.0 Hosting Bundle
- [ ] Restart IIS: `iisreset` in PowerShell
- [ ] Verify installation: Check "Programs and Features" for ASP.NET Core Runtime
- [ ] Ensure published files are in C:\inetpub\wwwroot\FWCycleDashboard

## Step 3: IIS Configuration

In IIS Manager:

- [ ] Create new website:
  - [ ] Name: FWCycleDashboard
  - [ ] Physical path: C:\inetpub\wwwroot\FWCycleDashboard
  - [ ] Port: 80 (or 8080)
  - [ ] Host name: (blank or server name)

- [ ] Configure Application Pool:
  - [ ] Pool name: FWCycleDashboard
  - [ ] .NET CLR version: No Managed Code
  - [ ] Managed pipeline mode: Integrated
  - [ ] Start application pool

## Step 4: File Permissions

- [ ] Right-click C:\inetpub\wwwroot\FWCycleDashboard folder
- [ ] Properties > Security > Edit
- [ ] Add IIS_IUSRS with Read & Execute permissions
- [ ] Add IIS AppPool\FWCycleDashboard with Modify permissions
- [ ] Apply and OK

## Step 5: Firewall Configuration

- [ ] Open Windows Firewall
- [ ] Create inbound rule for HTTP (port 80 or your chosen port)
- [ ] Test from another workstation on the network

## Step 6: Initial Testing

- [ ] Start the IIS website if not already started
- [ ] Open browser on the server: http://localhost
- [ ] Verify dashboard loads without errors
- [ ] Check browser console (F12) for any errors
- [ ] Test from another workstation: http://<ServerIP>

## Step 7: Add Machines and Groups

- [ ] Click "Machines" in navigation
- [ ] Add first machine with correct IP, port, and API key
- [ ] Verify connection works (should show machine status)
- [ ] Create groups via "Groups" page
- [ ] Assign machines to groups
- [ ] Return to dashboard and verify groups appear

## Step 8: Test Functionality

Test all major features:

- [ ] Manual refresh works
- [ ] Auto-refresh works (wait 30 seconds)
- [ ] Individual machine service controls work (Start/Stop/Restart)
- [ ] Individual machine stack light controls work
- [ ] Group reboot function works
- [ ] Group stack light controls work
- [ ] Group test lights function works
- [ ] Dashboard stays connected during long operations (30+ seconds)
- [ ] Check command history page shows logged commands

## Step 9: Performance Verification

- [ ] Leave dashboard open for 10+ minutes
- [ ] Verify no timeout or disconnection errors
- [ ] Test during bulk operations
- [ ] Monitor IIS logs for any errors
- [ ] Check application event log for exceptions

## Post-Deployment

- [ ] Document server URL for users
- [ ] Add server to network documentation
- [ ] Schedule regular database backups (fwcycle.db)
- [ ] Note any required Windows updates schedule
- [ ] Train users on new group control features

## Troubleshooting Reference

### Common Issues and Solutions

**Issue**: Dashboard loads but shows "Loading..." forever
- Check Raspberry Pi is reachable from server
- Verify fw-remote-supervisor service is running on Pi
- Check API key matches

**Issue**: Dashboard disconnects after a few minutes
- Verify web.config is present in deployment folder
- Check IIS application pool hasn't stopped
- Review browser console for WebSocket errors
- Verify IIS application pool recycling settings

**Issue**: Permission errors in IIS logs
- Confirm IIS AppPool\FWCycleDashboard has Modify permissions
- Check fwcycle.db file is not locked
- Verify application pool identity is correct

**Issue**: Group controls don't appear
- Ensure at least one group exists
- Assign machines to groups
- Refresh the dashboard

**Issue**: Stack light controls don't work
- Verify Pi has stack light hardware connected
- Check remote supervisor version supports stack lights
- Review command history for error messages

## Rollback Plan

If deployment fails:

1. Stop the IIS website
2. Restore previous version if this is an update
3. Check IIS application logs: `C:\inetpub\logs\LogFiles`
4. Review Windows Event Viewer > Application logs
5. Verify .NET 9.0 Runtime is installed correctly

## Update Procedure

For future updates:

1. [ ] Stop IIS website
2. [ ] Backup current fwcycle.db database
3. [ ] Backup current deployment folder (optional)
4. [ ] Publish new version to deployment folder
5. [ ] Verify web.config is present
6. [ ] Start IIS website
7. [ ] Test functionality
8. [ ] Monitor for errors

## Contact Information

- **Dashboard Location**: http://<ServerIP>
- **Server Name**: _____________
- **Deployment Date**: _____________
- **Deployed By**: _____________
- **IIS Version**: _____________
- **Notes**: _____________

---

**Deployment Complete!** ✓

Your FW Cycle Monitor Dashboard is now ready for production use.
