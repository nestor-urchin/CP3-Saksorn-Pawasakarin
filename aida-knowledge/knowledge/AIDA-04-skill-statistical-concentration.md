# AIDA-04 · Anomaly Skills I: Statistical (5.1) และ Concentration (5.2)
> ไฟล์: AIDA-04 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Z-Score / IQR / MAD / Percentile ใช้เมื่อไหร่, HHI / Top-N / Share วัดอะไร, ต้องมีข้อมูลอะไร, ใช้เกณฑ์เท่าไหร่, Evidence ต้องมีอะไร

## สรุปสั้น
ใช้เพื่อชี้ค่าที่เด่นหรือการพึ่งพิงที่สูง ไม่ใช่เพื่อชี้การกระทำผิด
- **5.1 Statistical** หาค่าที่โดดเด่นจากการกระจายของ amount / count / volume
- **5.2 Concentration** หาการกระจุกตัวหรือการพึ่งพิง entity ใด entity หนึ่ง
Evidence output ควรระบุ record/entity, metric, benchmark/distribution, threshold/configuration และ data reference

## 5.1 Statistical Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | ชี้รายการที่มีค่าโดดเด่นจากการกระจายของข้อมูลกลุ่มเดียวกัน |
| Non-purpose | ไม่สรุปเจตนาหรือความถูกต้องของรายการ ไม่ใช้แทน Materiality |
| Input | Numeric amount / count / volume + record key + กลุ่มเปรียบเทียบ (เช่น ประเภทรายการ งวด) |
| Output | Evidence: record, metric, ค่าสถิติ (z / fence / percentile), การกระจายที่ใช้เทียบ, threshold, data reference → ส่ง Evidence Quality Gate (AIDA-01 Stage 9) |
| Configuration | `STAT.*` และ `GATE.SAMPLE.MIN = 30` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) |
| Audit Trail | Run ID, skill version, วิธีที่ใช้, Registry version, กลุ่มเปรียบเทียบ, จำนวนรายการ |
| Success | คำนวณครบทุกกลุ่มที่ผ่าน gate และทุก Evidence ย้อนกลับถึง record ได้ |
| Stop/Skip | Skip เมื่อไม่มี numeric field หรือจำนวนต่อกลุ่มไม่ถึงขั้นต่ำ หรือการกระจายไม่เหมาะกับวิธี (เช่น ข้อมูลเบ้มากให้ใช้ MAD แทน Z-Score) |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Z-Score | ค่าที่ห่างจากค่าเฉลี่ยหลายเท่าของ SD | numeric + กลุ่ม | `STAT.ZSCORE.THRESHOLD = 3` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | record, ค่า, z, mean, SD | ไวต่อข้อมูลเบ้และค่าผิดปกติเอง |
| IQR | ค่าที่อยู่นอกรั้ว Q1/Q3 | numeric + กลุ่ม | `STAT.IQR.K = 1.5 (mild) / 3.0 (extreme)` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | record, ค่า, Q1, Q3, fence | ทนข้อมูลเบ้ได้ดีกว่า Z-Score |
| MAD | ค่าโดดเด่นโดยอิง Median | numeric + กลุ่ม | `STAT.MAD.THRESHOLD = 3.5` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | record, ค่า, modified z, median, MAD | เหมาะกับข้อมูลการเงินที่เบ้ |
| Percentile-based Detection | ค่าที่อยู่ปลายการกระจาย | numeric + กลุ่ม | `STAT.PERCENTILE = P99 / P1` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | record, ค่า, percentile | ได้สัดส่วนรายการคงที่เสมอ แม้ไม่มีค่าผิดปกติจริง |
| Extreme Amount | ยอดเงินสูง/ต่ำผิดปกติ | amount | ใช้ Z-Score / IQR / MAD ตามความเหมาะสม | record, amount, เกณฑ์ที่ใช้ | ยอดสูงอาจเป็นธุรกรรมปกติขนาดใหญ่ |
| Extreme Frequency | จำนวนครั้งต่อ entity/งวดสูงผิดปกติ | entity + นับครั้ง | เช่นเดียวกัน | entity, count, กลุ่มเทียบ | ตรวจฤดูกาลและนโยบายประกอบ |
| Extreme Volume | ปริมาณ (หน่วย/รายการ) สูงผิดปกติ | volume | เช่นเดียวกัน | entity/record, volume | ต้องแยกหน่วยวัดให้ตรงกัน |

