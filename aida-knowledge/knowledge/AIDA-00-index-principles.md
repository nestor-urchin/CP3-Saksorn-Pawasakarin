# AIDA-00 · สารบัญ หลักการ และอภิธานศัพท์
> ไฟล์: AIDA-00 | เวอร์ชัน: 3.1 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: AIDA คืออะไร, หลักการออกแบบ 6 ข้อมีอะไรบ้าง, Layer 1–10 คืออะไร, ควรเปิดไฟล์ไหนเพื่อตอบเรื่องใด, ศัพท์แต่ละคำหมายถึงอะไร

## สรุปสั้น
**AIDA (Audit Intelligence Architecture)** คือสถาปัตยกรรมที่เชื่อม Business Risk, Data, Evidence, Audit Judgment และ Management Action อย่างมีวินัย
เป้าหมาย: **"จาก เครื่องมือตรวจจับ สู่ ระบบปฏิบัติการด้านหลักฐานและข้อมูลเชิงลึกสำหรับงานตรวจสอบ"**
AIDA ระยะ A ทำหน้าที่ **ที่ปรึกษาด้านวิธีการ** — แนะนำ skill, gate, การตีความ และ output ตามกรอบนี้ โดยผู้ตรวจสอบเป็นผู้ตัดสินใจ
ระยะ B1 เพิ่มการ **วิเคราะห์ข้อมูลธุรกรรมจริง** ด้วย Code Interpreter (use case Potential Unusual Transactions across Mule Accounts)  — ผลเป็นสัญญาณให้ Human Review ไม่ใช่ข้อสรุป
ระยะ **C1** (Knowledge Pack 3.0) แทนการ์ดสูตร 34 ใบของ B1 ด้วย **engine ไฟล์เดียวที่ทดสอบแล้ว** ซึ่งทำงานตาม **บทบาทคอลัมน์** จึงวิเคราะห์ได้หลายประเภทข้อมูล: **E โอนเงินระหว่างบัญชี**, **C รับชำระค่างวดสินเชื่อ**, **A จ่ายเงินเจ้าหนี้**
ระยะ **C2** (Knowledge Pack 3.1, `aida_engine.py` v3.1.0, Registry 1.3) เพิ่มการ์ดรับรองของ **L ประกันชีวิต** (เวนคืน กู้ตามกรมธรรม์ เปลี่ยนผู้รับผลประโยชน์: L-R1–L-R6) และ **F ธุรกรรมกองทุนรวมของผู้ถือหน่วย** (ซื้อ ขายคืน สับเปลี่ยน: F-R1–F-R6) โดยใช้ 14 บทบาทเดิม พร้อม **ตารางเหตุการณ์ (event table)** 1 ตาราง และการยืนยัน **ความหมายของรหัสประเภทรายการ** (`code_values`) ที่ Intake Review
- ผู้ตรวจสอบเล่าบริบท ความหมายคอลัมน์ เงื่อนไข และ Risk Concern เป็นข้อความอิสระ → engine สร้าง **Intake Review** (ความหมายคอลัมน์, ความพอเพียงต่อความเสี่ยง + Data Request, เงื่อนไข, ความเสี่ยงที่แนะนำ, คุณภาพข้อมูล) → ผู้ตรวจสอบยืนยัน **ครั้งเดียว** → engine วิเคราะห์จนได้ Workbook / Dashboard
- คำถามนอกการ์ดรับรองใช้ **โหมดสำรวจ** (ผลติดป้าย "ยังไม่ผ่านการรับรอง" เลื่อนเป็น Finding ได้เมื่อผู้ตรวจสอบสั่ง)
- ขอบเขตถัดไป (ยังไม่มีการ์ดเฉพาะ): L1 เบี้ยประกัน, L2 สินไหม/เคลม, F2 พอร์ตลงทุนขององค์กร (ต้องใช้ราคาตลาด), บัตรเครดิต, มูลนิธิ, สหกรณ์ — ระหว่างนี้ใช้การ์ดทั่วไปที่บทบาทพอ + โหมดสำรวจ (ความกังวลเรื่องเคลมเร็วหลังทำกรมธรรม์ได้ Data Request ข้อมูลการเคลม)

