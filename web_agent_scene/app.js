import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { createEarth, latLonToVector } from "./models/earth.js?v=blue-green-earth-1";
import { createGroundAntenna } from "./models/ground-antenna.js";
import { createSatellite } from "./models/satellite.js";

const POLARIZATIONS = ["H", "V", "RHCP", "LHCP"];
const PASS_DURATION = 240;
const SNR_THRESHOLD = 10;
const LOCK_MIN = 5;
const TRACKING_LEAK = 0.055;
const BASE_NOISE_TEMP = 150;
const EARTH_RADIUS = 3;
const HORIZON_EPSILON = 0.04;
const ANOMALY_COLORS = {
  drift: 0xffce73,
  rfi: 0xff4f8b,
  polarization: 0xb58cff,
  multipath: 0x7af7c4,
  hardware: 0xff7b45,
};
const PHASES = [
  { at: 0, text: "Acquire the pass. The agent slews onto the predicted track." },
  { at: 24, text: "Nominal tracking. The receiver holds lock while the satellite moves." },
  { at: 50, text: "Anomaly: polarization rotation. The agent probes, then cycles polarization." },
  { at: 86, text: "Anomaly: antenna drift. The agent corrects pointing before lock drops." },
  { at: 126, text: "Anomaly: RFI burst. The agent shifts frequency and tightens bandwidth." },
  { at: 164, text: "Anomaly: multipath fade. The agent rides out the reflected signal." },
  { at: 196, text: "Anomaly: hardware noise. The agent narrows bandwidth to preserve lock." },
  { at: 222, text: "Handoff window open. The pass transfers to the next ground station." },
];

const episode = {
  satellite: "NOAA-19",
  maxElevation: 54,
  anomalies: [
    { kind: "polarization", onset: 50, duration: 26, truePolarization: 2 },
    { kind: "drift", onset: 86, duration: 32, azRate: 0.075, elRate: -0.045 },
    { kind: "rfi", onset: 126, duration: 28, severity: 0.9 },
    { kind: "multipath", onset: 164, duration: 28, severity: 0.85, phase: 0.7 },
    { kind: "hardware", onset: 196, duration: 28, severity: 0.75 },
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
};

const root = document.getElementById("scene-root");
const sceneLabels = {
  orbitData: document.querySelector("[data-scene-label='orbit-data']"),
  computedTrack: document.querySelector("[data-scene-label='computed-track']"),
  drift: document.querySelector("[data-scene-label='drift']"),
  polarization: document.querySelector("[data-scene-label='polarization']"),
  rfi: document.querySelector("[data-scene-label='rfi']"),
  multipath: document.querySelector("[data-scene-label='multipath']"),
  hardware: document.querySelector("[data-scene-label='hardware']"),
};

document.querySelectorAll("[data-panel]").forEach((panel) => {
  const panelName = panel.dataset.panel;
  const toggle = panel.querySelector("[data-panel-toggle]");
  if (!panelName || !toggle) return;

  const storageKey = `satellite-demo-panel-${panelName}`;
  const applyPanelState = (isCollapsed) => {
    panel.classList.toggle("is-collapsed", isCollapsed);
    toggle.setAttribute("aria-expanded", String(!isCollapsed));
    toggle.setAttribute("aria-label", `${isCollapsed ? "Expand" : "Collapse"} ${panelName} panel`);
    toggle.querySelector("span").textContent = isCollapsed ? "+" : "−";
  };

  applyPanelState(localStorage.getItem(storageKey) === "collapsed");

  toggle.addEventListener("click", () => {
    const isCollapsed = !panel.classList.contains("is-collapsed");
    applyPanelState(isCollapsed);
    localStorage.setItem(storageKey, isCollapsed ? "collapsed" : "expanded");
  });
});

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

const satelliteOrbit = new THREE.Group();
satellitePivot.add(satelliteOrbit);

const { group: satelliteGroup, leftPanel, rightPanel } = createSatellite();
satelliteGroup.position.set(7.3, 0, 0);
satelliteOrbit.add(satelliteGroup);

const beamMaterial = new THREE.LineBasicMaterial({ color: 0x6ae5ff, transparent: true, opacity: 0.9 });
const beamGeometry = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
const beamLine = new THREE.Line(beamGeometry, beamMaterial);
scene.add(beamLine);

const signalPulseMaterial = new THREE.MeshBasicMaterial({
  color: 0x8ff3ff,
  transparent: true,
  opacity: 0.9,
});
const signalPulses = Array.from({ length: 10 }, (_, index) => {
  const pulse = new THREE.Mesh(new THREE.SphereGeometry(0.055, 16, 16), signalPulseMaterial.clone());
  pulse.userData.offset = index / 10;
  scene.add(pulse);
  return pulse;
});

const multipathBeamMaterial = new THREE.LineBasicMaterial({
  color: ANOMALY_COLORS.multipath,
  transparent: true,
  opacity: 0,
});
const multipathBeam = new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()]),
  multipathBeamMaterial
);
scene.add(multipathBeam);

