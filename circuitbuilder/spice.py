"""Dunne koppeling met ngspice in batchmode.

Een netlist wordt als tekst aangeleverd; we voegen een .control-blok toe dat de
gevraagde analyses draait en de vectoren met `wrdata` naar tekstbestanden schrijft.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "circuitbuilder" / "models"


class SpiceError(RuntimeError):
    pass


def find_ngspice() -> str:
    env = os.environ.get("NGSPICE")
    if env:
        return env
    local = ROOT / "tools" / "Spice64" / "bin" / "ngspice_con.exe"
    if local.exists():
        return str(local)
    for name in ("ngspice_con", "ngspice"):
        found = shutil.which(name)
        if found:
            return found
    raise SpiceError("ngspice niet gevonden (zet NGSPICE of installeer in tools/Spice64)")


def run_multi(netlist: str, jobs: list[tuple[str, list[str]]],
              timeout: float = 120.0) -> list[np.ndarray]:
    """Draai meerdere analyses in één ngspice-proces.

    `jobs` is een lijst van (commando's, vectoren). Het commando mag uit meerdere
    regels bestaan (bijv. "noise ...\\nsetplot noise2"). Per job komt een array terug:
    kolom 0 = x-as, daarna de vectoren (complexe vectoren als re/im-paren).
    """
    with tempfile.TemporaryDirectory(prefix="cb_") as tmp:
        tmp = Path(tmp)
        lines = [".control", "set wr_singlescale", "set wr_vecnames"]
        outs = []
        for i, (cmd, vectors) in enumerate(jobs):
            out = tmp / f"out{i}.txt"
            outs.append(out)
            lines.append(cmd)
            lines.append(f"wrdata {out.as_posix()} {' '.join(vectors)}")
        lines += ["quit", ".endc"]
        body = netlist.rstrip()
        if body.lower().endswith(".end"):
            body = body[: -len(".end")]
        cir = tmp / "circuit.cir"
        cir.write_text(body + "\n" + "\n".join(lines) + "\n.end\n", encoding="ascii")
        proc = subprocess.run(
            [find_ngspice(), "-b", str(cir)],
            capture_output=True, text=True, timeout=timeout, cwd=tmp,
        )
        results = []
        for out in outs:
            if not out.exists():
                raise SpiceError(f"ngspice faalde:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")
            data = np.loadtxt(out, skiprows=1, ndmin=2)
            if data.size == 0:
                raise SpiceError("ngspice gaf geen data terug")
            results.append(data)
        return results


def run(netlist: str, analysis: str, vectors: list[str], timeout: float = 120.0) -> np.ndarray:
    return run_multi(netlist, [(analysis, vectors)], timeout)[0]


def include(name: str) -> str:
    return f'.include "{(MODELS / name).as_posix()}"'
