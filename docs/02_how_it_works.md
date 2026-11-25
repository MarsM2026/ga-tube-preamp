# How the circuit works

![Schematic of one channel](img/schematic_channel.svg)

*Schematic of channel L (references 1xx). Channel R is identical (2xx). The full
KiCad schematic is in `hardware/kicad/warm_preamp.kicad_sch` and as a PDF in
`hardware/export/schematic.pdf`.*

## The signal path in six steps

1. **Input** – C101 (2.2 µF film) and R101 (100 kΩ) block DC and set the input
   impedance (100 kΩ).
2. **Amplifier U1A** – non-inverting, gain 1 + 39k/20k = 2.95×. C102 makes the DC
   gain 1, so the offset is not amplified. Output: signal **V1**.
3. **Inverter U2A** – makes an inverted copy **−V1** (10k/10k).
4. **Two diode branches** – the heart of the "tube sound":
   - **Branch A** gets +V1 via R107 (6k2), **branch B** gets −V1 via R110 + trimmer RV101.
   - Each branch ends in **three 1N4148 diodes in series** to ground, biased at
     about 1 mA from a filtered +15 V (R108/R111 from VP).
   - The voltage across a diode is logarithmic: ln(1 + x). Branch A sees +x,
     branch B sees −x. When added, the odd terms (largely) cancel:
     ln(1+x) + ln(1−x) ≈ −x². That is **pure second harmonic** that grows in
     proportion to the signal level, just like a triode.
   - Because the branches are not exactly equal (chosen that way on purpose by the
     algorithm), a small, controlled amount of H3 appears as well, again like the tube.
5. **Summer U3A** – adds the clean signal (via R113 from −V1) and the two diode
   signals (via C104/R109 and C105/R112). R114 (1k27) sets the overall gain of
   10 dB. C106 (22 pF) keeps the opamp stable at high frequencies.
6. **Output** – R115 (100 Ω) keeps the output stable with long cables, C107 and
   R116 block DC.

## Why three diodes per branch?

The larger the voltage across the diode chain, the less the weak diode signal has to
be amplified afterwards, and so the less noise. With three diodes the signal is three
times as large, the noise only √3 times. The algorithm chose 3 by itself.

## Why a filtered +15 V for the diodes?

The diode bias comes straight from the supply. Hum on that line would end up in the
signal. R106 (47 Ω) and C103 (470 µF) form a filter (approx. 7 Hz) that suppresses
hum on +15 V by more than 40 dB (at 100 Hz).

## The trimmer

RV101 (500 Ω, multi-turn) is in series with R110 in branch B. It sets the balance
between the two branches, and with that the amount of H3 (about ±3 dB adjustment
range), without noticeably changing H2 or the gain. See
[trimming](05_build_guide.md#trimming).

## Opamp allocation

Three NE5532s (two opamps each) provide the six opamps for two channels. Each IC
handles one stage for both channels: U1 = input amplifier, U2 = inverter,
U3 = summer; unit A = channel L, unit B = channel R. That way the ICs sit on one
centre line on the PCB, with channel L above and channel R below.
