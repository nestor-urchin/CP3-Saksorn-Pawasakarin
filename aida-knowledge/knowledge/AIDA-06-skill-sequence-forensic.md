# AIDA-06 · Anomaly Skills III: Sequence (5.5) และ Forensic (5.6)
> ไฟล์: AIDA-06 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Create-to-Payment / Change-to-Transfer / Approval-to-Override คืออะไร, Benford ต้องมีข้อมูลกี่รายการ, Round Amount / Threshold Avoidance ใช้เกณฑ์อะไร

## สรุปสั้น
Sequence ต้องสร้างลำดับเหตุการณ์ได้ ส่วน Forensic ต้องผ่าน Minimum Data Requirement ของแต่ละวิธี
- **5.5 Sequence** หาลำดับเหตุการณ์หรือช่วงห่างระหว่างเหตุการณ์ที่ผิดปกติ
- **5.6 Forensic** หารูปแบบตัวเลขที่ผิดธรรมชาติ ไม่ผ่านขั้นต่ำ → ไม่ทำงาน

## 5.5 Sequence Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | สร้างลำดับเหตุการณ์ของ entity แล้วหาลำดับหรือช่วงเวลาที่ผิดจากกระบวนการปกติ |
| Non-purpose | ไม่สรุปว่าใครเป็นผู้ก่อเหตุการณ์ ไม่ใช้แทนการตรวจเอกสารอนุมัติ |
| Input | event type + timestamp + entity (+ ผู้ทำรายการถ้ามี) |
| Output | Evidence: entity, ลำดับเหตุการณ์, ช่วงห่าง, รูปแบบที่ตรง, data reference |
| Configuration | `SEQ.CREATE_TO_PAY.DAYS = 30` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `SEQ.CHANGE_TO_TRANSFER.DAYS = 7` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) และลำดับกระบวนการปกติที่องค์กรกำหนด |
| Audit Trail | Run ID, skill version, นิยามเหตุการณ์, ลำดับมาตรฐานที่ใช้เทียบ, Registry version |
| Success | ลำดับเหตุการณ์สร้างได้ครบสำหรับ entity ที่ผ่าน gate |
| Stop/Skip | Gate: Order can be reconstructed — ขาด event type / timestamp / entity → Skip + reason |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Event Chain Analysis | ห่วงโซ่เหตุการณ์ที่ขาดหรือเกิน | event + time + entity | ลำดับกระบวนการขององค์กร | entity, chain, ขั้นที่ขาด | ระบบต่างกันอาจบันทึกเหตุการณ์ต่างกัน |
| Sequential Pattern Analysis | รูปแบบลำดับที่พบไม่บ่อย | event + time + entity | ลำดับกระบวนการขององค์กร | รูปแบบ, ความถี่, entity | ความถี่ต่ำไม่ได้แปลว่าผิด |
| Create-to-Payment Pattern | จ่ายเงินเร็วหลังสร้าง vendor | vendor create + payment | `SEQ.CREATE_TO_PAY.DAYS = 30` | vendor, วันที่สร้าง, วันที่จ่ายครั้งแรก | vendor เร่งด่วนอาจมีเหตุผลทางธุรกิจ |
| Change-to-Transfer Pattern | โอนเงินเร็วหลังเปลี่ยนข้อมูลบัญชี | master change + transfer | `SEQ.CHANGE_TO_TRANSFER.DAYS = 7` | entity, field ที่เปลี่ยน, วันที่, การโอน | ตรวจเอกสารยืนยันการเปลี่ยนแปลง |
| Approval-to-Override Pattern | อนุมัติแล้วมีการ override | approval + override log | ลำดับกระบวนการขององค์กร | record, ผู้อนุมัติ, ผู้ override, เวลา | override บางประเภทเป็นขั้นตอนปกติ |
| Unusual Event Order | ลำดับสลับ เช่น จ่ายก่อนอนุมัติ | event + time | ลำดับกระบวนการขององค์กร | record, ลำดับจริง vs ลำดับปกติ | ตรวจ timezone และการบันทึกย้อนหลัง |
| Unusual Time Gap Between Events | ช่วงห่างสั้น/ยาวผิดปกติ | event + time | ใช้การกระจายของช่วงห่าง (AIDA-04) | record, ช่วงห่าง, ค่าปกติ | บางขั้นตอนอัตโนมัติจึงเร็ว |

