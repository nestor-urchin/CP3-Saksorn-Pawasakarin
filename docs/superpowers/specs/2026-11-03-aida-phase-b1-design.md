# AIDA Phase B1 — Data Analysis Design Spec

- วันที่: 2026-11-03
- สถานะ: รอผู้ใช้ตรวจ (Draft for review)
- ต่อยอดจาก: `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md` (ระยะ A, merged ใน PR #2)

---

## 1. เป้าหมาย (Intent)

ให้ AIDA ใน Microsoft 365 Copilot Agent Builder **วิเคราะห์ข้อมูลจริง** ด้วย Code Interpreter ตาม workflow 18 ขั้น
โดยยังคงหลักการระยะ A ทั้งหมด (ไม่กล่าวหา, ค่ามาตรฐานจาก AIDA-14, แยก C/M/P, Skip ต้องมีเหตุผล, มนุษย์เป็นผู้ตัดสิน)

| หัวข้อ | ข้อตกลง |
|---|---|
| ช่วงนี้ (B1) | ข้อมูล **C ธุรกรรมบัตร/การโอนเงิน** + **D Vendor Master + บันทึกการเปลี่ยนแปลง** |
| Skill ใน B1 | Statistical, Concentration, Behavioral, Temporal, Sequence, Network |
| ช่องทางข้อมูล | ทั้งไฟล์แนบในแชท และไฟล์ใน SharePoint/OneDrive |
| Output | Audit Workbook (.xlsx) + Network Investigation Package (.csv) + HTML Interactive Dashboard (ไฟล์เดียว) |
| ข้อมูลอ่อนไหว | **แสดงข้อมูลเต็มทุก output** (ผู้ใช้ตัดสินใจ) — องค์กรควบคุมการเข้าถึงไฟล์เอง; ทุก output มีป้ายเตือน |
| ที่มาของโค้ด | **การ์ดสูตร (recipe) สั้นแยกตามเทคนิค** เก็บใน Knowledge, โค้ดตายตัว + เวอร์ชัน, ทดสอบใน repo |
| Materiality | ผู้ใช้ระบุที่จุดยืนยัน 1 แบบ ก. ยอดเงินตรง หรือ ข. ตัวเลขฐาน + % ตาม AIDA-14; ไม่ระบุ → "ไม่ได้ประเมิน" |
| ข้อจำกัด | Knowledge ≤ 20 ไฟล์ (B1 ใช้ครบ 20); Instructions ≤ 8,000 ตัวอักษร |

### เกณฑ์ความสำเร็จ
1. ผลทดสอบ Code Interpreter (spike, ข้อ 7.1) ผ่านทั้ง 4 ข้อ หรือมีการปรับ design ตามผล
2. ทุก recipe ผ่าน unit test บนข้อมูลตัวอย่าง: พบกรณีที่ฝังไว้ และไม่แจ้งเตือนผิดในข้อมูลปกติ
3. End-to-end test สร้างไฟล์ 3 ชิ้นที่เปิดได้ และจำนวน Unified Finding ตรงกับเฉลย
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
- 20 recipes (ข้อ 4.3), ไฟล์ Knowledge ใหม่ 4 ไฟล์ (ข้อ 3), แก้ไฟล์เดิม 4 ไฟล์
- ข้อมูลตัวอย่างฝังความผิดปกติ + เฉลย, unit/end-to-end tests, spike kit, eval ระยะ B

### ไม่ทำใน B1
- ข้อมูล A (AP) และ B (GL/Journal Entries)
- Forensic (Benford ฯลฯ), Rule-based, ML — ถ้าผู้ใช้ขอ AIDA ตอบว่ายังไม่รองรับใน B1 และให้คำปรึกษาแบบระยะ A
- Output อื่นใน 16 แบบที่เป็นเอกสารแยก (เช่น Executive Summary แยกไฟล์)
- การปิดบังข้อมูลอ่อนไหว (masking)

---

## 3. ไฟล์

### 3.1 Knowledge ใหม่ (ใช้ช่อง 16–19 → รวม 20 ไฟล์)
| # | ไฟล์ | เนื้อหา |
|---|---|---|
| 16 | `AIDA-16-output-templates.md` | โครง sheet ของ Workbook, คอลัมน์ CSV ของ Network Package, template HTML ของ Dashboard |
| 17 | `AIDA-17-data-evidence-schema.md` | คอลัมน์มาตรฐาน (4.1), schema Evidence / Finding / Run Log (4.4), รูปแบบ Data Reference, ตารางความเสี่ยง R1–R3 |
| 18 | `AIDA-18-analysis-recipes.md` | การ์ดวิเคราะห์ 11 ใบ |
| 19 | `AIDA-19-pipeline-recipes.md` | การ์ดเตรียมข้อมูล, Gate, รวมผล, ประเมิน, สร้าง output 9 ใบ |

ชื่อไฟล์ 17–19 เปลี่ยนจากที่สงวนไว้ในระยะ A ให้ตรงกับเนื้อหา

### 3.2 ไฟล์เดิมที่ต้องแก้
| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `AIDA-agent-instructions.md` | กฎข้อ 7 เปลี่ยนจาก "ไม่วิเคราะห์ข้อมูล" เป็นขั้นตอนวิเคราะห์ B1 (ข้อ 5) + ขอบเขตที่ยังไม่รองรับ + ตาราง routing ของไฟล์ 16–19 |
| `AIDA-00-index-principles.md` | สารบัญไฟล์ 16–19 (ไม่ใช่ "สงวนไว้" อีกต่อไป) |
| `AIDA-14-configuration-registry.md` | v1.1: เพิ่มหัวข้อ "Machine Config" (ข้อ 4.5) |
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
| ตาราง | คอลัมน์ |
|---|---|
| `transactions` | tx_id, ts, from_acct, to_acct, amount, currency, merchant_id, channel |
| `vendor_master` | vendor_id, name, bank_acct, address, phone, tax_id, created_at |
| `vendor_changes` | vendor_id, field, old_value, new_value, changed_at, changed_by |

- AIDA เสนอการจับคู่คอลัมน์ของผู้ใช้ → ผู้ใช้ยืนยัน (จุดยืนยัน 1)
- ไม่จำเป็นต้องมีครบ: การ์ดที่ขาดคอลัมน์ที่ต้องใช้จะถูก Skip + reason
- record key: `tx_id` (transactions), `vendor_id` (vendor_master), `vendor_id + changed_at` (vendor_changes) — ไม่มี → STOP ตาม `GATE.TRACE.REQUIRED`

### 4.2 รูปแบบการ์ด (recipe contract)
```python
# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1
# Registry: NET.FUNNEL | Input: transactions(from_acct, to_acct, amount, ts)
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    ...
    return evidence_rows(...)
```
- บรรทัดหัว 2 บรรทัดตามรูปแบบนี้ (validator ตรวจ)
- ชื่อฟังก์ชัน = recipe ID ตัวพิมพ์เล็ก แทน `-` ด้วย `_`; signature `(tables: dict, cfg: dict) -> pd.DataFrame` สำหรับการ์ดวิเคราะห์
- ใช้ได้เฉพาะ pandas, numpy, Python standard library (+ openpyxl สำหรับ OUT-WORKBOOK) — **ไม่ใช้ networkx**
- เข้ากันได้กับ pandas ≥ 1.5
- ห้ามมีตัวเลขเกณฑ์ในโค้ด: อ่านจาก `cfg[<registry key>]` เท่านั้น
- ≤ 40 บรรทัดโค้ดต่อการ์ด (ยกเว้น template Dashboard ใน AIDA-16)
- การ์ดวิเคราะห์ส่งคืน DataFrame ตาม Evidence schema; DataFrame ว่าง = ไม่พบ

### 4.3 การ์ด 20 ใบ
| กลุ่ม | การ์ด | ไฟล์ |
|---|---|---|
| เตรียมข้อมูล + Gate | `PREP-MAP`, `PROF-PROFILE`, `GATE-CAPABILITY` | AIDA-19 |
| Statistical / Concentration | `STAT-MAD` (amount ภายใน channel), `CONC-SHARE-HHI` (merchant share + HHI) | AIDA-18 |
| Behavioral / Temporal | `BEH-VELOCITY` (จำนวนรายการ/วัน/บัญชี เทียบ baseline ของบัญชีเดียวกัน), `BEH-SPIKE` (ยอด/เดือน/บัญชี เทียบ baseline), `TEMP-OFFHOURS` | AIDA-18 |
| Sequence | `SEQ-CHANGE-TO-TRANSFER`, `SEQ-CREATE-TO-PAY` | AIDA-18 |
| Network | `NET-RESOLVE` (normalize identifier), `NET-SHARED-ID`, `NET-CYCLE` (DFS เขียนเอง), `NET-FUNNEL` | AIDA-18 |
| รวมผล + ประเมิน | `UNIFY-FINDINGS`, `ASSESS-CMP` | AIDA-19 |
| Output + Log | `OUT-WORKBOOK`, `OUT-NETWORK-CSV`, `OUT-DASHBOARD`, `LOG-RUN` | AIDA-19 |

`NET-RESOLVE` เป็นขั้นเตรียม (normalize bank_acct / phone / tax_id / address: ตัดช่องว่าง/ขีด, ตัวพิมพ์เล็ก) ไม่สร้าง Evidence

### 4.4 Schema (AIDA-17)
| Schema | คอลัมน์ |
|---|---|
| Evidence | evidence_id, run_id, recipe_id, recipe_version, skill_family, entity_type, entity_id, risk, period (YYYY-MM), metric, value, threshold, registry_key, registry_version, explanation, record_refs (list ของ record key), data_ref |
| Finding | finding_id, entity_id, risk, period, evidence_ids, skill_families, exposure, confidence, materiality, priority, review_status, review_reason |
| Run Log | run_id, timestamp, stage (1–18), status (OK / STOP / SKIP / REVIEW), detail, recipe_id, recipe_version, registry_version, pack_version, input_sha256 |

**Data Reference**
- ไฟล์แนบในแชท: `chat:<ชื่อไฟล์>#<sheet>@<เวลาอัปโหลด ISO>|sha256:<hash>`
- SharePoint/OneDrive: `sp:<URL>#<sheet>@<เวอร์ชันไฟล์ ถ้ามี>|sha256:<hash>`

**ความเสี่ยงใน B1**
| Risk | ชื่อ | การ์ดที่ให้ Evidence |
|---|---|---|
| R1 | การเคลื่อนย้ายเงินผิดปกติ | STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, NET-CYCLE, NET-FUNNEL |
| R2 | ความถูกต้องของข้อมูลหลักผู้ขาย | SEQ-CHANGE-TO-TRANSFER, SEQ-CREATE-TO-PAY, NET-SHARED-ID |
| R3 | การกระจุกตัว/การพึ่งพิง | CONC-SHARE-HHI |

### 4.5 Machine Config ใน AIDA-14 (v1.1)
recipe ต้องการค่าที่เครื่องอ่านได้ จึงเพิ่มหัวข้อ `## Machine Config (สำหรับ recipe)` เป็น code block JSON เดียว:
- key ระดับบนสุด = registry key ที่มีอยู่แล้วในตาราง AIDA-14 เท่านั้น (validator ตรวจ)
- ค่าเป็นตัวเลข/โครงสร้างที่ตรงกับความหมายในตาราง เช่น `"NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7}`, `"TEMP.OFF_HOURS": {"start": "08:00", "end": "18:00", "weekend": true}`
- `"REGISTRY.VERSION": "1.1"` อยู่ใน JSON เพื่อบันทึกลง Run Log
- ค่าใน JSON ต้องสอดคล้องกับตาราง (ตรวจโดย test ที่เทียบค่าตัวเลขหลัก)

### 4.6 การรวมผลและการประเมิน
- **Unify:** Evidence ที่ entity_id + risk + period (เดือน) เดียวกัน → 1 Finding
- **Confidence:** สูง = skill_families ≥ 2 และ data_ref ครบทุก Evidence / กลาง = 1 skill family และ data_ref ครบ / ต่ำ = data_ref ไม่ครบ
- **Exposure:** ผลรวม amount ของ record_refs ที่ไม่ซ้ำกัน; R2 (entity เป็น vendor) = ผลรวมยอดโอนเข้าบัญชีของ vendor ในเดือนนั้น; R3 (entity เป็น merchant) = ยอดรวมของ merchant ในเดือนนั้น
- **หน่วยของ baseline:** BEH-VELOCITY ใช้ "วัน" เป็นงวด, BEH-SPIKE ใช้ "เดือน" เป็นงวด — ทั้งคู่ใช้ `BEH.BASELINE.MIN_PERIODS` เป็นจำนวนงวดขั้นต่ำ (ระบุหน่วยใน Machine Config)
- **Materiality:** เทียบ exposure กับฐานที่ผู้ใช้ระบุ (แบบ ก./ข.) ตามระดับใน AIDA-14; ไม่ระบุ → "ไม่ได้ประเมิน"
- **Priority:** ตาราง Priority ใน AIDA-14; Materiality "ไม่ได้ประเมิน" → Priority = ระดับ Confidence และ review_reason = "ไม่มีฐาน Materiality"
- **Human Review:** ทุก Finding มี review_status = "รอ Human Review"; Finding ที่มี Evidence จาก Network หรือ Confidence ต่ำ ระบุ review_reason เพิ่ม

---

## 5. ขั้นตอนการทำงาน (Instructions กฎข้อ 7 ใหม่)
```
1. รับไฟล์ → sha256 + Data Reference
2. PREP-MAP → เสนอการจับคู่คอลัมน์
   ⏸ จุดยืนยัน 1: ผู้ใช้ยืนยัน mapping + ฐาน Materiality (แบบ ก. หรือ ข. หรือไม่ระบุ)
3. PROF-PROFILE → Dataset Profile; ไม่ผ่าน GATE.TRACE.REQUIRED → STOP
4. GATE-CAPABILITY → Analysis Plan (Run/Skip + เหตุผลทุกการ์ด)
   ⏸ จุดยืนยัน 2: ผู้ใช้ยืนยันแผน (เอาการ์ดออกได้)
5. รันการ์ดวิเคราะห์ → Evidence
6. UNIFY-FINDINGS → ASSESS-CMP
7. OUT-WORKBOOK + OUT-NETWORK-CSV + OUT-DASHBOARD + LOG-RUN → ส่งไฟล์ 3 ชิ้น + สรุปในแชท
```
- ห้ามข้ามจุดยืนยันแม้ผู้ใช้ขอ (อธิบายเหตุผล: Human Accountable)
- ใช้โค้ดจากการ์ดตามตัวอักษร ห้ามเขียนโค้ดวิเคราะห์ใหม่; ถ้าดึงการ์ดมาไม่ครบ → แจ้งผู้ใช้และไม่รันการ์ดนั้น (บันทึก SKIP + reason "ดึง recipe ไม่ครบ")
- บอกเสมอว่าค่าเกณฑ์เป็นค่ามาตรฐานจาก AIDA-14

---

## 6. Output

### 6.1 Audit Workbook (.xlsx) — sheet ตามลำดับ
1. `README` — ป้ายเตือนข้อมูลอ่อนไหว, run_id, วิธีอ่านไฟล์
2. `Dataset_Profile` 3. `Analysis_Plan` 4. `Evidence` 5. `Findings` (มีคอลัมน์ว่าง reviewer, disposition, review_date) 6. `Materiality` (ฐาน วิธีคำนวณ แหล่งที่มา) 7. `Run_Log`

### 6.2 Network Investigation Package (.csv)
- `nodes.csv`: node_id, node_type (account / vendor / identifier), label, finding_ids
- `edges.csv`: source, target, edge_type (transfer / shares_identifier), amount, ts, record_ref
- เฉพาะ subgraph ที่เกี่ยวกับ Finding

### 6.3 HTML Interactive Dashboard (ไฟล์เดียว, ไม่โหลดภายนอก)
- ป้ายเตือนข้อมูลอ่อนไหวบนสุด
- แท็บ: สรุป (จำนวน Finding ตาม Priority/Risk, Run/Skip) · Findings (กรองได้, คลิกเห็น Evidence + record_refs) · Network (SVG ของ subgraph ที่พบ, คลิก node เห็น Finding) · Run Log
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
+ บันทึกเวอร์ชัน pandas
ไม่ผ่านข้อใด → หยุดและปรับ design ก่อนทำต่อ

### 7.2 ข้อมูลตัวอย่าง (`tests/make_sample_data.py`, seed คงที่)
- ~5,000 ธุรกรรมปกติ, 200 vendor
- ฝัง 8 กรณี อย่างละ 1: Funnel, Cycle 3 ทอด, Shared bank account (3 vendor), Change-to-transfer 2 วัน, Create-to-pay 5 วัน, ยอดโดดเด่น, Velocity, Off-hours
- ไฟล์เฉลย: การ์ดใดต้องพบ entity ใด และจำนวน Unified Finding ที่ต้องได้

### 7.3 Tests ใน repo
- `extract_recipes.py` ดึงโค้ดจาก AIDA-18/19 → tests รันโค้ดชุดเดียวกับที่ AIDA ใช้
- Unit ต่อการ์ด: พบกรณีที่ฝัง + ไม่มี false positive ในข้อมูลปกติ
- End-to-end: ไฟล์ 3 ชิ้นเปิดได้ (openpyxl อ่าน xlsx ได้, HTML มี JSON ที่ parse ได้), จำนวน Finding ตรงเฉลย
- Gate: ไม่มี ts → Temporal/Sequence/Velocity Skip + reason; ไม่มี tx_id → STOP

### 7.4 Validator เพิ่ม
- จำนวนไฟล์ Knowledge ≤ 20 (B1 = 20)
- หัวการ์ดตามรูปแบบ 4.2
- โค้ดการ์ด ≤ 40 บรรทัด (ยกเว้น template ใน AIDA-16)
- key ใน `cfg[...]` และใน Machine Config มีอยู่ในตาราง AIDA-14
- การตรวจเดิมของระยะ A ยังทำงานครบ

### 7.5 Eval ระยะ B (~10 ข้อ เพิ่มใน `eval-questions.md`)
ตัวอย่าง: วิเคราะห์ไฟล์ตัวอย่าง → หยุดที่จุดยืนยัน 1 และ 2, ได้ไฟล์ 3 ชิ้น, Finding ตรงเฉลย · ไม่มีคอลัมน์เวลา → Skip + reason · ขอข้ามการยืนยัน → ปฏิเสธ · ขอ Benford → ยังไม่รองรับใน B1 · ไม่ระบุ Materiality → "ไม่ได้ประเมิน" · ขอปิดบังข้อมูล → แจ้งว่า B1 แสดงเต็มตามนโยบาย

---

## 8. ความเสี่ยงที่บันทึกไว้
| ความเสี่ยง | การรับมือ |
|---|---|
| ข้อมูลเต็ม (รวม PAN) อยู่ในไฟล์ output — อยู่ในขอบเขต PCI DSS / PDPA | ผู้ใช้ตัดสินใจแสดงเต็ม; ป้ายเตือนทุก output; README บันทึกความเสี่ยง; การเปลี่ยนเป็น masking ทำได้ที่ OUT-* จุดเดียว |
| Copilot ดึง recipe/template ไม่ครบ | spike ตรวจก่อน; Instructions ห้ามรันการ์ดที่ไม่ครบ |
| pandas ใน Code Interpreter เก่ากว่า repo | จำกัด API ที่ pandas ≥ 1.5; ยืนยันเวอร์ชันใน spike |
| ไฟล์ข้อมูลใหญ่เกินขีดจำกัดของ Code Interpreter | บันทึกขนาดที่ทดสอบได้ใน spike; README แนะนำแบ่งไฟล์ตามช่วงเวลา |
