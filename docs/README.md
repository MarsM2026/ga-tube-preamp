# Documentatie: warme opamp-voorversterker

Lees in deze volgorde:

1. [Overzicht](01_overzicht.md): wat het is, kerncijfers
2. [Hoe de schakeling werkt](02_hoe_het_werkt.md)
3. [Ontwerpproces met een genetisch algoritme](03_ontwerpproces.md)
4. [Resultaten en controles](04_resultaten.md)
5. [Bouwhandleiding](05_bouwhandleiding.md)
6. [Software zelf draaien](06_software.md)
7. [Kant-en-klaar laten maken (SMD-versie)](07_kant_en_klaar_smd.md)

**Bouw je hier een webpagina van?** Begin dan met
[WEBPAGINA_OVERDRACHT.md](WEBPAGINA_OVERDRACHT.md): daarin staat waar alle teksten,
afbeeldingen, data en downloads staan en welke paginaopbouw wordt voorgesteld.

## Mappen

| Map | Inhoud |
|---|---|
| `docs/` | teksten (Markdown) |
| `docs/img/` | grafieken en het leesbare schema |
| `docs/data/` | ruwe cijfers als JSON/CSV (voor interactieve grafieken) |
| `hardware/kicad/` | KiCad 10-project through-hole (schema, print, ERC/DRC-rapporten) |
| `hardware/export/` | through-hole: Gerbers (zip), schema-PDF, printlagen (SVG), 3D-renders, BOM |
| `hardware/kicad_smd/` | KiCad 10-project SMD-versie |
| `hardware/export_smd/` | SMD: Gerbers, montagebestanden (BOM + CPL), schema-PDF, printlagen, 3D-renders |
| `designs/` | ontwerpwaarden per GA-run en het definitieve ontwerp |
