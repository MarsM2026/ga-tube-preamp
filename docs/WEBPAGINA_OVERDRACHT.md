# Overdracht: van deze documentatie een webpagina maken

Dit document is bedoeld voor degene (mens of AI) die de projectwebpagina bouwt. Het
beschrijft waar alle inhoud staat, wat de kernboodschap is en welke onderdelen de
pagina zou moeten hebben. **Alle inhoud is al geschreven en gecontroleerd; de
paginabouwer hoeft geen technische inhoud te bedenken of te herberekenen.**

## Project in één zin

Een stereo hifi-voorversterker met opamps die het warme vervormingskarakter van een
12AX7-buizentrap nabootst, waarvan de componentwaarden zijn gevonden door een
genetisch algoritme dat duizenden SPICE-simulaties vergeleek met een gesimuleerde buis.

## Taal, doelgroep en toon

- **Taal:** Nederlands (alle teksten in `docs/` zijn Nederlands).
- **Doelgroep:** hifi- en elektronicahobbyisten met basiskennis (weten wat een opamp
  en harmonische vervorming zijn), plus mensen die nieuwsgierig zijn naar AI/algoritmen
  als ontwerpgereedschap.
- **Toon:** helder, enthousiast maar eerlijk. Het ontwerp is **gesimuleerd en
  gecontroleerd, nog niet fysiek gebouwd en gemeten**. Vermeld dat duidelijk (zie
  "Status" in `01_overzicht.md`). Overdrijf niet ("klinkt precies als een buis");
  de claim is: *dezelfde harmonische vingerafdruk als een 12AX7-trap, in simulatie*.

## Waar staat wat

| Inhoud | Bestand | Gebruik op de pagina |
|---|---|---|
| Intro, kerncijfers, idee | `docs/01_overzicht.md` | hero + "in het kort" |
| Werking van de schakeling | `docs/02_hoe_het_werkt.md` | sectie "Hoe werkt het" |
| Genetisch algoritme, verhaal van de 3 runs | `docs/03_ontwerpproces.md` | sectie "Ontworpen door evolutie" |
| Metingen, NE5532-controle, toleranties | `docs/04_resultaten.md` | sectie "Resultaten" |
| Onderdelen, solderen, afregelen | `docs/05_bouwhandleiding.md` | sectie "Zelf bouwen" |
| Reproduceren | `docs/06_software.md` | sectie "Open source / zelf draaien" (inklapbaar) |

### Afbeeldingen (`docs/img/`)

| Bestand | Inhoud | Aanbevolen plek |
|---|---|---|
| `schema_kanaal.svg` | leesbaar schema van één kanaal (vector) | "Hoe werkt het" |
| `resultaat_harmonischen.png` | H2/H3 opamp vs 12AX7 + frequentierespons (**hoofdgrafiek**) | hero of "Resultaten" |
| `buis_referentie.png` | vervorming van de 12AX7-referentie | "Ontworpen door evolutie" |
| `ga_convergentie.png` | kosten per generatie, 3 runs | "Ontworpen door evolutie" |
| `ne5532_vs_generiek.png` | controle met NE5532-model | "Resultaten" |
| `tolerantie_montecarlo.png` | spreiding met 1 %-onderdelen | "Resultaten" |

### Hardware-afbeeldingen en downloads (`hardware/export/`)

| Bestand | Inhoud |
|---|---|
| `render_3d_schuin.png` | 3D-render van de opgebouwde print (**mooiste beeld, geschikt als hero**) |
| `render_3d_top.png`, `render_3d_bottom.png` | 3D-boven- en onderaanzicht (transparante achtergrond) |
| `print_boven.svg`, `print_onder.svg`, `print_opbouw.svg` | printlagen als vector |
| `schema.pdf` / `warm_preamp.svg` | volledig KiCad-schema |
| `warm_preamp_gerbers.zip` | Gerbers + boorbestanden (download voor printfabrikant) |
| `bom.csv` | onderdelenlijst (download) |

