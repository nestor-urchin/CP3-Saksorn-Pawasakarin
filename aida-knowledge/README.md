# AIDA Knowledge Pack

ชุดไฟล์ Knowledge สำหรับ **AIDA Agent** ใน Microsoft 365 Copilot Agent Builder
- ระยะ A: AIDA เป็นที่ปรึกษาด้านวิธีการ (เลือก skill, gate, การตีความ, output)
- ระยะ B1: วิเคราะห์ธุรกรรมโอนเงิน (Mule Accounts) ด้วยการ์ดสูตร 34 ใบ — **ถูกแทนที่ใน C1**
- ระยะ C1 (Knowledge Pack **3.0**): วิเคราะห์ข้อมูลจริงด้วย engine ไฟล์เดียวที่ทดสอบแล้ว `engine/aida_engine.py` v3.1.0 ซึ่งทำงานตามบทบาทคอลัมน์ — ข้อมูล **E โอนเงิน**, **C รับชำระค่างวดสินเชื่อ**, **A จ่ายเงินเจ้าหนี้**; Intake Review ยืนยันครั้งเดียว; โหมดสำรวจสำหรับคำถามนอกการ์ด

- Spec: `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md` (A), `2026-11-03-aida-phase-b1-design.md` (B1), `2026-11-06-aida-c1-generic-engine-design.md` (C1)
- เวอร์ชัน: Knowledge Pack 3.1 · engine 3.1.0 · Registry 1.3

## โครงสร้าง
```
aida-knowledge/
├── knowledge/                    ← อัปโหลดทั้งโฟลเดอร์ (20 ไฟล์ = โควตาเต็ม)
├── AIDA-agent-instructions.md    ← วางในช่อง Instructions (ไม่อัปโหลด, ≤ 8,000 ตัวอักษร)
├── engine/aida_engine.py         ← engine (แนวทาง 2: วางใน SharePoint/OneDrive หรือแนบในแชต — ไม่อยู่ใน knowledge/)
├── samples/                      ← ข้อมูลตัวอย่าง E (ไฟล์ที่ราก + E/brief.md), C/, A/ พร้อม brief.md และเฉลย answer_key.json
├── spike/, spike-c1/             ← ชุดทดสอบ Code Interpreter ของ B1 และ C1 (ไม่อัปโหลดเป็น Knowledge ถาวร)
├── tests/                        ← eval-questions.md (47 ข้อ) + unit / end-to-end tests ของ engine
└── tools/                        ← validate_pack.py, build_risk_library_md.py
```

| ไฟล์ Knowledge ของ C1 | เนื้อหา |
|---|---|
| `AIDA-16-engine-install.md` | วิธีโหลด `aida_engine.py` จาก SharePoint/OneDrive หรือไฟล์แนบ, ตรวจเวอร์ชัน, สิ่งที่ต้องบอกเมื่อโหลดไม่ได้ |
| `AIDA-17-roles-schema.md` | 14 บทบาท + custom, preset E/C/A, พจนานุกรมชื่อคอลัมน์, Schema และ output |
| `AIDA-18-risk-library.md` | Risk Library + การ์ดรับรองทุกใบ (ภาษาไทย ไม่มีโค้ด) — **สร้างจาก engine** ด้วย `tools/build_risk_library_md.py` |
| `AIDA-19-engine-guide.md` | ลำดับเรียก engine, brief / answers, Intake Review A–E, กติกาการยืนยัน, โหมดสำรวจ, mapping profile, การแก้ปัญหา |

template Dashboard อยู่ใน engine แล้ว (ไม่มีไฟล์ output template ใน Knowledge อีก)

## แนวทาง 2 และ 3 (ผล spike)
ยังไม่ได้รับผล spike ใน Copilot จึงใช้ **แนวทาง 2**: engine อยู่นอก Knowledge และ AIDA โหลดตาม `AIDA-16-engine-install.md`
ถ้าผล spike (`spike-c1/`, ใน zip คือ `6-spike-c1/`) แสดงว่า **prompt ข้อ 2 ผ่าน** (import ไฟล์จาก Knowledge ได้) ให้ใช้ **แนวทาง 3**: อัปโหลด `aida_engine.py` เข้า Knowledge **แทน** `AIDA-16-engine-install.md` (ยังเป็น 20 ไฟล์) — validator รองรับทั้งสองแบบ (ถ้ามี `knowledge/aida_engine.py` ต้องเหมือน `engine/aida_engine.py` ทุกไบต์) และควรปรับข้อความที่อ้าง AIDA-16 ใน Instructions / AIDA-19 ให้บอกว่า engine อยู่ใน Knowledge

