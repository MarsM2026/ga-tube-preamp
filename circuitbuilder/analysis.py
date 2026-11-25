"""Measurements on simulation results: harmonics, THD and frequency response."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import spice

FLOOR_DB = -110.0  # below this level a harmonic is considered "absent"


@dataclass
class Harmonics:
    amplitude_in: float      # input peak amplitude [V]
    fundamental: float       # output fundamental peak amplitude [V]
    levels_db: np.ndarray    # H2..Hn in dB relative to the fundamental
    phases: np.ndarray       # phase of H2..Hn relative to the fundamental [rad]
    thd: float               # total harmonic distortion (fraction)

    @property
    def vout_rms(self) -> float:
        return self.fundamental / np.sqrt(2)

    @property
    def gain_db(self) -> float:
        return 20 * np.log10(self.fundamental / self.amplitude_in)


def harmonics_from_wave(t: np.ndarray, v: np.ndarray, f0: float, cycles: int,
                        n_harm: int = 6, amplitude_in: float = 1.0) -> Harmonics:
    """Least-squares fit of the last `cycles` periods using the basis
    1, t (for slow drift of coupling capacitors) and sin/cos of k*f0."""
    t_start = t[-1] - cycles / f0
    n = cycles * 256
    tu = t_start + np.arange(n) * (cycles / f0 / n)
    vu = np.interp(tu, t, v)
    w = 2 * np.pi * f0 * (tu - t_start)
    cols = [np.ones(n), (tu - tu.mean()) * f0]
    for k in range(1, n_harm + 1):
        cols += [np.cos(k * w), np.sin(k * w)]
    coef, *_ = np.linalg.lstsq(np.column_stack(cols), vu, rcond=None)
    c = coef[2::2] - 1j * coef[3::2]
    amps = np.abs(c)
    ph = np.angle(c)
    fund = amps[0]
    rel = np.maximum(amps[1:] / fund, 10 ** (FLOOR_DB / 20))
    rel_ph = np.angle(np.exp(1j * (ph[1:] - np.arange(2, n_harm + 1) * ph[0])))
    return Harmonics(
        amplitude_in=amplitude_in,
        fundamental=fund,
        levels_db=20 * np.log10(rel),
        phases=rel_ph,
        thd=float(np.sqrt(np.sum(rel ** 2))),
    )


def tran_command(f0: float, settle_cycles: int, cycles: int) -> str:
    period = 1.0 / f0
    step = period / 400
    return f"tran {step:.4g} {(settle_cycles + cycles) * period:.6g} 0 {step:.4g}"


def harmonic_sweep(netlist_fn, amplitudes, f0: float = 1000.0, settle_cycles: int = 20,
                   cycles: int = 10, out_node: str = "out") -> list[Harmonics]:
    """Run one transient simulation with a sine of f0 per input amplitude.

    `netlist_fn(amplitude, f0)` must return a netlist with a source that drives a sine
    onto node `in` and an output on node `out_node`.
    """
    results = []
    for a in amplitudes:
        data = spice.run(netlist_fn(a, f0), tran_command(f0, settle_cycles, cycles),
                         [f"v({out_node})"])
        results.append(harmonics_from_wave(data[:, 0], data[:, 1], f0, cycles,
                                           amplitude_in=a))
    return results


def ac_from_data(data: np.ndarray):
    """Convert wrdata output of [v(out), v(in)] to (f, dB, degrees)."""
    f = data[:, 0]
    h = (data[:, 1] + 1j * data[:, 2]) / (data[:, 3] + 1j * data[:, 4])
    return f, 20 * np.log10(np.abs(h)), np.degrees(np.unwrap(np.angle(h)))


def frequency_response(netlist: str, f_start=10.0, f_stop=100e3, points_per_decade=20,
                       out_node: str = "out", in_node: str = "in"):
    """Small-signal AC analysis. Returns (frequencies, gain in dB, phase in degrees)."""
    data = spice.run(netlist, f"ac dec {points_per_decade} {f_start} {f_stop}",
                     [f"v({out_node})", f"v({in_node})"])
    return ac_from_data(data)