### Data voor interactieve grafieken (`docs/data/`)

Wil de pagina interactieve grafieken (bijv. met Chart.js of Plotly), gebruik dan deze
bestanden in plaats van de PNG's:

| Bestand | Structuur |
|---|---|
| `key_figures.json` | platte lijst kerncijfers (versterking, ruis, H2/H3 bij 1 V, toleranties…) |
| `verify_build.json` | `levels[]`: per uitgangsniveau `vout_rms`, `h2`, `h3`, `h4`, `h5`, `thd`, `tube_h2`, `tube_h3` (dB t.o.v. grondtoon); `freq_response`: `f[]` (Hz), `db[]` |
| `tube_12ax7_harmonics.json` | doelcurve buis: `vout_rms[]` en `h[][]` = H2..H5 in dB |
| `ga_convergence.json` | `run1`/`run2`/`run3`: lijst `{gen, evals, best, median, seconds}` |
| `montecarlo.json` | `stats.<grootheid>.untrimmed/trimmed.{mean,sd,min,max}` en alle samples |
| `sensitivity.json` | per variant (onderdeel +1 %) de verandering van versterking/H2/H3 |
| `bom.json` / `bom.csv` | onderdelenlijst gegroepeerd per waarde |
| `final_design.json` | definitieve componentwaarden (GA-namen: RF1, RG1, RA, …) |

Voorstel voor de hoofdgrafiek: log-x-as "uitgangsniveau [V rms]" (0,1 – 7), y-as
"dB t.o.v. grondtoon" (−110 – −20); vier lijnen: H2 en H3 van de opamp (doorgetrokken)
en van de buis (gestippeld), uit `verify_build.json`.

## Voorgestelde paginaopbouw

1. **Hero:** titel "Warme opamp-voorversterker", ondertitel "Buizenkarakter, ontworpen
   door een genetisch algoritme", afbeelding `render_3d_schuin.png`, 3–4 kerncijfers
   (10 dB · 0,3 % H2 bij 1 V · ±0,1 dB 20 Hz–20 kHz · 3× NE5532).
2. **Het idee** (uit 01): waarom buizen warm klinken (H2) en hoe dat met diodes kan.
3. **Hoe werkt het** (uit 02): schema-SVG + de zes stappen; eventueel de formule
   ln(1+x) + ln(1−x) ≈ −x² uitgelicht.
4. **Ontworpen door evolutie** (uit 03): buisreferentie, fitness-tabel,
   convergentiegrafiek, het verhaal van de drie runs (inclusief de mislukte run 2: dat
   maakt het geloofwaardig).
5. **Resultaten** (uit 04): hoofdgrafiek, tabel kerncijfers, NE5532-controle,
   toleranties.
6. **Zelf bouwen** (uit 05): onderdelenlijst, downloads (Gerbers, BOM, schema-PDF,
   KiCad-project), soldeervolgorde, afregelen.
7. **Status en disclaimer:** gesimuleerd, nog niet gebouwd; werken met ±15 V is veilig,
   maar de voeding zelf (230 V) alleen door wie daar ervaring mee heeft.
8. **Open source** (uit 06): hoe je alles reproduceert.

## Wat níet op de pagina hoort

- Bestanden in `out/` (tussenresultaten, logs), `tools/` (ngspice, Freerouting) en
  `.venv/`.
- Persoonsgegevens van de maker: er staat bewust geen naam of e-mailadres in de
  documentatie. Vraag de eigenaar van het project of en hoe die genoemd wil worden.

## Consistentie

Alle getallen in de documentatie komen uit `docs/data/key_figures.json` en
`verify_build.json` (simulatie van de gebouwde schakeling met het NE5532-model).
Wijken teksten en data ooit af, dan zijn de JSON-bestanden leidend; ze worden opnieuw
gegenereerd met `python scripts/make_docs_assets.py`.
