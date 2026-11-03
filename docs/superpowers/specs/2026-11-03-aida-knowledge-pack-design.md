# AIDA Knowledge Pack — Design Spec

- วันที่: 2026-11-03
- สถานะ: รอผู้ใช้ตรวจ (Draft for review)
- ที่มา: สไลด์ "AIDA • Audit Intelligence Architecture" (20 ภาพ) + การ brainstorm ในเซสชันนี้

---

## 1. เป้าหมาย (Intent)

สร้างชุดไฟล์ Knowledge (.md) สำหรับ **AIDA Agent** ใน Microsoft 365 Copilot Agent Builder
ให้ Agent ตอบคำถามผู้ตรวจสอบได้ตรงตามหลักการออกแบบ AIDA

| หัวข้อ | ข้อตกลง |
|---|---|
| ผู้ใช้หลัก | ผู้ตรวจสอบภายใน (Internal Audit) |
| ระยะ A (รอบนี้) | AIDA เป็น **ที่ปรึกษาด้านวิธีการ** — ตอบว่าควรใช้ skill ใด, gate ใด, ตีความอย่างไร, output ควรเป็นอย่างไร **ไม่วิเคราะห์ข้อมูลจริง** |
| ระยะ B (อนาคต) | AIDA วิเคราะห์ข้อมูลที่อัปโหลดตาม workflow 18 ขั้น (ต้องใช้ Code Interpreter) — **ไม่อยู่ในขอบเขตรอบนี้** แต่สงวนช่องไฟล์ไว้ |
| ข้อจำกัด | อัปโหลด Knowledge ได้ไม่เกิน **20 ไฟล์**; Instructions ไม่เกิน **8,000 ตัวอักษร** |
| รูปแบบไฟล์ | **Markdown (.md)** ทั้งหมด; ไฟล์ใน repo = ไฟล์ที่อัปโหลดจริง |
| ภาษา | ไทย + ศัพท์เทคนิคภาษาอังกฤษตามสไลด์ |
| ค่ามาตรฐาน | ใส่ค่ามาตรฐานทั่วไปลงใน Registry **โดยไม่ติดป้ายรออนุมัติ** แต่ AIDA **ต้องแจ้งผู้ใช้ทุกครั้ง** ที่อ้างค่าเหล่านี้ว่าเป็นค่ามาตรฐานและปรับตามบริบทองค์กรได้ |

### เกณฑ์ความสำเร็จ
1. ไฟล์ใน `knowledge/` ≤ 20 ไฟล์ ครอบคลุมเนื้อหาสไลด์ทั้ง 20 ภาพ (ตาราง Coverage ข้อ 7)
2. `validate_pack.py` ผ่านทุกข้อ
3. ผู้ใช้ทดสอบด้วย `eval-questions.md` แล้ว AIDA ตอบผ่านเกณฑ์ (ทำโดยผู้ใช้ใน Copilot)

### Assumption ที่ยังไม่ได้ยืนยัน
- Tenant รองรับการอัปโหลด .md เป็น Knowledge (ผู้ใช้ควรทดลองอัปโหลด 1 ไฟล์ก่อน)
- Copilot ดึงเนื้อหาเป็นช่วง ๆ (chunk retrieval) ไม่ได้อ่านทุกไฟล์ทุกครั้ง → ทุกไฟล์ต้องอ่านเข้าใจได้ในตัวเอง

---

## 2. แนวทางที่เลือก

**แนวทาง 1 — แบ่งไฟล์ตาม "กลุ่มคำถามที่ผู้ใช้จะถาม"** (เลือกแทนการแบ่งตาม workflow หรือรวมเป็นไฟล์ใหญ่)
เหตุผล: retrieval ได้ไฟล์ตรงคำถามและแต่ละไฟล์ตอบได้ครบในตัว ยอมให้กฎสำคัญซ้ำกันเล็กน้อยโดยตั้งใจ

---

## 3. รายการไฟล์

### 3.1 Knowledge (อัปโหลด) — ระยะ A ใช้ 16 ช่อง

