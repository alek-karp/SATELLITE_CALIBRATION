import * as THREE from "three";

export function createEarth() {
  const group = new THREE.Group();

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(3, 96, 96),
    new THREE.MeshStandardMaterial({
      color: 0x1d6fb8,
      roughness: 0.88,
      metalness: 0.02,
      emissive: 0x071a2b,
      emissiveIntensity: 0.42,
    })
  );
  group.add(earth);

  const landMaterial = new THREE.MeshStandardMaterial({
    color: 0x2c9a62,
    roughness: 0.95,
    metalness: 0.01,
    emissive: 0x06180d,
    emissiveIntensity: 0.18,
  });

  [
    { lat: 24, lon: -25, scale: [0.9, 0.38, 0.03], rot: -0.3 },
    { lat: -12, lon: -55, scale: [0.55, 0.28, 0.03], rot: 0.5 },
    { lat: 40, lon: 78, scale: [1.05, 0.34, 0.03], rot: 0.18 },
    { lat: -24, lon: 128, scale: [0.48, 0.24, 0.03], rot: -0.12 },
    { lat: 4, lon: 20, scale: [0.6, 0.34, 0.03], rot: 0.85 },
  ].forEach((patch) => {
    const land = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 12), landMaterial);
    land.scale.set(...patch.scale);
    land.position.copy(latLonToVector(THREE.MathUtils.degToRad(patch.lat), THREE.MathUtils.degToRad(patch.lon), 3.02));
    land.lookAt(land.position.clone().multiplyScalar(2));
    land.rotateZ(patch.rot);
    group.add(land);
  });

  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(3.16, 64, 64),
    new THREE.MeshBasicMaterial({
      color: 0x70d9ff,
      transparent: true,
      opacity: 0.13,
      side: THREE.BackSide,
    })
  );
  group.add(atmosphere);

  const cloudBand = new THREE.Mesh(
    new THREE.SphereGeometry(3.06, 48, 48),
    new THREE.MeshStandardMaterial({
      color: 0xf4fbff,
      transparent: true,
      opacity: 0.07,
      roughness: 1,
    })
  );
  group.add(cloudBand);

  return { group, earth, atmosphere, cloudBand };
}

export function latLonToVector(lat, lon, radius) {
  return new THREE.Vector3(
    radius * Math.cos(lat) * Math.cos(lon),
    radius * Math.sin(lat),
    radius * Math.cos(lat) * Math.sin(lon)
  );
}
