import { COLORS, DASH, IDS, LABELS, UI, WIDTH } from "./theme.js";

const FONT = "IBM Plex Sans, system-ui, sans-serif";
const MONO = "IBM Plex Mono, ui-monospace, Consolas, monospace";

function layout(title, extra = {}) {
  return {
    title: { text: title, x: 0, xanchor: "left", font: { size: 15, color: UI.text } },
    paper_bgcolor: UI.panel,
    plot_bgcolor: UI.canvas,
    font: { family: FONT, size: 13, color: UI.text },
    margin: { l: 64, r: 150, t: 46, b: 48 },
    legend: { orientation: "v", x: 1.01, xanchor: "left", y: 1, font: { size: 13 } },
    hovermode: "x unified",
    xaxis: { title: "Time [s]", gridcolor: UI.grid, zeroline: false, tickfont: { family: MONO, size: 12 } },
    yaxis: { gridcolor: UI.grid, zeroline: false, tickfont: { family: MONO, size: 12 } },
    ...extra,
  };
}

const line = (c) => ({ color: COLORS[c], width: WIDTH[c], dash: DASH[c] });
const limits = (v, yref = "y") =>
  [-v, v].map((y) => ({ type: "line", xref: "paper", x0: 0, x1: 1, yref, y0: y, y1: y,
    line: { color: UI.limit, width: 1, dash: "dash" } }));

export function events(params) {
  const ev = [];
  if (params.ref_high_rpm !== params.ref_low_rpm) ev.push([params.ref_step_at_s, "speed step"]);
  if (params.load_step_to_nm != null) ev.push([params.load_step_at_s, "load step"]);
  if (params.bus_scale_after !== 1) ev.push([params.bus_sag_at_s, "bus sag"]);
  return ev;
}

