import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

await mkdir('assets/build/reports/browser', { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const errors = [];
const networkFailures = [];
let page;
try {
  page = await browser.newPage({ viewport: { width: 412, height: 850 }, deviceScaleFactor: 1, offline: true });
  page.on('pageerror', (error) => { errors.push(error.message); console.error('Browser error:', error.message); });
  page.on('requestfailed', request => networkFailures.push({ url: request.url().slice(0, 180), error: request.failure()?.errorText }));
  page.on('console', message => { if (message.type() === 'error') console.error('Browser console:', message.text().slice(0, 500)); });
  await page.goto(pathToFileURL(path.resolve('delivery/Abraham-Modular-Proof.html')).href);
  await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Abraham loaded'), null, { timeout: 60000 });
  await page.locator('#pause-animation').click();
  const states = [];
  let previousImage;
  for (let level = 0; level <= 3; level++) {
    await page.locator(`[data-level="${level}"]`).click();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const image = await page.locator('canvas').screenshot({ path: `assets/build/reports/browser/stage-${level}.png` });
    if (previousImage && image.equals(previousImage)) throw new Error(`Stage ${level} did not change the rendered model`);
    previousImage = image;
    const status = await page.locator('#status').textContent();
    if (status !== `Upgrade stage ${level} ready.`) throw new Error(status);
    states.push(status);
  }
  await page.locator('#pause-animation').click();
  for (const name of ['Idle', 'Walk', 'Run']) {
    await page.locator(`[data-animation="${name}"]`).click();
    await page.waitForTimeout(450);
    const before = await page.locator('canvas').screenshot();
    await page.waitForTimeout(450);
    const after = await page.locator('canvas').screenshot({ path: `assets/build/reports/browser/${name}.png` });
    if (before.equals(after)) throw new Error(`${name} animation did not visibly advance`);
    const status = await page.locator('#status').textContent();
    if (/unavailable|No compatible/.test(status)) throw new Error(status);
  }
  await page.screenshot({ path: 'assets/build/reports/browser/mobile-equipped.png' });
  if (errors.length) throw new Error(errors.join('\n'));
  await writeFile('assets/build/reports/browser/checks.json', JSON.stringify({ pass: true, offline: true, states, animated: ['Idle','Walk','Run'], errors }, null, 2));
} catch (error) {
  const status = page ? await page.locator('#status').textContent().catch(() => null) : null;
  await writeFile('assets/build/reports/browser/failure.json', JSON.stringify({ error: String(error), errors, networkFailures, status }, null, 2));
  if (page) await page.screenshot({ path: 'assets/build/reports/browser/failure.png' }).catch(() => {});
  throw error;
} finally {
  await browser.close();
}
