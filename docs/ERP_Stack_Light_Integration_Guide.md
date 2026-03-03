# FW Cycle Time Monitor - Stack Light Integration Guide

## For ERP System Engineers

---

## Overview

Each production machine has a Raspberry Pi running two services:

- **fw-cycle-monitor** -- Monitors a GPIO sensor for cycle completions, logs to CSV
- **fw-remote-supervisor** -- REST API (FastAPI) for remote control of service and stack lights

The ERP system controls stack lights by sending HTTP requests directly to each RPi's API. The RPi does **not** decide which color to show -- your ERP system owns that logic entirely.

---

## Connection Details

| Parameter | Value |
|-----------|-------|
| **Protocol** | HTTP or HTTPS |
| **Default Port** | `8443` |
| **Authentication** | `X-API-Key` header (required) |
| **Content-Type** | `application/json` |
| **Timeout recommendation** | 3-5 seconds (15s for test sequence) |

**Base URL pattern**: `http://<pi-ip>:8443`

---

## Light State Definitions

| Condition | Green | Amber | Red | Description |
|-----------|-------|-------|-----|-------------|
| Cycle time at or below expected | ON | off | off | Machine running within target |
| Cycle time above expected | off | ON | off | Machine running slow |
| No cycle for 3+ minutes | off | off | ON | Machine idle / down |
| Warning before going red | off | FLASH | off | Machine approaching idle timeout |
| All off | off | off | off | Shift ended / not monitored |

---

## API Endpoints -- Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stacklight/set` | POST | Set lights to solid on/off state |
| `/stacklight/flash` | POST | Start flashing specified lights |
| `/stacklight/stop-flash` | POST | Stop flashing and turn all off |
| `/stacklight/off` | POST | Turn off all lights |
| `/stacklight/test` | POST | Run test sequence (~8 seconds) |
| `/stacklight/status` | GET | Get current light state |
| `/metrics/summary` | GET | Get cycle time metrics |
| `/config` | GET | Get machine configuration |
| `/service/status` | GET | Get monitor service status |

---

## Endpoint Details

### POST `/stacklight/set` -- Set Solid Light State

Sets one or more lights to a solid (non-flashing) state. Automatically stops any active flash.

**Request body** (all three fields required):
```json
{
  "green": true,
  "amber": false,
  "red": false
}
```

**Response:**
```json
{
  "success": true,
  "state": {
    "green": true,
    "amber": false,
    "red": false,
    "flashing": false,
    "flash_interval": null,
    "last_updated": "2026-03-03T14:22:31.456789+00:00"
  },
  "timestamp": "2026-03-03T14:22:31+00:00",
  "error": null
}
```

### POST `/stacklight/flash` -- Flash Lights

Starts flashing the specified lights on and off at a configurable interval. Useful for warning states (e.g., flash amber when approaching idle timeout). Automatically stops any previous flash or solid state.

**Request body:**
```json
{
  "green": false,
  "amber": true,
  "red": false,
  "interval": 0.5
}
```

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| `green` | bool | `false` | -- | Flash green light |
| `amber` | bool | `false` | -- | Flash amber light |
| `red` | bool | `false` | -- | Flash red light |
| `interval` | float | `0.5` | 0.1 - 5.0 | Seconds per on/off half-cycle |

An `interval` of `0.5` means the light is on for 0.5s then off for 0.5s (1.0s full cycle = 60 blinks/min). An `interval` of `1.0` gives a slower, more deliberate blink.

**Response:**
```json
{
  "success": true,
  "state": {
    "green": false,
    "amber": true,
    "red": false,
    "flashing": true,
    "flash_interval": 0.5,
    "last_updated": "2026-03-03T14:22:31.456789+00:00"
  },
  "timestamp": "2026-03-03T14:22:31+00:00",
  "error": null
}
```

**Multiple lights**: You can flash more than one light simultaneously:
```json
{"green": false, "amber": true, "red": true, "interval": 0.3}
```

### POST `/stacklight/stop-flash` -- Stop Flashing

Stops any active flash and turns all lights off.

**Request body**: none

**Response**: Same format as `/stacklight/set`

### POST `/stacklight/off` -- Turn All Off

Turns off all lights and stops any active flash.

**Request body**: none

### POST `/stacklight/test` -- Test Sequence

Cycles through all lights: Green (2s) -> Amber (2s) -> Red (2s) -> Off (2s). This is a blocking call that takes approximately 8 seconds. Use a 15-second timeout.