## วิธีติดตั้งใน Agent Builder (ระยะ C1)
1. ลบไฟล์ Knowledge เดิมที่ไม่มีแล้ว: `AIDA-16-output-templates.md`, `AIDA-17-data-evidence-schema.md`, `AIDA-18-analysis-recipes.md`, `AIDA-19-pipeline-recipes.md` (และไฟล์ทดลองของ spike ถ้ามี)
2. อัปโหลดไฟล์ทั้งหมดใน `knowledge/` (**20 ไฟล์**) แล้วรอให้ index เสร็จ
3. เปิดใช้ **Code Interpreter** ใน Agent
4. คัดลอกเนื้อหา `AIDA-agent-instructions.md` ไปวางแทนข้อความเดิมในช่อง **Instructions**
5. วาง `engine/aida_engine.py` และ `knowledge/AIDA-14-configuration-registry.md` ไว้ในโฟลเดอร์เดียวกันบน SharePoint/OneDrive ของทีม (หรือแนบทั้งสองไฟล์ในแชตเมื่อจะวิเคราะห์)
6. ทดสอบด้วย `tests/eval-questions.md` (Q1–Q47) แล้วบันทึกผลในตารางท้ายไฟล์

ขั้นตอนที่ AIDA ทำเมื่อวิเคราะห์: โหลด engine (AIDA-16) → แยกคำอธิบายของผู้ตรวจสอบเป็น brief → `inspect` → แสดง **Intake Review** (A ความหมายคอลัมน์, B ความพอเพียง + Data Request, C เงื่อนไข, D ความเสี่ยงที่แนะนำ, E วันที่ / คุณภาพ / Materiality / แผน Run-Skip) → ผู้ตรวจสอบยืนยันครั้งเดียว → `confirm` + `run` ในคำตอบเดียวกัน → Workbook / Dashboard (+ CSV เครือข่ายสำหรับข้อมูล E)

## ความเสี่ยงที่ต้องรับทราบ
**ข้อมูลอ่อนไหว (PCI DSS / PDPA):** ทุก output แสดงข้อมูลบัญชีและธุรกรรมแบบเต็ม (ไม่ปิดบัง) ตามการตัดสินใจขององค์กร ไฟล์เหล่านี้จึงอาจอยู่ในขอบเขต PCI DSS / PDPA
- องค์กรต้องควบคุมการเข้าถึงไฟล์ output, ที่เก็บ และการส่งต่อเอง
- ทุก output มีป้ายเตือนข้อมูลอ่อนไหวข้อความเดียวกัน (`OUT_BANNER` ใน engine)
- C1 ยังไม่รองรับการปิดบังข้อมูล (masking)

**ข้อจำกัดของการหาเครือข่าย:** ใช้ข้อมูลธุรกรรมเท่านั้น (ไม่มีบัตรประชาชน เบอร์โทร ที่อยู่ อุปกรณ์) จึงไม่พบกลุ่มบัญชีที่เชื่อมกันด้วยข้อมูลร่วมโดยไม่มีธุรกรรมระหว่างกัน และบัญชีที่เป็นจุดรวมเงิน (hub ที่ทำหน้าที่ collector) อาจทำให้กลุ่มที่ไม่เกี่ยวข้องกันถูกรวมเป็นเครือข่ายเดียว — ควรทบทวนสมาชิกของแต่ละเครือข่ายก่อนสรุปผล

**ผลเป็นสัญญาณ ไม่ใช่ข้อสรุป:** ทุก Finding มีสถานะ "รอ Human Review"; ค่าเกณฑ์ Mule / Counterparty / Money Flow และหมวด 12 (จ่ายซ้ำ, แบ่งรายการ, ชำระใกล้วันครบกำหนด ฯลฯ) ใน AIDA-14 เป็นแนวปฏิบัติทั่วไป ไม่มีมาตรฐานทางการ องค์กรควรปรับตามบริบท

**ขนาดไฟล์ (ขีดที่ทดสอบแล้ว):** ไฟล์ใหญ่ที่สุดที่ทดสอบทั้งสายงาน (ข้อมูลจำลองแบบไม่เรียบร้อย: วันที่ พ.ศ., ยอดมีจุลภาค, บัญชีกิจกรรมหนาแน่น + hub) คือ **80,000 รายการ / 3,000 บัญชี / 6 เดือนต่อการรัน 1 ครั้ง** — ในเครื่อง ~35–39 วินาที, หน่วยความจำสูงสุด ~0.7 GB (pandas 3.0 และ 1.5.3 ได้ผลเท่ากัน; รายละเอียดใน `spike/LOCAL-RESULTS.md`)
- **ไฟล์เกิน 80,000 รายการ → แบ่งไฟล์ตามเดือน** แล้วรันทีละไฟล์ (Code Interpreter ใน Copilot มีขีดจำกัดเวลาและหน่วยความจำที่ยังไม่ได้วัด จึงไม่ควรเกินขนาดที่ทดสอบ)
- ข้อมูลหนาแน่นอาจทำให้ NET-CYCLE ค้นหาถึง `NET.CYCLE.MAX_PATHS` (ต่อเดือน) — engine แจ้งเดือนที่ผลอาจไม่ครบเป็น REVIEW ใน Run Log, README ของ Workbook และหน้าสรุปของ Dashboard; ถ้าต้องการผลครบ ให้แบ่งช่วงเวลาให้สั้นลงหรือจำกัดบัญชี