| # | ไฟล์ | เนื้อหา | สไลด์ต้นทาง |
|---|---|---|---|
| 00 | `AIDA-00-index-principles.md` | สารบัญ, Target State, หลักการ 6 ข้อ, อภิธานศัพท์, Layer 1–10 โดยย่อ | Target State |
| 01 | `AIDA-01-orchestration-workflow.md` | 18 Stage: Input / Skill / Output / Decision Gate / เส้นทางส่งต่อ | Workflow I–III |
| 02 | `AIDA-02-decision-gates.md` | Stop / Skip / Human Review: เงื่อนไข, Action, สิ่งที่ต้องบันทึก | Decision Gates |
| 03 | `AIDA-03-analysis-selection-matrix.md` | Capability Gate, Minimum Data Requirement, Selection/Skip Reason, ตาราง 8 skill family | Selection Matrix |
| 04 | `AIDA-04-skill-statistical-concentration.md` | 5.1 Statistical, 5.2 Concentration | Anomaly Skills I |
| 05 | `AIDA-05-skill-behavioral-temporal.md` | 5.3 Behavioral, 5.4 Temporal | Anomaly Skills II |
| 06 | `AIDA-06-skill-sequence-forensic.md` | 5.5 Sequence, 5.6 Forensic | Anomaly Skills III |
| 07 | `AIDA-07-skill-rule-ml.md` | 5.7 Rule-Based, 5.8 Machine Learning | Anomaly Skills IV |
| 08 | `AIDA-08-skill-network.md` | 5.9 Network Analysis | Anomaly Skills V |
| 09 | `AIDA-09-hybrid-assessment.md` | 5.10 Hybrid: evidence 4 ประเภท → Hybrid Logic → Assessment Output | Hybrid |
| 10 | `AIDA-10-assessment-model.md` | Confidence / Materiality / Priority, เกณฑ์ระดับ, ตาราง Priority, ข้อห้าม | Assessment Model |
| 11 | `AIDA-11-audit-procedures-language.md` | Audit Procedures 8 ขั้น, Interpretation (Layer 7), แนวภาษาไม่กล่าวหา + ตัวอย่างคำเทียบ | Audit Procedures, Layers 7–9 |
| 12 | `AIDA-12-output-framework.md` | 16 Output (หน้าที่, ผู้ใช้, drill-down), Reporting/Intelligence (Layer 8–9), กฎ Executive Output | Output Framework, Layers 7–9 |
| 13 | `AIDA-13-traceability-governance.md` | Evidence Lineage 7 ระดับ, Reproducibility test, Layer 10 Governance, Universal Skill Spec | Traceability, Layer 10, Skill Spec |
| 14 | `AIDA-14-configuration-registry.md` | ค่ามาตรฐานทั้งหมด (ข้อ 5) + version + กฎการแจ้งผู้ใช้ | ทุก skill |
| 15 | `AIDA-15-acceptance-checklist-faq.md` | Design Acceptance Checklist 12 ข้อ + FAQ ตัวอย่างถาม-ตอบ | Acceptance Checklist |

### 3.2 ช่องสงวนสำหรับระยะ B (ยังไม่สร้างไฟล์)
| # | ไฟล์ที่วางแผน | เนื้อหา |
|---|---|---|
| 16 | `AIDA-16-output-templates.md` | Template ของ Output 16 แบบ |
| 17 | `AIDA-17-evidence-schema.md` | Schema ของ Evidence / Finding / Lineage record |
| 18 | `AIDA-18-calculation-recipes.md` | สูตรและขั้นตอนคำนวณของแต่ละเทคนิค |
| 19 | `AIDA-19-run-log-template.md` | Template ของ Audit Trail / run log |

### 3.3 ไฟล์ที่ไม่อัปโหลด
- `AIDA-agent-instructions.md` — วางในช่อง Instructions
- `README.md` — วิธีอัปโหลด, การอัปเดตเวอร์ชัน, ช่องสงวนระยะ B
- `tests/eval-questions.md`, `tools/validate_pack.py`

---

## 4. โครงสร้างภายในไฟล์

### 4.1 โครงร่วม (ทุกไฟล์ใน `knowledge/`)
```markdown
# AIDA-XX · <ชื่อหัวข้อ>
> ไฟล์: AIDA-XX | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: <รายการคำถามที่ไฟล์นี้ตอบ>

## สรุปสั้น
## <เนื้อหาหลัก — หัวข้อ ## / ###>
## ข้อห้าม (Guardrails)
## ไฟล์ที่เกี่ยวข้อง
```
หัวข้อ `สรุปสั้น`, `ข้อห้าม (Guardrails)`, `ไฟล์ที่เกี่ยวข้อง` และบรรทัด `ไฟล์นี้ตอบคำถาม:` เป็นข้อบังคับ (สคริปต์ตรวจ)

### 4.2 ไฟล์ Skill (04–09)
แต่ละ skill family มี **Universal Skill Spec 8 ช่อง**: Purpose, Non-purpose, Input, Output, Configuration, Audit Trail, Success, Stop/Skip
ตามด้วยตารางเทคนิค:

| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |

### 4.3 Single source of truth ของค่ามาตรฐาน
- ค่าทุกค่ามีต้นฉบับใน AIDA-14 ในรูปแบบ `` `KEY` `` + ค่า
- ไฟล์อื่นอ้างได้ทั้ง key และค่า แต่ต้องเขียนรูปแบบ `` `KEY = ค่า` `` เพื่อให้สคริปต์ตรวจความตรงกันได้

### 4.4 กฎหลักใน `AIDA-agent-instructions.md`
1. ห้ามกล่าวหา — ใช้ "ความผิดปกติ" / "Potential Risk"; Anomaly Score ≠ Fraud Conclusion
2. อ้างอิงไฟล์/หัวข้อ AIDA ทุกคำตอบ
3. แจ้งเมื่อใช้ค่ามาตรฐานจาก AIDA-14 ทุกครั้ง
4. แยก Confidence / Materiality / Priority; Priority สูง ≠ ยืนยันการกระทำผิด; ห้ามใช้ Model Score เป็น Materiality
5. Skip ต้องมีเหตุผล; Stop ต้องบอกสาเหตุ
6. Human Accountable — AIDA แนะนำวิธีหาหลักฐาน ไม่ตัดสินแทนผู้ตรวจสอบ; Alert/ML ต้องผ่าน Human Review
7. ขอบเขตระยะ A — ถ้าขอวิเคราะห์ข้อมูลจริง ให้แจ้งขอบเขตและเสนอ Analysis Plan (skill + gate + ข้อมูลที่ต้องมี) แทน

---

## 5. ค่ามาตรฐานใน Registry (AIDA-14, เวอร์ชัน 1.0)

### 5.1 Gate ทั่วไป
| Key | ค่า | ที่มา |
|---|---|---|
| `GATE.COMPLETENESS.MIN` | 95% (field จำเป็นว่าง ≤ 5%) | แนวปฏิบัติ data quality |
| `GATE.SAMPLE.MIN` | 30 รายการต่อกลุ่ม | ขั้นต่ำทางสถิติทั่วไป |
| `GATE.TRACE.REQUIRED` | dataset + table + period + record key | ไม่ครบ → Stop |

### 5.2 Statistical & Concentration
| Key | ค่า | ที่มา |
|---|---|---|
| `STAT.ZSCORE.THRESHOLD` | 3 | 3-sigma rule |
| `STAT.IQR.K` | 1.5 (mild) / 3.0 (extreme) | Tukey fences |
| `STAT.MAD.THRESHOLD` | 3.5 (Modified Z) | Iglewicz & Hoaglin |
| `STAT.PERCENTILE` | P99 / P1 | ใช้ทั่วไป |
| `CONC.HHI` | < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง | US DOJ/FTC 2010 (หมายเหตุ: แนวทาง 2023 ใช้ 1,000/1,800) |
| `CONC.SINGLE_ENTITY_SHARE` | 10% | เกณฑ์ major customer 10% |
| `CONC.TOPN` | 10 | ใช้ทั่วไป |

### 5.3 Behavioral, Temporal, Sequence
| Key | ค่า |
|---|---|
| `BEH.BASELINE.MIN_PERIODS` | 6 งวด (แนะนำ 12) |
| `BEH.PEER.MIN_SIZE` | 5 ราย |
| `BEH.DEVIATION` | 3σ จาก baseline |
| `TEMP.PERIOD_END.WINDOW` | 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป |
| `TEMP.TREND.MIN_PERIODS` | 12 งวด (seasonality 24) |
| `TEMP.OFF_HOURS` | นอก 08:00–18:00, วันหยุด |
| `SEQ.CREATE_TO_PAY.DAYS` | 30 วัน |
| `SEQ.CHANGE_TO_TRANSFER.DAYS` | 7 วัน |

### 5.4 Forensic, ML, Network
| Key | ค่า | ที่มา |
|---|---|---|
| `FOR.BENFORD.MIN_N` | 1,000 รายการ (ยอด ≥ 10) | Nigrini |
| `FOR.BENFORD.MAD_1ST` | ≤ 0.006 / ≤ 0.012 / ≤ 0.015 / > 0.015 | Nigrini |
| `FOR.ROUND.UNIT` | 1,000 | ใช้ทั่วไป |
| `FOR.THRESHOLD_AVOID.BAND` | 90–99.99% ของวงเงินอนุมัติ | ใช้ทั่วไป |
| `FOR.REPEAT.MIN_COUNT` | 3 ครั้ง / entity / งวด | ใช้ทั่วไป |
| `ML.CONTAMINATION` | 1% | ใช้ทั่วไป |
| `ML.LOF.NEIGHBORS` | 20 | scikit-learn default |
| `ML.MIN_OBS` | 1,000 หรือ 10 × จำนวน feature | กฎทั่วไป; ML → Human Review เสมอ |
| `NET.SHARED_ID.MIN` | 2 entity | ใช้ทั่วไป |
| `NET.CYCLE` | 2–5 ทอด ภายใน 30 วัน | ใช้ทั่วไป |
| `NET.FUNNEL` | รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน | รูปแบบ mule ทั่วไป |

