"""Gevoeligheidsanalyse: hoeveel veranderen versterking, H2 en H3 als één onderdeel
afwijkt? Bepaalt waar een trimpotmeter het meeste effect heeft.

Gebruik:  python scripts/sensitivity.py [ontwerp.json]
Resultaat: tabel + out/sensitivity.json
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import fitness  # noqa: E402
from circuitbuilder.candidate import FIXED, Design  # noqa: E402

RESISTORS = ["RF1", "RG1", "RA", "RB", "RBA", "RBB", "RS0", "RSA", "RSB", "RF2", "RI1", "RI2"]
I1V, I4V = 2, 4  # indices in fitness.VOUT_LEVELS (1 V en 4 V rms)


def metrics(values: dict) -> dict:
    r = fitness.evaluate(Design(values), fitness.load_target())
    h = np.array(r.h)
    return {"gain": r.gain_db, "h2_1v": h[I1V, 0], "h3_1v": h[I1V, 1],
            "h2_4v": h[I4V, 0], "h3_4v": h[I4V, 1], "cost": r.cost}


def variants(base: dict) -> list[tuple[str, dict]]:
    out = [("nominaal", dict(base))]
    full = {**FIXED, **base}
    for name in RESISTORS:
        out.append((f"{name} +1%", {**base, name: full[name] * 1.01}))
    n = int(base["N"])
    out.append(("diodes tak A IS x1.5", {**base, **{f"IS_a{i}": 1.5 for i in range(n)}}))
    out.append(("diodes tak B IS x1.5", {**base, **{f"IS_b{i}": 1.5 for i in range(n)}}))
    out.append(("1 diode tak B IS x1.5", {**base, "IS_b0": 1.5}))
    return out


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "designs" / "run3.json"
    base = json.loads(src.read_text())["values"]
    vs = variants(base)
    with Pool(8) as pool:
        res = pool.map(metrics, [v for _, v in vs])
    nom = res[0]
    keys = ["gain", "h2_1v", "h3_1v", "h2_4v", "h3_4v"]
    print(f"{'variant':24s}  dGain   dH2@1V  dH3@1V  dH2@4V  dH3@4V   kosten")
    table = []
    for (name, _), m in zip(vs, res):
        d = {k: m[k] - nom[k] for k in keys}
        table.append({"variant": name, **{k: float(m[k]) for k in keys}, "cost": float(m["cost"]),
                      **{f"d_{k}": float(d[k]) for k in keys}})
        print(f"{name:24s}" + "".join(f"  {d[k]:+6.2f}" for k in keys) + f"   {m['cost']:6.2f}")
    (ROOT / "out" / "sensitivity.json").write_text(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
