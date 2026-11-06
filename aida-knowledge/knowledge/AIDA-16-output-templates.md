# AIDA-16 · Output Templates (Audit Workbook, Network Investigation Package, HTML Dashboard)
> ไฟล์: AIDA-16 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Audit Workbook มี sheet อะไรบ้างตามลำดับ, Network Investigation Package (nodes.csv / edges.csv / flows.csv) มีคอลัมน์อะไร, HTML Dashboard มีแท็บอะไรและสร้างจาก template อย่างไร, ป้ายเตือนข้อมูลอ่อนไหวเขียนว่าอะไร, ข้อจำกัดของการหาเครือข่ายคืออะไร

## สรุปสั้น
ไฟล์นี้กำหนดรูปแบบ output 3 ชนิดของ Phase B1 (ข้อ 8 ของขั้นตอน) ที่การ์ด OUT-WORKBOOK, OUT-NETWORK-CSV และ OUT-DASHBOARD ใน AIDA-19 สร้างจาก `bundle` ของการ์ด OUT-BUNDLE
ทุก output แสดงข้อมูลเต็ม (เลขบัญชี จำนวนเงิน tx_id) ตามที่ผู้ใช้/องค์กรกำหนด และมีป้ายเตือนข้อความเดียวกัน:
**"ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป"**
ข้อจำกัดที่ต้องแจ้งทุกครั้ง: การหาเครือข่ายใช้ข้อมูลธุรกรรมเท่านั้น (ไม่มีข้อมูลระบุตัวตน) และบัญชีที่เป็นจุดผ่านเงินซึ่งทำหน้าที่ collector อาจรวมกลุ่มที่ไม่เกี่ยวข้องกันเป็นเครือข่ายเดียว

## 1. Audit Workbook (.xlsx) — sheet ตามลำดับ
| # | Sheet | เนื้อหา |
|---|---|---|
| 1 | README | ป้ายเตือนข้อมูลอ่อนไหว, run_id + Registry version, ข้อจำกัดของการหาเครือข่าย, รูปแบบวันที่ที่ใช้แปลง, หมายเหตุข้อจำกัดของการ์ด (card_notes เช่น NET-CYCLE ค้นหาถึงขีดจำกัด), หมายเหตุ trace ที่ไม่ครบ, วิธีอ่านแต่ละ sheet |
| 2 | Dataset_Profile | ผล PROF-PROFILE (item, value, detail) |
| 3 | Analysis_Plan | ผล GATE-CAPABILITY (recipe_id, decision Run/Skip, reason, missing) |
| 4 | Evidence | Evidence schema (AIDA-17) ครบทุกคอลัมน์ รวม record_refs (tx_id คั่นด้วย ", ") และ data_ref |
| 5 | Findings | 14 คอลัมน์ Finding schema + member_accts + คอลัมน์ว่าง reviewer, disposition, review_date ให้ผู้ตรวจกรอกหลัง Human Review |
| 6 | Mule_Networks | Mule Network schema (network_id, member_accts, roles, internal_tx_count, internal_amount, period_start, period_end) |
| 7 | Money_Flow | หมายเหตุการไล่เส้นทาง (ครบ หรือถึง `FLOW.MAX_TRAIL_ROWS = 5,000` แล้วหยุด) เหนือตาราง Money Flow trail |
| 8 | Materiality | ฐานที่ผู้ใช้ยืนยัน (หรือ "ไม่ได้ประเมิน"), เกณฑ์สูง/กลาง/ต่ำ ตาม `ASSESS.CLEARLY_TRIVIAL = < 5% ของ Materiality` และจำนวน Finding ต่อระดับ |
| 9 | Run_Log | Run Log schema (AIDA-17) |