## Target State: หลักการออกแบบ 6 ข้อ
| หลักการ | ความหมาย | ผลต่อการทำงาน |
|---|---|---|
| **Evidence First** | ทุกผลลัพธ์เริ่มจากหลักฐานที่อ้างอิงกลับได้ | ทุก Finding ต้องมี Evidence + Data Reference (AIDA-13) |
| **Configuration Driven** | กฎ เกณฑ์ น้ำหนัก และเวอร์ชันถูกควบคุม | ค่าทุกค่ามาจาก Registry (AIDA-14) ไม่ Hard-code |
| **Human Accountable** | ผู้ตรวจสอบทบทวน Alert และใช้ดุลยพินิจ | Alert / ML / Output ก่อนใช้ ต้องผ่าน Human Review (AIDA-02) |
| **Non-Accusatory** | ระบบชี้ความผิดปกติและ Potential Risk ไม่ชี้ความผิด | ใช้ภาษากลาง (AIDA-11) |
| **Reproducible** | ผลลัพธ์ทำซ้ำ ตรวจสอบ และอธิบายได้ | Data + Configuration + Skill/Model Version เดิม ต้องได้ผลเดิม (AIDA-13) |
| **Actionable** | Output รองรับ Audit Procedure และ Management Action | ทุก Finding เชื่อมกับ Procedure และ Action (AIDA-11, AIDA-12) |

## สารบัญไฟล์
| ไฟล์ | หัวข้อ | เปิดเมื่อถามเรื่อง |
|---|---|---|
| AIDA-00 | สารบัญ หลักการ อภิธานศัพท์ | ภาพรวม, ความหมายของคำ |
| AIDA-01 | Orchestration Workflow 18 Stage | ขั้นตอนการทำงาน Input/Output ของแต่ละ Stage |
| AIDA-02 | Decision Gates: Stop / Skip / Human Review | เมื่อไหร่ต้องหยุด ข้าม หรือส่งให้คนทบทวน |
| AIDA-03 | Analysis Selection Matrix | ข้อมูลแบบนี้ใช้ skill ไหนได้ / ต้อง Skip |
| AIDA-04 | Skill 5.1 Statistical, 5.2 Concentration | Z-Score, IQR, MAD, HHI, Top-N |
| AIDA-05 | Skill 5.3 Behavioral, 5.4 Temporal | Baseline, Peer, Trend, Period-end |
| AIDA-06 | Skill 5.5 Sequence, 5.6 Forensic | Event chain, Benford, Round amount |
| AIDA-07 | Skill 5.7 Rule-Based, 5.8 Machine Learning | Business rules, Isolation Forest, LOF |
| AIDA-08 | Skill 5.9 Network Analysis | Entity resolution, Graph, Circular flow |
| AIDA-09 | 5.10 Hybrid Anomaly Assessment | การรวม Evidence หลายแหล่ง |
| AIDA-10 | Assessment Model | Confidence / Materiality / Priority |
| AIDA-11 | Audit Procedures และภาษาที่ไม่กล่าวหา | ขั้นตอนหาหลักฐานเพิ่ม, การเขียน Finding |
| AIDA-12 | Output Framework | Output 16 แบบ, Executive Output |
| AIDA-13 | Traceability และ Governance | Evidence Lineage, Audit Trail, Version |
| AIDA-14 | Configuration Registry | ค่ามาตรฐาน / Threshold |
| AIDA-15 | Acceptance Checklist และ FAQ | เกณฑ์ตรวจรับ, ตัวอย่างคำถาม |
| AIDA-16 | ติดตั้ง engine (ระยะ C1–C2) | โหลด `aida_engine.py` จาก SharePoint/OneDrive หรือไฟล์แนบ, ตรวจเวอร์ชัน, สิ่งที่ต้องบอกเมื่อโหลดไม่ได้ |
| AIDA-17 | บทบาทคอลัมน์และ Schema (ระยะ C2) | 14 บทบาท + custom, preset E/C/A/L/F, ความหมายของบทบาทตามประเภทข้อมูล (เช่น limit = มูลค่าเวนคืน), ตารางเหตุการณ์, รหัสประเภทรายการ (`code_values`), พจนานุกรมชื่อคอลัมน์ไทย/อังกฤษ, Schema Evidence / Finding / Exploratory / Data Dictionary / Data Request / Run Log, Output |
| AIDA-18 | Risk Library และการ์ดรับรอง (ระยะ C2) | ความเสี่ยง R1–R4, G-R1–G-R4, C-R1–C-R3, A-R1–A-R4, L-R1–L-R6, F-R1–F-R6: การ์ดที่ใช้, บทบาทและข้อมูลขั้นต่ำ, สิ่งที่ต้องขอเพิ่ม, Registry key ของการ์ดแต่ละใบ |
| AIDA-19 | คู่มือเรียก engine (ระยะ C2) | ลำดับ inspect → confirm → run, รูปแบบ brief / answers (รวม `code_values`, `dataset_type`), Intake Review A–E, การแนบตารางเหตุการณ์, ตัวอย่าง L/F, กติกาการยืนยัน, โหมดสำรวจและ promote, mapping profile, การแก้ปัญหา |

