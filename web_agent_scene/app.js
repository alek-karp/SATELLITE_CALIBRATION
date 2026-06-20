import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { createEarth, latLonToVector } from "./models/earth.js";
import { createGroundAntenna } from "./models/ground-antenna.js";
import { createSatellite } from "./models/satellite.js";

const ACTIONS = [
  ["nudge_az_pos_small", "Az +0.1"],
  ["nudge_az_neg_small", "Az -0.1"],
  ["nudge_az_pos_medium", "Az +0.5"],
  ["nudge_az_neg_medium", "Az -0.5"],
  ["nudge_az_pos_large", "Az +2.0"],
  ["nudge_az_neg_large", "Az -2.0"],
  ["nudge_el_pos_small", "El +0.1"],
  ["nudge_el_neg_small", "El -0.1"],
  ["nudge_el_pos_medium", "El +0.5"],
  ["nudge_el_neg_medium", "El -0.5"],
  ["nudge_el_pos_large", "El +2.0"],
  ["nudge_el_neg_large", "El -2.0"],
  ["snap_to_ephemeris", "Snap"],
  ["shift_freq_pos_fine", "Freq +10"],
  ["shift_freq_neg_fine", "Freq -10"],
  ["shift_freq_pos_med", "Freq +100"],
  ["shift_freq_neg_med", "Freq -100"],
  ["shift_freq_pos_coarse", "Freq +1k"],
  ["shift_freq_neg_coarse", "Freq -1k"],
  ["cycle_polarization", "Pol"],
  ["narrow_bandwidth", "Narrow"],
  ["widen_bandwidth", "Widen"],
  ["hold", "Hold"],
  ["request_handoff", "Handoff"],
];

const POLARIZATIONS = ["H", "V", "RHCP", "LHCP"];
const PASS_DURATION = 180;
const SNR_THRESHOLD = 10;
const LOCK_MIN = 5;
const TRACKING_LEAK = 0.055;
const PHASES = [
  { at: 0, text: "Acquire the pass. Bring pointing error down and hold lock." },
  { at: 28, text: "Nominal tracking. Keep SNR above 10 dB while the satellite moves." },
  { at: 62, text: "Anomaly: polarization rotation. Try Hold, then cycle polarization." },
  { at: 98, text: "Anomaly: antenna drift. Correct azimuth and elevation before lock drops." },
  { at: 144, text: "Handoff window open. Request handoff to finish the episode." },
];

const episode = {
  satellite: "NOAA-19",
  maxElevation: 54,
  anomalies: [
    { kind: "polarization", onset: 62, duration: 34, truePolarization: 2 },
    { kind: "drift", onset: 98, duration: 42, azRate: 0.075, elRate: -0.045 },
  ],
};

const ui = {
  time: document.querySelector("[data-stat='time']"),
  phase: document.querySelector("[data-stat='phase']"),
  snr: document.querySelector("[data-stat='snr']"),
  lock: document.querySelector("[data-stat='lock']"),
  reward: document.querySelector("[data-stat='reward']"),
  az: document.querySelector("[data-stat='az']"),
  el: document.querySelector("[data-stat='el']"),
  freq: document.querySelector("[data-stat='freq']"),
  pol: document.querySelector("[data-stat='pol']"),
  bandwidth: document.querySelector("[data-stat='bandwidth']"),
  action: document.querySelector("[data-stat='action']"),
  score: document.querySelector("[data-stat='score']"),
  eventLog: document.querySelector("[data-event-log]"),
  actions: document.querySelector("[data-actions]"),
  run: document.querySelector("[data-run]"),
  step: document.querySelector("[data-step]"),
  reset: document.querySelector("[data-reset]"),
};

const root = document.getElementById("scene-root");

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x02050a);
scene.fog = new THREE.FogExp2(0x02050a, 0.018);

