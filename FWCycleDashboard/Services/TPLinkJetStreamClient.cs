using System.Text;
using Renci.SshNet;

namespace FWCycleDashboard.Services;

/// <summary>
/// PoE switch client implementation for TP-Link JetStream series switches.
/// Uses SSH/CLI to control PoE ports on TL-SG2218P, TL-SG3452P, and similar models.
/// </summary>
public class TPLinkJetStreamClient : IPoESwitchClient
{
    private readonly ILogger<TPLinkJetStreamClient> _logger;
    private readonly string? _username;
    private readonly string? _password;
    private readonly int _sshPort;
    private readonly int _commandTimeout;

    public TPLinkJetStreamClient(
        ILogger<TPLinkJetStreamClient> logger,
        IConfiguration configuration)
    {
        _logger = logger;
        _username = configuration["PoESwitch:Username"] ?? "admin";
        _password = configuration["PoESwitch:Password"];
        _sshPort = int.TryParse(configuration["PoESwitch:SshPort"], out var port) ? port : 22;
        _commandTimeout = int.TryParse(configuration["PoESwitch:CommandTimeoutSeconds"], out var timeout) ? timeout : 30;
    }

    public async Task<(bool success, string? error)> PowerCyclePortAsync(
        string switchIp,
        int portNumber,
        int waitSeconds = 3)
    {
        _logger.LogInformation("Power cycling port {Port} on switch {SwitchIp}", portNumber, switchIp);

        // Disable PoE
        var (disableSuccess, disableError) = await DisablePortAsync(switchIp, portNumber);
        if (!disableSuccess)
        {
            return (false, $"Failed to disable port: {disableError}");
        }

        // Wait for clean shutdown
        _logger.LogInformation("Waiting {Seconds} seconds for clean shutdown", waitSeconds);
        await Task.Delay(waitSeconds * 1000);

        // Re-enable PoE
        var (enableSuccess, enableError) = await EnablePortAsync(switchIp, portNumber);
        if (!enableSuccess)
        {
            return (false, $"Failed to re-enable port: {enableError}");
        }

        _logger.LogInformation("Successfully power cycled port {Port} on switch {SwitchIp}", portNumber, switchIp);
        return (true, null);
    }

    public async Task<(bool success, string? error)> EnablePortAsync(string switchIp, int portNumber)
    {
        return await SetPortPoEStateAsync(switchIp, portNumber, true);
    }

    public async Task<(bool success, string? error)> DisablePortAsync(string switchIp, int portNumber)
    {
        return await SetPortPoEStateAsync(switchIp, portNumber, false);
    }

    public async Task<(bool? enabled, string? error)> GetPortStatusAsync(string switchIp, int portNumber)
    {
        try
        {
            var commands = new[]
            {
                "enable",
                $"show power inline interface gigabitEthernet 1/0/{portNumber}"
            };

            var (success, output, error) = await ExecuteSshCommandsAsync(switchIp, commands);

            if (!success)
            {
                return (null, error);
            }

            // Parse output to determine if PoE is enabled
            // Output typically contains "Admin Mode: Enable" or "Admin Mode: Disable"
            var isEnabled = output?.Contains("Admin Mode: Enable", StringComparison.OrdinalIgnoreCase) ?? false;

            return (isEnabled, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get port status for port {Port} on switch {SwitchIp}",
                portNumber, switchIp);
            return (null, ex.Message);
        }
    }

    private async Task<(bool success, string? error)> SetPortPoEStateAsync(
        string switchIp,
        int portNumber,
        bool enabled)
    {
        try
        {
            if (string.IsNullOrEmpty(_password))
            {
                return (false, "SSH password not configured. Set PoESwitch:Password in appsettings.json");
            }

            var action = enabled ? "enable" : "disable";

            // TP-Link JetStream CLI command sequence:
            // enable -> config -> interface gigabitEthernet 1/0/X -> power inline supply enable/disable -> exit -> exit
            var commands = new[]
            {
                "enable",
                "config",
                $"interface gigabitEthernet 1/0/{portNumber}",
                $"power inline supply {action}",
                "exit",
                "exit"
            };

            _logger.LogInformation(
                "Executing SSH command to {Action} PoE on port {Port} of switch {SwitchIp}",
                action,
                portNumber,
                switchIp);

            var (success, output, error) = await ExecuteSshCommandsAsync(switchIp, commands);

            if (!success)
            {
                return (false, error);
            }

            _logger.LogInformation(
                "Successfully {Action}d PoE on port {Port} of switch {SwitchIp}",
                action,
                portNumber,
                switchIp);

            return (true, null);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to set PoE state for port {Port} on switch {SwitchIp}",
                portNumber, switchIp);
            return (false, ex.Message);
        }
    }

    private async Task<(bool success, string? output, string? error)> ExecuteSshCommandsAsync(
        string host,
        string[] commands)
    {
        return await Task.Run(() =>
        {
            try
            {
                using var client = new SshClient(host, _sshPort, _username, _password);

                client.ConnectionInfo.Timeout = TimeSpan.FromSeconds(_commandTimeout);

                _logger.LogDebug("Connecting to switch {Host}:{Port} as {Username}", host, _sshPort, _username);

                client.Connect();

                if (!client.IsConnected)
                {
                    return (false, null, "Failed to establish SSH connection");
                }

                using var shellStream = client.CreateShellStream("terminal", 80, 24, 800, 600, 1024);

                // Wait for initial prompt
                Thread.Sleep(1000);

                var output = new StringBuilder();

                foreach (var command in commands)
                {
                    _logger.LogDebug("Executing command: {Command}", command);

                    shellStream.WriteLine(command);
                    Thread.Sleep(500); // Wait for command to execute

                    // Read output
                    while (shellStream.DataAvailable)
                    {
                        var line = shellStream.ReadLine();
                        if (line != null)
                        {
                            output.AppendLine(line);
                        }
                    }
                }

                // Give final command time to complete
                Thread.Sleep(500);

                // Read any remaining output
                while (shellStream.DataAvailable)
                {
                    var line = shellStream.ReadLine();
                    if (line != null)
                    {
                        output.AppendLine(line);
                    }
                }

                client.Disconnect();

                var outputStr = output.ToString();
                _logger.LogDebug("SSH command output: {Output}", outputStr);

                return (true, outputStr, null);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "SSH command execution failed for host {Host}", host);
                return (false, null, ex.Message);
            }
        });
    }
}