export function quantityChart(el, data, ids, qty) {
  const runs = data.runs;
  const first = runs[ids[0]];
  const t = first.time_s;
  const evShapes = events(data.params).flatMap(([x, label]) => [
    { type: "line", xref: "x", yref: "paper", x0: x, x1: x, y0: 0, y1: 1, line: { color: "#8FA2B0", width: 1, dash: "dot" } },
  ]);
  const evAnn = events(data.params).map(([x, label]) => ({ x, y: 1, yref: "paper", text: label, showarrow: false,
    xanchor: "left", font: { size: 11, color: UI.text2 } }));
  const pick = {
    speed: ["Speed", "Speed [RPM]", (r) => r.speed_rpm],
    current: ["Armature current", "Armature current [A]", (r) => r.i_a],
    voltage: ["Drive voltage (applied)", "Voltage [V]", (r) => r.v_applied],
    torque: ["Torque", "Torque [N·m]", (r) => r.torque_nm],
  };
  if (qty === "power") {
    const traces = [];
    ids.forEach((c) => {
      const r = runs[c];
      const p = r.v_applied.map((v, k) => v * r.i_a[k]);
      let e = 0;
      const dt = r.time_s[1] - r.time_s[0];
      const en = p.map((x) => (e += x * dt));
      traces.push({ x: r.time_s, y: p, name: LABELS[c], line: line(c), xaxis: "x", yaxis: "y" });
      traces.push({ x: r.time_s, y: en, name: LABELS[c], line: line(c), showlegend: false, xaxis: "x2", yaxis: "y2" });
    });
    Plotly.newPlot(el, traces, layout("Power and energy", {
      height: 520,
      xaxis: { domain: [0, 1], anchor: "y", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
      xaxis2: { domain: [0, 1], anchor: "y2", title: "Time [s]", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
      yaxis: { domain: [0.55, 1], title: "Electrical power [W]", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
      yaxis2: { domain: [0, 0.42], title: "Net electrical energy [J]", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
      shapes: evShapes, annotations: evAnn,
    }), { responsive: true, displaylogo: false });
    return;
  }
  const [title, ylabel, get] = pick[qty];
  const traces = [];
  if (qty === "speed") traces.push({ x: t, y: first.ref_rpm, name: "Reference", line: { color: UI.text, width: 1.5, dash: "dash" } });
  ids.forEach((c) => traces.push({ x: runs[c].time_s, y: get(runs[c]), name: LABELS[c], line: line(c) }));
  if (qty === "torque") traces.push({ x: t, y: first.load_nm, name: "Load torque", line: { color: "#9DB3C2", width: 1.5, dash: "dot" } });
  const lim = qty === "current" ? limits(first.i_max) : qty === "voltage" ? limits(first.v_max) : [];
  Plotly.newPlot(el, traces, layout(title, {
    height: qty === "speed" ? 460 : 380,
    yaxis: { title: ylabel, gridcolor: UI.grid, zeroline: false, tickfont: { family: MONO, size: 12 } },
    shapes: [...evShapes, ...lim], annotations: evAnn,
  }), { responsive: true, displaylogo: false });
}

export function mpcChart(el, snap, tsS, iMax, vMax) {
  const h = snap.predicted_y.length;
  const tf = Array.from({ length: h }, (_, i) => snap.time_s + (i + 1) * tsS);
  const c = COLORS.mpc;
  const traces = [
    { x: [snap.time_s], y: [snap.y_meas], mode: "markers", name: "Measured now", marker: { size: 11, color: "#36C4D8" }, xaxis: "x", yaxis: "y" },
    { x: tf, y: snap.predicted_y, name: "Predicted speed", line: { color: c, width: 2.6 }, xaxis: "x", yaxis: "y" },
    { x: [snap.time_s, tf[h - 1]], y: [snap.y_ref, snap.y_ref], name: "Reference", line: { color: UI.text, dash: "dash", width: 1.5 }, xaxis: "x", yaxis: "y" },
    { x: tf, y: snap.predicted_i, name: "Predicted current", line: { color: c, width: 2.2 }, xaxis: "x2", yaxis: "y2" },
  ];
  if (snap.planned_u_traj && snap.planned_u_traj.length)
    traces.push({ x: tf.slice(0, snap.planned_u_traj.length), y: snap.planned_u_traj, name: "Planned voltage",
      line: { color: c, width: 2.2, shape: "hv" }, xaxis: "x3", yaxis: "y3" });
  const ax = (d, a, t) => ({ domain: d, anchor: a, title: t, gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } });
  Plotly.newPlot(el, traces, layout("Prediction over the horizon", {
    height: 620,
    xaxis: { domain: [0, 1], anchor: "y", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
    xaxis2: { domain: [0, 1], anchor: "y2", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
    xaxis3: { domain: [0, 1], anchor: "y3", title: "Time [s]", gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
    yaxis: ax([0.64, 1], "x", "Speed [RPM]"),
    yaxis2: ax([0.34, 0.58], "x2", "Current [A]"),
    yaxis3: ax([0, 0.28], "x3", "Voltage [V]"),
    shapes: [
      ...limits(iMax, "y2"), ...limits(vMax, "y3"),
    ],
  }), { responsive: true, displaylogo: false });
}

export function barChart(el, title, unit, vals) {
  const traces = IDS.filter((c) => vals[c] != null).map((c) => ({
    type: "bar", name: LABELS[c], x: [title], y: [vals[c]], marker: { color: COLORS[c] },
    text: [Number(vals[c]).toPrecision(3)], textposition: "outside", cliponaxis: false,
  }));
  Plotly.newPlot(el, traces, layout(`${title} [${unit}]`, {
    height: 300, barmode: "group", hovermode: "closest", margin: { l: 56, r: 130, t: 44, b: 40 },
    xaxis: { gridcolor: UI.grid }, yaxis: { title: unit, gridcolor: UI.grid, tickfont: { family: MONO, size: 12 } },
  }), { responsive: true, displaylogo: false });
}
