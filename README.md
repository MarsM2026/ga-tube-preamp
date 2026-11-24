# circuitbuilder: warme opamp-voorversterker

Een stereo hifi-voorversterker met opamps die het warme vervormingskarakter van een
**12AX7-buizentrap** nabootst. De componentwaarden zijn gevonden door een
**genetisch algoritme** dat duizenden ngspice-simulaties vergeleek met een
gesimuleerde buis. Inclusief KiCad 10-schema, twee printontwerpen (through-hole om zelf
te solderen, SMD om kant-en-klaar te laten monteren) en documentatie.

| | |
|---|---|
| Versterking | 10 dB |
| Frequentierespons | 20 Hz – 20 kHz ±0,11 dB |
| Vervorming bij 1 V rms | 0,31 % (vrijwel alleen H2, gelijk aan de 12AX7) |
| Signaal/ruis | ca. 97,5 dB t.o.v. 1 V rms |
| Onderdelen | 3× NE5532P, 12× 1N4148, 1 %-weerstanden, 2 trimpotten |
| Voeding | ±15 V gestabiliseerd |
| Print | 2 lagen; through-hole 178 × 100 mm of SMD 129 × 72 mm (laten monteren) |

**Status:** volledig gesimuleerd en gecontroleerd (NE5532-model, Monte-Carlo-toleranties,
ERC/DRC zonder fouten). Nog niet fysiek gebouwd en gemeten.

## Waar staat wat

| Map / bestand | Inhoud |
|---|---|
| [docs/](docs/README.md) | **documentatie** (Nederlands): werking, ontwerpproces, resultaten, bouwhandleiding |
| [docs/WEBPAGINA_OVERDRACHT.md](docs/WEBPAGINA_OVERDRACHT.md) | **instructies voor wie hier een webpagina van maakt** |
| `docs/img/`, `docs/data/` | grafieken en ruwe cijfers (JSON/CSV) |
| `hardware/kicad/`, `hardware/export/` | through-hole: KiCad 10-project, Gerbers, schema-PDF/SVG, printlagen, 3D-renders, onderdelenlijst |
| `hardware/kicad_smd/`, `hardware/export_smd/` | SMD-versie: idem, plus montagebestanden voor de fabrikant ([uitleg](docs/07_kant_en_klaar_smd.md)) |
| `designs/` | ontwerpwaarden per GA-run en het definitieve ontwerp (`final.json`) |
| `circuitbuilder/` | Python-pakket: ngspice-koppeling, analyse, kandidaat, fitness, gebouwd ontwerp |
| `scripts/` | alle stappen: referentie, GA, controles, schema, print, documentatie |

## Snel starten

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python scripts\verify_build.py      # simulatie van de gebouwde schakeling
.\.venv\Scripts\python scripts\make_hardware.py     # KiCad-schema, print, Gerbers, renders
.\.venv\Scripts\python scripts\make_hardware.py --variant smd   # idem SMD-versie
```

Benodigd: ngspice 47 in `tools/Spice64`, KiCad 10, Java + Freerouting 2.5 in
`tools/freerouting/`. Zie [docs/06_software.md](docs/06_software.md) voor alle stappen.
