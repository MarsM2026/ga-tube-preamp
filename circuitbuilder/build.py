"""Het ontwerp zoals het gebouwd wordt: één bron van waarheid voor simulatie,
KiCad-schema, print en onderdelenlijst.

Per kanaal (L = 1xx, R = 2xx in de referenties):
  - ingang: CIN (film) + RIN naar massa
  - U1: niet-inverterende versterker (RF1/RG1, CG1 bipolair voor DC-versterking 1)
  - U2: inverter (RI1/RI2)
  - tak A/B: RA/RB (RB = vaste weerstand + trimpot), voorspanning via RBA/RBB uit een
    gefilterde +15 V (RFLT + CFLT), 3x 1N4148 per tak
  - U3: sommator (RS0, RSA+CSA, RSB+CSB, RF2 // CF2)
  - uitgang: ROUT in serie, COUT (bipolair) + RBLEED naar massa
Gedeeld: J1 voeding (+15/GND/-15), ontkoppeling per opamp, bulkcondensatoren.
Opamps (3x NE5532P, alle 6 opamps gebruikt): IC U1 = ingangstrap, U2 = inverter,
U3 = sommator; eenheid A = kanaal L, eenheid B = kanaal R.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import eseries, spice

ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / "designs" / "final.json"


@dataclass
class Part:
    ref: str
    value: str          # zoals op de print/BOM
    kind: str           # R, R_POT, C, CP, C_NP, D, OPAMP, PWR_CONN, SIG_CONN
    nets: dict          # pinnaam -> net
    spice_value: float | None = None
    footprint: str = ""
    descr: str = ""
    channel: str = ""   # "L", "R" of "" (gedeeld)
    block: str = ""     # functioneel blok (voor schema-indeling en documentatie)
    extra: dict = field(default_factory=dict)


FP = {
    "R": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
    "R_POT": "Potentiometer_THT:Potentiometer_Bourns_3296W_Vertical",
    "C_FILM": "Capacitor_THT:C_Rect_L7.2mm_W5.5mm_P5.00mm_FKS2_FKP2_MKS2_MKP2",
    "C_CER": "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm",
    "CP_6": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
    "CNP_6": "Capacitor_THT:C_Radial_D6.3mm_H11.0mm_P2.50mm",
    "CP_8": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
    "CP_10": "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
    "D": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
    "DIP8": "Package_DIP:DIP-8_W7.62mm_Socket",
    "TERM3": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal",
    "HDR2": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical",
}

# vaste (niet door het GA gekozen) waarden
FIXED_PARTS = {
    "CIN": (2.2e-6, "2µ2 film", "C_FILM", "C"),
    "RIN": (100e3, "100k", "R", "R"),
    "CG1": (22e-6, "22µ bipolair", "CNP_6", "C_NP"),
    "RI1": (10e3, "10k", "R", "R"),
    "RI2": (10e3, "10k", "R", "R"),
    "CSA": (47e-6, "47µ 25V", "CP_6", "CP"),
    "CSB": (47e-6, "47µ 25V", "CP_6", "CP"),
    "CF2": (22e-12, "22p C0G", "C_CER", "C"),
    "RFLT": (47.0, "47R", "R", "R"),
    "CFLT": (470e-6, "470µ 25V", "CP_10", "CP"),
    "ROUT": (100.0, "100R", "R", "R"),
    "COUT": (10e-6, "10µ bipolair", "CNP_6", "C_NP"),
    "RBLEED": (100e3, "100k", "R", "R"),
}


def load_values() -> dict:
    d = json.loads(FINAL.read_text())
    return d["values"], d["trim"]["RB"]


def channel_parts(ch: str, values: dict, trim: dict, opamp_refs: dict) -> list[Part]:
    """Onderdelen van één kanaal. opamp_refs: {'U1': ('U1', 'A'), ...} -> (IC, eenheid)."""
    base = 100 if ch == "L" else 200
    n = lambda s: f"{s}_{ch}"  # noqa: E731  netnaam per kanaal
    parts: list[Part] = []
    counters = {"R": 0, "C": 0, "D": 0, "RV": 0}

    def ref(prefix):
        counters[prefix] += 1
        return f"{prefix}{base + counters[prefix]}"

    def R(name, a, b, val=None, block=""):
        v = values[name] if val is None else val
        parts.append(Part(ref("R"), eseries.fmt(v), "R", {"1": a, "2": b}, v, FP["R"],
                          f"{name}, metaalfilm 1% 0,25 W", ch, block, {"role": name}))

    def C(name, a, b, block=""):
        v, label, fp, kind = FIXED_PARTS[name]
        parts.append(Part(ref("C"), label, kind, {"1": a, "2": b}, v, FP[fp],
                          name, ch, block, {"role": name}))

    def Rfix(name, a, b, block=""):
        v, label, _, _ = FIXED_PARTS[name]
        parts.append(Part(ref("R"), label, "R", {"1": a, "2": b}, v, FP["R"],
                          f"{name}, metaalfilm 1% 0,25 W", ch, block, {"role": name}))

    # ingang + U1
    C("CIN", n("IN"), n("I1"), "ingang")
    Rfix("RIN", n("I1"), "GND", "ingang")
    R("RF1", n("V1"), n("FB1"), block="versterker")
    R("RG1", n("FB1"), n("G1"), block="versterker")
    C("CG1", n("G1"), "GND", "versterker")
    # inverter
    Rfix("RI1", n("V1"), n("FB2"), "inverter")
    Rfix("RI2", n("V1N"), n("FB2"), "inverter")
    # voedingsfilter voor de diodevoorspanning
    Rfix("RFLT", "+15V", n("VP"), "voorspanning")
    C("CFLT", n("VP"), "GND", "voorspanning")
    # tak A
    R("RA", n("V1"), n("A"), block="tak A")
    R("RBA", n("VP"), n("A"), block="tak A")
    nd = int(values["N"])
    chain = [n("A")] + [n(f"A{i}") for i in range(1, nd)] + ["GND"]
    for i in range(nd):
        parts.append(Part(ref("D"), "1N4148", "D", {"A": chain[i], "K": chain[i + 1]}, None,
                          FP["D"], "1N4148 kleinsignaaldiode", ch, "tak A", {"role": f"DA{i}"}))
    C("CSA", n("A"), n("SA"), "tak A")
    R("RSA", n("SA"), n("S"), block="tak A")
    # tak B (RB = vast + trimpot als variabele weerstand)
    R("RB", n("V1N"), n("RB"), val=trim["fixed"], block="tak B")
    parts.append(Part(f"RV{base + 1}", eseries.fmt(trim["pot"]), "R_POT",
                      {"1": n("RB"), "2": n("B"), "3": n("B")}, trim["nominal"] - trim["fixed"],
                      FP["R_POT"], "trimpot 500R meerslagen (Bourns 3296W), H3-afregeling",
                      ch, "tak B", {"role": "RB_TRIM"}))
    R("RBB", n("VP"), n("B"), block="tak B")
    chain = [n("B")] + [n(f"B{i}") for i in range(1, nd)] + ["GND"]
    for i in range(nd):
        parts.append(Part(ref("D"), "1N4148", "D", {"A": chain[i], "K": chain[i + 1]}, None,
                          FP["D"], "1N4148 kleinsignaaldiode", ch, "tak B", {"role": f"DB{i}"}))
    C("CSB", n("B"), n("SB"), "tak B")
    R("RSB", n("SB"), n("S"), block="tak B")
    # sommator
    R("RS0", n("V1N"), n("S"), block="sommator")
    R("RF2", n("OUT0"), n("S"), block="sommator")
    C("CF2", n("OUT0"), n("S"), "sommator")
    # uitgang
    Rfix("ROUT", n("OUT0"), n("OUT1"), "uitgang")
    C("COUT", n("OUT1"), n("OUT"), "uitgang")
    Rfix("RBLEED", n("OUT"), "GND", "uitgang")
    # opamp-eenheden: (+in, -in, uit)
    for stage, (inp, inn, out) in {"U1": (n("I1"), n("FB1"), n("V1")),
                                   "U2": ("GND", n("FB2"), n("V1N")),
                                   "U3": ("GND", n("S"), n("OUT0"))}.items():
        ic, unit = opamp_refs[stage]
        parts.append(Part(f"{ic}{unit}", "NE5532P", "OPAMP", {"+": inp, "-": inn, "OUT": out},
                          None, FP["DIP8"], "NE5532P dubbele low-noise opamp", ch,
                          {"U1": "versterker", "U2": "inverter", "U3": "sommator"}[stage],
                          {"ic": ic, "unit": unit, "stage": stage}))
    # signaalaansluitingen
    parts.append(Part(f"J{2 if ch == 'L' else 3}", f"IN_{ch}", "SIG_CONN",
                      {"1": n("IN"), "2": "GND"}, None, FP["HDR2"],
                      f"ingang kanaal {ch} (signaal, massa)", ch, "ingang"))
    parts.append(Part(f"J{4 if ch == 'L' else 5}", f"OUT_{ch}", "SIG_CONN",
                      {"1": n("OUT"), "2": "GND"}, None, FP["HDR2"],
                      f"uitgang kanaal {ch} (signaal, massa)", ch, "uitgang"))
    return parts


# Per IC één trap van beide kanalen: eenheid A = kanaal L, eenheid B = kanaal R.
# Zo staan de IC's op de print op één middenlijn met L erboven en R eronder.
OPAMPS = {
    "L": {"U1": ("U1", "A"), "U2": ("U2", "A"), "U3": ("U3", "A")},
    "R": {"U1": ("U1", "B"), "U2": ("U2", "B"), "U3": ("U3", "B")},
}


def all_parts() -> list[Part]:
    values, trim = load_values()
    parts = channel_parts("L", values, trim, OPAMPS["L"]) + channel_parts("R", values, trim, OPAMPS["R"])
    # voeding
    parts.append(Part("J1", "+15V/GND/-15V", "PWR_CONN", {"1": "+15V", "2": "GND", "3": "-15V"},
                      None, FP["TERM3"], "voedingsaansluiting +/-15 V (gestabiliseerd)", "", "voeding"))
    parts.append(Part("C1", "100µ 25V", "CP", {"1": "+15V", "2": "GND"}, 100e-6, FP["CP_8"],
                      "bulk +15 V", "", "voeding"))
    parts.append(Part("C2", "100µ 25V", "CP", {"1": "GND", "2": "-15V"}, 100e-6, FP["CP_8"],
                      "bulk -15 V", "", "voeding"))
    k = 3
    for ic in ("U1", "U2", "U3"):
        parts.append(Part(f"C{k}", "100n", "C", {"1": "+15V", "2": "GND"}, 100e-9, FP["C_CER"],
                          f"ontkoppeling {ic} +15 V", "", "voeding", {"ic": ic}))
        parts.append(Part(f"C{k + 1}", "100n", "C", {"1": "GND", "2": "-15V"}, 100e-9, FP["C_CER"],
                          f"ontkoppeling {ic} -15 V", "", "voeding", {"ic": ic}))
        k += 2
        # voedingspinnen van de IC (pin 8 = V+, pin 4 = V-)
        parts.append(Part(f"{ic}C", "NE5532P", "OPAMP_PWR", {"V+": "+15V", "V-": "-15V"}, None,
                          FP["DIP8"], "voeding NE5532P", "", "voeding", {"ic": ic, "unit": "C"}))
    return parts


# ------------------------------------------------------------ simulatie -----
def spice_netlist(parts: list[Part], channel: str, source: str, r_load: float = 10e3) -> str:
    """SPICE-netlist van één kanaal met NE5532-model, inclusief voedingsfilter en
    uitgangsnetwerk. `source` zet een spanningsbron op net IN_<ch>."""
    lines = ["* gebouwde schakeling, kanaal " + channel,
             spice.include("parts.lib"), spice.include("ne5532.lib"),
             "VPOS VPOS15 0 DC 15", "VNEG VNEG15 0 DC -15", source,
             f"RLOAD OUT_{channel} 0 {r_load:g}"]
    alias = {"GND": "0", "+15V": "VPOS15", "-15V": "VNEG15"}
    net = lambda s: alias.get(s, s)  # noqa: E731
    for p in parts:
        if p.channel != channel:
            continue
        nn = {k: net(v) for k, v in p.nets.items()}
        if p.kind == "R":
            lines.append(f"R{p.ref} {nn['1']} {nn['2']} {p.spice_value:g}")
        elif p.kind == "R_POT":  # als variabele weerstand ingesteld op nominaal
            lines.append(f"R{p.ref} {nn['1']} {nn['2']} {p.spice_value:g}")
        elif p.kind in ("C", "CP", "C_NP"):
            lines.append(f"C{p.ref} {nn['1']} {nn['2']} {p.spice_value:g}")
        elif p.kind == "D":
            lines.append(f"D{p.ref} {nn['A']} {nn['K']} D1N4148")
        elif p.kind == "OPAMP":
            lines.append(f"X{p.ref} {nn['+']} {nn['-']} {nn['OUT']} OPAMP_NE5532")
    lines += [".options reltol=1e-4 abstol=1e-12 vntol=1e-7 itl4=50", ".end"]
    return "\n".join(lines)