**Request body**: none

### GET `/stacklight/status` -- Get Current State

Returns the current state of all lights including flash status.

**Response:**
```json
{
  "green": false,
  "amber": true,
  "red": false,
  "flashing": true,
  "flash_interval": 0.5,
  "last_updated": "2026-03-03T14:22:31.456789+00:00"
}
```

### GET `/metrics/summary` -- Get Cycle Metrics

Returns the last cycle time and rolling window averages. Used by the ERP to determine which light to show.

**Response:**
```json
{
  "machine_id": "M01",
  "last_cycle_seconds": 45.3,
  "window_averages": {
    "5": 44.2,
    "15": 45.1,
    "30": 45.5,
    "60": 46.0
  }
}
```

`window_averages` keys are minutes (5, 15, 30, 60). Values are `null` if not enough data.

---

## ERP Evaluation Logic

The ERP system should run a scheduled job (every 15-30 seconds) that evaluates each machine and sets the appropriate light.

### Decision Flow

```
For each machine:
  1. GET /metrics/summary
  2. If unreachable -> skip (retry next cycle)
  3. If no cycles for >= 3 minutes -> SET RED
  4. If last_cycle_seconds > expected_cycle_time -> SET AMBER
  5. If last_cycle_seconds <= expected_cycle_time -> SET GREEN
```

### Architecture Diagram

```
+----------------------------------------------------------+
|                      ERP System                          |
|                                                          |
|  +----------------------------------------------------+  |
|  | Scheduled Job (every 15-30 seconds)                |  |
|  |                                                     |  |
|  | For each active machine:                           |  |
|  |   1. Look up expected cycle time from work order   |  |
|  |   2. GET /metrics/summary from the RPi             |  |
|  |   3. Compare last_cycle_seconds to expected        |  |
|  |   4. Track idle time (no new cycle > 3 min)        |  |
|  |   5. POST /stacklight/set with correct color       |  |
|  +------------------+---------------------------------+  |
|                      |                                    |
+----------------------|------------------------------------+
                       | HTTP
         +-------------+-------------+
         v             v             v
     +--------+   +--------+   +--------+
     |  RPi   |   |  RPi   |   |  RPi   |
     |  M01   |   |  M02   |   |  M03   |
     | :8443  |   | :8443  |   | :8443  |
     +---+----+   +---+----+   +---+----+
         |            |            |
      [GREEN]      [AMBER]      [RED]
     Stack Light  Stack Light  Stack Light
```

---

## Code Examples

### curl -- Quick Reference

```bash
# Variables
PI="192.168.0.10"
PORT="8443"
KEY="your-api-key"
BASE="http://${PI}:${PORT}"

# ── Solid Colors ───────────────────────────────────────────

# Green (running within cycle time)
curl -X POST "${BASE}/stacklight/set" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": true, "amber": false, "red": false}'

# Amber (running above cycle time)
curl -X POST "${BASE}/stacklight/set" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": false, "amber": true, "red": false}'

# Red (idle 3+ minutes)
curl -X POST "${BASE}/stacklight/set" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": false, "amber": false, "red": true}'

# ── Flashing ───────────────────────────────────────────────

# Flash amber at default speed (0.5s on/off)
curl -X POST "${BASE}/stacklight/flash" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": false, "amber": true, "red": false, "interval": 0.5}'

# Flash red slowly (1s on/off)
curl -X POST "${BASE}/stacklight/flash" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": false, "amber": false, "red": true, "interval": 1.0}'

# Flash amber + red together (fast)
curl -X POST "${BASE}/stacklight/flash" \
  -H "X-API-Key: ${KEY}" \
  -H "Content-Type: application/json" \
  -d '{"green": false, "amber": true, "red": true, "interval": 0.3}'

# Stop flashing
curl -X POST "${BASE}/stacklight/stop-flash" \
  -H "X-API-Key: ${KEY}"

# ── Other ──────────────────────────────────────────────────

# Turn all off
curl -X POST "${BASE}/stacklight/off" \
  -H "X-API-Key: ${KEY}"

# Run test sequence (~8s, use longer timeout)
curl -X POST "${BASE}/stacklight/test" \
  -H "X-API-Key: ${KEY}" \
  --max-time 15

# Get current state
curl "${BASE}/stacklight/status" \
  -H "X-API-Key: ${KEY}"

# Get cycle metrics
curl "${BASE}/metrics/summary" \
  -H "X-API-Key: ${KEY}"
```

