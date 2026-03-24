#!/usr/bin/env python3
"""
Digilent Loopback Test

Generates a sine wave on W1 (Wavegen CH1) and measures it on CH1 (Scope).
Verifies that frequency, amplitude, and DC offset match the configured values.

Wiring:
    W1  →  CH1+
    GND →  CH1-  (or any GND pin)

Usage:
    python tests/loopback_test.py
    python tests/loopback_test.py --freq 5000 --amplitude 1.0
    python tests/loopback_test.py --url http://127.0.0.1:7272
"""

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class LoopbackConfig:
    url: str = "http://127.0.0.1:7272"
    wavegen_channel: int = 1
    scope_channel: int = 1
    freq_hz: float = 1000.0
    amplitude_v: float = 1.5       # half-amplitude (→ 3 Vpp)
    offset_v: float = 0.0
    freq_tolerance_pct: float = 2.0
    vpp_tolerance_pct: float = 10.0
    vavg_tolerance_v: float = 0.1
    scope_range_v: float = 5.0
    scope_sample_rate_hz: int = 200_000
    scope_duration_ms: int = 30     # ≥ 20 periods at 1 kHz
    settle_ms: int = 50             # wait for wavegen to stabilise


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, no requests dependency)
# ---------------------------------------------------------------------------

def _call(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())
    except urllib.error.URLError as exc:
        print(f"\n  [ERROR] Cannot reach server at {url}")
        print(f"          {exc.reason}")
        print(f"          → Start the server first: python tools/digilent_local_server.py")
        sys.exit(1)


def get(base: str, path: str) -> dict:
    return _call(f"{base}{path}")


def post(base: str, path: str, body: dict) -> dict:
    return _call(f"{base}{path}", method="POST", body=body)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_WARN = "\033[33mWARN\033[0m"

failures: list[str] = []


