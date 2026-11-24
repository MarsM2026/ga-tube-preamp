"""Bouw de complete hardware-uitvoer opnieuw op, in de juiste volgorde.

  1. KiCad-schema + parts.json          (scripts/kicad_schematic.py, venv-Python)
  2. Print: plaatsing + DSN              (scripts/kicad_pcb.py place, KiCad-Python)
  3. Automatisch routeren                (Freerouting, Java)
  4. Print afwerken: SES, massavlakken   (scripts/kicad_pcb.py finish, KiCad-Python)
  5. ERC en DRC                          (kicad-cli)
  6. Exports naar hardware/export/       (Gerbers + boorbestanden als zip, schema-PDF/SVG,
                                          print-SVG per laag, 3D-renders, BOM)

Gebruik:  python scripts/make_hardware.py [--skip-route]
Paden:    KICAD_DIR (standaard %LOCALAPPDATA%/Programs/KiCad/10.0), Java in PATH.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "hardware" / "kicad"
EXPORT = ROOT / "hardware" / "export"
KICAD = Path(os.environ.get("KICAD_DIR", Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KiCad/10.0"))
CLI = str(KICAD / "bin" / "kicad-cli.exe")
KPY = str(KICAD / "bin" / "python.exe")
FREEROUTING = ROOT / "tools" / "freerouting" / "freerouting.jar"
PCB = HW / "warm_preamp.kicad_pcb"
SCH = HW / "warm_preamp.kicad_sch"


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
    ap.add_argument("--skip-route", action="store_true", help="bestaande .ses hergebruiken")
    ap.add_argument("--render-quality", default="basic", choices=["basic", "high"],
                    help="3D-renders: basic (snel) of high (ca. 15 min per beeld)")
    args = ap.parse_args()

    run([sys.executable, ROOT / "scripts" / "kicad_schematic.py"])
    run([KPY, ROOT / "scripts" / "kicad_pcb.py", "place"])
    if not args.skip_route:
        (HW / "warm_preamp.ses").unlink(missing_ok=True)
        run(["java", "-jar", FREEROUTING, "-de", "warm_preamp.dsn", "-do", "warm_preamp.ses",
             "--router.autorouter.max_passes=40", "--gui.enabled=false"], cwd=HW, timeout=1800)
    run([KPY, ROOT / "scripts" / "kicad_pcb.py", "finish"])

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
    shutil.copy(ROOT / "hardware" / "bom.csv", EXPORT / "bom.csv") if (ROOT / "hardware" / "bom.csv").exists() else None
    print(f"\nKlaar. Uitvoer in {EXPORT}")


if __name__ == "__main__":
    main()
