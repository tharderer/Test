import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { build } from 'esbuild';

const viewer = path.join(process.cwd(), 'abraham_upgrade_proof');
const glb = await readFile(path.join(viewer, 'assets/abraham_upgrade_bundle.glb'));
if (glb.readUInt32LE(0) !== 0x46546c67) throw new Error('Not a GLB file');
const metadata = JSON.parse(glb.subarray(20, 20 + glb.readUInt32LE(12)).toString());
const clips = new Set((metadata.animations || []).map((clip) => clip.name));
for (const name of ['Idle', 'Walk', 'Run']) {
  if (!clips.has(name)) throw new Error(`Export lost ${name} animation`);
}
const names = new Set(metadata.nodes.map((node) => node.name));
for (const name of ['Equip_Staff', 'Equip_Belt', 'Equip_Mantle']) {
  if (!names.has(name)) throw new Error(`Export lost ${name}`);
}
const main = (await readFile(path.join(viewer, 'main.js'), 'utf8')).replace(
  "const MODEL_URL = './assets/abraham_upgrade_bundle.glb';",
  `const MODEL_URL = 'data:model/gltf-binary;base64,${glb.toString('base64')}';`
);
const result = await build({
  stdin: { contents: main, resolveDir: viewer, sourcefile: 'proof-main.js', loader: 'js' },
  bundle: true, write: false, format: 'iife', target: 'es2020', minify: true,
});
const script = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = await readFile(path.join(viewer, 'styles.css'), 'utf8');
const html = (await readFile(path.join(viewer, 'index.html'), 'utf8'))
  .replace(/<script type="importmap">[\s\S]*?<\/script>/, '')
  .replace('<link rel="stylesheet" href="./styles.css">', `<style>${css}</style>`)
  .replace('<script type="module" src="./main.js"></script>', `<script>${script}</script>`);
await mkdir('delivery', { recursive: true });
await writeFile('delivery/Abraham-Modular-Proof.html', html);
console.log(`Packaged ${glb.length} model bytes in ${Buffer.byteLength(html)} HTML bytes`);
