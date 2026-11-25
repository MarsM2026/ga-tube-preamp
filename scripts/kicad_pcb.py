"""Generate the PCB (hardware/kicad/warm_preamp.kicad_pcb) with the KiCad Python API.

Run with KiCad's own Python (not the venv), in three steps:

  python.exe scripts/kicad_pcb.py place [smd]   # placement + nets -> .kicad_pcb and .dsn
  java -jar tools/freerouting/freerouting.jar -de ... -do ...   (see scripts/make_hardware.py)
  python.exe scripts/kicad_pcb.py finish [smd]  # import .ses, ground pours, text

Without 'smd': through-hole variant in hardware/kicad/; with 'smd': hardware/kicad_smd/.

Layout (top view, approx. 178 x 100 mm; the width follows from the placement):
  - ICs U1 (input stage), U2 (inverter), U3 (summer) on the centre line;
    unit A (pins 1-3) faces channel L (top), unit B (5-7) faces channel R (bottom)
  - channel L in the top half, channel R mirrored in the bottom half
  - signal flows from left (inputs J2/J3) to right (outputs J4/J5)
  - power J1 on the left in the middle, decoupling right next to each IC
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
KICAD = Path(os.environ.get("KICAD_DIR",
                          Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
FPLIB = KICAD / "share" / "kicad" / "footprints"

if SMD:
    W, H = 60.0, 72.0
    ROWS_L = [7.5, 14.0, 20.5, 27.0]  # at most one electrolytic per block, so a 6.5 mm pitch is enough
    IC_BLOCK_MIN_W = 11.0
    COL_GAP, BLOCK_GAP = 0.8, 1.5
    DEC_DX = 5.0             # decoupling cap next to the IC
    TRACK, CLEAR, PWR_TRACK = 0.3, 0.2, 0.6
else:
    W, H = 100.0, 100.0      # board size [mm]; W grows with the placement
    ROWS_L = [8.0, 18.0, 28.0, 38.0]  # row centres of channel L (mirrored for R)
    IC_BLOCK_MIN_W = 18.0    # minimum block width around an IC (socket + decoupling)
    DEC_DX = 7.5
    COL_GAP, BLOCK_GAP = 1.2, 2.5
    TRACK, CLEAR, PWR_TRACK = 0.4, 0.25, 0.8
OX, OY = 100.0, 50.0         # origin on the KiCad canvas
MID = H / 2
BLOCKS = ["input", "amplifier", "inverter", "bias", "branch A", "branch B", "summer", "output"]
IC_OF_BLOCK = {"amplifier": "U1", "inverter": "U2", "summer": "U3"}
SUPPLY_NETS = {"+15V", "-15V", "GND"}              # nets of power symbols
POWER_NETS = {"+15V", "-15V", "GND", "/VP_L", "/VP_R"}  # wide tracks


def pcb_net_name(n: str) -> str:
    """Net name as KiCad derives it from the schematic (local labels: '/NAME')."""
    return n if n in SUPPLY_NETS else "/" + n


def mm(v: float) -> int:
    return P.FromMM(v)


def pt(x: float, y: float):
    return P.VECTOR2I(mm(OX + x), mm(OY + y))


def load_fp(fpid: str):
    lib, name = fpid.split(":")
    fp = P.FootprintLoad(str(FPLIB / f"{lib}.pretty"), name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    fp.SetFPID(P.LIB_ID(lib, name))
    return fp


def center_at(fp, x: float, y: float, angle: float = 0.0) -> None:
    fp.SetOrientationDegrees(angle)
    bb = fp.GetBoundingBox(False)  # without text
    c = bb.GetCenter()
    target = pt(x, y)
    fp.Move(P.VECTOR2I(target.x - c.x, target.y - c.y))


MEASURED_W: dict = {}         # SMD: measured width per reference (after rotation)


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
        if SMD:  # width of the footprint as it will be rotated, plus margin
            fp.SetOrientationDegrees(90.0 if is_vertical(p) else 0.0)
            MEASURED_W[p["ref"]] = P.ToMM(fp.GetBoundingBox(False).GetWidth()) + 0.4

    # ---------------- channel components in columns per block
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
                big = p is not None and column_width(p) > 10.0  # large electrolytic: own column
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
                shift = (IC_BLOCK_MIN_W - (x - x0)) / 2  # centre the columns in the block
                for q in items:
                    fps[q["ref"]].Move(P.VECTOR2I(mm(shift), 0))
                x = x0 + IC_BLOCK_MIN_W
            block_span.setdefault(blk, []).append((x0, x))
            x += BLOCK_GAP
        global W
        W = max(W, x + (12.0 if SMD else 8.0))

    # ---------------- ICs on the centre line, below the middle of their block
    for blk, ic in IC_OF_BLOCK.items():
        spans = block_span[blk]
        cx = sum((a + b) / 2 for a, b in spans) / len(spans)
        # pin 1 top left: pins 1-4 on top (unit A -> L), 5-8 at the bottom (unit B -> R)
        center_at(fps[ic], cx, MID, 90.0)
        pin1 = [pd for pd in fps[ic].Pads() if pd.GetNumber() == "1"][0].GetPosition()
        if pin1.y > pt(0, MID).y:  # make sure pin 1 is on top
            center_at(fps[ic], cx, MID, 270.0)
        # decoupling left/right of the IC
        dec = [p for p in parts if p["descr"].startswith(f"decoupling {ic} ")]
        for p, dx in zip(sorted(dec, key=lambda q: q["ref"]), (-DEC_DX, DEC_DX)):
            center_at(fps[p["ref"]], cx + dx, MID, 90.0)

    # ---------------- connectors and bulk capacitors
    center_at(fps["J1"], 5.5, MID, 90.0)
    center_at(fps["C1"], 15.5, MID - 6.5, 0.0)
    center_at(fps["C2"], 15.5, MID + 6.5, 0.0)
    if SMD:  # screw terminals, wire entry towards the edge
        center_at(fps["J2"], 5.5, ROWS_L[1], 90.0)
        center_at(fps["J3"], 5.5, H - ROWS_L[1], 90.0)
        center_at(fps["J4"], W - 5.5, ROWS_L[1], 270.0)
        center_at(fps["J5"], W - 5.5, H - ROWS_L[1], 270.0)
    else:
        center_at(fps["J2"], 4.0, ROWS_L[1], 0.0)
        center_at(fps["J3"], 4.0, H - ROWS_L[1], 0.0)
        center_at(fps["J4"], W - 4.0, ROWS_L[1], 0.0)
        center_at(fps["J5"], W - 4.0, H - ROWS_L[1], 0.0)

    # ---------------- board outline and mounting holes
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
    if SMD:  # one thermal spoke is enough for small SMD pads (e.g. decoupling caps)
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
    print(f"placed: {len(parts)} components; DSN export {'ok' if ok else 'FAILED'}")


def cmd_finish() -> None:
    global W, H
    size = json.loads((HW / "board_size.json").read_text())
    W, H = size["W"], size["H"]
    board = P.LoadBoard(str(BOARD_FILE))
    netclasses(board)
    if not P.ImportSpecctraSES(board, str(SES_FILE)):
        raise RuntimeError("SES import failed")
    add_zone(board, P.B_Cu, "GND")
    add_zone(board, P.F_Cu, "GND")
    silk_text(board, "WARM OPAMP PREAMP  12AX7 character  rev 1.0" + (" SMD" if SMD else ""),
              W / 2, MID, 1.4 if not SMD else 1.1, P.B_SilkS, bold=True)
    silk_text(board, "+15 GND -15", 9.0, MID - 10.0, 1.0)
    dy = 7.0 if SMD else 4.0  # SMD: above/below the screw terminal
    for s, x, y in (("IN L", 4.5, ROWS_L[1] - dy), ("IN R", 4.5, H - ROWS_L[1] + dy),
                    ("OUT L", W - 5.0, ROWS_L[1] - dy), ("OUT R", W - 5.0, H - ROWS_L[1] + dy),
                    ("CHANNEL L", W / 2, MID - 4.5), ("CHANNEL R", W / 2, MID + 4.5)):
        silk_text(board, s, x, y, 1.2, bold=True)
    silk_text(board, "KyntoSoftware - designed by a genetic algorithm", W / 2, H - 2.5, 1.0, P.B_SilkS)
    filler = P.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    P.SaveBoard(str(BOARD_FILE), board)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    print(f"routed: {len(tracks)} tracks, {len(vias)} vias; ground pours filled")


if __name__ == "__main__":
    {"place": cmd_place, "finish": cmd_finish}[sys.argv[1]]()
