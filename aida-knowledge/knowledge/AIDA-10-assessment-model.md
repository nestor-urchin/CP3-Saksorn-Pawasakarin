# AIDA-10 · Assessment Model: Confidence, Materiality, Priority
> ไฟล์: AIDA-10 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Confidence / Materiality / Priority ต่างกันอย่างไร, แต่ละระดับใช้เกณฑ์อะไร, Priority คำนวณอย่างไร, Priority สูงแปลว่ามีความผิดไหม

## สรุปสั้น
Confidence, Materiality และ Priority ตอบคำถามต่างกันและต้องไม่ใช้แทนกัน
| มิติ | คำถาม |
|---|---|
| Confidence | เรามั่นใจในข้อสังเกตมากเพียงใด? |
| Materiality | ผลกระทบอาจมีนัยสำคัญเพียงใด? |
| Priority | อะไรควรได้รับความสนใจก่อน? |
ประเมินตามลำดับ Stage 13 → 14 → 15 (AIDA-01)

## Confidence
**Considerations:** Evidence quality, Consistency, Source traceability, Diversity / independence

### ตาราง Confidence
เกณฑ์ ASSESS.CONFIDENCE ใน AIDA-14 (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร)
| ระดับ | เกณฑ์ |
|---|---|
| สูง | Evidence ≥ 2 แหล่งที่เป็นอิสระต่อกันยืนยันตรงกัน และ Lineage ครบทั้ง 7 ระดับ |
| กลาง | Evidence 1 แหล่ง และ Lineage ครบ |
| ต่ำ | Evidence ขัดแย้งกัน หรือ Lineage ไม่ครบ → ส่ง Human Review |

## Materiality
**Considerations:** Magnitude / exposure, Scope / prevalence, Business impact, Risk context

ฐานคำนวณ: `ASSESS.MATERIALITY = 5% กำไรก่อนภาษี / 0.5–1% รายได้ / 1–2% สินทรัพย์รวม` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
ระดับที่ถือว่าเล็กน้อยมาก: `ASSESS.CLEARLY_TRIVIAL = < 5% ของ Materiality` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)

| ระดับ | เกณฑ์ |
|---|---|
| สูง | exposure ตั้งแต่ระดับ Materiality ขึ้นไป หรือมีปัจจัยเชิงคุณภาพสำคัญ (กฎหมาย ชื่อเสียง ผู้บริหาร) |
| กลาง | ตั้งแต่ระดับ Clearly trivial แต่ต่ำกว่า Materiality |
| ต่ำ | ต่ำกว่าระดับ Clearly trivial และไม่มีปัจจัยเชิงคุณภาพ |

ใช้ exposure ทางธุรกิจ (ยอดเงิน จำนวนรายการที่ได้รับผลกระทบ ความแพร่หลาย) ไม่ใช้ Anomaly Score

## Priority
**Considerations:** Confidence, Materiality, Urgency, Configured criteria

Priority = ตาราง Confidence × Materiality แล้ว **ปรับขึ้น 1 ระดับ** เมื่อเร่งด่วน (Urgency) หรือเข้าเกณฑ์ที่องค์กรกำหนด (Configured criteria) — สูงสุดที่ระดับ สูง (ASSESS.PRIORITY ใน AIDA-14)

### ตาราง Priority
| Confidence \ Materiality | สูง | กลาง | ต่ำ |
|---|---|---|---|
| สูง | สูง | กลาง | ต่ำ |
| กลาง | สูง | กลาง | ต่ำ |
| ต่ำ | กลาง + Human Review | ต่ำ | ต่ำ |

## ตัวอย่าง
Finding: ยอดจ่าย vendor A ใต้วงเงินอนุมัติซ้ำหลายครั้ง
- Confidence **สูง** (Forensic + Rule ยืนยันกัน, Lineage ครบ)
- Materiality **กลาง** (exposure สูงกว่า Clearly trivial แต่ต่ำกว่า Materiality)
- ตาราง → **กลาง**; ใกล้ปิดงบและเข้าเกณฑ์องค์กร → ปรับขึ้นเป็น Priority **สูง**
- การสื่อสาร: "ควรตรวจสอบก่อน" — ไม่ใช่ "ยืนยันการกระทำผิด"

## ข้อห้าม (Guardrails)
**ข้อห้าม: ห้ามตีความ Priority สูงว่าเป็นการยืนยันการกระทำผิด และห้ามใช้ Model Score เป็น Materiality โดยตรง**
- ห้ามรวม Confidence, Materiality และ Priority เป็นคะแนนเดียว
- ต้องรายงานทั้ง 3 มิติแยกกันทุกครั้ง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Stage 13–15, AIDA-02 Human Review, AIDA-09 Hybrid, AIDA-12 Output 06–08, AIDA-14 Registry
