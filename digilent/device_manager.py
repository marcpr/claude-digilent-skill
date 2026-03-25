"""
Device Manager — exclusive session lifecycle, locking, and state machine.

States:
    absent      No device connected / library not found
    idle        Device open and ready for commands
    busy        A measurement or operation is in progress
    recovering  Transient error, attempting to reopen
    error       Unrecoverable error, manual reset required
"""

from __future__ import annotations

import contextlib
import copy
import ctypes
import threading
import time
from dataclasses import dataclass, field

from . import capability_registry
from . import dwf_adapter as dwf
from .errors import (
    DigilentBusyError,
    DigilentError,
    DigilentNotFoundError,
    DigilentTransportError,
)

# Device states
STATE_ABSENT = "absent"
STATE_IDLE = "idle"
STATE_BUSY = "busy"
STATE_RECOVERING = "recovering"
STATE_ERROR = "error"


@dataclass
class DeviceInfo:
    name: str = ""
    temperature_c: float | None = None
    capabilities: dict[str, bool] = field(default_factory=lambda: {
        "scope": True,
        "logic": True,
        "wavegen": True,
        "supplies": True,
        "static_io": True,
    })


class DeviceManager:
    """Manages an exclusive session with a WaveForms device."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = STATE_ABSENT
        self._hdwf = dwf.HDWF_NONE
        self._info = DeviceInfo()
        self._capability: capability_registry.CapabilityRecord | None = None
        self._error_msg: str | None = None
        self._open_count = 0

    # -----------------------------------------------------------------------
    # State accessors
    # -----------------------------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def hdwf(self) -> ctypes.c_int:
        return self._hdwf

    @property
    def device_info(self) -> DeviceInfo:
        return self._info

    @property
    def is_open(self) -> bool:
        return self._hdwf.value != dwf.HDWF_NONE.value

    @property
    def capability(self) -> capability_registry.CapabilityRecord | None:
        return self._capability

    def status_dict(self) -> dict:
        """Return a serialisable status snapshot."""
        return {
            "ok": True,
            "device_present": self._state != STATE_ABSENT,
            "device_open": self.is_open,
            "device_name": self._info.name or None,
            "state": self._state,
            "temperature_c": self._info.temperature_c,
            "capabilities": self._capability.to_dict() if self._capability else {},
            "error": self._error_msg,
        }

    # -----------------------------------------------------------------------
    # Open / close
    # -----------------------------------------------------------------------

    def open(self) -> None:
        """Open the first available WaveForms device. Idempotent if already open."""
        with self._lock:
            if self.is_open:
                return
            self._do_open()

    def close(self) -> None:
        """Close the device. Idempotent if already closed."""
        with self._lock:
            self._do_close()

    def reset_session(self) -> None:
        """Force-close and reopen the device to recover from error state."""
        with self._lock:
            self._do_close()
            self._state = STATE_ABSENT
            self._error_msg = None
        # Let caller reopen explicitly

    def _do_open(self) -> None:
        """Internal open — must be called with self._lock held."""
        try:
            devices = dwf.enumerate_devices_full()
            if not devices:
                self._state = STATE_ABSENT
                self._hdwf = dwf.HDWF_NONE
                return

            # Select first non-open device (-1 lets SDK pick, but we want to know devid)
            target = next((d for d in devices if not d.is_open), None)
            if target is None:
                raise DigilentNotFoundError(
                    "All WaveForms devices are in use by another process"
                )

            self._hdwf = dwf.open_device(target.idx)
            self._info.name = target.name
            self._info.temperature_c = dwf.read_temperature(self._hdwf)

            # Build capability from static registry, then refine with runtime config info
            cap = capability_registry.get_capability(target.devid)
            cap.name = target.name   # use name exactly as reported by SDK
            self._apply_config_overrides(cap, target.idx)
            self._capability = cap

            self._state = STATE_IDLE
            self._error_msg = None
            self._open_count += 1
        except DigilentNotFoundError:
            self._state = STATE_ABSENT
            self._hdwf = dwf.HDWF_NONE
        except DigilentTransportError as exc:
            self._state = STATE_ERROR
            self._error_msg = str(exc)
            self._hdwf = dwf.HDWF_NONE

    def _apply_config_overrides(
        self,
        cap: capability_registry.CapabilityRecord,
        device_idx: int,
    ) -> None:
        """Override static channel counts with values reported by FDwfEnumConfigInfo."""
        try:
            n_cfg = dwf.get_enum_config_count(device_idx)
        except Exception:
            return  # FDwfEnumConfig not supported — keep static defaults

        if n_cfg == 0:
            return

        cfg_idx = 0  # use first (default) configuration
        _overrides = [
            (dwf.DECI_ANALOG_IN_CHANNEL_COUNT,  "analog_in_ch"),
            (dwf.DECI_ANALOG_OUT_CHANNEL_COUNT, "analog_out_ch"),
            (dwf.DECI_ANALOG_IO_CHANNEL_COUNT,  "analog_io_ch"),
            (dwf.DECI_DIGITAL_IN_CHANNEL_COUNT,  "digital_in_ch"),
            (dwf.DECI_DIGITAL_OUT_CHANNEL_COUNT, "digital_out_ch"),
            (dwf.DECI_DIGITAL_IO_CHANNEL_COUNT,  "digital_io_ch"),
            (dwf.DECI_ANALOG_IN_BUFFER_SIZE,    "max_scope_buffer"),
            (dwf.DECI_DIGITAL_IN_BUFFER_SIZE,   "max_logic_buffer"),
        ]
        for deci_type, attr in _overrides:
            try:
                val = dwf.get_enum_config_info(device_idx, cfg_idx, deci_type)
                if val > 0:
                    setattr(cap, attr, val)
            except Exception:
                pass  # individual DECI query failed — keep static default

    def _do_close(self) -> None:
        """Internal close — must be called with self._lock held."""
        if self.is_open:
            dwf.close_device(self._hdwf)
        self._hdwf = dwf.HDWF_NONE
        self._info = DeviceInfo()
        self._capability = None
        if self._state not in (STATE_ERROR,):
            self._state = STATE_ABSENT

    # -----------------------------------------------------------------------
    # Exclusive operation context manager
    # -----------------------------------------------------------------------

    @contextlib.contextmanager
    def session(self):
        """
        Context manager that guarantees exclusive access while state=busy.
        Auto-opens the device if it is in idle state.
        Raises DigilentBusyError if already busy.
        """
        with self._lock:
            if self._state == STATE_BUSY:
                raise DigilentBusyError("Device is currently busy with another operation")

            if self._state in (STATE_ABSENT, STATE_RECOVERING):
                self._do_open()

            if not self.is_open:
                raise DigilentNotFoundError("No WaveForms device connected")

            if self._state == STATE_ERROR:
                raise DigilentTransportError(
                    f"Device in error state: {self._error_msg}"
                )

            self._state = STATE_BUSY

        try:
            yield self._hdwf
        except DigilentError as exc:
            # On DWF errors, try a single reconnect
            with self._lock:
                self._do_close()
                self._state = STATE_RECOVERING
            self._attempt_recovery()
            raise
        finally:
            with self._lock:
                if self._state == STATE_BUSY:
                    self._state = STATE_IDLE

    def _attempt_recovery(self) -> None:
        """Try to reopen the device once after an error."""
        time.sleep(0.5)
        with self._lock:
            if self._state == STATE_RECOVERING:
                self._do_open()

    # -----------------------------------------------------------------------
    # Temperature refresh
    # -----------------------------------------------------------------------

    def refresh_temperature(self) -> None:
        """Update cached temperature reading without acquiring full session lock."""
        if self.is_open and self._state == STATE_IDLE:
            self._info.temperature_c = dwf.read_temperature(self._hdwf)
