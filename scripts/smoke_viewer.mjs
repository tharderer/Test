import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

await mkdir('assets/build/reports/browser', { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 412, height: 850 }, deviceScaleFactor: 1 });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto(pathToFileURL(path.resolve('delivery/Abraham-Modular-Proof.html')).href);
  await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Abraham loaded'), null, { timeout: 60000 });
  await page.locator('#pause-animation').click();
  const states = [];
  let baseImage;
  for (let level = 0; level <= 3; level++) {
    await page.locator(`[data-level="${level}"]`).click();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const image = await page.locator('canvas').screenshot({ path: `assets/build/reports/browser/stage-${level}.png` });
    if (level === 0) baseImage = image;
    else if (image.equals(baseImage)) throw new Error(`Stage ${level} did not change the rendered model`);
    const status = await page.locator('#status').textContent();
    if (status !== `Upgrade stage ${level} ready.`) throw new Error(status);
    states.push(status);
  }
  await page.locator('#pause-animation').click();
  for (const name of ['Idle', 'Walk', 'Run']) {
    await page.locator(`[data-animation="${name}"]`).click();
    const status = await page.locator('#status').textContent();
    if (/unavailable|No compatible/.test(status)) throw new Error(status);
  }
  await page.screenshot({ path: 'assets/build/reports/browser/mobile-equipped.png' });
  if (errors.length) throw new Error(errors.join('\n'));
  await writeFile('assets/build/reports/browser/checks.json', JSON.stringify({ pass: true, states, errors }, null, 2));
} finally {
  await browser.close();
}