---

### Python -- Full ERP Integration Example

```python
import requests
import time
from dataclasses import dataclass


@dataclass
class Machine:
    machine_id: str
    ip_address: str
    port: int = 8443
    api_key: str = ""
    group: str = ""       # e.g., "low_bay", "high_bay"
    use_https: bool = False


# ── Machine Registry ────────────────────────────────────────
# Populate this from your ERP database or config file.

MACHINES = [
    Machine("M01", "192.168.0.10", api_key="key-m01", group="low_bay"),
    Machine("M02", "192.168.0.11", api_key="key-m02", group="low_bay"),
    Machine("M03", "192.168.0.12", api_key="key-m03", group="high_bay"),
    Machine("M04", "192.168.0.13", api_key="key-m04", group="high_bay"),
]


def _base_url(m: Machine) -> str:
    proto = "https" if m.use_https else "http"
    return f"{proto}://{m.ip_address}:{m.port}"


def _headers(m: Machine) -> dict:
    return {"X-API-Key": m.api_key, "Content-Type": "application/json"}


# ── Single-Machine Light Control ────────────────────────────

def set_light(m: Machine, green: bool, amber: bool, red: bool) -> dict:
    """Set stack light to a solid state."""
    resp = requests.post(
        f"{_base_url(m)}/stacklight/set",
        json={"green": green, "amber": amber, "red": red},
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def set_green(m: Machine) -> dict:
    return set_light(m, green=True, amber=False, red=False)


def set_amber(m: Machine) -> dict:
    return set_light(m, green=False, amber=True, red=False)


def set_red(m: Machine) -> dict:
    return set_light(m, green=False, amber=False, red=True)


def flash_light(m: Machine, green=False, amber=False, red=False, interval=0.5) -> dict:
    """Start flashing specified lights."""
    resp = requests.post(
        f"{_base_url(m)}/stacklight/flash",
        json={"green": green, "amber": amber, "red": red, "interval": interval},
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def flash_amber(m: Machine, interval=0.5) -> dict:
    return flash_light(m, amber=True, interval=interval)


def flash_red(m: Machine, interval=0.5) -> dict:
    return flash_light(m, red=True, interval=interval)


def stop_flash(m: Machine) -> dict:
    resp = requests.post(
        f"{_base_url(m)}/stacklight/stop-flash",
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def all_off(m: Machine) -> dict:
    resp = requests.post(
        f"{_base_url(m)}/stacklight/off",
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def test_sequence(m: Machine) -> dict:
    """Run test sequence. Takes ~8 seconds -- use longer timeout."""
    resp = requests.post(
        f"{_base_url(m)}/stacklight/test",
        headers=_headers(m),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def get_status(m: Machine) -> dict:
    resp = requests.get(
        f"{_base_url(m)}/stacklight/status",
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


def get_metrics(m: Machine) -> dict:
    resp = requests.get(
        f"{_base_url(m)}/metrics/summary",
        headers=_headers(m),
        timeout=5,
    )
    resp.raise_for_status()
    return resp.json()


# ── Group & Bulk Operations ─────────────────────────────────

def get_machines_by_group(group: str) -> list[Machine]:
    return [m for m in MACHINES if m.group == group]


def set_group_light(group: str, green: bool, amber: bool, red: bool) -> dict:
    """Set all machines in a group to the same solid light state."""
    results = {}
    for m in get_machines_by_group(group):
        try:
            results[m.machine_id] = set_light(m, green, amber, red)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def flash_group(group: str, green=False, amber=False, red=False, interval=0.5) -> dict:
    """Flash specified lights on all machines in a group."""
    results = {}
    for m in get_machines_by_group(group):
        try:
            results[m.machine_id] = flash_light(m, green, amber, red, interval)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def set_all_light(green: bool, amber: bool, red: bool) -> dict:
    """Set ALL machines to the same solid light state."""
    results = {}
    for m in MACHINES:
        try:
            results[m.machine_id] = set_light(m, green, amber, red)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def flash_all(green=False, amber=False, red=False, interval=0.5) -> dict:
    """Flash specified lights on ALL machines."""
    results = {}
    for m in MACHINES:
        try:
            results[m.machine_id] = flash_light(m, green, amber, red, interval)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def test_all() -> dict:
    """Run test sequence on all machines (sequential, ~8s each)."""
    results = {}
    for m in MACHINES:
        try:
            results[m.machine_id] = test_sequence(m)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def test_group(group: str) -> dict:
    """Run test sequence on all machines in a group."""
    results = {}
    for m in get_machines_by_group(group):
        try:
            results[m.machine_id] = test_sequence(m)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def all_off_all() -> dict:
    """Turn off all lights on all machines."""
    results = {}
    for m in MACHINES:
        try:
            results[m.machine_id] = all_off(m)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


def all_off_group(group: str) -> dict:
    """Turn off all lights in a group."""
    results = {}
    for m in get_machines_by_group(group):
        try:
            results[m.machine_id] = all_off(m)
        except Exception as e:
            results[m.machine_id] = {"success": False, "error": str(e)}
    return results


# ── ERP Cycle Time Evaluation Logic ─────────────────────────

# Track when we last saw a *new* cycle value per machine
_last_cycle_value: dict[str, float | None] = {}
_last_new_cycle_time: dict[str, float] = {}

IDLE_TIMEOUT_SECONDS = 180  # 3 minutes


def evaluate_machine(m: Machine, expected_cycle_seconds: float):
    """
    Core ERP evaluation logic.  Call this on a schedule (every 15-30s).

    Args:
        m: Machine to evaluate
        expected_cycle_seconds: Target cycle time for the part currently running
    """
    try:
        metrics = get_metrics(m)
    except Exception as e:
        print(f"[{m.machine_id}] Cannot reach RPi: {e}")
        return

    last_cycle = metrics.get("last_cycle_seconds")
    now = time.time()

    # --- Track idle time ---
    if last_cycle is None:
        # No cycle data at all
        set_red(m)
        print(f"[{m.machine_id}] RED - No cycle data")
        return

    prev_value = _last_cycle_value.get(m.machine_id)
    if prev_value is None or last_cycle != prev_value:
        _last_new_cycle_time[m.machine_id] = now
    _last_cycle_value[m.machine_id] = last_cycle

    time_since_new = now - _last_new_cycle_time.get(m.machine_id, now)

    # --- CASE: Idle for 3+ minutes -> Red ---
    if time_since_new >= IDLE_TIMEOUT_SECONDS:
        set_red(m)
        print(f"[{m.machine_id}] RED - Idle {time_since_new:.0f}s")
        return

    # --- CASE: Cycle time above expected -> Amber ---
    if last_cycle > expected_cycle_seconds:
        set_amber(m)
        print(f"[{m.machine_id}] AMBER - {last_cycle:.1f}s > {expected_cycle_seconds:.1f}s")
        return

    # --- CASE: Cycle time at or below expected -> Green ---
    set_green(m)
    print(f"[{m.machine_id}] GREEN - {last_cycle:.1f}s <= {expected_cycle_seconds:.1f}s")


def evaluate_all(expected_cycle_times: dict[str, float]):
    """
    Evaluate all machines.

    Args:
        expected_cycle_times: {"M01": 45.0, "M02": 60.0, ...}
    """
    for m in MACHINES:
        expected = expected_cycle_times.get(m.machine_id)
        if expected is not None:
            evaluate_machine(m, expected)
```

