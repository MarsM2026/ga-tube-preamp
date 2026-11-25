"""Target (12AX7 character) and cost function for candidate designs.

Lower cost = better. Terms:
  - gain at 1 kHz must be 10 dB
  - H2 and H3 versus output level equal to the tube stage
  - H4/H5 not above those of the tube
  - flat frequency response (20 Hz - 20 kHz)
  - noise: signal-to-noise ratio re 1 V rms at least 100 dB (unweighted)
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import analysis, spice
from .candidate import Design
from .reference import TubeStage

ROOT = Path(__file__).resolve().parent.parent
TARGET_FILE = ROOT / "out" / "target.json"

GAIN_DB = 10.0
F0 = 1000.0
VOUT_LEVELS = np.array([0.1, 0.3, 1.0, 2.0, 4.0, 7.0])  # V rms at the output
SNR_MIN_DB = 100.0
H_FLOOR = -100.0  # harmonics below this level count as equal


# -------------------------------------------------------------- target -------
def build_target(path: Path = TARGET_FILE) -> dict:
    stage = TubeStage()
    amps = np.geomspace(0.002, 1.5, 24)
    res = analysis.harmonic_sweep(stage.sine_netlist, amps, F0)
    tgt = {
        "vout_rms": [r.vout_rms for r in res],
        "h": [[float(x) for x in r.levels_db[:4]] for r in res],  # H2..H5
    }
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(tgt, indent=1))
    return tgt


def load_target() -> dict:
    if TARGET_FILE.exists():
        return json.loads(TARGET_FILE.read_text())
    return build_target()


def target_at(tgt: dict, vout_rms: np.ndarray) -> np.ndarray:
    """Target H2..H5 (dB) at the given output levels, interpolated on a log axis."""
    x = np.log10(tgt["vout_rms"])
    h = np.array(tgt["h"])
    xi = np.log10(vout_rms)
    return np.column_stack([np.interp(xi, x, h[:, k]) for k in range(h.shape[1])])


# ---------------------------------------------------------- evaluation -------
@dataclass
class Result:
    cost: float
    gain_db: float = np.nan
    vout_rms: list = field(default_factory=list)
    h: list = field(default_factory=list)          # measured H2..H5 per level
    h_target: list = field(default_factory=list)
    flat_db: float = np.nan                          # max deviation 20 Hz-20 kHz
    snr_db: float = np.nan
    parts: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in d.items()}


FAIL = 1e6
GAIN_SCREEN_DB = 4.0  # further than this from 10 dB: skip the transient simulation


def evaluate(design: Design, tgt: dict, opamp: str = "generic") -> Result:
    amps = VOUT_LEVELS * np.sqrt(2) / 10 ** (GAIN_DB / 20)
    # quick pre-screen on small-signal gain
    try:
        f, mag, _ = analysis.ac_from_data(
            spice.run(design.netlist([], opamp=opamp), "ac dec 10 10 50k",
                      ["v(out_ac)", "v(in_ac)"],
                      timeout=15))
        g = float(np.interp(F0, f, mag))
    except Exception as exc:  # noqa: BLE001
        return Result(cost=FAIL, error=str(exc)[:300])
    if abs(g - GAIN_DB) > GAIN_SCREEN_DB:
        return Result(cost=100 + 10 * abs(g - GAIN_DB), gain_db=g, error="gain out of range")
    try:
        tran, ac, nz = spice.run_multi(
            design.netlist(amps, F0, opamp=opamp),
            [
                (analysis.tran_command(F0, 20, 10), [f"v(out{i})" for i in range(len(amps))]),
                ("ac dec 10 10 50k", ["v(out_ac)", "v(in_ac)"]),
                ("noise v(out_ac) VAC dec 10 20 20k\nsetplot noise2", ["onoise_total"]),
            ],
            timeout=45,
        )
    except Exception as exc:  # noqa: BLE001 - any simulation error = bad candidate
        return Result(cost=FAIL, error=str(exc)[:300])

    harms = [analysis.harmonics_from_wave(tran[:, 0], tran[:, 1 + i], F0, 10, amplitude_in=a)
             for i, a in enumerate(amps)]
    vout = np.array([h.vout_rms for h in harms])
    meas = np.array([h.levels_db[:4] for h in harms])
    target = target_at(tgt, vout)

    gain_db = harms[0].gain_db
    f, mag, _ = analysis.ac_from_data(ac)
    band = (f >= 20) & (f <= 20e3)
    flat = float(np.max(np.abs(mag[band] - np.interp(F0, f, mag))))
    noise_v = float(nz[0, 1])
    snr = 20 * np.log10(1.0 / max(noise_v, 1e-15))

    m = np.maximum(meas, H_FLOOR)
    t = np.maximum(target, H_FLOOR)
    parts = {
        "gain": 2.0 * abs(gain_db - GAIN_DB),
        "h2": float(np.sqrt(np.mean((m[:, 0] - t[:, 0]) ** 2))),
        "h3": 0.3 * float(np.sqrt(np.mean((m[:, 1] - t[:, 1]) ** 2))),
        "h45": 0.3 * float(np.sum(np.maximum(0, meas[:, 2:] - np.maximum(target[:, 2:], -90)))),
        "flat": 5.0 * max(0.0, flat - 0.2),
        "noise": 0.5 * max(0.0, SNR_MIN_DB - snr),
    }
    if not np.all(np.isfinite(list(parts.values()))):
        return Result(cost=FAIL, error="non-finite measurement")
    return Result(
        cost=float(sum(parts.values())), gain_db=gain_db, vout_rms=vout.tolist(),
        h=meas.tolist(), h_target=target.tolist(), flat_db=flat, snr_db=snr, parts=parts,
    )
