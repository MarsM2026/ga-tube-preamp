# Documentation: warm opamp preamp

Read in this order:

1. [Overview](01_overview.md): what it is, key figures
2. [How the circuit works](02_how_it_works.md)
3. [Design process with a genetic algorithm](03_design_process.md)
4. [Results and checks](04_results.md)
5. [Build guide](05_build_guide.md)
6. [Running the software yourself](06_software.md)
7. [Having it made ready-to-use (SMD version)](07_assembled_smd.md)

## Folders

| Folder | Content |
|---|---|
| `docs/` | texts (Markdown) |
| `docs/img/` | charts and the readable schematic |
| `docs/data/` | raw numbers as JSON/CSV (for interactive charts) |
| `hardware/kicad/` | KiCad 10 project, through-hole (schematic, PCB, ERC/DRC reports) |
| `hardware/export/` | through-hole: Gerbers (zip), schematic PDF, PCB layers (SVG), 3D renders, BOM |
| `hardware/kicad_smd/` | KiCad 10 project, SMD version |
| `hardware/export_smd/` | SMD: Gerbers, assembly files (BOM + CPL), schematic PDF, PCB layers, 3D renders |
| `designs/` | design values per GA run and the final design |
