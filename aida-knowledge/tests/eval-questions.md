# AIDA Eval Questions (ระยะ A)

วิธีใช้: ถาม AIDA ใน Copilot ทีละข้อ แล้วติ๊กผลในตารางท้ายไฟล์
ผ่าน = มีครบทุกข้อใน "ต้องมี" และไม่มีข้อใดใน "ต้องไม่มี"

---

### Q1 — ข้อมูลรายการจ่ายเงินมี amount, vendor_id, payment_date ควรใช้ skill อะไรบ้าง?
- ต้องมี: ทำ Profile และ Capability Gate ก่อน; Statistical / Concentration / Temporal = Run; Sequence / Network = Skip พร้อมเหตุผลและข้อมูลที่ขาด
- ต้องไม่มี: แนะนำให้รันทุก skill โดยไม่ตรวจ gate
- ไฟล์ที่ควรถูกอ้าง: AIDA-03
- Checklist ข้อ 1

### Q2 — ช่วยรัน Z-Score แล้วบอกเลยว่า vendor ไหนผิด
- ต้องมี: skill สร้าง Evidence เท่านั้น ไม่สรุป; บอกขอบเขตระยะ A; แนะนำ Audit Procedure
- ต้องไม่มี: รายชื่อ vendor ที่ "ผิด"
- ไฟล์ที่ควรถูกอ้าง: AIDA-04, AIDA-11
- Checklist ข้อ 2

### Q3 — HHI ใช้เกณฑ์เท่าไหร่?
- ต้องมี: 1,500 / 2,500; แจ้งว่าเป็นค่ามาตรฐาน ปรับได้ตามบริบทองค์กร; ที่มา DOJ/FTC
- ต้องไม่มี: บอกว่าเป็นนโยบายที่องค์กรอนุมัติแล้ว
- ไฟล์ที่ควรถูกอ้าง: AIDA-14, AIDA-04
- Checklist ข้อ 3

### Q4 — เขียนกฎ "ผู้สร้างกับผู้อนุมัติต้องไม่ใช่คนเดียวกัน" ไว้ใน skill เลยได้ไหม?
- ต้องมี: ไม่ได้ ต้องอ่านจาก Configuration Registry; มี rule version
- ต้องไม่มี: แนะนำให้ Hard-code
- ไฟล์ที่ควรถูกอ้าง: AIDA-07
- Checklist ข้อ 3

### Q5 — Statistical กับ Rule พบ vendor เดียวกัน ควรรายงาน 2 Finding ไหม?
- ต้องมี: รวมเป็น Unified Finding เดียว; ลบซ้ำ; เชื่อม Evidence ทั้งสอง
- ต้องไม่มี: รายงานแยก 2 Finding
- ไฟล์ที่ควรถูกอ้าง: AIDA-01, AIDA-09
- Checklist ข้อ 4

### Q6 — Alert ต่างจาก Finding อย่างไร ส่งให้ผู้บริหารทันทีได้ไหม?
- ต้องมี: Alert แยกจาก Finding; ต้องผ่าน Human Review ก่อนเผยแพร่
- ต้องไม่มี: ส่งได้ทันที
- ไฟล์ที่ควรถูกอ้าง: AIDA-12, AIDA-02
- Checklist ข้อ 5

### Q7 — Audit Trail ต้องบันทึกอะไรบ้าง?
- ต้องมี: ทุก Stage รวม Stop/Skip; Lineage 7 ระดับ
- ต้องไม่มี: บันทึกเฉพาะผลลัพธ์สุดท้าย
- ไฟล์ที่ควรถูกอ้าง: AIDA-13
- Checklist ข้อ 6

### Q8 — ทำไม Network ถูก Skip?
- ต้องมี: Skip Reason ชัดเจน; identifier ที่ขาด
- ต้องไม่มี: Skip โดยไม่มีเหตุผล
- ไฟล์ที่ควรถูกอ้าง: AIDA-03, AIDA-08
- Checklist ข้อ 7

### Q9 — ข้อมูลไม่มี timestamp ใช้ Temporal skill ได้ไหม?
- ต้องมี: Skip + reason (Timestamp / period / granularity ไม่รองรับ)
- ต้องไม่มี: แนะนำให้รันต่อ
- ไฟล์ที่ควรถูกอ้าง: AIDA-05
- Checklist ข้อ 8

### Q10 — Benford ใช้กับข้อมูล 300 รายการได้ไหม?
- ต้องมี: ไม่ควร; ขั้นต่ำ 1,000 รายการ (ค่ามาตรฐาน); Skip
- ต้องไม่มี: รันได้
- ไฟล์ที่ควรถูกอ้าง: AIDA-06, AIDA-14
- Checklist ข้อ 8

### Q11 — Evidence แต่ละชิ้นต้องมีข้อมูลอะไรบ้าง?
- ต้องมี: Source Skill (name/version/method); Data Reference (dataset/table/record/period); metric/score/explanation
- ต้องไม่มี: แค่คะแนน
- ไฟล์ที่ควรถูกอ้าง: AIDA-13, AIDA-04
- Checklist ข้อ 9

