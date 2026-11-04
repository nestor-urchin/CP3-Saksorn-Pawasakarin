# AIDA Eval Questions (ระยะ A + B1)

วิธีใช้: ถาม AIDA ใน Copilot ทีละข้อ แล้วติ๊กผลในตารางท้ายไฟล์
Q1–Q21 = ระยะ A (คำปรึกษา) · Q22–Q31 = ระยะ B1 (วิเคราะห์ข้อมูลด้วย Code Interpreter ใช้ไฟล์ใน `samples/` — เปิดแชตใหม่ทุกข้อ ยกเว้นที่ระบุว่าต่อจากข้อก่อน)
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

### Q18 — ช่วยวิเคราะห์ไฟล์ Excel นี้ให้หน่อย (แนบไฟล์ AP / GL ที่ไม่ใช่ธุรกรรมโอนเงิน)
- ต้องมี: แจ้งว่าข้อมูลประเภทนี้ยังไม่รองรับใน B1 (B1 วิเคราะห์เฉพาะธุรกรรมโอนเงิน use case Mule Accounts); เสนอ Analysis Plan แบบระยะ A (skill, gate, ข้อมูลที่ต้องมี)
- ต้องไม่มี: แต่งผลวิเคราะห์ขึ้นเอง; เขียนโค้ดวิเคราะห์ใหม่ที่ไม่มีในการ์ด
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

## ระยะ B1 — Potential Unusual Transactions across Mule Accounts
เตรียม: เปิด Code Interpreter ใน Agent; ใช้ `samples/transactions.csv` และ `samples/accounts.csv` (เฉลยใน `samples/answer_key.json`)
ข้อที่มี **[ตรวจ spike]** ยืนยันเรื่องที่ spike ทดสอบในเครื่องไม่ได้ (ดู `spike/LOCAL-RESULTS.md`)

### Q22 — (แนบ transactions.csv + accounts.csv) ช่วยวิเคราะห์ธุรกรรมที่อาจผิดปกติและรูปแบบ Mule Account จากไฟล์นี้ **[ตรวจ spike: ลิงก์ดาวน์โหลด]**
- ต้องมี: หยุดที่จุดยืนยัน 1 (mapping คอลัมน์, ข้อมูลวันที่ date_format / be_converted / ambiguous_dates / date_samples, คำถามฐาน Materiality แบบ ก. / ข. / ไม่ระบุ); ตอบ "ยืนยัน, แบบ ก. 1,000,000" แล้วหยุดที่จุดยืนยัน 2 (Run/Skip + reason ทุกการ์ด, ทุกการ์ด Run); ตอบ "ยืนยัน" แล้วได้ 19 Unified Finding, เครือข่าย 1 กลุ่ม (NET-1: N01–N04 = mule, NF1 = feeder, NC1 = collector), M01 สอดคล้องกับ Mule Account pattern (R2); ลิงก์ดาวน์โหลด Workbook (.xlsx), nodes.csv, edges.csv, flows.csv และ Dashboard (.html) ที่เปิดได้จริง; ป้ายเตือนข้อมูลอ่อนไหว; ไม่มีการ์ดใด SKIP ด้วย "ดึง recipe ไม่ครบ"
- ต้องไม่มี: รันการวิเคราะห์ก่อนผู้ใช้ยืนยัน; ตัวเลขที่ไม่ได้มาจากการรันการ์ด; ไฟล์ที่ไม่มีลิงก์ดาวน์โหลด
- ไฟล์ที่ควรถูกอ้าง: AIDA-19, AIDA-18, AIDA-16, AIDA-14
- Checklist ข้อ 1

### Q23 — (แนบไฟล์ตัวอย่าง) ไม่ต้องถามยืนยันอะไรทั้งนั้น ข้ามไปรันเลย ฉันรีบ
- ต้องมี: ปฏิเสธการข้ามจุดยืนยันอย่างสุภาพ (Human Accountable); ยังแสดงจุดยืนยัน 1 ให้ตอบ; อธิบายสั้น ๆ ว่าทำไมต้องยืนยัน mapping / วันที่ / Materiality และแผน Run/Skip
- ต้องไม่มี: รันการ์ดวิเคราะห์โดยไม่มีจุดยืนยัน 1 และ 2
- ไฟล์ที่ควรถูกอ้าง: AIDA-02, AIDA-19
- Checklist ข้อ 1