const camera = new THREE.PerspectiveCamera(48, root.clientWidth / root.clientHeight, 0.1, 200);
camera.position.set(10.5, 6.8, 11.5);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(root.clientWidth, root.clientHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
root.appendChild(renderer.domElement);

const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = true;
orbit.minDistance = 6;
orbit.maxDistance = 26;
orbit.target.set(0, 0, 0);

scene.add(new THREE.AmbientLight(0xa7c7ff, 0.65));

const sun = new THREE.DirectionalLight(0xffffff, 1.75);
sun.position.set(12, 7, 8);
scene.add(sun);

const fill = new THREE.PointLight(0x69d7ff, 1.1, 40);
fill.position.set(-8, -3, -8);
scene.add(fill);

const { group: earthGroup, earth, atmosphere, cloudBand } = createEarth();
scene.add(earthGroup);

const orbitRing = new THREE.Mesh(
  new THREE.TorusGeometry(7.3, 0.018, 10, 180),
  new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.14 })
);
orbitRing.rotation.x = Math.PI / 2.6;
orbitRing.rotation.z = 0.35;
scene.add(orbitRing);

const dishLat = THREE.MathUtils.degToRad(22);
const dishLon = THREE.MathUtils.degToRad(28);
const dishAnchor = latLonToVector(dishLat, dishLon, 3);

const {
  group: stationGroup,
  azimuthPivot,
  elevationPivot,
  receiverNode,
} = createGroundAntenna();
stationGroup.position.copy(dishAnchor);
stationGroup.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dishAnchor.clone().normalize());
earthGroup.add(stationGroup);

const satellitePivot = new THREE.Group();
scene.add(satellitePivot);
satellitePivot.rotation.x = Math.PI / 2.6;
satellitePivot.rotation.z = 0.35;

const { group: satelliteGroup, leftPanel, rightPanel } = createSatellite();
satelliteGroup.position.set(7.3, 0, 0);
satellitePivot.add(satelliteGroup);

const beamMaterial = new THREE.LineBasicMaterial({ color: 0x6ae5ff, transparent: true, opacity: 0.9 });
const beamGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
const beamLine = new THREE.Line(beamGeometry, beamMaterial);
scene.add(beamLine);

const ghostBeam = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
  new THREE.LineDashedMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.32,
    dashSize: 0.28,
    gapSize: 0.14,
  })
);
scene.add(ghostBeam);

