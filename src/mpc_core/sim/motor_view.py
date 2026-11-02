"""Self-contained 2D motor animation (HTML/SVG + a little JS) for the Streamlit app.

The component replays one recorded closed-loop run. The shaft angle is the
integral of the recorded speed, shown ``VISUAL_SLOWDOWN`` times slower than the
real rotation so 1000+ RPM stays readable; the timeline itself plays at the
selected rate. Nothing here simulates: it only draws what the run recorded.
"""

from __future__ import annotations

import json

import numpy as np

from mpc_core.sim.simulate import SimulationResult

VISUAL_SLOWDOWN = 20.0
MAX_POINTS = 700


def _decimate(a: np.ndarray, idx: np.ndarray) -> list[float]:
    return [round(float(v), 4) for v in np.asarray(a)[idx]]


def motor_animation_html(run: SimulationResult, *, title: str, height: int = 360) -> str:
    """HTML document for ``st.components.v1.html`` replaying ``run``."""
    n = len(run.time_s)
    idx = np.unique(np.linspace(0, n - 1, min(n, MAX_POINTS)).astype(int))
    data = {
        "t": _decimate(run.time_s, idx),
        "rpm": _decimate(run.speed_rpm, idx),
        "ref": _decimate(run.ref_rpm, idx),
        "i": _decimate(run.i_a, idx),
        "v": _decimate(run.v_applied, idx),
        "load": _decimate(run.load_nm, idx),
        "ilim": [int(x) for x in run.i_limited[idx]],
        "vsat": [int(x) for x in run.v_saturated[idx]],
        "imax": run.i_max,
        "vmax": run.v_max,
        "slow": VISUAL_SLOWDOWN,
    }
    return (
        _TEMPLATE.replace("__DATA__", json.dumps(data))
        .replace("__TITLE__", title)
        .replace("__SLOW__", f"{VISUAL_SLOWDOWN:.0f}")
        .replace("__H__", str(height))
    )


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { --b:#304656; --s:#172633; --sub:#263A49; --t:#EAF1F5; --t2:#B3C2CB; --m:#8FA2B0;
          --a:#36C4D8; --c:#F0B35A; --ok:#55C68E; --bad:#F06C72; }
  * { box-sizing: border-box; }
  body { margin:0; font: 14px/1.4 'IBM Plex Sans', system-ui, sans-serif; color: var(--t); background: transparent; }
  .wrap { border:1px solid var(--b); border-radius:3px; background: var(--s); padding:12px 16px; }
  .top { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }
  .ttl { font-weight:600; }
  .note { color: var(--m); font-size:12px; }
  .row { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
  svg { width: 100%; max-width: 360px; height: auto; flex: 1 1 260px; }
  .stats { flex: 1 1 200px; display:grid; grid-template-columns: 1fr 1fr; gap:8px 16px; }
  .stat .k { color: var(--t2); font-size:12px; }
  .stat .v { font-size:20px; font-weight:600; font-variant-numeric: tabular-nums; font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace; }
  .badge { display:inline-block; padding:2px 10px; border-radius:3px; font-size:12px; font-weight:600;
           background: var(--sub); border:1px solid var(--b); }
  .ctl { display:flex; gap:10px; align-items:center; margin-top:8px; flex-wrap:wrap; }
  button, select { font: inherit; padding:4px 12px; border-radius:3px; border:1px solid var(--b);
                   background: var(--sub); color: var(--t); cursor:pointer; }
  button.primary { background: var(--a); border-color: var(--a); color:#0D1722; }
  input[type=range] { flex: 1 1 160px; accent-color: var(--a); }
  .bar { height:8px; background: var(--sub); border-radius:4px; overflow:hidden; border:1px solid var(--b); }
  .bar > i { display:block; height:100%; width:0; background: var(--a); }
</style></head>
<body><div class="wrap">
  <div class="top"><span class="ttl">__TITLE__</span>
    <span class="note">Shaft rotation drawn __SLOW__&times; slower than real speed</span></div>
  <div class="row">
    <svg viewBox="0 0 300 300" role="img" aria-label="Rotating motor shaft">
      <circle cx="150" cy="150" r="128" fill="var(--sub)" stroke="var(--b)" stroke-width="2"/>
      <path d="M150 22 A128 128 0 0 1 278 150 L240 150 A90 90 0 0 0 150 60 Z" fill="var(--c)" opacity=".85"/>
      <path d="M150 278 A128 128 0 0 1 22 150 L60 150 A90 90 0 0 0 150 240 Z" fill="var(--a)" opacity=".85"/>
      <text x="236" y="70" fill="#0D1722" font-size="16" font-weight="700">N</text>
      <text x="52" y="244" fill="#0D1722" font-size="16" font-weight="700">S</text>
      <g id="rotor">
        <circle cx="150" cy="150" r="76" fill="var(--s)" stroke="var(--t2)" stroke-width="2"/>
        <line x1="150" y1="150" x2="150" y2="84" stroke="var(--t)" stroke-width="6" stroke-linecap="round"/>
        <rect x="140" y="150" width="20" height="62" rx="4" fill="var(--m)" opacity=".55"/>
        <circle cx="150" cy="150" r="16" fill="var(--t2)"/>
      </g>
      <path id="dir" d="M0 0" fill="none" stroke="var(--ok)" stroke-width="5" stroke-linecap="round"/>
      <polygon id="dirhead" points="0,0 0,0 0,0" fill="var(--ok)"/>
      <rect id="loadbar" x="262" y="296" width="14" height="0" fill="var(--c)" rx="3"/>
    </svg>
    <div class="stats">
      <div class="stat"><div class="k">Speed</div><div class="v" id="rpm">0 RPM</div></div>
      <div class="stat"><div class="k">Reference</div><div class="v" id="ref">0 RPM</div></div>
      <div class="stat"><div class="k">Armature current</div><div class="v" id="cur">0 A</div>
        <div class="bar"><i id="curbar"></i></div></div>
      <div class="stat"><div class="k">Armature voltage</div><div class="v" id="volt">0 V</div>
        <div class="bar"><i id="voltbar"></i></div></div>
      <div class="stat"><div class="k">Load torque</div><div class="v" id="load">0 Nm</div></div>
      <div class="stat"><div class="k">State</div><div class="v"><span class="badge" id="state">Stopped</span></div></div>
    </div>
  </div>
  <div class="ctl">
    <button class="primary" id="play">Play</button>
    <button id="restart">Restart</button>
    <label class="note">Rate <select id="rate">
      <option value="0.5">0.5x</option><option value="1" selected>1x</option>
      <option value="2">2x</option><option value="4">4x</option></select></label>
    <input type="range" id="scrub" min="0" max="1000" value="0" aria-label="Time">
    <span class="note" id="clock">0.00 s</span>
  </div>
</div>
<script>
const D = __DATA__;
const n = D.t.length, T = D.t[n-1] || 1;
// Cumulative shaft angle [deg] drawn slowed by D.slow.
const ang = new Array(n).fill(0);
for (let k = 1; k < n; k++) {
  const w = 0.5 * (D.rpm[k] + D.rpm[k-1]) * 6;   // RPM -> deg/s
  ang[k] = ang[k-1] + w * (D.t[k] - D.t[k-1]) / D.slow;
}
const $ = id => document.getElementById(id);
let tNow = 0, playing = false, last = null;
function at(arr, t) {
  if (t <= D.t[0]) return arr[0];
  if (t >= T) return arr[n-1];
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (D.t[m] <= t) lo = m; else hi = m; }
  const f = (t - D.t[lo]) / (D.t[hi] - D.t[lo]);
  return arr[lo] + f * (arr[hi] - arr[lo]);
}
function nearest(arr, t) {
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (D.t[m] <= t) lo = m; else hi = m; }
  return arr[lo];
}
function arrow(dirSign) {
  if (dirSign === 0) { $('dir').setAttribute('d', 'M0 0'); $('dirhead').setAttribute('points', '0,0 0,0 0,0'); return; }
  // Arc around the stator; arrowhead points the way the shaft turns.
  const r = 142, a0 = -50, a1 = 50;
  const p = a => [150 + r * Math.sin(a * Math.PI / 180), 150 - r * Math.cos(a * Math.PI / 180)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  $('dir').setAttribute('d', `M${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1}`);
  const tip = dirSign > 0 ? p(a1 + 9) : p(a0 - 9), base = dirSign > 0 ? p(a1) : p(a0);
  const dx = tip[0] - base[0], dy = tip[1] - base[1], nx = -dy * 0.9, ny = dx * 0.9;
  $('dirhead').setAttribute('points', `${tip[0]},${tip[1]} ${base[0] + nx},${base[1] + ny} ${base[0] - nx},${base[1] - ny}`);
  // Mirror so CW/CCW matches the sign of the speed (positive = clockwise as drawn).
}
function draw() {
  const rpm = at(D.rpm, tNow), ref = at(D.ref, tNow), i = at(D.i, tNow), v = at(D.v, tNow), ld = at(D.load, tNow);
  $('rotor').setAttribute('transform', `rotate(${at(ang, tNow)} 150 150)`);
  $('rpm').textContent = Math.round(rpm) + ' RPM';
  $('ref').textContent = Math.round(ref) + ' RPM';
  $('cur').textContent = i.toFixed(2) + ' A';
  $('volt').textContent = v.toFixed(1) + ' V';
  $('load').textContent = ld.toFixed(3) + ' Nm';
  $('curbar').style.width = Math.min(100, Math.abs(i) / D.imax * 100) + '%';
  $('curbar').style.background = Math.abs(i) > 0.97 * D.imax ? 'var(--bad)' : 'var(--a)';
  $('voltbar').style.width = Math.min(100, Math.abs(v) / D.vmax * 100) + '%';
  const lh = Math.min(120, ld / 0.2 * 120);
  $('loadbar').setAttribute('y', 296 - lh); $('loadbar').setAttribute('height', lh);
  arrow(Math.abs(rpm) < 5 ? 0 : (rpm > 0 ? 1 : -1));
  let state = 'Running';
  const lim = nearest(D.ilim, tNow), sat = nearest(D.vsat, tNow);
  if (Math.abs(rpm) < 5 && Math.abs(ref) < 5) state = 'Stopped';
  else if (Math.abs(rpm - ref) > 0.1 * Math.max(200, Math.abs(ref))) state = rpm * ref < 0 ? 'Reversing' : (Math.abs(rpm) < Math.abs(ref) ? 'Accelerating' : 'Braking');
  if (lim) state = 'Current limit';
  else if (sat) state = 'Voltage limit';
  const b = $('state'); b.textContent = state;
  b.style.color = (lim || sat) ? 'var(--bad)' : (state === 'Running' ? 'var(--ok)' : 'var(--t)');
  $('scrub').value = Math.round(tNow / T * 1000);
  $('clock').textContent = tNow.toFixed(2) + ' s / ' + T.toFixed(1) + ' s';
}
function frame(ts) {
  if (playing) {
    if (last !== null) tNow += (ts - last) / 1000 * parseFloat($('rate').value);
    last = ts;
    if (tNow >= T) { tNow = T; playing = false; $('play').textContent = 'Replay'; }
    draw();
    if (playing) requestAnimationFrame(frame);
  }
}
$('play').onclick = () => {
  if (tNow >= T) tNow = 0;
  playing = !playing; last = null;
  $('play').textContent = playing ? 'Pause' : 'Play';
  if (playing) requestAnimationFrame(frame);
};
$('restart').onclick = () => { tNow = 0; last = null; draw(); };
$('scrub').oninput = e => { tNow = e.target.value / 1000 * T; draw(); };
draw();
</script></body></html>
"""
