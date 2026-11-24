# De software zelf draaien

Alles is reproduceerbaar: van de buissimulatie tot de Gerber-bestanden.

## Benodigdheden

- Windows, Python 3.13, Git
- ngspice 47 (uitgepakt in `tools/Spice64`, of omgevingsvariabele `NGSPICE`)
- KiCad 10 (voor schema en print), Java 17+ en Freerouting 2.5 (`tools/freerouting/freerouting.jar`)

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## Stappen

| Stap | Commando | Resultaat |
|---|---|---|
| 1. Buis doormeten | `python scripts/run_reference.py` | `out/reference.png`, doelcurves |
| 2. Genetisch algoritme | `python scripts/optimize.py --gen 40` | `out/best.json` (≈ 1 uur op 8 kernen) |
| 3. Rapport van een ontwerp | `python scripts/report.py designs/run3.json` | onderdelen, grafiek, netlist |
| 4. Controle met NE5532 | `python scripts/compare_opamp.py designs/final.json` | `out/compare_ne5532.png` |
| 5. Gevoeligheid | `python scripts/sensitivity.py designs/final.json` | effect van 1 % per onderdeel |
| 6. Toleranties | `python scripts/montecarlo.py --n 24` | Monte-Carlo met en zonder afregelen |
| 7. Gebouwde schakeling | `python scripts/verify_build.py` | versterking, ruis, PSRR, harmonischen |
| 8. Documentatieschema | `python scripts/draw_schematic.py` | `docs/img/schema_kanaal.svg` |
| 9. Hardware | `python scripts/make_hardware.py` | through-hole: KiCad-schema, print, Gerbers, renders |
| 9b. Hardware SMD | `python scripts/make_hardware.py --variant smd` | idem SMD-versie, plus montagebestanden (BOM + CPL) |
| 10. Documentatiedata | `python scripts/make_docs_assets.py` | `docs/data/*`, `docs/img/*` |

(Alle commando's met `.\.venv\Scripts\python`.)

## Code-overzicht

| Bestand | Rol |
|---|---|
| `circuitbuilder/spice.py` | ngspice in batchmode aansturen |
| `circuitbuilder/analysis.py` | harmonischen (kleinste-kwadratenfit), frequentierespons |
| `circuitbuilder/reference.py` | 12AX7-referentietrap |
| `circuitbuilder/candidate.py` | kandidaat-topologie voor het GA (genen → netlist) |
| `circuitbuilder/fitness.py` | doelcurves en kostenfunctie |
| `circuitbuilder/build.py` | **het gebouwde ontwerp**: één bron voor simulatie, schema, print en BOM; footprints per variant (tht/smd) |
| `circuitbuilder/models/` | 12AX7 (Koren), 1N4148, generieke opamp, NE5532 (TI-macromodel) |
| `scripts/kicad_schematic.py` | genereert het KiCad-schema |
| `scripts/kicad_pcb.py` | plaatsing, routering-import, massavlakken (KiCad-Python) |

## Modellen en bronnen

- 12AX7: triodemodel van Norman Koren (1996), herschreven voor ngspice.
- NE5532: TI/MicroSim "Parts"-macromodel van de NE5534 met 22 pF compensatie, via de
  [KiCad-Spice-Library](https://github.com/kicad-spice-library/KiCad-Spice-Library);
  gecontroleerd op GBW (9,7 MHz), uitgangszwaai (±13 V in 600 Ω) en ruis
  (6,4 nV/√Hz, datasheet 5 nV/√Hz).
- Genetisch algoritme: [pymoo](https://pymoo.org).
