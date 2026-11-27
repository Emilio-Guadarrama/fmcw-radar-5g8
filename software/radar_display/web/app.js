// Draws what the Python side computes. No radar maths happens here; the one
// number measured here is the delay from capture to screen.
"use strict";

const $ = (id) => document.getElementById(id);
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const COLOR = {
  surface: css("--surface"), ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"),
  grid: css("--line"), axis: css("--edge"), s1: css("--series-1"), s2: css("--series-2"),
  s3: css("--series-3"),
};
const MAX_RANGE_M = 45;
const WATERFALL_SPAN_S = 12;
const HEAT_MAX_DB = 45;
const MARGIN = { left: 46, right: 10, top: 8, bottom: 32 };
const CHART_FONT = "11px 'Segoe UI Variable Text', 'Segoe UI', system-ui, sans-serif";
// Below this plot height there is only room for fewer ticks and short labels.
const SHORT_PLOT_PX = 150;
// One blue hue, dark (near the noise) to light (strong).
const RAMP = ["#17181a", "#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]
  .map((hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)));

let frame = null;
let pending = null;
let frozen = false;
let lastMessageAt = 0;
let serverError = null;
let history = [];
let configKey = "";
let latencies = [];
let latencyShownAt = 0;
let visibilityChangedAt = 0;
let beatScaleMv = 10;
let hover = null;

function heat(db) {
  const x = Math.min(Math.max(db / HEAT_MAX_DB, 0), 1) * (RAMP.length - 1);
  const i = Math.min(Math.floor(x), RAMP.length - 2);
  const t = x - i;
  return RAMP[i].map((v, c) => Math.round(v + (RAMP[i + 1][c] - v) * t));
}

function setText(id, text) {
  const node = $(id);
  if (node.textContent !== text) node.textContent = text;
}

const fmt = (value, digits) => (value === null || value === undefined ? "–" : value.toFixed(digits));

// ---------- canvas helpers ----------

function prepare(canvas) {
  const ratio = window.devicePixelRatio || 1;
  // CSS decides the size; the bitmap follows it.
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const w = Math.round(width * ratio);
  const h = Math.round(height * ratio);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const g = canvas.getContext("2d");
  g.setTransform(ratio, 0, 0, ratio, 0, 0);
  g.clearRect(0, 0, width, height);
  g.font = CHART_FONT;
  const plot = {
    x0: MARGIN.left, x1: width - MARGIN.right, y0: MARGIN.top, y1: height - MARGIN.bottom,
  };
  return { g, plot, width, height };
}

function scale(d0, d1, r0, r1) {
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}

function axes(g, plot, x, y, xTicks, yTicks, xLabel, yLabel) {
  g.lineWidth = 1;
  g.fillStyle = COLOR.muted;
  g.strokeStyle = COLOR.grid;
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (const [value, label] of yTicks) {
    const py = Math.round(y(value)) + 0.5;
    g.beginPath();
    g.moveTo(plot.x0, py);
    g.lineTo(plot.x1, py);
    g.stroke();
    g.fillText(label, plot.x0 - 6, py);
  }
  g.textAlign = "center";
  g.textBaseline = "top";
  for (const [value, label] of xTicks) g.fillText(label, x(value), plot.y1 + 5);
  g.fillText(xLabel, (plot.x0 + plot.x1) / 2, plot.y1 + 19);
  g.save();
  g.translate(11, (plot.y0 + plot.y1) / 2);
  g.rotate(-Math.PI / 2);
  g.textBaseline = "middle";
  g.fillText(yLabel, 0, 0);
  g.restore();
  g.strokeStyle = COLOR.axis;
  g.beginPath();
  g.moveTo(plot.x0, plot.y1 + 0.5);
  g.lineTo(plot.x1, plot.y1 + 0.5);
  g.stroke();
}

const ticks = (from, to, step, digits = 0) => {
  const out = [];
  for (let v = Math.ceil(from / step) * step; v <= to + 1e-9; v += step) out.push([v, v.toFixed(digits)]);
  return out;
};

