"""Teken een leesbaar schema van één kanaal (voor documentatie / webpagina).

Waarden en referenties komen uit circuitbuilder/build.py (kanaal L, 1xx), zodat het
schema altijd overeenkomt met de print, de onderdelenlijst en de simulatie.

Resultaat: docs/img/schema_kanaal.svg
"""

from __future__ import annotations

import sys
from pathlib import Path

import schemdraw
import schemdraw.elements as elm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from circuitbuilder import build  # noqa: E402

OUT = ROOT / "docs" / "img"


def parts_by_role(ch="L"):
    roles = {}
    for p in build.all_parts():
        if p.channel != ch:
            continue
        if p.kind == "OPAMP":
            roles[p.extra["stage"]] = p
        elif "role" in p.extra:
            roles[p.extra["role"]] = p
    return roles


def main() -> None:
    P = parts_by_role()
    L = lambda k: f"{P[k].ref}\n{P[k].value}"  # noqa: E731
    OUT.mkdir(parents=True, exist_ok=True)
    schemdraw.config(fontsize=10, lw=1.2, font="sans-serif")
    d = schemdraw.Drawing(show=False)
    d.config(unit=2.4)

    # ------------------------------------------------ ingang + U1 (y = 0)
    d += elm.Dot(open=True).at((0, 0)).label("IN", "left")
    d += elm.Capacitor().right().label(L("CIN"))
    d += (i1 := elm.Dot())
    d += elm.Resistor().down().at(i1.center).length(2.4).label(L("RIN"), "bottom")
    d += elm.Ground()
    d += elm.Line().right(1.2).at(i1.center)
    d += (u1 := elm.Opamp(leads=True).flip().anchor("in2")
          .label(f"{P['U1'].ref}\n½ NE5532P", "top", ofst=0.25))
    # terugkoppeling onder de opamp: RF1 van uitgang naar -in, RG1+CG1 naar massa
    d += elm.Line().down(0.9).at(u1.in1)
    d += (fb1 := elm.Dot())
    d += elm.Line().right(1.1).at(fb1.center)
    d += elm.Resistor().right().tox(u1.out[0] + 0.6).label(L("RF1"), "bottom")
    d += elm.Line().up().toy(u1.out)
    d += elm.Resistor().down().at(fb1.center).length(2.2).label(L("RG1"), "top")
    d += elm.Capacitor().down().length(2.0).label(L("CG1"), "top")
    d += elm.Ground()
    d += elm.Line().right(0.6).at(u1.out)
    d += (v1 := elm.Dot().label("V1", "top"))

    # ------------------------------------------------ inverter U2 (y = -9)
    d += elm.Line().down(5.2).at(v1.center)
    d += (v1d := elm.Dot())
    d += elm.Line().down().toy(-9.6)
    d += elm.Resistor().right().label(L("RI1"), "bottom")
    d += (fb2 := elm.Dot())
    d += elm.Line().right(0.8)
    d += (u2 := elm.Opamp(leads=True).anchor("in1").label(f"{P['U2'].ref}\n½ NE5532P", "bottom", ofst=0.3))
    d += elm.Line().left(0.4).at(u2.in2)
    d += elm.Ground()
    d += elm.Line().up(1.6).at(fb2.center)
    d += elm.Resistor().right().tox(u2.out[0] + 0.6).label(L("RI2"))
    d += elm.Line().down().toy(u2.out)
    d += elm.Line().right(0.6).at(u2.out)
    d += (v1n := elm.Dot().label("−V1", "top"))

    # ------------------------------------------------ tak A (y = 0)
    xa = 19.0
    d += elm.Line().right().at(v1.center).tox(xa - 3.2)
    d += elm.Resistor().right().tox(xa).label(L("RA"))
    d += (na := elm.Dot().label("A", "top", ofst=(-0.35, 0.05)))
    d += elm.Resistor().up().at(na.center).length(2.6).label(L("RBA"), "bottom")
    d += elm.Dot(open=True).label("VP", "top")
    d += elm.Line().down(0.4).at(na.center)
    for i in range(3):
        d += elm.Diode().down().length(1.3).label(f"{P[f'DA{i}'].ref}", "bottom")
    d += elm.Ground()
    d += elm.Line().right(0.8).at(na.center)
    d += elm.Capacitor(polar=True).right().label(L("CSA"))
    d += elm.Resistor().right().label(L("RSA"))
    d += (sa := elm.Dot())

    # ------------------------------------------------ tak B (y = -9.6)
    xb = 25.0
    d += elm.Line().right().at(v1n.center).tox(xb - 6.0)
    d += elm.Resistor().right().label(L("RB"))
    d += elm.Potentiometer().right().tox(xb).label(f"{P['RB_TRIM'].ref}\n{P['RB_TRIM'].value} trim", "bottom")
    d += (nb := elm.Dot().label("B", "top", ofst=(-0.35, 0.05)))
    d += elm.Resistor().up().at(nb.center).length(2.6).label(L("RBB"), "bottom")
    d += elm.Dot(open=True).label("VP", "top")
    d += elm.Line().down(0.4).at(nb.center)
    for i in range(3):
        d += elm.Diode().down().length(1.3).label(f"{P[f'DB{i}'].ref}", "bottom")
    d += elm.Ground()
    d += elm.Line().right(0.8).at(nb.center)
    d += elm.Capacitor(polar=True).right().label(L("CSB"))
    d += elm.Resistor().right().label(L("RSB"))
    d += (sb := elm.Dot())

    # ------------------------------------------------ schoon pad RS0 (y = -16.5)
    xs = max(sa.center[0], sb.center[0]) + 1.6
    d += elm.Line().down(6.9).at(v1n.center)
    d += elm.Resistor().right().tox(xs).label(f"{P['RS0'].ref}  {P['RS0'].value}   (schoon signaal)")
    d += (s_low := elm.Dot())

    # ------------------------------------------------ sommator U3
    d += elm.Line().right().at(sa.center).tox(xs)
    d += (s_top := elm.Dot())
    d += elm.Line().right().at(sb.center).tox(xs)
    d += elm.Line().at(s_top.center).to(s_low.center)
    ys = -4.8
    d += (s := elm.Dot().at((xs, ys)).label("S", "left"))
    d += elm.Line().right(1.4).at(s.center)
    d += (u3 := elm.Opamp(leads=True).anchor("in1").label(f"{P['U3'].ref}\n½ NE5532P", "bottom", ofst=0.3))
    d += elm.Line().left(0.4).at(u3.in2)
    d += elm.Ground()
    d += elm.Line().up(1.8).at((xs + 0.7, ys))
    d += (ft := elm.Dot())
    d += elm.Resistor().right().tox(u3.out[0] + 0.7).label(L("RF2"))
    d += (fr := elm.Dot())
    d += elm.Line().down().toy(u3.out)
    d += elm.Line().up(1.6).at(ft.center)
    d += elm.Capacitor().right().tox(u3.out[0] + 0.7).label(L("CF2"))
    d += elm.Line().down().toy(fr.center)
    d += elm.Dot().at((xs + 0.7, ys))
    # uitgang
    d += elm.Line().right(0.7).at(u3.out)
    d += elm.Resistor().right().label(L("ROUT"))
    d += elm.Capacitor().right().label(L("COUT"))
    d += (no := elm.Dot())
    d += elm.Resistor().down().at(no.center).length(2.4).label(L("RBLEED"), "bottom")
    d += elm.Ground()
    d += elm.Line().right(1.0).at(no.center)
    d += elm.Dot(open=True).label("OUT", "right")

    # ------------------------------------------------ voedingsfilter VP
    d += elm.Dot(open=True).at((0, -15.5)).label("+15 V", "left")
    d += elm.Resistor().right().label(L("RFLT"))
    d += (vp := elm.Dot().label("VP", "top"))
    d += elm.Capacitor(polar=True).down().at(vp.center).length(2.2).label(L("CFLT"), "bottom")
    d += elm.Ground()
    d += elm.Line().right(1.2).at(vp.center)
    d += elm.Dot(open=True).label("naar RBA en RBB", "right")
    d += elm.Label().at((0, -20.3)).label(
        "Kanaal L (referenties 1xx). Kanaal R is identiek (2xx). "
        "3× NE5532P uit ±15 V, per IC 2× 100 nF ontkoppeling.", "right")
    d.save(str(OUT / "schema_kanaal.svg"))
    print(f"Schema: {OUT / 'schema_kanaal.svg'}")


if __name__ == "__main__":
    main()