### 5.5 Assessment Model
- `ASSESS.CONFIDENCE` — สูง: ≥ 2 แหล่งอิสระยืนยัน + lineage ครบ / กลาง: 1 แหล่ง + lineage ครบ / ต่ำ: ขัดแย้งหรือ lineage ไม่ครบ → Human Review
- `ASSESS.MATERIALITY` — 5% กำไรก่อนภาษี / 0.5–1% รายได้ / 1–2% สินทรัพย์รวม; Clearly trivial < 5% ของ Materiality
- `ASSESS.PRIORITY` — ตาราง Confidence × Materiality (3×3) แล้วปรับขึ้น 1 ระดับเมื่อเร่งด่วนหรือเข้าเกณฑ์ที่องค์กรกำหนด

---

## 6. การทดสอบ

### 6.1 `tools/validate_pack.py` (Python standard library เท่านั้น)
| # | ตรวจ | ล้มเหลวเมื่อ |
|---|---|---|
| 1 | จำนวนไฟล์ใน `knowledge/` | > 20 |
| 2 | หัวข้อบังคับ (ข้อ 4.1) | ขาดหัวข้อใด |
| 3 | Registry key ที่อ้างในรูป `` `KEY = ค่า` `` | key ไม่มีใน AIDA-14 หรือค่าไม่ตรง |
| 4 | คำกล่าวหา (ทุจริต, กระทำผิด, fraudster, โกง) | พบนอกหัวข้อ Guardrails และไม่อยู่ในบรรทัดปฏิเสธ (มี ≠, ไม่, ห้าม, not) |
| 5 | การอ้าง `AIDA-XX` | ชี้ไฟล์ที่ไม่มีและไม่ใช่ช่องสงวน 16–19 |
| 6 | ความยาว `AIDA-agent-instructions.md` | > 8,000 ตัวอักษร |

สคริปต์มี unit test (`tools/test_validate_pack.py`, unittest) ครอบคลุมกรณีผ่าน/ไม่ผ่านของแต่ละข้อ

### 6.2 `tests/eval-questions.md`
~20 คำถาม แต่ละข้อมี "ต้องมี" / "ต้องไม่มี" / ไฟล์ที่ควรถูกอ้าง ผูกกับ Acceptance Checklist อย่างน้อยข้อละ 1 คำถาม ตัวอย่าง:
- ไม่มี timestamp ใช้ Temporal ได้ไหม → Skip + reason
- Isolation Forest score 0.9 = ทุจริตไหม → ไม่ใช่ + Human Review
- HHI ใช้เกณฑ์เท่าไหร่ → 2,500 + แจ้งว่าเป็นค่ามาตรฐาน
- Priority สูงแปลว่าผิดไหม → ปฏิเสธ + อธิบาย C/M/P
- ช่วยวิเคราะห์ไฟล์นี้ → แจ้งขอบเขตระยะ A + เสนอ Analysis Plan

---

## 7. Coverage: สไลด์ → ไฟล์

| สไลด์ | ไฟล์ |
|---|---|
| Target State | 00 |
| Design Acceptance Checklist | 15 |
| Audit Procedures Generated from Findings | 11 |
| Assessment Model | 10 |
| Orchestration Workflow I, II, III | 01 |
| Decision Gates | 02 |
| Output Framework | 12 |
| Traceability & Evidence Lineage | 13 |
| Anomaly Skills I–V | 04–08 |
| 5.10 Hybrid | 09 |
| Layers 7–9 | 11, 12 |
| Layer 10 Governance | 13 |
| Universal Skill Spec | 13 (+ ใช้เป็นโครงใน 04–09) |
| Analysis Selection Matrix | 03 |

---

## 8. นอกขอบเขต
- เนื้อหาไฟล์ 16–19 (ระยะ B)
- การอัปโหลดเข้า Agent Builder (ผู้ใช้ทำตาม README)
- การรัน eval ใน Copilot (ผู้ใช้ทำ)
