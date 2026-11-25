"""E24 resistor series."""

import numpy as np

E24 = np.array([1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
                3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1])


def values(lo: float, hi: float) -> np.ndarray:
    """All E24 values from lo up to and including hi (lo and hi must be powers of 10)."""
    out = []
    decade = lo
    while decade < hi:
        out.extend(E24 * decade)
        decade *= 10
    out.append(hi)
    return np.round(np.array(out), 6)


def fmt(r: float) -> str:
    """Readable notation, e.g. 4k7, 220R, 1M."""
    for unit, scale in (("M", 1e6), ("k", 1e3), ("R", 1.0)):
        if r >= scale * 0.9999:
            s = f"{float(f'{r / scale:.3g}'):g}"  # at most 3 significant digits (E96)
            if "." in s:
                a, b = s.split(".")
                return f"{a}{unit}{b}"
            return f"{s}{unit}"
    return f"{r:g}R"
