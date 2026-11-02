"""Original engineering diagrams for DriveBench, as inline SVG strings (no assets).

A: motor drive architecture. B: four controllers into one drive and plant.
C: LQR design process. Flat strokes, theme tokens, consistent notation.
"""

from __future__ import annotations

from html import escape

from mpc_core.sim import theme as T

_STYLE = f"""
<style>
 .t {{ font-family: {T.FONT_SANS}; fill: {T.TEXT_PRIMARY}; font-size: 13px; }}
 .s {{ font-family: {T.FONT_SANS}; fill: {T.TEXT_SECONDARY}; font-size: 11px; }}
 .m {{ font-family: {T.FONT_MONO}; fill: {T.TEXT_SECONDARY}; font-size: 11px; }}
 .box {{ fill: {T.PANEL}; stroke: {T.BORDER}; stroke-width: 1.4; }}
 .hot {{ fill: {T.RAISED}; stroke: {T.ACCENT}; stroke-width: 1.6; }}
 .wire {{ stroke: {T.TEXT_SECONDARY}; stroke-width: 1.6; fill: none; }}
 .fb {{ stroke: {T.ACCENT}; stroke-width: 1.6; fill: none; stroke-dasharray: 6 4; }}
</style>
<defs>
 <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
  <path d="M0,0 L10,5 L0,10 z" fill="{T.TEXT_SECONDARY}"/></marker>
 <marker id="af" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
  <path d="M0,0 L10,5 L0,10 z" fill="{T.ACCENT}"/></marker>
</defs>
"""


def _wrap(w: int, h: int, body: str, label: str) -> str:
    return (
        f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{escape(label)}" '
        f'xmlns="http://www.w3.org/2000/svg" style="max-width:{w}px;background:{T.PANEL};'
        f'border:1px solid {T.BORDER};border-radius:3px">{_STYLE}{body}</svg>'
    )


def _box(x, y, w, h, title, sub="", hot=False) -> str:
    cls = "hot" if hot else "box"
    out = f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>'
    out += f'<text class="t" x="{x + w / 2}" y="{y + h / 2 - (4 if sub else -4)}" text-anchor="middle">{escape(title)}</text>'
    if sub:
        out += f'<text class="m" x="{x + w / 2}" y="{y + h / 2 + 12}" text-anchor="middle">{escape(sub)}</text>'
    return out


def _arrow(x1, y1, x2, y2, fb=False) -> str:
    cls = "fb" if fb else "wire"
    mk = "af" if fb else "ar"
    return f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#{mk})"/>'


def drive_architecture() -> str:
    """Diagram A: DC supply -> voltage drive -> PMDC motor -> load, with sensing and feedback."""
    b = _box(20, 70, 120, 70, "DC supply", "V_bus, sag") + _box(190, 70, 150, 70, "Voltage drive", "sat · slew · I window", hot=True)
    b += _box(390, 70, 140, 70, "PMDC motor", "L di/dt, J dω/dt") + _box(580, 70, 120, 70, "Mechanical load", "T_L(t), B ω")
    b += _arrow(140, 105, 190, 105) + _arrow(340, 105, 390, 105) + _arrow(530, 105, 580, 105)
    b += '<text class="m" x="365" y="97" text-anchor="middle">V_a</text>'
    b += '<text class="m" x="555" y="97" text-anchor="middle">T_em</text>'
    b += _box(400, 190, 120, 40, "Current sensor", "i_a") + _box(560, 190, 140, 40, "Speed encoder", "ω + noise")
    b += _arrow(460, 140, 460, 190, fb=True) + _arrow(640, 140, 640, 190, fb=True)
    b += _box(190, 270, 330, 44, "Controller (every 10 ms)", "PID · Opt. PID · LQR · MPC", hot=True)
    b += '<path class="fb" d="M460,230 L460,270" marker-end="url(#af)"/><path class="fb" d="M630,230 L630,292 L520,292" marker-end="url(#af)"/>'
    b += '<path class="wire" d="M190,292 L165,292 L165,140 L190,125" marker-end="url(#ar)"/>'
    b += '<text class="s" x="60" y="250" text-anchor="start">requested V</text>'
    b += '<text class="s" x="560" y="175">measurements</text>'
    b += '<text class="s" x="20" y="30">Motor drive architecture</text>'
    return _wrap(720, 340, b, "Motor drive architecture: supply, voltage drive, motor, load, sensors and controller feedback")


def four_controller_architecture() -> str:
    """Diagram B: four independent controllers feeding one common actuator and plant."""
    names = [("pid", "PID"), ("optimized_pid", "Optimised PID"), ("lqr", "LQR (LQI)"), ("mpc", "MPC")]
    b = '<text class="s" x="20" y="24">Four controllers, one drive, one plant</text>'
    for i, (cid, label) in enumerate(names):
        y = 40 + i * 62
        col = T.CONTROLLER_COLORS[cid]
        b += f'<rect class="box" x="30" y="{y}" width="170" height="48" rx="3" style="stroke:{col}"/>'
        b += f'<text class="t" x="115" y="{y + 29}" text-anchor="middle" style="fill:{col}">{escape(label)}</text>'
        b += f'<path class="wire" d="M200,{y + 24} L270,{y + 24} L270,146 L300,146" marker-end="url(#ar)"/>' if i < 3 else f'<path class="wire" d="M200,{y + 24} L270,{y + 24} L270,146 L300,146" marker-end="url(#ar)"/>'
    b += _box(300, 110, 150, 72, "Common drive", "same limits for all", hot=True)
    b += _box(500, 110, 150, 72, "PMDC motor", "one plant model", hot=False)
    b += _arrow(450, 146, 500, 146)
    b += '<path class="fb" d="M575,182 L575,296 L115,296" marker-end="url(#af)"/>'
    b += '<text class="s" x="345" y="314" text-anchor="middle">i_a, ω (same measurements to every controller)</text>'
    b += '<text class="m" x="352" y="104">selected one at a time per run</text>'
    return _wrap(700, 330, b, "Four controllers feed one common drive and plant with shared feedback")


def lqr_design_process() -> str:
    """Diagram C: model -> ZOH -> Q/R -> DARE -> K -> feedback controller."""
    steps = [
        ("State-space", "x=[i, ω], ξ̇=ω−r"),
        ("ZOH at Ts", "Ad, Bd (10 ms)"),
        ("Q / R weights", "normalised"),
        ("Riccati (DARE)", "P"),
        ("Gain K", "(R+BᵀPB)⁻¹BᵀPA"),
        ("Feedback law", "u = −K x_aug"),
    ]
    b = '<text class="s" x="20" y="24">LQR design process</text>'
    w, gap, x = 100, 18, 14
    for i, (t, s) in enumerate(steps):
        b += _box(x, 60, w, 64, t, s, hot=(i in (3, 4)))
        if i < len(steps) - 1:
            b += _arrow(x + w, 92, x + w + gap, 92)
        x += w + gap
    b += '<text class="s" x="14" y="165">Checks before the gain is accepted:</text>'
    b += '<text class="m" x="14" y="185">controllability rank = 3  ·  Riccati residual ≈ 0  ·  all closed-loop |λ| &lt; 1</text>'
    b += '<path class="fb" d="M640,124 L640,140 L100,140 L100,124" marker-end="url(#af)"/>'
    b += '<text class="s" x="370" y="134" text-anchor="middle">change weights → recompute</text>'
    return _wrap(736, 205, b, "LQR design process from state-space model to feedback controller")
