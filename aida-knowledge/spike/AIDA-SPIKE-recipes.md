# AIDA-SPIKE-recipes (ไฟล์ชั่วคราวสำหรับ spike เท่านั้น)

ไฟล์นี้อัปโหลดเข้า Knowledge ชั่วคราวเพื่อทดสอบ Code Interpreter ห้ามเก็บไว้หลัง spike

## การ์ด NET-FUNNEL (เวอร์ชัน spike)

เกณฑ์อ่านจาก `cfg["NET.FUNNEL"]` = `{"min_sources": 10, "out_ratio": 0.8, "days": 7}` (ใน spike กำหนดใน prompt)

```python
# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.FUNNEL | Input: transactions(from_acct, to_acct, amount, ts)
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    p = cfg["NET.FUNNEL"]
    tx = tables["transactions"].copy()
    tx["ts"] = pd.to_datetime(tx["ts"])
    tx = tx[(tx["from_acct"] != tx["to_acct"]) & (tx["amount"] > 0)]
    rows = []
    for acct, inc in tx.groupby("to_acct"):
        n_src = inc["from_acct"].nunique()
        if n_src < p["min_sources"]:
            continue
        t_in = inc["amount"].sum()
        end = inc["ts"].max() + pd.Timedelta(days=p["days"])
        out = tx[(tx["from_acct"] == acct) & (tx["ts"] >= inc["ts"].min()) & (tx["ts"] <= end)]
        ratio = out["amount"].sum() / t_in if t_in > 0 else 0.0
        if ratio >= p["out_ratio"]:
            rows.append({
                "acct": acct,
                "sources": int(n_src),
                "total_in": float(t_in),
                "out_ratio": round(float(ratio), 3),
                "record_refs": ";".join(inc["tx_id"].astype(str).tolist() + out["tx_id"].astype(str).tolist()),
            })
    cols = ["acct", "sources", "total_in", "out_ratio", "record_refs"]
    return pd.DataFrame(rows, columns=cols)
```

## Template Dashboard (ทดสอบการดึง template ยาว)

