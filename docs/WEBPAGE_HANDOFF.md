# Handoff: turning this documentation into a web page

This document is for whoever (human or AI) builds the project web page. It describes
where all content lives, what the core message is and which sections the page should
have. **All content has already been written and checked; the page builder does not
need to invent or recalculate any technical content.**

## The project in one sentence

A stereo hi-fi preamp built with opamps that imitates the warm distortion character
of a 12AX7 tube stage, with component values found by a genetic algorithm that
compared thousands of SPICE simulations against a simulated tube.

## Credit

The project comes from **KyntoSoftware**. Show that name as the author/maker (for
example in the header or footer, and in the page metadata). Do not add any personal
names or e-mail addresses.

## Language, audience and tone

- **Language:** English (all texts in `docs/` are English).
- **Audience:** hi-fi and electronics hobbyists with basic knowledge (they know what
  an opamp and harmonic distortion are), plus people curious about AI/algorithms as
  design tools.
- **Tone:** clear, enthusiastic but honest. The design is **simulated and checked,
  not yet physically built and measured**. State that clearly (see "Status" in
  `01_overview.md`). Do not exaggerate ("sounds exactly like a tube"); the claim is:
  *the same harmonic fingerprint as a 12AX7 stage, in simulation*.

## Where everything is

| Content | File | Use on the page |
|---|---|---|
| Intro, key figures, idea | `docs/01_overview.md` | hero + "at a glance" |
| How the circuit works | `docs/02_how_it_works.md` | section "How it works" |
| Genetic algorithm, story of the 3 runs | `docs/03_design_process.md` | section "Designed by evolution" |
| Measurements, NE5532 check, tolerances | `docs/04_results.md` | section "Results" |
| Parts, soldering, trimming (through-hole) | `docs/05_build_guide.md` | section "Build it yourself" |
| Having it made ready-to-use (SMD) | `docs/07_assembled_smd.md` | section "Can't solder? Have it made" |
| Reproducing everything | `docs/06_software.md` | section "Open source / run it yourself" (collapsible) |

### Images (`docs/img/`)

| File | Content | Suggested place |
|---|---|---|
| `schematic_channel.svg` | readable schematic of one channel (vector) | "How it works" |
| `result_harmonics.png` | H2/H3 opamp vs 12AX7 + frequency response (**main chart**) | hero or "Results" |
| `tube_reference.png` | distortion of the 12AX7 reference | "Designed by evolution" |
| `ga_convergence.png` | cost per generation, 3 runs | "Designed by evolution" |
| `ne5532_vs_generic.png` | check with the NE5532 model | "Results" |
| `tolerance_montecarlo.png` | spread with 1 % parts | "Results" |

### Hardware images and downloads

There are **two PCB variants** with the same schematic and the same values:

- **through-hole** (`hardware/export/`): to solder yourself, 178 × 100 mm;
- **SMD** (`hardware/export_smd/`): to have it made and assembled by a PCB fab,
  129 × 72 mm. This is the variant for visitors who don't solder; the project owner
  wants it on the page.

Both folders contain the same kinds of files:

| File | Content |
|---|---|
| `render_3d_angled.png` | 3D render of the assembled board (**best image, suitable as hero**) |
| `render_3d_top.png`, `render_3d_bottom.png` | 3D top and bottom view (transparent background) |
| `pcb_top.svg`, `pcb_bottom.svg`, `pcb_assembly.svg` | PCB layers as vector graphics |
| `schematic.pdf` / `warm_preamp.svg` | full KiCad schematic |
| `warm_preamp_gerbers.zip` | Gerbers + drill files (download for the PCB fab) |
| `bom.csv` | parts list (download) |

Only in `hardware/export_smd/`:

| File | Content |
|---|---|
| `jlcpcb_bom.csv` | parts list in fab format (JLCPCB; LCSC numbers deliberately empty) |
| `jlcpcb_cpl.csv` | placement file (position and rotation per part) |

