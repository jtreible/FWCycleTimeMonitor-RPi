using FWCycleDashboard.Components;
using FWCycleDashboard.Data;
using FWCycleDashboard.Services;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// Configure Kestrel for long-running connections
builder.WebHost.ConfigureKestrel(serverOptions =>
{
    serverOptions.Limits.KeepAliveTimeout = TimeSpan.FromMinutes(30);
    serverOptions.Limits.RequestHeadersTimeout = TimeSpan.FromMinutes(5);
});

// Add services to the container.
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

// Configure Blazor Server circuit options to prevent timeouts
builder.Services.AddServerSideBlazor(options =>
{
    options.DetailedErrors = true;
    options.DisconnectedCircuitRetentionPeriod = TimeSpan.FromMinutes(10);
    options.JSInteropDefaultCallTimeout = TimeSpan.FromMinutes(2);
});

// Configure circuit handler options for long-running operations
builder.Services.Configure<Microsoft.AspNetCore.Components.Server.CircuitOptions>(options =>
{
    options.DetailedErrors = true;
});

// Add database
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseSqlite(builder.Configuration.GetConnectionString("DefaultConnection")
        ?? "Data Source=fwcycle.db"));

// Add HTTP client for remote supervisor
builder.Services.AddHttpClient("RemoteSupervisor")
    .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
    {
        ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true // Accept self-signed certs
    });

builder.Services.AddScoped<RemoteSupervisorClient>();

// Add HTTP client for PoE switch
builder.Services.AddHttpClient("PoESwitch")
    .ConfigurePrimaryHttpMessageHandler(() => new HttpClientHandler
    {
        ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true // Accept self-signed certs from switches
    });

builder.Services.AddScoped<IPoESwitchClient, TPLinkJetStreamClient>();

var app = builder.Build();

// Ensure database is created
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    db.Database.EnsureCreated();
}

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
}


app.UseAntiforgery();

// API endpoint for RPi self-registration on boot
app.MapPost("/api/machines/register", async (
    MachineRegistrationRequest request,
    ApplicationDbContext db,
    ILogger<Program> logger) =>
{
    if (string.IsNullOrWhiteSpace(request.MachineId) ||
        string.IsNullOrWhiteSpace(request.IpAddress) ||
        string.IsNullOrWhiteSpace(request.ApiKey))
    {
        return Results.BadRequest(new { error = "machineId, ipAddress, and apiKey are required" });
    }

    var normalizedId = request.MachineId.Trim().ToUpper();
    var machine = await db.Machines
        .FirstOrDefaultAsync(m => m.MachineId == normalizedId);

    if (machine == null)
    {
        logger.LogWarning("Registration from unknown machine: {MachineId}", normalizedId);
        return Results.NotFound(new { error = $"Machine '{normalizedId}' not found" });
    }

    if (machine.ApiKey != request.ApiKey)
    {
        logger.LogWarning("Registration with invalid API key from machine: {MachineId}", normalizedId);
        return Results.Json(new { error = "Invalid API key" }, statusCode: 403);
    }

    var previousIp = machine.IpAddress;
    machine.IpAddress = request.IpAddress;
    machine.Port = request.Port;
    machine.LastSeenAt = DateTime.UtcNow;
    await db.SaveChangesAsync();

    if (previousIp != request.IpAddress)
    {
        logger.LogInformation("Machine {MachineId} IP updated: {OldIp} -> {NewIp}",
            normalizedId, previousIp, request.IpAddress);
    }
    else
    {
        logger.LogInformation("Machine {MachineId} registered at {Ip}:{Port}",
            normalizedId, request.IpAddress, request.Port);
    }

    return Results.Ok(new
    {
        status = "registered",
        machine_id = machine.MachineId,
        ip_address = machine.IpAddress,
        port = machine.Port
    });
});

app.MapStaticAssets();
app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

app.Run();

public record MachineRegistrationRequest(
    string MachineId,
    string IpAddress,
    int Port,
    string ApiKey
);