## การเปลี่ยนค่ามาตรฐาน
1. แก้ค่าใน `knowledge/AIDA-14-configuration-registry.md` (รูปแบบ `` `KEY = ค่า` ``) **และ** ค่าเดียวกันใน JSON หัวข้อ "Machine Config (สำหรับ recipe)" ท้ายไฟล์ (engine อ่านค่าจาก JSON นี้ — ไม่ต้องแตะโค้ด)
2. แก้ค่าเดียวกันในไฟล์ skill ที่อ้าง key นั้น (validator จะแจ้งถ้าไม่ตรง)
3. เพิ่มเวอร์ชัน (`REGISTRY.VERSION` ทั้งในตารางและ JSON และ `REGISTRY_VERSION` ใน engine) และบันทึกใน "ประวัติการเปลี่ยนแปลง" ของ AIDA-14
4. รัน validator และ tests แล้วอัปโหลด AIDA-14 ใหม่ทั้งใน Knowledge และข้าง engine บน SharePoint
- ค่าเฉพาะการรันครั้งเดียว: ผู้ตรวจสอบระบุ "ค่าขององค์กร" ที่ข้อ C ของ Intake Review ได้โดยไม่แก้ AIDA-14

## การตรวจไฟล์และรันเทสต์
ต้องมี Python 3 + pandas (≥ 1.5), numpy และ openpyxl (Dashboard ในเบราว์เซอร์ใช้ Node + Playwright ถ้ามี ไม่มีจะข้าม)
```bash
python3 aida-knowledge/tools/validate_pack.py aida-knowledge   # ตรวจทั้งชุด → "OK: 20 files validated"
python3 aida-knowledge/tools/build_risk_library_md.py           # สร้าง AIDA-18 ใหม่จาก engine (เมื่อแก้ RISK_LIBRARY / CHECKS)
cd aida-knowledge/tools && python3 -m unittest                  # ทดสอบ validator
cd aida-knowledge/tests && python3 -m unittest                  # unit + end-to-end ของ engine บนข้อมูลตัวอย่าง E / C / A
```

validator ตรวจ:
- Knowledge มี **20 ไฟล์พอดี** และไฟล์ .md มีหัวข้อบังคับครบ
- engine (`engine/aida_engine.py`): `__version__` ตรงกับที่ AIDA-00 และ AIDA-19 ระบุ (`` `aida_engine.py` v3.1.0 ``), `REGISTRY_VERSION` ตรงกับ `REGISTRY.VERSION` ใน AIDA-14, import เฉพาะ pandas / numpy / openpyxl / standard library (ไม่มีไลบรารีเครือข่าย), ทุก `cfg["KEY"]` มีใน Machine Config ของ AIDA-14
- Risk Library: ทุกความเสี่ยงอ้างการ์ดที่มีใน engine และบทบาทใน 14 บทบาท; AIDA-18 ตรงกับที่ `build_risk_library_md.py` สร้างจาก engine ทุกตัวอักษร
- Registry key ตรงกับ AIDA-14 และ Machine Config ตรงกับตาราง
- คำกล่าวหานอกหัวข้อ Guardrails (ทุจริต, กระทำผิด, กระทำความผิด, โกง, ยักยอก, คอร์รัปชัน, ฉ้อโกง, สมรู้ร่วมคิด, fraudster) — ยกเว้นเมื่อมีคำปฏิเสธ (≠ / ไม่ / ห้าม / not) อยู่ภายใน 20 ตัวอักษรก่อนคำนั้น
- ตาราง Priority และตาราง Confidence ใน AIDA-10 กับ AIDA-14 เหมือนกันทุกตัวอักษร
- การอ้างไฟล์ AIDA-XX ชี้ไปยังไฟล์ที่มีจริง
- ไฟล์ Instructions: ความยาว ≤ 8,000 ตัวอักษร และตรวจคำกล่าวหา / Registry key / การอ้างไฟล์ เหมือนไฟล์ Knowledge

`tools/extract_recipes.py` (ดึงการ์ด B1 จาก Markdown) ถูกลบใน C1 เพราะไม่มีการ์ดใน Knowledge แล้ว — tests โหลด engine โดยตรง (`tests/_engine.py`)

## ชุดไฟล์สำหรับส่งมอบ (AIDA-Knowledge-Pack-v3.1.zip)
```
AIDA-Knowledge-Pack/
├── 1-upload-knowledge/      ← 20 ไฟล์ อัปโหลดเป็น Knowledge
├── 2-paste-instructions/    ← AIDA-agent-instructions.md วางในช่อง Instructions
├── 3-test/                  ← eval-questions.md
├── 4-samples/E, C, A/       ← ข้อมูล, brief.md, answer_key.json (+ ชื่อคอลัมน์ 3 แบบใน variants/)
├── 5-engine/                ← aida_engine.py (วางบน SharePoint/OneDrive คู่กับ AIDA-14 หรือแนบในแชต)
├── 6-spike-c1/              ← ชุด spike (ไม่บังคับ)
└── README.md
```
