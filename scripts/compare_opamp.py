"""Compare a design using the generic opamp model (used by the GA) and the NE5532
macromodel. This shows whether the GA result holds up with a real opamp.

Usage:   python scripts/compare_opamp.py [design.json]   (default out/best.json)
Output:  table on screen + out/compare_ne5532.json + out/compare_ne5532.png
         (--plot-only redraws the plot from an existing out/compare_ne5532.json)
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
LEVELS = np.geomspace(0.05, 7, 12)  # design range; above this it clips (slow to simulate)


def measure(design: Design, opamp: str) -> dict:
    amps = LEVELS * np.sqrt(2) / 10 ** (fitness.GAIN_DB / 20)
    tran, ac, nz = spice.run_multi(design.netlist(amps, opamp=opamp), [
        (analysis.tran_command(1000, 20, 10), [f"v(out{i})" for i in range(len(amps))]),
        ("ac dec 20 5 500k", ["v(out_ac)", "v(in_ac)"]),
        ("noise v(out_ac) VAC dec 10 20 20k\nsetplot noise2", ["onoise_total"]),
    ], timeout=900)
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


def plot(gen: dict, ne: dict, tgt: dict) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    tx, th = np.array(tgt["vout_rms"]), np.array(tgt["h"])
    for k, c in ((0, "C0"), (1, "C1")):
        ax[0].semilogx(tx, th[:, k], ":", color=c, lw=2, label=f"12AX7 H{k + 2}")
        ax[0].semilogx(gen["vout"], gen["h"][:, k], "o-", color=c, alpha=0.5,
                       label=f"generic H{k + 2}")
        ax[0].semilogx(ne["vout"], ne["h"][:, k], "s--", color=c, label=f"NE5532 H{k + 2}")
    ax[0].set(title="Harmonics (1 kHz): generic model vs NE5532", xlabel="Vout [V rms]",
              ylabel="dB relative to fundamental", ylim=(-110, -10), xlim=(0.05, 10))
    ax[0].grid(True, which="both", alpha=0.3)
    ax[0].legend(fontsize=8, ncol=3)
    ax[1].semilogx(gen["f"], gen["mag"], label="generic")
    ax[1].semilogx(ne["f"], ne["mag"], "--", label="NE5532")
    ax[1].axvspan(20, 20e3, color="C2", alpha=0.08)
    ax[1].set(title="Frequency response", xlabel="Hz", ylabel="dB",
              ylim=(fitness.GAIN_DB - 6, fitness.GAIN_DB + 2))
    ax[1].grid(True, which="both", alpha=0.3)
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(OUT / "compare_ne5532.png", dpi=120)
    print(f"\nPlot: {OUT / 'compare_ne5532.png'}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tgt = fitness.load_target()
    saved = OUT / "compare_ne5532.json"
    if "--plot-only" in sys.argv:
        d = json.loads(saved.read_text())
        gen, ne = ({k: np.array(v) for k, v in d[m].items()} for m in ("generic", "ne5532"))
        plot(gen, ne, tgt)
        return
    src = Path(args[0]) if args else OUT / "best.json"
    design = Design(json.loads(src.read_text())["values"])
    gen = measure(design, "generic")
    ne = measure(design, "ne5532")
    saved.write_text(json.dumps({m: {k: np.asarray(v).tolist() for k, v in d.items()}
                                 for m, d in (("generic", gen), ("ne5532", ne))}))

    for name, m in (("generic", gen), ("NE5532", ne)):
        g1k = np.interp(1000, m["f"], m["mag"])
        band = (m["f"] >= 20) & (m["f"] <= 20e3)
        flat = np.max(np.abs(m["mag"][band] - g1k))
        print(f"{name:9s} gain {g1k:5.2f} dB  flatness +/-{flat:.2f} dB  "
              f"SNR {m['snr']:.1f} dB")

    print("\n  Vout    |   generic: THD%    H2     H3   |  NE5532: THD%   H2     H3   |  tube H2   H3")
    tv = fitness.target_at(tgt, gen["vout"])
    for i in range(len(LEVELS)):
        print(f"  {gen['vout'][i]:5.2f}V  |  {gen['thd'][i] * 100:9.3f} {gen['h'][i, 0]:6.1f} "
              f"{gen['h'][i, 1]:6.1f}  |  {ne['thd'][i] * 100:9.3f} {ne['h'][i, 0]:6.1f} "
              f"{ne['h'][i, 1]:6.1f}  |  {tv[i, 0]:6.1f} {tv[i, 1]:6.1f}")
    plot(gen, ne, tgt)


if __name__ == "__main__":
    main()
