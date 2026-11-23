"""Referentie: klassieke 12AX7-versterkertrap met gemeenschappelijke kathode.

Dit is het doelgedrag dat de opamp-schakeling straks moet nabootsen.
Standaardwaarden zijn gangbaar voor een hifi-voortrap.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import spice


@dataclass
class TubeStage:
    b_plus: float = 250.0     # voedingsspanning [V]
    r_plate: float = 100e3    # plaatweerstand
    r_cathode: float = 1.5e3  # kathodeweerstand
    c_cathode: float = 22e-6  # ontkoppel-C over Rk (0 = niet ontkoppeld)
    r_grid: float = 1e6       # roosterlek
    c_in: float = 100e-9      # ingangscondensator
    c_out: float = 100e-9     # uitgangscondensator
    r_load: float = 100e3     # belasting (ingang volgende trap/versterker)

    def netlist(self, source: str) -> str:
        ck = (f"CK k 0 {self.c_cathode:g}\n" if self.c_cathode > 0 else "")
        return f"""* 12AX7 common-cathode referentietrap
{spice.include('12ax7.lib')}
VB bplus 0 DC {self.b_plus:g}
{source}
CIN in g0 {self.c_in:g}
RG g0 0 {self.r_grid:g}
RGS g0 g 1k
XV1 p g k 12AX7
RA bplus p {self.r_plate:g}
RK k 0 {self.r_cathode:g}
{ck}COUT p out {self.c_out:g}
RL out 0 {self.r_load:g}
.options reltol=1e-4 abstol=1e-12 vntol=1e-7
.end
"""

    def sine_netlist(self, amplitude: float, f0: float) -> str:
        return self.netlist(f"VIN in 0 SIN(0 {amplitude:g} {f0:g})")

    def ac_netlist(self) -> str:
        return self.netlist("VIN in 0 DC 0 AC 1")
