import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

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

const earthGroup = new THREE.Group();
scene.add(earthGroup);

const earth = new THREE.Mesh(
  new THREE.SphereGeometry(3, 64, 64),
  new THREE.MeshStandardMaterial({
    color: 0x1f68ad,
    roughness: 0.92,
    metalness: 0.02,
    emissive: 0x082238,
    emissiveIntensity: 0.45,
  })
);
earthGroup.add(earth);

const atmosphere = new THREE.Mesh(
  new THREE.SphereGeometry(3.14, 48, 48),
  new THREE.MeshBasicMaterial({
    color: 0x6ed7ff,
    transparent: true,
    opacity: 0.12,
    side: THREE.BackSide,
  })
);
earthGroup.add(atmosphere);

const cloudBand = new THREE.Mesh(
  new THREE.SphereGeometry(3.05, 32, 32),
  new THREE.MeshStandardMaterial({
    color: 0xeef8ff,
    transparent: true,
    opacity: 0.06,
  })
);
earthGroup.add(cloudBand);

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

const stationGroup = new THREE.Group();
stationGroup.position.copy(dishAnchor);
stationGroup.lookAt(dishAnchor.clone().multiplyScalar(2));
earthGroup.add(stationGroup);

const mount = new THREE.Mesh(
  new THREE.CylinderGeometry(0.11, 0.14, 0.9, 12),
  new THREE.MeshStandardMaterial({ color: 0x7f98ac, roughness: 0.55, metalness: 0.45 })
);
mount.position.y = 0.45;
stationGroup.add(mount);

const azimuthPivot = new THREE.Group();
azimuthPivot.position.y = 0.88;
stationGroup.add(azimuthPivot);

const elevationPivot = new THREE.Group();
azimuthPivot.add(elevationPivot);

const dish = new THREE.Mesh(
  new THREE.SphereGeometry(0.68, 32, 32, 0, Math.PI * 2, 0, Math.PI / 2.1),
  new THREE.MeshStandardMaterial({
    color: 0xd5e4f1,
    roughness: 0.25,
    metalness: 0.7,
    side: THREE.DoubleSide,
  })
);
dish.rotation.x = Math.PI / 2;
elevationPivot.add(dish);

const feedArm = new THREE.Mesh(
  new THREE.CylinderGeometry(0.028, 0.028, 0.62, 8),
  new THREE.MeshStandardMaterial({ color: 0x7ac6ff, metalness: 0.65, roughness: 0.28 })
);
feedArm.rotation.z = THREE.MathUtils.degToRad(62);
feedArm.position.set(0.22, 0.2, 0);
elevationPivot.add(feedArm);

const receiverNode = new THREE.Mesh(
  new THREE.SphereGeometry(0.09, 16, 16),
  new THREE.MeshStandardMaterial({ color: 0x7af7c4, emissive: 0x1f8f75, emissiveIntensity: 1.2 })
);
receiverNode.position.set(0.42, 0.36, 0);
elevationPivot.add(receiverNode);

const groundMarker = new THREE.Mesh(
  new THREE.SphereGeometry(0.14, 16, 16),
  new THREE.MeshBasicMaterial({ color: 0xffce73 })
);
groundMarker.position.copy(dishAnchor.clone().normalize().multiplyScalar(0.12));
stationGroup.add(groundMarker);

const satellitePivot = new THREE.Group();
scene.add(satellitePivot);
satellitePivot.rotation.x = Math.PI / 2.6;
satellitePivot.rotation.z = 0.35;

const satelliteGroup = new THREE.Group();
satelliteGroup.position.set(7.3, 0, 0);
satellitePivot.add(satelliteGroup);

const bus = new THREE.Mesh(
  new THREE.BoxGeometry(0.42, 0.42, 0.54),
  new THREE.MeshStandardMaterial({ color: 0xd9dde5, metalness: 0.88, roughness: 0.22 })
);
satelliteGroup.add(bus);

const panelGeo = new THREE.BoxGeometry(0.9, 0.04, 0.34);
const panelMat = new THREE.MeshStandardMaterial({ color: 0x386caa, emissive: 0x113964, emissiveIntensity: 0.75 });
const leftPanel = new THREE.Mesh(panelGeo, panelMat);
leftPanel.position.set(-0.68, 0, 0);
satelliteGroup.add(leftPanel);
const rightPanel = leftPanel.clone();
rightPanel.position.set(0.68, 0, 0);
satelliteGroup.add(rightPanel);

const dishGeo = new THREE.CylinderGeometry(0.03, 0.03, 0.46, 8);
const dishSupport = new THREE.Mesh(dishGeo, new THREE.MeshStandardMaterial({ color: 0x9cb2c5 }));
dishSupport.rotation.z = Math.PI / 2;
dishSupport.position.set(0, 0, 0.38);
satelliteGroup.add(dishSupport);

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

function latLonToVector(lat, lon, radius) {
  const x = radius * Math.cos(lat) * Math.cos(lon);
  const y = radius * Math.sin(lat);
  const z = radius * Math.cos(lat) * Math.sin(lon);
  return new THREE.Vector3(x, y, z);
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
