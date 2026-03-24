#!/usr/bin/env python3
"""
Digilent Local Setup Verification

Checks that the WaveForms SDK is installed and a device is reachable.
Run this once before using the digilent-local skill with Claude Code.

Usage:
    python tools/digilent_local_setup.py
"""

import ctypes
import ctypes.util
import os
import platform
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_OK   = "\033[32m[OK]  \033[0m"
_WARN = "\033[33m[WARN]\033[0m"
_FAIL = "\033[31m[FAIL]\033[0m"

_issues: list[str] = []


def _check(label: str, ok: bool, detail: str = "", fix: str = "") -> bool:
    if ok:
        print(f"{_OK} {label}" + (f"  ({detail})" if detail else ""))
    else:
        print(f"{_FAIL} {label}" + (f"  ({detail})" if detail else ""))
        if fix:
            print(f"       → {fix}")
        _issues.append(label)
    return ok


def _warn(label: str, detail: str = "") -> None:
    print(f"{_WARN} {label}" + (f"  ({detail})" if detail else ""))


# ---------------------------------------------------------------------------
# 1. Python version
# ---------------------------------------------------------------------------
print("\n=== Digilent Local Setup Check ===\n")

ver = sys.version_info
_check(
    f"Python {ver.major}.{ver.minor}.{ver.micro}",
    ok=ver >= (3, 8),
    fix="Python 3.8 or newer is required",
)

# ---------------------------------------------------------------------------
# 2. Architecture (macOS Apple Silicon warning)
# ---------------------------------------------------------------------------
machine = platform.machine()
if sys.platform == "darwin" and machine == "arm64":
    # Check if WaveForms framework is also ARM
    fw = Path("/Library/Frameworks/dwf.framework/dwf")
    if fw.exists():
        try:
            import subprocess
            out = subprocess.check_output(["file", str(fw)], text=True)
            if "arm64" in out:
                _check("Apple Silicon + ARM WaveForms", ok=True, detail="native ARM")
            else:
                _check(
                    "Apple Silicon + ARM WaveForms",
                    ok=False,
                    detail="x86_64 framework detected with ARM Python",
                    fix="Install WaveForms ≥ 3.21.2 (universal binary) from digilent.com",
                )
        except Exception:
            _warn("Cannot determine WaveForms framework architecture")
    else:
        pass  # will be caught by library check below

# ---------------------------------------------------------------------------
# 3. DWF library loading
# ---------------------------------------------------------------------------
platform_paths = {
    "linux": [
        "/usr/lib/libdwf.so",
        "/usr/local/lib/libdwf.so",
        "/usr/lib/x86_64-linux-gnu/libdwf.so",
        "/usr/lib/aarch64-linux-gnu/libdwf.so",
    ],
    "darwin": [
        "/Library/Frameworks/dwf.framework/dwf",
        "/usr/local/lib/libdwf.dylib",
        "/opt/homebrew/lib/libdwf.dylib",
    ],
    "win32": [
        r"C:\Windows\System32\dwf.dll",
        r"C:\Program Files\Digilent\WaveFormsSDK\lib\x64\dwf.dll",
    ],
}
plat_key = "linux" if sys.platform.startswith("linux") else sys.platform
search_paths = platform_paths.get(plat_key, [])

lib = None
found_path = None

for path in search_paths:
    if os.path.exists(path):
        try:
            lib = ctypes.cdll.LoadLibrary(path)
            found_path = path
            break
        except OSError:
            pass

if lib is None:
    name = ctypes.util.find_library("dwf")
    if name:
        try:
            lib = ctypes.cdll.LoadLibrary(name)
            found_path = name
        except OSError:
            pass

_check(
    "WaveForms SDK (dwf library)",
    ok=lib is not None,
    detail=found_path or "not found",
    fix=(
        "Install WaveForms from https://digilent.com/reference/software/waveforms/waveforms-3/start\n"
        "       On Linux also install the Adept Runtime package."
    ),
)

# ---------------------------------------------------------------------------
# 4. Device enumeration
# ---------------------------------------------------------------------------
device_count = 0
device_name = None

if lib is not None:
    import ctypes
    count = ctypes.c_int()
    result = lib.FDwfEnum(ctypes.c_int(0), ctypes.byref(count))
    if result:
        device_count = count.value

    if device_count > 0:
        buf = (ctypes.c_char * 32)()
        lib.FDwfEnumDeviceName(ctypes.c_int(0), buf)
        device_name = buf.value.decode("utf-8", errors="replace").strip()

_check(
    f"Device detected ({device_count} found)" if device_count > 0 else "Device detected",
    ok=device_count > 0,
    detail=device_name or "",
    fix=(
        "Connect the Analog Discovery via USB, then re-run this check.\n"
        "       If WaveForms GUI is open, close it first (exclusive USB access)."
    ),
)

# ---------------------------------------------------------------------------
# 5. WaveForms GUI conflict warning
# ---------------------------------------------------------------------------
if device_count == 0 and lib is not None:
    # Try to get the last error message
    try:
        msg_buf = (ctypes.c_char * 512)()
        lib.FDwfGetLastErrorMsg(msg_buf)
        msg = msg_buf.value.decode("utf-8", errors="replace").strip()
        if "already" in msg.lower() or "open" in msg.lower():
            _warn("WaveForms GUI may be holding the device open", detail=msg)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if not _issues:
    print("✓  All checks passed.")
    print(f"\nStart the local server with:")
    print(f"    python tools/digilent_local_server.py\n")
else:
    print(f"✗  {len(_issues)} issue(s) need attention before the server can run.")
    print()
