"""Verification of the circuit as built (circuitbuilder/build.py), with the NE5532
model, supply filter, output network and a 10 kOhm load.

Measures: gain, frequency response, harmonics compared with the 12AX7, noise and
power-supply rejection (PSRR) of the +15 V rail.

Usage:   python scripts/verify_build.py [--channel L] [--plot-only]
Output:  table + out/verify_build.json + out/verify_build.png
         (--plot-only redraws the plot from an existing out/verify_build.json)
"""

from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import analysis, build, fitness, spice  # noqa: E402

LEVELS = np.array([0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 6.0])  # V rms output
F0 = 1000.0
RESULT = ROOT / "out" / "verify_build.json"


def harm(args):
    ch, vout = args
    parts = build.all_parts()
    a = vout * np.sqrt(2) / 10 ** (fitness.GAIN_DB / 20)
    net = build.spice_netlist(parts, ch, f"VIN IN_{ch} 0 SIN(0 {a:g} {F0:g})")
    d = spice.run(net, analysis.tran_command(F0, 20, 10), [f"v(OUT_{ch})"], timeout=900)
    h = analysis.harmonics_from_wave(d[:, 0], d[:, 1], F0, 10, amplitude_in=a)
    return {"vout": h.vout_rms, "h": h.levels_db[:4].tolist(), "thd": h.thd}


def plot(result: dict, tgt: dict) -> None:
    vout = np.array([x["vout_rms"] for x in result["levels"]])
    meas = np.array([[x["h2"], x["h3"]] for x in result["levels"]])
    f = np.array(result["freq_response"]["f"])
    mag = np.array(result["freq_response"]["db"])
    g1k = result["gain_db"]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    tx, th = np.array(tgt["vout_rms"]), np.array(tgt["h"])
    for k, c in ((0, "C0"), (1, "C1")):
        ax[0].semilogx(tx, th[:, k], ":", color=c, lw=2, label=f"12AX7 H{k + 2}")
        ax[0].semilogx(vout, meas[:, k], "s-", color=c, label=f"opamp preamp H{k + 2}")
    ax[0].set(title="Harmonics at 1 kHz", xlabel="Output level [V rms]",
              ylabel="dB relative to fundamental", ylim=(-110, -20), xlim=(0.08, 8))
    ax[0].grid(True, which="both", alpha=0.3)
    ax[0].legend(fontsize=9)
    ax[1].semilogx(f, mag)
    ax[1].axvspan(20, 20e3, color="C2", alpha=0.08)
    ax[1].set(title="Frequency response (10 kΩ load)", xlabel="Hz", ylabel="dB",
              ylim=(g1k - 6, g1k + 2))
    ax[1].grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "out" / "verify_build.png", dpi=120)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="L")
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args()
    tgt = fitness.load_target()
    if args.plot_only:
        plot(json.loads(RESULT.read_text()), tgt)
        return
    ch = args.channel
    parts = build.all_parts()

    ac_net = build.spice_netlist(parts, ch, f"VIN IN_{ch} 0 DC 0 AC 1")
    ac, nz = spice.run_multi(ac_net, [
        ("ac dec 20 5 500k", [f"v(OUT_{ch})", f"v(IN_{ch})"]),
        (f"noise v(OUT_{ch}) VIN dec 10 20 20k\nsetplot noise2", ["onoise_total"]),
    ], timeout=900)
    f, mag, _ = analysis.ac_from_data(ac)
    g1k = float(np.interp(F0, f, mag))
    band = (f >= 20) & (f <= 20e3)
    flat = float(np.max(np.abs(mag[band] - g1k)))
    snr = float(20 * np.log10(1 / nz[0, 1]))

    psrr = {}
    # Only +15 V: it also feeds the diode bias. The opamp's own PSRR is not in the
    # macromodel (internal supply); NE5532 datasheet: approx. 100 dB.
    for rail, src in (("+15V", "VPOS VPOS15 0 DC 15 AC 1"),):
        net = build.spice_netlist(parts, ch, f"VIN IN_{ch} 0 DC 0")
        name = src.split()[0]
        net = "\n".join(src if ln.startswith(name + " ") else ln for ln in net.splitlines())
        d = spice.run(net, "ac dec 10 10 20k", [f"v(OUT_{ch})"])
        fr = d[:, 0]
        h = 20 * np.log10(np.abs(d[:, 1] + 1j * d[:, 2]))
        psrr[rail] = {"100Hz": float(-np.interp(100, fr, h)), "1kHz": float(-np.interp(1000, fr, h))}

    op = spice.run(ac_net, "op", [f"v(OUT_{ch})", f"v(OUT0_{ch})", f"v(VP_{ch})", f"v(A_{ch})",
                                   f"v(B_{ch})", f"v(V1_{ch})"])
    with Pool(4) as pool:
        hs = pool.map(harm, [(ch, v) for v in LEVELS])
    vout = np.array([h["vout"] for h in hs])
    meas = np.array([h["h"] for h in hs])
    tv = fitness.target_at(tgt, vout)

    print(f"Channel {ch} (NE5532, supply filter, output network, 10k load)")
    print(f"  gain at 1 kHz     : {g1k:.2f} dB")
    print(f"  flatness 20-20k   : +/-{flat:.2f} dB")
    print(f"  SNR (1 V rms, 20 kHz bandwidth, unweighted): {snr:.1f} dB")
    for r, v in psrr.items():
        print(f"  PSRR {r}: {v['100Hz']:.1f} dB @100 Hz, {v['1kHz']:.1f} dB @1 kHz")
    print(f"  operating point: VP={op[0, 3]:.2f} V  A={op[0, 4]:.3f} V  B={op[0, 5]:.3f} V  "
          f"V1={op[0, 6] * 1e3:.2f} mV  OUT0={op[0, 2] * 1e3:.2f} mV  OUT={op[0, 1] * 1e3:.2f} mV")
    print("\n  Vout    THD%     H2     H3     H4   | tube H2    H3")
    for v, h, t, th in zip(vout, meas, tv, [x["thd"] for x in hs]):
        print(f"  {v:5.2f}  {th * 100:6.3f}  {h[0]:6.1f} {h[1]:6.1f} {h[2]:6.1f}  | {t[0]:6.1f} {t[1]:6.1f}")

    result = {"channel": ch, "gain_db": g1k, "flat_db": flat, "snr_db": snr, "psrr_db": psrr,
              "op": {"VP": op[0, 3], "A": op[0, 4], "B": op[0, 5], "V1": op[0, 6], "OUT": op[0, 1]},
              "levels": [{"vout_rms": float(v), "thd": float(x["thd"]), "h2": float(h[0]),
                          "h3": float(h[1]), "h4": float(h[2]), "h5": float(h[3]),
                          "tube_h2": float(t[0]), "tube_h3": float(t[1])}
                         for v, h, t, x in zip(vout, meas, tv, hs)],
              "freq_response": {"f": f.tolist(), "db": mag.tolist()}}
    RESULT.write_text(json.dumps(result, indent=1))
    plot(result, tgt)


if __name__ == "__main__":
    main()