## 5.6 Forensic Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | หารูปแบบตัวเลขที่ผิดจากธรรมชาติ เช่น การกระจายหลักแรก ยอดกลม ยอดใกล้วงเงิน |
| Non-purpose | ไม่ใช้กับข้อมูลที่ถูกกำหนดค่าโดยธรรมชาติ (ราคาตายตัว เลขที่เอกสาร) ไม่สรุปเจตนา |
| Input | amount (โครงสร้างตัวเลข) + entity + record key (+ วงเงินอนุมัติสำหรับ Threshold Avoidance) |
| Output | Evidence: กลุ่ม/entity, สถิติที่ใช้ (เช่น MAD ของ Benford), รายการที่เกี่ยวข้อง, data reference |
| Configuration | `FOR.*` (AIDA-14) และวงเงินอนุมัติตามนโยบายองค์กร |
| Audit Trail | Run ID, skill version, จำนวนรายการที่ใช้/ที่ตัดออก, วงเงินอนุมัติที่ใช้, Registry version |
| Success | ผ่านขั้นต่ำของแต่ละวิธีและคำนวณครบ |
| Stop/Skip | Gate: ไม่ผ่าน Minimum Data Requirement → ไม่ทำงาน (Skip + reason เฉพาะวิธีนั้น) |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Benford Analysis | การกระจายหลักแรกผิดจากกฎ Benford | amount จำนวนมาก หลายหลัก | `FOR.BENFORD.MIN_N = 1,000 (ยอด ≥ 10)` และ `FOR.BENFORD.MAD_1ST = ≤ 0.006 / ≤ 0.012 / ≤ 0.015 / > 0.015` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | กลุ่ม, MAD, หลักที่เบี่ยงมากที่สุด | ข้อมูลที่มีเพดาน/ราคาตายตัวไม่เหมาะกับ Benford |
| Round Amount Analysis | สัดส่วนยอดกลมสูงผิดปกติ | amount | `FOR.ROUND.UNIT = 1,000` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | entity, สัดส่วนยอดกลม | ค่าธรรมเนียม/เงินมัดจำมักเป็นยอดกลม |
| Threshold Avoidance | ยอดกระจุกใต้เกณฑ์ที่ต้องควบคุม | amount + เกณฑ์ | `FOR.THRESHOLD_AVOID.BAND = 90–99.99% ของวงเงินอนุมัติ` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | entity, จำนวนรายการในช่วง, เกณฑ์ | ต้องใช้เกณฑ์จริงขององค์กร |
| Approval Limit Avoidance | ยอดกระจุกใต้วงเงินอนุมัติ/แบ่งรายการ | amount + approver + วงเงิน | `FOR.THRESHOLD_AVOID.BAND = 90–99.99% ของวงเงินอนุมัติ` | approver, entity, รายการที่ใกล้วงเงิน | ดูการแบ่งรายการในวันเดียวกันประกอบ |
| Repeated Amount Pattern | ยอดเดียวกันซ้ำหลายครั้ง | amount + entity + period | `FOR.REPEAT.MIN_COUNT = 3` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | entity, ยอด, จำนวนครั้ง | ค่าเช่า/ค่าบริการรายเดือนซ้ำตามปกติ |
| Digit Pattern Analysis | รูปแบบหลักท้าย/หลักที่สอง | amount | ใช้ขั้นต่ำเดียวกับ Benford | กลุ่ม, การกระจายหลัก | ตรวจการปัดเศษของระบบ |

## ข้อห้าม (Guardrails)
- ห้ามรัน Benford เมื่อข้อมูลไม่ถึงขั้นต่ำ — ผลจะไม่มีความหมาย
- การไม่สอดคล้องกับ Benford หรือยอดกลมจำนวนมาก ไม่ใช่หลักฐานว่ามีการกระทำผิด
- ห้ามใช้วงเงินสมมติแทนวงเงินอนุมัติจริงโดยไม่แจ้งผู้ใช้

## ไฟล์ที่เกี่ยวข้อง
- AIDA-03 Selection Matrix, AIDA-04 Statistical, AIDA-05 Temporal, AIDA-09 Hybrid, AIDA-14 Registry
