"""Kandidaat-topologie: opamp-voorversterker met even-harmonischen-generator.

Signaalpad (alle opamps uit +/-15 V):

  in -> CIN/RIN -> U1 (niet-inverterend, versterking 1+RF1/RG1) -> v1
                   U2 (inverter, 10k/10k)                        -> v1n = -v1
  Tak A: v1  -RA-> knoop a, voorspanning via RBA uit +15 V, N diodes in serie naar massa
  Tak B: v1n -RB-> knoop b, idem met RBB
  U3 (inverterende sommator, RF2):  out = -RF2 * ( v1n/RS0 + a~/RSA + b~/RSB )
     (a~, b~ = wisselspanning via 47 uF)

De diodespanning is ~ ln(1 + x) met x evenredig met het signaal. Tak A ziet +x,
tak B -x: bij optellen vallen de oneven termen (grotendeels) weg en blijft vooral
x^2 over, dus H2 die evenredig met het niveau groeit, net als bij een triode.
Verschillen tussen de takken geven gedoseerd H3.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import eseries, spice

R_SMALL = eseries.values(100, 1e5)
R_MID = eseries.values(1e3, 1e5)
R_WIDE = eseries.values(1e3, 1e6)

# (naam, toegestane waarden)
GENES: list[tuple[str, np.ndarray]] = [
    ("RF1", R_MID),
    ("RG1", R_MID),
    ("RA", R_WIDE),
    ("RB", R_WIDE),
    ("RBA", R_WIDE),
    ("RBB", R_WIDE),
    ("RS0", R_MID),
    ("RSA", R_SMALL),
    ("RSB", R_SMALL),
    ("RF2", R_MID),
    ("N", np.array([1, 2, 3, 4])),
]
N_GENES = len(GENES)
UPPER = np.array([len(v) - 1 for _, v in GENES])
FIXED = {"RIN": 100e3, "RI1": 10e3, "RI2": 10e3}


@dataclass
class Design:
    values: dict

    @classmethod
    def from_genes(cls, genes) -> "Design":
        g = np.clip(np.round(np.asarray(genes)).astype(int), 0, UPPER)
        return cls({name: float(vals[i]) for (name, vals), i in zip(GENES, g)})

    def bom(self) -> str:
        v = self.values
        lines = [f"  {k:4s} = {eseries.fmt(v[k])}" for k, _ in GENES if k != "N"]
        lines.append(f"  N    = {int(v['N'])} x 1N4148 per tak")
        return "\n".join(lines)

    def subckt(self, opamp: str = "OPAMP") -> str:
        """Subcircuit. Optionele sleutels in `values` (voor toleranties):
        RIN, RI1, RI2 (vaste weerstanden) en IS_a0.., IS_b0.. (schaalfactor op de
        verzadigingsstroom van elke diode, 1 = nominaal)."""
        v = {**FIXED, **self.values}
        n = int(v["N"])
        models = []

        def chain(top: str, tag: str) -> str:
            nodes = [top] + [f"{tag}{i}" for i in range(1, n)] + ["0"]
            lines = []
            for i in range(n):
                k = v.get(f"IS_{tag}{i}", 1.0)
                model = "D1N4148"
                if k != 1.0:
                    model = f"DM{tag}{i}"
                    models.append(f".model {model} D(IS={2.52e-9 * k:.4g} RS=0.568 N=1.752 "
                                  "CJO=4p M=0.4 TT=20n BV=100 IBV=100u)")
                lines.append(f"D{tag}{i} {nodes[i]} {nodes[i + 1]} {model}")
            return "\n".join(lines)

        chain_a, chain_b = chain("a", "a"), chain("b", "b")
        return f""".subckt PREAMP in out vp
{chr(10).join(models)}
CIN in i1 2.2u
RIN i1 0 {v['RIN']:g}
XU1 i1 fb1 v1 {opamp}
RF1 v1 fb1 {v['RF1']:g}
RG1 fb1 g1 {v['RG1']:g}
CG1 g1 0 470u
XU2 0 fb2 v1n {opamp}
RI1 v1 fb2 {v['RI1']:g}
RI2 v1n fb2 {v['RI2']:g}
RA v1 a {v['RA']:g}
RBA vp a {v['RBA']:g}
{chain_a}
RB v1n b {v['RB']:g}
RBB vp b {v['RBB']:g}
{chain_b}
RS0 v1n s {v['RS0']:g}
CSA a sa 47u
RSA sa s {v['RSA']:g}
CSB b sb 47u
RSB sb s {v['RSB']:g}
XU3 0 s out {opamp}
RF2 out s {v['RF2']:g}
CF2 out s 22p
.ends PREAMP
"""

    def netlist(self, amplitudes, f0: float = 1000.0, r_load: float = 10e3,
                opamp: str = "generic") -> str:
        """Eén netlist met per amplitude een eigen kopie (in<i>/out<i>) plus een
        AC-kopie (in_ac/out_ac) voor frequentierespons en ruis.

        opamp: "generic" (snel, voor het GA) of "ne5532" (TI-macromodel, ter controle).
        """
        parts = ["* opamp-voorversterker, kandidaat", spice.include("parts.lib")]
        if opamp == "ne5532":
            parts.append(spice.include("ne5532.lib"))
            sub = self.subckt("OPAMP_NE5532")
        else:
            sub = self.subckt()
        parts += [
            sub,
            "VP vp 0 DC 15",
            "XAC in_ac out_ac vp PREAMP",
            "VAC in_ac 0 DC 0 AC 1",
            f"RLAC out_ac 0 {r_load:g}",
        ]
        for i, a in enumerate(amplitudes):
            parts += [
                f"X{i} in{i} out{i} vp PREAMP",
                f"VIN{i} in{i} 0 SIN(0 {a:g} {f0:g})",
                f"RL{i} out{i} 0 {r_load:g}",
            ]
        parts += [".options reltol=1e-4 abstol=1e-12 vntol=1e-7 itl4=50", ".end"]
        return "\n".join(parts)
