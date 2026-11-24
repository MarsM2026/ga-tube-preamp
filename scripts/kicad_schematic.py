"""Genereer het KiCad-schema (hardware/kicad/warm_preamp.kicad_sch) en de
onderdelen/net-lijst voor de printgenerator (hardware/kicad/parts.json).

Bron: circuitbuilder/build.py. Symbolen komen uit de geïnstalleerde KiCad-bibliotheek
en worden in het schema ingesloten. Componenten zijn verbonden via netlabels
(korte draadstompjes op elke pin), gegroepeerd per functioneel blok en kanaal.

Gebruik:  python scripts/kicad_schematic.py
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import math
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import build  # noqa: E402
from circuitbuilder.sexpr import Q, dump, find, find_all, parse  # noqa: E402

KICAD = Path(os.environ.get("KICAD_DIR", r"C:\Users\marce\AppData\Local\Programs\KiCad\10.0"))
SYMLIB = KICAD / "share" / "kicad" / "symbols"
OUTDIR = ROOT / "hardware" / "kicad"
PROJECT = "warm_preamp"
NS = uuid.UUID("6f1c3a52-6a7e-4d0e-9a51-1b2c3d4e5f60")
ROOT_UUID = str(uuid.uuid5(NS, "root"))

SYMBOL_OF = {
    "R": "Device:R", "R_POT": "Device:R_Potentiometer_Trim", "C": "Device:C",
    "CP": "Device:C_Polarized", "C_NP": "Device:C", "D": "Device:D",
    "OPAMP": "Amplifier_Operational:NE5532", "OPAMP_PWR": "Amplifier_Operational:NE5532",
    "SIG_CONN": "Connector_Generic:Conn_01x02", "PWR_CONN": "Connector_Generic:Conn_01x03",
}
POWER_NETS = {"GND": "power:GND", "+15V": "power:+15V", "-15V": "power:-15V"}
OPAMP_PINS = {"A": {"OUT": "1", "-": "2", "+": "3"}, "B": {"OUT": "7", "-": "6", "+": "5"},
              "C": {"V+": "8", "V-": "4"}}
UNIT_NUM = {"A": 1, "B": 2, "C": 3}
BLOCK_ORDER = ["ingang", "versterker", "inverter", "voorspanning", "tak A", "tak B",
               "sommator", "uitgang"]
BLOCK_TITLE = {"ingang": "Ingang", "versterker": "U1: versterker (x2,5)",
               "inverter": "U2: inverter", "voorspanning": "Voorspanning diodes (gefilterde +15 V)",
               "tak A": "Tak A: diodeketen (+V1)", "tak B": "Tak B: diodeketen (-V1) met trimpot",
               "sommator": "U3: sommator", "uitgang": "Uitgang", "voeding": "Voeding en ontkoppeling"}

G = 1.27  # rastermaat


def uid(*key) -> str:
    return str(uuid.uuid5(NS, "/".join(map(str, key))))


def snap(v: float) -> float:
    return round(round(v / G) * G, 4)


# ------------------------------------------------------------ symbolen -----
_lib_cache: dict = {}


def lib_symbols(lib: str) -> dict:
    if lib not in _lib_cache:
        tree = parse((SYMLIB / f"{lib}.kicad_sym").read_text(encoding="utf-8"))
        _lib_cache[lib] = {str(s[1]): s for s in find_all(tree, "symbol")}
    return _lib_cache[lib]


def flat_symbol(lib_id: str):
    """Symbooldefinitie, met 'extends' opgelost, hernoemd naar 'Lib:Naam'."""
    lib, name = lib_id.split(":")
    syms = lib_symbols(lib)
    node = copy.deepcopy(syms[name])
    ext = find(node, "extends")
    if ext is not None:
        parent_name = str(ext[1])
        parent = flat_symbol(f"{lib}:{parent_name}")
        child_props = {str(p[1]): p for p in find_all(node, "property")}
        merged = [Q(lib_id)]
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == "property" and str(item[1]) in child_props:
                merged.append(child_props[str(item[1])])
            elif isinstance(item, list) and item[0] == "symbol":
                sub = copy.deepcopy(item)
                sub[1] = Q(str(sub[1]).replace(parent_name, name, 1))
                merged.append(sub)
            else:
                merged.append(item)
        return ["symbol"] + merged
    node[1] = Q(lib_id)
    return node


def pin_table(sym) -> dict:
    """{(unit, pinnummer): (x, y, hoek)} in bibliotheekcoördinaten (y omhoog)."""
    name = str(sym[1]).split(":")[1]
    out = {}
    for sub in find_all(sym, "symbol"):
        parts = str(sub[1]).rsplit("_", 2)
        unit = int(parts[-2])
        for pin in find_all(sub, "pin"):
            at = find(pin, "at")
            num = str(find(pin, "number")[1])
            out[(unit, num)] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
    return out


def pin_pos(sym_xy, pin):
    """Verbindingspunt en richting naar buiten in schemacoördinaten (y omlaag)."""
    px, py, ang = pin
    x, y = sym_xy[0] + px, sym_xy[1] - py
    a = math.radians(ang)
    # pin wijst vanaf het verbindingspunt richting het symbool: (cos a, sin a) in lib
    dx, dy = -math.cos(a), math.sin(a)  # naar buiten, in schema-assen
    return (snap(x), snap(y)), (round(dx), round(dy))


# ------------------------------------------------------------ elementen ----
def font(size=1.27, hide=False, justify=None, bold=False):
    eff = ["effects", ["font", ["size", size, size]] + ([["bold", "yes"]] if bold else [])]
    if justify:
        eff.append(["justify"] + justify.split())
    if hide:
        eff.append(["hide", "yes"])
    return eff


def prop(name, value, xy, hide=False, angle=0, justify=None):
    return ["property", Q(name), Q(value), ["at", xy[0], xy[1], angle], font(hide=hide, justify=justify)]


def symbol_instance(lib_id, ref, value, xy, unit, footprint, descr, pins, key, angle=0,
                    in_bom=True, ref_xy=None, val_xy=None, kind=""):
    if kind in ("D", "OPAMP"):  # tekst boven/onder het symbool, vrij van de pinlabels
        dy = 3.81 if kind == "D" else 6.35
        ref_xy = ref_xy or (xy[0] - 2.54, xy[1] - dy)
        val_xy = val_xy or (xy[0] - 2.54, xy[1] + dy + 1.27)
    ref_xy = ref_xy or (xy[0] + 2.54, xy[1] - 1.27)
    val_xy = val_xy or (xy[0] + 2.54, xy[1] + 1.27)
    node = ["symbol", ["lib_id", Q(lib_id)], ["at", xy[0], xy[1], angle], ["unit", unit],
            ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
            ["on_board", "yes" if in_bom else "no"], ["dnp", "no"], ["uuid", Q(uid(key))],
            prop("Reference", ref, ref_xy, justify="left", hide=not in_bom),
            prop("Value", value, val_xy, justify="left"),
            prop("Footprint", footprint, xy, hide=True),
            prop("Datasheet", "~", xy, hide=True),
            prop("Description", descr, xy, hide=True)]
    for p in pins:
        node.append(["pin", Q(p), ["uuid", Q(uid(key, "pin", p))]])
    node.append(["instances", ["project", Q(PROJECT),
                               ["path", Q(f"/{ROOT_UUID}"), ["reference", Q(ref)], ["unit", unit]]]])
    return node


def wire(a, b):
    return ["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
            ["stroke", ["width", 0], ["type", "default"]], ["uuid", Q(uid("w", a, b))]]


def label(net, xy, direction):
    ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[direction]
    just = "left bottom" if ang in (0, 90) else "right bottom"
    return ["label", Q(net), ["at", xy[0], xy[1], ang], font(justify=just),
            ["uuid", Q(uid("lbl", net, xy))]]


def text(s, xy, size=2.0, bold=True):
    return ["text", Q(s), ["exclude_from_sim", "no"], ["at", xy[0], xy[1], 0],
            font(size=size, justify="left bottom", bold=bold), ["uuid", Q(uid("txt", s, xy))]]


# ------------------------------------------------------------ indeling -----
CELL_W = {"OPAMP": 40.64, "OPAMP_PWR": 22.86, "D": 33.02, "SIG_CONN": 33.02, "PWR_CONN": 33.02}
ROW_H = 33.02
BLOCK_MAX_W = 135.0


def layout(parts):
    """Plaats per kanaal (kolom) de blokken onder elkaar; voeding rechts."""
    groups: dict = {}
    for p in parts:
        key = (p.channel or "-", p.block)
        groups.setdefault(key, []).append(p)
    positions, titles = {}, []
    col_x = {"L": 25.4, "R": 190.5, "-": 355.6}
    for ch in ("L", "R", "-"):
        y = 30.48
        blocks = BLOCK_ORDER if ch != "-" else ["voeding"]
        for blk in blocks:
            items = groups.get((ch, blk), [])
            if not items:
                continue
            title = BLOCK_TITLE[blk] + (f"  (kanaal {ch})" if ch != "-" else "")
            titles.append((title, (col_x[ch], y)))
            x, row_y = col_x[ch] + 7.62, y + 15.24
            for p in items:
                w = CELL_W.get(p.kind, 27.94 if ch == "-" else 17.78)
                if x + w > col_x[ch] + BLOCK_MAX_W:
                    x, row_y = col_x[ch] + 7.62, row_y + ROW_H
                positions[id(p)] = (snap(x + (12.7 if p.kind in ("OPAMP", "D", "SIG_CONN", "PWR_CONN") else 0)),
                                    snap(row_y))
                x += w
            y = row_y + ROW_H - 7.62
    return positions, titles


# ------------------------------------------------------------ hoofdprogramma
def main() -> None:
    parts = build.all_parts()
    positions, titles = layout(parts)
    lib_ids = sorted(set(SYMBOL_OF[p.kind] for p in parts) | set(POWER_NETS.values()) | {"power:PWR_FLAG"})
    syms = {lid: flat_symbol(lid) for lid in lib_ids}
    pins = {lid: pin_table(s) for lid, s in syms.items()}

    items, pcb_parts, pwr_n = [], {}, [0]

    def power_symbol(net, xy, direction):
        pwr_n[0] += 1
        lid = POWER_NETS[net]
        if net == "GND":
            ang = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}[direction]
        else:
            ang = {(0, -1): 0, (0, 1): 180, (1, 0): 270, (-1, 0): 90}[direction]
        ref = f"#PWR{pwr_n[0]:03d}"
        return symbol_instance(lid, ref, net, xy, 1, "", "", ["1"], ("pwr", pwr_n[0]), angle=ang,
                               in_bom=False, ref_xy=(xy[0], xy[1] + 5), val_xy=(xy[0] + 1.27, xy[1] + 3.5))

    for p in parts:
        lid = SYMBOL_OF[p.kind]
        xy = positions[id(p)]
        if p.kind in ("OPAMP", "OPAMP_PWR"):
            unit_letter = p.extra["unit"]
            unit = UNIT_NUM[unit_letter]
            ref = p.extra["ic"]
            pinmap = {OPAMP_PINS[unit_letter][k]: net for k, net in p.nets.items()}
        else:
            unit, ref = 1, p.ref
            pinmap = {("1" if k == "K" else "2" if k == "A" else k): net for k, net in p.nets.items()}
        sym_pins = [num for (u, num) in pins[lid] if u in (0, unit)]
        items.append(symbol_instance(lid, ref, p.value, xy, unit, p.footprint, p.descr, sym_pins,
                                     ("sym", p.ref), kind=p.kind))
        for num, net in pinmap.items():
            pin = pins[lid].get((unit, num)) or pins[lid].get((0, num))
            (x, y), (dx, dy) = pin_pos(xy, pin)
            end = (snap(x + dx * 2.54), snap(y + dy * 2.54))
            items.append(wire((x, y), end))
            if net in POWER_NETS:
                items.append(power_symbol(net, end, (dx, dy)))
            else:
                items.append(label(net, end, (dx, dy)))
        # printgegevens: per IC samenvoegen
        entry = pcb_parts.setdefault(ref, {"ref": ref, "value": p.value, "footprint": p.footprint,
                                           "pads": {}, "channel": p.channel, "block": p.block,
                                           "descr": p.descr, "symbol_uuid": uid("sym", p.ref)})
        entry["pads"].update(pinmap)
        if p.kind == "OPAMP" and p.extra["unit"] == "A":
            entry["symbol_uuid"] = uid("sym", p.ref)
            entry["channel"], entry["block"] = p.channel, "opamp"

    # PWR_FLAG op de voedingsnetten (bij J1) zodat ERC weet dat ze gevoed worden
    j1 = positions[id(next(p for p in parts if p.ref == "J1"))]
    for i, net in enumerate(("+15V", "GND", "-15V")):
        xy = (snap(j1[0] + 160.0 + i * 15.24), snap(j1[1] - 5.08))
        items.append(symbol_instance("power:PWR_FLAG", f"#FLG0{i + 1}", "PWR_FLAG", xy, 1, "", "",
                                     ["1"], ("flg", i), in_bom=False,
                                     ref_xy=(xy[0], xy[1] - 5), val_xy=(xy[0], xy[1] - 3.5)))
        end = (xy[0], snap(xy[1] + 2.54))
        items.append(wire(xy, end))
        items.append(power_symbol(net, end, (0, 1) if net == "GND" else (0, -1)) if net == "GND"
                     else power_symbol(net, end, (0, -1)))

    for t, xy in titles:
        items.append(text(t, (snap(xy[0]), snap(xy[1]))))
    items.append(text("Opamp-voorversterker met 12AX7-karakter (stereo). Ontwerp: genetisch algoritme "
                      "(circuitbuilder). Alle weerstanden metaalfilm 1 %.", (25.4, 17.78), size=2.5))

    today = dt.date.today().isoformat()
    sch = ["kicad_sch", ["version", "20250114"], ["generator", Q("circuitbuilder")],
           ["generator_version", Q("9.0")], ["uuid", Q(ROOT_UUID)], ["paper", Q("A1")],
           ["title_block", ["title", Q("Warme opamp-voorversterker (12AX7-karakter)")],
            ["date", Q(today)], ["rev", Q("1.0")], ["company", Q("circuitbuilder")],
            ["comment", 1, Q("Stereo, 3x NE5532P, +/-15 V, versterking 10 dB")],
            ["comment", 2, Q("Waarden geoptimaliseerd met genetisch algoritme t.o.v. 12AX7-trap")]],
           ["lib_symbols"] + list(syms.values())] + items + [
           ["sheet_instances", ["path", Q("/"), ["page", Q("1")]]], ["embedded_fonts", "no"]]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"{PROJECT}.kicad_sch").write_text(dump(sch) + "\n", encoding="utf-8")
    (OUTDIR / "parts.json").write_text(json.dumps(sorted(pcb_parts.values(), key=lambda e: e["ref"]),
                                                  indent=1, ensure_ascii=False), encoding="utf-8")
    pro = OUTDIR / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text(json.dumps({"meta": {"filename": f"{PROJECT}.kicad_pro", "version": 3}},
                                  indent=2), encoding="utf-8")
    print(f"Schema: {OUTDIR / (PROJECT + '.kicad_sch')}  ({len(parts)} symbool-eenheden)")
    print(f"Printdata: {OUTDIR / 'parts.json'}  ({len(pcb_parts)} componenten)")


if __name__ == "__main__":
    main()
