"""Rebuild the complete hardware output, in the right order.

  1. KiCad schematic + parts.json       (scripts/kicad_schematic.py, venv Python)
  2. PCB: placement + DSN                (scripts/kicad_pcb.py place, KiCad Python)
  3. Autorouting                         (Freerouting, Java)
  4. Finish PCB: SES, ground pours       (scripts/kicad_pcb.py finish, KiCad Python)
  5. ERC and DRC                         (kicad-cli)
  6. Exports to hardware/export/         (Gerbers + drill files as zip, schematic PDF/SVG,
                                          PCB SVG per layer, 3D renders, BOM)
  7. SMD only: assembly files for a fab  (JLCPCB format: BOM + CPL)

Usage:  python scripts/make_hardware.py [--variant tht|smd] [--skip-route]
        tht (default): hardware/kicad + hardware/export
        smd:           hardware/kicad_smd + hardware/export_smd
Paths:  KICAD_DIR (default %LOCALAPPDATA%/Programs/KiCad/10.0), Java in PATH.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import build  # noqa: E402
KICAD = Path(os.environ.get("KICAD_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
CLI = str(KICAD / "bin" / "kicad-cli.exe")
KPY = str(KICAD / "bin" / "python.exe")
FREEROUTING = ROOT / "tools" / "freerouting" / "freerouting.jar"
HW = EXPORT = PCB = SCH = None  # set per variant in main()


def ref_key(r: str):
    return (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))


def assembly_files() -> None:
    """Assembly files in JLCPCB format (also usable for other fabs).

    BOM: Comment, Designator, Footprint, LCSC Part #   (LCSC numbers left empty: pick them
         in the fab's parts search; the description is in the Description column)
    CPL: Designator, Mid X, Mid Y, Layer, Rotation      (from kicad-cli pcb export pos)
    """
    parts = json.loads((HW / "parts.json").read_text(encoding="utf-8"))
    groups: dict = {}
    for p in parts:
        groups.setdefault((p["value"], p["footprint"]), []).append(p)
    rows = []
    for (value, fpid), ps in sorted(groups.items(), key=lambda kv: ref_key(kv[1][0]["ref"])):
        refs = sorted((p["ref"] for p in ps), key=ref_key)
        rows.append({"Comment": value, "Designator": ",".join(refs),
                     "Footprint": fpid.split(":")[1], "LCSC Part #": "",
                     "Quantity": len(refs), "Description": ps[0]["descr"]})
    with open(EXPORT / "jlcpcb_bom.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    pos = EXPORT / "positions_kicad.csv"
    run([CLI, "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
         "--exclude-dnp", "-o", pos, PCB])
    with open(pos, encoding="utf-8") as f, open(EXPORT / "jlcpcb_cpl.csv", "w", newline="",
                                                 encoding="utf-8") as g:
        w = csv.writer(g)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in csv.DictReader(f):
            if r["Ref"].startswith("H"):  # mounting holes
                continue
            w.writerow([r["Ref"], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                        "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):g}"])
    pos.unlink()
    print(f"  assembly files: {len(rows)} BOM lines, CPL with {len(parts)} positions")


def run(cmd, cwd=None, timeout=900):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, timeout=timeout, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + "\n  ".join(out.splitlines()[-6:]))
    if r.returncode != 0:
        raise SystemExit(f"failed (exit {r.returncode})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="tht", choices=["tht", "smd"])
    ap.add_argument("--skip-route", action="store_true", help="reuse the existing .ses")
    ap.add_argument("--render-quality", default="basic", choices=["basic", "high"],
                    help="3D renders: basic (fast) or high (approx. 15 min per image)")
    args = ap.parse_args()
    global HW, EXPORT, PCB, SCH
    build.set_variant(args.variant)
    HW, EXPORT = build.hw_dirs()
    PCB, SCH = HW / "warm_preamp.kicad_pcb", HW / "warm_preamp.kicad_sch"
    smd = ["smd"] if args.variant == "smd" else []

    run([sys.executable, ROOT / "scripts" / "kicad_schematic.py", "--variant", args.variant])
    run([KPY, ROOT / "scripts" / "kicad_pcb.py", "place"] + smd)
    if not args.skip_route:
        (HW / "warm_preamp.ses").unlink(missing_ok=True)
        run(["java", "-jar", FREEROUTING, "-de", "warm_preamp.dsn", "-do", "warm_preamp.ses",
             "--router.autorouter.max_passes=40", "--gui.enabled=false"], cwd=HW, timeout=1800)
    run([KPY, ROOT / "scripts" / "kicad_pcb.py", "finish"] + smd)

    run([CLI, "sch", "erc", "--severity-all", "-o", "erc.rpt", SCH.name], cwd=HW)
    run([CLI, "pcb", "drc", "--severity-all", "--schematic-parity", "-o", "drc.rpt", PCB.name], cwd=HW)

    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    (EXPORT / "gerber").mkdir(parents=True)
    run([CLI, "sch", "export", "pdf", "-o", EXPORT / "schematic.pdf", SCH])
    run([CLI, "sch", "export", "svg", "-o", EXPORT, SCH])
    run([CLI, "sch", "export", "bom", "-o", EXPORT / "bom_kicad.csv",
         "--fields", "Reference,Value,Footprint,${QUANTITY},Description",
         "--group-by", "Value,Footprint", "--exclude-dnp", SCH])
    run([CLI, "pcb", "export", "gerbers", "-o", str(EXPORT / "gerber") + os.sep,
         "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts", PCB])
    run([CLI, "pcb", "export", "drill", "-o", str(EXPORT / "gerber") + os.sep,
         "--format", "excellon", "--excellon-separate-th", "--generate-map", "--map-format", "pdf", PCB])
    with zipfile.ZipFile(EXPORT / "warm_preamp_gerbers.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((EXPORT / "gerber").iterdir()):
            z.write(f, f.name)
    run([CLI, "pcb", "export", "pdf", "-o", EXPORT / "pcb_layers.pdf", "--mode-separate",
         "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts", PCB])
    for name, layers in (("pcb_top", "F.Cu,F.Silkscreen,Edge.Cuts"),
                         ("pcb_bottom", "B.Cu,B.Silkscreen,Edge.Cuts"),
                         ("pcb_assembly", "F.Silkscreen,F.Fab,Edge.Cuts")):
        run([CLI, "pcb", "export", "svg", "--mode-single", "--layers", layers, "--fit-page-to-board",
             "--exclude-drawing-sheet", "-o", EXPORT / f"{name}.svg", PCB])
    for side in ("top", "bottom"):
        run([CLI, "pcb", "render", "--side", side, "--quality", args.render_quality,
             "--width", "1800", "--height", "1200", "--background", "transparent", "-o", EXPORT / f"render_3d_{side}.png", PCB],
            timeout=1800)
    run([CLI, "pcb", "render", "--side", "top", "--rotate", "-45,0,30", "--quality", args.render_quality,
         "--width", "1800", "--height", "1200", "--zoom", "0.9", "--background", "transparent",
         "-o", EXPORT / "render_3d_angled.png", PCB], timeout=1800)
    bom = ROOT / "hardware" / ("bom.csv" if args.variant == "tht" else "bom_smd.csv")
    if bom.exists():  # readable parts list from make_docs_assets.py
        shutil.copy(bom, EXPORT / "bom.csv")
    if args.variant == "smd":
        assembly_files()
    print(f"\nDone. Output in {EXPORT}")


if __name__ == "__main__":
    main()
