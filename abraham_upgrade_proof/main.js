import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const MODEL_URL = './assets/abraham_upgrade_bundle.glb';

const viewport = document.getElementById('viewport');
const statusEl = document.getElementById('status');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111821);
const camera = new THREE.PerspectiveCamera(40, 1, 0.02, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.autoRotateSpeed = 1.5;
controls.minDistance = 0.5;
controls.maxDistance = 12;

scene.add(new THREE.HemisphereLight(0xf6e9cf, 0x26364a, 2.25));
const key = new THREE.DirectionalLight(0xffffff, 3.25);
key.position.x = 3.5;
key.position.y = -4.5;
key.position.z = 6;
scene.add(key);
const fill = new THREE.DirectionalLight(0xffd8a3, 1.2);
fill.position.x = -4;
fill.position.y = 1.5;
fill.position.z = 2.5;
scene.add(fill);

const ground = new THREE.Mesh(
  new THREE.CircleGeometry(3, 72),
  new THREE.MeshStandardMaterial({ color: 0x2a2f34, roughness: 1 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.z = -0.01;
scene.add(ground);

let root = null;
let mixer = null;
let actions = new Map();
let currentAction = null;
let gear = { staff: null, belt: null, mantle: null };
let bounds = null;
const clock = new THREE.Clock();

function showStatus(message, warning = false) {
  statusEl.textContent = message;
  statusEl.dataset.warning = warning ? 'true' : 'false';
}

function fitCamera() {
  if (!root) return;
  bounds = new THREE.Box3().setFromObject(root);
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z, 1);
  controls.target.copy(center);
  camera.position.x = center.x + maxSize * 0.10;
  camera.position.y = center.y - maxSize * 2.15;
  camera.position.z = center.z + maxSize * 0.12;
  camera.near = Math.max(0.01, maxSize / 100);
  camera.far = maxSize * 20;
  camera.updateProjectionMatrix();
  controls.update();
  ground.position.x = center.x;
  ground.position.y = center.y;
  ground.position.z = bounds.min.z;
}

function setUpgradeLevel(level) {
  if (!root) return;
  if (gear.staff) gear.staff.visible = level >= 1 || level === 4;
  if (gear.belt) gear.belt.visible = level >= 2 || level === 4;
  if (gear.mantle) gear.mantle.visible = level >= 3 || level === 4;
  const missing = [];
  if (level >= 1 && !gear.staff) missing.push('staff');
  if (level >= 2 && !gear.belt) missing.push('belt');
  if (level >= 3 && !gear.mantle) missing.push('mantle');
  if (missing.length) showStatus(`Base Abraham is loaded. Missing optional gear: ${missing.join(', ')}.`, true);
  else showStatus(`Upgrade stage ${level} ready.`);
}

function playAnimation(requestedName) {
  if (!mixer) return;
  let selectedName = requestedName;
  let next = actions.get(selectedName);
  if (!next) {
    selectedName = 'Idle';
    next = actions.get('Idle');
    showStatus(`${requestedName} is unavailable; using Idle.`, true);
  }
  if (!next) {
    showStatus('No compatible animation clips found. Base remains visible.', true);
    return;
  }
  next.enabled = true;
  next.reset();
  next.fadeIn(0.22);
  next.play();
  if (currentAction && currentAction !== next) currentAction.fadeOut(0.22);
  currentAction = next;
}

function prepareModel(gltf) {
  root = gltf.scene;
  scene.add(root);
  gear = {
    staff: root.getObjectByName('Equip_Staff'),
    belt: root.getObjectByName('Equip_Belt'),
    mantle: root.getObjectByName('Equip_Mantle'),
  };
  root.traverse((object) => {
    if (!object.isMesh) return;
    object.castShadow = false;
    object.receiveShadow = false;
    if (object.material && 'envMapIntensity' in object.material) object.material.envMapIntensity = 0.65;
  });
  mixer = new THREE.AnimationMixer(root);
  for (const clip of gltf.animations) {
    if (!['Idle', 'Walk', 'Run'].includes(clip.name)) continue;
    actions.set(clip.name, mixer.clipAction(clip));
  }
  setUpgradeLevel(0);
  fitCamera();
  playAnimation('Idle');
  const missing = Object.entries(gear).filter(([, node]) => !node).map(([name]) => name);
  showStatus(missing.length ? `Abraham loaded. Missing optional gear: ${missing.join(', ')}.` : 'Abraham loaded. Gear is pre-fitted; runtime only toggles visibility.', missing.length > 0);
}

const loader = new GLTFLoader();
loader.load(
  MODEL_URL,
  prepareModel,
  (event) => {
    if (!event.total) return;
    const percent = Math.round((event.loaded / event.total) * 100);
    showStatus(`Loading Abraham bundle… ${percent}%`);
  },
  (error) => {
    console.error(error);
    showStatus('Could not load Abraham bundle. Base viewer remains running; rebuild/copy the proof asset and retry.', true);
  }
);

document.querySelectorAll('[data-level]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-level]').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    setUpgradeLevel(Number(button.dataset.level));
  });
});

document.querySelectorAll('[data-animation]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-animation]').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    playAnimation(button.dataset.animation);
  });
});

document.getElementById('reset-camera').addEventListener('click', fitCamera);
document.getElementById('auto-rotate').addEventListener('click', (event) => {
  controls.autoRotate = !controls.autoRotate;
  event.currentTarget.classList.toggle('active', controls.autoRotate);
});

function resize() {
  const width = Math.max(1, viewport.clientWidth);
  const height = Math.max(1, viewport.clientHeight);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

function render() {
  requestAnimationFrame(render);
  const delta = Math.min(clock.getDelta(), 0.05);
  if (mixer) mixer.update(delta);
  controls.update();
  renderer.render(scene, camera);
}
render();