def check(label: str, measured, expected, tolerance, unit: str = "") -> bool:
    if measured is None:
        print(f"  {_WARN}  {label}: no measurement")
        return False

    if isinstance(tolerance, float) and tolerance < 1.0:
        # absolute tolerance
        ok = abs(measured - expected) <= tolerance
        detail = f"{measured:.4f}{unit}  (expected {expected:.4f}±{tolerance}{unit})"
    else:
        # percentage tolerance
        ok = abs(measured - expected) / max(abs(expected), 1e-9) * 100 <= tolerance
        detail = f"{measured:.4f}{unit}  (expected {expected:.4f}±{tolerance}%{unit})"

    tag = _PASS if ok else _FAIL
    print(f"  {tag}  {label}: {detail}")
    if not ok:
        failures.append(label)
    return ok


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def run(cfg: LoopbackConfig) -> int:
    print("\n=== Digilent Loopback Test ===\n")
    print(f"Server : {cfg.url}")
    print(f"Wiring : W{cfg.wavegen_channel} → CH{cfg.scope_channel}+  |  GND → CH{cfg.scope_channel}-")
    print(f"Signal : {cfg.freq_hz:.0f} Hz sine, {cfg.amplitude_v * 2:.2f} Vpp, "
          f"offset {cfg.offset_v:.2f} V\n")

    # ------------------------------------------------------------------
    # 1. Ping
    # ------------------------------------------------------------------
    print("[ 1/5 ] Server ping ...")
    ping = get(cfg.url, "/api/digilent/ping")
    if not ping.get("ok"):
        print(f"  {_FAIL}  Server not responding correctly: {ping}")
        return 1
    print(f"  {_PASS}  {ping.get('server', 'ok')}")

    # ------------------------------------------------------------------
    # 2. Device status
    # ------------------------------------------------------------------
    print("[ 2/5 ] Device status ...")
    status = get(cfg.url, "/api/digilent/status")

    if not status.get("device_present"):
        print(f"  {_FAIL}  No device detected. Connect the Analog Discovery and retry.")
        return 1

    if not status.get("device_open"):
        print("  Opening device ...")
        post(cfg.url, "/api/digilent/device/open", {})
        status = get(cfg.url, "/api/digilent/status")

    if status.get("state") != "idle":
        print(f"  {_FAIL}  Device state is '{status.get('state')}', expected 'idle'.")
        return 1

    name = status.get("device_name", "unknown")
    temp = status.get("temperature_c")
    temp_str = f", {temp} °C" if temp is not None else ""
    print(f"  {_PASS}  {name}{temp_str}")

    # ------------------------------------------------------------------
    # 3. Start wavegen
    # ------------------------------------------------------------------
    print("[ 3/5 ] Starting wavegen ...")
    wg = post(cfg.url, "/api/digilent/wavegen/set", {
        "channel": cfg.wavegen_channel,
        "waveform": "sine",
        "frequency_hz": cfg.freq_hz,
        "amplitude_v": cfg.amplitude_v,
        "offset_v": cfg.offset_v,
        "symmetry_percent": 50,
        "enable": True,
    })
    if not wg.get("ok"):
        print(f"  {_FAIL}  Wavegen error: {wg.get('error', wg)}")
        return 1
    print(f"  {_PASS}  Wavegen CH{cfg.wavegen_channel} running")

    time.sleep(cfg.settle_ms / 1000)

    # ------------------------------------------------------------------
    # 4. Scope capture
    # ------------------------------------------------------------------
    print("[ 4/5 ] Scope capture ...")
    try:
        meas = post(cfg.url, "/api/digilent/scope/measure", {
            "channels": [cfg.scope_channel],
            "range_v": cfg.scope_range_v,
            "offset_v": 0.0,
            "sample_rate_hz": cfg.scope_sample_rate_hz,
            "duration_ms": cfg.scope_duration_ms,
            "trigger": {
                "enabled": True,
                "source": f"ch{cfg.scope_channel}",
                "edge": "rising",
                "level_v": cfg.offset_v,
                "timeout_ms": 2000,
            },
        })
    except Exception as exc:
        print(f"  {_FAIL}  Scope request failed: {exc}")
        post(cfg.url, "/api/digilent/wavegen/stop", {"channel": cfg.wavegen_channel})
        return 1

    if not meas.get("ok"):
        err = meas.get("error", {})
        print(f"  {_FAIL}  Scope error [{err.get('code')}]: {err.get('message')}")
        post(cfg.url, "/api/digilent/wavegen/stop", {"channel": cfg.wavegen_channel})
        return 1

    m = meas.get("metrics", {}).get(f"ch{cfg.scope_channel}", {})
    print(f"  {_PASS}  Captured  ({meas.get('duration_ms', '?')} ms)\n")

    # ------------------------------------------------------------------
    # 5. Validate results
    # ------------------------------------------------------------------
    print("[ 5/5 ] Validation\n")

    expected_vpp = cfg.amplitude_v * 2
    check("Frequency", m.get("freq_est_hz"), cfg.freq_hz,
          cfg.freq_tolerance_pct, " Hz")
    check("Vpp      ", m.get("vpp"),        expected_vpp,
          cfg.vpp_tolerance_pct, " V")
    check("Vavg     ", m.get("vavg"),       cfg.offset_v,
          cfg.vavg_tolerance_v, " V")

    print(f"\n  Vmin={m.get('vmin', '?'):.4f} V  "
          f"Vmax={m.get('vmax', '?'):.4f} V  "
          f"Vrms={m.get('vrms', '?'):.4f} V")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    print()
    post(cfg.url, "/api/digilent/wavegen/stop", {"channel": cfg.wavegen_channel})
    print("Wavegen stopped.\n")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    if failures:
        print(f"Result : {_FAIL}  {len(failures)} check(s) failed: {', '.join(failures)}")
        print("         Check wiring: W1 → CH1+  and  GND → CH1-\n")
        return 1
    else:
        print(f"Result : {_PASS}  All checks passed.\n")
        return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Digilent loopback test")
    parser.add_argument("--url", default="http://127.0.0.1:7272",
                        help="Server URL (default: http://127.0.0.1:7272)")
    parser.add_argument("--freq", type=float, default=1000.0,
                        help="Sine frequency in Hz (default: 1000)")
    parser.add_argument("--amplitude", type=float, default=1.5,
                        help="Half-amplitude in V, i.e. Vpp/2 (default: 1.5 → 3 Vpp)")
    parser.add_argument("--offset", type=float, default=0.0,
                        help="DC offset in V (default: 0.0)")
    parser.add_argument("--freq-tolerance", type=float, default=2.0,
                        help="Frequency tolerance in %% (default: 2.0)")
    args = parser.parse_args()

    cfg = LoopbackConfig(
        url=args.url,
        freq_hz=args.freq,
        amplitude_v=args.amplitude,
        offset_v=args.offset,
        freq_tolerance_pct=args.freq_tolerance,
        scope_range_v=max(5.0, args.amplitude * 2 * 1.5),
    )
    sys.exit(run(cfg))


if __name__ == "__main__":
    main()
