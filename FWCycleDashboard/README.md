# FW Cycle Monitor Dashboard

A web-based dashboard for monitoring and controlling Raspberry Pi-based injection molding cycle time monitors across your facility.

## Features

- **Real-time Monitoring**: View status of all machines in one dashboard with compact tiles
- **Remote Control**: Start, stop, and restart monitoring services remotely
- **Group Management**: Organize machines into groups with dedicated group control tiles on main dashboard
- **Bulk Operations**: Control all machines in a group with one click - reboot, stack lights, and testing
- **Stack Light Control**: Control industrial stack lights on each machine (Green/Amber/Red indicators)
- **Command History**: Track all commands executed with success/failure status
- **Auto-refresh**: Automatically updates machine status every 30 seconds
- **Persistent Connections**: Configured for long-running sessions without timeouts
- **No Authentication Required**: Designed for internal network use only

## Prerequisites

- .NET 9.0 SDK or later
- Windows Server with IIS (for production deployment)
- Network access to Raspberry Pi machines running the cycle monitor

## Quick Start (Development)

1. **Clone the repository** (if not already done)
   ```bash
   cd C:\Users\Operation1\Documents\GitHub\FWCycleTimeMonitor-RPi\FWCycleDashboard
   ```

2. **Build the application**
   ```bash
   dotnet build
   ```

3. **Run the application**
   ```bash
   dotnet run
   ```

4. **Open your browser**
   Navigate to: http://localhost:5217 (or the URL shown in the console)

## Adding Your First Machine

