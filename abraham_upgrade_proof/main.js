import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

const MODEL_URL = './assets/abraham_upgrade_bundle.glb';
const viewport = document.getElementById('viewport');
const statusEl = document.getElementById('status');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111821);
const camera = new THREE.PerspectiveCamera(40, 1, .02, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.autoRotateSpeed = 1.5;
controls.minDistance = .5;
controls.maxDistance = 12;
scene.add(new THREE.HemisphereLight(0xf6e9cf, 0x26364a, 2.25));
const key = new THREE.DirectionalLight(0xffffff, 3.25);
key.position.x = 3.5;
key.position.y = 6;
key.position.z = 4.5;
scene.add(key);
const fill = new THREE.DirectionalLight(0xffd8a3, 1.2);
fill.position.x = -4;
fill.position.y = 2.5;
fill.position.z = 1.5;
scene.add(fill);
const ground = new THREE.Mesh(new THREE.CircleGeometry(3, 72), new THREE.MeshStandardMaterial({ color: 0x2a2f34, roughness: 1 }));
ground.rotation.x = -Math.PI / 2;
ground.position.y = -.01;
scene.add(ground);

let root = null;
let mixer = null;
const actions = new Map();
let currentAction = null;
let paused = false;
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
  camera.position.x = center.x + maxSize * .10;
  camera.position.y = center.y + maxSize * .12;
  camera.position.z = center.z + maxSize * 2.15;
  camera.near = Math.max(.01, maxSize / 100);
  camera.far = maxSize * 20;
  camera.updateProjectionMatrix();
  controls.update();
  ground.position.x = center.x;
  ground.position.z = center.z;
  ground.position.y = bounds.min.y;
}

function setUpgradeLevel(level) {
  if (!root) return;
  if (gear.staff) gear.staff.visible = level >= 1;
  if (gear.belt) gear.belt.visible = level >= 2;
  if (gear.mantle) gear.mantle.visible = level >= 3;
  const missing = [];
  if (level >= 1 && !gear.staff) missing.push('staff');
  if (level >= 2 && !gear.belt) missing.push('belt');
  if (level >= 3 && !gear.mantle) missing.push('mantle');
  showStatus(missing.length ? `Missing equipment: ${missing.join(', ')}.` : `Upgrade stage ${level} ready.`, missing.length > 0);
}

function playAnimation(name) {
  if (!mixer) return;
  const next = actions.get(name);
  if (!next) {
    showStatus(`${name} is unavailable.`, true);
    return;
  }
  next.enabled = true;
  next.reset().fadeIn(.22).play();
  if (currentAction && currentAction !== next) currentAction.fadeOut(.22);
  currentAction = next;
}

function prepareModel(gltf) {
  root = gltf.scene;
  scene.add(root);
  gear = { staff: root.getObjectByName('Equip_Staff'), belt: root.getObjectByName('Equip_Belt'), mantle: root.getObjectByName('Equip_Mantle') };
  root.traverse((object) => {
    if (!object.isMesh) return;
    object.castShadow = false;
    object.receiveShadow = false;
    if (object.material && 'envMapIntensity' in object.material) object.material.envMapIntensity = .65;
  });
  mixer = new THREE.AnimationMixer(root);
  for (const clip of gltf.animations) {
    if (['Idle', 'Walk', 'Run'].includes(clip.name)) actions.set(clip.name, mixer.clipAction(clip));
  }
  setUpgradeLevel(0);
  playAnimation('Idle');
  mixer.update(0);
  root.updateMatrixWorld(true);
  fitCamera();
  const missing = Object.entries(gear).filter(([, node]) => !node).map(([name]) => name);
  showStatus(missing.length ? `Abraham loaded. Missing gear: ${missing.join(', ')}.` : 'Abraham loaded. Equipment is pre-fitted.', missing.length > 0);
}

const loader = new GLTFLoader();
const draco = new DRACOLoader();
draco.setDecoderPath('https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/libs/draco/gltf/');
loader.setDRACOLoader(draco);
loader.load(MODEL_URL, prepareModel, (event) => {
  if (event.total) showStatus(`Loading Abraham bundle… ${Math.round(event.loaded / event.total * 100)}%`);
}, (error) => {
  console.error(error);
  showStatus('Could not load the Abraham model. Please reopen with an internet connection for the mesh decoder.', true);
});

document.querySelectorAll('[data-level]').forEach((button) => button.addEventListener('click', () => {
  if (!root) return;
  document.querySelectorAll('[data-level]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  setUpgradeLevel(Number(button.dataset.level));
}));
document.querySelectorAll('[data-animation]').forEach((button) => button.addEventListener('click', () => {
  if (!mixer) return;
  document.querySelectorAll('[data-animation]').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  playAnimation(button.dataset.animation);
}));
document.getElementById('pause-animation')?.addEventListener('click', (event) => {
  paused = !paused;
  event.currentTarget.textContent = paused ? 'Resume' : 'Pause';
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
  const delta = Math.min(clock.getDelta(), .05);
  if (mixer && !paused) mixer.update(delta);
  controls.update();
  renderer.render(scene, camera);
}
render();
