"""Vergelijk een ontwerp met het generieke opamp-model (gebruikt door het GA) en met
het NE5532-macromodel. Zo zien we of het GA-resultaat standhoudt met een echte opamp.

Gebruik:  python scripts/compare_opamp.py [ontwerp.json]   (standaard out/best.json)
Resultaat: tabel op het scherm + out/compare_ne5532.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import analysis, fitness, spice  # noqa: E402
from circuitbuilder.candidate import Design  # noqa: E402

OUT = ROOT / "out"
LEVELS = np.geomspace(0.05, 7, 12)  # ontwerpbereik; daarboven clipt het (traag te simuleren)


def measure(design: Design, opamp: str) -> dict:
    amps = LEVELS * np.sqrt(2) / 10 ** (fitness.GAIN_DB / 20)
    tran, ac, nz = spice.run_multi(design.netlist(amps, opamp=opamp), [
        (analysis.tran_command(1000, 20, 10), [f"v(out{i})" for i in range(len(amps))]),
        ("ac dec 20 5 500k", ["v(out_ac)", "v(in_ac)"]),
        ("noise v(out_ac) VAC dec 10 20 20k\nsetplot noise2", ["onoise_total"]),
    ], timeout=300)
    harms = [analysis.harmonics_from_wave(tran[:, 0], tran[:, 1 + i], 1000, 10, amplitude_in=a)
             for i, a in enumerate(amps)]
    f, mag, _ = analysis.ac_from_data(ac)
    return {
        "vout": np.array([h.vout_rms for h in harms]),
        "h": np.array([h.levels_db[:4] for h in harms]),
        "thd": np.array([h.thd for h in harms]),
        "f": f, "mag": mag,
        "snr": 20 * np.log10(1 / nz[0, 1]),
    }


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "best.json"
    design = Design(json.loads(src.read_text())["values"])
    tgt = fitness.load_target()
    gen = measure(design, "generic")
    ne = measure(design, "ne5532")

    for name, m in (("generiek", gen), ("NE5532", ne)):
        g1k = np.interp(1000, m["f"], m["mag"])
        band = (m["f"] >= 20) & (m["f"] <= 20e3)
        flat = np.max(np.abs(m["mag"][band] - g1k))
        print(f"{name:9s} versterking {g1k:5.2f} dB  vlakheid +/-{flat:.2f} dB  "
              f"S/R {m['snr']:.1f} dB")

    print("\n  Vout    |   generiek: THD%   H2     H3   |  NE5532: THD%   H2     H3   |  buis H2   H3")
    tv = fitness.target_at(tgt, gen["vout"])
    for i in range(len(LEVELS)):
        print(f"  {gen['vout'][i]:5.2f}V  |  {gen['thd'][i] * 100:9.3f} {gen['h'][i, 0]:6.1f} "
              f"{gen['h'][i, 1]:6.1f}  |  {ne['thd'][i] * 100:9.3f} {ne['h'][i, 0]:6.1f} "
              f"{ne['h'][i, 1]:6.1f}  |  {tv[i, 0]:6.1f} {tv[i, 1]:6.1f}")

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    tx, th = np.array(tgt["vout_rms"]), np.array(tgt["h"])
    for k, c in ((0, "C0"), (1, "C1")):
        ax[0].semilogx(tx, th[:, k], ":", color=c, lw=2, label=f"12AX7 H{k + 2}")
        ax[0].semilogx(gen["vout"], gen["h"][:, k], "o-", color=c, alpha=0.5,
                       label=f"generiek H{k + 2}")
        ax[0].semilogx(ne["vout"], ne["h"][:, k], "s--", color=c, label=f"NE5532 H{k + 2}")
    ax[0].set(title="Harmonischen (1 kHz): generiek model vs NE5532", xlabel="Vout [V rms]",
              ylabel="dB t.o.v. grondtoon", ylim=(-110, -10), xlim=(0.05, 10))
    ax[0].grid(True, which="both", alpha=0.3)
    ax[0].legend(fontsize=8, ncol=3)
    ax[1].semilogx(gen["f"], gen["mag"], label="generiek")
    ax[1].semilogx(ne["f"], ne["mag"], "--", label="NE5532")
    ax[1].axvspan(20, 20e3, color="C2", alpha=0.08)
    ax[1].set(title="Frequentierespons", xlabel="Hz", ylabel="dB",
              ylim=(fitness.GAIN_DB - 6, fitness.GAIN_DB + 2))
    ax[1].grid(True, which="both", alpha=0.3)
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(OUT / "compare_ne5532.png", dpi=120)
    print(f"\nPlot: {OUT / 'compare_ne5532.png'}")


if __name__ == "__main__":
    main()