- ข้อความที่ขึ้นต้นด้วย = + - @ แท็บ หรือ carriage return ถูกเติม `'` ข้างหน้าทั้งใน Workbook และ CSV (กันไม่ให้ข้อมูลกลายเป็นสูตร — การ์ด OUT-CELL) และตัดอักขระควบคุมที่ Excel เก็บไม่ได้
- list / dict เขียนเป็นข้อความ (คั่นด้วย ", ") — ข้อความที่ยาวเกินที่ Excel เก็บได้ใน 1 ช่องถูกตัดและลงท้าย "…" (ฉบับเต็มอยู่ใน CSV / Dashboard)

## 2. Network Investigation Package (.csv, UTF-8)
| ไฟล์ | คอลัมน์ | หมายเหตุ |
|---|---|---|
| `nodes.csv` | node_id, role, network_id, finding_ids | role = mule / collector / feeder / other (บทบาทในเครือข่าย ไม่ใช่ข้อสรุป); finding_ids คั่นด้วย "; " |
| `edges.csv` | source, target, amount, ts, tx_id, network_id | รายการใน record_refs ของ Finding; network_id ว่างเมื่อไม่ได้อยู่ภายในเครือข่ายเดียวกัน |
| `flows.csv` | trace_id, start_acct, direction, hop, from_acct, to_acct, amount, ts, tx_id | Money Flow trail (AIDA-17) |

- เฉพาะ subgraph ที่เกี่ยวกับ Finding — ไม่ใช่ธุรกรรมทั้งไฟล์; นำเข้าเครื่องมือ graph ขององค์กรได้โดยตรง

