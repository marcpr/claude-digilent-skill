"""
Thin ctypes wrapper around the Digilent WaveForms SDK.

Supports Linux (x86-64, ARM), macOS (Intel + Apple Silicon), and Windows.

All DWF library calls are confined to this module. Higher-level services
must not call libdwf functions directly.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from ctypes import byref, c_bool, c_char, c_double, c_int, c_ubyte, c_uint

from .capability_registry import DeviceEnumInfo
from .errors import DigilentNotFoundError, DigilentTransportError

# ---------------------------------------------------------------------------
# Library loading
# ---------------------------------------------------------------------------

_lib: ctypes.CDLL | None = None
_lib_error: str | None = None

HDWF_NONE = c_int(-1)
HDWF = c_int

# ---------------------------------------------------------------------------
# FDwfEnumConfigInfo DECI type constants (WaveForms SDK §14)
# ---------------------------------------------------------------------------

DECI_ANALOG_IN_CHANNEL_COUNT = 1
DECI_ANALOG_OUT_CHANNEL_COUNT = 2
DECI_ANALOG_IO_CHANNEL_COUNT = 3
DECI_DIGITAL_IN_CHANNEL_COUNT = 4
DECI_DIGITAL_OUT_CHANNEL_COUNT = 5
DECI_DIGITAL_IO_CHANNEL_COUNT = 6
DECI_ANALOG_IN_BUFFER_SIZE = 7
DECI_ANALOG_OUT_BUFFER_SIZE = 8
DECI_DIGITAL_IN_BUFFER_SIZE = 9
DECI_DIGITAL_OUT_BUFFER_SIZE = 10

_ACQMODE_SINGLE = c_int(1)
_TRIGSRC_NONE = c_int(0)
_TRIGSRC_PC = c_int(1)
_TRIGSRC_DET_ANALOG_IN = c_int(2)
_TRIGSRC_DET_DIGITAL_IN = c_int(3)
_SLOPE_RISE = c_int(0)
_SLOPE_FALL = c_int(1)
_SLOPE_EITHER = c_int(2)

# Trigger types (FDwfAnalogInTriggerTypeSet)
_TRIGTYPE_EDGE = c_int(0)
_TRIGTYPE_PULSE = c_int(1)
_TRIGTYPE_TRANSITION = c_int(2)
_TRIGTYPE_WINDOW = c_int(3)
_TRIGTYPE_MAP: dict[str, c_int] = {
    "edge": _TRIGTYPE_EDGE,
    "pulse": _TRIGTYPE_PULSE,
    "transition": _TRIGTYPE_TRANSITION,
    "window": _TRIGTYPE_WINDOW,
}

# Channel filter types (FDwfAnalogInChannelFilterSet)
_FILTER_DECIMATE = c_int(0)
_FILTER_AVERAGE = c_int(1)
_FILTER_MINMAX = c_int(2)
_FILTER_MAP: dict[str, c_int] = {
    "none": _FILTER_DECIMATE,
    "decimate": _FILTER_DECIMATE,
    "average": _FILTER_AVERAGE,
    "minmax": _FILTER_MINMAX,
}

# Waveform function codes (FDwfAnalogOutNodeFunctionSet)
_FUNC_DC = c_ubyte(0)
_FUNC_SINE = c_ubyte(1)
_FUNC_SQUARE = c_ubyte(2)
_FUNC_TRIANGLE = c_ubyte(3)
_FUNC_RAMPUP = c_ubyte(4)
_FUNC_RAMPDOWN = c_ubyte(5)
_FUNC_NOISE = c_ubyte(6)
_FUNC_CUSTOM = c_ubyte(30)   # funcCustom in WaveForms SDK

# Modulation types and nodes
_MOD_AM = c_int(1)
_MOD_FM = c_int(2)
_MOD_MAP: dict[str, c_int] = {"am": _MOD_AM, "fm": _MOD_FM}
_NODE_CARRIER = c_int(0)
_NODE_AM = c_int(1)
_NODE_FM = c_int(2)

_ENUMFILTER_ALL = c_int(0)
_STATE_DONE = c_ubyte(2)
_DIG_FORMAT_16 = c_int(16)


def _platform_search_paths() -> list[str]:
    paths = [
        # Linux (Pi ARM + x86-64)
        "/usr/lib/libdwf.so",
        "/usr/local/lib/libdwf.so",
        "/usr/lib/x86_64-linux-gnu/libdwf.so",
        "/usr/lib/aarch64-linux-gnu/libdwf.so",
        "/usr/lib/arm-linux-gnueabihf/libdwf.so",
    ]
    if sys.platform == "darwin":
        paths += [
            "/Library/Frameworks/dwf.framework/dwf",
            "/usr/local/lib/libdwf.dylib",
            "/opt/homebrew/lib/libdwf.dylib",
        ]
    elif sys.platform == "win32":
        paths += [
            r"C:\Windows\System32\dwf.dll",
            r"C:\Program Files\Digilent\WaveFormsSDK\lib\x64\dwf.dll",
        ]
    return paths


def _load_lib() -> ctypes.CDLL:
    """Load the DWF library, raising DigilentTransportError if not found."""
    global _lib, _lib_error
    if _lib is not None:
        return _lib
    if _lib_error is not None:
        raise DigilentTransportError(_lib_error)

    for path in _platform_search_paths():
        if os.path.exists(path):
            try:
                _lib = ctypes.cdll.LoadLibrary(path)
                return _lib
            except OSError as exc:
                _lib_error = f"Failed to load {path}: {exc}"

    name = ctypes.util.find_library("dwf")
    if name:
        try:
            _lib = ctypes.cdll.LoadLibrary(name)
            return _lib
        except OSError as exc:
            _lib_error = f"Failed to load {name}: {exc}"

    install_url = "https://digilent.com/reference/software/waveforms/waveforms-3/start"
    _lib_error = (
        f"WaveForms SDK (dwf library) not found on {sys.platform}. "
        f"Install WaveForms from {install_url}"
    )
    raise DigilentTransportError(_lib_error)


def _check(result, op: str) -> None:
    val = result if isinstance(result, int) else bool(result)
    if not val:
        lib = _load_lib()
        msg_buf = (c_char * 512)()
        lib.FDwfGetLastErrorMsg(msg_buf)
        msg = msg_buf.value.decode("utf-8", errors="replace").strip()
        raise DigilentTransportError(f"DWF call failed [{op}]: {msg}")


# ---------------------------------------------------------------------------
# Device enumeration and lifecycle
# ---------------------------------------------------------------------------

def enumerate_devices() -> int:
    lib = _load_lib()
    count = c_int()
    _check(lib.FDwfEnum(_ENUMFILTER_ALL, byref(count)), "FDwfEnum")
    return count.value


def get_device_name(idx: int) -> str:
    lib = _load_lib()
    buf = (c_char * 32)()
    _check(lib.FDwfEnumDeviceName(c_int(idx), buf), "FDwfEnumDeviceName")
    return buf.value.decode("utf-8", errors="replace").strip()


def get_device_type(idx: int) -> tuple[int, int]:
    """Return (devid, devver) for the device at enumeration index *idx*."""
    lib = _load_lib()
    devid, devver = c_int(), c_int()
    _check(lib.FDwfEnumDeviceType(c_int(idx), byref(devid), byref(devver)), "FDwfEnumDeviceType")
    return devid.value, devver.value


def get_device_sn(idx: int) -> str:
    """Return the serial-number string for the device at enumeration index *idx*."""
    lib = _load_lib()
    buf = (c_char * 32)()
    _check(lib.FDwfEnumSN(c_int(idx), buf), "FDwfEnumSN")
    return buf.value.decode("utf-8", errors="replace").strip()


def get_device_is_opened(idx: int) -> bool:
    """Return True if the device at *idx* is already opened by another process."""
    lib = _load_lib()
    is_open = c_int()
    _check(lib.FDwfEnumDeviceIsOpened(c_int(idx), byref(is_open)), "FDwfEnumDeviceIsOpened")
    return bool(is_open.value)


def get_enum_config_count(device_idx: int) -> int:
    """Return the number of configurations available for the device at *device_idx*."""
    lib = _load_lib()
    count = c_int()
    _check(lib.FDwfEnumConfig(c_int(device_idx), byref(count)), "FDwfEnumConfig")
    return count.value


def get_enum_config_info(device_idx: int, cfg_idx: int, info_type: int) -> int:
    """Return one DECI_* value for configuration *cfg_idx* of device *device_idx*."""
    lib = _load_lib()
    val = c_int()
    _check(
        lib.FDwfEnumConfigInfo(c_int(cfg_idx), c_int(info_type), byref(val)),
        "FDwfEnumConfigInfo",
    )
    return val.value


def enumerate_devices_full() -> list[DeviceEnumInfo]:
    """Call FDwfEnum and return a DeviceEnumInfo for every discovered device."""
    lib = _load_lib()
    count = c_int()
    _check(lib.FDwfEnum(_ENUMFILTER_ALL, byref(count)), "FDwfEnum")

    devices: list[DeviceEnumInfo] = []
    for idx in range(count.value):
        devid, devver = get_device_type(idx)
        name = get_device_name(idx)
        sn = get_device_sn(idx)
        is_open = get_device_is_opened(idx)
        devices.append(DeviceEnumInfo(
            idx=idx,
            devid=devid,
            devver=devver,
            name=name,
            sn=sn,
            is_open=is_open,
        ))
    return devices


def open_device(idx: int = -1) -> c_int:
    lib = _load_lib()
    hdwf = c_int()
    result = lib.FDwfDeviceOpen(c_int(idx), byref(hdwf))
    if not result or hdwf.value == HDWF_NONE.value:
        msg_buf = (c_char * 512)()
        lib.FDwfGetLastErrorMsg(msg_buf)
        msg = msg_buf.value.decode("utf-8", errors="replace").strip()
        raise DigilentNotFoundError(
            f"No WaveForms device found (idx={idx}). "
            f"Ensure the device is connected and WaveForms GUI is closed. DWF: {msg}"
        )
    return hdwf


def close_device(hdwf: c_int) -> None:
    if hdwf.value == HDWF_NONE.value:
        return
    try:
        lib = _load_lib()
        lib.FDwfDeviceClose(hdwf)
    except DigilentTransportError:
        pass


def read_temperature(hdwf: c_int) -> float | None:
    try:
        lib = _load_lib()
        temp = c_double()
        for ch in range(4):
            result = lib.FDwfAnalogIOChannelNodeGet(hdwf, c_int(ch), c_int(0), byref(temp))
            if result:
                t = temp.value
                if -40.0 <= t <= 125.0:
                    return round(t, 1)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Oscilloscope (AnalogIn)
# ---------------------------------------------------------------------------

def scope_sample_raw(
    hdwf: c_int,
    channels: list[int],
    range_v: float,
    offset_v: float,
) -> dict[int, float]:
    """Read one instantaneous sample per channel via FDwfAnalogInStatusSample."""
    import time
    lib = _load_lib()

    lib.FDwfAnalogInReset(hdwf)
    for ch in (0, 1, 2, 3):
        lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(ch), c_bool(False))

    for ch in channels:
        idx = ch - 1
        _check(lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(idx), c_bool(True)), "ChannelEnableSet")
        _check(lib.FDwfAnalogInChannelRangeSet(hdwf, c_int(idx), c_double(range_v)), "ChannelRangeSet")
        _check(lib.FDwfAnalogInChannelOffsetSet(hdwf, c_int(idx), c_double(offset_v)), "ChannelOffsetSet")

    _check(lib.FDwfAnalogInTriggerSourceSet(hdwf, _TRIGSRC_NONE), "TriggerSourceSet(none)")
    _check(lib.FDwfAnalogInAcquisitionModeSet(hdwf, _ACQMODE_SINGLE), "AcquisitionModeSet")
    _check(lib.FDwfAnalogInBufferSizeSet(hdwf, c_int(1)), "BufferSizeSet")
    _check(lib.FDwfAnalogInConfigure(hdwf, c_bool(True), c_bool(True)), "Configure")

    # Wait briefly for acquisition
    time.sleep(0.01)
    sts = c_ubyte()
    _check(lib.FDwfAnalogInStatus(hdwf, c_bool(True), byref(sts)), "Status")

    result: dict[int, float] = {}
    for ch in channels:
        val = c_double()
        _check(lib.FDwfAnalogInStatusSample(hdwf, c_int(ch - 1), byref(val)), "StatusSample")
        result[ch] = round(val.value, 6)
    return result


def scope_capture_raw(
    hdwf: c_int,
    channels: list[int],
    range_v: float,
    offset_v: float,
    sample_rate_hz: float,
    n_samples: int,
    trigger_source: str,
    trigger_edge: str,
    trigger_channel: int,
    trigger_level_v: float,
    trigger_timeout_s: float,
    filter: str = "none",
    trigger_type: str = "edge",
) -> dict[int, list[float]]:
    import time
    lib = _load_lib()

    # Reset to clear any stuck state from a previous timed-out capture
    lib.FDwfAnalogInReset(hdwf)

    for ch in (0, 1):
        lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(ch), c_bool(False))

    filter_val = _FILTER_MAP.get(filter, _FILTER_DECIMATE)
    for ch in channels:
        idx = ch - 1
        _check(lib.FDwfAnalogInChannelEnableSet(hdwf, c_int(idx), c_bool(True)), "ChannelEnableSet")
        _check(lib.FDwfAnalogInChannelRangeSet(hdwf, c_int(idx), c_double(range_v)), "ChannelRangeSet")
        _check(lib.FDwfAnalogInChannelOffsetSet(hdwf, c_int(idx), c_double(offset_v)), "ChannelOffsetSet")
        if filter != "none":
            lib.FDwfAnalogInChannelFilterSet(hdwf, c_int(idx), filter_val)

    _check(lib.FDwfAnalogInFrequencySet(hdwf, c_double(sample_rate_hz)), "FrequencySet")
    _check(lib.FDwfAnalogInBufferSizeSet(hdwf, c_int(n_samples)), "BufferSizeSet")
    _check(lib.FDwfAnalogInAcquisitionModeSet(hdwf, _ACQMODE_SINGLE), "AcquisitionModeSet")

    if trigger_source == "none":
        # trigsrcNone (0): acquisition fires immediately after Configure, no trigger needed
        _check(lib.FDwfAnalogInTriggerSourceSet(hdwf, _TRIGSRC_NONE), "TriggerSourceSet(none)")
    else:
        _check(lib.FDwfAnalogInTriggerSourceSet(hdwf, _TRIGSRC_DET_ANALOG_IN), "TriggerSourceSet(det)")
        _check(lib.FDwfAnalogInTriggerAutoTimeoutSet(hdwf, c_double(trigger_timeout_s)), "TriggerAutoTimeoutSet")
        _check(lib.FDwfAnalogInTriggerChannelSet(hdwf, c_int(trigger_channel - 1)), "TriggerChannelSet")
        ttype_val = _TRIGTYPE_MAP.get(trigger_type, _TRIGTYPE_EDGE)
        lib.FDwfAnalogInTriggerTypeSet(hdwf, ttype_val)
        edge_val = {"rising": _SLOPE_RISE, "falling": _SLOPE_FALL, "either": _SLOPE_EITHER}.get(
            trigger_edge, _SLOPE_RISE
        )
        _check(lib.FDwfAnalogInTriggerConditionSet(hdwf, edge_val), "TriggerConditionSet")
        _check(lib.FDwfAnalogInTriggerLevelSet(hdwf, c_double(trigger_level_v)), "TriggerLevelSet")

    # fReconfigure=True applies all staged settings; fStart=True begins acquisition
    _check(lib.FDwfAnalogInConfigure(hdwf, c_bool(True), c_bool(True)), "Configure")

    # Poll until n_samples are valid or state reaches Done.
    # Note: on some SDK versions the state stays at 3 (Running) throughout single
    # acquisition and never transitions to Done (2). Checking samples_valid is the
    # reliable cross-version completion test.
    deadline = time.monotonic() + trigger_timeout_s
    sts = c_ubyte()
    samples_valid = c_int()
    while time.monotonic() < deadline:
        _check(lib.FDwfAnalogInStatus(hdwf, c_bool(True), byref(sts)), "Status")
        lib.FDwfAnalogInStatusSamplesValid(hdwf, byref(samples_valid))
        if samples_valid.value >= n_samples or sts.value == _STATE_DONE.value:
            break
        time.sleep(0.005)
    else:
        lib.FDwfAnalogInReset(hdwf)
        from .errors import DigilentCaptureTimeoutError
        raise DigilentCaptureTimeoutError("Scope capture timed out")

    result: dict[int, list[float]] = {}
    for ch in channels:
        buf = (c_double * n_samples)()
        _check(lib.FDwfAnalogInStatusData(hdwf, c_int(ch - 1), buf, c_int(n_samples)), "StatusData")
        result[ch] = list(buf)

    return result


# ---------------------------------------------------------------------------
# Logic Analyzer (DigitalIn)
# ---------------------------------------------------------------------------

def logic_capture_raw(
    hdwf: c_int,
    channels: list[int],
    sample_rate_hz: float,
    n_samples: int,
    trigger_enabled: bool,
    trigger_channel: int,
    trigger_edge: str,
    trigger_timeout_s: float,
) -> dict[int, list[int]]:
    lib = _load_lib()

    hz_system = c_double()
    _check(lib.FDwfDigitalInInternalClockInfo(hdwf, byref(hz_system)), "InternalClockInfo")
    div = max(1, int(hz_system.value / sample_rate_hz))

    _check(lib.FDwfDigitalInDividerSet(hdwf, c_uint(div)), "DividerSet")
    _check(lib.FDwfDigitalInSampleFormatSet(hdwf, _DIG_FORMAT_16), "SampleFormatSet")
    _check(lib.FDwfDigitalInBufferSizeSet(hdwf, c_int(n_samples)), "BufferSizeSet")
    _check(lib.FDwfDigitalInAcquisitionModeSet(hdwf, _ACQMODE_SINGLE), "AcquisitionModeSet")

    if trigger_enabled:
        _check(lib.FDwfDigitalInTriggerSourceSet(hdwf, _TRIGSRC_DET_DIGITAL_IN), "TriggerSourceSet")
        ch_mask = c_uint(1 << trigger_channel)
        zero = c_uint(0)
        if trigger_edge == "rising":
            _check(lib.FDwfDigitalInTriggerSet(hdwf, zero, zero, ch_mask, zero), "TriggerSet(rise)")
        elif trigger_edge == "falling":
            _check(lib.FDwfDigitalInTriggerSet(hdwf, zero, zero, zero, ch_mask), "TriggerSet(fall)")
        else:
            _check(lib.FDwfDigitalInTriggerSet(hdwf, zero, zero, ch_mask, ch_mask), "TriggerSet(either)")
    else:
        _check(lib.FDwfDigitalInTriggerSourceSet(hdwf, _TRIGSRC_PC), "TriggerSourceSet(pc)")

    _check(lib.FDwfDigitalInConfigure(hdwf, c_bool(False), c_bool(True)), "Configure")

    import time
    deadline = time.monotonic() + trigger_timeout_s + 1.0
    sts = c_ubyte()
    while time.monotonic() < deadline:
        _check(lib.FDwfDigitalInStatus(hdwf, c_bool(True), byref(sts)), "Status")
        if sts.value == _STATE_DONE.value:
            break
        time.sleep(0.005)
    else:
        from .errors import DigilentCaptureTimeoutError
        raise DigilentCaptureTimeoutError("Logic capture timed out")

    raw_buf = (ctypes.c_uint16 * n_samples)()
    _check(lib.FDwfDigitalInStatusData(hdwf, raw_buf, c_int(ctypes.sizeof(raw_buf))), "StatusData")

    result: dict[int, list[int]] = {}
    for ch in channels:
        mask = 1 << ch
        result[ch] = [1 if (raw_buf[i] & mask) else 0 for i in range(n_samples)]

    return result


# ---------------------------------------------------------------------------
# Waveform Generator (AnalogOut)
# ---------------------------------------------------------------------------

_WAVEFORM_MAP: dict[str, c_ubyte] = {
    "dc": _FUNC_DC,
    "sine": _FUNC_SINE,
    "square": _FUNC_SQUARE,
    "triangle": _FUNC_TRIANGLE,
    "rampup": _FUNC_RAMPUP,
    "rampdown": _FUNC_RAMPDOWN,
    "noise": _FUNC_NOISE,
    "custom": _FUNC_CUSTOM,
}


def wavegen_apply(
    hdwf: c_int,
    channel: int,
    waveform: str,
    frequency_hz: float,
    amplitude_v: float,
    offset_v: float,
    symmetry_percent: float,
    phase_deg: float,
    enable: bool,
) -> None:
    lib = _load_lib()
    idx = c_int(channel - 1)
    func = _WAVEFORM_MAP.get(waveform, _FUNC_SINE)

    _check(lib.FDwfAnalogOutNodeEnableSet(hdwf, idx, _NODE_CARRIER, c_bool(True)), "NodeEnableSet")
    _check(lib.FDwfAnalogOutNodeFunctionSet(hdwf, idx, _NODE_CARRIER, func), "NodeFunctionSet")
    _check(lib.FDwfAnalogOutNodeFrequencySet(hdwf, idx, _NODE_CARRIER, c_double(frequency_hz)), "NodeFrequencySet")
    _check(lib.FDwfAnalogOutNodeAmplitudeSet(hdwf, idx, _NODE_CARRIER, c_double(amplitude_v)), "NodeAmplitudeSet")
    _check(lib.FDwfAnalogOutNodeOffsetSet(hdwf, idx, _NODE_CARRIER, c_double(offset_v)), "NodeOffsetSet")
    _check(lib.FDwfAnalogOutNodeSymmetrySet(hdwf, idx, _NODE_CARRIER, c_double(symmetry_percent)), "NodeSymmetrySet")
    _check(lib.FDwfAnalogOutNodePhaseSet(hdwf, idx, _NODE_CARRIER, c_double(phase_deg)), "NodePhaseSet")
    _check(lib.FDwfAnalogOutConfigure(hdwf, idx, c_bool(enable)), "Configure")


def wavegen_set_custom_data(hdwf: c_int, channel: int, data: list[float]) -> None:
    """Upload custom waveform samples via FDwfAnalogOutNodeDataSet."""
    lib = _load_lib()
    idx = c_int(channel - 1)
    n = len(data)
    buf = (c_double * n)(*data)
    _check(lib.FDwfAnalogOutNodeDataSet(hdwf, idx, _NODE_CARRIER, buf, c_int(n)), "NodeDataSet")


def wavegen_set_modulation(
    hdwf: c_int,
    channel: int,
    mod_type: str,
    freq_hz: float,
    depth: float,
) -> None:
    """Configure AM or FM modulation on a wavegen channel."""
    lib = _load_lib()
    idx = c_int(channel - 1)
    node = _NODE_AM if mod_type == "am" else _NODE_FM
    mod_val = _MOD_MAP.get(mod_type, _MOD_AM)

    _check(lib.FDwfAnalogOutNodeEnableSet(hdwf, idx, node, c_bool(True)), "ModNodeEnableSet")
    _check(lib.FDwfAnalogOutNodeFunctionSet(hdwf, idx, node, _FUNC_SINE), "ModNodeFunctionSet")
    _check(lib.FDwfAnalogOutNodeFrequencySet(hdwf, idx, node, c_double(freq_hz)), "ModNodeFrequencySet")
    _check(lib.FDwfAnalogOutNodeAmplitudeSet(hdwf, idx, node, c_double(depth)), "ModNodeAmplitudeSet")
    _check(lib.FDwfAnalogOutModulationSet(hdwf, idx, mod_val), "ModulationSet")


def wavegen_stop(hdwf: c_int, channel: int) -> None:
    lib = _load_lib()
    lib.FDwfAnalogOutConfigure(hdwf, c_int(channel - 1), c_bool(False))


# ---------------------------------------------------------------------------
# Power Supplies (AnalogIO)
# ---------------------------------------------------------------------------

def supplies_apply(
    hdwf: c_int,
    vplus_v: float,
    vminus_v: float,
    enable_vplus: bool,
    enable_vminus: bool,
) -> None:
    """Legacy AD2-hardcoded supply helper — kept for backward compatibility."""
    lib = _load_lib()
    _check(lib.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(0), c_double(1.0 if enable_vplus else 0.0)), "V+ enable")
    _check(lib.FDwfAnalogIOChannelNodeSet(hdwf, c_int(0), c_int(1), c_double(vplus_v)), "V+ voltage")
    _check(lib.FDwfAnalogIOChannelNodeSet(hdwf, c_int(1), c_int(0), c_double(1.0 if enable_vminus else 0.0)), "V- enable")
    _check(lib.FDwfAnalogIOChannelNodeSet(hdwf, c_int(1), c_int(1), c_double(vminus_v)), "V- voltage")
    _check(lib.FDwfAnalogIOEnableSet(hdwf, c_bool(enable_vplus or enable_vminus)), "IOEnableSet")


def supplies_off(hdwf: c_int) -> None:
    lib = _load_lib()
    lib.FDwfAnalogIOEnableSet(hdwf, c_bool(False))


def supplies_channel_node_set(hdwf: c_int, ch_idx: int, node_idx: int, value: float) -> None:
    """Set one AnalogIO channel node value (FDwfAnalogIOChannelNodeSet)."""
    lib = _load_lib()
    _check(
        lib.FDwfAnalogIOChannelNodeSet(hdwf, c_int(ch_idx), c_int(node_idx), c_double(value)),
        f"AnalogIOChannelNodeSet(ch={ch_idx},node={node_idx})",
    )


def supplies_channel_node_get(hdwf: c_int, ch_idx: int, node_idx: int) -> float:
    """Read one AnalogIO channel node monitor value (FDwfAnalogIOChannelNodeStatus)."""
    lib = _load_lib()
    val = c_double()
    _check(
        lib.FDwfAnalogIOChannelNodeStatus(hdwf, c_int(ch_idx), c_int(node_idx), byref(val)),
        f"AnalogIOChannelNodeStatus(ch={ch_idx},node={node_idx})",
    )
    return val.value


def supplies_io_status(hdwf: c_int) -> None:
    """Call FDwfAnalogIOStatus to update all monitor readings."""
    lib = _load_lib()
    _check(lib.FDwfAnalogIOStatus(hdwf), "AnalogIOStatus")


def supplies_master_enable(hdwf: c_int, enable: bool) -> None:
    """Set the AnalogIO master enable (FDwfAnalogIOEnableSet)."""
    lib = _load_lib()
    _check(lib.FDwfAnalogIOEnableSet(hdwf, c_bool(enable)), "AnalogIOEnableSet")


# ---------------------------------------------------------------------------
# Static I/O (DigitalIO)
# ---------------------------------------------------------------------------

def static_io_apply(
    hdwf: c_int,
    pins: list[tuple[int, str, int]],
) -> dict[int, int]:
    lib = _load_lib()

    output_enable_mask = 0
    output_mask = 0
    for idx, mode, value in pins:
        if mode == "output":
            output_enable_mask |= 1 << idx
            if value:
                output_mask |= 1 << idx

    _check(lib.FDwfDigitalIOOutputEnableSet(hdwf, c_uint(output_enable_mask)), "OutputEnableSet")
    _check(lib.FDwfDigitalIOOutputSet(hdwf, c_uint(output_mask)), "OutputSet")
    _check(lib.FDwfDigitalIOStatus(hdwf), "IOStatus")

    input_word = c_uint()
    _check(lib.FDwfDigitalIOInputStatus(hdwf, byref(input_word)), "IOInputStatus")

    return {
        idx: 1 if (input_word.value & (1 << idx)) else 0
        for idx, mode, _ in pins
        if mode == "input"
    }


def is_available() -> bool:
    try:
        _load_lib()
        return True
    except DigilentTransportError:
        return False
