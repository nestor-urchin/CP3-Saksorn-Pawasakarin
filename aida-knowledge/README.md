# AIDA Knowledge Pack

ชุดไฟล์ Knowledge สำหรับ **AIDA Agent** ใน Microsoft 365 Copilot Agent Builder
- ระยะ A: AIDA เป็นที่ปรึกษาด้านวิธีการ (เลือก skill, gate, การตีความ, output)
- ระยะ B1: AIDA วิเคราะห์ข้อมูลธุรกรรมจริงด้วย Code Interpreter สำหรับ use case **Potential Unusual Transactions across Mule Accounts** โดยรันการ์ดสูตร (recipe) จาก Knowledge ตามตัวอักษร

- Spec ระยะ A: `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md`
- Spec ระยะ B1: `docs/superpowers/specs/2026-11-03-aida-phase-b1-design.md`
- Registry เวอร์ชัน: 1.1 · Knowledge Pack เวอร์ชัน: 2.0

## โครงสร้าง
```
aida-knowledge/
├── knowledge/                    ← อัปโหลดทั้งโฟลเดอร์ (20 ไฟล์ = โควตาเต็ม)
├── AIDA-agent-instructions.md    ← วางในช่อง Instructions (ไม่อัปโหลด, ≤ 8,000 ตัวอักษร)
├── samples/                      ← ข้อมูลตัวอย่าง (transactions.csv, accounts.csv) + เฉลย answer_key.json
├── spike/                        ← ชุดทดสอบ Code Interpreter (ไม่อัปโหลดเป็น Knowledge ถาวร)
├── tests/                        ← eval-questions.md (31 ข้อ) + unit / end-to-end tests ของการ์ด
└── tools/                        ← validate_pack.py, extract_recipes.py
```

| ไฟล์ใหม่ใน B1 | เนื้อหา |
|---|---|
| `AIDA-16-output-templates.md` | sheet ของ Audit Workbook, คอลัมน์ nodes/edges/flows.csv, template HTML Dashboard |
| `AIDA-17-data-evidence-schema.md` | คอลัมน์มาตรฐาน, Schema Evidence / Finding / Mule Network / Money Flow trail / Run Log, Data Reference, R1–R4 |
| `AIDA-18-analysis-recipes.md` | การ์ดวิเคราะห์ 15 ใบ (STAT, BEH, TEMP, NET, MULE, CPTY, FLOW) |
| `AIDA-19-pipeline-recipes.md` | การ์ด pipeline / ช่วย / output 19 ใบ (เตรียมข้อมูล, Gate, รวมผล, ประเมิน, Run Log, Output) |

## วิธีติดตั้งใน Agent Builder (ระยะ B1)
1. ถ้าเคยอัปโหลด `AIDA-SPIKE-recipes.md` (จาก spike) ไว้ใน Knowledge ให้ **ลบออกก่อน** — ไฟล์นี้ใช้ทดสอบเท่านั้นและจะทำให้เกินโควตา 20 ไฟล์
2. อัปโหลดไฟล์ทั้งหมดใน `knowledge/` (**20 ไฟล์**) เป็น Knowledge (แทนที่ไฟล์เดิมของระยะ A ทุกไฟล์ที่ชื่อซ้ำ) แล้วรอให้ index เสร็จ
3. เปิดใช้ **Code Interpreter** ใน Agent (ตั้งค่า Capabilities)
4. คัดลอกเนื้อหา `AIDA-agent-instructions.md` ไปวางแทนข้อความเดิมในช่อง **Instructions**
5. ทดสอบด้วย `tests/eval-questions.md` (Q1–Q31; Q22–Q31 เป็นของระยะ B1 ใช้ไฟล์ใน `samples/`) แล้วบันทึกผลในตารางท้ายไฟล์

