"""Rapport van het beste ontwerp (out/best.json): onderdelenlijst, vergelijking met de
12AX7-referentie en een losse netlist (out/best.cir).

Gebruik:  python scripts/report.py [pad/naar/ontwerp.json]
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


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / "best.json"
    design = Design(json.loads(src.read_text())["values"])
    tgt = fitness.load_target()

    # dichter raster van niveaus voor de plot
    levels = np.geomspace(0.05, 9, 14)
    amps = levels * np.sqrt(2) / 10 ** (fitness.GAIN_DB / 20)
    tran, ac, nz = spice.run_multi(design.netlist(amps), [
        (analysis.tran_command(1000, 20, 10), [f"v(out{i})" for i in range(len(amps))]),
        ("ac dec 20 5 200k", ["v(out_ac)", "v(in_ac)"]),
        ("noise v(out_ac) VAC dec 10 20 20k\nsetplot noise2", ["onoise_total"]),
    ])
    harms = [analysis.harmonics_from_wave(tran[:, 0], tran[:, 1 + i], 1000, 10, amplitude_in=a)
             for i, a in enumerate(amps)]
    vout = np.array([h.vout_rms for h in harms])
    meas = np.array([h.levels_db[:4] for h in harms])
    thd = np.array([h.thd for h in harms])
    f, mag, _ = analysis.ac_from_data(ac)
    snr = 20 * np.log10(1 / nz[0, 1])

    r = fitness.evaluate(design, tgt)
    print("Onderdelen:\n" + design.bom())
    print(f"\nKosten {r.cost:.2f}   versterking {r.gain_db:.2f} dB   vlakheid 20 Hz-20 kHz "
          f"+/-{r.flat_db:.2f} dB   S/R {snr:.1f} dB (t.o.v. 1 V rms, 20 kHz)")
    print("Kostendelen:", {k: round(float(v), 2) for k, v in r.parts.items()})
    print("\n  Vout(rms)   THD%    H2     H3     H4     H5   | buis H2   H3")
    tv = fitness.target_at(tgt, vout)
    for v, t, h, ht in zip(vout, thd, meas, tv):
        print(f"  {v:7.2f}  {t * 100:6.3f}" + "".join(f" {x:6.1f}" for x in h)
              + f"   | {ht[0]:6.1f} {ht[1]:6.1f}")

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    tx = np.array(tgt["vout_rms"])
    th = np.array(tgt["h"])
    colors = ["C0", "C1", "C2", "C3"]
    for k in range(3):
        ax[0].semilogx(tx, th[:, k], "--", color=colors[k], alpha=0.7, label=f"12AX7 H{k + 2}")
        ax[0].semilogx(vout, meas[:, k], "o-", color=colors[k], label=f"opamp H{k + 2}")
    ax[0].set(title="Harmonischen t.o.v. grondtoon (1 kHz)", xlabel="Vout [V rms]",
              ylabel="dB", ylim=(-110, -10), xlim=(0.05, 10))
    ax[0].grid(True, which="both", alpha=0.3)
    ax[0].legend(fontsize=8, ncol=2)
    ax[1].semilogx(f, mag)
    ax[1].set(title="Frequentierespons opamp-voorversterker", xlabel="Hz", ylabel="dB",
              ylim=(fitness.GAIN_DB - 6, fitness.GAIN_DB + 2))
    ax[1].axvspan(20, 20e3, color="C2", alpha=0.08)
    ax[1].grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "best.png", dpi=120)

    cir = OUT / "best.cir"
    cir.write_text(design.netlist([1.0]).replace(
        spice.include("parts.lib"), (ROOT / "circuitbuilder/models/parts.lib").read_text()))
    print(f"\nPlot: {OUT / 'best.png'}\nNetlist: {cir}")


if __name__ == "__main__":
    main()
