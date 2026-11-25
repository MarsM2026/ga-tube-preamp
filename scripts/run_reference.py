"""Characterise the 12AX7 reference stage: operating point, frequency response and
harmonics versus output level. Results in out/reference.png."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from circuitbuilder import analysis, spice  # noqa: E402
from circuitbuilder.reference import TubeStage  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "out"
OUT.mkdir(exist_ok=True)


def main() -> None:
    stage = TubeStage()

    op = spice.run(stage.ac_netlist(), "op", ["v(p)", "v(k)"])
    print(f"Operating point: Vplate = {op[0, 1]:.1f} V, Vcathode = {op[0, 2]:.2f} V, "
          f"Iplate = {op[0, 2] / stage.r_cathode * 1e3:.2f} mA")

    f, mag, _ = analysis.frequency_response(stage.ac_netlist(), 5, 200e3)
    g1k = np.interp(1000, f, mag)
    lo = f[np.argmax(mag > g1k - 3)]
    hi = f[len(mag) - 1 - np.argmax(mag[::-1] > g1k - 3)]
    print(f"Gain at 1 kHz: {g1k:.1f} dB, -3 dB band: {lo:.1f} Hz .. {hi / 1e3:.1f} kHz")

    amps = np.geomspace(0.005, 1.5, 14)
    res = analysis.harmonic_sweep(stage.sine_netlist, amps)
    print("\n  Vin(pk)  Vout(rms)    THD%     H2dB    H3dB    H4dB    H5dB")
    for r in res:
        print(f"  {r.amplitude_in:7.3f}  {r.fundamental / np.sqrt(2):8.3f}  {r.thd * 100:7.3f}"
              + "".join(f"  {x:6.1f}" for x in r.levels_db[:4]))

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].semilogx(f, mag)
    ax[0].set(title="12AX7 stage: frequency response", xlabel="Hz", ylabel="dB")
    ax[0].grid(True, which="both", alpha=0.3)
    vout = np.array([r.fundamental / np.sqrt(2) for r in res])
    for k in range(4):
        ax[1].semilogx(vout, [r.levels_db[k] for r in res], "o-", label=f"H{k + 2}")
    ax[1].set(title="Harmonics relative to fundamental (1 kHz)", xlabel="Vout [V rms]",
              ylabel="dB", ylim=(-110, 0))
    ax[1].grid(True, which="both", alpha=0.3)
    ax[1].legend()
    fig.tight_layout()
    fig.savefig(OUT / "reference.png", dpi=120)
    print(f"\nPlot: {OUT / 'reference.png'}")


if __name__ == "__main__":
    main()
