#!/usr/bin/env python3
"""
Digital protocol capture and decode tool.

Configures a digital protocol (UART, SPI, I2C, or CAN), captures data for
a specified duration, formats it as a hex+ASCII dump, and writes a Markdown
summary report.

Usage:
    # UART capture at 115200 baud, 2 seconds, TX on DIO0, RX on DIO1
    python protocol_decode.py uart --baud 115200 --tx 0 --rx 1 --duration 2.0 --out uart_capture

    # I2C bus capture at 100 kHz
    python protocol_decode.py i2c --rate 100000 --scl 0 --sda 1 --duration 1.0 --out i2c_capture

    # SPI capture at 1 MHz
    python protocol_decode.py spi --freq 1000000 --clk 0 --mosi 1 --miso 2 --cs 3 --out spi_capture

    # CAN bus capture at 500 kbps
    python protocol_decode.py can --rate 500000 --tx 0 --rx 1 --duration 2.0 --out can_capture
"""

import argparse
import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _call(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def post(base, path, body):
    return _call(f"{base}{path}", method="POST", body=body)


def get(base, path):
    return _call(f"{base}{path}")


# ---------------------------------------------------------------------------
# Hex+ASCII dump formatter
# ---------------------------------------------------------------------------

def hex_dump(data: bytes, width: int = 16) -> list[str]:
    """Format bytes as hex+ASCII lines, 16 bytes per line."""
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset:offset + width]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        # Pad hex part to fixed width
        hex_part = hex_part.ljust(width * 3 - 1)
        lines.append(f"{offset:08X}  {hex_part}  |{ascii_part}|")
    return lines


# ---------------------------------------------------------------------------
# UART capture
# ---------------------------------------------------------------------------

def capture_uart(base, args):
    print(f"  Configuring UART @ {args.baud} baud, TX={args.tx}, RX={args.rx}")
    resp = post(base, "/api/digilent/protocol/uart/configure", {
        "baud_rate": args.baud,
        "bits": 8,
        "parity": "none",
        "stop_bits": 1.0,
        "tx_ch": args.tx,
        "rx_ch": args.rx,
        "polarity": 0,
    })
    if not resp.get("ok"):
        raise RuntimeError(f"UART configure failed: {resp}")

    print(f"  Receiving for {args.duration} s...")
    resp = post(base, "/api/digilent/protocol/uart/receive", {
        "max_bytes": 4096,
        "timeout_s": args.duration,
    })
    if not resp.get("ok"):
        raise RuntimeError(f"UART receive failed: {resp}")

    data_str = resp.get("data", "")
    data_bytes = data_str.encode("utf-8", errors="replace")
    warnings = resp.get("warnings", [])
    return {
        "protocol": "uart",
        "bytes_received": resp.get("bytes_received", 0),
        "raw": data_bytes,
        "frames": [{"data": data_bytes}],
        "errors": len(warnings),
        "warnings": warnings,
        "meta": {"baud_rate": args.baud},
    }


# ---------------------------------------------------------------------------
# I2C capture (poll-based read from address 0x00–0x7F scan)
# ---------------------------------------------------------------------------

def capture_i2c(base, args):
    print(f"  Configuring I2C @ {args.rate} Hz, SCL={args.scl}, SDA={args.sda}")
    resp = post(base, "/api/digilent/protocol/i2c/configure", {
        "rate_hz": args.rate,
        "scl_ch": args.scl,
        "sda_ch": args.sda,
    })
    if not resp.get("ok"):
        raise RuntimeError(f"I2C configure failed: {resp}")

    # Scan bus for responding devices
    print("  Scanning I2C bus (0x00–0x7F)...")
    responding = []
    deadline = time.monotonic() + args.duration
    for addr in range(0x08, 0x78):
        if time.monotonic() > deadline:
            break
        try:
            r = post(base, "/api/digilent/protocol/i2c/write", {
                "address": addr,
                "data": [],
            })
            if r.get("ok") and r.get("nak", 1) == 0:
                responding.append(addr)
                print(f"    Found device @ 0x{addr:02X}")
        except Exception:
            pass

    frames = [{"address": addr, "nak": 0} for addr in responding]
    return {
        "protocol": "i2c",
        "bytes_received": len(responding),
        "raw": bytes(),
        "frames": frames,
        "errors": 0,
        "warnings": [],
        "meta": {"rate_hz": args.rate, "devices_found": responding},
    }


# ---------------------------------------------------------------------------
# SPI capture
# ---------------------------------------------------------------------------

