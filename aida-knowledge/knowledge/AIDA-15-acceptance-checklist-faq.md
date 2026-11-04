# AIDA-15 · Design Acceptance Checklist และ FAQ
> ไฟล์: AIDA-15 | เวอร์ชัน: 1.1 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: เกณฑ์ตรวจรับสถาปัตยกรรม AIDA มีอะไรบ้าง, จะตรวจแต่ละข้ออย่างไร, คำถามที่พบบ่อยและคำตอบตามกรอบ AIDA

## สรุปสั้น
Design Acceptance Checklist คือเกณฑ์ตรวจรับสถาปัตยกรรมจากข้อกำหนดที่กำหนดไว้ มี 12 ข้อ
ใช้ตรวจทั้งการออกแบบ การทำงานของ Agent และ Output ที่ส่งมอบ
FAQ ด้านล่างเป็นตัวอย่างคำตอบที่ถูกต้องตามกรอบ AIDA

## Design Acceptance Checklist
| ข้อ | เกณฑ์ | ตรวจอย่างไร | ไฟล์อ้างอิง |
|---|---|---|---|
| 1 | Profile และ Capability Gate ทำงานก่อน Analysis | Audit Trail แสดง Stage 3 และ 5 ก่อน Stage 8 ทุกการรัน | AIDA-01, AIDA-03 |
| 2 | Analysis Skills สร้าง Evidence เท่านั้น | ผลของ skill ไม่มีข้อสรุป/ระดับ Priority มีแต่ Evidence | AIDA-04 ถึง AIDA-08 |
| 3 | Rules/Thresholds อ่านจาก Registry | ทุกเกณฑ์ใน Evidence มี Registry key + version | AIDA-14, AIDA-07 |
| 4 | Unified Findings ลบซ้ำและเชื่อมหลักฐาน | Finding หนึ่งรายการต่อ entity/risk/time และมี link ไป Evidence ทุกชิ้น | AIDA-01, AIDA-09 |
| 5 | Alert แยกจาก Finding และผ่าน Human Review | Alert อยู่ใน Output 15 แยกต่างหาก และมี Review Reference ก่อนเผยแพร่ | AIDA-02, AIDA-12 |
| 6 | Audit Trail ครบทุก Stage | Output 16 มีรายการครบ 18 Stage รวม Stop/Skip | AIDA-13, AIDA-01 |
| 7 | Planner อธิบาย Selection / Skip Reason | Analysis Plan มีเหตุผลทุก skill family | AIDA-03 |
| 8 | Minimum Data Requirement ถูกบังคับใช้ | skill ที่ไม่ผ่านขั้นต่ำถูก Skip ไม่ถูกรัน | AIDA-03, AIDA-14 |
| 9 | Evidence เก็บ Source Skill และ Data Reference | Evidence ทุกชิ้นมี skill name/version และ dataset/table/record/period | AIDA-13 |
| 10 | Confidence / Materiality / Priority แยกความหมาย | Output 06–08 แยกกัน และไม่มีคะแนนรวม | AIDA-10 |
| 11 | Executive Output Drill Down ได้ | ทุกประเด็นใน Output 12–13 เจาะไปยัง Finding และ Evidence ได้ | AIDA-12 |
| 12 | Version / Change / Error / Reproducibility ถูกควบคุม | ผ่าน Reproducibility test และมีบันทึก Change Control / Error log | AIDA-13 |

## FAQ
**ถาม: ข้อมูลไม่มี timestamp ใช้ Temporal skill ได้ไหม?**
ตอบ: ไม่ได้ ต้อง Skip พร้อมเหตุผล "Timestamp / period / granularity ไม่รองรับ" แต่ยังใช้ Statistical หรือ Concentration ได้ถ้าผ่าน gate (AIDA-05, AIDA-03)

**ถาม: Isolation Forest ให้คะแนนสูง แปลว่ามีความผิดไหม?**
ตอบ: ไม่ใช่ Anomaly Score ≠ Fraud Conclusion ผลต้องผ่าน Human Review และใช้ Audit Procedure เพื่อหาหลักฐานเพิ่ม (AIDA-07, AIDA-02)

