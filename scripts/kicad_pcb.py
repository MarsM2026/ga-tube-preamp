"""Genereer de print (hardware/kicad/warm_preamp.kicad_pcb) met de KiCad-Python-API.

Draaien met de Python van KiCad (niet de venv), in drie stappen:

  python.exe scripts/kicad_pcb.py place [smd]   # plaatsing + nets -> .kicad_pcb en .dsn
  java -jar tools/freerouting/freerouting.jar -de ... -do ...   (zie scripts/make_hardware.py)
  python.exe scripts/kicad_pcb.py finish [smd]  # .ses importeren, massavlakken, tekst

Zonder 'smd': through-hole-variant in hardware/kicad/; met 'smd': hardware/kicad_smd/.

Indeling (bovenaanzicht, ca. 178 x 100 mm; breedte volgt uit de plaatsing):
  - IC's U1 (ingangstrap), U2 (inverter), U3 (sommator) op de middenlijn;
    eenheid A (pinnen 1-3) wijst naar kanaal L (boven), eenheid B (5-7) naar kanaal R (onder)
  - kanaal L in de bovenste helft, kanaal R gespiegeld in de onderste helft
  - signaalstroom van links (ingangen J2/J3) naar rechts (uitgangen J4/J5)
  - voeding J1 links in het midden, ontkoppeling direct naast elk IC
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pcbnew as P

ROOT = Path(__file__).resolve().parent.parent
SMD = len(sys.argv) > 2 and sys.argv[2] == "smd"
HW = ROOT / "hardware" / ("kicad_smd" if SMD else "kicad")
BOARD_FILE = HW / "warm_preamp.kicad_pcb"
DSN_FILE = HW / "warm_preamp.dsn"
SES_FILE = HW / "warm_preamp.ses"
KICAD = Path(os.environ.get("KICAD_DIR", r"C:\Users\marce\AppData\Local\Programs\KiCad\10.0"))
FPLIB = KICAD / "share" / "kicad" / "footprints"

if SMD:
    W, H = 60.0, 72.0
    ROWS_L = [7.5, 14.0, 20.5, 27.0]  # max. één elco per blok, dus 6,5 mm steek volstaat
    IC_BLOCK_MIN_W = 11.0
    COL_GAP, BLOCK_GAP = 0.8, 1.5
    DEC_DX = 5.0             # ontkoppel-C naast het IC
    TRACK, CLEAR, PWR_TRACK = 0.3, 0.2, 0.6
else:
    W, H = 100.0, 100.0      # printafmetingen [mm]; W groeit mee met de plaatsing
    ROWS_L = [8.0, 18.0, 28.0, 38.0]  # rij-middens kanaal L (gespiegeld voor R)
    IC_BLOCK_MIN_W = 18.0    # minimale blokbreedte rond een IC (socket + ontkoppeling)
    DEC_DX = 7.5
    COL_GAP, BLOCK_GAP = 1.2, 2.5
    TRACK, CLEAR, PWR_TRACK = 0.4, 0.25, 0.8
OX, OY = 100.0, 50.0         # oorsprong op het KiCad-canvas
MID = H / 2
BLOCKS = ["ingang", "versterker", "inverter", "voorspanning", "tak A", "tak B", "sommator", "uitgang"]
IC_OF_BLOCK = {"versterker": "U1", "inverter": "U2", "sommator": "U3"}
SUPPLY_NETS = {"+15V", "-15V", "GND"}              # netten van voedingssymbolen
POWER_NETS = {"+15V", "-15V", "GND", "/VP_L", "/VP_R"}  # brede sporen


def pcb_net_name(n: str) -> str:
    """Netnaam zoals KiCad hem uit het schema afleidt (lokale labels: '/NAAM')."""
    return n if n in SUPPLY_NETS else "/" + n


def mm(v: float) -> int:
    return P.FromMM(v)


def pt(x: float, y: float):
    return P.VECTOR2I(mm(OX + x), mm(OY + y))


def load_fp(fpid: str):
    lib, name = fpid.split(":")
    fp = P.FootprintLoad(str(FPLIB / f"{lib}.pretty"), name)
    if fp is None:
        raise RuntimeError(f"footprint niet gevonden: {fpid}")
    fp.SetFPID(P.LIB_ID(lib, name))
    return fp


def center_at(fp, x: float, y: float, angle: float = 0.0) -> None:
    fp.SetOrientationDegrees(angle)
    bb = fp.GetBoundingBox(False)  # zonder tekst
    c = bb.GetCenter()
    target = pt(x, y)
    fp.Move(P.VECTOR2I(target.x - c.x, target.y - c.y))


MEASURED_W: dict = {}         # SMD: gemeten breedte per referentie (na draaien)


def column_width(part) -> float:
    fp = part["footprint"]
    if SMD:
        return MEASURED_W[part["ref"]]
    if "CP_Radial_D10" in fp:
        return 11.5
    if "CP_Radial_D8" in fp:
        return 9.5
    if "Radial_D6.3" in fp:
        return 7.6
    if "Potentiometer" in fp:
        return 10.5
    if "C_Rect" in fp:
        return 7.6
    return 5.6


def is_vertical(part) -> bool:
    fp = part["footprint"]
    return (fp.startswith(("Resistor_THT", "Diode_THT", "Resistor_SMD", "Diode_SMD"))
            or any(k in fp for k in ("C_Rect", "C_Disc", "C_0805", "C_1206", "Elec_6.3x7.7")))


def place(board, parts) -> None:
    by_ref = {p["ref"]: p for p in parts}
    fps = {}
    nets = {}

    def net(name):
        if name not in nets:
            ni = P.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    for p in parts:
        fp = load_fp(p["footprint"])
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPath(P.KIID_PATH("/" + p["symbol_uuid"]))
        board.Add(fp)
        for pad in fp.Pads():
            n = p["pads"].get(pad.GetNumber())
            if n:
                pad.SetNet(net(pcb_net_name(n)))
        fp.SetField("Description", p["descr"])
        fp.SetField("Datasheet", "~")
        fps[p["ref"]] = fp
        if SMD:  # breedte van de footprint zoals hij straks gedraaid staat, plus marge
            fp.SetOrientationDegrees(90.0 if is_vertical(p) else 0.0)
            MEASURED_W[p["ref"]] = P.ToMM(fp.GetBoundingBox(False).GetWidth()) + 0.4

    # ---------------- kanaalcomponenten in kolommen per blok
    block_span = {}
    x_start = 15.0
    for ch, rows in (("L", ROWS_L), ("R", [H - r for r in ROWS_L])):
        x = x_start
        for blk in BLOCKS:
            items = [p for p in parts if p["channel"] == ch and p["block"] == blk
                     and not p["ref"].startswith(("U", "J"))]
            if not items:
                continue
            x0 = x
            col, colw = [], 0.0
            for p in items + [None]:
                big = p is not None and column_width(p) > 10.0  # grote elco: eigen kolom
                if p is not None and not big and len(col) < len(rows) and not (
                        col and column_width(col[0]) > 10.0):
                    col.append(p)
                    colw = max(colw, column_width(p))
                    continue
                for r, q in zip(rows, col):
                    center_at(fps[q["ref"]], x + colw / 2, r, 90.0 if is_vertical(q) else 0.0)
                x += colw + COL_GAP
                col, colw = ([p], column_width(p)) if p is not None else ([], 0.0)
            if blk in IC_OF_BLOCK and x - x0 < IC_BLOCK_MIN_W:
                shift = (IC_BLOCK_MIN_W - (x - x0)) / 2  # kolommen centreren in het blok
                for q in items:
                    fps[q["ref"]].Move(P.VECTOR2I(mm(shift), 0))
                x = x0 + IC_BLOCK_MIN_W
            block_span.setdefault(blk, []).append((x0, x))
            x += BLOCK_GAP
        global W
        W = max(W, x + (12.0 if SMD else 8.0))

    # ---------------- IC's op de middenlijn, onder het midden van hun blok
    for blk, ic in IC_OF_BLOCK.items():
        spans = block_span[blk]
        cx = sum((a + b) / 2 for a, b in spans) / len(spans)
        # pin 1 linksboven: rij 1-4 boven (eenheid A -> L), 5-8 onder (eenheid B -> R)
        center_at(fps[ic], cx, MID, 90.0)
        pin1 = [pd for pd in fps[ic].Pads() if pd.GetNumber() == "1"][0].GetPosition()
        if pin1.y > pt(0, MID).y:  # zorg dat pin 1 boven ligt
            center_at(fps[ic], cx, MID, 270.0)
        # ontkoppeling links/rechts van het IC
        dec = [p for p in parts if p["descr"].startswith(f"ontkoppeling {ic} ")]
        for p, dx in zip(sorted(dec, key=lambda q: q["ref"]), (-DEC_DX, DEC_DX)):
            center_at(fps[p["ref"]], cx + dx, MID, 90.0)

    # ---------------- aansluitingen en bulkcondensatoren
    center_at(fps["J1"], 5.5, MID, 90.0)
    center_at(fps["C1"], 15.5, MID - 6.5, 0.0)
    center_at(fps["C2"], 15.5, MID + 6.5, 0.0)
    if SMD:  # schroefklemmen, draadinvoer naar de rand
        center_at(fps["J2"], 5.5, ROWS_L[1], 90.0)
        center_at(fps["J3"], 5.5, H - ROWS_L[1], 90.0)
        center_at(fps["J4"], W - 5.5, ROWS_L[1], 270.0)
        center_at(fps["J5"], W - 5.5, H - ROWS_L[1], 270.0)
    else:
        center_at(fps["J2"], 4.0, ROWS_L[1], 0.0)
        center_at(fps["J3"], 4.0, H - ROWS_L[1], 0.0)
        center_at(fps["J4"], W - 4.0, ROWS_L[1], 0.0)
        center_at(fps["J5"], W - 4.0, H - ROWS_L[1], 0.0)

    # ---------------- printomtrek en montagegaten
    rect = P.PCB_SHAPE(board)
    rect.SetShape(P.SHAPE_T_RECT)
    rect.SetStart(pt(0, 0))
    rect.SetEnd(pt(W, H))
    rect.SetLayer(P.Edge_Cuts)
    rect.SetWidth(mm(0.1))
    board.Add(rect)
    for i, (x, y) in enumerate(((3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5))):
        mh = load_fp("MountingHole:MountingHole_3.2mm_M3")
        mh.SetReference(f"H{i + 1}")
        mh.SetValue("M3")
        mh.SetBoardOnly(True)
        mh.SetExcludedFromBOM(True)
        board.Add(mh)
        center_at(mh, x, y)


def netclasses(board) -> None:
    ds = board.GetDesignSettings()
    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetTrackWidth(mm(TRACK))
    default.SetClearance(mm(CLEAR))
    default.SetViaDiameter(mm(0.9))
    default.SetViaDrill(mm(0.45))
    pwr = P.NETCLASS("Power")
    pwr.SetTrackWidth(mm(PWR_TRACK))
    pwr.SetClearance(mm(0.3))
    pwr.SetViaDiameter(mm(1.0))
    pwr.SetViaDrill(mm(0.5))
    ns.SetNetclass("Power", pwr)
    for n in POWER_NETS:
        ns.SetNetclassPatternAssignment(n, "Power")
    if SMD:  # één thermische spaak is genoeg voor kleine SMD-pads (bijv. ontkoppel-C's)
        ds.m_MinResolvedSpokes = 1
    ns.RecomputeEffectiveNetclasses()
    board.SynchronizeNetsAndNetClasses(True)


def add_zone(board, layer, netname) -> None:
    z = P.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(board.FindNet(netname).GetNetCode())
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)):
        p = pt(x, y)
        ol.Append(p.x, p.y)
    z.SetLocalClearance(mm(0.4))
    z.SetMinThickness(mm(0.3))
    z.SetPadConnection(P.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(mm(0.5))
    z.SetThermalReliefSpokeWidth(mm(0.5))
    board.Add(z)


def silk_text(board, s, x, y, size=1.5, layer=None, bold=False) -> None:
    t = P.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer if layer is not None else P.F_SilkS)
    t.SetTextSize(P.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * 0.15))
    t.SetBold(bold)
    if t.GetLayer() == P.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def cmd_place() -> None:
    parts = json.loads((HW / "parts.json").read_text(encoding="utf-8"))
    board = P.BOARD()
    board.SetCopperLayerCount(2)
    place(board, parts)
    netclasses(board)
    (HW / "board_size.json").write_text(json.dumps({"W": W, "H": H}))
    P.SaveBoard(str(BOARD_FILE), board)
    board = P.LoadBoard(str(BOARD_FILE))
    netclasses(board)
    ok = P.ExportSpecctraDSN(board, str(DSN_FILE))
    print(f"geplaatst: {len(parts)} componenten; DSN-export {'ok' if ok else 'MISLUKT'}")


def cmd_finish() -> None:
    global W, H
    size = json.loads((HW / "board_size.json").read_text())
    W, H = size["W"], size["H"]
    board = P.LoadBoard(str(BOARD_FILE))
    netclasses(board)
    if not P.ImportSpecctraSES(board, str(SES_FILE)):
        raise RuntimeError("SES-import mislukt")
    add_zone(board, P.B_Cu, "GND")
    add_zone(board, P.F_Cu, "GND")
    silk_text(board, "WARME OPAMP-VOORVERSTERKER  12AX7-karakter  rev 1.0" + (" SMD" if SMD else ""),
              W / 2, MID, 1.4 if not SMD else 1.1, P.B_SilkS, bold=True)
    silk_text(board, "+15 GND -15", 9.0, MID - 10.0, 1.0)
    dy = 7.0 if SMD else 4.0  # SMD: boven/onder de schroefklem
    for s, x, y in (("IN L", 4.5, ROWS_L[1] - dy), ("IN R", 4.5, H - ROWS_L[1] + dy),
                    ("OUT L", W - 5.0, ROWS_L[1] - dy), ("OUT R", W - 5.0, H - ROWS_L[1] + dy),
                    ("KANAAL L", W / 2, MID - 4.5), ("KANAAL R", W / 2, MID + 4.5)):
        silk_text(board, s, x, y, 1.2, bold=True)
    silk_text(board, "circuitbuilder - genetisch algoritme", W / 2, H - 2.5, 1.0, P.B_SilkS)
    filler = P.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    P.SaveBoard(str(BOARD_FILE), board)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    print(f"geroute: {len(tracks)} sporen, {len(vias)} vias; massavlakken gevuld")


if __name__ == "__main__":
    {"place": cmd_place, "finish": cmd_finish}[sys.argv[1]]()
