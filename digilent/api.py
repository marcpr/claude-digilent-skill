"""
Digilent API — HTTP dispatch and module-level controller facade.

Usage from local server:

    import digilent.api as digilent_api
    digilent_api.init()                          # loads config, opens device
    digilent_api.handle_get(handler, path)
    digilent_api.handle_post(handler, path)
    digilent_api.shutdown()

Or with a pre-built config (e.g. local server with auto_open=True):

    from digilent.config import DigilentConfig
    digilent_api.init_with_config(DigilentConfig(auto_open=True))
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from .config import DigilentConfig, load_config
from .device_manager import DeviceManager
from .digital_io_service import DigitalIOService
from .errors import DigilentBusyError, DigilentConfigInvalidError, DigilentError, DigilentNotFoundError, DigilentTransportError
from .impedance_service import ImpedanceService
from .logic_service import LogicService
from .models import (
    BasicMeasureRequest,
    CanConfigureRequest,
    CanReceiveRequest,
    CanSendRequest,
    CanSniffRequest,
    DigitalIOConfigureRequest,
    DigitalIOWriteRequest,
    I2cConfigureRequest,
    I2cReadRequest,
    I2cSpyConfigureRequest,
    I2cSpyReadRequest,
    I2cWriteReadRequest,
    I2cWriteRequest,
    ImpedanceCompensationRequest,
    ImpedanceConfigureRequest,
    ImpedanceMeasureRequest,
    ImpedanceSweepRequest,
    LogicCaptureRequest,
    PatternSetRequest,
    PatternStopRequest,
    ScopeCaptureRequest,
    ScopeRecordRequest,
    ScopeSampleRequest,
    SpiConfigureRequest,
    SpiSniffRequest,
    SpiTransferRequest,
    StaticIoRequest,
    SuppliesMasterRequest,
    SuppliesRequest,
    SuppliesSetRequest,
    UartConfigureRequest,
    UartReceiveRequest,
    UartSendRequest,
    UartSniffRequest,
    WavegenRequest,
)
from .orchestration import OrchestrationService
from .pattern_service import PatternService
from .protocol_service import ProtocolService
from .scope_service import ScopeService
from .supplies_service import StaticIoService, SuppliesService
from .wavegen_service import WavegenService

_log = logging.getLogger("digilent.api")

_config: DigilentConfig | None = None
_manager: DeviceManager | None = None
_scope: ScopeService | None = None
_logic: LogicService | None = None
_wavegen: WavegenService | None = None
_supplies: SuppliesService | None = None
_static_io: StaticIoService | None = None
_digital_io: DigitalIOService | None = None
_pattern: PatternService | None = None
_impedance: ImpedanceService | None = None
_protocol: ProtocolService | None = None
_orchestration: OrchestrationService | None = None


def _setup_services(cfg: DigilentConfig) -> None:
    """Initialise all service objects from a config."""
    global _config, _manager, _scope, _logic, _wavegen, _supplies, _static_io
    global _digital_io, _pattern, _impedance, _protocol, _orchestration
    _config = cfg
    _manager = DeviceManager()
    _scope = ScopeService(_manager, _config)
    _logic = LogicService(_manager, _config)
    _wavegen = WavegenService(_manager, _config)
    _supplies = SuppliesService(_manager, _config)
    _static_io = StaticIoService(_manager, _config)
    _digital_io = DigitalIOService(_manager, _config)
    _pattern = PatternService(_manager, _config)
    _impedance = ImpedanceService(_manager, _config)
    _protocol = ProtocolService(_manager, _config)
    _orchestration = OrchestrationService(_manager, _config)


def init(config_path: str | None = None) -> None:
    """Initialise services, loading config from file (falls back to defaults)."""
    cfg = load_config(config_path)
    if not cfg.enabled:
        _log.info("Digilent extension disabled by configuration")
        return
    _setup_services(cfg)
    if cfg.auto_open:
        try:
            _manager.open()
            _log.info("Digilent device opened: %s", _manager.device_info.name)
        except DigilentError as exc:
            _log.warning("auto_open failed: %s", exc)


def init_with_config(cfg: DigilentConfig) -> None:
    """Initialise services with a pre-built DigilentConfig object."""
    if not cfg.enabled:
        _log.info("Digilent extension disabled by configuration")
        return
    _setup_services(cfg)
    if cfg.auto_open:
        try:
            _manager.open()
            _log.info("Digilent device opened: %s", _manager.device_info.name)
        except DigilentError as exc:
            _log.warning("auto_open failed: %s", exc)


def shutdown() -> None:
    """Close device gracefully."""
    if _manager:
        _manager.close()


# ---------------------------------------------------------------------------
# HTTP dispatch
# ---------------------------------------------------------------------------

def handle_get(handler, path: str) -> None:
    if path == "/api/digilent/status":
        _h_status(handler)
    elif path == "/api/digilent/capabilities":
        _h_capabilities(handler)
    elif path == "/api/digilent/ping":
        handler._send_json({"ok": True, "server": "digilent-local", "version": "1.0"})
    elif path == "/api/digilent/supplies/info":
        _h_supplies_info(handler)
    elif path == "/api/digilent/supplies/status":
        _h_supplies_status(handler)
    elif path == "/api/digilent/digital-io/read":
        _h_digital_io_read(handler)
    else:
        _not_found(handler, path)


def handle_post(handler, path: str) -> None:
    routes = {
        "/api/digilent/device/open": _h_device_open,
        "/api/digilent/device/close": _h_device_close,
        "/api/digilent/scope/capture": _h_scope_capture,
        "/api/digilent/scope/measure": _h_scope_measure,
        "/api/digilent/scope/sample": _h_scope_sample,
        "/api/digilent/scope/record": _h_scope_record,
        "/api/digilent/logic/capture": _h_logic_capture,
        "/api/digilent/wavegen/set": _h_wavegen_set,
        "/api/digilent/wavegen/stop": _h_wavegen_stop,
        "/api/digilent/supplies/set": _h_supplies_set,
        "/api/digilent/supplies/master": _h_supplies_master,
        "/api/digilent/static-io/set": _h_static_io_set,
        "/api/digilent/digital-io/configure": _h_digital_io_configure,
        "/api/digilent/digital-io/write": _h_digital_io_write,
        "/api/digilent/pattern/set": _h_pattern_set,
        "/api/digilent/pattern/stop": _h_pattern_stop,
        "/api/digilent/impedance/configure": _h_impedance_configure,
        "/api/digilent/impedance/measure": _h_impedance_measure,
        "/api/digilent/impedance/sweep": _h_impedance_sweep,
        "/api/digilent/impedance/compensation": _h_impedance_compensation,
        "/api/digilent/protocol/uart/configure": _h_uart_configure,
        "/api/digilent/protocol/uart/send": _h_uart_send,
        "/api/digilent/protocol/uart/receive": _h_uart_receive,
        "/api/digilent/protocol/spi/configure": _h_spi_configure,
        "/api/digilent/protocol/spi/transfer": _h_spi_transfer,
        "/api/digilent/protocol/i2c/configure": _h_i2c_configure,
        "/api/digilent/protocol/i2c/write": _h_i2c_write,
        "/api/digilent/protocol/i2c/read": _h_i2c_read,
        "/api/digilent/protocol/i2c/write-read": _h_i2c_write_read,
        "/api/digilent/protocol/i2c/spy/configure": _h_i2c_spy_configure,
        "/api/digilent/protocol/i2c/spy/read": _h_i2c_spy_read,
        "/api/digilent/protocol/uart/sniff": _h_uart_sniff,
        "/api/digilent/protocol/can/sniff": _h_can_sniff,
        "/api/digilent/protocol/spi/sniff": _h_spi_sniff,
        "/api/digilent/protocol/can/configure": _h_can_configure,
        "/api/digilent/protocol/can/send": _h_can_send,
        "/api/digilent/protocol/can/receive": _h_can_receive,
        "/api/digilent/measure/basic": _h_measure_basic,
        "/api/digilent/session/reset": _h_session_reset,
    }
    fn = routes.get(path)
    if fn is None:
        _not_found(handler, path)
    else:
        fn(handler)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req_id() -> str:
    return f"req-{uuid.uuid4().hex[:8]}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok_if_not_init(handler) -> bool:
    if _manager is None:
        handler._send_json({
            "ok": False, "ts": _ts(), "request_id": _req_id(),
            "error": {"code": "DIGILENT_NOT_AVAILABLE", "message": "Digilent services not initialised"},
        }, 503)
        return True
    return False


def _error_response(exc: DigilentError) -> tuple[dict, int]:
    status_map = {
        "DIGILENT_BUSY": 409,
        "DIGILENT_NOT_FOUND": 503,
        "DIGILENT_CONFIG_INVALID": 400,
        "DIGILENT_RANGE_VIOLATION": 400,
        "DIGILENT_NOT_ENABLED": 403,
        "DIGILENT_CAPTURE_TIMEOUT": 504,
        "DIGILENT_TRIGGER_TIMEOUT": 504,
        "DIGILENT_NOT_AVAILABLE": 405,
        "DIGILENT_SDK_ERROR": 500,
        "DIGILENT_PROTOCOL_ERROR": 422,
        "DIGILENT_SESSION_LOST": 503,
    }
    return {
        "ok": False, "ts": _ts(), "request_id": _req_id(),
        "error": exc.to_dict(),
    }, status_map.get(exc.code, 500)


def _run(handler, fn, *args, **kwargs) -> None:
    t0 = time.monotonic()
    req_id = _req_id()
    try:
        result = fn(*args, **kwargs)
        result.setdefault("request_id", req_id)
        duration_ms = round((time.monotonic() - t0) * 1000, 1)
        _log.info('{"component":"digilent","op":"%s","request_id":"%s","duration_ms":%s,"status":"ok"}',
                  fn.__name__, req_id, duration_ms)
        handler._send_json(result)
    except DigilentError as exc:
        resp, status = _error_response(exc)
        resp["request_id"] = req_id
        _log.warning('{"component":"digilent","op":"%s","request_id":"%s","status":"error","code":"%s"}',
                     fn.__name__, req_id, exc.code)
        handler._send_json(resp, status)
    except Exception as exc:
        _log.exception("Unexpected error in digilent handler")
        handler._send_json({
            "ok": False, "ts": _ts(), "request_id": req_id,
            "error": {"code": "DIGILENT_INTERNAL_ERROR", "message": f"Unexpected error: {exc}"},
        }, 500)


def _not_found(handler, path: str) -> None:
    handler._send_json({"ok": False, "error": {"code": "NOT_FOUND", "message": f"No endpoint at {path}"}}, 404)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _h_status(handler) -> None:
    if _manager is None:
        handler._send_json({
            "ok": True, "device_present": False, "device_open": False,
            "device_name": None, "state": "absent", "temperature_c": None,
            "capabilities": {}, "extension_enabled": False,
        })
        return
    _manager.refresh_temperature()
    handler._send_json(_manager.status_dict())


def _h_capabilities(handler) -> None:
    if _manager is None:
        handler._send_json({
            "ok": False, "ts": _ts(), "request_id": _req_id(),
            "error": {
                "code": "DIGILENT_NOT_AVAILABLE",
                "message": "Digilent services not initialised",
            },
        }, 503)
        return
    cap = _manager.capability
    if cap is None:
        handler._send_json({
            "ok": False, "ts": _ts(), "request_id": _req_id(),
            "error": {
                "code": "DIGILENT_NOT_FOUND",
                "message": "No device open — capabilities not available",
            },
        }, 503)
        return
    handler._send_json({
        "ok": True,
        "ts": _ts(),
        "device": cap.name,
        "data": cap.to_dict(),
    })


def _h_device_open(handler) -> None:
    if _ok_if_not_init(handler):
        return
    _run(handler, _manager.open)


def _h_device_close(handler) -> None:
    if _ok_if_not_init(handler):
        return
    def _close():
        _manager.close()
        return {"ok": True, "ts": _ts(), "message": "Device closed"}
    _run(handler, _close)


def _h_scope_capture(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ScopeCaptureRequest.from_dict(handler._read_json() or {})
    _run(handler, _scope.capture, req)


def _h_scope_measure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ScopeCaptureRequest.from_dict(handler._read_json() or {})
    _run(handler, _scope.measure, req)


def _h_scope_sample(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ScopeSampleRequest.from_dict(handler._read_json() or {})
    _run(handler, _scope.sample, req)


def _h_scope_record(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ScopeRecordRequest.from_dict(handler._read_json() or {})
    _run(handler, _scope.record, req)


def _h_logic_capture(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = LogicCaptureRequest.from_dict(handler._read_json() or {})
    _run(handler, _logic.capture, req)


def _h_wavegen_set(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = WavegenRequest.from_dict(handler._read_json() or {})
    _run(handler, _wavegen.set, req)


def _h_wavegen_stop(handler) -> None:
    if _ok_if_not_init(handler):
        return
    body = handler._read_json() or {}
    _run(handler, _wavegen.stop, int(body.get("channel", 1)))


def _h_supplies_info(handler) -> None:
    if _ok_if_not_init(handler):
        return
    _run(handler, _supplies.info)


def _h_supplies_status(handler) -> None:
    if _ok_if_not_init(handler):
        return
    _run(handler, _supplies.status)


def _h_supplies_set(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = SuppliesSetRequest.from_dict(handler._read_json() or {})
    _run(handler, _supplies.set, req)


def _h_supplies_master(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = SuppliesMasterRequest.from_dict(handler._read_json() or {})
    _run(handler, _supplies.master, req)


def _h_static_io_set(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = StaticIoRequest.from_dict(handler._read_json() or {})
    _run(handler, _static_io.set, req)


def _h_measure_basic(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = BasicMeasureRequest.from_dict(handler._read_json() or {})
    _run(handler, _orchestration.measure_basic, req.action, req.params)


def _h_session_reset(handler) -> None:
    if _ok_if_not_init(handler):
        return
    def _reset():
        _manager.reset_session()
        return {"ok": True, "ts": _ts(), "message": "Session reset — device closed"}
    _run(handler, _reset)


# ---------------------------------------------------------------------------
# Digital I/O handlers
# ---------------------------------------------------------------------------

def _h_digital_io_read(handler) -> None:
    if _ok_if_not_init(handler):
        return
    _run(handler, _digital_io.read)


def _h_digital_io_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = DigitalIOConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _digital_io.configure, req)


def _h_digital_io_write(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = DigitalIOWriteRequest.from_dict(handler._read_json() or {})
    _run(handler, _digital_io.write, req)


# ---------------------------------------------------------------------------
# Pattern Generator handlers
# ---------------------------------------------------------------------------

def _h_pattern_set(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = PatternSetRequest.from_dict(handler._read_json() or {})
    _run(handler, _pattern.set, req)


def _h_pattern_stop(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = PatternStopRequest.from_dict(handler._read_json() or {})
    _run(handler, _pattern.stop, req)


# ---------------------------------------------------------------------------
# Impedance Analyzer handlers
# ---------------------------------------------------------------------------

def _h_impedance_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ImpedanceConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _impedance.configure, req)


def _h_impedance_measure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ImpedanceMeasureRequest.from_dict(handler._read_json() or {})
    _run(handler, _impedance.measure, req)


def _h_impedance_sweep(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ImpedanceSweepRequest.from_dict(handler._read_json() or {})
    _run(handler, _impedance.sweep, req)


def _h_impedance_compensation(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = ImpedanceCompensationRequest.from_dict(handler._read_json() or {})
    _run(handler, _impedance.set_compensation, req)


# ---------------------------------------------------------------------------
# Protocol handlers — UART
# ---------------------------------------------------------------------------

def _h_uart_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = UartConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.uart_configure, req)


def _h_uart_send(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = UartSendRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.uart_send, req)


def _h_uart_receive(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = UartReceiveRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.uart_receive, req)


# ---------------------------------------------------------------------------
# Protocol handlers — SPI
# ---------------------------------------------------------------------------

def _h_spi_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = SpiConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.spi_configure, req)


def _h_spi_transfer(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = SpiTransferRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.spi_transfer, req)


# ---------------------------------------------------------------------------
# Protocol handlers — I2C
# ---------------------------------------------------------------------------

def _h_i2c_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_configure, req)


def _h_i2c_write(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cWriteRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_write, req)


def _h_i2c_read(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cReadRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_read, req)


def _h_i2c_write_read(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cWriteReadRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_write_read, req)


# ---------------------------------------------------------------------------
# Protocol handlers — Sniff
# ---------------------------------------------------------------------------

def _h_i2c_spy_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cSpyConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_spy_configure, req)


def _h_i2c_spy_read(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = I2cSpyReadRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.i2c_spy_read, req)


def _h_uart_sniff(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = UartSniffRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.uart_sniff, req)


def _h_can_sniff(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = CanSniffRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.can_sniff, req)


def _h_spi_sniff(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = SpiSniffRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.spi_sniff, req)


# ---------------------------------------------------------------------------
# Protocol handlers — CAN
# ---------------------------------------------------------------------------

def _h_can_configure(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = CanConfigureRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.can_configure, req)


def _h_can_send(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = CanSendRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.can_send, req)


def _h_can_receive(handler) -> None:
    if _ok_if_not_init(handler):
        return
    req = CanReceiveRequest.from_dict(handler._read_json() or {})
    _run(handler, _protocol.can_receive, req)
