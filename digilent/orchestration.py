"""
High-level orchestration actions for agent-friendly measurements.

Actions are composites that use the lower-level services and return
structured pass/fail results with tolerances.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

from .config import DigilentConfig
from .device_manager import DeviceManager
from .errors import DigilentConfigInvalidError
from .models import (
    I2cConfigureRequest,
    I2cWriteRequest,
    LogicCaptureRequest,
    ScopeCaptureRequest,
    SuppliesMasterRequest,
    SuppliesRequest,
    TriggerConfig,
    UartConfigureRequest,
    UartReceiveRequest,
    UartSendRequest,
    WavegenRequest,
)
from .logic_service import LogicService
from .protocol_service import ProtocolService
from .scope_service import ScopeService
from .supplies_service import SuppliesService
from .wavegen_service import WavegenService


class OrchestrationService:
    def __init__(self, manager: DeviceManager, config: DigilentConfig) -> None:
        self._manager = manager
        self._cfg = config
        self._scope = ScopeService(manager, config)
        self._logic = LogicService(manager, config)
        self._wavegen = WavegenService(manager, config)
        self._supplies = SuppliesService(manager, config)
        self._protocol = ProtocolService(manager, config)

    def measure_basic(self, action: str, params: dict) -> dict:
        """Dispatch a named high-level measurement action."""
        dispatch = {
            "measure_esp32_pwm": self._measure_esp32_pwm,
            "measure_voltage_level": self._measure_voltage_level,
            "detect_logic_activity": self._detect_logic_activity,
            "bode_sweep": self._bode_sweep,
            "uart_loopback_test": self._uart_loopback_test,
            "i2c_scan": self._i2c_scan,
            "characterize_supply": self._characterize_supply,
            "digital_frequency": self._digital_frequency,
        }
        handler = dispatch.get(action)
        if handler is None:
            raise DigilentConfigInvalidError(
                f"Unknown action '{action}'. "
                f"Available actions: {sorted(dispatch.keys())}"
            )
        return handler(params)

    # -----------------------------------------------------------------------
    # Action: measure_esp32_pwm
    # -----------------------------------------------------------------------

    def _measure_esp32_pwm(self, params: dict) -> dict:
        """
        Measure PWM output from an ESP32 GPIO.

        params:
            channel (int): Scope channel (default: 1)
            expected_freq_hz (float): Expected PWM frequency
            tolerance_percent (float): Acceptable deviation in percent (default: 5)
            sample_rate_hz (int): Scope sample rate (default: 2×expected)
            duration_ms (int): Capture window (default: 20)
        """
        ch = int(params.get("channel", 1))
        expected_hz = float(params.get("expected_freq_hz", 1000.0))
        tolerance = float(params.get("tolerance_percent", 5.0))
        sample_rate = int(params.get("sample_rate_hz", max(int(expected_hz * 20), 100_000)))
        duration_ms = int(params.get("duration_ms", 20))
        range_v = float(params.get("range_v", 5.0))

        req = ScopeCaptureRequest(
            channels=[ch],
            range_v=range_v,
            offset_v=0.0,
            sample_rate_hz=sample_rate,
            duration_ms=duration_ms,
            trigger=TriggerConfig(enabled=True, source=f"ch{ch}", edge="rising", level_v=range_v / 2),
        )
        capture = self._scope.capture(req)
        ch_metrics = capture["metrics"].get(f"ch{ch}", {})

        measured_hz = ch_metrics.get("freq_est_hz")
        duty = ch_metrics.get("duty_cycle_percent")
        vpp = ch_metrics.get("vpp")

        within = None
        if measured_hz is not None and expected_hz > 0:
            deviation_pct = abs(measured_hz - expected_hz) / expected_hz * 100.0
            within = deviation_pct <= tolerance

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "measure_esp32_pwm",
            "within_tolerance": within,
            "result": {
                "measured_freq_hz": measured_hz,
                "expected_freq_hz": expected_hz,
                "tolerance_percent": tolerance,
                "duty_cycle_percent": duty,
                "vpp": vpp,
                "vmin": ch_metrics.get("vmin"),
                "vmax": ch_metrics.get("vmax"),
            },
        }

    # -----------------------------------------------------------------------
    # Action: measure_voltage_level
    # -----------------------------------------------------------------------

    def _measure_voltage_level(self, params: dict) -> dict:
        """
        Measure DC or slowly-varying voltage on a scope channel.

        params:
            channel (int): Scope channel (default: 1)
            expected_v (float): Expected voltage (for tolerance check)
            tolerance_v (float): Acceptable deviation in volts (default: 0.1)
            range_v (float): Scope range in volts (default: 5.0)
            duration_ms (int): Capture window (default: 10)
        """
        ch = int(params.get("channel", 1))
        expected_v = params.get("expected_v")
        tolerance_v = float(params.get("tolerance_v", 0.1))
        range_v = float(params.get("range_v", 5.0))
        duration_ms = int(params.get("duration_ms", 10))

        req = ScopeCaptureRequest(
            channels=[ch],
            range_v=range_v,
            offset_v=0.0,
            sample_rate_hz=10_000,
            duration_ms=duration_ms,
            trigger=TriggerConfig(enabled=False),
        )
        capture = self._scope.capture(req)
        ch_metrics = capture["metrics"].get(f"ch{ch}", {})
        vavg = ch_metrics.get("vavg")

        within = None
        if vavg is not None and expected_v is not None:
            within = abs(vavg - expected_v) <= tolerance_v

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "measure_voltage_level",
            "within_tolerance": within,
            "result": {
                "measured_v": vavg,
                "expected_v": expected_v,
                "tolerance_v": tolerance_v,
                "vmin": ch_metrics.get("vmin"),
                "vmax": ch_metrics.get("vmax"),
                "vrms": ch_metrics.get("vrms"),
            },
        }

    # -----------------------------------------------------------------------
    # Action: detect_logic_activity
    # -----------------------------------------------------------------------

    def _detect_logic_activity(self, params: dict) -> dict:
        """
        Detect digital activity (transitions) on one or more logic channels.

        params:
            channels (list[int]): Logic channels to observe (default: [0])
            sample_rate_hz (int): Sample rate (default: 1_000_000)
            duration_samples (int): Number of samples (default: 10_000)
            min_edges (int): Minimum edge count to consider "active" (default: 2)
        """
        channels = list(params.get("channels", [0]))
        sample_rate = int(params.get("sample_rate_hz", 1_000_000))
        n_samples = int(params.get("duration_samples", 10_000))
        min_edges = int(params.get("min_edges", 2))

        req = LogicCaptureRequest(
            channels=channels,
            sample_rate_hz=sample_rate,
            samples=n_samples,
            trigger=TriggerConfig(enabled=False),
        )
        capture = self._logic.capture(req)

        active_channels: list[int] = []
        channel_results: dict[str, dict] = {}
        for ch in channels:
            metrics = capture["metrics"].get(str(ch), {})
            edges = metrics.get("edge_count", 0)
            active = edges >= min_edges
            if active:
                active_channels.append(ch)
            channel_results[str(ch)] = {
                "edge_count": edges,
                "active": active,
                "freq_est_hz": metrics.get("freq_est_hz"),
                "duty_cycle_percent": metrics.get("duty_cycle_percent"),
            }

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "detect_logic_activity",
            "within_tolerance": len(active_channels) > 0,
            "result": {
                "active_channels": active_channels,
                "min_edges_threshold": min_edges,
                "channels": channel_results,
            },
        }

    # -----------------------------------------------------------------------
    # Action: bode_sweep
    # -----------------------------------------------------------------------

    def _bode_sweep(self, params: dict) -> dict:
        """
        Signal-injection Bode sweep: drive W1, measure CH1 (ref) and CH2 (DUT).

        params:
            f_start_hz (float): Start frequency Hz (default: 100)
            f_stop_hz (float): Stop frequency Hz (default: 100000)
            steps (int): Number of log-spaced steps (default: 30)
            amplitude_v (float): Wavegen amplitude V (default: 1.0)
            ref_channel (int): Reference scope channel (default: 1)
            dut_channel (int): DUT scope channel (default: 2)
            range_v (float): Scope range V per channel (default: 5.0)
        """
        f_start = float(params.get("f_start_hz", 100.0))
        f_stop = float(params.get("f_stop_hz", 100_000.0))
        steps = int(params.get("steps", 30))
        amplitude_v = float(params.get("amplitude_v", 1.0))
        ref_ch = int(params.get("ref_channel", 1))
        dut_ch = int(params.get("dut_channel", 2))
        range_v = float(params.get("range_v", 5.0))

        if f_start <= 0 or f_stop <= f_start or steps < 2:
            raise DigilentConfigInvalidError(
                "bode_sweep: f_start > 0, f_stop > f_start, steps >= 2"
            )

        frequencies = [
            f_start * (f_stop / f_start) ** (i / (steps - 1))
            for i in range(steps)
        ]

        gains_db: list[float] = []
        phases_deg: list[float] = []

        for freq in frequencies:
            # Set wavegen frequency; use at least 20 samples per period
            sample_rate = min(max(int(freq * 40), 10_000), 100_000_000)
            periods_to_capture = 10
            duration_ms = max(1.0, periods_to_capture / freq * 1000.0)
            duration_ms = min(duration_ms, 50.0)  # cap at 50 ms

            self._wavegen.set(WavegenRequest(
                channel=1,
                waveform="sine",
                frequency_hz=freq,
                amplitude_v=amplitude_v,
                offset_v=0.0,
                enable=True,
            ))
            time.sleep(0.02)  # settle

            capture = self._scope.capture(ScopeCaptureRequest(
                channels=[ref_ch, dut_ch],
                range_v=range_v,
                offset_v=0.0,
                sample_rate_hz=sample_rate,
                duration_ms=duration_ms,
                trigger=TriggerConfig(enabled=False),
                return_waveform=True,
            ))
            ref_m = capture["metrics"].get(f"ch{ref_ch}", {})
            dut_m = capture["metrics"].get(f"ch{dut_ch}", {})

            ref_rms = ref_m.get("vrms") or 1e-12
            dut_rms = dut_m.get("vrms") or 1e-12
            gain_db = 20.0 * math.log10(max(dut_rms / ref_rms, 1e-12))
            gains_db.append(round(gain_db, 3))

            # Phase from waveform cross-correlation (use zero-crossing method)
            waveforms = capture.get("waveform", [])
            ref_wave = next((w for w in waveforms if w.get("channel") == ref_ch), None)
            dut_wave = next((w for w in waveforms if w.get("channel") == dut_ch), None)
            phase = 0.0
            if ref_wave and dut_wave:
                ref_v = ref_wave.get("voltage_v", [])
                dut_v = dut_wave.get("voltage_v", [])
                ref_t = ref_wave.get("time_s", [])
                if ref_v and dut_v and ref_t and len(ref_v) == len(dut_v) >= 4:
                    n = len(ref_v)
                    dt = (ref_t[-1] - ref_t[0]) / (n - 1) if n > 1 else 1.0
                    # Cross-correlation lag estimate
                    cross = [
                        sum(ref_v[j] * dut_v[(j + lag) % n] for j in range(n))
                        for lag in range(-n // 4, n // 4 + 1)
                    ]
                    best_lag = cross.index(max(cross)) - n // 4
                    lag_s = best_lag * dt
                    phase = round(math.degrees(2 * math.pi * freq * lag_s), 2)
            phases_deg.append(phase)

        # Stop wavegen
        self._wavegen.stop(WavegenRequest(channel=1, enable=False))

        # Find -3 dB frequency
        fc_3db = None
        if gains_db:
            passband_gain = gains_db[0]
            threshold = passband_gain - 3.0
            for i in range(1, len(gains_db)):
                if gains_db[i] <= threshold:
                    fc_3db = round(frequencies[i], 2)
                    break

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "bode_sweep",
            "within_tolerance": True,
            "result": {
                "frequencies_hz": [round(f, 2) for f in frequencies],
                "gain_db": gains_db,
                "phase_deg": phases_deg,
                "fc_3db_hz": fc_3db,
                "steps": steps,
                "amplitude_v": amplitude_v,
            },
        }

    # -----------------------------------------------------------------------
    # Action: uart_loopback_test
    # -----------------------------------------------------------------------

    def _uart_loopback_test(self, params: dict) -> dict:
        """
        Configure UART and verify TX→RX loopback.

        params:
            baud (int): Baud rate (default: 115200)
            tx_ch (int): TX DIO channel (default: 0)
            rx_ch (int): RX DIO channel (default: 1)
            test_string (str): Bytes to send (default: "Hello")
            timeout_s (float): Receive timeout (default: 1.0)
        """
        baud = int(params.get("baud", 115200))
        tx_ch = int(params.get("tx_ch", 0))
        rx_ch = int(params.get("rx_ch", 1))
        test_string = str(params.get("test_string", "Hello"))
        timeout_s = float(params.get("timeout_s", 1.0))

        self._protocol.uart_configure(UartConfigureRequest(
            baud_rate=baud,
            bits=8,
            parity="none",
            stop_bits=1.0,
            tx_ch=tx_ch,
            rx_ch=rx_ch,
        ))

        self._protocol.uart_send(UartSendRequest(data=test_string))

        result = self._protocol.uart_receive(UartReceiveRequest(
            max_bytes=len(test_string) + 16,
            timeout_s=timeout_s,
        ))

        received = result.get("data", "")
        match = received.strip() == test_string.strip()
        warnings = result.get("warnings", [])

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "uart_loopback_test",
            "within_tolerance": match,
            "result": {
                "sent": test_string,
                "received": received,
                "match": match,
                "bytes_received": result.get("bytes_received", 0),
                "baud": baud,
                "warnings": warnings,
            },
        }

    # -----------------------------------------------------------------------
    # Action: i2c_scan
    # -----------------------------------------------------------------------

    def _i2c_scan(self, params: dict) -> dict:
        """
        Scan I2C bus for responding devices (addresses 0x08–0x77).

        params:
            rate_hz (float): I2C bus rate (default: 100000)
            scl_ch (int): SCL DIO channel (default: 0)
            sda_ch (int): SDA DIO channel (default: 1)
            addr_start (int): First address to probe (default: 0x08)
            addr_stop (int): Last address to probe inclusive (default: 0x77)
        """
        rate_hz = float(params.get("rate_hz", 100_000.0))
        scl_ch = int(params.get("scl_ch", 0))
        sda_ch = int(params.get("sda_ch", 1))
        addr_start = int(params.get("addr_start", 0x08))
        addr_stop = int(params.get("addr_stop", 0x77))

        self._protocol.i2c_configure(I2cConfigureRequest(
            rate_hz=rate_hz,
            scl_ch=scl_ch,
            sda_ch=sda_ch,
        ))

        found: list[str] = []
        for addr in range(addr_start, addr_stop + 1):
            try:
                result = self._protocol.i2c_write(I2cWriteRequest(
                    address=addr,
                    data=[],
                ))
                if result.get("nak", 1) == 0:
                    found.append(f"0x{addr:02X}")
            except Exception:
                pass

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "i2c_scan",
            "within_tolerance": True,
            "result": {
                "devices_found": found,
                "count": len(found),
                "scan_range": f"0x{addr_start:02X}–0x{addr_stop:02X}",
                "rate_hz": rate_hz,
            },
        }

    # -----------------------------------------------------------------------
    # Action: characterize_supply
    # -----------------------------------------------------------------------

    def _characterize_supply(self, params: dict) -> dict:
        """
        Enable a power supply rail and measure its actual voltage with the scope.

        params:
            vplus_v (float): Target V+ voltage (default: 3.3)
            vminus_v (float): Target V- voltage (default: 0.0)
            enable_vplus (bool): Enable positive rail (default: true)
            enable_vminus (bool): Enable negative rail (default: false)
            scope_channel (int): Scope channel to measure on (default: 1)
            scope_range_v (float): Scope range V (default: 5.0)
            settle_ms (int): Settle time before measurement ms (default: 200)
        """
        vplus_v = float(params.get("vplus_v", 3.3))
        vminus_v = float(params.get("vminus_v", 0.0))
        enable_vplus = bool(params.get("enable_vplus", True))
        enable_vminus = bool(params.get("enable_vminus", False))
        scope_ch = int(params.get("scope_channel", 1))
        scope_range_v = float(params.get("scope_range_v", 5.0))
        settle_ms = int(params.get("settle_ms", 200))

        self._supplies.set_legacy(SuppliesRequest(
            vplus_v=vplus_v,
            vminus_v=vminus_v,
            enable_vplus=enable_vplus,
            enable_vminus=enable_vminus,
            confirm_unsafe=True,
        ))
        self._supplies.master(SuppliesMasterRequest(enable=True, confirm_unsafe=True))

        time.sleep(settle_ms / 1000.0)

        capture = self._scope.capture(ScopeCaptureRequest(
            channels=[scope_ch],
            range_v=scope_range_v,
            offset_v=0.0,
            sample_rate_hz=10_000,
            duration_ms=20,
            trigger=TriggerConfig(enabled=False),
        ))
        ch_m = capture["metrics"].get(f"ch{scope_ch}", {})
        measured_v = ch_m.get("vavg")

        within = None
        if measured_v is not None and enable_vplus:
            within = abs(measured_v - vplus_v) <= 0.1

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "characterize_supply",
            "within_tolerance": within,
            "result": {
                "target_vplus_v": vplus_v if enable_vplus else None,
                "target_vminus_v": vminus_v if enable_vminus else None,
                "measured_v": measured_v,
                "vmin": ch_m.get("vmin"),
                "vmax": ch_m.get("vmax"),
                "vrms": ch_m.get("vrms"),
                "ripple_vpp": ch_m.get("vpp"),
            },
        }

    # -----------------------------------------------------------------------
    # Action: digital_frequency
    # -----------------------------------------------------------------------

    def _digital_frequency(self, params: dict) -> dict:
        """
        Measure frequency of a digital signal on a DIO channel via logic analyzer.

        params:
            channel (int): DIO channel (default: 0)
            sample_rate_hz (int): Sample rate (default: 10000000)
            duration_samples (int): Capture length (default: 100000)
            expected_freq_hz (float): Expected frequency for tolerance check
            tolerance_percent (float): Tolerance % (default: 5.0)
        """
        channel = int(params.get("channel", 0))
        sample_rate = int(params.get("sample_rate_hz", 10_000_000))
        n_samples = int(params.get("duration_samples", 100_000))
        expected_hz = params.get("expected_freq_hz")
        tolerance = float(params.get("tolerance_percent", 5.0))

        req = LogicCaptureRequest(
            channels=[channel],
            sample_rate_hz=sample_rate,
            samples=n_samples,
            trigger=TriggerConfig(enabled=False),
        )
        capture = self._logic.capture(req)
        metrics = capture["metrics"].get(str(channel), {})
        freq_hz = metrics.get("freq_est_hz")
        duty = metrics.get("duty_cycle_percent")
        edges = metrics.get("edge_count", 0)

        within = None
        if freq_hz is not None and expected_hz is not None:
            deviation_pct = abs(freq_hz - float(expected_hz)) / float(expected_hz) * 100.0
            within = deviation_pct <= tolerance

        return {
            "ok": True,
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": "digital_frequency",
            "within_tolerance": within,
            "result": {
                "channel": channel,
                "freq_hz": freq_hz,
                "expected_freq_hz": float(expected_hz) if expected_hz is not None else None,
                "tolerance_percent": tolerance,
                "duty_cycle_percent": duty,
                "edge_count": edges,
            },
        }