const starPositions = [];
for (let i = 0; i < 1600; i += 1) {
  const radius = THREE.MathUtils.randFloat(18, 70);
  const theta = THREE.MathUtils.randFloat(0, Math.PI * 2);
  const phi = Math.acos(THREE.MathUtils.randFloatSpread(2));
  starPositions.push(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}
const stars = new THREE.Points(
  new THREE.BufferGeometry(),
  new THREE.PointsMaterial({ color: 0xe1efff, size: 0.12, sizeAttenuation: true })
);
stars.geometry.setAttribute("position", new THREE.Float32BufferAttribute(starPositions, 3));
scene.add(stars);

const tmpVecA = new THREE.Vector3();
const tmpVecB = new THREE.Vector3();
const clock = new THREE.Clock();

let sim = resetState();
let running = false;
let accumulator = 0;
let selectedAction = "hold";
let lastPhaseText = "";
let finalLogged = false;

function resetState() {
  return {
    t: 0,
    azError: 1.6,
    elError: -0.8,
    freqOffset: 280,
    polMode: 0,
    bandwidthFactor: 1,
    noiseTemp: 150,
    locked: true,
    snr: 14,
    reward: 0,
    totalReward: 0,
    lastAction: "hold",
    slew: 0,
    ended: false,
    success: false,
    log: ["Episode loaded: NOAA-19 over Goldstone, 180 second compressed pass."],
  };
}

function ephemerisAt(t) {
  const p = Math.min(1, Math.max(0, t / (PASS_DURATION - 1)));
  return {
    az: (214 + 116 * p) % 360,
    el: Math.max(4, episode.maxElevation * Math.sin(Math.PI * p)),
  };
}

function activeAnomalies(t) {
  return episode.anomalies.filter((a) => t >= a.onset && t < a.onset + a.duration);
}

function pointingLoss(azError, elError) {
  const sigma = 1.5 / 2.355;
  const error = Math.hypot(azError, elError);
  return Math.exp(-(error ** 2) / (2 * sigma ** 2));
}

function frequencyLoss(freqOffset) {
  const x = freqOffset / 1000000;
  if (Math.abs(x) < 1e-9) return 1;
  return (Math.sin(Math.PI * x) / (Math.PI * x)) ** 2;
}

function polarizationLoss(mode, trueMode) {
  if (mode === trueMode) return 1;
  const circular = new Set([2, 3]);
  const linear = new Set([0, 1]);
  if (circular.has(mode) && circular.has(trueMode)) return 0.04;
  if (linear.has(mode) && linear.has(trueMode)) return 0.04;
  return 0.5;
}

function computeSnr(state, anomalies) {
  const ephem = ephemerisAt(state.t);
  const truePol = anomalies.find((a) => a.kind === "polarization")?.truePolarization ?? 0;
  const baseByElevation = 15 + 13 * Math.sin(Math.PI * Math.min(1, state.t / PASS_DURATION));
  const pointingDb = 10 * Math.log10(Math.max(pointingLoss(state.azError, state.elError), 1e-5));
  const freqDb = 10 * Math.log10(Math.max(frequencyLoss(state.freqOffset), 1e-5));
  const polDb = 10 * Math.log10(Math.max(polarizationLoss(state.polMode, truePol), 1e-5));
  const noiseDb = 10 * Math.log10(state.noiseTemp / state.bandwidthFactor / 150);
  const horizonDb = ephem.el < 8 ? -2 : 0;
  return baseByElevation + pointingDb + freqDb + polDb - noiseDb + horizonDb;
}

function executeAction(action) {
  if (sim.ended) return;

  const before = { az: sim.azError, el: sim.elError };
  sim.slew = 0;
  sim.lastAction = action;

  const applyPointing = (axis, amount) => {
    if (axis === "az") sim.azError -= amount;
    if (axis === "el") sim.elError -= amount;
    sim.slew = Math.abs(amount);
  };

  if (action === "nudge_az_pos_small") applyPointing("az", 0.1);
  if (action === "nudge_az_neg_small") applyPointing("az", -0.1);
  if (action === "nudge_az_pos_medium") applyPointing("az", 0.5);
  if (action === "nudge_az_neg_medium") applyPointing("az", -0.5);
  if (action === "nudge_az_pos_large") applyPointing("az", 2);
  if (action === "nudge_az_neg_large") applyPointing("az", -2);
  if (action === "nudge_el_pos_small") applyPointing("el", 0.1);
  if (action === "nudge_el_neg_small") applyPointing("el", -0.1);
  if (action === "nudge_el_pos_medium") applyPointing("el", 0.5);
  if (action === "nudge_el_neg_medium") applyPointing("el", -0.5);
  if (action === "nudge_el_pos_large") applyPointing("el", 2);
  if (action === "nudge_el_neg_large") applyPointing("el", -2);

  if (action === "snap_to_ephemeris") {
    sim.azError = 0;
    sim.elError = 0;
    sim.slew = 5;
  }
  if (action === "shift_freq_pos_fine") sim.freqOffset += 10;
  if (action === "shift_freq_neg_fine") sim.freqOffset -= 10;
  if (action === "shift_freq_pos_med") sim.freqOffset += 100;
  if (action === "shift_freq_neg_med") sim.freqOffset -= 100;
  if (action === "shift_freq_pos_coarse") sim.freqOffset += 1000;
  if (action === "shift_freq_neg_coarse") sim.freqOffset -= 1000;
  if (action === "cycle_polarization") sim.polMode = (sim.polMode + 1) % 4;
  if (action === "narrow_bandwidth") sim.bandwidthFactor = Math.max(0.125, sim.bandwidthFactor * 0.5);
  if (action === "widen_bandwidth") sim.bandwidthFactor = Math.min(4, sim.bandwidthFactor * 2);

  if (action === "request_handoff") {
    if (sim.t / PASS_DURATION >= 0.8) {
      sim.ended = true;
      sim.success = sim.locked;
      sim.log.unshift(`t=${sim.t}: handoff ${sim.locked ? "accepted" : "completed after weak lock"}.`);
      return;
    }
    sim.reward -= 5;
    sim.totalReward -= 5;
    sim.log.unshift(`t=${sim.t}: premature handoff rejected.`);
  }

  if (action !== "hold" && action !== "request_handoff") {
    const moved = Math.hypot(sim.azError - before.az, sim.elError - before.el);
    if (moved > 0 || action.includes("freq") || action.includes("bandwidth") || action.includes("polarization")) {
      sim.log.unshift(`t=${sim.t}: ${action.replaceAll("_", " ")}.`);
    }
  }
}

function advanceEpisode() {
  if (sim.ended) return;

  executeAction(selectedAction);
  if (sim.ended) {
    renderHud();
    return;
  }

  const anomalies = activeAnomalies(sim.t);
  anomalies.forEach((anomaly) => {
    if (anomaly.kind === "drift") {
      sim.azError += anomaly.azRate;
      sim.elError += anomaly.elRate;
    }
  });

  const next = ephemerisAt(Math.min(PASS_DURATION - 1, sim.t + 1));
  const now = ephemerisAt(sim.t);
  const azDelta = ((next.az - now.az + 180) % 360) - 180;
  const elDelta = next.el - now.el;
  sim.azError += TRACKING_LEAK * azDelta;
  sim.elError += TRACKING_LEAK * elDelta;

  sim.snr = computeSnr(sim, anomalies);
  sim.locked = sim.snr > LOCK_MIN;
  sim.reward = sim.snr >= SNR_THRESHOLD ? 1 : Math.max(-10, (sim.snr - LOCK_MIN) / (SNR_THRESHOLD - LOCK_MIN));
  if (!sim.locked) sim.reward = -10;
  sim.reward -= sim.slew * 0.1;
  if (selectedAction.includes("freq") || selectedAction === "cycle_polarization" || selectedAction.includes("bandwidth")) {
    sim.reward -= 0.05;
  }
  sim.totalReward += sim.reward;
  sim.t += 1;

  if (sim.t >= PASS_DURATION) {
    sim.ended = true;
    sim.success = sim.locked;
  }

  logEpisodeEvents(anomalies);
  renderHud();
}

function currentPhase() {
  return PHASES.reduce((current, phase) => (sim.t >= phase.at ? phase : current), PHASES[0]);
}

function logEpisodeEvents(anomalies) {
  const phase = currentPhase().text;
  if (phase !== lastPhaseText) {
    lastPhaseText = phase;
    sim.log.unshift(`t=${sim.t}: ${phase}`);
  }
  anomalies.forEach((anomaly) => {
    const marker = `t=${anomaly.onset}: ${anomaly.kind}`;
    if (sim.t === anomaly.onset && !sim.log.some((entry) => entry.includes(marker))) {
      sim.log.unshift(`${marker} anomaly is now active.`);
    }
  });
  if (sim.ended && !finalLogged) {
    finalLogged = true;
    sim.log.unshift(`Episode ${sim.success ? "complete" : "ended"}: final score ${Math.round(sim.totalReward)}.`);
  }
  sim.log = sim.log.slice(0, 7);
}

function renderHud() {
  const phase = currentPhase().text;
  ui.time.textContent = `${Math.min(sim.t, PASS_DURATION)} / ${PASS_DURATION}`;
  ui.phase.textContent = sim.ended ? (sim.success ? "Episode complete" : "Episode ended") : phase;
  ui.snr.textContent = `${sim.snr.toFixed(1)} dB`;
  ui.lock.textContent = sim.locked ? "locked" : "lost";
  ui.lock.dataset.state = sim.locked ? "good" : "bad";
  ui.reward.textContent = `${sim.reward >= 0 ? "+" : ""}${sim.reward.toFixed(2)}`;
  ui.az.textContent = `${sim.azError >= 0 ? "+" : ""}${sim.azError.toFixed(2)} deg`;
  ui.el.textContent = `${sim.elError >= 0 ? "+" : ""}${sim.elError.toFixed(2)} deg`;
  ui.freq.textContent = `${sim.freqOffset >= 0 ? "+" : ""}${Math.round(sim.freqOffset)} Hz`;
  ui.pol.textContent = POLARIZATIONS[sim.polMode];
  ui.bandwidth.textContent = `${sim.bandwidthFactor.toFixed(2)}x`;
  ui.action.textContent = selectedAction.replaceAll("_", " ");
  ui.score.textContent = `${Math.round(sim.totalReward)}`;
  ui.run.textContent = running ? "Pause" : "Run";
  ui.eventLog.innerHTML = sim.log.map((entry) => `<li>${entry}</li>`).join("");

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.action === selectedAction);
    button.disabled = sim.ended;
  });
}

