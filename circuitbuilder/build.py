"""The design as built: single source of truth for simulation, KiCad schematic,
PCB and bill of materials.

Per channel (L = 1xx, R = 2xx in the reference designators):
  - input: CIN (film) + RIN to ground
  - U1: non-inverting amplifier (RF1/RG1, CG1 bipolar for unity DC gain)
  - U2: inverter (RI1/RI2)
  - branch A/B: RA/RB (RB = fixed resistor + trimmer), biased via RBA/RBB from a
    filtered +15 V (RFLT + CFLT), 3x 1N4148 per branch
  - U3: summer (RS0, RSA+CSA, RSB+CSB, RF2 // CF2)
  - output: series ROUT, COUT (bipolar) + RBLEED to ground
Shared: J1 power (+15/GND/-15), decoupling per opamp, bulk capacitors.
Opamps (3x NE5532, all 6 opamps used): IC U1 = input stage, U2 = inverter,
U3 = summer; unit A = channel L, unit B = channel R.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import eseries, spice

ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / "designs" / "final.json"


@dataclass
class Part:
    ref: str
    value: str          # as printed on the PCB/BOM
    kind: str           # R, R_POT, C, CP, C_NP, D, OPAMP, PWR_CONN, SIG_CONN
    nets: dict          # pin name -> net
    spice_value: float | None = None
    footprint: str = ""
    descr: str = ""
    channel: str = ""   # "L", "R" or "" (shared)
    block: str = ""     # functional block (for schematic layout and documentation)
    extra: dict = field(default_factory=dict)


# Two PCB variants with the same schematic and the same values:
#   tht - through-hole, to solder yourself        -> hardware/kicad, hardware/export
#   smd - SMD, to have it assembled by a fab       -> hardware/kicad_smd, hardware/export_smd
# Selected with the environment variable CB_VARIANT (default tht) or set_variant().
VARIANT = os.environ.get("CB_VARIANT", "tht")

FP_THT = {
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

# SMD: everything machine-placeable except the screw terminals (the fab mounts those
# as through-hole parts). Inputs and outputs also on screw terminals: no soldering needed.
FP_SMD = {
    "R": "Resistor_SMD:R_0805_2012Metric",
    "R_POT": "Potentiometer_SMD:Potentiometer_Bourns_3224W_Vertical",
    "C_FILM": "Capacitor_SMD:C_1206_3216Metric",
    "C_CER": "Capacitor_SMD:C_0805_2012Metric",
    "CP_6": "Capacitor_SMD:CP_Elec_6.3x7.7",
    "CNP_6": "Capacitor_SMD:C_Elec_6.3x7.7",
    "CP_8": "Capacitor_SMD:CP_Elec_6.3x7.7",
    "CP_10": "Capacitor_SMD:CP_Elec_10x10.5",
    "D": "Diode_SMD:D_SOD-323",
    "DIP8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "TERM3": FP_THT["TERM3"],
    "HDR2": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
}

# part names that differ per variant (value, description)
NAMES = {
    "tht": {"opamp": "NE5532P", "opamp_d": "NE5532P dual low-noise opamp",
            "diode": "1N4148", "diode_d": "1N4148 small-signal diode",
            "pot_d": "trimmer 500R multi-turn (Bourns 3296W), H3 adjustment",
            "res": "metal film 1% 0.25 W", "cin": "2µ2 film",
            "sig_d": "pin header 1x2"},
    "smd": {"opamp": "NE5532DR", "opamp_d": "NE5532 dual low-noise opamp (SOIC-8)",
            "diode": "1N4148WS", "diode_d": "1N4148WS small-signal diode (SOD-323)",
            "pot_d": "trimmer 500R multi-turn (Bourns 3224W), H3 adjustment",
            "res": "thick film 1% 0805", "cin": "2µ2 X7R 50V",
            "sig_d": "screw terminal 2-pin"},
}


def set_variant(v: str) -> None:
    global VARIANT
    assert v in ("tht", "smd"), v
    VARIANT = v


def fp(key: str) -> str:
    return (FP_SMD if VARIANT == "smd" else FP_THT)[key]


def name(key: str) -> str:
    return NAMES[VARIANT][key]


def hw_dirs() -> tuple[Path, Path]:
    """(KiCad project folder, export folder) of the active variant."""
    suffix = "" if VARIANT == "tht" else "_smd"
    return ROOT / "hardware" / f"kicad{suffix}", ROOT / "hardware" / f"export{suffix}"


# fixed values (not chosen by the GA)
FIXED_PARTS = {
    "CIN": (2.2e-6, "2µ2 film", "C_FILM", "C"),
    "RIN": (100e3, "100k", "R", "R"),
    "CG1": (22e-6, "22µ bipolar", "CNP_6", "C_NP"),
    "RI1": (10e3, "10k", "R", "R"),
    "RI2": (10e3, "10k", "R", "R"),
    "CSA": (47e-6, "47µ 25V", "CP_6", "CP"),
    "CSB": (47e-6, "47µ 25V", "CP_6", "CP"),
    "CF2": (22e-12, "22p C0G", "C_CER", "C"),
    "RFLT": (47.0, "47R", "R", "R"),
    "CFLT": (470e-6, "470µ 25V", "CP_10", "CP"),
    "ROUT": (100.0, "100R", "R", "R"),
    "COUT": (10e-6, "10µ bipolar", "CNP_6", "C_NP"),
    "RBLEED": (100e3, "100k", "R", "R"),
}


def load_values() -> dict:
    d = json.loads(FINAL.read_text())
    return d["values"], d["trim"]["RB"]


def channel_parts(ch: str, values: dict, trim: dict, opamp_refs: dict) -> list[Part]:
    """Parts of one channel. opamp_refs: {'U1': ('U1', 'A'), ...} -> (IC, unit)."""
    base = 100 if ch == "L" else 200
    n = lambda s: f"{s}_{ch}"  # noqa: E731  net name per channel
    parts: list[Part] = []
    counters = {"R": 0, "C": 0, "D": 0, "RV": 0}

    def ref(prefix):
        counters[prefix] += 1
        return f"{prefix}{base + counters[prefix]}"

    def R(role, a, b, val=None, block=""):
        v = values[role] if val is None else val
        parts.append(Part(ref("R"), eseries.fmt(v), "R", {"1": a, "2": b}, v, fp("R"),
                          f"{role}, {NAMES[VARIANT]['res']}", ch, block, {"role": role}))

    def C(role, a, b, block=""):
        v, label, fpk, kind = FIXED_PARTS[role]
        if role == "CIN":
            label = NAMES[VARIANT]["cin"]
        parts.append(Part(ref("C"), label, kind, {"1": a, "2": b}, v, fp(fpk),
                          role, ch, block, {"role": role}))

    def Rfix(role, a, b, block=""):
        v, label, _, _ = FIXED_PARTS[role]
        parts.append(Part(ref("R"), label, "R", {"1": a, "2": b}, v, fp("R"),
                          f"{role}, {NAMES[VARIANT]['res']}", ch, block, {"role": role}))

    # input + U1
    C("CIN", n("IN"), n("I1"), "input")
    Rfix("RIN", n("I1"), "GND", "input")
    R("RF1", n("V1"), n("FB1"), block="amplifier")
    R("RG1", n("FB1"), n("G1"), block="amplifier")
    C("CG1", n("G1"), "GND", "amplifier")
    # inverter
    Rfix("RI1", n("V1"), n("FB2"), "inverter")
    Rfix("RI2", n("V1N"), n("FB2"), "inverter")
    # supply filter for the diode bias
    Rfix("RFLT", "+15V", n("VP"), "bias")
    C("CFLT", n("VP"), "GND", "bias")
    # branch A
    R("RA", n("V1"), n("A"), block="branch A")
    R("RBA", n("VP"), n("A"), block="branch A")
    nd = int(values["N"])
    chain = [n("A")] + [n(f"A{i}") for i in range(1, nd)] + ["GND"]
    for i in range(nd):
        parts.append(Part(ref("D"), name("diode"), "D", {"A": chain[i], "K": chain[i + 1]}, None,
                          fp("D"), name("diode_d"), ch, "branch A", {"role": f"DA{i}"}))
    C("CSA", n("A"), n("SA"), "branch A")
    R("RSA", n("SA"), n("S"), block="branch A")
    # branch B (RB = fixed resistor + trimmer used as variable resistor)
    R("RB", n("V1N"), n("RB"), val=trim["fixed"], block="branch B")
    parts.append(Part(f"RV{base + 1}", eseries.fmt(trim["pot"]), "R_POT",
                      {"1": n("RB"), "2": n("B"), "3": n("B")}, trim["nominal"] - trim["fixed"],
                      fp("R_POT"), name("pot_d"),
                      ch, "branch B", {"role": "RB_TRIM"}))
    R("RBB", n("VP"), n("B"), block="branch B")
    chain = [n("B")] + [n(f"B{i}") for i in range(1, nd)] + ["GND"]
    for i in range(nd):
        parts.append(Part(ref("D"), name("diode"), "D", {"A": chain[i], "K": chain[i + 1]}, None,
                          fp("D"), name("diode_d"), ch, "branch B", {"role": f"DB{i}"}))
    C("CSB", n("B"), n("SB"), "branch B")
    R("RSB", n("SB"), n("S"), block="branch B")
    # summer
    R("RS0", n("V1N"), n("S"), block="summer")
    R("RF2", n("OUT0"), n("S"), block="summer")
    C("CF2", n("OUT0"), n("S"), "summer")
    # output
    Rfix("ROUT", n("OUT0"), n("OUT1"), "output")
    C("COUT", n("OUT1"), n("OUT"), "output")
    Rfix("RBLEED", n("OUT"), "GND", "output")
    # opamp units: (+in, -in, out)
    for stage, (inp, inn, out) in {"U1": (n("I1"), n("FB1"), n("V1")),
                                   "U2": ("GND", n("FB2"), n("V1N")),
                                   "U3": ("GND", n("S"), n("OUT0"))}.items():
        ic, unit = opamp_refs[stage]
        parts.append(Part(f"{ic}{unit}", name("opamp"), "OPAMP", {"+": inp, "-": inn, "OUT": out},
                          None, fp("DIP8"), name("opamp_d"), ch,
                          {"U1": "amplifier", "U2": "inverter", "U3": "summer"}[stage],
                          {"ic": ic, "unit": unit, "stage": stage}))
    # signal connectors
    parts.append(Part(f"J{2 if ch == 'L' else 3}", f"IN_{ch}", "SIG_CONN",
                      {"1": n("IN"), "2": "GND"}, None, fp("HDR2"),
                      f"input channel {ch} (signal, ground)", ch, "input"))
    parts.append(Part(f"J{4 if ch == 'L' else 5}", f"OUT_{ch}", "SIG_CONN",
                      {"1": n("OUT"), "2": "GND"}, None, fp("HDR2"),
                      f"output channel {ch} (signal, ground)", ch, "output"))
    return parts


# Each IC carries one stage of both channels: unit A = channel L, unit B = channel R.
# That way the ICs sit on one centre line on the PCB with L above and R below.
OPAMPS = {
    "L": {"U1": ("U1", "A"), "U2": ("U2", "A"), "U3": ("U3", "A")},
    "R": {"U1": ("U1", "B"), "U2": ("U2", "B"), "U3": ("U3", "B")},
}


def all_parts() -> list[Part]:
    values, trim = load_values()
    parts = channel_parts("L", values, trim, OPAMPS["L"]) + channel_parts("R", values, trim, OPAMPS["R"])
    # power
    parts.append(Part("J1", "+15V/GND/-15V", "PWR_CONN", {"1": "+15V", "2": "GND", "3": "-15V"},
                      None, fp("TERM3"), "power input +/-15 V (regulated)", "", "supply"))
    parts.append(Part("C1", "100µ 25V", "CP", {"1": "+15V", "2": "GND"}, 100e-6, fp("CP_8"),
                      "bulk +15 V", "", "supply"))
    parts.append(Part("C2", "100µ 25V", "CP", {"1": "GND", "2": "-15V"}, 100e-6, fp("CP_8"),
                      "bulk -15 V", "", "supply"))
    k = 3
    for ic in ("U1", "U2", "U3"):
        parts.append(Part(f"C{k}", "100n", "C", {"1": "+15V", "2": "GND"}, 100e-9, fp("C_CER"),
                          f"decoupling {ic} +15 V", "", "supply", {"ic": ic}))
        parts.append(Part(f"C{k + 1}", "100n", "C", {"1": "GND", "2": "-15V"}, 100e-9, fp("C_CER"),
                          f"decoupling {ic} -15 V", "", "supply", {"ic": ic}))
        k += 2
        # supply pins of the IC (pin 8 = V+, pin 4 = V-)
        parts.append(Part(f"{ic}C", name("opamp"), "OPAMP_PWR", {"V+": "+15V", "V-": "-15V"}, None,
                          fp("DIP8"), "supply " + name("opamp"), "", "supply", {"ic": ic, "unit": "C"}))
    return parts


# ------------------------------------------------------------ simulation -----
def spice_netlist(parts: list[Part], channel: str, source: str, r_load: float = 10e3) -> str:
    """SPICE netlist of one channel with the NE5532 model, including the supply filter
    and output network. `source` puts a voltage source on net IN_<ch>."""
    lines = ["* as-built circuit, channel " + channel,
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
        elif p.kind == "R_POT":  # as a variable resistor set to its nominal value
            lines.append(f"R{p.ref} {nn['1']} {nn['2']} {p.spice_value:g}")
        elif p.kind in ("C", "CP", "C_NP"):
            lines.append(f"C{p.ref} {nn['1']} {nn['2']} {p.spice_value:g}")
        elif p.kind == "D":
            lines.append(f"D{p.ref} {nn['A']} {nn['K']} D1N4148")
        elif p.kind == "OPAMP":
            lines.append(f"X{p.ref} {nn['+']} {nn['-']} {nn['OUT']} OPAMP_NE5532")
    lines += [".options reltol=1e-4 abstol=1e-12 vntol=1e-7 itl4=50", ".end"]
    return "\n".join(lines)