function path(g, xs, ys, color, width = 2) {
  g.strokeStyle = color;
  g.lineWidth = width;
  g.lineJoin = "round";
  g.beginPath();
  xs.forEach((px, i) => (i ? g.lineTo(px, ys[i]) : g.moveTo(px, ys[i])));
  g.stroke();
}

function clipTo(g, plot) {
  g.save();
  g.beginPath();
  g.rect(plot.x0, plot.y0, plot.x1 - plot.x0, plot.y1 - plot.y0);
  g.clip();
}

// Shade the distances that are not searched for targets.
function shadeUntested(g, plot, x, targets) {
  g.fillStyle = "rgba(0,0,0,0.38)";
  g.fillRect(plot.x0, plot.y0, x(targets.min_range_m) - plot.x0, plot.y1 - plot.y0);
  g.fillRect(x(targets.max_range_m), plot.y0, plot.x1 - x(targets.max_range_m), plot.y1 - plot.y0);
}

// ---------- charts ----------

function drawSpectrum() {
  const { g, plot } = prepare($("spectrum"));
  const s = frame.spectrum;
  const bottom = -100;
  const top = 0;
  const x = scale(0, MAX_RANGE_M, plot.x0, plot.x1);
  const y = scale(bottom, top, plot.y1, plot.y0);
  const short = plot.y1 - plot.y0 < SHORT_PLOT_PX;
  axes(g, plot, x, y, ticks(0, MAX_RANGE_M, 5), ticks(short ? -80 : bottom, top, short ? 40 : 20),
    "Distance (m)", short ? "dBV" : "Echo strength (dBV)");
  clipTo(g, plot);
  shadeUntested(g, plot, x, frame.targets);
  g.fillStyle = COLOR.muted;
  g.textAlign = "left";
  g.textBaseline = "top";
  // Label a shaded area only where the words fit inside it.
  const label = "not searched";
  const needed = g.measureText(label).width + 3;
  for (const [from, to] of [[0, frame.targets.min_range_m], [frame.targets.max_range_m, MAX_RANGE_M]]) {
    if (x(to) - x(from) >= needed) g.fillText(label, x(from) + 2, plot.y0 + 2);
  }

  const clamp = (v) => Math.max(v, bottom);
  const lineX = s.db.map((_, i) => x(i * s.range_step_m));
  const lineY = s.db.map((v) => y(clamp(v)));
  g.beginPath();
  g.moveTo(lineX[0], plot.y1);
  lineX.forEach((px, i) => g.lineTo(px, lineY[i]));
  g.lineTo(lineX[lineX.length - 1], plot.y1);
  g.globalAlpha = 0.1;
  g.fillStyle = COLOR.s1;
  g.fill();
  g.globalAlpha = 1;
  path(g, lineX, lineY, COLOR.s1);

  // Threshold: one flat step per range cell, only where cells are tested.
  const cell = frame.settings.range_cell_m;
  const xs = [];
  const ys = [];
  const lo = frame.targets.min_range_m - cell / 2;
  const hi = frame.targets.max_range_m + cell / 2;
  s.cell_range_m.forEach((r, i) => {
    if (r < lo || r > hi) return;
    xs.push(x(r - cell / 2), x(r + cell / 2));
    ys.push(y(clamp(s.threshold_db[i])), y(clamp(s.threshold_db[i])));
  });
  path(g, xs, ys, COLOR.s2);

  s.cell_range_m.forEach((r, i) => {
    g.beginPath();
    g.arc(x(r), y(clamp(s.cell_db[i])), 3.5, 0, 2 * Math.PI);
    g.fillStyle = COLOR.s1;
    g.fill();
    g.strokeStyle = COLOR.surface;
    g.lineWidth = 1.5;
    g.stroke();
  });

  for (const t of frame.truth || []) {
    g.fillStyle = COLOR.ink2;
    g.fillRect(x(t.range_m) - 1, plot.y1 - 12, 2, 12);
  }

  let labelEnd = -Infinity;
  [...frame.detections].sort((a, b) => a.range_m - b.range_m).forEach((d) => {
    const px = x(d.range_m);
    const py = Math.max(y(d.amplitude_dbv) - 6, plot.y0 + 24);
    g.fillStyle = COLOR.ink;
    g.beginPath();
    g.moveTo(px - 6, py - 9);
    g.lineTo(px + 6, py - 9);
    g.lineTo(px, py);
    g.fill();
    const text = `${d.range_m.toFixed(2)} m`;
    const half = g.measureText(text).width / 2;
    // Skip a label that would collide; the table still lists the target.
    if (px - half > labelEnd + 6) {
      g.textAlign = "center";
      g.textBaseline = "bottom";
      g.fillText(text, px, py - 11);
      labelEnd = px + half;
    }
  });
  g.restore();

  crosshair("spectrum", g, plot, x, (r) => {
    const i = Math.round(r / s.range_step_m);
    if (i < 0 || i >= s.db.length) return null;
    let k = 0;
    s.cell_range_m.forEach((c, j) => {
      if (Math.abs(c - r) < Math.abs(s.cell_range_m[k] - r)) k = j;
    });
    return `Distance ${r.toFixed(2)} m\nEcho ${s.db[i].toFixed(1)} dBV\n` +
      `Nearest cell ${s.cell_db[k].toFixed(1)} dBV\nIts threshold ${s.threshold_db[k].toFixed(1)} dBV`;
  }, 0, MAX_RANGE_M);
}

