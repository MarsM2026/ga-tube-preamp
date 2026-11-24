"""Bouw de complete hardware-uitvoer opnieuw op, in de juiste volgorde.

  1. KiCad-schema + parts.json          (scripts/kicad_schematic.py, venv-Python)
  2. Print: plaatsing + DSN              (scripts/kicad_pcb.py place, KiCad-Python)
  3. Automatisch routeren                (Freerouting, Java)
  4. Print afwerken: SES, massavlakken   (scripts/kicad_pcb.py finish, KiCad-Python)
  5. ERC en DRC                          (kicad-cli)
  6. Exports naar hardware/export/       (Gerbers + boorbestanden als zip, schema-PDF/SVG,
                                          print-SVG per laag, 3D-renders, BOM)
  7. Alleen SMD: montagebestanden voor een fabrikant (JLCPCB-formaat: BOM + CPL)

Gebruik:  python scripts/make_hardware.py [--variant tht|smd] [--skip-route]
          tht (standaard): hardware/kicad + hardware/export
          smd:             hardware/kicad_smd + hardware/export_smd
Paden:    KICAD_DIR (standaard %LOCALAPPDATA%/Programs/KiCad/10.0), Java in PATH.
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
HW = EXPORT = PCB = SCH = None  # gezet in main() per variant


def ref_key(r: str):
    return (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))


def assembly_files() -> None:
    """Montagebestanden in JLCPCB-formaat (ook bruikbaar voor andere fabrikanten).

    BOM: Comment, Designator, Footprint, LCSC Part #   (LCSC-nummers leeg: kies ze in de
         onderdelenzoeker van de fabrikant; de omschrijving staat in kolom Description)
    CPL: Designator, Mid X, Mid Y, Layer, Rotation      (uit kicad-cli pcb export pos)
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
            if r["Ref"].startswith("H"):  # montagegaten
                continue
            w.writerow([r["Ref"], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm",
                        "Top" if r["Side"] == "top" else "Bottom", f"{float(r['Rot']):g}"])
    pos.unlink()
    print(f"  montagebestanden: {len(rows)} BOM-regels, CPL met {len(parts)} posities")


def run(cmd, cwd=None, timeout=900):
    print(">", " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, timeout=timeout, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + "\n  ".join(out.splitlines()[-6:]))
    if r.returncode != 0:
        raise SystemExit(f"mislukt (exit {r.returncode})")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="tht", choices=["tht", "smd"])
    ap.add_argument("--skip-route", action="store_true", help="bestaande .ses hergebruiken")
    ap.add_argument("--render-quality", default="basic", choices=["basic", "high"],
                    help="3D-renders: basic (snel) of high (ca. 15 min per beeld)")
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
    run([CLI, "sch", "export", "pdf", "-o", EXPORT / "schema.pdf", SCH])
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
    run([CLI, "pcb", "export", "pdf", "-o", EXPORT / "print_lagen.pdf", "--mode-separate",
         "--layers", "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts", PCB])
    for name, layers in (("print_boven", "F.Cu,F.Silkscreen,Edge.Cuts"),
                         ("print_onder", "B.Cu,B.Silkscreen,Edge.Cuts"),
                         ("print_opbouw", "F.Silkscreen,F.Fab,Edge.Cuts")):
        run([CLI, "pcb", "export", "svg", "--mode-single", "--layers", layers, "--fit-page-to-board",
             "--exclude-drawing-sheet", "-o", EXPORT / f"{name}.svg", PCB])
    for side in ("top", "bottom"):
        run([CLI, "pcb", "render", "--side", side, "--quality", args.render_quality,
             "--width", "1800", "--height", "1200", "--background", "transparent", "-o", EXPORT / f"render_3d_{side}.png", PCB],
            timeout=1800)
    run([CLI, "pcb", "render", "--side", "top", "--rotate", "-45,0,30", "--quality", args.render_quality,
         "--width", "1800", "--height", "1200", "--zoom", "0.9", "--background", "transparent",
         "-o", EXPORT / "render_3d_schuin.png", PCB], timeout=1800)
    bom = ROOT / "hardware" / ("bom.csv" if args.variant == "tht" else "bom_smd.csv")
    if bom.exists():  # leesbare onderdelenlijst uit make_docs_assets.py
        shutil.copy(bom, EXPORT / "bom.csv")
    if args.variant == "smd":
        assembly_files()
    print(f"\nKlaar. Uitvoer in {EXPORT}")


if __name__ == "__main__":
    main()
