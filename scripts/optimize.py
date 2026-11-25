"""Optimise the opamp preamp with a genetic algorithm (pymoo), followed by a
local search step over neighbouring E24 values.

Usage:   python scripts/optimize.py [--pop 48] [--gen 40] [--workers 8] [--seed 1]
Output:  out/best.json (+ progress in out/ga_log.csv)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.callback import Callback
from pymoo.core.problem import ElementwiseProblem
from pymoo.parallelization import StarmapParallelization
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.repair.rounding import RoundingRepair
from pymoo.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import fitness  # noqa: E402
from circuitbuilder.candidate import GENES, N_GENES, UPPER, Design  # noqa: E402

OUT = ROOT / "out"

HAND = dict(RF1=10e3, RG1=10e3, RA=10e3, RB=10e3, RBA=12e3, RBB=12e3,
            RS0=10e3, RSA=1e3, RSB=1e3, RF2=15e3, N=4)


def to_genes(values: dict) -> np.ndarray:
    return np.array([int(np.argmin(np.abs(vals - values[name]))) for name, vals in GENES])


def cost_of(genes, tgt) -> float:
    return fitness.evaluate(Design.from_genes(genes), tgt).cost


class PreampProblem(ElementwiseProblem):
    def __init__(self, tgt, **kw):
        super().__init__(n_var=N_GENES, n_obj=1, xl=np.zeros(N_GENES), xu=UPPER, vtype=int, **kw)
        self.tgt = tgt

    def _evaluate(self, x, out, *args, **kwargs):
        out["F"] = cost_of(x, self.tgt)


class Logger(Callback):
    def __init__(self, t0):
        super().__init__()
        self.t0 = t0
        self.log = open(OUT / "ga_log.csv", "w", buffering=1)
        self.log.write("gen,evals,best,median,seconds\n")

    def notify(self, algorithm):
        f = algorithm.pop.get("F")[:, 0]
        gen, n = algorithm.n_gen, algorithm.evaluator.n_eval
        el = time.time() - self.t0
        self.log.write(f"{gen},{n},{f.min():.4f},{np.median(f):.4f},{el:.0f}\n")
        print(f"gen {gen:3d}  evals {n:5d}  best {f.min():8.3f}  median {np.median(f):9.3f}"
              f"  ({el:.0f} s)", flush=True)
        best = algorithm.opt[0].X
        save(Design.from_genes(best), algorithm.opt[0].F[0], "ga")


def save(design: Design, cost: float, stage: str) -> None:
    (OUT / "best.json").write_text(json.dumps(
        {"stage": stage, "cost": float(cost), "values": design.values}, indent=1))


def local_search(genes, cost, tgt, pool) -> tuple[np.ndarray, float]:
    """Try the neighbouring E24 value (+/-1, +/-2) for each gene; keep the best improvement."""
    improved = True
    while improved:
        improved = False
        trials = []
        for i in range(N_GENES):
            for d in (-2, -1, 1, 2):
                g = genes.copy()
                g[i] = np.clip(g[i] + d, 0, UPPER[i])
                if g[i] != genes[i]:
                    trials.append(g)
        costs = pool.starmap(cost_of, [(g, tgt) for g in trials])
        k = int(np.argmin(costs))
        if costs[k] < cost - 1e-3:
            genes, cost = trials[k], costs[k]
            improved = True
            print(f"  local: cost {cost:.3f}", flush=True)
            save(Design.from_genes(genes), cost, "local")
    return genes, cost


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pop", type=int, default=48)
    ap.add_argument("--gen", type=int, default=40)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    tgt = fitness.load_target()
    rng = np.random.default_rng(args.seed)
    init = rng.integers(0, UPPER + 1, size=(args.pop, N_GENES))
    init[0] = to_genes(HAND)
    # earlier results as starting points, plus symmetric variants (branch B = branch A)
    names = [n for n, _ in GENES]
    idx = {n: i for i, n in enumerate(names)}
    seeds = [to_genes(json.loads(p.read_text())["values"])
             for p in sorted((ROOT / "designs").glob("*.json"))]
    row = 1
    for s in seeds:
        init[row] = s
        row += 1
    base = seeds + [to_genes(HAND)]
    n_sym = args.pop // 3
    for k in range(n_sym):
        g = base[k % len(base)].copy()
        for a, b in (("RA", "RB"), ("RBA", "RBB"), ("RSA", "RSB")):
            g[idx[b]] = g[idx[a]]
        if k >= len(base):  # mutate, except for the exact symmetric copies
            mask = rng.random(N_GENES) < 0.5
            g = np.clip(g + mask * rng.integers(-3, 4, N_GENES), 0, UPPER)
        init[row] = g
        row += 1

    t0 = time.time()
    with Pool(args.workers) as pool:
        problem = PreampProblem(tgt, elementwise_runner=StarmapParallelization(pool.starmap))
        algo = GA(
            pop_size=args.pop,
            sampling=init.astype(float),
            crossover=SBX(prob=0.9, eta=8, vtype=float, repair=RoundingRepair()),
            mutation=PM(eta=8, vtype=float, repair=RoundingRepair()),
            eliminate_duplicates=True,
        )
        res = minimize(problem, algo, ("n_gen", args.gen), seed=args.seed,
                       callback=Logger(t0), verbose=False)
        genes = np.round(res.X).astype(int)
        print(f"GA done: cost {res.F[0]:.3f}. Local refinement...", flush=True)
        genes, cost = local_search(genes, float(res.F[0]), tgt, pool)

    design = Design.from_genes(genes)
    save(design, cost, "final")
    print(f"\nDone in {time.time() - t0:.0f} s, cost {cost:.3f}\n{design.bom()}")


if __name__ == "__main__":
    main()