**ถาม: HHI ใช้เกณฑ์เท่าไหร่?**
ตอบ: ค่ามาตรฐาน `CONC.HHI = < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) อ้างอิงแนวทาง US DOJ/FTC 2010

**ถาม: Priority สูงแปลว่าผิดใช่ไหม?**
ตอบ: ไม่ใช่ Priority บอกว่าอะไรควรได้รับความสนใจก่อน ไม่ได้ยืนยันการกระทำใด ๆ Confidence, Materiality และ Priority ตอบคำถามต่างกัน (AIDA-10)

**ถาม: ช่วยวิเคราะห์ไฟล์ข้อมูลนี้ให้หน่อย**
ตอบ: ระยะ B1 AIDA วิเคราะห์ข้อมูลจริงด้วย Code Interpreter ได้เฉพาะข้อมูลธุรกรรมโอนเงิน (transactions และ accounts ถ้ามี) สำหรับ use case Mule Accounts ตามขั้นตอน B1 ใน Instructions: เสนอ mapping คอลัมน์ → จุดยืนยัน 1 (mapping, รูปแบบวันที่, ฐาน Materiality) → Dataset Profile → Analysis Plan → จุดยืนยัน 2 (Run/Skip) → รันการ์ดใน AIDA-18/19 ตามตัวอักษร → ส่ง Workbook, CSV และ Dashboard (AIDA-19, AIDA-17) ข้อมูลหรือ use case อื่น (เช่น AP, GL, Auto Loan) ยังไม่รองรับใน B1 จึงให้คำปรึกษาแบบระยะ A โดยเสนอ Analysis Plan: skill ที่เหมาะ, gate ที่ต้องผ่าน และข้อมูลที่ต้องมี (AIDA-03)

**ถาม: Statistical กับ Rule พบ vendor เดียวกัน ควรรายงาน 2 Finding ไหม?**
ตอบ: ไม่ควร ถ้าเป็น entity + risk + time เดียวกัน ให้ลบซ้ำและรวมเป็น Unified Finding เดียวที่เชื่อม Evidence ทั้งสองชิ้น (ระบุ Source Skill และ Data Reference ของแต่ละชิ้น) และใช้ Evidence ที่อิสระต่อกันนี้ประเมิน Confidence แยก Finding เฉพาะเมื่อความเสี่ยงหรือช่วงเวลาต่างกัน (AIDA-01 หัวข้อ Unified Findings, AIDA-09)

**ถาม: Benford ใช้กับข้อมูล 300 รายการได้ไหม?**
ตอบ: ไม่ควร เพราะต่ำกว่าขั้นต่ำ `FOR.BENFORD.MIN_N = 1,000 (ยอด ≥ 10)` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) ต้อง Skip + reason (AIDA-06)

**ถาม: ไม่มี record key ทำอย่างไร?**
ตอบ: Stop ทั้ง workflow เพราะอ้างอิงต้นทางไม่ได้ ผู้ใช้ต้องเพิ่มรหัสรายการแล้วเริ่มใหม่ (AIDA-02)

**ถาม: ผล Statistical และ ML ขัดกัน ควรเชื่ออันไหน?**
ตอบ: ไม่เลือกเชื่อฝ่ายใดเอง บันทึก conflict ใน Evidence map, Confidence ต่ำ และส่ง Human Review (AIDA-09)

**ถาม: เขียน Finding ให้ผู้บริหารอย่างไร?**
ตอบ: ใช้ภาษาผู้บริหาร เน้นประเด็น ความเสี่ยง ผลกระทบทางธุรกิจ และสิ่งที่ควรดำเนินการ ไม่เน้นค่าทางเทคนิค ไม่กล่าวหา และต้อง Drill Down ได้ (AIDA-12, AIDA-11)

**ถาม: Alert ต่างจาก Finding อย่างไร?**
ตอบ: Alert คือสัญญาณเตือนล่วงหน้าที่ยังไม่ผ่านการประเมินครบ ต้องแยกจาก Finding และผ่าน Human Review ก่อนเผยแพร่ (AIDA-12)

**ถาม: กฎธุรกิจควรเขียนไว้ใน skill เลยได้ไหม?**
ตอบ: ไม่ได้ ต้องอ่านกฎจาก Configuration Registry เท่านั้น ห้าม Hard-code ใน Skill และต้องมี rule version (AIDA-07)

**ถาม: ทำอย่างไรให้ผลทำซ้ำได้?**
ตอบ: เก็บ Lineage 7 ระดับ และใช้ Data + Configuration + Skill/Model Version เดิม ถ้าผลต่างต้องบันทึกสาเหตุ (AIDA-13)

## ข้อห้าม (Guardrails)
- ห้ามรายงานว่าผ่าน Checklist ข้อใดโดยไม่มีหลักฐานจาก Audit Trail
- คำตอบใน FAQ เป็นแนวทาง ผู้ตรวจสอบเป็นผู้ตัดสินขั้นสุดท้าย

## ไฟล์ที่เกี่ยวข้อง
- AIDA-00 สารบัญ, AIDA-01 Workflow, AIDA-10 Assessment, AIDA-13 Governance, AIDA-14 Registry
