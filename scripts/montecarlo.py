"""Monte Carlo tolerance analysis of the final design.

Every virtual board gets random deviations:
  - resistors: uniform +/-1 % (metal film), except the trimmer chain RB
  - diodes: saturation current lognormal (sigma 0.25, approx. +/-11 mV threshold voltage)
For each board we compute H2/H3 and gain twice:
  1. "untrimmed": trimmer set so that RB = 4.70 kOhm (set with a multimeter)
  2. "trimmed":   trimmer set so that H3 at 4 V rms is back at the nominal level
                  (as when adjusting with a sound card + REW)

Usage:   python scripts/montecarlo.py [--n 24] [--workers 4] [--plot-only]
Output:  out/montecarlo.json and out/montecarlo.png
         (--plot-only redraws the plot from an existing out/montecarlo.json)
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
from circuitbuilder import fitness  # noqa: E402
from circuitbuilder.candidate import FIXED, Design  # noqa: E402

FINAL = json.loads((ROOT / "designs" / "final.json").read_text())
TRIM = FINAL["trim"]["RB"]
VARY = ["RF1", "RG1", "RA", "RBA", "RBB", "RS0", "RSA", "RSB", "RF2", "RIN", "RI1", "RI2"]
I1V, I4V = 2, 4


def measure(values: dict):
    r = fitness.evaluate(Design(values), fitness.load_target())
    if r.error:
        return None
    h = np.array(r.h)
    return {"gain": r.gain_db, "h2_1v": h[I1V, 0], "h3_1v": h[I1V, 1],
            "h2_4v": h[I4V, 0], "h3_4v": h[I4V, 1]}


def sample(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    base = {**FIXED, **FINAL["values"]}
    v = dict(base)
    for k in VARY:
        v[k] = base[k] * (1 + rng.uniform(-0.01, 0.01))
    n = int(base["N"])
    for tag in "ab":
        for i in range(n):
            v[f"IS_{tag}{i}"] = float(np.exp(rng.normal(0, 0.25)))
    untrimmed = measure(v)
    out = {"seed": seed, "untrimmed": untrimmed, "trimmed": None, "rb_trim": None}
    if untrimmed is None:
        return out
    # trimming: H3@4V is nearly linear in RB -> secant step towards nominal
    target = NOMINAL["h3_4v"]
    rb0, h0 = TRIM["nominal"], untrimmed["h3_4v"]
    rb1 = rb0 * 0.98
    m1 = measure({**v, "RB": rb1})
    if m1 is None:
        return out
    slope = (m1["h3_4v"] - h0) / (rb1 - rb0)
    rb = float(np.clip(rb0 + (target - h0) / slope, TRIM["fixed"], TRIM["fixed"] + TRIM["pot"]))
    out["trimmed"] = measure({**v, "RB": rb})
    out["rb_trim"] = rb
    return out


NOMINAL: dict | None = None  # set per worker process via init_worker


def init_worker(nominal):
    global NOMINAL
    NOMINAL = nominal


def plot(summary: dict) -> None:
    ok = [r for r in summary["samples"] if r["untrimmed"] and r["trimmed"]]
    nominal = summary["nominal"]
    fig, ax = plt.subplots(1, 3, figsize=(13, 4))
    for a, k, title in zip(ax, ["gain", "h2_1v", "h3_4v"],
                           ["Gain [dB]", "H2 at 1 V rms [dB]", "H3 at 4 V rms [dB]"]):
        u = [r["untrimmed"][k] for r in ok]
        t = [r["trimmed"][k] for r in ok]
        a.hist([u, t], bins=10, label=["untrimmed (RB = 4k70)", "trimmed"])
        a.axvline(nominal[k], color="k", ls="--", lw=1, label="nominal")
        a.set(title=title)
        a.grid(alpha=0.3)
    ax[0].legend(fontsize=8)
    fig.suptitle(f"Monte Carlo: {len(ok)} boards, 1 % resistors, diode spread")
    fig.tight_layout()
    fig.savefig(ROOT / "out" / "montecarlo.png", dpi=120)
    print(f"Plot: {ROOT / 'out' / 'montecarlo.png'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args()
    if args.plot_only:
        plot(json.loads((ROOT / "out" / "montecarlo.json").read_text()))
        return
    nominal = measure({**FIXED, **FINAL["values"]})
    print("nominal:", {k: round(v, 2) for k, v in nominal.items()})
    with Pool(args.workers, initializer=init_worker, initargs=(nominal,)) as pool:
        res = pool.map(sample, range(args.n))
    ok = [r for r in res if r["untrimmed"] and r["trimmed"]]
    print(f"{len(ok)}/{len(res)} boards succeeded")
    summary = {"nominal": nominal, "n": len(ok), "samples": res, "stats": {}}
    keys = ["gain", "h2_1v", "h3_1v", "h2_4v", "h3_4v"]
    print(f"\n{'quantity':8s} {'nominal':>9s} | untrimmed: mean  +/-sd   min..max | trimmed: mean  +/-sd   min..max")
    for k in keys:
        st = {}
        line = f"{k:8s} {nominal[k]:9.2f} |"
        for mode in ("untrimmed", "trimmed"):
            x = np.array([r[mode][k] for r in ok])
            st[mode] = {"mean": float(x.mean()), "sd": float(x.std()), "min": float(x.min()),
                        "max": float(x.max())}
            line += f" {x.mean():8.2f} {x.std():5.2f} {x.min():7.2f}..{x.max():6.2f} |"
        summary["stats"][k] = st
        print(line)
    rbs = np.array([r["rb_trim"] for r in ok])
    print(f"\nTrimmer setting RB: {rbs.min():.0f}..{rbs.max():.0f} Ohm (range {TRIM['fixed']:.0f}.."
          f"{TRIM['fixed'] + TRIM['pot']:.0f})")
    summary["rb_trim_range"] = [float(rbs.min()), float(rbs.max())]
    (ROOT / "out" / "montecarlo.json").write_text(json.dumps(summary, indent=1))
    plot(summary)


if __name__ == "__main__":
    main()