## 5.2 Concentration Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | วัดการกระจุกตัวและการพึ่งพิง entity (vendor / customer / merchant) |
| Non-purpose | ไม่สรุปว่าการกระจุกตัวไม่เหมาะสม อาจเป็นผลจากโครงสร้างตลาดหรือสัญญาระยะยาว |
| Input | entity id + amount (หรือ count) + period + record key |
| Output | Evidence: entity, ส่วนแบ่ง, อันดับ, HHI, period, threshold, data reference |
| Configuration | `CONC.*` (AIDA-14) |
| Audit Trail | Run ID, skill version, ฐานการคำนวณ (amount หรือ count), period, Registry version |
| Success | คำนวณส่วนแบ่งครบทุก entity และผลรวมส่วนแบ่ง = 100% |
| Stop/Skip | Skip เมื่อไม่มี entity id หรือ entity ไม่ได้รับการระบุตัวตนที่ชัดเจน (ชื่อซ้ำ/สะกดต่างกันมาก — ควรทำ Entity Resolution ก่อน, AIDA-08) |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Top-N Analysis | entity อันดับต้นที่ครองยอด | entity + amount | `CONC.TOPN = 10` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | รายชื่อ Top-N, ยอด, ส่วนแบ่งสะสม | ดูแนวโน้มข้ามงวดประกอบ |
| Share Analysis | ส่วนแบ่งของแต่ละ entity | entity + amount | `CONC.SINGLE_ENTITY_SHARE = 10%` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | entity, ส่วนแบ่ง % | ส่วนแบ่งสูงอาจเป็นผู้ขายรายเดียวในตลาด |
| HHI Analysis | ระดับการกระจุกตัวโดยรวม | entity + amount | `CONC.HHI = < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | HHI, ระดับ, จำนวน entity | HHI สูงไม่ได้แปลว่ามีความผิดปกติในการจัดซื้อ |
| Entity Dependency | การพึ่งพิง entity เดียวต่อกระบวนการ | entity + amount + กระบวนการ | `CONC.SINGLE_ENTITY_SHARE = 10%` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) | entity, กระบวนการ, ส่วนแบ่ง | เชื่อมกับความเสี่ยงความต่อเนื่องทางธุรกิจ |
| Vendor Concentration | การกระจุกตัวของผู้ขาย | vendor + amount | Share / HHI ข้างต้น | vendor, ส่วนแบ่ง, HHI | ตรวจสัญญาและการคัดเลือกผู้ขายประกอบ |
| Customer Concentration | การกระจุกตัวของลูกค้า | customer + revenue | Share / HHI ข้างต้น | customer, ส่วนแบ่งรายได้ | เกี่ยวข้องกับการเปิดเผยข้อมูลลูกค้ารายใหญ่ |
| Merchant Concentration | การกระจุกตัวของร้านค้า/คู่ค้าในธุรกรรมบัตร/การชำระเงิน | merchant + amount | Share / HHI ข้างต้น | merchant, ส่วนแบ่ง | แยกตามประเภทร้านค้าก่อนเทียบ |

## ข้อห้าม (Guardrails)
- ค่าที่เกิน threshold หมายถึง "ควรพิจารณาเพิ่มเติม" ไม่ใช่การสรุปว่าผิด
- ห้ามใช้ Z-Score / HHI เป็น Materiality โดยตรง (AIDA-10)
- ห้ามเทียบข้ามกลุ่มที่ไม่ควรเทียบกัน (ต่างสกุลเงิน ต่างหน่วย ต่างประเภทรายการ)

## ไฟล์ที่เกี่ยวข้อง
- AIDA-03 Selection Matrix, AIDA-09 Hybrid, AIDA-10 Assessment, AIDA-14 Registry
