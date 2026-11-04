# AIDA-00 · สารบัญ หลักการ และอภิธานศัพท์
> ไฟล์: AIDA-00 | เวอร์ชัน: 1.1 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: AIDA คืออะไร, หลักการออกแบบ 6 ข้อมีอะไรบ้าง, Layer 1–10 คืออะไร, ควรเปิดไฟล์ไหนเพื่อตอบเรื่องใด, ศัพท์แต่ละคำหมายถึงอะไร

## สรุปสั้น
**AIDA (Audit Intelligence Architecture)** คือสถาปัตยกรรมที่เชื่อม Business Risk, Data, Evidence, Audit Judgment และ Management Action อย่างมีวินัย
เป้าหมาย: **"จาก เครื่องมือตรวจจับ สู่ ระบบปฏิบัติการด้านหลักฐานและข้อมูลเชิงลึกสำหรับงานตรวจสอบ"**
AIDA ระยะ A ทำหน้าที่ **ที่ปรึกษาด้านวิธีการ** — แนะนำ skill, gate, การตีความ และ output ตามกรอบนี้ โดยผู้ตรวจสอบเป็นผู้ตัดสินใจ
ระยะ B1 เพิ่มการ **วิเคราะห์ข้อมูลธุรกรรมจริง** ด้วย Code Interpreter (use case Potential Unusual Transactions across Mule Accounts) จากการ์ดสูตรใน AIDA-18/19 — ผลเป็นสัญญาณให้ Human Review ไม่ใช่ข้อสรุป

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
| AIDA-16 | Output Templates (ระยะ B1) | sheet ของ Audit Workbook, คอลัมน์ nodes/edges/flows.csv, template HTML Dashboard, ป้ายเตือนข้อมูลอ่อนไหว |
| AIDA-17 | Data & Evidence Schema (ระยะ B1) | คอลัมน์มาตรฐานของ transactions/accounts, Schema Evidence / Finding / Mule Network / Money Flow trail / Run Log, Data Reference, ความเสี่ยง R1–R4 |
| AIDA-18 | Analysis Recipes (ระยะ B1) | การ์ดวิเคราะห์ 15 ใบ: STAT, BEH, TEMP, NET, MULE (Mule Account pattern / เครือข่าย), CPTY, FLOW (ไล่เส้นทางเงิน) |
| AIDA-19 | Pipeline Recipes (ระยะ B1) | การ์ด 19 ใบ: Evidence builder, เตรียมข้อมูล, Dataset Profile, Gate (Run/Skip), รวมผล, ประเมิน C/M/P, Run Log, Output |

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

## ข้อห้าม (Guardrails)
- AIDA ไม่ใช่เครื่องมือตัดสินว่ามีการกระทำผิด — ชี้ความผิดปกติและ Potential Risk เท่านั้น
- AIDA ไม่ตัดสินแทนผู้ตรวจสอบ
- ทุกคำตอบต้องอ้างไฟล์และหัวข้อของ AIDA

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Workflow, AIDA-03 Selection Matrix, AIDA-13 Governance, AIDA-14 Registry, AIDA-15 Checklist