1. Click **Machines** in the navigation menu
2. Click **Add Machine**
3. Fill in the details:
   - **Machine ID**: M402 (or your machine's ID)
   - **IP Address**: 192.168.0.96
   - **Port**: 8443
   - **API Key**: z68cMjqyLyzMj5UFwpS94MKeSnUiUGJYWpN-YWYMpsw
   - **Use HTTPS**: Leave unchecked (unless you configured TLS on the Pi)
   - **Location** (optional): Building A, Line 1, etc.
4. Click **Save**

## Creating Groups

1. Click **Groups** in the navigation menu
2. Click **Add Group**
3. Enter a name (e.g., "Building A", "Line 1", "Second Floor")
4. Click **Save**
5. Go back to **Machines** and edit each machine to assign it to a group

## Using the Dashboard

### Main Dashboard

The dashboard is now organized into three sections:

#### 1. Summary Cards
- Quick overview showing online, stopped, offline, and total machine counts
- Compact view at the top of the page

#### 2. Group Control Tiles
- Each group appears as a tile with bulk controls
- **Reboot All Pi**: Reboot all Raspberry Pis in the group at once
- **Stack Light Controls**: Set all machines to Green, Amber, Red, or Off
- **Test Lights**: Run test sequence on all machines in the group
- Shows online/total machine count for each group

#### 3. Machine Tiles
- Compact tiles showing individual machine status
- Color-coded borders:
  - **Green**: Service running
  - **Red**: Service stopped
  - **Gray**: Machine offline/unreachable
- Each tile shows:
  - Machine ID and group name
  - IP address and uptime
  - Last cycle time and average
  - Service control buttons (Start/Restart/Stop with icons)
  - Reboot Pi button
  - Stack light controls (G/A/R/Off buttons)
- Tiles are scaled down to fit 6 machines per row on large screens

### Individual Machine Operations
- Click service control buttons on any machine tile
- Stack light buttons show current state (solid color when active)
- All operations are logged to command history

### Command History
- View all commands executed on any machine
- See success/failure status
- Useful for troubleshooting

## Deployment to IIS (Windows Server)

### Step 1: Publish the Application

1. Open PowerShell in the FWCycleDashboard directory
2. Run the publish command:
   ```powershell
   dotnet publish -c Release -o C:\inetpub\wwwroot\FWCycleDashboard
   ```

### Step 2: Install ASP.NET Core Hosting Bundle

1. Download the **ASP.NET Core 9.0 Hosting Bundle** from:
   https://dotnet.microsoft.com/download/dotnet/9.0

2. Install it on your Windows Server

3. Restart IIS:
   ```powershell
   iisreset
   ```

### Step 3: Create IIS Application

1. Open **IIS Manager**
2. Right-click **Sites** > **Add Website**
3. Configure:
   - **Site name**: FWCycleDashboard
   - **Physical path**: C:\inetpub\wwwroot\FWCycleDashboard
   - **Binding**:
     - Type: http
     - Port: 80 (or 8080 if 80 is in use)
     - Host name: (leave blank or enter your server name)
4. Click **OK**

### Step 4: Configure Application Pool

1. In IIS Manager, click **Application Pools**
2. Find **FWCycleDashboard** pool
3. Right-click > **Basic Settings**
4. Set **.NET CLR version** to **No Managed Code**
5. Click **OK**

### Step 5: Set Permissions

1. Right-click the **FWCycleDashboard** folder
2. Properties > Security > Edit
3. Add **IIS_IUSRS** with **Read & Execute** permissions
4. Add **IIS AppPool\FWCycleDashboard** with **Modify** permissions (for database writes)

### Step 6: Test

1. Open a browser on any workstation in your domain
2. Navigate to: `http://<ServerName>` or `http://<ServerIP>`
3. You should see the dashboard

### Step 7: Configure for Long-Running Sessions

The application now includes `web.config` with settings optimized for IIS deployment:
- WebSocket support for Blazor Server
- Extended timeout values to prevent disconnections
- Connection keep-alive for 30 minutes

These settings are automatically applied when you publish and deploy to IIS. The dashboard will maintain connections even during long operations like bulk reboots.

## Configuration

### Database Location
The SQLite database is stored as `fwcycle.db` in the application root directory.

To change the database location, edit `appsettings.json`:
```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Data Source=C:\\path\\to\\your\\database.db"
  }
}
```

### Auto-Refresh Interval
By default, the dashboard refreshes every 30 seconds. To change this, edit `Components/Pages/Home.razor`, line 213:
```csharp
// Change FromSeconds(30) to your desired interval
refreshTimer = new System.Threading.Timer(async _ =>
{
    if (autoRefreshEnabled)
    {
        await InvokeAsync(async () => await RefreshAll());
    }
}, null, TimeSpan.FromSeconds(30), TimeSpan.FromSeconds(30));
```

## Recent Updates (v2.0)

**Dashboard Improvements:**
- Redesigned main dashboard with compact machine tiles (6 per row on large screens)
- Added group control tiles directly on main dashboard for quick bulk operations
- Bulk reboot functionality per group with confirmation dialogs
- Bulk stack light control (set all, test all) per group
- Fixed timeout issues - dashboard now stays connected during long-running operations
- Improved title scaling in navigation bar
- Enhanced mobile responsiveness with smaller tiles

**Configuration Changes:**
- Added `web.config` for IIS with optimized timeout settings
- Configured Kestrel for 30-minute keep-alive connections
- Extended Blazor Server circuit retention to 10 minutes
- Increased JS interop timeout to 2 minutes for long operations

## Troubleshooting

### Dashboard times out or disconnects
- This should now be resolved with v2.0 updates
- If issues persist, check IIS application pool is not recycling frequently
- Verify `web.config` was deployed with the application
- Check browser console for WebSocket connection errors

### "Cannot connect" errors on dashboard
- Verify the Raspberry Pi is on the network
- Check that `fw-remote-supervisor.service` is running on the Pi:
  ```bash
  sudo systemctl status fw-remote-supervisor.service
  ```
- Verify the IP address and port are correct
- Ensure API key matches what's configured on the Pi

### Dashboard not accessible from other workstations
- Check Windows Firewall on the server
- Verify IIS website is started
- Check Application Pool is running
- Ensure client workstations can reach the server's IP/hostname

### Database permission errors
- Ensure `IIS AppPool\FWCycleDashboard` has **Modify** permissions on the application folder
- Check that the database file is not locked by another process

### Service commands not working
- Verify the Pi user running the service has sudo permissions for systemctl
- Check the remote supervisor logs on the Pi:
  ```bash
  sudo journalctl -u fw-remote-supervisor.service
  ```

## Updating the Dashboard

1. Stop the IIS website
2. Rebuild and publish:
   ```powershell
   dotnet publish -c Release -o C:\inetpub\wwwroot\FWCycleDashboard
   ```
3. Start the IIS website

## Security Notes

- This dashboard has **no authentication** by design
- It should **only** be used on internal, trusted networks
- Do not expose to the internet
- API keys are stored in the database - keep backups secure
- Consider using Windows Firewall to restrict access to authorized IP ranges

## Next Steps / Future Enhancements

Some ideas for future improvements:
- Add charts/graphs for cycle time trends
- Email/SMS alerts for offline machines
- Export machine data to Excel/CSV
- Windows domain authentication
- HTTPS/TLS support
- Historical metrics storage and reporting
- Machine availability/uptime reporting

## Support

For issues or questions about the dashboard:
- Check the troubleshooting section above
- Review application logs in IIS
- Check Raspberry Pi remote supervisor logs

## License

Internal use only - FW Automation