## 3. HTML Interactive Dashboard (ไฟล์เดียว ไม่โหลดสิ่งใดจากภายนอก)
- ป้ายเตือนข้อมูลอ่อนไหวบนสุด; แท็บ **สรุป** (จำนวน Finding ตาม Priority / Risk, จำนวนเครือข่าย, Run / Skip, ข้อจำกัด) · **Findings** (กรองตาม Priority และ Risk, คลิกแถวเห็น Evidence + record_refs) · **Mule Networks** (SVG วงกลม 1 ภาพต่อเครือข่าย สีตามบทบาท พร้อมคำอธิบายสี, คลิก node เห็น Finding) · **Money Flow** (เลือก trace, ทอดเรียงเป็นคอลัมน์ซ้าย → ขวา) · **Run Log**
- หัวตารางเป็นภาษาไทย (ชื่อคอลัมน์ Schema อยู่ใน tooltip); เครือข่ายที่มีสมาชิกเกิน 40 บัญชี (`NET_DRAW_MAX` ใน template) แสดงเป็นตารางสมาชิก (บัญชี, บทบาท, Finding) แทนภาพวงกลม และชี้ไปที่ nodes.csv / edges.csv
- ตารางแบ่งหน้า หน้าละ 50 แถว และแต่ละทอดของ Money Flow แสดงไม่เกิน 200 รายการ (ที่เหลือดูใน flows.csv / sheet Money_Flow) เพื่อให้ไฟล์ใหญ่ยังใช้งานได้
- วิธีสร้าง: คัดลอก block ```html ด้านล่าง **ทั้งหมดตามตัวอักษร** เป็นข้อความ `template` แล้วเรียก `out_dashboard(bundle, template, path, cfg)` (AIDA-19) — ไม่มีบรรทัด `<!-- END-OF-TEMPLATE -->` = ดึงมาไม่ครบ ให้ดึงใหม่ ห้ามเขียนส่วนที่ขาดเอง

### Template Dashboard
```html
<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIDA Dashboard</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1f2933;--mute:#5b6676;--line:#d8dde4;--head:#eef1f5;--accent:#1d5c96;--warn:#7a4100;--warnbg:#fff3dc}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Sarabun","Noto Sans Thai","Leelawadee UI",Tahoma,"Loma",sans-serif}
.banner{background:var(--warnbg);color:var(--warn);border-bottom:2px solid #e9a94b;padding:10px 16px;font-weight:600}
header{padding:12px 16px 4px}h1{font-size:18px;margin:0}h3{font-size:15px;margin:18px 0 8px}
nav{display:flex;flex-wrap:wrap;gap:2px;padding:0 16px;border-bottom:1px solid var(--line)}
nav button{border:0;background:none;padding:10px 14px;font:inherit;color:var(--mute);cursor:pointer;border-bottom:3px solid transparent}
nav button.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
main{padding:16px;max-width:1280px}section{display:none}section.on{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.card b{display:block;font-size:24px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);font-size:13px}
th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}th{background:var(--head)}
td{max-width:520px;overflow-wrap:break-word}
.badge{display:inline-block;background:var(--warnbg);color:var(--warn);border:1px solid #e9a94b;border-radius:10px;padding:0 8px;font-size:12px;font-weight:600;white-space:nowrap}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--head);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:12px;margin:4px 0}
.xp{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin-bottom:10px}.xp h4{margin:0 0 4px;font-size:14px}tr.click{cursor:pointer}tr.click:hover{background:#eaf3ff}
.note{color:var(--mute);font-size:13px}.warn{color:var(--warn);background:var(--warnbg);padding:6px 10px;border-radius:6px}
select,.pager button{font:inherit;margin:4px 6px 8px 0}.refs{font-family:monospace;font-size:12px;overflow-wrap:anywhere}
.legend span{display:inline-flex;align-items:center;margin:0 14px 6px 0}.dot{width:12px;height:12px;border-radius:50%;margin-right:5px}
svg{background:var(--card);border:1px solid var(--line);border-radius:8px}svg circle{cursor:pointer;stroke:#fff;stroke-width:2}
.flow{display:flex;gap:12px;overflow-x:auto;align-items:flex-start}.hop{min-width:230px;flex:0 0 230px}
.tx{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:6px 8px;margin-bottom:6px;font-size:12px}
</style>
</head>
<body>
<div class="banner" role="note">ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป</div>
<header><h1>AIDA · Potential Unusual Transactions across Mule Accounts</h1><div class="note" id="meta"></div></header>
<nav id="tabs"><button data-tab="sum" class="on">สรุป</button><button data-tab="fnd">Findings</button><button data-tab="net">Mule Networks</button><button data-tab="flow">Money Flow</button><button data-tab="log">Run Log</button></nav>
<main>
<section id="sum" class="on"></section>
<section id="fnd"><label>Priority <select id="fP"></select></label> <label>ความเสี่ยง <select id="fR"></select></label><div id="fT"></div><div id="fD"></div></section>
<section id="net"><div class="legend" id="legend"></div><div id="netV"></div><div id="netD"></div></section>
<section id="flow"><label id="tL">เลือก trace <select id="tS"></select></label><div id="tN"></div><div class="flow" id="tV"></div></section>
<section id="log"></section>
</main>
<script id="aida-data" type="application/json">/*__AIDA_DATA__*/</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("aida-data").textContent);
const PAGE = 50, HOP_CAP = 200, NET_DRAW_MAX = 40; // rows per page / transfers per hop column / members drawn as a circle
const LABEL = {finding_id: "รหัส Finding", entity_type: "ประเภท", entity_id: "บัญชี / เครือข่าย", risk: "ความเสี่ยง", period: "เดือน",
  exposure: "ยอดเงินที่เกี่ยวข้อง (Exposure)", confidence: "ความมั่นใจ (Confidence)", materiality: "สาระสำคัญ (Materiality)",
  priority: "ลำดับความสำคัญ (Priority)", network_id: "เครือข่าย", review_reason: "เหตุผลที่ต้องทบทวน", evidence_id: "รหัส Evidence",
  recipe_id: "การ์ดวิเคราะห์", skill_family: "กลุ่มวิธีวิเคราะห์", metric: "ตัวชี้วัด", value: "ค่าที่พบ", threshold: "เกณฑ์",
  explanation: "คำอธิบาย", record_refs: "รายการอ้างอิง (tx_id)", decision: "รัน / ข้าม (Run / Skip)", reason: "เหตุผล",
  missing: "ข้อมูลที่ขาด", item: "รายการ", detail: "รายละเอียด", name: "ชื่อความเสี่ยง", findings: "จำนวน Finding",
  run_id: "รหัสการรัน", timestamp: "เวลา", stage: "ขั้นตอน", status: "สถานะ", recipe_version: "เวอร์ชันการ์ด",
  registry_version: "เวอร์ชัน Registry", pack_version: "เวอร์ชัน Pack", input_sha256: "ค่า hash ของไฟล์ (sha256)",
  account: "บัญชี", role: "บทบาทในเครือข่าย", finding_ids: "Finding ที่เกี่ยวข้อง", source_label: "ที่มา", section: "หัวข้อ",
  table: "ตาราง", column: "คอลัมน์", meaning: "ความหมาย", code_values: "ความหมายของค่ารหัส", confirmed_by: "ผู้ยืนยัน",
  confirmed_at: "วันที่ยืนยัน", no: "ลำดับ", risk_id: "ความเสี่ยง", request: "ข้อมูลที่ควรขอเพิ่ม"};
const RISK = {R1: "การเคลื่อนย้ายเงินผิดปกติ", R2: "รูปแบบบัญชีรับ-ส่งต่อเงิน (สอดคล้องกับ Mule Account pattern)",
  R3: "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกัน (Mule network)", R4: "ความผิดปกติของคู่ค้า (Counterparty)"};
const ROLE = {mule: ["mule — สอดคล้องกับ Mule Account pattern", "#c2410c"],
  collector: ["collector — รับเงินจากหลายบัญชีในกลุ่ม", "#6d28d9"],
  feeder: ["feeder — ส่งเงินให้หลายบัญชีในกลุ่ม", "#0f766e"], other: ["บทบาทอื่น", "#64748b"]};
Object.assign(RISK, D.risk_names || {});
const IS_E = !("data_type" in D) || D.data_type === "E"; // Mule Networks / Money Flow only for data type E (or older bundles)
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmt = v => typeof v === "number" ? v.toLocaleString("th-TH", {maximumFractionDigits: 2})
  : Array.isArray(v) ? v.join(", ") : v && typeof v === "object" ? Object.entries(v).map(([k, x]) => k + ": " + x).join(", ")
  : typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v) ? v.replace("T", " ").slice(0, 19) : v;
const roleOf = r => String(r || "other").split("/")[0];
const opts = a => a.map(o => "<option>" + esc(o) + "</option>").join("");

function tbl(el, rows, cols, click, page) {
  page = page || 0;
  const n = Math.max(1, Math.ceil(rows.length / PAGE));
  let h = '<div class="wrap"><table><tr>' + cols.map(c => '<th title="' + esc(c) + '">' + esc(LABEL[c] || c) + "</th>").join("") + "</tr>";
  rows.slice(page * PAGE, (page + 1) * PAGE).forEach((r, i) => {
    h += "<tr" + (click ? ' class="click" data-i="' + (page * PAGE + i) + '"' : "") + ">" +
      cols.map(c => "<td>" + (c === "source_label" && r[c] ? '<span class="badge">' + esc(r[c]) + "</span>" : esc(fmt(r[c]))) + "</td>").join("") + "</tr>";
  });
  if (!rows.length) h += '<tr><td colspan="' + cols.length + '" class="note">ไม่มีรายการ</td></tr>';
  h += "</table></div>";
  if (n > 1) h += '<div class="pager note">หน้า ' + (page + 1) + " / " + n + " (" + rows.length + ' แถว) <button data-p="' +
    (page - 1) + '"' + (page ? "" : " disabled") + '>ก่อนหน้า</button><button data-p="' + (page + 1) + '"' +
    (page < n - 1 ? "" : " disabled") + ">ถัดไป</button></div>";
  el.innerHTML = h;
  el.querySelectorAll("[data-p]").forEach(b => b.onclick = () => tbl(el, rows, cols, click, +b.dataset.p));
  if (click) el.querySelectorAll("tr[data-i]").forEach(tr => tr.onclick = () => click(rows[+tr.dataset.i]));
}
function count(rows, k) { const m = {}; rows.forEach(r => { m[r[k]] = (m[r[k]] || 0) + 1; }); return m; }
function showTab(t) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("on", b.dataset.tab === t));
  document.querySelectorAll("main section").forEach(s => s.classList.toggle("on", s.id === t));
}

