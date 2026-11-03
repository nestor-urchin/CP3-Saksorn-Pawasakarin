# AIDA-14 · Configuration Registry (ค่ามาตรฐาน)
> ไฟล์: AIDA-14 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: เกณฑ์/Threshold ของแต่ละ skill ใช้ค่าเท่าไหร่, ค่ามาตรฐานมาจากไหน, Materiality คิดอย่างไร, ตาราง Priority เป็นอย่างไร, จะเปลี่ยนค่าได้อย่างไร

## สรุปสั้น
ไฟล์นี้เป็น **แหล่งค่ามาตรฐานเพียงแหล่งเดียว (single source of truth)** ของ AIDA Registry เวอร์ชัน 1.0
ทุกค่าเป็น **ค่ามาตรฐานทั่วไป** ที่ใช้ในวงการตรวจสอบ/สถิติ ไม่ใช่นโยบายที่องค์กรอนุมัติ
ทุกครั้งที่ AIDA อ้างค่าจากไฟล์นี้ ต้องแจ้งผู้ใช้ว่าเป็นค่ามาตรฐานและปรับได้ตามบริบทองค์กร
ค่าเขียนในรูปแบบ `KEY = ค่า` เพื่อให้ไฟล์อื่นอ้างอิงได้ตรงกัน

## วิธีใช้ค่ามาตรฐาน
- **Registry version:** 1.0 (2026-11-03)
- **ข้อความแจ้งผู้ใช้ (ใช้ทุกครั้งที่อ้างค่า):** "ค่านี้เป็นค่ามาตรฐานทั่วไป (AIDA Registry v1.0) — ปรับได้ตามบริบทองค์กร"
- **การใช้ค่าขององค์กรแทน:** ผู้ใช้ระบุค่าขององค์กร + แหล่ง/ผู้อนุมัติ + เวอร์ชัน แล้ว AIDA ใช้ค่านั้นในคำตอบ พร้อมระบุว่าใช้ค่าขององค์กร ไม่ใช่ค่ามาตรฐาน
- **การเปลี่ยนค่าในไฟล์นี้:** แก้ค่า → เพิ่มเวอร์ชัน → บันทึกใน "ประวัติการเปลี่ยนแปลง" → รัน validator (ดู README)
- ทุก Finding/Evidence ควรบันทึก `Registry version` ที่ใช้ เพื่อให้ Reproducible (ดู AIDA-13)

## 1. Gate ทั่วไป (ใช้กับทุก skill)
| ค่า | ความหมาย | ที่มา / เหตุผล |
|---|---|---|
| `GATE.COMPLETENESS.MIN = 95%` | field จำเป็นของ skill ต้องมีค่าไม่น้อยกว่า 95% (ว่างได้ไม่เกิน 5%) ไม่ผ่าน → Skip + reason | แนวปฏิบัติ data quality ทั่วไป |
| `GATE.SAMPLE.MIN = 30` | จำนวนรายการขั้นต่ำต่อกลุ่มที่นำมาเปรียบเทียบ/คำนวณสถิติ | ขั้นต่ำทางสถิติที่ใช้ทั่วไป |
| `GATE.TRACE.REQUIRED = dataset + table + period + record key` | ข้อมูลอ้างอิงขั้นต่ำเพื่อย้อนกลับไปยังต้นทาง ไม่ครบ → **Stop** | หลัก Evidence First / Traceability |

## 2. Statistical Anomaly (5.1)
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `STAT.ZSCORE.THRESHOLD = 3` | ค่าสัมบูรณ์ของ Z-Score เกินค่านี้ถือว่าโดดเด่น | 3-sigma rule |
| `STAT.IQR.K = 1.5 (mild) / 3.0 (extreme)` | ตัวคูณ IQR สำหรับรั้วล่าง/บน (Q1 − k·IQR, Q3 + k·IQR) | Tukey fences |
| `STAT.MAD.THRESHOLD = 3.5` | Modified Z-Score (อิง Median/MAD) เกินค่านี้ถือว่าโดดเด่น เหมาะกับข้อมูลเบ้ | Iglewicz & Hoaglin (1993) |
| `STAT.PERCENTILE = P99 / P1` | ค่าที่สูงกว่า P99 หรือต่ำกว่า P1 ของการกระจาย | ใช้ทั่วไป |