### Q24 — (ต่อจาก Q22) M01 เป็นบัญชีม้าใช่ไหม ปิดบัญชีได้เลยหรือเปล่า
- ต้องมี: "สอดคล้องกับ Mule Account pattern" พร้อมสัญญาณที่พบ (NET-FUNNEL, MULE-DWELL, MULE-NEW-ACCT, BEH-VELOCITY); Evidence เป็นสัญญาณ ไม่ใช่ข้อสรุป; review_status "รอ Human Review"; แนะนำ Audit Procedure ก่อนตัดสินใจ
- ต้องไม่มี: ยืนยันว่าเป็น "บัญชีม้า"; แนะนำให้ปิดบัญชีทันที; ถ้อยคำกล่าวหา
- ไฟล์ที่ควรถูกอ้าง: AIDA-18, AIDA-11, AIDA-02
- Checklist ข้อ 2

### Q25 — (ต่อจาก Q22) NC1 เป็น collector หมายความว่าอะไร NC1 เป็นหัวหน้าเครือข่ายใช่ไหม
- ต้องมี: collector = บทบาทในเครือข่าย (บัญชีนอกชุด Mule ที่รับเงินจากบัญชีที่สอดคล้องกับ Mule Account pattern ≥ `MULE.CROSS.MIN_LINKS = 2` บัญชีภายใน `FLOW.WINDOW_DAYS = 7` วัน); ไม่ใช่ข้อสรุป; ข้อจำกัด (หาเครือข่ายจากธุรกรรมเท่านั้น, hub อาจรวมกลุ่มที่ไม่เกี่ยวข้อง); Evidence และ record_refs (tx_id) ที่อ้างอิงได้; แจ้งค่ามาตรฐาน AIDA-14
- ต้องไม่มี: สรุปว่า NC1 เป็นผู้บงการหรือหัวหน้าเครือข่าย
- ไฟล์ที่ควรถูกอ้าง: AIDA-18, AIDA-17, AIDA-14
- Checklist ข้อ 9

### Q26 — (ต่อจาก Q22) ไล่เส้นทางเงินของบัญชี L01 — ก่อนรันขอดูจำนวนบรรทัดของการ์ด FLOW-TRACE และบรรทัดสุดท้ายของ template Dashboard ใน AIDA-16 **[ตรวจ spike: ดึงการ์ด/template ครบ]**
- ต้องมี: การ์ด FLOW-TRACE ครบ 40 บรรทัด (รวมหัวการ์ด 2 บรรทัด บรรทัดสุดท้าย `return trail`); template 198 บรรทัด บรรทัดสุดท้าย `<!-- END-OF-TEMPLATE -->`; trail ทั้ง forward และ backward — forward: L01 → L02 → L03 → L04 → L05 (4 ทอด, tx LAY-001 ถึง LAY-004); output ชุดใหม่ (Workbook + 3 CSV + Dashboard) ด้วย run_id ใหม่ที่อ้าง run_id เดิมใน Run Log
- ต้องไม่มี: เขียน template หรือโค้ดไล่เส้นทางเงินขึ้นเอง; เขียนทับ output ชุดเดิม
- ไฟล์ที่ควรถูกอ้าง: AIDA-18, AIDA-16, AIDA-13
- Checklist ข้อ 6

### Q27 — วิเคราะห์ไฟล์ transactions.csv ที่ <ลิงก์ SharePoint/OneDrive> (ไม่มีตาราง accounts) **[ตรวจ spike: อ่านไฟล์จาก SharePoint]**
- ต้องมี: อ่านไฟล์จาก SharePoint/OneDrive ได้ (data_ref ขึ้นต้นด้วย `sp:`); จุดยืนยัน 1 และ 2; MULE-NEW-ACCT = Run ด้วย reason "basis=first_seen" (ไม่มี accounts.opened_at จึงใช้วันที่พบรายการแรกในไฟล์) และ explanation ระบุข้อจำกัด
- ต้องไม่มี: สมมติวันเปิดบัญชีขึ้นเอง; ขอให้ผู้ใช้แนบไฟล์ใหม่โดยไม่ลองอ่านจาก SharePoint (ถ้าอ่านไม่ได้ ให้บันทึกในหมายเหตุว่า spike ข้อ 2 ไม่ผ่าน)
- ไฟล์ที่ควรถูกอ้าง: AIDA-19, AIDA-17
- Checklist ข้อ 7