def capture_spi(base, args):
    print(f"  Configuring SPI @ {args.freq} Hz, CLK={args.clk}, MOSI={args.mosi}, MISO={args.miso}, CS={args.cs}")
    resp = post(base, "/api/digilent/protocol/spi/configure", {
        "freq_hz": args.freq,
        "mode": args.mode,
        "clk_ch": args.clk,
        "mosi_ch": args.mosi,
        "miso_ch": args.miso,
        "cs_ch": args.cs,
        "cs_idle": 1,
        "order": "msb",
        "duty_pct": 50.0,
    })
    if not resp.get("ok"):
        raise RuntimeError(f"SPI configure failed: {resp}")

    # Transfer a test pattern: 0x00..0x0F
    test_tx = list(range(16))
    print(f"  Transferring {len(test_tx)} test bytes...")
    resp = post(base, "/api/digilent/protocol/spi/transfer", {
        "tx_data": test_tx,
        "rx_len": len(test_tx),
    })
    if not resp.get("ok"):
        raise RuntimeError(f"SPI transfer failed: {resp}")

    rx_data = bytes(resp.get("rx_data", []))
    tx_data = bytes(test_tx)
    frames = [{
        "tx": list(tx_data),
        "rx": list(rx_data),
        "bytes": resp.get("bytes_transferred", 0),
    }]
    return {
        "protocol": "spi",
        "bytes_received": len(rx_data),
        "raw": rx_data,
        "frames": frames,
        "errors": 0,
        "warnings": [],
        "meta": {"freq_hz": args.freq, "mode": args.mode},
    }


# ---------------------------------------------------------------------------
# CAN capture
# ---------------------------------------------------------------------------

def capture_can(base, args):
    print(f"  Configuring CAN @ {args.rate} bps, TX={args.tx}, RX={args.rx}")
    resp = post(base, "/api/digilent/protocol/can/configure", {
        "rate_hz": args.rate,
        "tx_ch": args.tx,
        "rx_ch": args.rx,
    })
    if not resp.get("ok"):
        raise RuntimeError(f"CAN configure failed: {resp}")

    frames = []
    raw_bytes = b""
    deadline = time.monotonic() + args.duration
    print(f"  Receiving CAN frames for {args.duration} s...")
    frame_count = 0

    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        resp = post(base, "/api/digilent/protocol/can/receive", {
            "timeout_s": min(0.5, remaining),
        })
        if not resp.get("ok"):
            break
        if resp.get("timeout"):
            break
        can_id = resp.get("id", "0x0")
        data = bytes(resp.get("data", []))
        raw_bytes += data
        frames.append({
            "id": can_id,
            "data": list(data),
            "extended": resp.get("extended", False),
            "remote": resp.get("remote", False),
        })
        frame_count += 1
        print(f"    Frame #{frame_count}: ID={can_id} data={data.hex()}")

    return {
        "protocol": "can",
        "bytes_received": len(raw_bytes),
        "raw": raw_bytes,
        "frames": frames,
        "errors": 0,
        "warnings": [],
        "meta": {"rate_hz": args.rate, "frame_count": frame_count},
    }


# ---------------------------------------------------------------------------
# Markdown report writer
# ---------------------------------------------------------------------------