function updateBeams() {
  const dishWorld = receiverNode.getWorldPosition(tmpVecA);
  const satWorld = satelliteGroup.getWorldPosition(tmpVecB);
  beamLine.geometry.setFromPoints([dishWorld, satWorld]);

  const stationWorld = stationGroup.getWorldPosition(new THREE.Vector3());
  const predicted = stationWorld.clone().normalize().multiplyScalar(stationWorld.length() + 0.18);
  ghostBeam.geometry.setFromPoints([predicted, satWorld]);
  ghostBeam.computeLineDistances();

  const health = THREE.MathUtils.clamp((sim.snr - LOCK_MIN) / (SNR_THRESHOLD + 10), 0.05, 1);
  beamMaterial.opacity = sim.locked ? 0.22 + health * 0.72 : 0.08;
  beamMaterial.color.set(sim.locked ? 0x6ae5ff : 0xff5c7c);
  receiverNode.scale.setScalar(sim.locked ? 1 + health * 0.55 : 0.65 + Math.sin(clock.elapsedTime * 8) * 0.08);
}

function animate() {
  const delta = clock.getDelta();
  accumulator += delta;

  if (running && accumulator >= 0.72) {
    accumulator = 0;
    advanceEpisode();
    if (sim.ended) running = false;
  }

  const progress = Math.min(1, sim.t / PASS_DURATION);
  earth.rotation.y += delta * 0.035;
  cloudBand.rotation.y += delta * 0.08;
  atmosphere.rotation.y += delta * 0.04;
  satellitePivot.rotation.y = progress * Math.PI * 1.38 - 0.42;
  satelliteGroup.rotation.y += delta * 0.9;
  leftPanel.rotation.z = Math.sin(clock.elapsedTime * 0.8) * 0.08;
  rightPanel.rotation.z = -leftPanel.rotation.z;
  azimuthPivot.rotation.y = THREE.MathUtils.degToRad(18 - sim.azError * 8);
  elevationPivot.rotation.z = THREE.MathUtils.degToRad(-32 + sim.elError * 7);
  satelliteGroup.position.y = Math.sin(progress * Math.PI) * 0.72 + Math.sin(clock.elapsedTime * 0.55) * 0.12;
  updateBeams();

  receiverNode.material.emissiveIntensity = sim.locked ? 1.2 + Math.sin(clock.elapsedTime * 2.4) * 0.25 : 0.25;

  orbit.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

function renderActions() {
  ui.actions.innerHTML = ACTIONS.map(
    ([action, label]) => `<button type="button" data-action="${action}" title="${action}">${label}</button>`
  ).join("");
}

ui.actions.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action]");
  if (!button || sim.ended) return;
  selectedAction = button.dataset.action;
  renderHud();
});

ui.run.addEventListener("click", () => {
  if (sim.ended) return;
  running = !running;
  renderHud();
});

ui.step.addEventListener("click", () => {
  running = false;
  advanceEpisode();
});

ui.reset.addEventListener("click", () => {
  sim = resetState();
  selectedAction = "hold";
  running = false;
  accumulator = 0;
  lastPhaseText = "";
  finalLogged = false;
  renderHud();
});

window.addEventListener("keydown", (event) => {
  if (event.target.closest("button")) return;
  if (event.code === "Space") {
    event.preventDefault();
    if (!sim.ended) running = !running;
  }
  if (event.key === ".") {
    advanceEpisode();
  }
});

window.addEventListener("resize", () => {
  camera.aspect = root.clientWidth / root.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(root.clientWidth, root.clientHeight);
});

renderActions();
renderHud();
animate();
