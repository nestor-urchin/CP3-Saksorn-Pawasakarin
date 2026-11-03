# AIDA-02 · Decision Gates: Stop, Skip และ Human Review
> ไฟล์: AIDA-02 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: เมื่อไหร่ต้องหยุด workflow, เมื่อไหร่ต้องข้าม skill, อะไรต้องส่งให้ผู้ตรวจสอบทบทวน, ต้องบันทึกอะไรใน Audit Trail

## สรุปสั้น
การหยุดและการข้ามเป็นผลลัพธ์ที่ถูกต้อง เมื่อระบบอธิบายเหตุผลและบันทึก Audit Trail
- **STOP** = ยุติทั้ง workflow เพราะ input เชื่อถือไม่ได้
- **SKIP** = ข้ามเฉพาะ analysis ที่ข้อมูลไม่รองรับ workflow เดินต่อ
- **HUMAN REVIEW** = ส่งให้ผู้ตรวจสอบทบทวนก่อนเผยแพร่หรือดำเนินการ

## STOP
**เงื่อนไข (อย่างใดอย่างหนึ่ง)**
- Input ใช้ไม่ได้ (format ผิด เปิดไม่ได้ เข้าถึงไม่ได้)
- อ้างอิงต้นทางไม่ได้ — ขาดข้อมูลอ้างอิงขั้นต่ำ `GATE.TRACE.REQUIRED = dataset + table + period + record key` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- ไม่สามารถประมวลผลอย่างน่าเชื่อถือ

**Action:** ยุติ workflow และบันทึก error/exception

**บันทึกใน Audit Trail:** Run ID, Stage ที่หยุด, สาเหตุ, input ที่เกี่ยวข้อง, สิ่งที่ผู้ใช้ต้องแก้ไขเพื่อเริ่มใหม่

## SKIP
**เงื่อนไข (อย่างใดอย่างหนึ่ง)**
- Dataset ไม่รองรับ skill (ขาด field ตาม Minimum capability — AIDA-03)
- ต่ำกว่า Minimum Data Requirement เช่น field จำเป็นมีค่าครบต่ำกว่า `GATE.COMPLETENESS.MIN = 95%` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) หรือจำนวนรายการต่อกลุ่มต่ำกว่า `GATE.SAMPLE.MIN = 30` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- ไม่มี baseline หรือ relationship ที่ skill ต้องใช้

**Action:** ข้ามเฉพาะ analysis นั้น และบันทึก Skip Reason

**บันทึกใน Audit Trail:** skill ที่ข้าม, gate ที่ไม่ผ่าน, field/ปริมาณที่ขาด, ค่า Registry ที่ใช้ตัดสิน, ข้อมูลที่ต้องเพิ่มหากต้องการรัน

## HUMAN REVIEW
**เงื่อนไข (อย่างใดอย่างหนึ่ง)**
- Evidence ขัดแย้งกัน
- Confidence ต่ำ (AIDA-10)
- Alert ใหม่ (Early Warning)
- ML หรือ Network pattern ที่ต้องตีความ
- Output ใด ๆ ก่อนนำไปใช้

**Action:** ส่งให้ผู้ตรวจสอบทบทวนก่อนเผยแพร่หรือดำเนินการ

**บันทึกใน Audit Trail (Review Reference):** decision, reviewer, disposition, วันที่, เหตุผล

## ตารางเทียบ 3 Gate
| | STOP | SKIP | HUMAN REVIEW |
|---|---|---|---|
| ขอบเขตผลกระทบ | ทั้ง workflow | skill เดียว | finding / alert / output |
| workflow เดินต่อ | ไม่ | ใช่ | รอผลทบทวน |
| ต้องมีเหตุผล | ใช่ | ใช่ (Skip Reason) | ใช่ (Disposition) |
| ผู้ตัดสินใจ | ระบบตามเกณฑ์ | ระบบตามเกณฑ์ | ผู้ตรวจสอบ |

## ตัวอย่างการตอบผู้ใช้
- "ไฟล์ไม่มีคอลัมน์ record key จึงอ้างอิงต้นทางไม่ได้ → **Stop** กรุณาเพิ่มรหัสรายการแล้วเริ่มใหม่"
- "ข้อมูลไม่มี timestamp → Temporal Anomaly **Skip** เหตุผล: Timestamp / period / granularity ไม่รองรับ"
- "Isolation Forest ให้คะแนนสูง → ต้อง **Human Review** ก่อนนำไปใช้ คะแนนสูงไม่ใช่ข้อสรุป"

## ข้อห้าม (Guardrails)
- ห้าม Skip หรือ Stop โดยไม่ระบุเหตุผล
- ห้ามเผยแพร่ Alert หรือผล ML ก่อน Human Review
- ห้ามรัน skill ต่อเมื่อไม่ผ่าน Minimum Data Requirement เพื่อ "ลองดู"

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Workflow, AIDA-03 Selection Matrix, AIDA-10 Confidence, AIDA-13 Audit Trail, AIDA-14 Registry
