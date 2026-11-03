# AIDA Knowledge Pack

ชุดไฟล์ Knowledge สำหรับ **AIDA Agent** ใน Microsoft 365 Copilot Agent Builder
ระยะ A: AIDA เป็นที่ปรึกษาด้านวิธีการ (เลือก skill, gate, การตีความ, output) ยังไม่วิเคราะห์ข้อมูลจริง

- Spec: `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md`
- Registry เวอร์ชัน: 1.0

## โครงสร้าง
```
aida-knowledge/
├── knowledge/                    ← อัปโหลดทั้งโฟลเดอร์ (16 ไฟล์ จากโควตา 20)
├── AIDA-agent-instructions.md    ← วางในช่อง Instructions (ไม่อัปโหลด)
├── tests/eval-questions.md       ← คำถามทดสอบ 21 ข้อ
└── tools/validate_pack.py        ← สคริปต์ตรวจไฟล์
```

## วิธีติดตั้งใน Agent Builder
1. **ทดลองก่อน:** อัปโหลด `knowledge/AIDA-00-index-principles.md` 1 ไฟล์ เพื่อเช็กว่า tenant รับไฟล์ .md
   - ถ้าไม่รับ: เปลี่ยนนามสกุลเป็น `.txt` (เนื้อหาเหมือนเดิม) หรือแปลงเป็น .docx
2. อัปโหลดไฟล์ทั้งหมดใน `knowledge/` (16 ไฟล์) เป็น Knowledge
3. คัดลอกเนื้อหา `AIDA-agent-instructions.md` ไปวางในช่อง **Instructions**
4. ทดสอบด้วย `tests/eval-questions.md` แล้วบันทึกผลในตารางท้ายไฟล์

## ช่องสงวนสำหรับระยะ B (ยังไม่สร้าง)
| # | ไฟล์ที่วางแผน | เนื้อหา |
|---|---|---|
| 16 | `AIDA-16-output-templates.md` | Template ของ Output 16 แบบ |
| 17 | `AIDA-17-evidence-schema.md` | Schema ของ Evidence / Finding / Lineage record |
| 18 | `AIDA-18-calculation-recipes.md` | สูตรและขั้นตอนคำนวณของแต่ละเทคนิค |
| 19 | `AIDA-19-run-log-template.md` | Template ของ Audit Trail / run log |

ระยะ B ต้องเปิด Code Interpreter ใน Agent และปรับกฎข้อ 7 ใน Instructions

## การเปลี่ยนค่ามาตรฐาน
1. แก้ค่าใน `knowledge/AIDA-14-configuration-registry.md` (รูปแบบ `` `KEY = ค่า` ``)
2. แก้ค่าเดียวกันในไฟล์ skill ที่อ้าง key นั้น (validator จะแจ้งถ้าไม่ตรง)
3. เพิ่มเวอร์ชันและบันทึกใน "ประวัติการเปลี่ยนแปลง" ของ AIDA-14
4. รัน validator แล้วอัปโหลดไฟล์ที่แก้ใหม่

## การตรวจไฟล์
```bash
python3 aida-knowledge/tools/validate_pack.py aida-knowledge     # ตรวจทั้งชุด
cd aida-knowledge/tools && python3 -m unittest test_validate_pack # ทดสอบสคริปต์
```
สคริปต์ตรวจ:
- จำนวนไฟล์ ≤ 20 และหัวข้อบังคับครบ
- Registry key ตรงกับ AIDA-14 (รวมรูปแบบที่เว้นวรรคต่างกัน เช่น `KEY=ค่า`)
- คำกล่าวหานอกหัวข้อ Guardrails (ทุจริต, กระทำผิด, กระทำความผิด, โกง, ยักยอก, คอร์รัปชัน, ฉ้อโกง, สมรู้ร่วมคิด, fraudster) — ยกเว้นเมื่อมีคำปฏิเสธ (≠ / ไม่ / ห้าม / not) อยู่ภายใน 20 ตัวอักษรก่อนคำนั้น
- ตาราง Priority และตาราง Confidence ใน AIDA-10 กับ AIDA-14 ต้องเหมือนกันทุกตัวอักษร
- การอ้างไฟล์ AIDA-XX ชี้ไปยังไฟล์ที่มีจริง
- ไฟล์ Instructions: ความยาว ≤ 8,000 ตัวอักษร และตรวจคำกล่าวหา / Registry key / การอ้างไฟล์ เหมือนไฟล์ Knowledge
ต้องการแค่ Python 3 (ไม่มี dependency)
