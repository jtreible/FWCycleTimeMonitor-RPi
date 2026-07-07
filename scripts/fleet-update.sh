#!/bin/bash
# fleet-update.sh — Force every reachable cycle-monitor Pi to the latest code.
#
# This is the manual counterpart to the on-boot auto-updater. Use it to push the
# newest 'main' to Pis immediately, or to un-wedge a Pi that is stuck on old code
# (e.g. one whose working tree was edited in place). For each live Pi it:
#
#   1. cd /opt/fw-cycle-monitor && git fetch origin && git reset --hard origin/main
#      (hard reset, so a dirty working tree can never block the update)
#   2. restarts fw-cycle-monitor + fw-remote-supervisor, which re-runs the Debian 13
#      GPIO compatibility fix (gpio_fix.py) automatically on startup
#   3. verifies both services are active and reports the running commit
#
# It is idempotent — safe to re-run as each batch of Pis comes online.
#
# Usage:
#   PI_PASS='<pw>' bash fleet-update.sh                 # scan 192.168.3.4-254
#   PI_PASS='<pw>' bash fleet-update.sh 192.168.3.20-40 # scan an explicit range
#   PI_PASS='<pw>' bash fleet-update.sh 192.168.3.5      # a single Pi
#   PI_PASS='<pw>' bash fleet-update.sh --dry-run        # report versions, change nothing
#
# Auth:
#   - On Windows it connects with plink (PuTTY) using $PI_PASS (prompted if unset).
#   - Elsewhere it falls back to ssh with key auth (run setup-ssh-keys.sh first).
#   - Override the login user with PI_USER (default: fstre).

set -uo pipefail

PI_USER="${PI_USER:-fstre}"
DEFAULT_SUBNET="192.168.3"
DEFAULT_START=4
DEFAULT_END=254
PROBE_TIMEOUT=1        # seconds to wait on the TCP port-22 reachability probe
SSH_TIMEOUT=10         # seconds for the actual SSH command connect
BRANCH="main"

DRY_RUN=false
TARGET=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
        -*)        echo "Unknown option: $arg" >&2; exit 2 ;;
        *)         TARGET="$arg" ;;
    esac
done

# ---- Resolve the list of candidate IPs -------------------------------------
declare -a HOSTS=()
if [ -z "$TARGET" ]; then
    for i in $(seq "$DEFAULT_START" "$DEFAULT_END"); do HOSTS+=("${DEFAULT_SUBNET}.${i}"); done
elif [[ "$TARGET" == *-* ]]; then
    # e.g. 192.168.3.20-40  ->  net=192.168.3, start=20, end=40
    lhs="${TARGET%-*}"        # 192.168.3.20
    end="${TARGET#*-}"        # 40
    net="${lhs%.*}"           # 192.168.3
    start="${lhs##*.}"        # 20
    for i in $(seq "$start" "$end"); do HOSTS+=("${net}.${i}"); done
else
    HOSTS+=("$TARGET")                    # single IP/host
fi

# ---- Pick a transport ------------------------------------------------------
PLINK=""
for cand in "plink" "/c/Program Files/PuTTY/plink.exe" "/c/Program Files (x86)/PuTTY/plink.exe"; do
    if command -v "$cand" >/dev/null 2>&1 || [ -x "$cand" ]; then PLINK="$cand"; break; fi
done

USE_PLINK=false
if [ -n "$PLINK" ]; then
    USE_PLINK=true
    if [ -z "${PI_PASS:-}" ]; then
        read -rs -p "SSH password for ${PI_USER}@<pi> (same across fleet): " PI_PASS; echo
    fi
    if [ -z "${PI_PASS:-}" ]; then echo "No PI_PASS provided; aborting." >&2; exit 2; fi
fi

run_remote() {  # run_remote <ip> <command-string>
    local ip="$1" cmd="$2"
    if $USE_PLINK; then
        # `echo y` accepts an uncached host key on first contact; harmless once cached.
        echo y | "$PLINK" -ssh -pw "$PI_PASS" "${PI_USER}@${ip}" "$cmd" 2>&1
    else
        ssh -o ConnectTimeout="$SSH_TIMEOUT" -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes "${PI_USER}@${ip}" "$cmd" 2>&1
    fi
}

port_open() { timeout "$PROBE_TIMEOUT" bash -c ">/dev/tcp/$1/22" >/dev/null 2>&1; }

# ---- Remote work -----------------------------------------------------------
UPDATE_CMD='
set -e
cd /opt/fw-cycle-monitor
sudo systemctl stop fw-cycle-monitor fw-remote-supervisor 2>/dev/null || true
git fetch origin --quiet
git reset --hard origin/'"$BRANCH"' --quiet
sudo systemctl start fw-cycle-monitor 2>/dev/null || true
sudo systemctl start fw-remote-supervisor 2>/dev/null || true
sleep 8
echo "HEAD=$(git rev-parse --short HEAD)"
echo "cycle-monitor=$(systemctl is-active fw-cycle-monitor 2>/dev/null)"
echo "remote-supervisor=$(systemctl is-active fw-remote-supervisor 2>/dev/null)"
'

DRYRUN_CMD='
cd /opt/fw-cycle-monitor 2>/dev/null || { echo "NO-REPO"; exit 0; }
git fetch origin --quiet 2>/dev/null || { echo "FETCH-FAILED"; exit 0; }
d=no; [ -n "$(git status --porcelain)" ] && d=yes
echo "local=$(git rev-parse --short HEAD) remote=$(git rev-parse --short origin/'"$BRANCH"') dirty=$d"
'

# ---- Drive ------------------------------------------------------------------
TOTAL=0; OK=0; FAIL=0; declare -a FAILED=()
echo "=================================================="
echo " FW Cycle Monitor — Fleet Code Update"
echo " Candidates: ${#HOSTS[@]}   User: ${PI_USER}   $($DRY_RUN && echo '[DRY RUN]')"
echo " Transport:  $($USE_PLINK && echo plink || echo ssh)"
echo "=================================================="

for ip in "${HOSTS[@]}"; do
    port_open "$ip" || continue          # skip anything not answering on :22 fast
    TOTAL=$((TOTAL+1))
    printf ">>> %-15s " "$ip"
    if $DRY_RUN; then
        out="$(run_remote "$ip" "$DRYRUN_CMD")"
        echo "$out" | tr '\n' ' '; echo
        OK=$((OK+1))
        continue
    fi
    out="$(run_remote "$ip" "$UPDATE_CMD")"
    head_line="$(echo "$out" | grep '^HEAD=' | cut -d= -f2)"
    cyc="$(echo "$out" | grep '^cycle-monitor=' | cut -d= -f2)"
    sup="$(echo "$out" | grep '^remote-supervisor=' | cut -d= -f2)"
    if [ "$cyc" = "active" ]; then
        echo "OK   HEAD=$head_line  cycle-monitor=$cyc  remote-supervisor=${sup:-n/a}"
        OK=$((OK+1))
    else
        echo "FAIL cycle-monitor=${cyc:-unreachable}"
        echo "$out" | sed 's/^/        | /' | tail -6
        FAIL=$((FAIL+1)); FAILED+=("$ip")
    fi
done

echo "=================================================="
echo " Reachable: $TOTAL   OK: $OK   Failed: $FAIL"
if [ "${#FAILED[@]}" -gt 0 ]; then
    printf ' Failed:'; printf ' %s' "${FAILED[@]}"; echo
    exit 1
fi
echo "=================================================="
