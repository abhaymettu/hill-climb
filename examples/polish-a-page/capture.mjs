// Fixed capture: same views, same order, same sizes every round. Usage: node capture.mjs <outdir>
// Also runs the gates and writes gates.json: text unchanged, no horizontal overflow, WCAG contrast of every text node.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
const out = process.argv[2];
fs.mkdirSync(out, { recursive: true });
const url = 'file://' + path.resolve('index.html');
const views = [['desktop', 1280, 900], ['mobile', 390, 844]];
const browser = await chromium.launch();
const gates = { overflow: {}, minContrast: {}, text: null };
for (const [name, w, h] of views) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await page.goto(url);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  const r = await page.evaluate(() => {
    const parse = s => (s.match(/[\d.]+/g) || []).map(Number);
    const lum = ([r, g, b]) => { const f = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
    const bgOf = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c.length === 3 || (c.length === 4 && c[3] > 0.99)) return c.slice(0, 3); } return [255, 255, 255]; };
    let min = 99, worst = '';
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const n = walker.currentNode; if (!n.textContent.trim()) continue;
      const el = n.parentElement; const fg = parse(getComputedStyle(el).color).slice(0, 3);
      const a = lum(fg), b = lum(bgOf(el)); const cr = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (cr < min) { min = cr; worst = n.textContent.trim().slice(0, 40); }
    }
    return { overflow: document.documentElement.scrollWidth > window.innerWidth, min: +min.toFixed(2), worst, text: document.body.innerText.replace(/\s+/g, ' ').trim() };
  });
  gates.overflow[name] = r.overflow; gates.minContrast[name] = { ratio: r.min, worst: r.worst }; gates.text = r.text;
  await page.close();
}
await browser.close();
fs.writeFileSync(`${out}/gates.json`, JSON.stringify(gates, null, 1));
const fails = [];
for (const v of Object.keys(gates.overflow)) { if (gates.overflow[v]) fails.push(`overflow ${v}`); if (gates.minContrast[v].ratio < 4.5) fails.push(`contrast ${v} ${gates.minContrast[v].ratio}`); }
const ref = fs.existsSync('.hillclimb/baseline-text.txt') ? fs.readFileSync('.hillclimb/baseline-text.txt', 'utf8') : null;
if (ref !== null && ref !== gates.text) fails.push('visible text changed');
console.log(fails.length ? 'GATES FAIL: ' + fails.join('; ') : 'GATES PASS', JSON.stringify(gates.minContrast));
