"""Pure-Python SPI bit-stream decoder — no ctypes / libdwf dependency."""

from __future__ import annotations


def spi_decode(
    samples: dict[int, list[int]],
    clk_ch: int,
    mosi_ch: int,
    miso_ch: int,
    cs_ch: int,
    mode: int,
    order: str,
    cs_active_low: bool = True,
) -> list[dict]:
    """Decode SPI transactions from raw logic-capture samples.

    Parameters
    ----------
    samples:
        Dict mapping channel index → list of 0/1 integers (one per sample).
    clk_ch, mosi_ch, miso_ch, cs_ch:
        Channel indices in *samples*.
    mode:
        SPI mode 0–3 (CPOL/CPHA). Determines which CLK edge to sample on:
        modes 0 and 3 → rising edge; modes 1 and 2 → falling edge.
    order:
        "msb" or "lsb" — bit-to-byte packing order.
    cs_active_low:
        True (default) → CS assert = low; False → CS assert = high.

    Returns
    -------
    List of transaction dicts: ``{mosi: [int], miso: [int], bits: int}``.
    """
    clk  = samples.get(clk_ch,  [])
    mosi = samples.get(mosi_ch, [])
    miso = samples.get(miso_ch, [])
    cs   = samples.get(cs_ch,   [])
    n = len(clk)
    if n == 0:
        return []

    # Mode 0 (CPOL=0,CPHA=0): sample on rising edge
    # Mode 1 (CPOL=0,CPHA=1): sample on falling edge
    # Mode 2 (CPOL=1,CPHA=0): sample on falling edge
    # Mode 3 (CPOL=1,CPHA=1): sample on rising edge
    sample_on_rising = mode in (0, 3)
    cs_assert = 0 if cs_active_low else 1

    def _pack(bits: list[int]) -> list[int]:
        out = []
        for i in range(0, len(bits), 8):
            chunk = bits[i:i + 8]
            if len(chunk) < 8:
                chunk += [0] * (8 - len(chunk))
            if order == "msb":
                out.append(sum(b << (7 - j) for j, b in enumerate(chunk)))
            else:
                out.append(sum(b << j for j, b in enumerate(chunk)))
        return out

    transactions: list[dict] = []
    in_xact = False
    mosi_bits: list[int] = []
    miso_bits: list[int] = []

    for i in range(1, n):
        cs_prev, cs_curr = cs[i - 1], cs[i]

        if not in_xact and cs_prev != cs_assert and cs_curr == cs_assert:
            in_xact = True
            mosi_bits = []
            miso_bits = []
            continue

        if in_xact and cs_prev == cs_assert and cs_curr != cs_assert:
            in_xact = False
            if mosi_bits or miso_bits:
                transactions.append({
                    "mosi": _pack(mosi_bits),
                    "miso": _pack(miso_bits),
                    "bits": len(mosi_bits),
                })
            continue

        if not in_xact:
            continue

        clk_prev, clk_curr = clk[i - 1], clk[i]
        is_rising  = clk_prev == 0 and clk_curr == 1
        is_falling = clk_prev == 1 and clk_curr == 0
        if (sample_on_rising and is_rising) or (not sample_on_rising and is_falling):
            mosi_bits.append(mosi[i] if mosi else 0)
            miso_bits.append(miso[i] if miso else 0)

    # Flush open transaction (CS not present or always asserted)
    if in_xact and (mosi_bits or miso_bits):
        transactions.append({
            "mosi": _pack(mosi_bits),
            "miso": _pack(miso_bits),
            "bits": len(mosi_bits),
        })

    return transactions
