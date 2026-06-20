import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { createEarth, latLonToVector } from "./models/earth.js";
import { createGroundAntenna } from "./models/ground-antenna.js";
import { createSatellite } from "./models/satellite.js";

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
const groundNormal = latLonToVector(dishLat, dishLon, 3);
const dishAnchor = groundNormal.clone();

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

function updateBeams() {
  const dishWorld = receiverNode.getWorldPosition(tmpVecA);
  const satWorld = satelliteGroup.getWorldPosition(tmpVecB);
  beamLine.geometry.setFromPoints([dishWorld, satWorld]);

  const stationWorld = stationGroup.getWorldPosition(new THREE.Vector3());
  const predicted = stationWorld.clone().normalize().multiplyScalar(stationWorld.length() + 0.18);
  ghostBeam.geometry.setFromPoints([predicted, satWorld]);
  ghostBeam.computeLineDistances();
  beamMaterial.opacity = 0.82;
  receiverNode.scale.setScalar(1);
}

function animate() {
  const delta = clock.getDelta();
  earth.rotation.y += delta * 0.08;
  cloudBand.rotation.y += delta * 0.11;
  atmosphere.rotation.y += delta * 0.05;
  satellitePivot.rotation.y += delta * 0.34;
  satelliteGroup.rotation.y += delta * 0.9;
  leftPanel.rotation.z = Math.sin(clock.elapsedTime * 0.8) * 0.08;
  rightPanel.rotation.z = -leftPanel.rotation.z;
  azimuthPivot.rotation.y = THREE.MathUtils.degToRad(18);
  elevationPivot.rotation.z = THREE.MathUtils.degToRad(-32);
  updateBeams();

  receiverNode.material.emissiveIntensity = 1.6 + Math.sin(clock.elapsedTime * 2.4) * 0.2;
  satelliteGroup.position.y = Math.sin(clock.elapsedTime * 0.55) * 0.5;

  orbit.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

window.addEventListener("resize", () => {
  camera.aspect = root.clientWidth / root.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(root.clientWidth, root.clientHeight);
});

animate();