function drawBeat() {
  const { g, plot } = prepare($("beat"));
  const b = frame.beat;
  const chirpMs = frame.settings.chirp_ms;
  const peak = Math.max(...b.first_chirp_mv.map(Math.abs), 5);
  // Grow at once, shrink slowly, so the axis does not jitter.
  const wanted = niceCeil(peak * 1.15);
  if (wanted > beatScaleMv || wanted < beatScaleMv / 2) beatScaleMv = wanted;
  const x = scale(0, chirpMs, plot.x0, plot.x1);
  const y = scale(-beatScaleMv, beatScaleMv, plot.y1, plot.y0);
  const short = plot.y1 - plot.y0 < SHORT_PLOT_PX;
  const yTicks = (short ? [-1, 0, 1] : [-1, -0.5, 0, 0.5, 1]).map((f) => [f * beatScaleMv, `${+(f * beatScaleMv).toFixed(1)}`]);
  axes(g, plot, x, y, ticks(0, chirpMs, chirpMs / 5, 1), yTicks,
    "Time within the chirp (ms)", short ? "mV" : "Voltage (mV)");
  clipTo(g, plot);
  const xs = b.t_ms.map(x);
  path(g, xs, b.first_chirp_mv.map(y), COLOR.s1);
  path(g, xs, b.average_mv.map(y), COLOR.s3);
  g.restore();
  crosshair("beat", g, plot, x, (t) => {
    const i = Math.round(t / (b.t_ms[1] - b.t_ms[0]));
    if (i < 0 || i >= b.t_ms.length) return null;
    return `Time ${b.t_ms[i].toFixed(2)} ms\nOne chirp ${b.first_chirp_mv[i].toFixed(2)} mV\n` +
      `Average ${b.average_mv[i].toFixed(2)} mV`;
  }, 0, chirpMs);
}

function niceCeil(v) {
  const power = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 4, 5, 10].map((m) => m * power).find((c) => c >= v);
}

function rowImage(values, step) {
  const used = Math.min(values.length, Math.floor(MAX_RANGE_M / step) + 1);
  const row = document.createElement("canvas");
  row.width = used;
  row.height = 1;
  const g = row.getContext("2d");
  const image = g.createImageData(used, 1);
  for (let i = 0; i < used; i += 1) image.data.set([...heat(values[i]), 255], 4 * i);
  g.putImageData(image, 0, 0);
  return { row, firstM: -step / 2, lastM: (used - 0.5) * step };
}

