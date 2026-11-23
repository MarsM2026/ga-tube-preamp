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
.\.venv\Scripts\python scripts\run_reference.py
```
