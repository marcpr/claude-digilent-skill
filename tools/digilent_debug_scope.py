#!/usr/bin/env python3
"""
Minimal scope debug script — calls DWF directly, prints every status transition.
Run while W1 is wired to CH1 (or leave unwired for free-running test).
"""
import ctypes, sys, time
from ctypes import byref, c_bool, c_char, c_double, c_int, c_ubyte

# --- load library ---
for path in ["/usr/lib/libdwf.so", "/usr/local/lib/libdwf.so"]:
    try:
        lib = ctypes.cdll.LoadLibrary(path)
        print(f"[OK] Loaded {path}")
        break
    except OSError:
        pass
else:
    sys.exit("[FAIL] libdwf.so not found")

STATE_NAMES = {0: "Ready", 1: "Armed", 2: "Done", 3: "Triggered/Running",
               4: "Config", 5: "Prefill", 7: "Wait"}

def check(r, op):
    if not r:
        buf = (c_char * 512)()
        lib.FDwfGetLastErrorMsg(buf)
        print(f"[ERR] {op}: {buf.value.decode().strip()}")
        sys.exit(1)

# --- open device ---
hdwf = c_int()
check(lib.FDwfDeviceOpen(c_int(-1), byref(hdwf)), "DeviceOpen")
print(f"[OK] Device opened (hdwf={hdwf.value})")

def run_test(label, use_trigger):
    print(f"\n--- {label} ---")
    lib.FDwfAnalogInReset(hdwf)

    lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(0), c_bool(False))
    lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(1), c_bool(False))
    check(lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(0), c_bool(True)), "EnableSet CH1")
    check(lib.FDwfAnalogInChannelRangeSet(hdwf, c_int(0), c_double(5.0)), "RangeSet")
    check(lib.FDwfAnalogInChannelOffsetSet(hdwf, c_int(0), c_double(0.0)), "OffsetSet")
    check(lib.FDwfAnalogInFrequencySet(hdwf, c_double(100_000)), "FreqSet 100kHz")
    check(lib.FDwfAnalogInBufferSizeSet(hdwf, c_int(1000)), "BufSizeSet 1000")
    check(lib.FDwfAnalogInAcquisitionModeSet(hdwf, c_int(1)), "AcqMode Single")

    if use_trigger:
        check(lib.FDwfAnalogInTriggerSourceSet(hdwf, c_int(2)), "TrigSrc=DetAnalogIn")
        check(lib.FDwfAnalogInTriggerAutoTimeoutSet(hdwf, c_double(3.0)), "AutoTimeout=3s")
        check(lib.FDwfAnalogInTriggerChannelSet(hdwf, c_int(0)), "TrigCh=0")
        check(lib.FDwfAnalogInTriggerConditionSet(hdwf, c_int(0)), "TrigCond=Rise")
        check(lib.FDwfAnalogInTriggerLevelSet(hdwf, c_double(0.0)), "TrigLevel=0V")
    else:
        check(lib.FDwfAnalogInTriggerSourceSet(hdwf, c_int(0)), "TrigSrc=None")

    print("Calling Configure(reconfigure=True, start=True)...")
    check(lib.FDwfAnalogInConfigure(hdwf, c_bool(True), c_bool(True)), "Configure")

    sts = c_ubyte()
    prev = None
    deadline = time.monotonic() + 5.0
    n = 0
    while time.monotonic() < deadline:
        r = lib.FDwfAnalogInStatus(hdwf, c_bool(True), byref(sts))
        if not r:
            buf = (c_char * 512)()
            lib.FDwfGetLastErrorMsg(buf)
            print(f"  [ERR] Status call failed: {buf.value.decode().strip()}")
            break
        s = sts.value
        name = STATE_NAMES.get(s, f"Unknown({s})")
        if s != prev:
            print(f"  t={time.monotonic()-deadline+5:.3f}s  state → {s} ({name})")
            prev = s
        if s == 2:  # Done
            print("  [OK] Capture complete!")
            break
        n += 1
        time.sleep(0.01)
    else:
        print(f"  [TIMEOUT] Last state: {prev} ({STATE_NAMES.get(prev, '?')})")

run_test("FREE-RUNNING (trigsrcNone)", use_trigger=False)
run_test("TRIGGERED (trigsrcDetAnalogIn, timeout=3s)", use_trigger=True)

lib.FDwfDeviceClose(hdwf)
print("\n[OK] Device closed")