function drawWaterfall() {
  const { g, plot } = prepare($("waterfall"));
  const x = scale(0, MAX_RANGE_M, plot.x0, plot.x1);
  const y = scale(0, WATERFALL_SPAN_S, plot.y0, plot.y1);
  const every = plot.y1 - plot.y0 < 90 ? 6 : 3;
  axes(g, plot, x, y, ticks(0, MAX_RANGE_M, 5),
    ticks(0, WATERFALL_SPAN_S, every).map(([v]) => [v, v ? `${v} s ago` : "now"]), "Distance (m)", "");
  clipTo(g, plot);
  const newest = history.length ? history[history.length - 1].time : 0;
  const period = 1 / (frame.stream.update_rate_hz || 12.5);
  g.imageSmoothingEnabled = false;
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const entry = history[i];
    const age = (newest - entry.time) / 1000;
    // A row lasts one frame period, so lost frames show as dark gaps.
    g.drawImage(entry.row, x(entry.firstM), y(age), x(entry.lastM) - x(entry.firstM),
      Math.max(y(period) - y(0), 1) + 0.6);
  }
  shadeUntested(g, plot, x, frame.targets);
  g.restore();
}

function drawRamp() {
  const g = $("ramp").getContext("2d");
  for (let i = 0; i < 100; i += 1) {
    g.fillStyle = `rgb(${heat((i / 99) * HEAT_MAX_DB).join(",")})`;
    g.fillRect(i, 0, 1, 8);
  }
}

// ---------- hover ----------

function crosshair(id, g, plot, x, describe, d0, d1) {
  const tip = $("tooltip");
  if (!hover || hover.id !== id) return;
  const px = hover.x;
  if (px < plot.x0 || px > plot.x1) {
    tip.hidden = true;
    return;
  }
  const value = d0 + ((px - plot.x0) / (plot.x1 - plot.x0)) * (d1 - d0);
  const text = describe(value);
  if (!text) return;
  g.strokeStyle = COLOR.muted;
  g.lineWidth = 1;
  g.beginPath();
  g.moveTo(px, plot.y0);
  g.lineTo(px, plot.y1);
  g.stroke();
  tip.textContent = text;
  tip.hidden = false;
  tip.style.left = `${Math.min(hover.clientX + 14, window.innerWidth - 190)}px`;
  tip.style.top = `${hover.clientY + 14}px`;
}

function setupHover() {
  const tip = document.createElement("div");
  tip.id = "tooltip";
  tip.hidden = true;
  document.body.append(tip);
  for (const id of ["spectrum", "beat"]) {
    $(id).addEventListener("pointermove", (event) => {
      const box = $(id).getBoundingClientRect();
      hover = { id, x: event.clientX - box.left, clientX: event.clientX, clientY: event.clientY };
      if (frame) redraw();
    });
    $(id).addEventListener("pointerleave", () => {
      hover = null;
      tip.hidden = true;
      if (frame) redraw();
    });
  }
}

// ---------- text panels ----------