#### Usage Examples

```python
# ── Single machine ──
m = MACHINES[0]

set_green(m)                          # Solid green
set_amber(m)                          # Solid amber
set_red(m)                            # Solid red

flash_amber(m)                        # Flash amber (default 0.5s)
flash_amber(m, interval=1.0)          # Flash amber slowly
flash_red(m, interval=0.3)            # Flash red fast
flash_light(m, amber=True, red=True)  # Flash amber + red together
stop_flash(m)                         # Stop flashing

all_off(m)                            # All lights off
test_sequence(m)                      # Run test (~8s)
get_status(m)                         # Get current state

# ── By group ──
set_group_light("low_bay", green=True, amber=False, red=False)  # Low bay green
set_group_light("high_bay", green=False, amber=False, red=True) # High bay red
flash_group("low_bay", amber=True)                              # Flash amber low bay
test_group("high_bay")                                          # Test high bay
all_off_group("low_bay")                                        # Off low bay

# ── All machines ──
set_all_light(green=True, amber=False, red=False)  # All green
flash_all(red=True, interval=0.3)                  # Flash red all
test_all()                                         # Test all
all_off_all()                                      # All off

# ── ERP evaluation loop ──
evaluate_all({"M01": 45.0, "M02": 60.0, "M03": 30.0, "M04": 90.0})
```

