// Browser check of the exploratory badge and Intake tab (used by test_explore_outputs).
// Usage: node explore_smoke.js <dashboard.html> <screenshot dir>
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

(async () => {
  const [html, shots] = process.argv.slice(2);
  fs.mkdirSync(shots, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [], requests = [];
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", e => errors.push(String(e)));
  page.on("request", r => { if (!r.url().startsWith("file:")) requests.push(r.url()); });
  await page.goto("file://" + path.resolve(html));
  const res = { errors, requests };
  res.tabs = await page.$$eval("nav button", bs => bs.map(b => b.textContent));
  const ids = await page.$$eval("nav button", bs => bs.map(b => b.dataset.tab));
  for (let i = 0; i < ids.length; i++) {
    await page.click(`nav button[data-tab="${ids[i]}"]`);
    if (ids[i] === "fnd") {
      res.badges = await page.$$eval("#fT .badge", es => es.map(e => e.textContent));
      res.badge_visible = await page.locator("#fT .badge").first().isVisible().catch(() => false);
    }
    if (ids[i] === "intake") {
      res.intake_text = await page.locator("#intake").innerText();
      res.intake_pre = await page.locator("#intake pre").count();
    }
    await page.screenshot({ path: path.join(shots, `${i + 1}-${ids[i]}.png`), fullPage: true });
  }
  res.xss = await page.evaluate(() => window.__x === undefined);
  res.injected = await page.locator("img[src='x'], #intake script").count();
  await browser.close();
  process.stdout.write(JSON.stringify(res));
})().catch(e => { console.error(e); process.exit(1); });
