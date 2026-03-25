"""Digital I/O service — static bit-bang via FDwfDigitalIO* SDK calls."""

from __future__ import annotations

from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError, DigilentNotAvailable
from .models import DigitalIOConfigureRequest, DigitalIOWriteRequest


class DigitalIOService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_digital_io(self) -> None:
        cap = self._manager.capability
        if cap is not None and cap.digital_io_ch == 0:
            raise DigilentNotAvailable(
                "Digital I/O is not available on this device",
                {"device": cap.name},
            )

    def _offset(self) -> int:
        """Bit offset for channel indices (24 on Digital Discovery, 0 elsewhere)."""
        cap = self._manager.capability
        return cap.digital_io_offset if cap is not None else 0

    def _n_channels(self) -> int:
        cap = self._manager.capability
        return cap.digital_io_ch if cap is not None else 16

    # ------------------------------------------------------------------
    # POST /digital-io/configure
    # ------------------------------------------------------------------

    def configure(self, req: DigitalIOConfigureRequest) -> dict:
        """Set output-enable mask and initial output values."""
        self._require_digital_io()
        offset = self._offset()
        enable_mask = req.output_enable_mask << offset
        output_val = req.output_value << offset

        with self._manager.session() as hdwf:
            dwf.digital_io_configure(hdwf, enable_mask, output_val)
            input_word = dwf.digital_io_read(hdwf)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "output_enable_mask": hex(req.output_enable_mask),
            "output_value": hex(req.output_value),
            "input_word": hex(input_word >> offset),
        }

    # ------------------------------------------------------------------
    # GET /digital-io/read
    # ------------------------------------------------------------------

    def read(self) -> dict:
        """Read all digital input pins."""
        self._require_digital_io()
        offset = self._offset()
        n_ch = self._n_channels()

        with self._manager.session() as hdwf:
            input_word = dwf.digital_io_read(hdwf)

        shifted = input_word >> offset
        pins = {i: (shifted >> i) & 1 for i in range(n_ch)}
        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "input_word": hex(shifted),
            "pins": pins,
        }

    # ------------------------------------------------------------------
    # POST /digital-io/write
    # ------------------------------------------------------------------

    def write(self, req: DigitalIOWriteRequest) -> dict:
        """Read-modify-write the output register, applying only the masked bits."""
        self._require_digital_io()
        offset = self._offset()
        value = req.value << offset
        mask = req.mask << offset

        with self._manager.session() as hdwf:
            dwf.digital_io_write(hdwf, value, mask)
            input_word = dwf.digital_io_read(hdwf)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "input_word": hex(input_word >> offset),
        }