const rfiMaterial = new THREE.MeshBasicMaterial({
  color: ANOMALY_COLORS.rfi,
  transparent: true,
  opacity: 0,
  depthWrite: false,
});
const rfiBursts = Array.from({ length: 18 }, (_, index) => {
  const burst = new THREE.Mesh(new THREE.BoxGeometry(0.032, 0.032, 0.62), rfiMaterial.clone());
  burst.userData.offset = index / 18;
  burst.visible = false;
  scene.add(burst);
  return burst;
});

const hardwareGlowMaterial = new THREE.MeshBasicMaterial({
  color: ANOMALY_COLORS.hardware,
  transparent: true,
  opacity: 0,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
});
const hardwareGlow = new THREE.Mesh(new THREE.SphereGeometry(0.34, 24, 24), hardwareGlowMaterial);
hardwareGlow.visible = false;
scene.add(hardwareGlow);

const hardwareLight = new THREE.PointLight(ANOMALY_COLORS.hardware, 0, 4);
scene.add(hardwareLight);

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
const tmpVecC = new THREE.Vector3();
const satelliteLabelOffset = new THREE.Vector3(0, 0.7, 0);
const trackLabelAnchor = new THREE.Vector3(-3.4, 6.45, 0);
const clock = new THREE.Clock();

let sim = resetState();
let accumulator = 0;
let lastPhaseText = "";
let finalLogged = false;

function segmentIntersectsEarth(start, end) {
  const segment = end.clone().sub(start);
  const lengthSq = segment.lengthSq();
  if (lengthSq === 0) return false;

  const closestT = THREE.MathUtils.clamp(-start.dot(segment) / lengthSq, 0, 1);
  const closestPoint = start.clone().add(segment.multiplyScalar(closestT));
  return closestT > HORIZON_EPSILON && closestT < 1 - HORIZON_EPSILON && closestPoint.length() < EARTH_RADIUS;
}

function hasStationLineOfSight(stationWorld, dishWorld, satWorld) {
  const stationNormal = stationWorld.clone().normalize();
  const satFromStation = satWorld.clone().sub(stationWorld);
  return satFromStation.dot(stationNormal) > 0 && !segmentIntersectsEarth(dishWorld, satWorld);
}