function summary() {
  const F = D.findings, P = count(F, "priority"), Rk = count(F, "risk"), pl = count(D.plan, "decision");
  const card = (t, v) => '<div class="card">' + esc(t) + "<b>" + esc(v) + "</b></div>";
  let h = '<div class="cards">' + card("Finding ทั้งหมด", F.length) +
    ["สูง", "กลาง", "ต่ำ"].map(p => card("Priority " + p, P[p] || 0)).join("") +
    (IS_E ? card("เครือข่าย (Mule network)", D.mule_networks.length) : "") + card("การ์ดที่รัน / Skip", (pl.Run || 0) + " / " + (pl.Skip || 0)) + "</div>";
  h += "<h3>Finding ตามความเสี่ยง</h3><div id='sR'></div>";
  h += '<p class="note">ทุก Finding มีสถานะ "รอ Human Review" — Priority มาจาก Confidence (จำนวนกลุ่มวิธีวิเคราะห์ที่ให้สัญญาณตรงกัน' +
    " และความครบของแหล่งข้อมูล) ร่วมกับ Materiality (ยอดเงินที่เกี่ยวข้องเทียบกับฐานที่ผู้ใช้ยืนยัน) ตาม AIDA-14</p>";
  h += (D.limits ? '<p class="warn">' + esc(D.limits) + "</p>" : "") + (D.card_notes || []).concat(D.flow_notes).map(n => '<p class="warn">' + esc(n) + "</p>").join("");
  h += "<h3>Analysis Plan (Run / Skip พร้อมเหตุผล)</h3><div id='sP'></div><h3>Materiality</h3><div id='sM'></div>";
  $("sum").innerHTML = h;
  tbl($("sR"), (D.risk_names ? Object.keys(Rk).sort() : Object.keys(RISK)).map(r => ({risk: r, name: RISK[r], findings: Rk[r] || 0})), ["risk", "name", "findings"]);
  tbl($("sP"), D.plan, ["recipe_id", "decision", "reason", "missing"]);
  tbl($("sM"), D.materiality, ["item", "value", "detail"]);
}

