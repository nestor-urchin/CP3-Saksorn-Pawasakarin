# AIDA-01 · Orchestration Workflow 18 Stage
> ไฟล์: AIDA-01 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: AIDA ทำงานกี่ขั้นตอน, แต่ละ Stage รับอะไร ส่งอะไร, Decision Gate ของแต่ละ Stage คืออะไร, Stage ไหนส่งต่อไปไหน

## สรุปสั้น
Workflow มี 18 Stage แบ่ง 3 ช่วง: **I. Intake → Plan (1–6)**, **II. Execute → Unified Findings (7–12)**, **III. Assess → Deliver (13–18)**
แต่ละ Stage มี Input, Skill/งาน, Output, Decision Gate และเส้นทางส่งต่อ
หลักสำคัญ: รันเฉพาะ skill ที่ผ่าน Capability Gate, ตรวจคุณภาพ Evidence ก่อนรวมผล และแยกการประเมิน การตีความ การรายงาน และการอนุมัติใช้งานออกจากกัน
ทุก Stage บันทึก Audit Trail (AIDA-13)

## Workflow I: Intake → Plan
แต่ละ Stage มี Input, Skill, Output, Decision Gate และเส้นทางส่งต่อ

| Stage | ชื่อ | Input | Output | Decision Gate | ถัดไป |
|---|---|---|---|---|---|
| 1 | User Request | คำขอ + files/data refs | Validated input (ส่งตรวจ) | — | 2 |
| 2 | Input Validation | format / accessibility / traceability | Accept หรือ Stop | Stop เมื่อ input ใช้ไม่ได้หรืออ้างอิงต้นทางไม่ได้ (AIDA-02) | 3 หรือ ยุติ |
| 3 | Data Profiling | dataset | Dataset Profile (Output 01) | — | 4 |
| 4 | Risk Understanding | คำขอ + Risk Library | Risk Context (Output 02) | — | 5 |
| 5 | Capability Assessment | profile + quality | Supported / Unsupported ต่อ skill family | Capability Gate (AIDA-03) | 6 |
| 6 | Analysis Planning | risk + capability + config | Analysis Plan (Output 03) พร้อม Selection / Skip Reason | Skip + reason สำหรับ skill ที่ไม่รองรับ | 7 |

## Workflow II: Execute → Unified Findings
รันเฉพาะ skill ที่ผ่าน Capability Gate และตรวจคุณภาพ Evidence ก่อนรวมผล

| Stage | ชื่อ | Input | Output | Decision Gate | ถัดไป |
|---|---|---|---|---|---|
| 7 | Select Skills | Analysis Plan | Execution set | — | 8 |
| 8 | Run Analysis Skills | data + config | Evidence (Output 04 Evidence Package) | Stop/Skip ระดับ skill | 9 |
| 9 | Evidence Quality Gate | completeness / lineage / validity | Accept • Re-run • Review | Re-run เมื่อแก้ได้, Review เมื่อขัดแย้ง | 10 |
| 10 | Normalize & Deduplicate | qualified evidence | Normalized evidence | — | 11 |
| 11 | Evidence Correlation | entity + risk + time | Evidence groups | — | 12 |
| 12 | Unified Findings | groups + source links | Unified Findings (Output 05) | — | 13 |

## Workflow III: Assess → Deliver
แยกการประเมิน การตีความ การรายงาน และการอนุมัติใช้งานออกจากกัน

| Stage | ชื่อ | Input | Output | Decision Gate | ถัดไป |
|---|---|---|---|---|---|
| 13 | Confidence | finding + evidence quality | Confidence Assessment (Output 06) | Confidence ต่ำ → Human Review | 14 |
| 14 | Materiality | finding + impact context | Materiality Assessment (Output 07) | — | 15 |
| 15 | Priority | C + M + config criteria | Priority Assessment (Output 08) | — | 16 |
| 16 | Interpretation | assessed finding | Auditor language + risks (Output 09) | — | 17 |
| 17 | Audit Procedures | gaps + hypotheses | Recommended procedures (Output 10) | — | 18 |
| 18 | Outputs & Trail | all approved artefacts | Workbook / Executive / Dashboard / Trail (Output 11–16) | Human Review ก่อนเผยแพร่ | จบ |

## การส่งต่อระหว่างช่วง
- Stage 2 Stop → ยุติ workflow และบันทึก error/exception
- Stage 5–6 Skip → ข้ามเฉพาะ skill นั้น workflow เดินต่อ
- Stage 9 Review / Stage 13 Confidence ต่ำ / Alert ใหม่ / ML หรือ Network pattern → Human Review
- Stage 18 เผยแพร่เฉพาะ artefact ที่ผ่านการอนุมัติ (approved)

## ข้อห้าม (Guardrails)
- ห้ามรัน skill ที่ไม่ผ่าน Capability Gate
- ห้ามรวมผล (Stage 10–12) ก่อนผ่าน Evidence Quality Gate
- ห้ามรวม Confidence, Materiality และ Priority เป็นค่าเดียว
- ห้ามเผยแพร่ Output ก่อน Human Review

## ไฟล์ที่เกี่ยวข้อง
- AIDA-02 Decision Gates, AIDA-03 Selection Matrix, AIDA-10 Assessment Model, AIDA-12 Output Framework, AIDA-13 Audit Trail