function fillList(id, rows) {
  const list = $(id);
  const key = JSON.stringify(rows);
  if (list.dataset.key === key) return;
  list.dataset.key = key;
  list.replaceChildren(...rows.flatMap(([term, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = value;
    return [dt, dd];
  }));
}

const SCENE_NOTES = {
  single: "One still reflector. Its echo weakens with distance.",
  pair: "Two equal echoes, for the two-target (resolution) question.",
  moving: "1 m/s, 4 to 28 m. Simplified: still within each frame. A real moving target could fade or vanish.",
  three: "Still reflectors at 6, 14 and 24 m. Far ones are much weaker.",
  empty: "No reflectors. Any detection here is a false alarm.",
};

// Show the server's choice, unless the user is using that control right now.
function showChoice(name, value) {
  const seg = $(`${name}-seg`);
  if (seg.contains(document.activeElement)) return;
  seg.querySelector(`input[value="${value}"]`).checked = true;
}

function showSimulation() {
  // Another tab, or a reload, must show the window the server is really using.
  showChoice("window", frame.settings.window);
  const sim = frame.simulation;
  $("sim-controls").hidden = !sim;
  $("drop").hidden = !sim;
  if (!sim) return;
  showChoice("sweep", sim.sweep);
  for (const id of ["scene", "distance_m", "separation_m", "noise_mv"]) {
    // Leave a control alone while the user is using it.
    if (document.activeElement !== $(id)) $(id).value = sim[id];
  }
  setText("distance-out", `${Number($("distance_m").value).toFixed(1)} m`);
  setText("separation-out", `${Number($("separation_m").value).toFixed(1)} m`);
  setText("noise-out", `${$("noise_mv").value} mV RMS`);
  setText("scene-note", SCENE_NOTES[sim.scene]);
  $("distance-row").hidden = !["single", "pair"].includes(sim.scene);
  $("separation-row").hidden = sim.scene !== "pair";
}

function showTables() {
  const rows = frame.detections.map((d, i) => {
    const tr = document.createElement("tr");
    for (const text of [`${i + 1}`, `${d.range_m.toFixed(2)} m`, `${d.snr_db.toFixed(1)} dB`,
      `${(d.beat_hz / 1000).toFixed(2)} kHz`]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.append(td);
    }
    return tr;
  });
  if (!rows.length) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 4;
    td.textContent = "No target above the threshold";
    tr.append(td);
    rows.push(tr);
  }
  $("detections").replaceChildren(...rows);
  setText("tab-found", `Targets (${frame.detections.length})`);
  const truth = frame.truth;
  let note = "";
  if (truth) {
    note = truth.length
      ? `Simulation's true positions: ${truth.map((t) => `${t.range_m.toFixed(2)} m`).join(", ")}.`
      : "The simulation has no targets.";
  }
  setText("truth-note", note);

  const s = frame.settings;
  const sim = frame.simulation;
  fillList("settings", [
    ["Sweep", `${s.f_start_ghz.toFixed(3)}–${s.f_stop_ghz.toFixed(3)} GHz`],
    ["Bandwidth", `${s.bandwidth_mhz.toFixed(0)} MHz`],
    ["Range cell c/(2B)", `${s.range_cell_m.toFixed(3)} m`],
    ["Chirp time (assumption)", `${s.chirp_ms.toFixed(1)} ms`],
    ["Sample rate (assumption)", `${s.sample_rate_ksps.toFixed(0)} kSPS`],
    ["Samples per chirp", `${s.samples_per_chirp}`],
    ["Chirps per frame", `${s.chirps_per_frame}`],
    ["Time to record a frame", `${s.frame_capture_ms.toFixed(0)} ms (no gaps assumed)`],
    ["Latency counts", "recording + processing + screen (no USB link yet)"],
    ["Processing time (this PC)", `${Math.round(frame.stream.processing_ms)} ms`],
    ["Window", s.window === "hann" ? "Hann" : "Rectangular"],
    ["Gain from averaging (still target)", `${s.integration_gain_db.toFixed(1)} dB`],
    ["False-alarm setting (Pfa)", `${s.pfa} per cell per frame`],
    ["Threshold above noise", `${s.threshold_above_noise_db.toFixed(1)} dB`],
    ["Range cells searched", `${s.cells_tested}`],
    ["Expected false alarms (ideal noise)", s.false_alarm_every_s
      ? `about 1 every ${Math.round(s.false_alarm_every_s)} s or less` : "–"],
    ["Farthest unaliased distance", `${s.max_unaliased_range_m.toFixed(1)} m`],
    ["Simulated converter (assumption)", `${s.adc_bits} bit, ±${s.adc_full_scale_v} V`],
    ...(sim ? [["Simulated noise (assumption)", `${sim.noise_mv} mV RMS per sample`]] : []),
  ]);

  const t = frame.targets;
  const sweep = s.bandwidth_mhz > 120 ? "150" : "115";
  fillList("targets", [
    ["Two equal targets told apart", `at ${t.resolution_m[sweep]} m or less (rectangular)`],
    ["Distance error", `≤ ${t.accuracy_m.toFixed(2)} m in 95 % of trials, SNR ≥ ${t.accuracy_snr_db} dB`],
    ["Chance of detection", `≥ ${t.pd.toFixed(2)} at Pfa ${t.pfa}`],
    ["Searched distances", `${t.min_range_m} to ${t.max_range_m} m`],
    ["Update rate", `≥ ${t.update_rate_hz} Hz`],
    ["Latency", `≤ ${t.latency_ms} ms`],
    ["Reference reflector", "triangular trihedral, 0.15 m leg edge (not modelled)"],
  ]);
}

