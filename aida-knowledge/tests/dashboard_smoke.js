// Browser check of the AIDA dashboard (used by test_outputs.TestDashboard.test_dashboard_in_browser).
// Usage: node dashboard_smoke.js <dashboard.html> <screenshot dir>
// Opens the file in Chromium, clicks every tab, a network node and a finding row, screenshots each
// tab, and prints JSON: console/page errors, every non-file request, tab labels and what rendered.
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
  const tabs = await page.$$eval("nav button", bs => bs.map(b => b.textContent));
  const ids = await page.$$eval("nav button", bs => bs.map(b => b.dataset.tab));
  const res = { errors, requests, tabs };
  for (let i = 0; i < ids.length; i++) {
    await page.click(`nav button[data-tab="${ids[i]}"]`);
    if (ids[i] === "net") {
      res.nodes = await page.locator("#netV circle").count();
      res.member_rows = await page.locator("#netV .members tr[data-i]").count();
      if (res.nodes) await page.locator("#netV circle").first().click();
      else if (res.member_rows) await page.locator("#netV .members tr[data-i]").first().click();
      res.node_findings = await page.locator("#nF tr[data-i]").count() > 0;
    }
    if (ids[i] === "fnd") {
      if (await page.locator("#fT tr[data-i]").count()) await page.locator("#fT tr[data-i]").first().click();
      res.finding_headers = await page.$$eval("#fT th", ths => ths.map(t => [t.textContent, t.title]));
      res.finding_evidence = await page.locator("#fE tr").count() > 1;
    }
    if (ids[i] === "flow") {  // show the trace with the most hops (columns left to right)
      let best = [null, 0];
      for (const v of await page.$$eval("#tS option", os => os.map(o => o.value))) {
        await page.selectOption("#tS", v);
        const n = await page.locator("#tV .hop").count();
        if (n > best[1]) best = [v, n];
      }
      if (best[0]) await page.selectOption("#tS", best[0]);
      res.flow_columns = best[1];
    }
    await page.screenshot({ path: path.join(shots, `${i + 1}-${ids[i]}.png`), fullPage: true });
  }
  await browser.close();
  process.stdout.write(JSON.stringify(res));
})().catch(e => { console.error(e); process.exit(1); });
