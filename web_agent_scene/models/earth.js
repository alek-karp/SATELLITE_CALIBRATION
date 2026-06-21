import * as THREE from "three";

const earthTexture = new THREE.TextureLoader().load("./assets/earth-blue-marble-2048.jpg");
earthTexture.colorSpace = THREE.SRGBColorSpace;
earthTexture.anisotropy = 8;

export function createEarth() {
  const group = new THREE.Group();

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(3, 96, 96),
    new THREE.MeshStandardMaterial({
      map: earthTexture,
      color: 0xffffff,
      roughness: 0.72,
      metalness: 0.02,
      emissive: 0x061424,
      emissiveIntensity: 0.16,
    })
  );
  group.add(earth);

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
