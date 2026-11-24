# circuitbuilder

Met een genetisch algoritme een **opamp-hifi-voorversterker (±15 V)** ontwerpen die het
subtiel warme karakter van een **12AX7-buizentrap** nabootst, met bouwbare componenten
(E-reeks, echte opamp-modellen).

## Opzet

```
circuitbuilder/
  spice.py       koppeling met ngspice (batchmode)
  analysis.py    harmonischen/THD en frequentierespons
  reference.py   12AX7-referentietrap (doelgedrag)
  models/        SPICE-modellen (12AX7 van Koren)
scripts/
  run_reference.py   meet de referentie door -> out/reference.png
tools/           lokale ngspice-installatie (niet in git)
```

## Installatie

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

ngspice 47 (Windows) uitpakken naar `tools/Spice64` (of zet de omgevingsvariabele `NGSPICE`).

## Gebruik

```powershell
.\.venv\Scripts\python scripts\run_reference.py          # buizentrap doormeten
.\.venv\Scripts\python scripts\optimize.py --gen 40       # GA (ca. 1 uur op 8 kernen) -> out/best.json
.\.venv\Scripts\python scripts\report.py designs\run3.json        # rapport + out/best.png, out/best.cir
.\.venv\Scripts\python scripts\compare_opamp.py designs\run3.json # generiek model vs NE5532
```

## Beste ontwerp tot nu toe: `designs/run3.json`

Versterking 9,6 dB, vlak ±0,1 dB (20 Hz–20 kHz), S/R ca. 98–99 dB t.o.v. 1 V rms.
H2 en H3 volgen de 12AX7-trap binnen ~1 dB van 0,1 tot 6 V rms; met NE5532 gecontroleerd.

| Onderdeel | Waarde | | Onderdeel | Waarde |
|---|---|---|---|---|
| RF1 | 39k | | RBB | 8k2 |
| RG1 | 20k | | RS0 | 1k2 |
| RA | 6k2 | | RSA | 180R |
| RB | 4k7 | | RSB | 160R |
| RBA | 9k1 | | RF2 | 1k2 |
| diodes | 2 × 3× 1N4148 | | opamps | 3× NE5532-helft |

Vaste onderdelen: CIN 2µ2, RIN 100k, CG1 470µ, RI1/RI2 10k, CSA/CSB 47µ, CF2 22p.