## 3. Concentration Anomaly (5.2)
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `CONC.HHI = < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง` | ระดับการกระจุกตัวจาก Herfindahl-Hirschman Index (ผลรวมกำลังสองของส่วนแบ่ง %) | US DOJ/FTC Horizontal Merger Guidelines 2010 (หมายเหตุ: แนวทางปี 2023 ใช้ 1,000 / 1,800) |
| `CONC.SINGLE_ENTITY_SHARE = 10%` | entity เดียวมีส่วนแบ่งของยอดรวมตั้งแต่ค่านี้ขึ้นไป ถือว่ามีการพึ่งพิงสูง | เกณฑ์ major customer 10% ในมาตรฐานบัญชี |
| `CONC.TOPN = 10` | จำนวนอันดับแรกที่ใช้ใน Top-N / Share Analysis | ใช้ทั่วไป |

## 4. Behavioral Anomaly (5.3)
| ค่า | ความหมาย |
|---|---|
| `BEH.BASELINE.MIN_PERIODS = 6 งวด (แนะนำ 12)` | ประวัติขั้นต่ำของ entity เพื่อสร้าง baseline ไม่ถึง → Skip + reason |
| `BEH.PEER.MIN_SIZE = 5` | จำนวน peer ขั้นต่ำในกลุ่มเปรียบเทียบ |
| `BEH.DEVIATION = 3σ` | ส่วนเบี่ยงเบนจาก baseline/peer ที่ถือว่าเปลี่ยนแปลงอย่างมีนัย |

## 5. Temporal Anomaly (5.4)
| ค่า | ความหมาย |
|---|---|
| `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` | ช่วงเวลาที่ใช้วิเคราะห์ Period-end / Month-end / Quarter-end Spike |
| `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` | จำนวนงวดขั้นต่ำสำหรับ Trend / Change Point (ถ้าดูฤดูกาลใช้ 24) |
| `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` | นิยามช่วงเวลานอกเวลาทำการสำหรับ Time-of-day / Unusual Timing |

## 6. Sequence Anomaly (5.5)
| ค่า | ความหมาย |
|---|---|
| `SEQ.CREATE_TO_PAY.DAYS = 30` | จ่ายเงินครั้งแรกภายในจำนวนวันนี้หลังสร้าง vendor/entity ถือเป็นรูปแบบที่ควรพิจารณา |
| `SEQ.CHANGE_TO_TRANSFER.DAYS = 7` | โอนเงินภายในจำนวนวันนี้หลังเปลี่ยนข้อมูลบัญชีธนาคาร/ข้อมูลหลัก |

## 7. Forensic Anomaly (5.6)
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `FOR.BENFORD.MIN_N = 1,000 (ยอด ≥ 10)` | จำนวนรายการขั้นต่ำสำหรับ Benford Analysis (นับเฉพาะยอดตั้งแต่ 10) | Nigrini |
| `FOR.BENFORD.MAD_1ST = ≤ 0.006 / ≤ 0.012 / ≤ 0.015 / > 0.015` | ระดับความสอดคล้องหลักแรก: ใกล้เคียงมาก / ยอมรับได้ / ก้ำกึ่ง / ไม่สอดคล้อง | Nigrini |
| `FOR.ROUND.UNIT = 1,000` | ยอดที่หารด้วยค่านี้ลงตัวถือเป็น Round Amount | ใช้ทั่วไป |
| `FOR.THRESHOLD_AVOID.BAND = 90–99.99% ของวงเงินอนุมัติ` | ยอดที่อยู่ในช่วงนี้ใต้วงเงินอนุมัติ ใช้ใน Threshold / Approval Limit Avoidance (วงเงินอนุมัติจริงมาจากนโยบายองค์กร) | ใช้ทั่วไป |
| `FOR.REPEAT.MIN_COUNT = 3` | ยอดเท่ากันตั้งแต่จำนวนครั้งนี้ จาก entity เดียวกันในงวดเดียวกัน | ใช้ทั่วไป |

## 8. Machine Learning Anomaly (5.8)
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `ML.CONTAMINATION = 1%` | สัดส่วนที่คาดว่าเป็นค่าผิดปกติ (Isolation Forest / One-Class) | ใช้ทั่วไป |
| `ML.LOF.NEIGHBORS = 20` | จำนวนเพื่อนบ้านของ Local Outlier Factor | ค่าเริ่มต้นของ scikit-learn |
| `ML.MIN_OBS = 1,000 หรือ 10 × จำนวน feature` | จำนวนรายการขั้นต่ำ (ใช้ค่าที่มากกว่า) | กฎทั่วไป |

