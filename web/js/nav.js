export function mountNav(active) {
  const items = [
    ["index.html", "overview", "System Overview"],
    ["bench.html", "bench", "Experiment Bench"],
    ["lqr.html", "lqr", "LQR Design Studio"],
    ["mpc.html", "mpc", "MPC Prediction Explorer"],
    ["performance.html", "performance", "Performance Review"],
    ["plant.html", "plant", "Plant Model"],
  ];
  return `
    <aside class="sidebar">
      <p class="brand">DriveBench</p>
      <p class="tag">PMDC Motor Control &amp; Analysis Studio</p>
      <nav class="nav">${items
        .map(([href, id, label]) => `<a href="${href}" class="${id === active ? "active" : ""}">${label}</a>`)
        .join("")}</nav>
      <p class="note" style="margin-top:28px">Static build of the Streamlit app, using precomputed simulation data. Custom motors, live LQR weights and live runs need the Streamlit app.</p>
    </aside>`;
}

export function shell(active, inner) {
  document.getElementById("shell").innerHTML = `${mountNav(active)}<main class="main">${inner}</main>`;
}

export function status(scenario) {
  return `<div class="status"><span>Plant: <b>PMDC motor</b></span><span>Model: <b>3-state, RK4 1 ms</b></span><span>Controller Ts: <b>10 ms</b></span><span>Scenario: <b>${scenario}</b></span></div>`;
}

export async function getJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