```html
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>AIDA Dashboard (spike template)</title>
<style>
  :root { --bg:#f6f7f9; --fg:#1d2330; --card:#fff; --line:#d9dde5; --acc:#1f5fbf; --warn:#b3261e; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: "Segoe UI", Tahoma, sans-serif; background:var(--bg); color:var(--fg); }
  header { padding:12px 20px; background:var(--card); border-bottom:1px solid var(--line); }
  .warn { background:#fdecea; color:var(--warn); padding:8px 20px; font-size:14px; }
  nav { display:flex; gap:4px; padding:8px 20px 0; }
  nav button { border:1px solid var(--line); border-bottom:none; background:#eef0f4;
               padding:8px 16px; cursor:pointer; border-radius:6px 6px 0 0; }
  nav button.on { background:var(--card); color:var(--acc); font-weight:600; }
  main { padding:16px 20px; }
  .tab { display:none; background:var(--card); border:1px solid var(--line); padding:16px; border-radius:0 6px 6px 6px; }
  .tab.on { display:block; }
  .kpis { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
  .kpi { border:1px solid var(--line); border-radius:6px; padding:10px 16px; min-width:120px; }
  .kpi b { display:block; font-size:24px; color:var(--acc); }
  table { border-collapse:collapse; width:100%; font-size:14px; }
  th, td { border-bottom:1px solid var(--line); padding:6px 8px; text-align:left; }
  tr.row { cursor:pointer; }
  tr.row:hover { background:#eef4ff; }
  #detail { margin-top:12px; padding:10px; background:#f3f6fb; border-left:4px solid var(--acc); display:none; }
  .bar { fill:var(--acc); }
  .bar.hi { fill:var(--warn); }
  footer { padding:8px 20px; font-size:12px; color:#667; }
</style>
</head>
<body>
<header><h1>รายงานสรุปผลการวิเคราะห์ (ตัวอย่าง template สำหรับ spike)</h1></header>
<div class="warn">ข้อมูลอ่อนไหว: ใช้ภายในงานตรวจสอบเท่านั้น ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป</div>
<nav id="tabs"></nav>
<main>
  <section class="tab" id="t-summary">
    <div class="kpis" id="kpis"></div>
    <svg id="chart" width="480" height="160" role="img" aria-label="จำนวน Finding ตาม Risk"></svg>
  </section>
  <section class="tab" id="t-findings">
    <label>กรอง Risk: <select id="flt"><option value="">ทั้งหมด</option></select></label>
    <table>
      <thead><tr><th>บัญชี</th><th>Risk</th><th>ข้อสังเกต</th><th>จำนวนรายการ</th></tr></thead>
      <tbody id="fbody"></tbody>
    </table>
    <div id="detail"></div>
  </section>
  <section class="tab" id="t-log">
    <table><thead><tr><th>Card</th><th>สถานะ</th><th>เหตุผล</th></tr></thead><tbody id="lbody"></tbody></table>
  </section>
</main>
<footer>สร้างโดย AIDA - ผลลัพธ์สอดคล้องกับ Mule Account pattern ต้องได้รับการยืนยันจากผู้ตรวจสอบ</footer>
<script>
const DATA = {
  findings: [
    {acct: "F01", risk: "R1", note: "รับจาก 12 แหล่ง และโอนออกประมาณ 85% ภายใน 3 วัน", refs: ["T0010", "T0020", "T0030"]},
    {acct: "A07", risk: "R1", note: "โอนถี่กว่าปกติในช่วงสั้น", refs: ["T0044"]},
    {acct: "A12", risk: "R2", note: "สัญญาณหลายตัวพร้อมกัน", refs: ["T0051", "T0052"]}
  ],
  log: [
    {card: "NET-FUNNEL", status: "Run", reason: ""},
    {card: "MULE-DWELL", status: "Skip", reason: "ไม่มีคอลัมน์ ts ที่ใช้ได้"}
  ]
};
const TABS = [["summary", "สรุป"], ["findings", "Findings"], ["log", "Run Log"]];
function show(id) {
  TABS.forEach(([k]) => {
    document.getElementById("t-" + k).classList.toggle("on", k === id);
    document.getElementById("b-" + k).classList.toggle("on", k === id);
  });
}
TABS.forEach(([k, label]) => {
  const b = document.createElement("button");
  b.id = "b-" + k; b.textContent = label; b.onclick = () => show(k);
  document.getElementById("tabs").appendChild(b);
});
function renderSummary() {
  const byRisk = {};
  DATA.findings.forEach(f => byRisk[f.risk] = (byRisk[f.risk] || 0) + 1);
  const k = document.getElementById("kpis");
  k.innerHTML = `<div class="kpi"><b>${DATA.findings.length}</b>Findings</div>` +
    `<div class="kpi"><b>${DATA.log.filter(l => l.status === "Run").length}</b>Run</div>` +
    `<div class="kpi"><b>${DATA.log.filter(l => l.status === "Skip").length}</b>Skip</div>`;
  const svg = document.getElementById("chart");
  Object.keys(byRisk).sort().forEach((r, i) => {
    const h = byRisk[r] * 40, y = 130 - h;
    svg.insertAdjacentHTML("beforeend",
      `<rect class="bar ${r === "R2" ? "hi" : ""}" x="${30 + i * 70}" y="${y}" width="44" height="${h}"/>` +
      `<text x="${38 + i * 70}" y="150">${r}</text><text x="${46 + i * 70}" y="${y - 4}">${byRisk[r]}</text>`);
  });
}
function renderFindings() {
  const sel = document.getElementById("flt");
  [...new Set(DATA.findings.map(f => f.risk))].forEach(r => sel.add(new Option(r, r)));
  const draw = () => {
    const body = document.getElementById("fbody"); body.innerHTML = "";
    DATA.findings.filter(f => !sel.value || f.risk === sel.value).forEach(f => {
      const tr = document.createElement("tr"); tr.className = "row";
      tr.innerHTML = `<td>${f.acct}</td><td>${f.risk}</td><td>${f.note}</td><td>${f.refs.length}</td>`;
      tr.onclick = () => {
        const d = document.getElementById("detail"); d.style.display = "block";
        d.textContent = "record_refs: " + f.refs.join(", ");
      };
      body.appendChild(tr);
    });
  };
  sel.onchange = draw; draw();
}
function renderLog() {
  document.getElementById("lbody").innerHTML = DATA.log.map(
    l => `<tr><td>${l.card}</td><td>${l.status}</td><td>${l.reason}</td></tr>`).join("");
}
renderSummary(); renderFindings(); renderLog(); show("summary");
</script>
</body>
</html>
<!-- END-OF-TEMPLATE -->
```