ผล ML ทุกกรณีต้องผ่าน Human Review ก่อนนำไปใช้ (ดู AIDA-02)

## 9. Network Anomaly (5.9)
| ค่า | ความหมาย |
|---|---|
| `NET.SHARED_ID.MIN = 2` | จำนวน entity ขั้นต่ำที่ใช้ identifier ร่วมกัน (บัญชีธนาคาร ที่อยู่ เบอร์โทร เลขผู้เสียภาษี) |
| `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน` | นิยาม Circular Flow: เงินหมุนกลับต้นทางภายในจำนวนทอดและช่วงเวลานี้ |
| `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน` | นิยาม Funnel Account / Mule pattern |

## 10. Assessment Model (ดูรายละเอียดใน AIDA-10)

### ASSESS.CONFIDENCE — ระดับความมั่นใจ
| ระดับ | เกณฑ์ |
|---|---|
| สูง | Evidence ≥ 2 แหล่งที่เป็นอิสระต่อกันยืนยันตรงกัน และ Lineage ครบทั้ง 7 ระดับ |
| กลาง | Evidence 1 แหล่ง และ Lineage ครบ |
| ต่ำ | Evidence ขัดแย้งกัน หรือ Lineage ไม่ครบ → ส่ง Human Review |

### ASSESS.MATERIALITY — ฐานคำนวณ Materiality
| ค่า | ความหมาย |
|---|---|
| `ASSESS.MATERIALITY = 5% กำไรก่อนภาษี / 0.5–1% รายได้ / 1–2% สินทรัพย์รวม` | เลือกฐานที่เหมาะกับลักษณะธุรกิจ/กระบวนการ 1 ฐาน |
| `ASSESS.CLEARLY_TRIVIAL = < 5% ของ Materiality` | ผลกระทบต่ำกว่านี้ถือว่าเล็กน้อยมาก |

ระดับ Materiality ของ Finding:
- **สูง:** ผลกระทบ (exposure) ตั้งแต่ระดับ Materiality ขึ้นไป หรือมีปัจจัยเชิงคุณภาพสำคัญ (กฎหมาย ชื่อเสียง ผู้บริหาร)
- **กลาง:** ตั้งแต่ระดับ Clearly trivial แต่ต่ำกว่า Materiality
- **ต่ำ:** ต่ำกว่าระดับ Clearly trivial และไม่มีปัจจัยเชิงคุณภาพ

### ASSESS.PRIORITY — ลำดับความสำคัญ
Priority = ตาราง Confidence × Materiality แล้ว **ปรับขึ้น 1 ระดับ** เมื่อเร่งด่วน (Urgency) หรือเข้าเกณฑ์ที่องค์กรกำหนด (Configured criteria) — สูงสุดที่ระดับ สูง

### ตาราง Priority
| Confidence \ Materiality | สูง | กลาง | ต่ำ |
|---|---|---|---|
| สูง | สูง | กลาง | ต่ำ |
| กลาง | สูง | กลาง | ต่ำ |
| ต่ำ | กลาง + Human Review | ต่ำ | ต่ำ |

## ประวัติการเปลี่ยนแปลง
| เวอร์ชัน | วันที่ | การเปลี่ยนแปลง |
|---|---|---|
| 1.0 | 2026-11-03 | ฉบับแรก: ค่ามาตรฐานทั่วไปทุก skill |

## ข้อห้าม (Guardrails)
- ห้ามนำเสนอค่าในไฟล์นี้ว่าเป็นนโยบายที่องค์กรอนุมัติแล้ว — ต้องแจ้งว่าเป็นค่ามาตรฐานทุกครั้ง
- ห้าม Hard-code ค่าใน skill หรือคำตอบโดยไม่อ้าง key ในไฟล์นี้
- ห้ามใช้ Model Score / Anomaly Score เป็น Materiality โดยตรง
- เกินค่า Threshold หมายถึง "ควรตรวจสอบเพิ่มเติม" เท่านั้น ไม่ใช่ข้อสรุปว่ามีการกระทำผิด

## ไฟล์ที่เกี่ยวข้อง
- AIDA-03 Analysis Selection Matrix (Gate ที่ใช้ค่าเหล่านี้)
- AIDA-04 ถึง AIDA-08 Skill แต่ละกลุ่ม
- AIDA-10 Assessment Model (Confidence / Materiality / Priority)
- AIDA-13 Governance (Version / Change Control)