function findings() {
  const all = k => ["ทั้งหมด"].concat([...new Set(D.findings.map(f => f[k]))].sort());
  $("fP").innerHTML = opts(all("priority")); $("fR").innerHTML = opts(all("risk"));
  const go = () => {
    const p = $("fP").value, r = $("fR").value;
    const rows = D.findings.filter(f => (p === "ทั้งหมด" || f.priority === p) && (r === "ทั้งหมด" || f.risk === r));
    tbl($("fT"), rows, ["finding_id", "entity_type", "entity_id", "risk", "period", "exposure", "confidence", "materiality", "priority", "network_id", "review_reason"]
      .concat(D.findings.some(f => f.source_label) ? ["source_label"] : []), showFinding);
    $("fD").innerHTML = '<p class="note">คลิกแถวเพื่อดู Evidence และ record_refs</p>';
  };
  $("fP").onchange = go; $("fR").onchange = go; go();
}
function showFinding(f) {
  showTab("fnd");
  const ids = new Set(f.evidence_ids || []), ev = D.evidence.filter(e => ids.has(e.evidence_id));
  $("fD").innerHTML = "<h3>" + esc(f.finding_id) + " · " + esc(f.entity_id) + " · " + esc(RISK[f.risk] || f.risk) + "</h3><p>" +
    esc(f.review_status) + " — " + esc(f.review_reason) + (f.source_label ? ' <span class="badge">' + esc(f.source_label) + "</span> ยังไม่ผ่านการรับรอง" : "") +
    "</p><div id='fE'></div><h3>record_refs (tx_id) " +
    (f.record_refs || []).length + " รายการ</h3><div class='refs'>" + esc((f.record_refs || []).join(", ")) + "</div>";
  tbl($("fE"), ev, ["evidence_id", "recipe_id", "skill_family", "period", "metric", "value", "threshold", "explanation", "record_refs"]);
  $("fD").scrollIntoView({block: "nearest"});
}