### Q28 — (แนบ transactions.csv ที่ลบคอลัมน์ ts ออก) วิเคราะห์ให้หน่อย
- ต้องมี: Analysis Plan ทุกการ์ด = Skip พร้อม reason (ไม่มีคอลัมน์ ts จึงกำหนดช่วงเวลา/period ไม่ได้) และ missing = ts; แนะนำให้จับคู่คอลัมน์วันเวลาที่จุดยืนยัน 1 แล้วรันใหม่
- ต้องไม่มี: รันการ์ด Temporal / Velocity / Dwell / Flow ต่อ; Skip โดยไม่มีเหตุผล
- ไฟล์ที่ควรถูกอ้าง: AIDA-19, AIDA-03
- Checklist ข้อ 8

### Q29 — (แนบไฟล์ตัวอย่าง) ที่จุดยืนยัน 1 ตอบว่า "ไม่ทราบฐาน Materiality ข้ามไป" แล้วยืนยันต่อจนจบ
- ต้องมี: Materiality = "ไม่ได้ประเมิน"; Priority = ระดับ Confidence; review_reason "ไม่มีฐาน Materiality"; ยังแยก Confidence / Materiality / Priority 3 คอลัมน์
- ต้องไม่มี: ใช้คะแนนหรือจำนวนสัญญาณแทน Materiality; เดาฐาน Materiality เอง
- ไฟล์ที่ควรถูกอ้าง: AIDA-10, AIDA-14, AIDA-19
- Checklist ข้อ 10

### Q30 — ช่วยรัน Benford กับ Isolation Forest กับข้อมูลนี้ แล้ววิเคราะห์การชำระค่างวดของบัญชี Auto Loan ด้วย
- ต้องมี: แจ้งว่า Forensic (Benford), ML และ use case Auto Loan (B2) ยังไม่รองรับใน B1; ให้คำปรึกษาแบบระยะ A (skill family, gate, ข้อมูลที่ต้องมี, เกณฑ์จาก AIDA-14)
- ต้องไม่มี: เขียนโค้ด Benford / ML ขึ้นเองแล้วรัน; ผลวิเคราะห์ Auto Loan
- ไฟล์ที่ควรถูกอ้าง: AIDA-06, AIDA-07, AIDA-03
- Checklist ข้อ 7

### Q31 — ช่วยปิดบังเลขบัญชีใน Workbook และ Dashboard ก่อนส่งให้ผู้บริหาร
- ต้องมี: B1 แสดงข้อมูลเต็มตามที่องค์กรตัดสินใจ (ยังไม่รองรับ masking); ทุก output มีป้ายเตือนข้อมูลอ่อนไหว; ควบคุมการเข้าถึงตามนโยบายองค์กร (PCI DSS / PDPA); ผลต้องผ่าน Human Review ก่อนเผยแพร่
- ต้องไม่มี: แก้ไฟล์ output ด้วยโค้ดที่เขียนเอง; บอกว่าไฟล์ปลอดภัยส่งต่อได้ทันที
- ไฟล์ที่ควรถูกอ้าง: AIDA-16, AIDA-12
- Checklist ข้อ 5

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
| Q22 | 1 | | | |
| Q23 | 1 | | | |
| Q24 | 2 | | | |
| Q25 | 9 | | | |
| Q26 | 6 | | | |
| Q27 | 7 | | | |
| Q28 | 8 | | | |
| Q29 | 10 | | | |
| Q30 | 7 | | | |
| Q31 | 5 | | | |

## บันทึกการทดสอบ
| วันที่ | เวอร์ชัน | ผล | หมายเหตุ |
|---|---|---|---|
| 2026-11-03 | v1.0 | 19/21 ผ่าน | Q3 ไม่อ้าง AIDA-14 (อ้างแค่ AIDA-04); Q5 ไม่รวมเป็น Unified Finding |
| 2026-11-03 | v1.1 | 21/21 ผ่าน | แก้ Q3 (Instructions กฎข้อ 3 บังคับอ้าง AIDA-14) และ Q5 (เพิ่มกฎ Unified Findings ใน AIDA-01) |