function resetState() {
  return {
    t: 0,
    azError: 1.6,
    elError: -0.8,
    freqOffset: 280,
    polMode: 0,
    bandwidthFactor: 1,
    noiseTemp: BASE_NOISE_TEMP,
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

function anomalyProgress(anomaly, t) {
  return THREE.MathUtils.clamp((t - anomaly.onset) / Math.max(1, anomaly.duration), 0, 1);
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
  const rfi = anomalies.find((a) => a.kind === "rfi");
  const multipath = anomalies.find((a) => a.kind === "multipath");
  const baseByElevation = 15 + 13 * Math.sin(Math.PI * Math.min(1, state.t / PASS_DURATION));
  const pointingDb = 10 * Math.log10(Math.max(pointingLoss(state.azError, state.elError), 1e-5));
  const freqDb = 10 * Math.log10(Math.max(frequencyLoss(state.freqOffset), 1e-5));
  const polDb = 10 * Math.log10(Math.max(polarizationLoss(state.polMode, truePol), 1e-5));
  const noiseDb = 10 * Math.log10(state.noiseTemp / state.bandwidthFactor / BASE_NOISE_TEMP);
  const rfiEscape = THREE.MathUtils.clamp(Math.abs(state.freqOffset) / 1400, 0.12, 1);
  const rfiDb = rfi ? -8.5 * (rfi.severity ?? 1) * (1 - rfiEscape) * Math.sqrt(state.bandwidthFactor) : 0;
  const multipathWave = multipath
    ? (1 + Math.sin((multipath.phase ?? 0) + (state.t - multipath.onset) * 0.42)) / 2
    : 0;
  const multipathDb = multipath ? -1.2 - 5.2 * (multipath.severity ?? 1) * multipathWave : 0;
  const horizonDb = ephem.el < 8 ? -2 : 0;
  return baseByElevation + pointingDb + freqDb + polDb + rfiDb + multipathDb - noiseDb + horizonDb;
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

function chooseScriptedAction() {
  const active = activeAnomalies(sim.t);
  const hasPolarizationAnomaly = active.some((anomaly) => anomaly.kind === "polarization");
  const hasRfiAnomaly = active.some((anomaly) => anomaly.kind === "rfi");
  const hasHardwareAnomaly = active.some((anomaly) => anomaly.kind === "hardware");

  if (sim.t / PASS_DURATION >= 0.82) return "request_handoff";
  if (sim.t === 0) return "snap_to_ephemeris";
  if (hasPolarizationAnomaly && sim.t === 50) return "hold";
  if (hasPolarizationAnomaly && sim.polMode !== 2) return "cycle_polarization";
  if (hasRfiAnomaly && Math.abs(sim.freqOffset) < 1500) return "shift_freq_pos_coarse";
  if ((hasRfiAnomaly || hasHardwareAnomaly) && sim.bandwidthFactor > 0.5) return "narrow_bandwidth";

  const axis = Math.abs(sim.azError) >= Math.abs(sim.elError) ? "az" : "el";
  const error = axis === "az" ? sim.azError : sim.elError;
  const magnitude = Math.abs(error);
  if (magnitude > 1.2) return `nudge_${axis}_${error > 0 ? "pos" : "neg"}_large`;
  if (magnitude > 0.35) return `nudge_${axis}_${error > 0 ? "pos" : "neg"}_medium`;
  if (magnitude > 0.12) return `nudge_${axis}_${error > 0 ? "pos" : "neg"}_small`;
  if (!hasRfiAnomaly && Math.abs(sim.freqOffset) > 120) return sim.freqOffset > 0 ? "shift_freq_neg_med" : "shift_freq_pos_med";
  if (!hasRfiAnomaly && !hasHardwareAnomaly && sim.bandwidthFactor !== 1) {
    return sim.bandwidthFactor < 1 ? "widen_bandwidth" : "narrow_bandwidth";
  }
  return "hold";
}

function advanceEpisode() {
  if (sim.ended) return;

  const action = chooseScriptedAction();
  executeAction(action);
  if (sim.ended) {
    renderHud();
    return;
  }

  const anomalies = activeAnomalies(sim.t);
  sim.noiseTemp = BASE_NOISE_TEMP;
  anomalies.forEach((anomaly) => {
    if (anomaly.kind === "drift") {
      sim.azError += anomaly.azRate;
      sim.elError += anomaly.elRate;
    }
    if (anomaly.kind === "hardware") {
      sim.noiseTemp += 360 * (anomaly.severity ?? 1);
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
  if (action.includes("freq") || action === "cycle_polarization" || action.includes("bandwidth")) {
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
  const active = activeAnomalies(sim.t);
  const activeKinds = new Set(active.map((anomaly) => anomaly.kind));
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
  ui.action.textContent = sim.lastAction.replaceAll("_", " ");
  ui.score.textContent = `${Math.round(sim.totalReward)}`;
  ui.eventLog.innerHTML = sim.log.map((entry) => `<li>${entry}</li>`).join("");
  document.body.dataset.anomaly = active[0]?.kind ?? "none";
  ui.az.dataset.state = activeKinds.has("drift") ? "warn" : "normal";
  ui.el.dataset.state = activeKinds.has("drift") ? "warn" : "normal";
  ui.freq.dataset.state = activeKinds.has("rfi") ? "bad" : "normal";
  ui.pol.dataset.state = activeKinds.has("polarization") ? "warn" : "normal";
  ui.bandwidth.dataset.state = activeKinds.has("rfi") || activeKinds.has("hardware") ? "warn" : "normal";
  ui.snr.dataset.state = sim.snr < SNR_THRESHOLD ? "bad" : "good";
}

function updateBeams() {
  const dishWorld = receiverNode.getWorldPosition(tmpVecA);
  const satWorld = satelliteGroup.getWorldPosition(tmpVecB);
  const stationWorld = stationGroup.getWorldPosition(tmpVecC);
  const hasLineOfSight = hasStationLineOfSight(stationWorld, dishWorld, satWorld);
  const active = activeAnomalies(sim.t);
  const activeKinds = new Set(active.map((anomaly) => anomaly.kind));
  const beamDirection = satWorld.clone().sub(dishWorld).normalize();
  const side = new THREE.Vector3().crossVectors(beamDirection, camera.position.clone().sub(dishWorld).normalize());
  if (side.lengthSq() < 0.001) side.set(0, 1, 0);
  side.normalize();
  const up = new THREE.Vector3().crossVectors(side, beamDirection).normalize();
  beamLine.geometry.setFromPoints([dishWorld, satWorld]);

  const health = THREE.MathUtils.clamp((sim.snr - LOCK_MIN) / (SNR_THRESHOLD + 10), 0.05, 1);
  const primaryAnomaly = active[0]?.kind;
  beamLine.visible = hasLineOfSight;
  beamMaterial.opacity = hasLineOfSight ? (sim.locked ? 0.22 + health * 0.72 : 0.08) : 0;
  beamMaterial.color.set(primaryAnomaly ? ANOMALY_COLORS[primaryAnomaly] : sim.locked ? 0x6ae5ff : 0xff5c7c);

  signalPulses.forEach((pulse) => {
    if (!hasLineOfSight) {
      pulse.visible = false;
      return;
    }

    const travel = (clock.elapsedTime * (sim.locked ? 0.38 + health * 0.62 : 0.16) + pulse.userData.offset) % 1;
    const fade = Math.sin(travel * Math.PI);
    const twist = clock.elapsedTime * 4.2 + pulse.userData.offset * Math.PI * 2;
    const polarizationOffset = activeKinds.has("polarization")
      ? side.clone().multiplyScalar(Math.cos(twist) * 0.22 * fade).add(up.clone().multiplyScalar(Math.sin(twist) * 0.22 * fade))
      : new THREE.Vector3();
    pulse.position.lerpVectors(dishWorld, satWorld, travel).add(polarizationOffset);
    pulse.scale.setScalar(sim.locked ? 0.75 + fade * (0.8 + health * 0.9) : 0.45 + fade * 0.35);
    pulse.material.opacity = sim.locked ? fade * (0.28 + health * 0.68) : fade * 0.18;
    pulse.material.color.set(primaryAnomaly ? ANOMALY_COLORS[primaryAnomaly] : sim.locked ? 0x8ff3ff : 0xff5c7c);
    pulse.visible = pulse.material.opacity > 0.03;
  });

  const multipath = active.find((anomaly) => anomaly.kind === "multipath");
  if (multipath && hasLineOfSight) {
    const progress = anomalyProgress(multipath, sim.t);
    const reflection = dishWorld.clone().lerp(satWorld, 0.48);
    reflection.add(up.clone().multiplyScalar(-1.0 - 0.36 * Math.sin(clock.elapsedTime * 2.4)));
    reflection.add(side.clone().multiplyScalar(0.42 * Math.sin(clock.elapsedTime * 1.6)));
    multipathBeam.geometry.setFromPoints([dishWorld, reflection, satWorld]);
    multipathBeamMaterial.opacity = (0.18 + 0.32 * Math.sin(clock.elapsedTime * 5.4) ** 2) * Math.sin(progress * Math.PI);
  } else {
    multipathBeamMaterial.opacity = 0;
  }

  rfiBursts.forEach((burst) => {
    const rfi = active.find((anomaly) => anomaly.kind === "rfi");
    burst.visible = Boolean(rfi) && hasLineOfSight;
    if (!rfi) return;
    const travel = (clock.elapsedTime * 1.85 + burst.userData.offset) % 1;
    const jitter = Math.sin(clock.elapsedTime * 20 + burst.userData.offset * 44);
    burst.position.lerpVectors(dishWorld, satWorld, travel);
    burst.position.add(side.clone().multiplyScalar(0.7 + jitter * 0.34));
    burst.position.add(up.clone().multiplyScalar(Math.cos(clock.elapsedTime * 17 + burst.userData.offset * 21) * 0.28));
    burst.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), side);
    burst.scale.set(1, 1, 0.4 + Math.abs(jitter) * 1.6);
    burst.material.opacity = 0.18 + Math.abs(jitter) * 0.46;
  });

  const hardware = active.find((anomaly) => anomaly.kind === "hardware");
  hardwareGlow.visible = Boolean(hardware);
  if (hardware) {
    const pulse = 0.5 + 0.5 * Math.sin(clock.elapsedTime * 8);
    hardwareGlow.position.copy(dishWorld);
    hardwareGlow.scale.setScalar(0.9 + pulse * 0.42);
    hardwareGlow.material.opacity = 0.24 + pulse * 0.26;
    hardwareLight.position.copy(dishWorld);
    hardwareLight.intensity = 0.9 + pulse * 1.4;
  } else {
    hardwareGlow.material.opacity = 0;
    hardwareLight.intensity = 0;
  }
}

function projectLabel(label, worldPosition, offsetX = 0, offsetY = -18) {
  if (!label) return;

  const projected = tmpVecC.copy(worldPosition).project(camera);
  const isVisible = projected.z > -1 && projected.z < 1;
  label.classList.toggle("is-visible", isVisible);
  if (!isVisible) return;

  const x = (projected.x * 0.5 + 0.5) * root.clientWidth;
  const y = (-projected.y * 0.5 + 0.5) * root.clientHeight;
  label.style.left = `${Math.round(x + offsetX)}px`;
  label.style.top = `${Math.round(y + offsetY)}px`;
}

function setEffectLabel(kind, visible, worldPosition, offsetX = 0, offsetY = -18) {
  const label = sceneLabels[kind];
  if (!label) return;
  if (!visible) {
    label.classList.remove("is-visible");
    return;
  }
  projectLabel(label, worldPosition, offsetX, offsetY);
}

function updateSceneLabels() {
  const satelliteWorld = satelliteGroup.getWorldPosition(tmpVecA).add(satelliteLabelOffset);
  projectLabel(sceneLabels.orbitData, satelliteWorld, 46, -22);

  const trackAnchor = tmpVecB.copy(trackLabelAnchor).applyEuler(orbitRing.rotation);
  projectLabel(sceneLabels.computedTrack, trackAnchor, -24, 18);

  const active = activeAnomalies(sim.t);
  const activeKinds = new Set(active.map((anomaly) => anomaly.kind));
  const dishWorld = receiverNode.getWorldPosition(new THREE.Vector3());
  const satWorld = satelliteGroup.getWorldPosition(new THREE.Vector3());
  const beamDirection = satWorld.clone().sub(dishWorld).normalize();
  const side = new THREE.Vector3().crossVectors(beamDirection, camera.position.clone().sub(dishWorld).normalize());
  if (side.lengthSq() < 0.001) side.set(0, 1, 0);
  side.normalize();
  const up = new THREE.Vector3().crossVectors(side, beamDirection).normalize();
  const beamMid = dishWorld.clone().lerp(satWorld, 0.55);

  setEffectLabel("drift", activeKinds.has("drift"), satWorld.clone().add(side.clone().multiplyScalar(0.7)), 24, -20);
  setEffectLabel("polarization", activeKinds.has("polarization"), beamMid.clone().add(up.clone().multiplyScalar(0.46)), 0, -24);
  setEffectLabel("rfi", activeKinds.has("rfi"), beamMid.clone().add(side.clone().multiplyScalar(1.0)), 18, -18);
  setEffectLabel(
    "multipath",
    activeKinds.has("multipath"),
    dishWorld.clone().lerp(satWorld, 0.48).add(up.clone().multiplyScalar(-1.15)),
    8,
    28
  );
  setEffectLabel("hardware", activeKinds.has("hardware"), dishWorld.clone().add(up.clone().multiplyScalar(0.56)), 24, -18);
}

function animate() {
  const delta = clock.getDelta();
  accumulator += delta;

  if (!sim.ended && accumulator >= 0.42) {
    accumulator = 0;
    advanceEpisode();
  }

  const progress = Math.min(1, sim.t / PASS_DURATION);
  earth.rotation.y += delta * 0.035;
  cloudBand.rotation.y += delta * 0.08;
  atmosphere.rotation.y += delta * 0.04;
  satelliteOrbit.rotation.z = progress * Math.PI * 1.38 - 0.42;
  satelliteGroup.rotation.y += delta * 0.9;
  leftPanel.rotation.z = Math.sin(clock.elapsedTime * 0.8) * 0.08;
  rightPanel.rotation.z = -leftPanel.rotation.z;
  azimuthPivot.rotation.y = THREE.MathUtils.degToRad(18 - sim.azError * 8);
  elevationPivot.rotation.z = THREE.MathUtils.degToRad(-32 + sim.elError * 7);
  satelliteGroup.position.x = 7.3 + Math.sin(clock.elapsedTime * 0.55) * 0.08;
  orbit.update();
  updateBeams();
  updateSceneLabels();

  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

window.addEventListener("resize", () => {
  camera.aspect = root.clientWidth / root.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(root.clientWidth, root.clientHeight);
});

renderHud();
animate();