ขั้นตอนที่ AIDA ทำเมื่อวิเคราะห์ (Instructions กฎข้อ 7): รับไฟล์ → เสนอ mapping คอลัมน์ → **จุดยืนยัน 1** (mapping, รูปแบบวันที่, ฐาน Materiality) → Dataset Profile (STOP ถ้าไม่มี tx_id) → Analysis Plan → **จุดยืนยัน 2** (Run/Skip) → การ์ดวิเคราะห์ → รวมผลและประเมิน → ไล่เส้นทางเงินอัตโนมัติ → ส่งไฟล์ Output
Output ที่ได้: Audit Workbook (.xlsx), Network Investigation Package (nodes.csv, edges.csv, flows.csv) และ HTML Interactive Dashboard (ไฟล์เดียว)

## ความเสี่ยงที่ต้องรับทราบ
**ข้อมูลอ่อนไหว (PCI DSS / PDPA):** ทุก output แสดงข้อมูลบัญชีและธุรกรรมแบบเต็ม (ไม่ปิดบัง) ตามการตัดสินใจขององค์กร ไฟล์เหล่านี้จึงอาจอยู่ในขอบเขต PCI DSS / PDPA
- องค์กรต้องควบคุมการเข้าถึงไฟล์ output, ที่เก็บ และการส่งต่อเอง
- ทุก output มีป้ายเตือนข้อมูลอ่อนไหวข้อความเดียวกัน (`OUT_BANNER` ในการ์ด OUT-BUNDLE)
- ถ้าองค์กรต้องการปิดบังข้อมูล (masking) แก้ได้ที่การ์ด OUT-* ใน AIDA-19 จุดเดียว (B1 ยังไม่รองรับ)

**ข้อจำกัดของการหาเครือข่าย:** ใช้ข้อมูลธุรกรรมเท่านั้น (ไม่มีบัตรประชาชน เบอร์โทร ที่อยู่ อุปกรณ์) จึงไม่พบกลุ่มบัญชีที่เชื่อมกันด้วยข้อมูลร่วมโดยไม่มีธุรกรรมระหว่างกัน และบัญชีที่เป็นจุดรวมเงิน (hub ที่ทำหน้าที่ collector) อาจทำให้กลุ่มที่ไม่เกี่ยวข้องกันถูกรวมเป็นเครือข่ายเดียว — ควรทบทวนสมาชิกของแต่ละเครือข่ายก่อนสรุปผล

**ผลเป็นสัญญาณ ไม่ใช่ข้อสรุป:** ทุก Finding มีสถานะ "รอ Human Review"; ค่าเกณฑ์ Mule / Counterparty / Money Flow ใน AIDA-14 เป็นแนวปฏิบัติทั่วไป ไม่มีมาตรฐานทางการ องค์กรควรปรับตามบริบท

**ขนาดไฟล์:** Code Interpreter มีขีดจำกัดขนาดไฟล์และเวลาประมวลผล ถ้าไฟล์ใหญ่ ให้แบ่งไฟล์ตามช่วงเวลา (เช่น รายเดือน/ไตรมาส)

## สิ่งที่ยังไม่ได้ยืนยันใน Copilot จริง (จาก spike)
spike ทดสอบในเครื่องผ่านแล้ว (`spike/LOCAL-RESULTS.md`: pandas 1.5.3, openpyxl, Chromium) แต่ 3 เรื่องต่อไปนี้ทดสอบได้เฉพาะใน Copilot และตรวจใน eval ระยะ B (Q26, Q27, Q22 ตามลำดับ):
1. Copilot ดึงการ์ดยาวและ template Dashboard ใน AIDA-16 มาครบทุกบรรทัด (เห็นบรรทัดปิดของการ์ด และ `<!-- END-OF-TEMPLATE -->`)
2. Code Interpreter อ่านไฟล์จาก SharePoint/OneDrive ได้
3. Copilot ให้ลิงก์ดาวน์โหลดไฟล์ .xlsx / .csv / .html ที่สร้างได้
ถ้าข้อใดไม่ผ่าน ให้บันทึกในตารางผลของ eval และปรับ design ก่อนใช้งานจริง (เช่น แนบไฟล์ในแชทแทน SharePoint, แยก template เป็นส่วน)