Note: the trimmers are missing from the SMD renders (no 3D model in KiCad); that is
not a design error.

Tip: show the two variants side by side (e.g. tabs or two cards) with the comparison
table from `07_assembled_smd.md`.

### Data for interactive charts (`docs/data/`)

If the page uses interactive charts (e.g. Chart.js or Plotly), use these files
instead of the PNGs:

| File | Structure |
|---|---|
| `key_figures.json` | flat list of key figures (gain, noise, H2/H3 at 1 V, tolerances, PCB sizes…) |
| `verify_build.json` | `levels[]`: per output level `vout_rms`, `h2`, `h3`, `h4`, `h5`, `thd`, `tube_h2`, `tube_h3` (dB relative to the fundamental); `freq_response`: `f[]` (Hz), `db[]` |
| `tube_12ax7_harmonics.json` | tube target curve: `vout_rms[]` and `h[][]` = H2..H5 in dB |
| `ga_convergence.json` | `run1`/`run2`/`run3`: list of `{gen, evals, best, median, seconds}` |
| `montecarlo.json` | `stats.<quantity>.untrimmed/trimmed.{mean,sd,min,max}` and all samples |
| `sensitivity.json` | per variant (one part +1 %) the change in gain/H2/H3 |
| `compare_ne5532.json` | `generic` / `ne5532`: `vout[]`, `h[][]` (H2..H5), `thd[]`, `f[]`, `mag[]`, `snr` |
| `bom.json` / `bom.csv` | through-hole parts list, grouped by value (`qty`, `value`, `type`, `references`, `footprint`) |
| `bom_smd.json` / `bom_smd.csv` | SMD parts list, same structure |
| `final_design.json` | final component values (GA names: RF1, RG1, RA, …) |

Suggestion for the main chart: log x axis "output level [V rms]" (0.1 – 7), y axis
"dB relative to fundamental" (−110 – −20); four lines: H2 and H3 of the opamp
(solid) and of the tube (dotted), from `verify_build.json`.

## Suggested page structure

1. **Hero:** title "Warm opamp preamp", subtitle "Tube character, designed by a
   genetic algorithm", image `render_3d_angled.png`, 3–4 key figures
   (10 dB · 0.3 % H2 at 1 V · ±0.1 dB 20 Hz–20 kHz · 3× NE5532), "by KyntoSoftware".
2. **The idea** (from 01): why tubes sound warm (H2) and how diodes can do that.
3. **How it works** (from 02): schematic SVG + the six steps; possibly highlight the
   formula ln(1+x) + ln(1−x) ≈ −x².
4. **Designed by evolution** (from 03): tube reference, fitness table, convergence
   chart, the story of the three runs (including the failed run 2: that makes it
   credible).
5. **Results** (from 04): main chart, key figures table, NE5532 check, tolerances.
6. **Build it** (from 05 and 07): two routes side by side.
   - *Solder it yourself* (through-hole): parts list, downloads (Gerbers, BOM,
     schematic PDF, KiCad project), soldering order, trimming.
   - *Have it made ready-to-use* (SMD): render `export_smd/render_3d_angled.png`,
     ordering steps, downloads (Gerbers, `jlcpcb_bom.csv`, `jlcpcb_cpl.csv`),
     connecting with screw terminals. Emphasise: no soldering needed.
7. **Status and disclaimer:** simulated, not yet built; working with ±15 V is safe,
   but the supply itself (mains voltage) only for people experienced with it.
8. **Open source** (from 06): how to reproduce everything, and the license (see the
   root `README.md`).

## What does not belong on the page

- Files in `out/` (intermediate results, logs), `tools/` (ngspice, Freerouting) and
  `.venv/`.
- Personal details of the maker: credit only **KyntoSoftware**.

## Consistency

All numbers in the documentation come from `docs/data/key_figures.json` and
`verify_build.json` (simulation of the as-built circuit with the NE5532 model). If
text and data ever disagree, the JSON files are authoritative; they are regenerated
with `python scripts/make_docs_assets.py`.
