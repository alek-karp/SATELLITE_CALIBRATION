import * as THREE from "three";

export function createSatellite() {
  const group = new THREE.Group();

  const bodyMaterial = new THREE.MeshStandardMaterial({
    color: 0xd9dde5,
    metalness: 0.88,
    roughness: 0.22,
  });

  const bus = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.42, 0.54), bodyMaterial);
  group.add(bus);

  const panelMaterial = new THREE.MeshStandardMaterial({
    color: 0x386caa,
    emissive: 0x113964,
    emissiveIntensity: 0.75,
    metalness: 0.25,
    roughness: 0.34,
  });

  const panelGeometry = new THREE.BoxGeometry(0.9, 0.04, 0.34);
  const leftPanel = new THREE.Mesh(panelGeometry, panelMaterial);
  leftPanel.position.set(-0.68, 0, 0);
  group.add(leftPanel);

  const rightPanel = leftPanel.clone();
  rightPanel.position.set(0.68, 0, 0);
  group.add(rightPanel);

  const boom = new THREE.Mesh(
    new THREE.CylinderGeometry(0.03, 0.03, 0.46, 8),
    new THREE.MeshStandardMaterial({ color: 0x9cb2c5, metalness: 0.5, roughness: 0.28 })
  );
  boom.rotation.z = Math.PI / 2;
  boom.position.set(0, 0, 0.38);
  group.add(boom);

  const sensor = new THREE.Mesh(
    new THREE.ConeGeometry(0.12, 0.2, 24),
    new THREE.MeshStandardMaterial({ color: 0x111820, metalness: 0.45, roughness: 0.2 })
  );
  sensor.rotation.x = Math.PI / 2;
  sensor.position.set(0, 0, 0.68);
  group.add(sensor);

  return { group, leftPanel, rightPanel };
}