function networks() {
  $("legend").innerHTML = Object.values(ROLE).map(([t, c]) => '<span><i class="dot" style="background:' + c + '"></i>' + esc(t) + "</span>").join("") +
    '<span class="note">บทบาทเป็นข้อสังเกตจากธุรกรรม ไม่ใช่ข้อสรุป · คลิก node เพื่อดู Finding</span>';
  $("netV").innerHTML = D.mule_networks.length ? D.mule_networks.map((n, k) => "<h3>" + esc(n.network_id) + " · สมาชิก " + n.member_accts.length +
    " บัญชี · ธุรกรรมภายใน " + esc(fmt(n.internal_tx_count)) + " รายการ รวม " + esc(fmt(n.internal_amount)) + " · " +
    esc(n.period_start) + " ถึง " + esc(n.period_end) + "</h3>" + (n.member_accts.length > NET_DRAW_MAX ? '<p class="warn">สมาชิก ' +
    n.member_accts.length + " บัญชี มากกว่า " + NET_DRAW_MAX + " บัญชี จึงแสดงเป็นตารางแทนภาพ — ดูความเชื่อมโยงทั้งหมดใน nodes.csv / edges.csv" +
    ' (นำเข้าเครื่องมือ graph ได้)</p><div class="members" id="nm' + k + '"></div>' : netSvg(n, k))).join("") : '<p class="note">ไม่พบเครือข่าย</p>';
  D.mule_networks.forEach((n, k) => { if (n.member_accts.length > NET_DRAW_MAX) tbl($("nm" + k), n.member_accts.map(a => ({account: a,
    role: n.roles[a] || "other", finding_ids: findingsOf(a).map(f => f.finding_id)})), ["account", "role", "finding_ids"], r => showNode(n, r.account)); });
  document.querySelectorAll("circle[data-k]").forEach(c => c.onclick = () => {
    const n = D.mule_networks[+c.dataset.k]; showNode(n, n.member_accts[+c.dataset.m]);
  });
}
function netSvg(n, k) {
  const M = n.member_accts, W = 560, H = 400, R = Math.min(W, H) / 2 - 60, r = 16, pos = {}, pairs = {};
  M.forEach((a, i) => { const t = 2 * Math.PI * i / M.length - Math.PI / 2; pos[a] = [W / 2 + R * Math.cos(t), H / 2 + R * Math.sin(t)]; });
  D.edges.filter(e => e.network_id === n.network_id).forEach(e => { const key = JSON.stringify([e.source, e.target]); pairs[key] = (pairs[key] || 0) + e.amount; });
  let s = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" style="max-width:' + W + 'px" role="img" aria-label="' + esc(n.network_id) +
    '"><defs><marker id="ar' + k + '" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="#94a3b8"/></marker></defs>';
  Object.keys(pairs).forEach(key => {
    const [a, b] = JSON.parse(key); if (!pos[a] || !pos[b]) return;
    const [x1, y1] = pos[a], [x2, y2] = pos[b], d = Math.hypot(x2 - x1, y2 - y1) || 1;
    s += '<line x1="' + (x1 + (x2 - x1) * r / d) + '" y1="' + (y1 + (y2 - y1) * r / d) + '" x2="' + (x2 - (x2 - x1) * (r + 3) / d) + '" y2="' +
      (y2 - (y2 - y1) * (r + 3) / d) + '" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#ar' + k + ')"><title>' +
      esc(a + " → " + b + " รวม " + fmt(pairs[key])) + "</title></line>";
  });
  M.forEach((a, i) => {
    const [x, y] = pos[a], role = n.roles[a] || "other";
    s += '<circle data-k="' + k + '" data-m="' + i + '" cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + (ROLE[roleOf(role)] || ROLE.other)[1] +
      '"><title>' + esc(a + " · " + role) + '</title></circle><text x="' + x + '" y="' + (y + r + 14) + '" text-anchor="middle" font-size="12">' + esc(a) + "</text>";
  });
  return s + "</svg>";
}
const findingsOf = a => D.findings.filter(f => f.entity_id === a || (f.entity_type === "network" && (f.member_accts || []).includes(a)));
function showNode(n, a) {
  const F = findingsOf(a);
  const role = n.roles[a] || "other";
  $("netD").innerHTML = "<h3>บัญชี " + esc(a) + " · " + esc(n.network_id) + " · บทบาท " + esc(role) + " (" +
    esc((ROLE[roleOf(role)] || ROLE.other)[0]) + ")</h3><p class='note'>คลิก Finding เพื่อดู Evidence</p><div id='nF'></div>";
  tbl($("nF"), F, ["finding_id", "entity_id", "risk", "period", "exposure", "priority", "review_reason"], showFinding);
}

