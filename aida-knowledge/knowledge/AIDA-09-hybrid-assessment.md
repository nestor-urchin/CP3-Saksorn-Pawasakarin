# AIDA-09 · 5.10 Hybrid Anomaly Assessment
> ไฟล์: AIDA-09 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: รวม Evidence จากหลาย skill อย่างไร, ถ้า Evidence ยืนยันกันหรือขัดแย้งกันทำอย่างไร, ทำไมห้ามรวมคะแนนตรง ๆ, Assessment Output มีอะไร

## สรุปสั้น
รวม Evidence อย่างมีหลักเกณฑ์ โดยรักษาความเป็นอิสระและความหมายดั้งเดิมของคะแนน
Evidence 4 ประเภท → Hybrid Logic (น้ำหนัก/สูตรจาก Configuration Registry) → Assessment Output
ไม่ทำให้ Statistical Score, Model Score และ Business Priority มีความหมายเดียวกัน
Evidence หลายชิ้นจากหลาย skill ที่เป็น entity + risk + time เดียวกัน → รวมเป็น **Unified Finding เดียว** ไม่แยกรายงาน (กฎการลบซ้ำและรวม Evidence ดู AIDA-01 หัวข้อ "Unified Findings")

## Evidence 4 ประเภท
| ประเภท | ความหมาย | มาจาก |
|---|---|---|
| Statistical Evidence | distribution / deviation | AIDA-04, AIDA-05 |
| Rule Evidence | configured exception | AIDA-07 (5.7) |
| ML Evidence | model anomaly score | AIDA-07 (5.8) |
| Network Evidence | relationship pattern | AIDA-08 |
Sequence, Temporal และ Forensic Evidence (AIDA-05, AIDA-06) จัดอยู่กลุ่ม Statistical/Rule ตามลักษณะของวิธี และต้องระบุ source skill เสมอ

## Hybrid Logic (6 หลัก)
1. น้ำหนัก/สูตรมาจาก Configuration Registry
2. รักษา Evidence ดั้งเดิม (ไม่แทนที่คะแนนเดิมด้วยคะแนนรวม)
3. ระบุ Source Skill ของ Evidence ทุกชิ้น
4. ประเมิน Evidence Diversity (มาจากกี่ประเภท)
5. ประเมิน Evidence Independence (ใช้ข้อมูล/วิธีที่เป็นอิสระต่อกันหรือไม่)
6. ห้ามรวมคะแนนโดยไม่มีหลักเกณฑ์

Evidence สองชิ้นที่ใช้ข้อมูลชุดเดียวกันด้วยวิธีคล้ายกัน (เช่น Z-Score และ IQR บนยอดเดียวกัน) ไม่นับว่าเป็นอิสระต่อกัน

## Assessment Output
- **Evidence map** — Evidence ทุกชิ้นของ Finding พร้อม source skill
- **Corroboration / conflict** — ชิ้นไหนยืนยันกัน ชิ้นไหนขัดแย้ง
- **Configured synthesis** — ผลสังเคราะห์ตามน้ำหนักใน Registry พร้อมเวอร์ชัน
- **Human-review flags** — จุดที่ต้องให้ผู้ตรวจสอบทบทวน

## ตัวอย่าง (Worked examples)
**กรณียืนยันกัน:** vendor A มียอดจ่ายโดดเด่นจาก MAD (Statistical) และเข้ากฎ "จ่ายก่อนรับของ" (Rule) — สองแหล่งเป็นอิสระต่อกัน และ Lineage ครบ → Confidence สูง ตามเกณฑ์ ASSESS.CONFIDENCE ใน AIDA-14 → ส่งต่อประเมิน Materiality และ Priority (AIDA-10)

**กรณีขัดแย้ง:** Isolation Forest ให้คะแนนสูงแก่ vendor B แต่ Peer Comparison พบว่าอยู่ในช่วงปกติของกลุ่ม → บันทึก conflict ใน Evidence map → Confidence ต่ำ → Human Review (AIDA-02) ห้ามเลือกเชื่อแหล่งใดแหล่งหนึ่งโดยไม่มีเหตุผล

## ข้อห้าม (Guardrails)
- ห้ามบวก/เฉลี่ยคะแนนจากต่างวิธีโดยไม่มีสูตรใน Registry
- ห้ามทำให้ Statistical Score, Model Score และ Business Priority มีความหมายเดียวกัน
- ห้ามนับ Evidence ที่ไม่อิสระต่อกันเป็นการยืนยันซ้ำ
- ห้ามซ่อน Evidence ที่ขัดแย้ง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Stage 9–12, AIDA-02 Human Review, AIDA-04 ถึง AIDA-08 Skill, AIDA-10 Assessment, AIDA-14 Registry