เวอร์ชันที่ใช้คู่กัน: Knowledge Pack 3.1 · `aida_engine.py` v3.1.0 · Registry 1.3 (AIDA-14)

## Layer 1–10 โดยย่อ
Layer 7–10 มาจากสไลด์โดยตรง ส่วน Layer 1–6 จัดกลุ่มตามโครงสร้าง workflow (AIDA-01) และกลุ่ม skill
| Layer | ชื่อ | หน้าที่ | ไฟล์ |
|---|---|---|---|
| 1 | Intake & Validation (ตามโครงสร้าง workflow) | รับคำขอ ตรวจรูปแบบ การเข้าถึง และ traceability ของ input | AIDA-01, AIDA-02 |
| 2 | Data Profiling (ตามโครงสร้าง workflow) | สร้าง Dataset Profile | AIDA-01 |
| 3 | Risk Understanding (ตามโครงสร้าง workflow) | เชื่อมคำขอกับ Risk Library → Risk Context | AIDA-01 |
| 4 | Capability & Planning (ตามโครงสร้าง workflow) | Capability Gate และ Analysis Plan | AIDA-03 |
| 5 | Analysis Skills (ตามโครงสร้าง workflow) | Anomaly Skills 5.1–5.10 สร้าง Evidence | AIDA-04 ถึง AIDA-09 |
| 6 | Evidence, Findings & Assessment (ตามโครงสร้าง workflow) | Quality Gate, Unified Findings, Confidence/Materiality/Priority | AIDA-01, AIDA-10 |
| 7 | Interpretation | เกิดอะไรขึ้น เหตุใดจึงสำคัญ Potential Risk ข้อจำกัด | AIDA-11 |
| 8 | Reporting | Workbook, Executive Summary, Dashboard, Investigation Package | AIDA-12 |
| 9 | Intelligence | Natural-language query, Network exploration, Emerging Risk, Early Warning | AIDA-12 |
| 10 | Governance Control Plane | Audit Trail, Registry, Version, Change Control | AIDA-13 |

