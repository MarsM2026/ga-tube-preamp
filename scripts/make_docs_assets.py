"""Collect all data and images for the documentation/web page in docs/.

  docs/data/*.json, *.csv   - raw numbers (for interactive charts)
  docs/img/*.png            - ready-made charts

Requires that these have been run first: run_reference/build_target (out/target.json),
verify_build.py, montecarlo.py, sensitivity.py, compare_opamp.py and the GA runs
(out/optimize*.log).

Usage:  python scripts/make_docs_assets.py
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import build, fitness  # noqa: E402

OUT = ROOT / "out"
DATA = ROOT / "docs" / "data"
IMG = ROOT / "docs" / "img"


def ga_logs() -> dict:
    runs = {}
    for i, name in ((1, "optimize.log"), (2, "optimize2.log"), (3, "optimize3.log")):
        f = OUT / name
        if not f.exists():
            continue
        rows = []
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            # the logs of the original runs were written in Dutch ("beste"/"mediaan")
            m = re.match(r"gen\s+(\d+)\s+evals\s+(\d+)\s+(?:best|beste)\s+([\d.]+)\s+(?:median|mediaan)\s+([\d.]+)\s+\((\d+) s\)", line)
            if m:
                g, e, b, med, s = m.groups()
                rows.append({"gen": int(g), "evals": int(e), "best": float(b), "median": float(med),
                             "seconds": int(s)})
        runs[f"run{i}"] = rows
    return runs


def bom_rows(variant: str = "tht"):
    """Parts list grouped by value/footprint, for PCB variant tht or smd."""
    build.set_variant(variant)
    groups = defaultdict(list)
    info = {}
    for p in build.all_parts():
        if p.kind == "OPAMP_PWR":
            continue
        ref = p.extra.get("ic", p.ref) if p.kind == "OPAMP" else p.ref
        key = (p.kind, p.value, p.footprint)
        if ref not in groups[key]:
            groups[key].append(ref)
        info[key] = p.descr.split(",")[0] if p.kind in ("R",) else p.descr
    kind_name = {"R": "Resistor metal film 1% 0.25 W", "R_POT": "Trimmer multi-turn (Bourns 3296W)",
                 "C": "Capacitor", "CP": "Electrolytic (polarised)", "C_NP": "Electrolytic bipolar (NP)",
                 "D": "Diode", "OPAMP": "Opamp NE5532P (DIP-8) + IC socket",
                 "SIG_CONN": "Pin header 1x2 2.54 mm", "PWR_CONN": "Screw terminal 3-pin 5.08 mm"}
    if variant == "smd":
        kind_name.update({"R": "Resistor thick film 1% 0805", "R_POT": "Trimmer multi-turn SMD (Bourns 3224W)",
                          "C": "Capacitor SMD", "CP": "Electrolytic SMD (polarised)",
                          "C_NP": "Electrolytic SMD bipolar (NP)", "D": "Diode SMD (SOD-323)",
                          "OPAMP": "Opamp NE5532 (SOIC-8)",
                          "SIG_CONN": "Screw terminal 2-pin 5.08 mm (through-hole)",
                          "PWR_CONN": "Screw terminal 3-pin 5.08 mm (through-hole)"})
    order = ["OPAMP", "D", "R", "R_POT", "C", "CP", "C_NP", "PWR_CONN", "SIG_CONN"]
    rows = []
    for key in sorted(groups, key=lambda k: (order.index(k[0]), k[1])):
        kind, value, fp = key
        refs = sorted(groups[key], key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
        rows.append({"qty": len(refs), "value": value, "type": kind_name[kind],
                     "references": " ".join(refs), "footprint": fp})
    return rows


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    # --- target (12AX7) and design values
    shutil.copy(OUT / "target.json", DATA / "tube_12ax7_harmonics.json")
    shutil.copy(ROOT / "designs" / "final.json", DATA / "final_design.json")
    for name in ("run1", "run2", "run3"):
        shutil.copy(ROOT / "designs" / f"{name}.json", DATA / f"design_{name}.json")
    for name in ("verify_build.json", "montecarlo.json", "sensitivity.json", "compare_ne5532.json"):
        if (OUT / name).exists():
            shutil.copy(OUT / name, DATA / name)

    # --- GA convergence
    runs = ga_logs()
    (DATA / "ga_convergence.json").write_text(json.dumps(runs, indent=1))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    notes = {"run1": "run 1: random start", "run2": "run 2: time-outs (220 µF)",
             "run3": "run 3: corrected, seeded from runs 1 and 2"}
    for k, rows in runs.items():
        ax.semilogy([r["gen"] for r in rows], [r["best"] for r in rows], "o-", ms=3, label=notes[k])
    ax.set(title="Genetic algorithm: best cost per generation", xlabel="generation",
           ylabel="cost (lower = better)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "ga_convergence.png", dpi=130)
    plt.close(fig)

    # --- copies of charts
    for src, dst in (("reference.png", "tube_reference.png"), ("verify_build.png", "result_harmonics.png"),
                     ("montecarlo.png", "tolerance_montecarlo.png"),
                     ("compare_ne5532.png", "ne5532_vs_generic.png")):
        if (OUT / src).exists():
            shutil.copy(OUT / src, IMG / dst)

    # --- parts list
    hw = ROOT / "hardware"
    for variant, stem in (("tht", "bom"), ("smd", "bom_smd")):
        rows = bom_rows(variant)
        with open(DATA / f"{stem}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
            w.writeheader()
            w.writerows(rows)
        (DATA / f"{stem}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
        shutil.copy(DATA / f"{stem}.csv", hw / f"{stem}.csv")
    build.set_variant("tht")

    # --- key figures in one file (for the web page)
    vb = json.loads((OUT / "verify_build.json").read_text())
    mc = json.loads((OUT / "montecarlo.json").read_text())
    lv = {round(x["vout_rms"], 1): x for x in vb["levels"]}
    one = min(vb["levels"], key=lambda x: abs(x["vout_rms"] - 1.0))
    key = {
        "gain_db": round(vb["gain_db"], 2),
        "flatness_20Hz_20kHz_db": round(vb["flat_db"], 2),
        "snr_db_re_1Vrms": round(vb["snr_db"], 1),
        "psrr_plus15V_100Hz_db": round(vb["psrr_db"]["+15V"]["100Hz"], 1),
        "h2_at_1Vrms_db": round(one["h2"], 1), "h2_tube_at_1Vrms_db": round(one["tube_h2"], 1),
        "h3_at_1Vrms_db": round(one["h3"], 1), "h3_tube_at_1Vrms_db": round(one["tube_h3"], 1),
        "thd_at_1Vrms_percent": round(one["thd"] * 100, 3),
        "max_output_Vrms": 7.0,
        "supply": "+/-15 V regulated",
        "opamps": "3x NE5532",
        "tolerance_h3_sd_untrimmed_db": round(mc["stats"]["h3_4v"]["untrimmed"]["sd"], 2),
        "tolerance_h2_sd_db": round(mc["stats"]["h2_1v"]["untrimmed"]["sd"], 2),
        "tolerance_gain_sd_db": round(mc["stats"]["gain"]["untrimmed"]["sd"], 2),
        "ga_evaluations_total": sum(r[-1]["evals"] for r in runs.values() if r),
    }
    for variant, d in (("tht", "kicad"), ("smd", "kicad_smd")):
        f = ROOT / "hardware" / d / "board_size.json"
        if f.exists():
            bs = json.loads(f.read_text())
            key[f"pcb_{variant}_mm"] = f"{bs['W']:.0f} x {bs['H']:.0f}"
    (DATA / "key_figures.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(key, indent=1, ensure_ascii=False))
    print(f"\nData: {DATA}\nImages: {IMG}")


if __name__ == "__main__":
    main()
