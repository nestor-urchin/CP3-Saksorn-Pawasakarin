# AIDA Phase B1 — Use Case 1: Potential Unusual Transactions across Mule Accounts

- วันที่: 2026-11-03
- สถานะ: รอผู้ใช้ตรวจ (Draft for review) — ฉบับที่ 2 (ปรับเป็น use case-driven)
- ต่อยอดจาก: `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md` (ระยะ A, merged ใน PR #2)

---

## 1. เป้าหมาย (Intent)

ให้ AIDA ใน Microsoft 365 Copilot Agent Builder **วิเคราะห์ข้อมูลธุรกรรมจริง** ด้วย Code Interpreter เพื่อชี้
**ธุรกรรมที่อาจผิดปกติซึ่งวิ่งข้ามกลุ่มบัญชีที่มีรูปแบบ Mule Account** — ทั้งระดับบัญชีและระดับเครือข่าย
โดยยังคงหลักการระยะ A ทั้งหมด (ไม่กล่าวหา, ค่ามาตรฐานจาก AIDA-14, แยก C/M/P, Skip ต้องมีเหตุผล, มนุษย์เป็นผู้ตัดสิน)

### Roadmap ระยะ B (ขับเคลื่อนด้วย use case)
| ช่วง | Use case | สถานะ |
|---|---|---|
| **B1** | **Potential Unusual Transactions across Mule Accounts** | spec นี้ |
| B2 | Analysis of Anomalous Bill Payment Transactions across Auto Loan Accounts | spec แยกหลัง B1 — ใช้ผล Mule ของ B1 เป็น input (เช่น ผู้ชำระค่างวดเป็นบัญชีที่เข้ารูปแบบ Mule) |

### ข้อตกลงหลัก
| หัวข้อ | ข้อตกลง |
|---|---|
| ข้อมูล | `transactions` (บังคับ) + `accounts` (ไม่บังคับ: acct_id, opened_at, account_type) — **ไม่มีข้อมูลระบุตัวตน** (บัตรประชาชน เบอร์โทร ที่อยู่ อุปกรณ์) จึงหาเครือข่ายจากความสัมพันธ์ทางธุรกรรมเท่านั้น |
| ช่องทางข้อมูล | ไฟล์แนบในแชท และไฟล์ใน SharePoint/OneDrive |
| วิธีวิเคราะห์ | สูตรสถิติและกฎที่ตายตัว (ไม่ใช้ ML ใน B1) — LLM ไม่คำนวณ ตัวเลขทุกตัวมาจากโค้ดในการ์ด |
| ที่มาของโค้ด | **การ์ดสูตร (recipe) สั้นแยกตามเทคนิค** เก็บใน Knowledge, โค้ดตายตัว + เวอร์ชัน, ทดสอบใน repo |
| Output | Audit Workbook (.xlsx) + Network Investigation Package (.csv) + HTML Interactive Dashboard (ไฟล์เดียว) |
| ข้อมูลอ่อนไหว | **แสดงข้อมูลเต็มทุก output** (ผู้ใช้ตัดสินใจ) — องค์กรควบคุมการเข้าถึงเอง; ทุก output มีป้ายเตือน |
| Materiality | ผู้ใช้ระบุที่จุดยืนยัน 1: แบบ ก. ยอดเงินตรง หรือ ข. ตัวเลขฐาน + % ตาม AIDA-14; ไม่ระบุ → "ไม่ได้ประเมิน" |
| Money Flow | อัตโนมัติสำหรับ Finding Priority สูงสุด (จำกัดจำนวน) + ตามคำสั่งผู้ใช้ |
| ข้อจำกัด | Knowledge ≤ 20 ไฟล์ (B1 ใช้ครบ 20); Instructions ≤ 8,000 ตัวอักษร |

### เกณฑ์ความสำเร็จ
1. ผลทดสอบ Code Interpreter (spike, ข้อ 7.1) ผ่านทั้ง 4 ข้อ หรือมีการปรับ design ตามผล
2. ทุก recipe ผ่าน unit test บนข้อมูลตัวอย่าง: พบกรณีที่ฝังไว้ และไม่แจ้งเตือนผิดในข้อมูลปกติ
3. End-to-end test สร้างไฟล์ output ครบที่เปิดได้ และจำนวน Unified Finding + Mule network ตรงกับเฉลย
4. `validate_pack.py` ผ่าน (รวมการตรวจใหม่ข้อ 7.4)
5. ผู้ใช้รัน eval ระยะ B ใน Copilot ผ่าน

### Assumption ที่ยังไม่ได้ยืนยัน (ตรวจใน spike)
- Code Interpreter ของ tenant รัน pandas ได้ และสร้างไฟล์ .xlsx/.html ให้ดาวน์โหลดได้
- Code Interpreter อ่านไฟล์จาก SharePoint/OneDrive ได้
- Copilot ดึง recipe ≤ 40 บรรทัด และ template Dashboard มาครบโดยไม่ถูกตัด
- เวอร์ชัน pandas ของ Code Interpreter ≥ 1.5

---

## 2. ขอบเขต

### ทำใน B1
- 34 recipes (ข้อ 4.3: การ์ดวิเคราะห์ 15 ใบใน AIDA-18 + การ์ด pipeline/ช่วย/output 19 ใบใน AIDA-19), ไฟล์ Knowledge ใหม่ 4 ไฟล์ (ข้อ 3), แก้ไฟล์เดิม 4 ไฟล์
- ข้อมูลตัวอย่างฝังความผิดปกติ + เฉลย, unit/end-to-end tests, spike kit, eval ระยะ B

### ไม่ทำใน B1
- Use case 2 Auto Loan (B2)
- ข้อมูล Vendor Master / AP / GL; การ์ด Sequence ของ vendor, Concentration ของ merchant, Shared identifier
- Forensic (Benford ฯลฯ), Rule-based, ML — ถ้าผู้ใช้ขอ AIDA ตอบว่ายังไม่รองรับใน B1 และให้คำปรึกษาแบบระยะ A
- การปิดบังข้อมูลอ่อนไหว (masking)

---

## 3. ไฟล์

### 3.1 Knowledge ใหม่ (ใช้ช่อง 16–19 → รวม 20 ไฟล์)
| # | ไฟล์ | เนื้อหา |
|---|---|---|
| 16 | `AIDA-16-output-templates.md` | โครง sheet ของ Workbook, คอลัมน์ CSV ของ Network Package, template HTML ของ Dashboard |
| 17 | `AIDA-17-data-evidence-schema.md` | คอลัมน์มาตรฐาน (4.1), schema Evidence / Finding / Mule Network / Run Log (4.4), รูปแบบ Data Reference, ตารางความเสี่ยง R1–R4 |
| 18 | `AIDA-18-analysis-recipes.md` | การ์ดวิเคราะห์ 15 ใบ |
| 19 | `AIDA-19-pipeline-recipes.md` | การ์ด Evidence builder, เตรียมข้อมูล, Gate, รวมผล, ประเมิน, Run Log, สร้าง output 19 ใบ (รวมการ์ดช่วย) |

ชื่อไฟล์ 17–19 เปลี่ยนจากที่สงวนไว้ในระยะ A ให้ตรงกับเนื้อหา

### 3.2 ไฟล์เดิมที่ต้องแก้
| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `AIDA-agent-instructions.md` | กฎข้อ 7 เปลี่ยนจาก "ไม่วิเคราะห์ข้อมูล" เป็นขั้นตอนวิเคราะห์ B1 (ข้อ 5) + ขอบเขตที่ยังไม่รองรับ + routing ของไฟล์ 16–19 |
| `AIDA-00-index-principles.md` | สารบัญไฟล์ 16–19 (ไม่ใช่ "สงวนไว้" อีกต่อไป) |
| `AIDA-14-configuration-registry.md` | v1.1: key ใหม่ (ข้อ 4.6) + หัวข้อ "Machine Config" (ข้อ 4.5) |
| `aida-knowledge/README.md` | ขั้นตอนระยะ B, ความเสี่ยงข้อมูลอ่อนไหว/PCI DSS, การรันเทสต์ |

### 3.3 ไฟล์ใน repo (ไม่อัปโหลด)
```
aida-knowledge/
├── spike/                         ← ชุดทดสอบ Code Interpreter (ข้อ 7.1)
├── samples/                       ← ข้อมูลตัวอย่าง + เฉลย (สร้างจากสคริปต์)
├── tests/make_sample_data.py, tests/test_recipes.py, tests/test_pipeline.py
└── tools/extract_recipes.py       ← ดึงโค้ดจาก AIDA-18/19 มาให้ tests ใช้
```

---

## 4. รายละเอียดการออกแบบ

### 4.1 คอลัมน์มาตรฐาน (input)
| ตาราง | คอลัมน์ | บังคับ |
|---|---|---|
| `transactions` | tx_id, ts, from_acct, to_acct, amount, currency, channel | ใช่ (currency, channel ไม่บังคับ) |
| `accounts` | acct_id, opened_at, account_type | ไม่ |

- AIDA เสนอการจับคู่คอลัมน์ของผู้ใช้ → ผู้ใช้ยืนยัน (จุดยืนยัน 1)
- ขาดคอลัมน์ที่การ์ดต้องใช้ → การ์ดนั้น Skip + reason
- record key: `tx_id` (transactions), `acct_id` (accounts) — ไม่มี `tx_id` → STOP ตาม `GATE.TRACE.REQUIRED`

### 4.2 รูปแบบการ์ด (recipe contract)
```python
# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.FUNNEL | Input: transactions(from_acct, to_acct, amount, ts)
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    ...
    return evidence_rows(...)
```
- บรรทัดหัว 2 บรรทัดตามรูปแบบนี้ (validator ตรวจ)
- ชื่อฟังก์ชัน = recipe ID ตัวพิมพ์เล็ก แทน `-` ด้วย `_`; การ์ดวิเคราะห์ใช้ signature `(tables: dict, cfg: dict) -> pd.DataFrame`
- การ์ดที่ต้องใช้ผลของการ์ดอื่น (MULE-PATTERN, MULE-CROSS-TX, MULE-NETWORK) รับผลผ่าน `tables["evidence"]`
- ใช้ได้เฉพาะ pandas, numpy, Python standard library (+ openpyxl สำหรับ OUT-WORKBOOK) — **ไม่ใช้ networkx / scikit-learn**
- เข้ากันได้กับ pandas ≥ 1.5
- ห้ามมีตัวเลขเกณฑ์ในโค้ด: อ่านจาก `cfg[<registry key>]` เท่านั้น
- ≤ 40 บรรทัดโค้ดต่อการ์ด (ยกเว้น template Dashboard ใน AIDA-16)
- การ์ดวิเคราะห์ส่งคืน DataFrame ตาม Evidence schema; DataFrame ว่าง = ไม่พบ

### 4.3 การ์ด 34 ใบ
เดิมวางแผน 25 ใบ ระหว่างพัฒนาแยกฟังก์ชันช่วยออกเป็นการ์ดของตัวเองเพื่อให้แต่ละใบ ≤ 40 บรรทัด จึงเป็น 34 ใบ (AIDA-18: 15 ใบ, AIDA-19: 19 ใบ)
| กลุ่ม | การ์ด | วิธี | ไฟล์ |
|---|---|---|---|
| เตรียมข้อมูล + Gate | `PREP-MAP`, `PROF-PROFILE`, `GATE-CAPABILITY` | จับคู่คอลัมน์, Dataset Profile + Gate, Run/Skip ทุกการ์ด | AIDA-19 |
| Statistical | `STAT-MAD` | Modified Z-Score ของ amount ภายใน channel (หรือทั้งชุดถ้าไม่มี channel) | AIDA-18 |
| Behavioral / Temporal | `BEH-VELOCITY` | จำนวนรายการ/วัน/บัญชี เทียบ baseline ของบัญชีเดียวกัน (± `BEH.DEVIATION`) | AIDA-18 |
| | `BEH-SPIKE` | ยอด/เดือน/บัญชี เทียบ baseline ของบัญชีเดียวกัน | AIDA-18 |
| | `TEMP-OFFHOURS` | กฎช่วงเวลานอกเวลาทำการ/วันหยุด | AIDA-18 |
| Network | `NET-CYCLE` | DFS เขียนเอง หาวงเงินหมุนวน 2–5 ทอดในช่วงเวลา | AIDA-18 |
| | `NET-FUNNEL` | นับแหล่งเงินเข้า + อัตราส่วนเงินออก/เข้าในช่วงเวลา | AIDA-18 |
| Mule (บัญชี) | `MULE-DWELL` | ระยะเวลาที่เงินอยู่ในบัญชี (จับคู่เงินเข้ากับเงินออกถัดไปตามลำดับเวลา) | AIDA-18 |
| | `MULE-NEW-ACCT` | อายุบัญชีตอนเริ่มมีรายการมาก (basis = opened_at หรือ first_seen) | AIDA-18 |
| | `MULE-PATTERN` | นับสัญญาณต่อบัญชีต่อเดือน ≥ `MULE.MIN_SIGNALS` | AIDA-18 |
| Mule (ข้ามบัญชี) | `MULE-CROSS-TX` | ธุรกรรม mule↔mule, collector, feeder (ข้อ 4.7) | AIDA-18 |
| | `MULE-NETWORK` | union-find รวม mule + collector + feeder ที่เชื่อมกันเป็นกลุ่ม | AIDA-18 |
| Counterparty | `CPTY-PROFILE` | จำนวนคู่ค้า, สัดส่วนคู่ค้าใหม่, ส่วนแบ่งคู่ค้าสูงสุด ต่อบัญชีต่อเดือน | AIDA-18 |
| | `CPTY-NEW-LARGE` | ยอดโอนครั้งแรกให้คู่ค้าใหม่ ≥ ตัวคูณ × median ของบัญชี | AIDA-18 |
| Money Flow | `FLOW-TRACE` | BFS ตามเวลา ไปข้างหน้า/ย้อนกลับ ≤ `FLOW.MAX_HOPS` ทอด (อัตโนมัติ + ตามคำสั่ง) | AIDA-18 |
| | `FLOW-LAYERING` | เส้นทาง ≥ 3 ทอดที่แต่ละทอดส่งต่อ ≥ `FLOW.MIN_PASS_RATIO` | AIDA-18 |
| Evidence builder (ใช้ร่วม) | `CORE-EVIDENCE` | ฟังก์ชันสร้างแถว Evidence ตาม schema 4.4 ให้ทุกการ์ดวิเคราะห์ใช้ร่วมกัน (โหลดก่อนการ์ดอื่น) | AIDA-19 |
| รวมผล + ประเมิน | `UNIFY-FINDINGS`, `ASSESS-CMP` | จัดกลุ่ม entity + risk + เดือน; ตาราง Priority | AIDA-19 |
| Output + Log | `OUT-WORKBOOK`, `OUT-NETWORK-CSV`, `OUT-DASHBOARD`, `LOG-RUN` | | AIDA-19 |
| การ์ดช่วย (เพิ่มระหว่างพัฒนา) | `CORE-BASELINE` | ฟังก์ชัน baseline ร่วมของ BEH-VELOCITY / BEH-SPIKE | AIDA-19 |
| | `PREP-DATE`, `PREP-TS` | แยกและแปลงวันที่ (พ.ศ., เดือนไทย, dd/mm/yyyy, Excel serial) ตัดสินรูปแบบครั้งเดียวต่อคอลัมน์ ให้ PREP-MAP ใช้ | AIDA-19 |
| | `PROF-CHECKS` | เงื่อนไข STOP ของ PROF-PROFILE | AIDA-19 |
| | `GATE-VOLUME` | ตรวจปริมาณข้อมูลที่ทำให้การ์ดไม่มีผลแน่นอน → Skip + reason ให้ GATE-CAPABILITY | AIDA-19 |
| | `UNIFY-REFS` | ทำให้ record_refs เป็น list ของ tx_id เสมอ ให้ UNIFY-FINDINGS / ASSESS-CMP / OUT-BUNDLE | AIDA-19 |
| | `SELECT-AUTO-TRACE` | เลือกบัญชี (R2/R3 Priority สูงสุด ≤ `FLOW.AUTO_MAX_ENTITIES`) สำหรับ FLOW-TRACE อัตโนมัติ | AIDA-19 |
| | `OUT-BUNDLE` | รวมผลทุกขั้นเป็น bundle + ป้ายเตือน/ข้อจำกัด ให้การ์ด OUT-* | AIDA-19 |
| | `OUT-CELL` | กันข้อความที่ Excel อ่านเป็นสูตร (formula injection) ใน Workbook และ CSV | AIDA-19 |

### 4.4 Schema (AIDA-17)
| Schema | คอลัมน์ |
|---|---|
| Evidence | evidence_id, run_id, recipe_id, recipe_version, skill_family, entity_type (account / network), entity_id, risk, period (YYYY-MM), metric, value, threshold, registry_key, registry_version, explanation, record_refs (list ของ tx_id), data_ref |
| Finding | finding_id, entity_type, entity_id, risk, period, evidence_ids, skill_families, exposure, confidence, materiality, priority, review_status, review_reason, network_id (ถ้าบัญชีอยู่ในเครือข่าย) |
| Mule Network | network_id, member_accts, roles (mule / collector / feeder ต่อบัญชี), internal_tx_count, internal_amount, period_start, period_end |
| Money Flow trail | trace_id, start_acct, direction, hop, from_acct, to_acct, amount, ts, tx_id |
| Run Log | run_id, timestamp, stage (1–18), status (OK / STOP / SKIP / REVIEW), detail, recipe_id, recipe_version, registry_version, pack_version, input_sha256 |

**Data Reference**
- ไฟล์แนบในแชท: `chat:<ชื่อไฟล์>#<sheet>@<เวลาอัปโหลด ISO>|sha256:<hash>`
- SharePoint/OneDrive: `sp:<URL>#<sheet>@<เวอร์ชันไฟล์ ถ้ามี>|sha256:<hash>`

**ความเสี่ยงใน B1**
| Risk | ชื่อ | entity | การ์ดที่ให้ Evidence |
|---|---|---|---|
| R1 | การเคลื่อนย้ายเงินผิดปกติ | account | STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, NET-CYCLE, NET-FUNNEL, FLOW-LAYERING, MULE-DWELL, MULE-NEW-ACCT |
| R2 | รูปแบบบัญชีรับ-ส่งต่อเงิน (Mule Account pattern) | account | MULE-PATTERN (+ สัญญาณที่ถูกรวมเข้ามา) |
| R3 | ธุรกรรมข้ามกลุ่มบัญชี Mule (Mule network) | network | MULE-CROSS-TX, MULE-NETWORK |
| R4 | ความผิดปกติของคู่ค้า (Counterparty) | account | CPTY-PROFILE, CPTY-NEW-LARGE |

FLOW-TRACE ไม่สร้าง Evidence — สร้าง Money Flow trail สำหรับการสอบสวน

### 4.5 Machine Config ใน AIDA-14 (v1.1)
- หัวข้อ `## Machine Config (สำหรับ recipe)` เป็น code block JSON เดียว
- key ระดับบนสุด = registry key ที่มีในตาราง AIDA-14 เท่านั้น (validator ตรวจ)
- ค่าเป็นตัวเลข/โครงสร้างที่ตรงกับความหมายในตาราง เช่น `"NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7}`, `"TEMP.OFF_HOURS": {"start": "08:00", "end": "18:00", "weekend": true}`, `"BEH.BASELINE.MIN_PERIODS": {"velocity_days": 6, "spike_months": 6}`
- `"REGISTRY.VERSION": "1.1"` อยู่ใน JSON เพื่อบันทึกลง Run Log
- ค่าตัวเลขหลักใน JSON ต้องตรงกับตาราง (ตรวจโดย test)

### 4.6 Registry keys ใหม่ (AIDA-14 v1.1 — แหล่งที่มา: แนวปฏิบัติทั่วไป ไม่มีมาตรฐานทางการ)
| Key | ค่า | ความหมาย |
|---|---|---|
| `MULE.DWELL_HOURS` | 24 | เงินเข้าแล้วออกภายในกี่ชั่วโมง ถือว่า dwell สั้น |
| `MULE.DWELL_MIN_PAIRS` | 3 | จำนวนคู่เงินเข้า-เงินออกที่ dwell สั้นขั้นต่ำ จึงนับเป็นสัญญาณ (Ruling R-1) |
| `MULE.NEW_ACCT_DAYS` | 30 | บัญชีอายุไม่เกินกี่วันเมื่อเริ่มมีรายการมาก |
| `MULE.NEW_ACCT_MIN_TX` | 20 | จำนวนรายการขั้นต่ำภายใน `MULE.NEW_ACCT_DAYS` ที่ถือว่า "มีรายการมาก" (Ruling R-1) |
| `MULE.MIN_SIGNALS` | 3 (จาก 5 สัญญาณ) | จำนวนสัญญาณขั้นต่ำที่ถือว่าเข้ารูปแบบ Mule |
| `MULE.CROSS.MIN_LINKS` | 2 | collector/feeder ต้องเชื่อมกับบัญชี Mule อย่างน้อยกี่บัญชี |
| `MULE.NETWORK.MIN_SIZE` | 3 | จำนวนบัญชีขั้นต่ำของกลุ่มเครือข่าย |
| `CPTY.NEW_RATIO` | 50% | สัดส่วนคู่ค้าใหม่ต่อเดือนที่ถือว่าผิดปกติ |
| `CPTY.NEW_LARGE.MULTIPLIER` | 5 | ตัวคูณ median ยอดของบัญชี สำหรับคู่ค้าใหม่ยอดสูง |
| `FLOW.MAX_HOPS` | 4 | ไล่เส้นทางเงินสูงสุดกี่ทอด |
| `FLOW.WINDOW_DAYS` | 7 | ช่วงเวลาที่ไล่เส้นทางเงิน |
| `FLOW.MIN_PASS_RATIO` | 90% | แต่ละทอดส่งต่อเงินอย่างน้อยเท่าไรจึงนับเป็น layering |
| `FLOW.AUTO_MAX_ENTITIES` | 10 | จำนวนบัญชีที่ไล่เส้นทางเงินอัตโนมัติ |

key ที่เพิ่มระหว่างพัฒนา (คัดลอกจาก AIDA-14 v1.1):

| Key | ค่า | ความหมาย |
|---|---|---|
| `NET.CYCLE.MAX_PATHS` | 100,000 | จำนวนเส้นทางสูงสุดที่ NET-CYCLE ค้นหา ถึงขีดนี้แล้วหยุดและแจ้งว่าผลอาจไม่ครบ — ที่มา: ขีดจำกัดทางเทคนิคเพื่อป้องกันหน่วยความจำเต็ม |
| `BEH.VELOCITY.SD_FLOOR` | sqrt(mean) (Poisson) | ค่า SD ขั้นต่ำของ baseline จำนวนรายการต่อวัน (BEH-VELOCITY): ใช้ max(SD, √ค่าเฉลี่ย) — ที่มา: ความแปรปรวนของข้อมูลนับแบบ Poisson; Machine Config "none" = ไม่ใช้ค่าขั้นต่ำ |
| `FLOW.MAX_TRAIL_ROWS` | 5,000 | จำนวนแถวสูงสุดของ Money Flow trail ต่อการไล่ 1 ครั้ง ถึงขีดนี้แล้วหยุดและแจ้งว่าผลอาจไม่ครบ — ที่มา: ขีดจำกัดทางเทคนิคเพื่อให้ผลอ่านได้และไม่เกินเวลาประมวลผล |

### 4.7 Use case logic: Mule Accounts

**ระดับบัญชี — MULE-PATTERN (R2)**
| สัญญาณ | การ์ด |
|---|---|
| รับหลายแหล่ง → โอนออกเกือบหมด | NET-FUNNEL |
| เงินอยู่ในบัญชีสั้น (dwell time) | MULE-DWELL |
| บัญชีใหม่แล้วมีรายการมากทันที | MULE-NEW-ACCT |
| โอนถี่ผิดปกติ | BEH-VELOCITY |
| ทำรายการนอกเวลา | TEMP-OFFHOURS |
- นับสัญญาณต่อบัญชีต่อเดือน; ≥ `MULE.MIN_SIGNALS` → Evidence R2 ที่ระบุสัญญาณที่พบครบทุกตัว
- MULE-NEW-ACCT: มี `accounts.opened_at` → basis = opened_at; ไม่มี → basis = first_seen (วันที่เห็นธุรกรรมแรกในไฟล์) และ explanation ระบุข้อจำกัด
- **Mule absorption:** Evidence R1 ที่เป็นสัญญาณของบัญชีนั้นในเดือนเดียวกันถูกรวมเข้า Finding R2 (ไม่รายงานซ้ำใน R1)

**ข้ามบัญชี — MULE-CROSS-TX และ MULE-NETWORK (R3)**
- MULE-CROSS-TX ใช้รายการบัญชี R2 เป็นชุด "mule" แล้วหา:
  - **mule↔mule:** ธุรกรรมที่ผู้โอนและผู้รับเป็น mule ทั้งคู่
  - **collector:** บัญชี (ไม่ใช่ mule) ที่รับเงินจาก mule ≥ `MULE.CROSS.MIN_LINKS` บัญชี ภายใน `FLOW.WINDOW_DAYS`
  - **feeder:** บัญชี (ไม่ใช่ mule) ที่โอนเงินให้ mule ≥ `MULE.CROSS.MIN_LINKS` บัญชี ภายใน `FLOW.WINDOW_DAYS`
- MULE-NETWORK รวม mule + collector + feeder ที่เชื่อมด้วยธุรกรรมข้างต้นเป็นกลุ่ม (union-find); กลุ่มขนาด ≥ `MULE.NETWORK.MIN_SIZE` → **1 Finding R3 ต่อกลุ่ม** (entity_type = network)
- Finding R2 ของสมาชิกยังอยู่ (ระดับบัญชีสำหรับการทบทวนรายบัญชี) และอ้าง network_id
- ถ้อยคำ: "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern" — ห้ามใช้ "แก๊งบัญชีม้า"/"บัญชีม้า"; collector/feeder อธิบายเป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป

**Counterparty (R4)**
- CPTY-PROFILE: แจ้งเมื่อสัดส่วนคู่ค้าใหม่ ≥ `CPTY.NEW_RATIO` และบัญชีมีประวัติ ≥ จำนวนงวดขั้นต่ำ
- CPTY-NEW-LARGE: โอนให้คู่ค้าที่ไม่เคยติดต่อ ด้วยยอด ≥ `CPTY.NEW_LARGE.MULTIPLIER` × median ยอดของบัญชีนั้น

**Money Flow**
- FLOW-TRACE อัตโนมัติ: จากบัญชีใน Finding R2/R3 ที่ Priority สูงสุด ไม่เกิน `FLOW.AUTO_MAX_ENTITIES` บัญชี
- FLOW-TRACE ตามคำสั่ง: "ไล่เส้นทางเงินของบัญชี X" → output ฉบับใหม่ (run_id ใหม่ อ้าง run_id เดิม)
- FLOW-LAYERING → Evidence R1

### 4.8 การรวมผลและการประเมิน
- **Unify:** Evidence ที่ entity_id + risk + period (เดือน) เดียวกัน → 1 Finding; R3 จัดกลุ่มตาม network_id
- **Confidence:** สูง = skill_families ≥ 2 และ data_ref ครบทุก Evidence / กลาง = 1 skill family และ data_ref ครบ / ต่ำ = data_ref ไม่ครบ; R3 นับ skill family ของ Evidence ทุกสมาชิก
- **Exposure:** R1/R2/R4 = ผลรวม amount ของ record_refs ที่ไม่ซ้ำ; R3 = internal_amount ของเครือข่าย
- **Materiality:** เทียบ exposure กับฐานที่ผู้ใช้ระบุ ตามระดับใน AIDA-14; ไม่ระบุ → "ไม่ได้ประเมิน"
- **Priority:** ตาราง Priority ใน AIDA-14; Materiality "ไม่ได้ประเมิน" → Priority = ระดับ Confidence และ review_reason = "ไม่มีฐาน Materiality"
- **Human Review:** ทุก Finding มี review_status = "รอ Human Review"; R2/R3 และ Confidence ต่ำ ระบุ review_reason เพิ่ม

---

## 5. ขั้นตอนการทำงาน (Instructions กฎข้อ 7 ใหม่)
```
1. รับไฟล์ → sha256 + Data Reference
2. PREP-MAP → เสนอการจับคู่คอลัมน์
   ⏸ จุดยืนยัน 1: ผู้ใช้ยืนยัน mapping + ฐาน Materiality (แบบ ก. หรือ ข. หรือไม่ระบุ)
3. PROF-PROFILE → Dataset Profile; ไม่ผ่าน GATE.TRACE.REQUIRED → STOP
4. GATE-CAPABILITY → Analysis Plan (Run/Skip + เหตุผลทุกการ์ด)
   ⏸ จุดยืนยัน 2: ผู้ใช้ยืนยันแผน (เอาการ์ดออกได้)
5. รันการ์ดวิเคราะห์ระดับบัญชี → MULE-PATTERN → MULE-CROSS-TX → MULE-NETWORK → Evidence
6. UNIFY-FINDINGS → ASSESS-CMP
7. FLOW-TRACE อัตโนมัติ
8. OUT-WORKBOOK + OUT-NETWORK-CSV + OUT-DASHBOARD + LOG-RUN → ส่งไฟล์ + สรุปในแชท
9. (ตามคำสั่ง) ผู้ใช้สั่งไล่เส้นทางเงินบัญชีอื่น → FLOW-TRACE → output ฉบับใหม่
```
- ห้ามข้ามจุดยืนยันแม้ผู้ใช้ขอ (Human Accountable)
- ใช้โค้ดจากการ์ดตามตัวอักษร ห้ามเขียนโค้ดวิเคราะห์ใหม่; ดึงการ์ดมาไม่ครบ → แจ้งผู้ใช้และไม่รันการ์ดนั้น (SKIP + reason "ดึง recipe ไม่ครบ")
- บอกเสมอว่าค่าเกณฑ์เป็นค่ามาตรฐาน/ค่าตั้งต้นจาก AIDA-14

---

## 6. Output

### 6.1 Audit Workbook (.xlsx) — sheet ตามลำดับ
1. `README` — ป้ายเตือนข้อมูลอ่อนไหว, run_id, วิธีอ่านไฟล์
2. `Dataset_Profile` 3. `Analysis_Plan` 4. `Evidence` 5. `Findings` (คอลัมน์ว่าง reviewer, disposition, review_date) 6. `Mule_Networks` 7. `Money_Flow` 8. `Materiality` 9. `Run_Log`

### 6.2 Network Investigation Package (.csv)
- `nodes.csv`: node_id, role (mule / collector / feeder / other), network_id, finding_ids
- `edges.csv`: source, target, amount, ts, tx_id, network_id
- `flows.csv`: Money Flow trail (schema ข้อ 4.4)
- เฉพาะ subgraph ที่เกี่ยวกับ Finding

### 6.3 HTML Interactive Dashboard (ไฟล์เดียว, ไม่โหลดภายนอก)
- ป้ายเตือนข้อมูลอ่อนไหวบนสุด
- แท็บ: **สรุป** (จำนวน Finding ตาม Priority/Risk, จำนวนเครือข่าย, Run/Skip) · **Findings** (กรองได้, คลิกเห็น Evidence + record_refs) · **Mule Networks** (SVG ของแต่ละเครือข่าย สีตามบทบาท mule/collector/feeder, คลิก node เห็น Finding) · **Money Flow** (แผนภาพไหลซ้าย→ขวาตามทอด, เลือก trace ได้) · **Run Log**
- ข้อมูลฝังเป็น JSON; JavaScript เขียนเองในไฟล์
- ภาษาไทย, ไม่กล่าวหา, อธิบายตัวเลขเทคนิคเป็นภาษาธุรกิจ

---

## 7. การทดสอบ

### 7.1 Spike (งานแรก — ผู้ใช้รันใน Copilot)
`aida-knowledge/spike/`: `spike-transactions.csv` (200 แถว) + prompt 4 ข้อ + ตารางผล
1. ดึงการ์ด NET-FUNNEL จาก Knowledge มาครบและรันได้
2. อ่านไฟล์จาก SharePoint
3. สร้าง .xlsx ดาวน์โหลดได้
4. สร้าง .html จาก template ยาว และ template ถูกดึงมาครบ
+ บันทึกเวอร์ชัน pandas และขนาดไฟล์สูงสุดที่ทดลอง
ไม่ผ่านข้อใด → หยุดและปรับ design ก่อนทำต่อ

### 7.2 ข้อมูลตัวอย่าง (`tests/make_sample_data.py`, seed คงที่)
- ~5,000 ธุรกรรมปกติ, ~300 บัญชี
- ฝัง 9 กรณี:
  1. Funnel  2. Cycle 3 ทอด  3. ยอดโดดเด่น  4. Velocity  5. Off-hours
  6. Mule account เดี่ยว (บัญชีใหม่ + dwell สั้น + funnel + velocity)
  7. **Mule network**: mule 4 บัญชี + collector 1 + feeder 1
  8. คู่ค้าใหม่ยอดสูง  9. Layering chain 4 ทอด
- 2 ชุด: มีตาราง `accounts` และไม่มี (ทดสอบ basis = first_seen)
- ไฟล์เฉลย: การ์ดใดต้องพบ entity ใด, จำนวน Unified Finding และจำนวนเครือข่ายที่ต้องได้

### 7.3 Tests ใน repo
- `extract_recipes.py` ดึงโค้ดจาก AIDA-18/19 → tests รันโค้ดชุดเดียวกับที่ AIDA ใช้
- Unit ต่อการ์ด: พบกรณีที่ฝัง + ไม่มี false positive ในข้อมูลปกติ
- End-to-end: ไฟล์ output เปิดได้ (openpyxl อ่าน xlsx ได้, HTML มี JSON ที่ parse ได้, CSV มีคอลัมน์ครบ), จำนวน Finding และเครือข่ายตรงเฉลย
- Gate: ไม่มี ts → Temporal/Velocity/Dwell/Flow Skip + reason; ไม่มี tx_id → STOP; ไม่มี accounts → MULE-NEW-ACCT ใช้ first_seen

### 7.4 Validator เพิ่ม
- จำนวนไฟล์ Knowledge ≤ 20 (B1 = 20)
- หัวการ์ดตามรูปแบบ 4.2; โค้ดการ์ด ≤ 40 บรรทัด (ยกเว้น template ใน AIDA-16)
- key ใน `cfg[...]` และใน Machine Config มีอยู่ในตาราง AIDA-14
- การตรวจเดิมของระยะ A ยังทำงานครบ (รวมคำกล่าวหา — "บัญชีม้า" ใช้ได้เฉพาะใน Guardrails/ประโยคปฏิเสธ)

### 7.5 Eval ระยะ B (~10 ข้อ เพิ่มใน `eval-questions.md`)
- วิเคราะห์ไฟล์ตัวอย่าง → หยุดที่จุดยืนยัน 1 และ 2, ได้ไฟล์ครบ, Finding + เครือข่ายตรงเฉลย
- บัญชีเข้ารูปแบบ Mule → ใช้ "สอดคล้องกับ pattern" ไม่ใช่ "บัญชีม้า" + Human Review
- ถามบทบาท collector → อธิบายเป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป
- ไล่เส้นทางเงินของบัญชี X → trail + output ฉบับใหม่
- ไม่มีตาราง accounts → ระบุ basis = first_seen
- ไม่มีคอลัมน์เวลา → Skip + reason
- ขอข้ามการยืนยัน → ปฏิเสธ
- ขอ Benford / ML / ข้อมูล Auto Loan → ยังไม่รองรับใน B1
- ไม่ระบุ Materiality → "ไม่ได้ประเมิน"
- ขอปิดบังข้อมูล → แจ้งว่า B1 แสดงเต็มตามที่องค์กรกำหนด

---

## 8. ความเสี่ยงที่บันทึกไว้
| ความเสี่ยง | การรับมือ |
|---|---|
| ข้อมูลเต็มอยู่ในไฟล์ output — อยู่ในขอบเขต PCI DSS / PDPA | ผู้ใช้ตัดสินใจแสดงเต็ม; ป้ายเตือนทุก output; README บันทึกความเสี่ยง; เปลี่ยนเป็น masking ได้ที่การ์ด OUT-* จุดเดียว |
| ไม่มีข้อมูลระบุตัวตน → เครือข่ายที่เชื่อมด้วยข้อมูลร่วม (ไม่มีธุรกรรมระหว่างกัน) จะไม่ถูกพบ | ระบุข้อจำกัดใน Dashboard/README; เพิ่ม NET-SHARED-ID ได้ภายหลังเมื่อมีข้อมูล |
| ค่าตั้งต้นของ Mule/Flow ไม่มีมาตรฐานทางการ | ระบุแหล่งที่มา "แนวปฏิบัติทั่วไป" และแจ้งผู้ใช้ทุกครั้ง; องค์กรปรับใน AIDA-14 |
| Copilot ดึง recipe/template ไม่ครบ | spike ตรวจก่อน; Instructions ห้ามรันการ์ดที่ไม่ครบ |
| pandas ใน Code Interpreter เก่ากว่า repo | จำกัด API ที่ pandas ≥ 1.5; ยืนยันเวอร์ชันใน spike |
| ไฟล์ข้อมูลใหญ่เกินขีดจำกัดของ Code Interpreter | บันทึกขนาดที่ทดสอบได้ใน spike; README แนะนำแบ่งไฟล์ตามช่วงเวลา |