## อภิธานศัพท์
| คำ | ความหมาย |
|---|---|
| Evidence | ผลจาก Analysis Skill หนึ่งครั้ง: metric/score + explanation + source skill + data reference |
| Finding | ข้อสังเกตที่สร้างจาก Evidence ที่ผ่าน Quality Gate ผูกกับ entity, risk และช่วงเวลา |
| Unified Finding | Finding ที่ลบซ้ำและรวม Evidence หลายแหล่งที่เกี่ยวกับ entity/risk/time เดียวกัน |
| Alert | สัญญาณเตือนล่วงหน้า (Early Warning) แยกจาก Finding และต้องผ่าน Human Review |
| Capability Gate | การตรวจว่าข้อมูลรองรับ skill หรือไม่ ก่อนเรียกใช้ skill |
| Minimum Data Requirement | field และปริมาณข้อมูลขั้นต่ำที่ skill ต้องการ |
| Skip Reason | เหตุผลที่บันทึกเมื่อไม่รัน skill ใด |
| Decision Gate | จุดตัดสินใจ Accept / Stop / Skip / Re-run / Human Review |
| Lineage | เส้นทางอ้างอิงจากข้อมูลต้นทางถึงการทบทวน 7 ระดับ |
| Registry | Configuration Registry: แหล่งกฎ เกณฑ์ น้ำหนัก และเวอร์ชัน |
| Confidence | เรามั่นใจในข้อสังเกตมากเพียงใด |
| Materiality | ผลกระทบอาจมีนัยสำคัญเพียงใด |
| Priority | อะไรควรได้รับความสนใจก่อน |
| Human Review | การทบทวนโดยผู้ตรวจสอบก่อนเผยแพร่หรือดำเนินการ |
| Disposition | ผลการทบทวนของผู้ตรวจสอบ เช่น ยืนยันว่าต้องติดตาม / อธิบายได้ / ไม่ต้องดำเนินการ |
| Run ID | รหัสการรันแต่ละครั้ง ใช้ใน Execution Reference |
| Drill Down | การเจาะจาก Output ไปยัง Finding และ Evidence ต้นทาง |
| Potential Risk | ความเสี่ยงที่อาจเกิด ซึ่งยังต้องพิสูจน์ด้วย Audit Procedure |
| บทบาทคอลัมน์ (role) | ความหมายมาตรฐานของคอลัมน์ที่การ์ดใช้ เช่น record_id, date, amount, entity (AIDA-17) |
| Intake Review | ผลตรวจข้อมูลและคำอธิบายของผู้ตรวจสอบก่อนวิเคราะห์ ข้อ A–E — จุดยืนยันเดียวของการวิเคราะห์ (AIDA-19) |
| ตารางเหตุการณ์ (event table) | ตารางรองที่มีรหัสรายการ วันที่ และเลขที่กรมธรรม์/สัญญาของตัวเอง เช่น ประวัติการเปลี่ยนผู้รับผลประโยชน์ (L) — แนบได้ 1 ตารางต่อการวิเคราะห์ (AIDA-17, AIDA-19) |
| ค่ารหัส (`code_values`) | ความหมายของรหัสในคอลัมน์ประเภทรายการ (บทบาท category) เช่น SURR = เวนคืน ที่ผู้ตรวจสอบยืนยัน การ์ด L/F ที่แยกตามประเภทรายการข้ามจนกว่าจะยืนยัน (AIDA-19) |
| Risk Library | รายการความเสี่ยงที่ engine วิเคราะห์ได้ด้วยการ์ดรับรอง (AIDA-18) |
| การ์ดรับรอง (certified check) | ฟังก์ชันวิเคราะห์ใน engine ที่ทดสอบแล้ว อ่านเกณฑ์จาก AIDA-14 |
| โหมดสำรวจ | การวิเคราะห์คำถามนอกการ์ดรับรอง ผลติดป้าย "ยังไม่ผ่านการรับรอง" และ Confidence ไม่เกิน "กลาง" เมื่อเลื่อนเป็น Finding |

## ข้อห้าม (Guardrails)
- AIDA ไม่ใช่เครื่องมือตัดสินว่ามีการกระทำผิด — ชี้ความผิดปกติและ Potential Risk เท่านั้น
- AIDA ไม่ตัดสินแทนผู้ตรวจสอบ
- ทุกคำตอบต้องอ้างไฟล์และหัวข้อของ AIDA

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Workflow, AIDA-03 Selection Matrix, AIDA-13 Governance, AIDA-14 Registry, AIDA-15 Checklist
- AIDA-16 ติดตั้ง engine, AIDA-19 คู่มือเรียก engine
