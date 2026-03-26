"""Digital Protocol service — UART, SPI, I2C, CAN via FDwfDigital* SDK calls."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from . import dwf_adapter as dwf
from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError, DigilentNotAvailable
from .models import (
    CanConfigureRequest,
    CanReceiveRequest,
    CanSendRequest,
    CanSniffRequest,
    I2cConfigureRequest,
    I2cReadRequest,
    I2cSpyConfigureRequest,
    I2cSpyReadRequest,
    I2cWriteReadRequest,
    I2cWriteRequest,
    SpiConfigureRequest,
    SpiSniffRequest,
    SpiTransferRequest,
    UartConfigureRequest,
    UartReceiveRequest,
    UartSendRequest,
    UartSniffRequest,
)

_VALID_PARITY = {"none", "even", "odd", "mark", "space"}
_VALID_SPI_ORDERS = {"msb", "lsb"}

# Device-specific protocol notes keyed by DEVID (returned in configure responses).
_DEVICE_PROTOCOL_NOTES: dict[int, str] = {
    8: (
        "ADP5250 uses fixed protocol pins — see WaveForms SDK §14.6 for pinout. "
        "Only I2C and SPI are supported; UART and CAN are not available on this device."
    ),
}


class ProtocolService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_protocols(self) -> None:
        cap = self._manager.capability
        if cap is not None and not cap.has_protocols:
            raise DigilentNotAvailable(
                "Digital protocols are not available on this device",
                {"device": cap.name},
            )

    def _device_note(self) -> str | None:
        cap = self._manager.capability
        if cap is None:
            return None
        return _DEVICE_PROTOCOL_NOTES.get(cap.devid)

    # ------------------------------------------------------------------
    # UART
    # ------------------------------------------------------------------

    def uart_configure(self, req: UartConfigureRequest) -> dict:
        self._require_protocols()
        if req.parity not in _VALID_PARITY:
            raise DigilentConfigInvalidError(f"Invalid parity '{req.parity}'")

        with self._manager.session() as hdwf:
            dwf.uart_configure(
                hdwf, req.baud_rate, req.bits, req.parity,
                req.stop_bits, req.tx_ch, req.rx_ch, req.polarity,
            )
        resp: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "baud_rate": req.baud_rate,
        }
        note = self._device_note()
        if note:
            resp["device_note"] = note
        return resp

    def uart_send(self, req: UartSendRequest) -> dict:
        self._require_protocols()
        data = req.data.encode("utf-8") if isinstance(req.data, str) else bytes(req.data)

        with self._manager.session() as hdwf:
            dwf.uart_send(hdwf, data)
        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "bytes_sent": len(data),
        }

    def uart_receive(self, req: UartReceiveRequest) -> dict:
        self._require_protocols()
        deadline = time.monotonic() + req.timeout_s
        received = b""
        parity_errors = 0

        with self._manager.session() as hdwf:
            while time.monotonic() < deadline and len(received) < req.max_bytes:
                chunk, parity = dwf.uart_receive(hdwf, req.max_bytes - len(received))
                if chunk:
                    received += chunk
                    parity_errors += abs(parity)
                time.sleep(0.01)

        result: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": received.decode("utf-8", errors="replace"),
            "bytes_received": len(received),
        }
        if parity_errors:
            result["warnings"] = [f"Parity errors detected: {parity_errors}"]
        return result

    # ------------------------------------------------------------------
    # SPI
    # ------------------------------------------------------------------

    def spi_configure(self, req: SpiConfigureRequest) -> dict:
        self._require_protocols()
        if req.order not in _VALID_SPI_ORDERS:
            raise DigilentConfigInvalidError(f"Invalid SPI order '{req.order}'")
        if req.mode not in (0, 1, 2, 3):
            raise DigilentConfigInvalidError(f"Invalid SPI mode {req.mode}")

        with self._manager.session() as hdwf:
            dwf.spi_configure(
                hdwf, req.freq_hz, req.mode,
                req.clk_ch, req.mosi_ch, req.miso_ch,
                req.cs_ch, req.cs_idle, req.order, req.duty_pct,
            )
        resp: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "freq_hz": req.freq_hz,
        }
        note = self._device_note()
        if note:
            resp["device_note"] = note
        return resp

    def spi_transfer(self, req: SpiTransferRequest) -> dict:
        self._require_protocols()
        tx = bytes(req.tx_data)

        with self._manager.session() as hdwf:
            rx = dwf.spi_transfer(hdwf, tx, req.rx_len)
        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "rx_data": list(rx),
            "bytes_transferred": max(len(tx), req.rx_len),
        }

    # ------------------------------------------------------------------
    # I2C
    # ------------------------------------------------------------------

    def i2c_configure(self, req: I2cConfigureRequest) -> dict:
        self._require_protocols()

        with self._manager.session() as hdwf:
            dwf.i2c_configure(hdwf, req.rate_hz, req.scl_ch, req.sda_ch)
        resp: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "rate_hz": req.rate_hz,
        }
        note = self._device_note()
        if note:
            resp["device_note"] = note
        return resp

    def i2c_write(self, req: I2cWriteRequest) -> dict:
        self._require_protocols()
        data = bytes(req.data)

        with self._manager.session() as hdwf:
            nak = dwf.i2c_write(hdwf, req.address, data)
        result: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "address": hex(req.address),
            "nak": nak,
        }
        if nak:
            result["warnings"] = [f"NAK received (count={nak})"]
        return result

    def i2c_read(self, req: I2cReadRequest) -> dict:
        self._require_protocols()

        with self._manager.session() as hdwf:
            data, nak = dwf.i2c_read(hdwf, req.address, req.length)
        result: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "address": hex(req.address),
            "data": list(data),
            "nak": nak,
        }
        if nak:
            result["warnings"] = [f"NAK received (count={nak})"]
        return result

    def i2c_write_read(self, req: I2cWriteReadRequest) -> dict:
        self._require_protocols()
        tx = bytes(req.tx)

        with self._manager.session() as hdwf:
            rx, nak = dwf.i2c_write_read(hdwf, req.address, tx, req.rx_len)
        result: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "address": hex(req.address),
            "rx_data": list(rx),
            "nak": nak,
        }
        if nak:
            result["warnings"] = [f"NAK received (count={nak})"]
        return result

    # ------------------------------------------------------------------
    # I2C Spy (passive sniffer — SDK-native)
    # ------------------------------------------------------------------

    def i2c_spy_configure(self, req: I2cSpyConfigureRequest) -> dict:
        self._require_protocols()

        with self._manager.session() as hdwf:
            dwf.i2c_spy_start(hdwf, req.scl_ch, req.sda_ch, req.rate_hz)
        resp: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "rate_hz": req.rate_hz,
            "mode": "spy",
        }
        note = self._device_note()
        if note:
            resp["device_note"] = note
        return resp

    def i2c_spy_read(self, req: I2cSpyReadRequest) -> dict:
        self._require_protocols()
        deadline = time.monotonic() + req.duration_s
        frames: list[dict] = []
        bytes_captured = 0

        with self._manager.session() as hdwf:
            while time.monotonic() < deadline and len(frames) < req.max_frames:
                start, stop, data, nak = dwf.i2c_spy_read(hdwf, req.max_bytes)
                if data or start or stop:
                    frames.append({
                        "start": start,
                        "stop": stop,
                        "data": list(data),
                        "nak": nak,
                    })
                    bytes_captured += len(data)
                time.sleep(0.005)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "frames": frames,
            "frame_count": len(frames),
            "bytes_captured": bytes_captured,
        }

    # ------------------------------------------------------------------
    # UART Sniff (passive RX — no TX driven)
    # ------------------------------------------------------------------

    def uart_sniff(self, req: UartSniffRequest) -> dict:
        self._require_protocols()
        if req.parity not in _VALID_PARITY:
            raise DigilentConfigInvalidError(f"Invalid parity '{req.parity}'")

        with self._manager.session() as hdwf:
            # tx_ch=-1 disables TX output; only RX pin is used
            dwf.uart_configure(
                hdwf, req.baud_rate, req.bits, req.parity,
                req.stop_bits, -1, req.rx_ch, 0,
            )
            deadline = time.monotonic() + req.duration_s
            received = b""
            parity_errors = 0
            while time.monotonic() < deadline and len(received) < req.max_bytes:
                chunk, parity = dwf.uart_receive(hdwf, req.max_bytes - len(received))
                if chunk:
                    received += chunk
                    parity_errors += abs(parity)
                time.sleep(0.01)

        result: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "data": received.decode("utf-8", errors="replace"),
            "bytes_received": len(received),
            "baud_rate": req.baud_rate,
        }
        if parity_errors:
            result["warnings"] = [f"Parity errors detected: {parity_errors}"]
        return result

    # ------------------------------------------------------------------
    # CAN Sniff (passive RX — no TX driven)
    # ------------------------------------------------------------------

    def can_sniff(self, req: CanSniffRequest) -> dict:
        self._require_protocols()
        deadline = time.monotonic() + req.duration_s
        frames: list[dict] = []

        with self._manager.session() as hdwf:
            # tx_ch=-1: configure RX only, nothing transmitted
            dwf.can_configure(hdwf, req.rate_hz, -1, req.rx_ch)
            while time.monotonic() < deadline and len(frames) < req.max_frames:
                can_id, data, extended, remote, status = dwf.can_receive(hdwf)
                if status == 0 and (data or remote):
                    frames.append({
                        "id": hex(can_id),
                        "data": list(data),
                        "extended": extended,
                        "remote": remote,
                    })
                time.sleep(0.005)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "frames": frames,
            "frame_count": len(frames),
            "rate_hz": req.rate_hz,
        }

    # ------------------------------------------------------------------
    # SPI Sniff (logic analyzer + software decode)
    # ------------------------------------------------------------------

    def spi_sniff(self, req: SpiSniffRequest) -> dict:
        self._require_protocols()
        if req.order not in _VALID_SPI_ORDERS:
            raise DigilentConfigInvalidError(f"Invalid SPI order '{req.order}'")
        if req.mode not in (0, 1, 2, 3):
            raise DigilentConfigInvalidError(f"Invalid SPI mode {req.mode}")

        with self._manager.session() as hdwf:
            transactions = dwf.spi_sniff_raw(
                hdwf=hdwf,
                clk_ch=req.clk_ch,
                mosi_ch=req.mosi_ch,
                miso_ch=req.miso_ch,
                cs_ch=req.cs_ch,
                spi_freq_hz=req.spi_freq_hz,
                mode=req.mode,
                order=req.order,
                duration_s=req.duration_s,
                cs_active_low=req.cs_active_low,
            )

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "transactions": transactions,
            "transaction_count": len(transactions),
            "spi_freq_hz": req.spi_freq_hz,
            "mode": req.mode,
            "order": req.order,
        }

    # ------------------------------------------------------------------
    # CAN
    # ------------------------------------------------------------------

    def can_configure(self, req: CanConfigureRequest) -> dict:
        self._require_protocols()

        with self._manager.session() as hdwf:
            dwf.can_configure(hdwf, req.rate_hz, req.tx_ch, req.rx_ch)
        resp: dict = {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "rate_hz": req.rate_hz,
        }
        note = self._device_note()
        if note:
            resp["device_note"] = note
        return resp

    def can_send(self, req: CanSendRequest) -> dict:
        self._require_protocols()
        data = bytes(req.data)
        if len(data) > 8:
            raise DigilentConfigInvalidError("CAN data frame max 8 bytes")

        with self._manager.session() as hdwf:
            dwf.can_send(hdwf, req.id, data, req.extended, req.remote)
        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "id": hex(req.id),
            "bytes_sent": len(data),
        }

    def can_receive(self, req: CanReceiveRequest) -> dict:
        self._require_protocols()
        deadline = time.monotonic() + req.timeout_s

        with self._manager.session() as hdwf:
            while time.monotonic() < deadline:
                can_id, data, extended, remote, status = dwf.can_receive(hdwf)
                if status == 0 and (data or remote):
                    return {
                        "ok": True,
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "id": hex(can_id),
                        "data": list(data),
                        "extended": extended,
                        "remote": remote,
                    }
                time.sleep(0.01)

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "id": None,
            "data": [],
            "extended": False,
            "remote": False,
            "timeout": True,
        }
