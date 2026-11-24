# Hoe de schakeling werkt

![Schema van één kanaal](img/schema_kanaal.svg)

*Schema van kanaal L (referenties 1xx). Kanaal R is identiek (2xx). Het volledige
KiCad-schema staat in `hardware/kicad/warm_preamp.kicad_sch` en als PDF in
`hardware/export/schema.pdf`.*

## Signaalpad in zes stappen

1. **Ingang** – C101 (2,2 µF film) en R101 (100 kΩ) blokkeren gelijkspanning en
   bepalen de ingangsimpedantie (100 kΩ).
2. **Versterker U1A** – niet-inverterend, versterking 1 + 39k/20k = 2,95×. C102 maakt
   de DC-versterking 1, zodat offset niet versterkt wordt. Uitgang: signaal **V1**.
3. **Inverter U2A** – maakt een omgekeerde kopie **−V1** (10k/10k).
4. **Twee diodetakken** – de kern van het "buizengeluid":
   - **Tak A** krijgt +V1 via R107 (6k2), **tak B** krijgt −V1 via R110 + trimpot RV101.
   - Elke tak eindigt in **drie 1N4148-diodes in serie** naar massa, voorgespannen
     met ongeveer 1 mA uit een gefilterde +15 V (R108/R111 vanaf VP).
   - De spanning over een diode is logaritmisch: ln(1 + x). Tak A ziet +x, tak B −x.
     Opgeteld vallen de oneven termen (grotendeels) weg:
     ln(1+x) + ln(1−x) ≈ −x². Dat is **zuivere tweede harmonische** die
     evenredig met het signaalniveau groeit, net als bij een triode.
   - Omdat de takken niet exact gelijk zijn (door het algoritme bewust zo gekozen),
     ontstaat er ook een kleine, gedoseerde hoeveelheid H3, ook weer zoals bij de buis.
5. **Sommator U3A** – telt het schone signaal (via R113 vanaf −V1) en de twee
   diodesignalen (via C104/R109 en C105/R112) op. R114 (1k27) bepaalt de totale
   versterking van 10 dB. C106 (22 pF) houdt de opamp stabiel bij hoge frequenties.
6. **Uitgang** – R115 (100 Ω) maakt de uitgang stabiel bij lange kabels, C107 en
   R116 houden gelijkspanning tegen.

## Waarom drie diodes per tak?

Hoe groter de spanning over de diodeketen, hoe minder het zwakke diodesignaal
achteraf versterkt hoeft te worden, en dus hoe minder ruis. Met drie diodes is het
signaal drie keer zo groot, de ruis maar √3 keer. Het algoritme koos zelf voor 3.

## Waarom een gefilterde +15 V voor de diodes?

De voorspanning van de diodes komt direct uit de voeding. Brom op die lijn zou in het
signaal terechtkomen. R106 (47 Ω) en C103 (470 µF) vormen een filter (ca. 7 Hz)
dat brom op +15 V met ruim 40 dB onderdrukt (bij 100 Hz).

## De trimpot

RV101 (500 Ω, meerslagen) staat in serie met R110 in tak B. Hiermee stel je de balans
tussen de twee takken af, en daarmee de hoeveelheid H3 (ongeveer ±3 dB regelbereik),
zonder dat H2 of de versterking merkbaar verandert. Zie
[afregelen](05_bouwhandleiding.md#afregelen).

## Opamp-indeling

Drie NE5532P (elk twee opamps) leveren de zes opamps voor twee kanalen. Elk IC doet
één trap voor beide kanalen: U1 = ingangsversterker, U2 = inverter, U3 = sommator;
eenheid A = kanaal L, eenheid B = kanaal R. Op de print staan de IC's daardoor op
één middenlijn met kanaal L erboven en kanaal R eronder.