function showTiles() {
  const best = frame.detections[0];
  const count = frame.detections.length;
  setText("t-range", best ? best.range_m.toFixed(2) : "none");
  let found = "Nothing is above the threshold";
  if (count === 1) found = "The only target found";
  if (count > 1) found = `Loudest of ${count} targets found`;
  setText("t-range-sub", found);
  setText("t-snr", best ? best.snr_db.toFixed(1) : "–");
  setText("t-snr-sub", best ? "Echo above noise (estimate)" : "No target, so no SNR");
  setText("t-rate", fmt(frame.stream.update_rate_hz, 1));
  setText("t-rate-sub", `Goal ≥ ${frame.targets.update_rate_hz} Hz, on this PC`);
  const st = frame.stream;
  setText("t-dropped", `${st.dropped}`);
  setText("t-dropped-sub",
    `${st.dropped_last_10_s} in last 10 s, ${(100 * st.dropped_fraction).toFixed(1)} % in all`);
}

// Capture-to-screen delay, plus the time needed to record the frame.
function measureLatency(shown) {
  // A hidden window pauses drawing, so such a sample would time the pause.
  if (document.hidden || visibilityChangedAt >= shown.captured_epoch_ms) return;
  const toScreen = Date.now() - shown.captured_epoch_ms;
  const total = shown.settings.frame_capture_ms + Math.max(toScreen, 0);
  latencies.push(total);
  if (latencies.length > 25) latencies.shift();
  if (performance.now() - latencyShownAt < 500) return;
  latencyShownAt = performance.now();
  const worst = Math.max(...latencies);
  setText("t-latency", total.toFixed(0));
  setText("t-latency-sub",
    `Worst recent ${worst.toFixed(0)} ms, goal ≤ ${shown.targets.latency_ms} ms`);
}

function showHeader() {
  const s = frame.settings;
  const key = s.bandwidth_mhz > 120 ? "150" : "115";
  setText("sweep-name",
    `${s.bandwidth_mhz.toFixed(0)} MHz, ${s.f_start_ghz.toFixed(3)}–${s.f_stop_ghz.toFixed(3)} GHz`);
  setText("sweep-note", frame.sweep_notes[key]);
  setText("u-chirp", `${s.chirp_ms.toFixed(1)} ms`);
  setText("u-rate", `${s.sample_rate_ksps.toFixed(0)} kSPS`);
  setText("u-chirps", `${s.chirps_per_frame}`);
  setText("u-window", s.window === "hann" ? "Hann" : "Rectangular");
  const simulated = frame.source.is_simulated;
  setText("banner-title", simulated ? "SIMULATED DATA" : "HARDWARE DATA SOURCE");
  setText("banner-text", simulated
    ? "No radar hardware is connected. Nothing here is a measurement."
    : frame.source.description);
  const notes = [];
  if (s.window === "rect") {
    notes.push("RESOLUTION TEST VIEW (rectangular window). Look for two separate bumps on the blue curve. Normal detection uses Hann.");
  }
  if (frame.beat.clipped) notes.push("Signal is clipping at the converter limit.");
  if (serverError) notes.push(`Processing error: ${serverError}`);
  $("alert").hidden = !notes.length;
  $("alert").classList.toggle("error", Boolean(serverError));
  setText("alert", notes.join("  "));
}

function redraw() {
  drawSpectrum();
  drawWaterfall();
  drawBeat();
}

