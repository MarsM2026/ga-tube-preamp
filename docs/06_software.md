# Running the software yourself

Everything is reproducible: from the tube simulation to the Gerber files.

## Requirements

- Windows, Python 3.13, Git (other platforms should work, but are untested)
- ngspice 47 (unpacked in `tools/Spice64`, or the environment variable `NGSPICE`)
- KiCad 10 (for schematic and PCB), Java 17+ and Freerouting 2.5 (`tools/freerouting/freerouting.jar`)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Steps

| Step | Command | Result |
|---|---|---|
| 1. Characterise the tube | `python scripts/run_reference.py` | `out/reference.png`, target curves |
| 2. Genetic algorithm | `python scripts/optimize.py --gen 40` | `out/best.json` (≈ 1 hour on 8 cores) |
| 3. Report on a design | `python scripts/report.py designs/run3.json` | parts, chart, netlist |
| 4. Check with NE5532 | `python scripts/compare_opamp.py designs/final.json` | `out/compare_ne5532.png` |
| 5. Sensitivity | `python scripts/sensitivity.py designs/final.json` | effect of 1 % per part |
| 6. Tolerances | `python scripts/montecarlo.py --n 24` | Monte Carlo with and without trimming |
| 7. As-built circuit | `python scripts/verify_build.py` | gain, noise, PSRR, harmonics |
| 8. Documentation schematic | `python scripts/draw_schematic.py` | `docs/img/schematic_channel.svg` |
| 9. Hardware | `python scripts/make_hardware.py` | through-hole: KiCad schematic, PCB, Gerbers, renders |
| 9b. Hardware SMD | `python scripts/make_hardware.py --variant smd` | same for the SMD version, plus assembly files (BOM + CPL) |
| 10. Documentation data | `python scripts/make_docs_assets.py` | `docs/data/*`, `docs/img/*` |

(All commands with `.\.venv\Scripts\python`.) Steps 4, 6 and 7 accept `--plot-only`
to redraw the chart from the saved JSON without simulating again.

## Code overview

| File | Role |
|---|---|
| `circuitbuilder/spice.py` | drive ngspice in batch mode |
| `circuitbuilder/analysis.py` | harmonics (least-squares fit), frequency response |
| `circuitbuilder/reference.py` | 12AX7 reference stage |
| `circuitbuilder/candidate.py` | candidate topology for the GA (genes → netlist) |
| `circuitbuilder/fitness.py` | target curves and cost function |
| `circuitbuilder/build.py` | **the as-built design**: single source for simulation, schematic, PCB and BOM; footprints per variant (tht/smd) |
| `circuitbuilder/models/` | 12AX7 (Koren), 1N4148, generic opamp, NE5532 (TI macromodel) |
| `scripts/kicad_schematic.py` | generates the KiCad schematic |
| `scripts/kicad_pcb.py` | placement, routing import, ground pours (KiCad Python) |

## Models and sources

- 12AX7: triode model by Norman Koren (1996), rewritten for ngspice.
- NE5532: TI/MicroSim "Parts" macromodel of the NE5534 with 22 pF compensation, via
  the [KiCad-Spice-Library](https://github.com/kicad-spice-library/KiCad-Spice-Library);
  checked for GBW (9.7 MHz), output swing (±13 V into 600 Ω) and noise
  (6.4 nV/√Hz, datasheet 5 nV/√Hz).
- Genetic algorithm: [pymoo](https://pymoo.org).