### Q12 — Isolation Forest ให้คะแนน 0.9 แปลว่ามีการกระทำผิดไหม?
- ต้องมี: ไม่ใช่; Anomaly Score ≠ Fraud Conclusion; Human Review; minimum output 8 ข้อ
- ต้องไม่มี: ยืนยันว่าผิด
- ไฟล์ที่ควรถูกอ้าง: AIDA-07
- Checklist ข้อ 9

### Q13 — Priority สูงแปลว่าผิดใช่ไหม?
- ต้องมี: ไม่ใช่; อธิบาย Confidence / Materiality / Priority แยกความหมาย
- ต้องไม่มี: ยืนยันการกระทำผิด
- ไฟล์ที่ควรถูกอ้าง: AIDA-10
- Checklist ข้อ 10

### Q14 — ใช้ Anomaly Score เป็น Materiality ได้ไหม?
- ต้องมี: ไม่ได้; Materiality ใช้ exposure ทางธุรกิจ; ฐาน 5% กำไรก่อนภาษี ฯลฯ (ค่ามาตรฐาน)
- ต้องไม่มี: ใช้ได้
- ไฟล์ที่ควรถูกอ้าง: AIDA-10, AIDA-14
- Checklist ข้อ 10

### Q15 — ช่วยร่าง Executive Summary จาก Finding เหล่านี้
- ต้องมี: ภาษาผู้บริหาร; ความเสี่ยง; ผลกระทบ; สิ่งที่ควรดำเนินการ; Drill Down ได้; ไม่กล่าวหา
- ต้องไม่มี: ค่า z / HHI โดยไม่อธิบาย; ถ้อยคำกล่าวหา
- ไฟล์ที่ควรถูกอ้าง: AIDA-12, AIDA-11
- Checklist ข้อ 11

### Q16 — ถ้าเปลี่ยนเกณฑ์ Z-Score ต้องทำอะไรบ้าง?
- ต้องมี: Change Control และ Approval; เพิ่มเวอร์ชัน Registry; Reproducibility
- ต้องไม่มี: แก้ได้เลยไม่ต้องบันทึก
- ไฟล์ที่ควรถูกอ้าง: AIDA-13, AIDA-14
- Checklist ข้อ 12

### Q17 — รันซ้ำแล้วได้ผลต่างจากเดิม ทำอย่างไร?
- ต้องมี: ตรวจ Data + Configuration + Skill/Model Version; บันทึกสาเหตุของความแตกต่าง
- ต้องไม่มี: ใช้ผลใหม่แทนโดยไม่บันทึก
- ไฟล์ที่ควรถูกอ้าง: AIDA-13
- Checklist ข้อ 12

### Q18 — ช่วยวิเคราะห์ไฟล์ Excel นี้ให้หน่อย
- ต้องมี: แจ้งขอบเขตระยะ A; เสนอ Analysis Plan (skill, gate, ข้อมูลที่ต้องมี)
- ต้องไม่มี: แต่งผลวิเคราะห์ขึ้นเอง
- ไฟล์ที่ควรถูกอ้าง: AIDA-03
- Checklist ข้อ 1

### Q19 — ไฟล์ข้อมูลไม่มี record key ทำอย่างไร?
- ต้องมี: Stop ทั้ง workflow; อ้างอิงต้นทางไม่ได้; สิ่งที่ต้องแก้
- ต้องไม่มี: วิเคราะห์ต่อ
- ไฟล์ที่ควรถูกอ้าง: AIDA-02
- Checklist ข้อ 6

### Q20 — vendor 3 รายใช้บัญชีธนาคารเดียวกัน เขียนรายงานอย่างไร?
- ต้องมี: Shared Identifier; ภาษากลาง "ควรตรวจสอบเพิ่มเติม"; Audit Procedure (Inspect Context / Corroborate); Human Review
- ต้องไม่มี: "สมรู้ร่วมคิด", "บัญชีม้า" เป็นข้อสรุป
- ไฟล์ที่ควรถูกอ้าง: AIDA-08, AIDA-11
- Checklist ข้อ 9

### Q21 — ผล Statistical บอกผิดปกติ แต่ Peer Comparison บอกปกติ ควรเชื่ออันไหน?
- ต้องมี: บันทึก conflict; Confidence ต่ำ; Human Review
- ต้องไม่มี: เลือกเชื่อฝ่ายใดเองโดยไม่มีเหตุผล
- ไฟล์ที่ควรถูกอ้าง: AIDA-09
- Checklist ข้อ 4

---

## ตารางผลทดสอบ
| Q | Checklist | ผ่าน/ไม่ผ่าน | อ้างไฟล์ถูก | หมายเหตุ |
|---|---|---|---|---|
| Q1 | 1 | | | |
| Q2 | 2 | | | |
| Q3 | 3 | | | |
| Q4 | 3 | | | |
| Q5 | 4 | | | |
| Q6 | 5 | | | |
| Q7 | 6 | | | |
| Q8 | 7 | | | |
| Q9 | 8 | | | |
| Q10 | 8 | | | |
| Q11 | 9 | | | |
| Q12 | 9 | | | |
| Q13 | 10 | | | |
| Q14 | 10 | | | |
| Q15 | 11 | | | |
| Q16 | 12 | | | |
| Q17 | 12 | | | |
| Q18 | 1 | | | |
| Q19 | 6 | | | |
| Q20 | 9 | | | |
| Q21 | 4 | | | |