function flows() {
  const ids = [...new Set(D.flows.map(r => r.trace_id))];
  if (!ids.length) { $("tL").style.display = "none"; $("tV").innerHTML = '<p class="note">ไม่มีการไล่เส้นทางเงินในรอบนี้</p>'; return; }
  $("tS").innerHTML = opts(ids);
  const go = () => {
    const id = $("tS").value, rows = D.flows.filter(r => r.trace_id === id), f = rows[0];
    const hops = [...new Set(rows.map(r => r.hop))].sort((a, b) => a - b);
    $("tN").innerHTML = '<p class="note">' + (f.direction === "forward" ? "ไปข้างหน้า: เงินจากบัญชี " + esc(f.start_acct) + " ไปที่ใด"
      : "ย้อนกลับ: เงินที่เข้าบัญชี " + esc(f.start_acct) + " มาจากที่ใด") + " · ทอดที่ 1 อยู่ซ้ายสุด · เส้นทางเงินเป็นข้อมูลประกอบการสอบสวน ไม่ใช่ข้อสรุป</p>" +
      D.flow_notes.filter(n => n.indexOf(id + ":") === 0).map(n => '<p class="warn">' + esc(n) + "</p>").join("");
    $("tV").innerHTML = hops.map(h => {
      const hr = rows.filter(r => r.hop === h);
      return '<div class="hop"><h3>ทอดที่ ' + esc(h) + " (" + hr.length + " รายการ)</h3>" + hr.slice(0, HOP_CAP).map(r => '<div class="tx"><b>' +
        esc(r.from_acct) + " → " + esc(r.to_acct) + "</b><br>" + esc(fmt(r.amount)) + " · " + esc(fmt(r.ts)) + "<br>tx_id " + esc(r.tx_id) + "</div>").join("") +
        (hr.length > HOP_CAP ? '<p class="note">แสดง ' + HOP_CAP + " รายการแรกจาก " + hr.length + " — ดูทั้งหมดใน flows.csv หรือ sheet Money_Flow</p>" : "") + "</div>";
    }).join("");
  };
  $("tS").onchange = go; go();
}

