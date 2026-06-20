import * as THREE from "three";

export function createGroundAntenna() {
  const group = new THREE.Group();

  const metal = new THREE.MeshStandardMaterial({
    color: 0xb9c7d4,
    roughness: 0.32,
    metalness: 0.78,
  });
  const darkMetal = new THREE.MeshStandardMaterial({
    color: 0x4f6576,
    roughness: 0.42,
    metalness: 0.72,
  });
  const signalMaterial = new THREE.MeshStandardMaterial({
    color: 0x7af7c4,
    emissive: 0x1f8f75,
    emissiveIntensity: 1.45,
    roughness: 0.22,
    metalness: 0.2,
  });

  const basePad = new THREE.Mesh(new THREE.CylinderGeometry(0.48, 0.56, 0.12, 40), darkMetal);
  basePad.position.y = 0.06;
  group.add(basePad);

  const pedestal = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.22, 0.82, 24), darkMetal);
  pedestal.position.y = 0.5;
  group.add(pedestal);

  const azimuthPivot = new THREE.Group();
  azimuthPivot.position.y = 0.94;
  group.add(azimuthPivot);

  const turntable = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.16, 32), metal);
  turntable.rotation.x = Math.PI / 2;
  azimuthPivot.add(turntable);

  const yoke = new THREE.Group();
  azimuthPivot.add(yoke);

  const leftFork = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.62, 0.08), darkMetal);
  leftFork.position.set(-0.46, 0.18, 0);
  yoke.add(leftFork);

  const rightFork = leftFork.clone();
  rightFork.position.x = 0.46;
  yoke.add(rightFork);

  const crossbar = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 1.04, 18), darkMetal);
  crossbar.rotation.z = Math.PI / 2;
  crossbar.position.y = 0.48;
  yoke.add(crossbar);

  const elevationPivot = new THREE.Group();
  elevationPivot.position.y = 0.5;
  yoke.add(elevationPivot);

  const dish = new THREE.Mesh(
    new THREE.SphereGeometry(0.78, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2.25),
    metal
  );
  dish.rotation.x = Math.PI / 2;
  dish.scale.z = 0.42;
  elevationPivot.add(dish);

  const rim = new THREE.Mesh(new THREE.TorusGeometry(0.79, 0.025, 12, 72), darkMetal);
  rim.rotation.x = Math.PI / 2;
  elevationPivot.add(rim);

  const rearHub = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.18, 0.18, 24), darkMetal);
  rearHub.rotation.x = Math.PI / 2;
  rearHub.position.z = -0.22;
  elevationPivot.add(rearHub);

  const feedMast = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.86, 10), darkMetal);
  feedMast.rotation.z = THREE.MathUtils.degToRad(55);
  feedMast.position.set(0.31, 0.3, 0);
  elevationPivot.add(feedMast);

  const feedHorn = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.24, 28), signalMaterial);
  feedHorn.rotation.z = THREE.MathUtils.degToRad(-35);
  feedHorn.position.set(0.56, 0.54, 0);
  elevationPivot.add(feedHorn);

  [-0.32, 0.32].forEach((x) => {
    const strut = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, 0.9, 8), darkMetal);
    strut.position.set(x, 0.22, 0.02);
    strut.rotation.z = x < 0 ? THREE.MathUtils.degToRad(-34) : THREE.MathUtils.degToRad(34);
    elevationPivot.add(strut);
  });

  const receiverNode = new THREE.Mesh(new THREE.SphereGeometry(0.085, 20, 20), signalMaterial);
  receiverNode.position.set(0.59, 0.6, 0);
  elevationPivot.add(receiverNode);

  const groundMarker = new THREE.Mesh(
    new THREE.CylinderGeometry(0.28, 0.34, 0.035, 32),
    new THREE.MeshBasicMaterial({ color: 0xffce73 })
  );
  groundMarker.position.y = -0.02;
  group.add(groundMarker);

  return { group, azimuthPivot, elevationPivot, receiverNode };
}