---

### C# / .NET -- ERP Integration

```csharp
using System.Net.Http.Json;

// ── Models ──────────────────────────────────────────────────

public record StackLightSetRequest(bool Green, bool Amber, bool Red);

public record StackLightFlashRequest(
    bool Green, bool Amber, bool Red, double Interval = 0.5);

public record StackLightState(
    bool Green, bool Amber, bool Red,
    bool Flashing, double? FlashInterval, string? LastUpdated);

public record StackLightResponse(
    bool Success, StackLightState? State,
    string? Message, string? Timestamp, string? Error);

public record MachineConfig(
    string MachineId, string IpAddress, int Port = 8443,
    string ApiKey = "", string Group = "", bool UseHttps = false);


// ── Client ──────────────────────────────────────────────────

public class StackLightClient : IDisposable
{
    private readonly HttpClient _http;

    public StackLightClient(HttpClient? http = null)
    {
        _http = http ?? new HttpClient();
        _http.Timeout = TimeSpan.FromSeconds(5);
    }

    private string BaseUrl(MachineConfig m) =>
        $"{(m.UseHttps ? "https" : "http")}://{m.IpAddress}:{m.Port}";

    private void SetKey(MachineConfig m)
    {
        _http.DefaultRequestHeaders.Remove("X-API-Key");
        _http.DefaultRequestHeaders.Add("X-API-Key", m.ApiKey);
    }

    // ── Solid light control ──

    public async Task<StackLightResponse?> SetLightAsync(
        MachineConfig m, bool green, bool amber, bool red)
    {
        SetKey(m);
        var resp = await _http.PostAsJsonAsync(
            $"{BaseUrl(m)}/stacklight/set",
            new StackLightSetRequest(green, amber, red));
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StackLightResponse>();
    }

    public Task<StackLightResponse?> SetGreenAsync(MachineConfig m) =>
        SetLightAsync(m, true, false, false);

    public Task<StackLightResponse?> SetAmberAsync(MachineConfig m) =>
        SetLightAsync(m, false, true, false);

    public Task<StackLightResponse?> SetRedAsync(MachineConfig m) =>
        SetLightAsync(m, false, false, true);

    // ── Flash control ──

    public async Task<StackLightResponse?> FlashAsync(
        MachineConfig m, bool green = false, bool amber = false,
        bool red = false, double interval = 0.5)
    {
        SetKey(m);
        var resp = await _http.PostAsJsonAsync(
            $"{BaseUrl(m)}/stacklight/flash",
            new StackLightFlashRequest(green, amber, red, interval));
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StackLightResponse>();
    }

    public Task<StackLightResponse?> FlashAmberAsync(
        MachineConfig m, double interval = 0.5) =>
        FlashAsync(m, amber: true, interval: interval);

    public Task<StackLightResponse?> FlashRedAsync(
        MachineConfig m, double interval = 0.5) =>
        FlashAsync(m, red: true, interval: interval);

    public async Task<StackLightResponse?> StopFlashAsync(MachineConfig m)
    {
        SetKey(m);
        var resp = await _http.PostAsync(
            $"{BaseUrl(m)}/stacklight/stop-flash", null);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StackLightResponse>();
    }

    // ── Other ──

    public async Task<StackLightResponse?> TurnOffAsync(MachineConfig m)
    {
        SetKey(m);
        var resp = await _http.PostAsync($"{BaseUrl(m)}/stacklight/off", null);
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StackLightResponse>();
    }

    public async Task<StackLightResponse?> TestAsync(MachineConfig m)
    {
        SetKey(m);
        _http.Timeout = TimeSpan.FromSeconds(15);
        var resp = await _http.PostAsync($"{BaseUrl(m)}/stacklight/test", null);
        resp.EnsureSuccessStatusCode();
        _http.Timeout = TimeSpan.FromSeconds(5);
        return await resp.Content.ReadFromJsonAsync<StackLightResponse>();
    }

    public async Task<StackLightState?> GetStatusAsync(MachineConfig m)
    {
        SetKey(m);
        var resp = await _http.GetAsync($"{BaseUrl(m)}/stacklight/status");
        resp.EnsureSuccessStatusCode();
        return await resp.Content.ReadFromJsonAsync<StackLightState>();
    }

    // ── Bulk helpers ──

    public async Task<Dictionary<string, StackLightResponse?>> SetGroupAsync(
        IEnumerable<MachineConfig> machines,
        bool green, bool amber, bool red)
    {
        var results = new Dictionary<string, StackLightResponse?>();
        foreach (var m in machines)
        {
            try { results[m.MachineId] = await SetLightAsync(m, green, amber, red); }
            catch (Exception ex) { results[m.MachineId] = new(false, null, ex.Message, null, ex.Message); }
        }
        return results;
    }

    public async Task<Dictionary<string, StackLightResponse?>> FlashGroupAsync(
        IEnumerable<MachineConfig> machines,
        bool green = false, bool amber = false,
        bool red = false, double interval = 0.5)
    {
        var results = new Dictionary<string, StackLightResponse?>();
        foreach (var m in machines)
        {
            try { results[m.MachineId] = await FlashAsync(m, green, amber, red, interval); }
            catch (Exception ex) { results[m.MachineId] = new(false, null, ex.Message, null, ex.Message); }
        }
        return results;
    }

    public async Task<Dictionary<string, StackLightResponse?>> TestGroupAsync(
        IEnumerable<MachineConfig> machines)
    {
        var results = new Dictionary<string, StackLightResponse?>();
        foreach (var m in machines)
        {
            try { results[m.MachineId] = await TestAsync(m); }
            catch (Exception ex) { results[m.MachineId] = new(false, null, ex.Message, null, ex.Message); }
        }
        return results;
    }

    public void Dispose() => _http.Dispose();
}
```