function render() {
  if (!pending) return;
  frame = pending;
  pending = null;
  showHeader();
  showTiles();
  showSimulation();
  showTables();
  setText("avg-label", `Average of ${frame.settings.chirps_per_frame} chirps`);
  redraw();
  const shown = frame;
  // The next animation frame is the first one after this drawing is shown.
  requestAnimationFrame(() => measureLatency(shown));
}

function accept(next) {
  // While frozen, nothing on screen may change, the waterfall included.
  if (frozen) return;
  // Old rows are not comparable after a sweep or window change.
  const key = `${next.settings.bandwidth_mhz}/${next.settings.window}`;
  if (key !== configKey) {
    configKey = key;
    history = [];
    latencies = [];
  }
  history.push({
    time: next.captured_epoch_ms,
    ...rowImage(next.waterfall.above_floor_db, next.waterfall.range_step_m),
  });
  while (history.length && history[0].time < next.captured_epoch_ms - WATERFALL_SPAN_S * 1000) {
    history.shift();
  }
  const waiting = pending !== null;
  pending = next;
  if (!waiting) requestAnimationFrame(render);
}

function setLink(state, text) {
  $("link").className = `link ${state}`;
  setText("link", text);
  document.body.classList.toggle("stale", state === "lost");
}

function connect() {
  const stream = new EventSource("/api/stream");
  stream.onmessage = (event) => {
    const message = JSON.parse(event.data);
    serverError = message.error;
    if (serverError) {
      setLink("lost", "processing error");
      $("alert").hidden = false;
      $("alert").classList.add("error");
      setText("alert", `Processing error: ${serverError}`);
      return;
    }
    lastMessageAt = performance.now();
    setLink("live", frozen ? "screen frozen" : "live");
    accept(message.frame);
  };
  stream.onerror = () => setLink("lost", "connection lost, retrying… (values shown are old)");
}

setInterval(() => {
  if (lastMessageAt && performance.now() - lastMessageAt > 1500 && !serverError) {
    setLink("lost", "no new data (values shown are old)");
  }
}, 500);

async function send(command) {
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(command),
    });
    if (!response.ok) console.warn((await response.json()).error);
  } catch (error) {
    console.warn(error);
  }
}

function setupControls() {
  $("scene").addEventListener("change", () => {
    send({ simulation: { scene: $("scene").value } });
    $("scene").blur();
  });
  $("sweep-seg").addEventListener("change", (event) => {
    send({ simulation: { sweep: event.target.value } });
  });
  $("window-seg").addEventListener("change", (event) => send({ window: event.target.value }));
  // After a mouse click the choice must not stay "in use". Keyboard focus stays.
  for (const id of ["sweep-seg", "window-seg"]) {
    $(id).addEventListener("pointerup", () => setTimeout(() => document.activeElement.blur(), 300));
  }
  for (const id of ["distance_m", "separation_m", "noise_mv"]) {
    $(id).addEventListener("input", () => send({ simulation: { [id]: Number($(id).value) } }));
    $(id).addEventListener("pointerup", () => $(id).blur());
  }
  $("drop").addEventListener("click", () => send({ drop_frames: 5 }));
  $("freeze").addEventListener("click", () => {
    frozen = !frozen;
    if (frozen) pending = null;
    $("freeze").setAttribute("aria-pressed", String(frozen));
    setText("freeze", frozen ? "Resume screen" : "Freeze screen");
  });
}

function setupTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const select = (chosen) => {
    for (const tab of tabs) {
      const on = tab === chosen;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      $(tab.getAttribute("aria-controls")).hidden = !on;
    }
  };
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      const next = tabs[(i + step + tabs.length) % tabs.length];
      select(next);
      next.focus();
      event.preventDefault();
    });
  });
}

// Redraw whenever a graph changes size (window resize, a notice appearing).
const resized = new ResizeObserver(() => frame && redraw());
document.querySelectorAll(".plot").forEach((node) => resized.observe(node));
document.addEventListener("visibilitychange", () => {
  visibilityChangedAt = Date.now();
});
drawRamp();
setupHover();
setupControls();
setupTabs();
connect();
