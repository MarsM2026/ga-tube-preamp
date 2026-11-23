"""Evalueer één handmatig gekozen ontwerp (handig om de fitness te controleren)."""

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from circuitbuilder import fitness  # noqa: E402
from circuitbuilder.candidate import Design  # noqa: E402

tgt = fitness.load_target()
print("doel H2..H5 @1V:", np.round(fitness.target_at(tgt, np.array([1.0]))[0], 1))
vals = dict(RF1=10e3, RG1=10e3, RA=10e3, RB=10e3, RBA=12e3, RBB=12e3,
            RS0=10e3, RSA=1e3, RSB=1e3, RF2=15e3, N=4)
if len(sys.argv) > 1:  # pad naar een ontwerp-JSON (zoals designs/run1.json)
    vals.update(json.loads(Path(sys.argv[1]).read_text())["values"])
t = time.time()
r = fitness.evaluate(Design(vals), tgt)
print(f"evaluatie: {time.time() - t:.2f} s")
print(f"kosten {r.cost:.2f}  gain {r.gain_db:.2f} dB  vlakheid {r.flat_db:.2f} dB  SNR {r.snr_db:.1f} dB")
print("delen:", {k: round(v, 2) for k, v in r.parts.items()}, r.error)
for v, h, ht in zip(r.vout_rms, r.h, r.h_target):
    print(f"  {v:6.2f} Vrms  gemeten {np.round(h, 1)}  doel {np.round(ht, 1)}")