#### Usage Examples

```csharp
var machines = new List<MachineConfig>
{
    new("M01", "192.168.0.10", ApiKey: "key-m01", Group: "low_bay"),
    new("M02", "192.168.0.11", ApiKey: "key-m02", Group: "low_bay"),
    new("M03", "192.168.0.12", ApiKey: "key-m03", Group: "high_bay"),
};

using var client = new StackLightClient();

// Single machine
await client.SetGreenAsync(machines[0]);
await client.FlashAmberAsync(machines[0]);
await client.FlashRedAsync(machines[0], interval: 1.0);
await client.StopFlashAsync(machines[0]);
await client.TestAsync(machines[0]);

// Group
var lowBay = machines.Where(m => m.Group == "low_bay");
await client.SetGroupAsync(lowBay, green: true, amber: false, red: false);
await client.FlashGroupAsync(lowBay, amber: true, interval: 0.5);
await client.TestGroupAsync(lowBay);

// All machines
await client.SetGroupAsync(machines, green: false, amber: false, red: true);
await client.FlashGroupAsync(machines, red: true, interval: 0.3);
await client.TestGroupAsync(machines);
```

---

### PowerShell -- Bulk Operations

```powershell
# ── Machine Registry ────────────────────────────────────────
$Machines = @(
    @{ Id="M01"; Ip="192.168.0.10"; Port=8443; Key="key-m01"; Group="low_bay" }
    @{ Id="M02"; Ip="192.168.0.11"; Port=8443; Key="key-m02"; Group="low_bay" }
    @{ Id="M03"; Ip="192.168.0.12"; Port=8443; Key="key-m03"; Group="high_bay" }
    @{ Id="M04"; Ip="192.168.0.13"; Port=8443; Key="key-m04"; Group="high_bay" }
)

function Set-StackLight {
    param(
        [hashtable]$Machine,
        [bool]$Green = $false,
        [bool]$Amber = $false,
        [bool]$Red   = $false
    )
    $base = "http://$($Machine.Ip):$($Machine.Port)"
    $headers = @{ "X-API-Key" = $Machine.Key; "Content-Type" = "application/json" }
    $body = @{ green = $Green; amber = $Amber; red = $Red } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Uri "$base/stacklight/set" -Method POST `
            -Headers $headers -Body $body -TimeoutSec 5
        Write-Host "[$($Machine.Id)] Set: G=$Green A=$Amber R=$Red"
        return $resp
    } catch {
        Write-Warning "[$($Machine.Id)] FAILED: $_"
    }
}

