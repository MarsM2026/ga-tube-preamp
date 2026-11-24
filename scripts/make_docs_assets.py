"""Verzamel alle data en afbeeldingen voor de documentatie/webpagina in docs/.

  docs/data/*.json, *.csv   - ruwe cijfers (voor interactieve grafieken)
  docs/img/*.png            - kant-en-klare grafieken

Vereist dat eerst gedraaid zijn: run_reference/build_target (out/target.json),
verify_build.py, montecarlo.py, sensitivity.py en de GA-runs (out/optimize*.log).

Gebruik:  python scripts/make_docs_assets.py
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
            m = re.match(r"gen\s+(\d+)\s+evals\s+(\d+)\s+beste\s+([\d.]+)\s+mediaan\s+([\d.]+)\s+\((\d+) s\)", line)
            if m:
                g, e, b, med, s = m.groups()
                rows.append({"gen": int(g), "evals": int(e), "best": float(b), "median": float(med),
                             "seconds": int(s)})
        runs[f"run{i}"] = rows
    return runs


def bom_rows(variant: str = "tht"):
    """Onderdelenlijst gegroepeerd per waarde/footprint, voor printvariant tht of smd."""
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
    kind_name = {"R": "Weerstand metaalfilm 1% 0,25 W", "R_POT": "Trimpot meerslagen (Bourns 3296W)",
                 "C": "Condensator", "CP": "Elco (gepolariseerd)", "C_NP": "Elco bipolair (NP)",
                 "D": "Diode", "OPAMP": "Opamp NE5532P (DIP-8) + IC-voet",
                 "SIG_CONN": "Pinheader 1x2 2,54 mm", "PWR_CONN": "Schroefklem 3-polig 5,08 mm"}
    if variant == "smd":
        kind_name.update({"R": "Weerstand dikfilm 1% 0805", "R_POT": "Trimpot meerslagen SMD (Bourns 3224W)",
                          "C": "Condensator SMD", "CP": "Elco SMD (gepolariseerd)",
                          "C_NP": "Elco SMD bipolair (NP)", "D": "Diode SMD (SOD-323)",
                          "OPAMP": "Opamp NE5532 (SOIC-8)",
                          "SIG_CONN": "Schroefklem 2-polig 5,08 mm (through-hole)",
                          "PWR_CONN": "Schroefklem 3-polig 5,08 mm (through-hole)"})
    order = ["OPAMP", "D", "R", "R_POT", "C", "CP", "C_NP", "PWR_CONN", "SIG_CONN"]
    rows = []
    for key in sorted(groups, key=lambda k: (order.index(k[0]), k[1])):
        kind, value, fp = key
        refs = sorted(groups[key], key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0)))
        rows.append({"aantal": len(refs), "waarde": value, "soort": kind_name[kind],
                     "referenties": " ".join(refs), "footprint": fp})
    return rows


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    # --- doel (12AX7) en ontwerpwaarden
    shutil.copy(OUT / "target.json", DATA / "tube_12ax7_harmonics.json")
    shutil.copy(ROOT / "designs" / "final.json", DATA / "final_design.json")
    for name in ("run1", "run2", "run3"):
        shutil.copy(ROOT / "designs" / f"{name}.json", DATA / f"design_{name}.json")
    for name in ("verify_build.json", "montecarlo.json", "sensitivity.json"):
        if (OUT / name).exists():
            shutil.copy(OUT / name, DATA / name)

    # --- GA-convergentie
    runs = ga_logs()
    (DATA / "ga_convergence.json").write_text(json.dumps(runs, indent=1))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    notes = {"run1": "run 1: willekeurige start", "run2": "run 2: time-outs (220 µF)",
             "run3": "run 3: gecorrigeerd, start vanuit run 1 en 2"}
    for k, rows in runs.items():
        ax.semilogy([r["gen"] for r in rows], [r["best"] for r in rows], "o-", ms=3, label=notes[k])
    ax.set(title="Genetisch algoritme: beste kosten per generatie", xlabel="generatie",
           ylabel="kosten (lager = beter)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG / "ga_convergentie.png", dpi=130)
    plt.close(fig)

    # --- kopieën van grafieken
    for src, dst in (("reference.png", "buis_referentie.png"), ("verify_build.png", "resultaat_harmonischen.png"),
                     ("montecarlo.png", "tolerantie_montecarlo.png"),
                     ("compare_ne5532.png", "ne5532_vs_generiek.png")):
        if (OUT / src).exists():
            shutil.copy(OUT / src, IMG / dst)

    # --- onderdelenlijst
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

    # --- kerncijfers in één bestand (voor de webpagina)
    vb = json.loads((OUT / "verify_build.json").read_text())
    mc = json.loads((OUT / "montecarlo.json").read_text())
    lv = {round(x["vout_rms"], 1): x for x in vb["levels"]}
    one = min(vb["levels"], key=lambda x: abs(x["vout_rms"] - 1.0))
    key = {
        "versterking_db": round(vb["gain_db"], 2),
        "vlakheid_20Hz_20kHz_db": round(vb["flat_db"], 2),
        "signaal_ruis_db_ref_1Vrms": round(vb["snr_db"], 1),
        "psrr_plus15V_100Hz_db": round(vb["psrr_db"]["+15V"]["100Hz"], 1),
        "h2_bij_1Vrms_db": round(one["h2"], 1), "h2_buis_bij_1Vrms_db": round(one["tube_h2"], 1),
        "h3_bij_1Vrms_db": round(one["h3"], 1), "h3_buis_bij_1Vrms_db": round(one["tube_h3"], 1),
        "thd_bij_1Vrms_procent": round(one["thd"] * 100, 3),
        "max_uitgang_Vrms": 7.0,
        "voeding": "+/-15 V gestabiliseerd",
        "opamps": "3x NE5532P",
        "tolerantie_h3_sd_onafgeregeld_db": round(mc["stats"]["h3_4v"]["untrimmed"]["sd"], 2),
        "tolerantie_h2_sd_db": round(mc["stats"]["h2_1v"]["untrimmed"]["sd"], 2),
        "tolerantie_gain_sd_db": round(mc["stats"]["gain"]["untrimmed"]["sd"], 2),
        "ga_evaluaties_totaal": sum(r[-1]["evals"] for r in runs.values() if r),
    }
    for variant, d in (("tht", "kicad"), ("smd", "kicad_smd")):
        f = ROOT / "hardware" / d / "board_size.json"
        if f.exists():
            bs = json.loads(f.read_text())
            key[f"print_{variant}_mm"] = f"{bs['W']:.0f} x {bs['H']:.0f}"
    (DATA / "key_figures.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(key, indent=1, ensure_ascii=False))
    print(f"\nData: {DATA}\nAfbeeldingen: {IMG}")


if __name__ == "__main__":
    main()