function intake() {
  const I = D.intake;
  let h = '<p class="note">สรุปสิ่งที่ผู้ตรวจสอบยืนยันก่อนวิเคราะห์ (Intake) — ตัวเลขและข้อความมาจาก engine</p>' +
    "<h3>Intake Review</h3><div id='iR'></div><h3>Data Dictionary</h3><div id='iD'></div><h3>Data Request</h3><div id='iQ'></div>" +
    '<h3>โหมดสำรวจ <span class="badge">จากโหมดสำรวจ</span> ยังไม่ผ่านการรับรอง</h3>';
  const X = D.exploratory || [];
  h += X.length ? X.map(x => '<div class="xp"><h4>' + esc(x.explore_id) + " · " + esc(x.question) + (x.promoted === "ใช่" ? " · เลื่อนเป็น Finding โดย " +
    esc(x.promoted_by) + " (" + esc(x.promoted_finding) + ")" : "") + "</h4><pre>" + esc(x.code) + '</pre><p class="note">ผล: ' + esc(x.result_summary) +
    "</p>" + (x.note ? '<p class="note">หมายเหตุ: ' + esc(x.note) + "</p>" : "") + (x.promote_reason ? '<p class="note">เหตุผลที่เลื่อน: ' + esc(x.promote_reason) +
    "</p>" : "") + '<p class="note">เวลา ' + esc(x.time) + "</p></div>").join("") : '<p class="note">ไม่มีการวิเคราะห์ในโหมดสำรวจ</p>';
  $("intake").innerHTML = h;
  tbl($("iR"), I.review, ["section", "item", "detail"]);
  tbl($("iD"), I.dictionary, ["table", "column", "meaning", "role", "code_values", "confirmed_by", "confirmed_at"]);
  tbl($("iQ"), I.requests, ["no", "risk_id", "request"]);
}
if (D.intake) {
  const b = document.createElement("button"), s = document.createElement("section");
  b.dataset.tab = "intake"; b.textContent = "Intake"; s.id = "intake";
  document.querySelector('nav button[data-tab="sum"]').after(b); $("sum").after(s);
}
if (!IS_E) {
  document.querySelectorAll('nav button[data-tab="net"], nav button[data-tab="flow"], #net, #flow').forEach(e => e.remove());
  document.querySelector("h1").textContent = "AIDA · ข้อสังเกตที่ควรตรวจสอบเพิ่มเติมจากข้อมูลรายการ";
}
$("meta").textContent = "run_id " + D.run_id + " · Registry v" + D.registry_version + " · รูปแบบวันที่ที่ใช้แปลง " + ((D.prep || {}).date_format || "-");
document.querySelectorAll("nav button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
if (D.intake) intake();
summary(); findings();
if (IS_E) { networks(); flows(); }
tbl($("log"), D.run_log, ["run_id", "timestamp", "stage", "status", "detail", "recipe_id", "recipe_version", "registry_version", "pack_version", "input_sha256"]);
</script>
</body>
</html>
<!-- END-OF-TEMPLATE -->
```

## ข้อห้าม (Guardrails)
- ห้ามตัดป้ายเตือนข้อมูลอ่อนไหวหรือข้อจำกัดของการหาเครือข่ายออกจาก output ใด ๆ และห้ามปิดบัง/แก้ข้อมูลเองโดยไม่แจ้ง (การปิดบังทำได้ที่การ์ด OUT-* จุดเดียวตามนโยบายองค์กร)
- ใช้ template ตามตัวอักษร ห้ามเขียน Dashboard ขึ้นเอง ห้ามเพิ่มการโหลด script / font / รูปจากภายนอก — ดึง template ไม่ครบ (ไม่มี `<!-- END-OF-TEMPLATE -->`) ให้ดึงใหม่
- ถ้อยคำทุก output เป็นสัญญาณให้ตรวจสอบเพิ่มเติมตาม AIDA-11 เช่น "สอดคล้องกับ Mule Account pattern" — ห้ามใช้คำว่า "บัญชีม้า" หรือคำกล่าวหาว่าทุจริต และ collector / feeder เป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป
- ห้ามเปลี่ยนลำดับ sheet หรือคอลัมน์ CSV นอกที่กำหนดในไฟล์นี้ และห้ามแต่ง tx_id ที่ไม่มีในข้อมูลจริง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-19 Pipeline Recipes (การ์ด OUT-BUNDLE, OUT-WORKBOOK, OUT-NETWORK-CSV, OUT-DASHBOARD)
- AIDA-17 Data & Evidence Schema (คอลัมน์ Evidence / Finding / Mule Network / Money Flow trail / Run Log)
- AIDA-12 Output Framework (หลักการ output)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ไม่กล่าวหา)
- AIDA-14 Configuration Registry (`FLOW.MAX_TRAIL_ROWS`, `ASSESS.CLEARLY_TRIVIAL`)