function Start-StackLightFlash {
    param(
        [hashtable]$Machine,
        [bool]$Green    = $false,
        [bool]$Amber    = $false,
        [bool]$Red      = $false,
        [double]$Interval = 0.5
    )
    $base = "http://$($Machine.Ip):$($Machine.Port)"
    $headers = @{ "X-API-Key" = $Machine.Key; "Content-Type" = "application/json" }
    $body = @{ green = $Green; amber = $Amber; red = $Red; interval = $Interval } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod -Uri "$base/stacklight/flash" -Method POST `
            -Headers $headers -Body $body -TimeoutSec 5
        Write-Host "[$($Machine.Id)] Flashing: G=$Green A=$Amber R=$Red interval=${Interval}s"
        return $resp
    } catch {
        Write-Warning "[$($Machine.Id)] FAILED: $_"
    }
}

function Stop-StackLightFlash {
    param([hashtable]$Machine)
    $base = "http://$($Machine.Ip):$($Machine.Port)"
    $headers = @{ "X-API-Key" = $Machine.Key }
    Invoke-RestMethod -Uri "$base/stacklight/stop-flash" -Method POST `
        -Headers $headers -TimeoutSec 5
}

function Test-StackLight {
    param([hashtable]$Machine)
    $base = "http://$($Machine.Ip):$($Machine.Port)"
    $headers = @{ "X-API-Key" = $Machine.Key }
    Invoke-RestMethod -Uri "$base/stacklight/test" -Method POST `
        -Headers $headers -TimeoutSec 15
}

# ── Single machine ──────────────────────────────────────────
Set-StackLight -Machine $Machines[0] -Green $true
Start-StackLightFlash -Machine $Machines[0] -Amber $true -Interval 0.5
Stop-StackLightFlash -Machine $Machines[0]

# ── All machines to green ───────────────────────────────────
$Machines | ForEach-Object { Set-StackLight -Machine $_ -Green $true }

# ── All machines to red ─────────────────────────────────────
$Machines | ForEach-Object { Set-StackLight -Machine $_ -Red $true }

# ── Flash amber on "low_bay" group ──────────────────────────
$Machines | Where-Object { $_.Group -eq "low_bay" } |
    ForEach-Object { Start-StackLightFlash -Machine $_ -Amber $true }

# ── Flash red on "high_bay" group (slow) ────────────────────
$Machines | Where-Object { $_.Group -eq "high_bay" } |
    ForEach-Object { Start-StackLightFlash -Machine $_ -Red $true -Interval 1.0 }

# ── Test all machines in a group ────────────────────────────
$Machines | Where-Object { $_.Group -eq "low_bay" } |
    ForEach-Object { Test-StackLight -Machine $_ }

# ── Test ALL machines ───────────────────────────────────────
$Machines | ForEach-Object { Test-StackLight -Machine $_ }

# ── Turn off everything ─────────────────────────────────────
$Machines | ForEach-Object {
    $base = "http://$($_.Ip):$($_.Port)"
    $headers = @{ "X-API-Key" = $_.Key }
    Invoke-RestMethod -Uri "$base/stacklight/off" -Method POST `
        -Headers $headers -TimeoutSec 5
}
```

---

## Error Handling

| HTTP Status | Meaning | Action |
|-------------|---------|--------|
| `200` | Request processed | Check `success` field in response body |
| `403` | Invalid or missing API key | Verify `X-API-Key` header |
| `404` | Stack light disabled in config | RPi has `stacklight.enabled: false` |
| `422` | Invalid request body | Check field names/types (e.g., `interval` out of range) |
| `500` | GPIO or hardware error | Log and retry next cycle |
| Timeout | RPi unreachable | Network issue or Pi is down; skip and retry |

**Important**: A `200` response with `"success": false` means the API received the request but the GPIO operation failed. Always check the `success` field.

---

## Important Notes

1. **Only one light at a time** for standard operation -- set the other two to `false`
2. **Flash replaces solid** -- calling `/stacklight/flash` automatically stops any solid state
3. **Solid replaces flash** -- calling `/stacklight/set` automatically stops any active flash
4. **Idempotent** -- calling `set_green()` when already green is safe with no side effects
5. **No state memory** -- the RPi does not track "why" a light is on; your ERP owns all logic
6. **Flash interval range** -- minimum 0.1s (fast), maximum 5.0s (very slow), default 0.5s
7. **Test sequence is blocking** -- `/stacklight/test` takes ~8 seconds; use a 15s timeout
8. **GPIO pin mapping** -- Green=GPIO21, Amber=GPIO20, Red=GPIO26 (internal to the Pi, your ERP never needs this)
9. **Active-low relays** -- handled internally; `true` always means "ON" from the API
10. **Recommended polling interval** -- 15-30 seconds for the ERP evaluation loop