## การเปลี่ยนค่ามาตรฐาน
1. แก้ค่าใน `knowledge/AIDA-14-configuration-registry.md` (รูปแบบ `` `KEY = ค่า` ``) **และ** ค่าเดียวกันใน JSON หัวข้อ "Machine Config (สำหรับ recipe)" ท้ายไฟล์ (การ์ดอ่านค่าจาก JSON นี้)
2. แก้ค่าเดียวกันในไฟล์ skill / การ์ดที่อ้าง key นั้น (validator จะแจ้งถ้าไม่ตรง)
3. เพิ่มเวอร์ชัน (`REGISTRY.VERSION` ทั้งในตารางและ JSON) และบันทึกใน "ประวัติการเปลี่ยนแปลง" ของ AIDA-14
4. รัน validator และ tests แล้วอัปโหลดไฟล์ที่แก้ใหม่

## การตรวจไฟล์และรันเทสต์
ต้องมี Python 3; tests ของการ์ดต้องมี pandas (≥ 1.5), numpy และ openpyxl (Dashboard ในเบราว์เซอร์ใช้ Node + Playwright ถ้ามี ไม่มีจะข้าม)
```bash
python3 aida-knowledge/tools/validate_pack.py aida-knowledge   # ตรวจทั้งชุด → "OK: 20 files validated"
cd aida-knowledge/tools && python3 -m unittest                  # ทดสอบ validator และ extract_recipes
cd aida-knowledge/tests && python3 -m unittest                  # unit + end-to-end ของการ์ดทั้ง 34 ใบบนข้อมูลตัวอย่าง
python3 aida-knowledge/tests/make_sample_data.py                # สร้าง samples/ ใหม่ (seed คงที่)
```
tests ดึงโค้ดจาก AIDA-18/19 ด้วย `tools/extract_recipes.py` จึงทดสอบโค้ดชุดเดียวกับที่ AIDA รันใน Copilot และตรวจว่าผล (19 Unified Finding, 1 เครือข่าย) ตรงกับ `samples/answer_key.json`

validator ตรวจ:
- จำนวนไฟล์ ≤ 20 และหัวข้อบังคับครบ
- Registry key ตรงกับ AIDA-14 (รวมรูปแบบที่เว้นวรรคต่างกัน เช่น `KEY=ค่า`) และ key ใน `cfg[...]` / Machine Config มีในตาราง AIDA-14
- หัวการ์ด 2 บรรทัดตามรูปแบบ และโค้ดการ์ด ≤ 40 บรรทัด (ยกเว้น template ใน AIDA-16)
- คำกล่าวหานอกหัวข้อ Guardrails (ทุจริต, กระทำผิด, กระทำความผิด, โกง, ยักยอก, คอร์รัปชัน, ฉ้อโกง, สมรู้ร่วมคิด, fraudster) — ยกเว้นเมื่อมีคำปฏิเสธ (≠ / ไม่ / ห้าม / not) อยู่ภายใน 20 ตัวอักษรก่อนคำนั้น
- ตาราง Priority และตาราง Confidence ใน AIDA-10 กับ AIDA-14 ต้องเหมือนกันทุกตัวอักษร
- การอ้างไฟล์ AIDA-XX ชี้ไปยังไฟล์ที่มีจริง
- ไฟล์ Instructions: ความยาว ≤ 8,000 ตัวอักษร และตรวจคำกล่าวหา / Registry key / การอ้างไฟล์ เหมือนไฟล์ Knowledge

## ชุดไฟล์สำหรับส่งมอบ (AIDA-Knowledge-Pack-v2.0.zip)
```
AIDA-Knowledge-Pack/
├── 1-upload-knowledge/      ← 20 ไฟล์ .md อัปโหลดเป็น Knowledge
├── 2-paste-instructions/    ← AIDA-agent-instructions.md วางในช่อง Instructions
├── 3-test/                  ← eval-questions.md
├── 4-samples/               ← transactions.csv, accounts.csv, answer_key.json สำหรับ eval Q22–Q31
└── README.md
```