def write_report(out_path: pathlib.Path, capture_result: dict, args):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    protocol = capture_result["protocol"].upper()
    frames = capture_result["frames"]
    raw = capture_result["raw"]
    errors = capture_result["errors"]
    meta = capture_result.get("meta", {})

    lines = [
        f"# Protocol Decode Report — {protocol}",
        f"",
        f"**Generated:** {ts}  ",
        f"**Protocol:** {protocol}  ",
        f"**Bytes captured:** {capture_result['bytes_received']}  ",
        f"**Frame count:** {len(frames)}  ",
        f"**Error count:** {errors}  ",
        f"",
    ]

    # Protocol-specific parameters
    if protocol == "UART":
        lines += [
            f"## Configuration",
            f"",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Baud rate | {meta.get('baud_rate', '-')} |",
            f"",
        ]
    elif protocol == "I2C":
        found = meta.get("devices_found", [])
        lines += [
            f"## Bus Scan Results",
            f"",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Rate | {meta.get('rate_hz', '-')} Hz |",
            f"| Devices found | {len(found)} |",
            f"",
        ]
        if found:
            lines += [
                f"### Responding Devices",
                f"",
                f"| Address (hex) | Address (dec) |",
                f"|---------------|---------------|",
            ]
            for addr in found:
                lines.append(f"| 0x{addr:02X} | {addr} |")
            lines.append("")
    elif protocol == "SPI":
        lines += [
            f"## Configuration",
            f"",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Frequency | {meta.get('freq_hz', '-')} Hz |",
            f"| Mode | {meta.get('mode', '-')} |",
            f"",
        ]
    elif protocol == "CAN":
        lines += [
            f"## Captured Frames",
            f"",
            f"| # | ID | DLC | Data (hex) | Extended | Remote |",
            f"|---|----|-----|-----------|----------|--------|",
        ]
        for i, fr in enumerate(frames[:50]):  # cap at 50 rows
            data_hex = bytes(fr.get("data", [])).hex(" ") or "(empty)"
            dlc = len(fr.get("data", []))
            lines.append(
                f"| {i+1} | {fr.get('id','?')} | {dlc} | `{data_hex}` "
                f"| {fr.get('extended', False)} | {fr.get('remote', False)} |"
            )
        if len(frames) > 50:
            lines.append(f"| … | … | … | … | … | … |")
        lines.append("")

    # Hex dump for UART/SPI
    if raw and protocol in ("UART", "SPI"):
        dump_lines = hex_dump(raw[:512])  # cap at 512 bytes for report
        lines += [
            f"## Hex Dump{' (first 512 bytes)' if len(raw) > 512 else ''}",
            f"",
            f"```",
        ]
        lines += dump_lines
        lines += ["```", ""]

    if capture_result.get("warnings"):
        lines += [f"## Warnings", ""]
        for w in capture_result["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        f"---",
        f"*Generated by protocol_decode.py*",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  Report saved: {out_path}")


# ---------------------------------------------------------------------------
# Raw hex dump output file
# ---------------------------------------------------------------------------

def write_hex_file(out_path: pathlib.Path, raw: bytes):
    if not raw:
        return
    dump_lines = hex_dump(raw)
    with open(out_path, "w") as f:
        f.write("\n".join(dump_lines) + "\n")
    print(f"  Hex dump saved: {out_path}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Digilent digital protocol capture and decode"
    )
    parser.add_argument("--base", default="http://localhost:8765",
                        help="Local server base URL (default: http://localhost:8765)")
    parser.add_argument("--out", default="protocol_capture",
                        help="Output filename stem (default: protocol_capture)")
    parser.add_argument("--duration", type=float, default=1.0,
                        help="Capture/timeout duration in seconds (default: 1.0)")

    sub = parser.add_subparsers(dest="protocol", required=True)

    # UART
    p_uart = sub.add_parser("uart", help="UART capture")
    p_uart.add_argument("--baud", type=int, default=115200)
    p_uart.add_argument("--tx", type=int, default=0, help="TX DIO channel")
    p_uart.add_argument("--rx", type=int, default=1, help="RX DIO channel")

    # I2C
    p_i2c = sub.add_parser("i2c", help="I2C bus scan and capture")
    p_i2c.add_argument("--rate", type=float, default=100_000.0, help="Bus rate Hz")
    p_i2c.add_argument("--scl", type=int, default=0, help="SCL DIO channel")
    p_i2c.add_argument("--sda", type=int, default=1, help="SDA DIO channel")

    # SPI
    p_spi = sub.add_parser("spi", help="SPI transfer capture")
    p_spi.add_argument("--freq", type=float, default=1_000_000.0, help="Clock Hz")
    p_spi.add_argument("--mode", type=int, default=0, choices=[0, 1, 2, 3])
    p_spi.add_argument("--clk", type=int, default=0)
    p_spi.add_argument("--mosi", type=int, default=1)
    p_spi.add_argument("--miso", type=int, default=2)
    p_spi.add_argument("--cs", type=int, default=3)

    # CAN
    p_can = sub.add_parser("can", help="CAN bus capture")
    p_can.add_argument("--rate", type=float, default=500_000.0, help="Bit rate Hz")
    p_can.add_argument("--tx", type=int, default=0, help="TX DIO channel")
    p_can.add_argument("--rx", type=int, default=1, help="RX DIO channel")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    out_stem = pathlib.Path(args.out)
    out_stem.parent.mkdir(parents=True, exist_ok=True)

    print(f"Protocol decode: {args.protocol.upper()}")

    CAPTURE_FNS = {
        "uart": capture_uart,
        "i2c": capture_i2c,
        "spi": capture_spi,
        "can": capture_can,
    }

    try:
        result = CAPTURE_FNS[args.protocol](args.base, args)
    except Exception as exc:
        print(f"ERROR: capture failed — {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  Captured {result['bytes_received']} bytes, "
          f"{len(result['frames'])} frames, "
          f"{result['errors']} errors")

    md_path = out_stem.with_suffix(".md")
    hex_path = out_stem.with_suffix(".hex")

    write_hex_file(hex_path, result["raw"])
    write_report(md_path, result, args)

    print("Done.")


if __name__ == "__main__":
    main()
