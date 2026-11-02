export const IDS = ["pid", "optimized_pid", "lqr", "mpc"];
export const LABELS = { pid: "PID", optimized_pid: "Optimised PID", lqr: "LQR", mpc: "MPC" };
export const COLORS = { pid: "#78A8D5", optimized_pid: "#43C5A2", lqr: "#F0B35A", mpc: "#B49AF7" };
export const DASH = { pid: "solid", optimized_pid: "dash", lqr: "dashdot", mpc: "solid" };
export const WIDTH = { pid: 1.8, optimized_pid: 1.8, lqr: 2, mpc: 2.6 };
export const UI = { text: "#EAF1F5", text2: "#B3C2CB", panel: "#172633", canvas: "#0D1722", grid: "#243747", limit: "#F06C72" };

export function legend(ids = IDS) {
  const dash = { solid: "solid", dash: "dashed", dashdot: "dotted" };
  return `<div class="legend">${ids
    .map((c) => `<span><i style="border-top-style:${dash[DASH[c]]};color:${COLORS[c]}"></i>${LABELS[c]}</span>`)
    .join("")}</div>
    <p class="note">LQR is the integral-augmented design (LQI): the integral state gives zero steady-state speed error.</p>`;
}
