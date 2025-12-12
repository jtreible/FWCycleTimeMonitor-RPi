using System.Text;
using Renci.SshNet;

Console.WriteLine("PoE Switch Test Program");
Console.WriteLine("======================");

var switchIp = "192.168.0.84";
var port = 5;
var username = "admin";
var password = "Fstre13748$";
var sshPort = 22;

Console.WriteLine($"Target: {switchIp}");
Console.WriteLine($"Port to control: {port}");
Console.WriteLine($"SSH Port: {sshPort}");
Console.WriteLine();

Console.WriteLine("Select operation:");
Console.WriteLine("1. Power Down (disable PoE)");
Console.WriteLine("2. Power On (enable PoE)");
Console.WriteLine("3. Power Cycle");
Console.WriteLine("4. Get Port Status");
Console.Write("Choice: ");

var choice = Console.ReadLine();

string[] commands;
switch (choice)
{
    case "1":
        Console.WriteLine("Executing Power Down...");
        commands = new[]
        {
            "enable",
            "config",
            $"interface gigabitEthernet 1/0/{port}",
            "power inline supply disable",
            "exit",
            "exit"
        };
        break;
    case "2":
        Console.WriteLine("Executing Power On...");
        commands = new[]
        {
            "enable",
            "config",
            $"interface gigabitEthernet 1/0/{port}",
            "power inline supply enable",
            "exit",
            "exit"
        };
        break;
    case "3":
        Console.WriteLine("Executing Power Cycle...");
        Console.WriteLine("Step 1: Disabling port...");
        ExecuteCommands(switchIp, sshPort, username, password, new[]
        {
            "enable",
            "config",
            $"interface gigabitEthernet 1/0/{port}",
            "power inline supply disable",
            "exit",
            "exit"
        });
        Console.WriteLine("Waiting 3 seconds...");
        Thread.Sleep(3000);
        Console.WriteLine("Step 2: Enabling port...");
        commands = new[]
        {
            "enable",
            "config",
            $"interface gigabitEthernet 1/0/{port}",
            "power inline supply enable",
            "exit",
            "exit"
        };
        break;
    case "4":
        Console.WriteLine("Getting Port Status...");
        commands = new[]
        {
            "enable",
            $"show power inline interface gigabitEthernet 1/0/{port}"
        };
        break;
    default:
        Console.WriteLine("Invalid choice");
        return;
}

ExecuteCommands(switchIp, sshPort, username, password, commands);

Console.WriteLine("\nPress any key to exit...");
Console.ReadKey();

static void ExecuteCommands(string host, int sshPort, string username, string password, string[] commands)
{
    try
    {
        Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss.fff}] Connecting to {host}:{sshPort}...");
        using var client = new SshClient(host, sshPort, username, password);

        client.ConnectionInfo.Timeout = TimeSpan.FromSeconds(60);
        client.Connect();

        if (!client.IsConnected)
        {
            Console.WriteLine("[ERROR] Failed to establish SSH connection");
            return;
        }

        Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Connected successfully");

        using var shellStream = client.CreateShellStream("terminal", 80, 24, 800, 600, 1024);

        Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Shell stream created, waiting for initial prompt...");

        // Wait for and capture initial prompt
        var initialPrompt = WaitForPrompt(shellStream, 5000);
        Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Initial prompt detected: '{initialPrompt}'");

        var output = new StringBuilder();

        foreach (var command in commands)
        {
            Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss.fff}] Sending: {command}");
            shellStream.WriteLine(command);

            // Wait for prompt to return, indicating command completed
            var responseWithPrompt = WaitForPrompt(shellStream, 10000);

            if (!string.IsNullOrEmpty(responseWithPrompt))
            {
                output.AppendLine(responseWithPrompt);
                Console.WriteLine($"[RESPONSE]\n{responseWithPrompt}");
            }
            else
            {
                Console.WriteLine("[WARNING] No response or prompt detected!");
            }
        }

        client.Disconnect();
        Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss.fff}] Disconnected");

        Console.WriteLine("\n=== FULL OUTPUT ===");
        Console.WriteLine(output.ToString());
        Console.WriteLine("===================");
    }
    catch (Exception ex)
    {
        Console.WriteLine($"[ERROR] {ex.GetType().Name}: {ex.Message}");
        Console.WriteLine($"Stack: {ex.StackTrace}");
    }
}

static string WaitForPrompt(ShellStream stream, int timeoutMs)
{
    var output = new StringBuilder();
    var startTime = DateTime.Now;
    var lastDataTime = DateTime.Now;
    var noDataTimeout = 1000; // If no data for 1 second after receiving some, consider complete
    bool dataReceived = false;

    Console.WriteLine($"[{DateTime.Now:HH:mm:ss.fff}] Waiting for output (timeout: {timeoutMs}ms)...");

    while ((DateTime.Now - startTime).TotalMilliseconds < timeoutMs)
    {
        if (stream.DataAvailable)
        {
            // Read all available data
            var data = stream.Read();
            output.Append(data);
            Console.Write(data); // Print in real-time
            lastDataTime = DateTime.Now;
            dataReceived = true;
        }
        else if (dataReceived && (DateTime.Now - lastDataTime).TotalMilliseconds > noDataTimeout)
        {
            // No data for timeout period after receiving data - command completed
            Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss.fff}] No more data - command complete");
            return output.ToString();
        }

        Thread.Sleep(50); // Small delay to avoid busy waiting
    }

    Console.WriteLine($"\n[{DateTime.Now:HH:mm:ss.fff}] Timeout");
    return output.ToString();
}
