# AIDA-14 · Configuration Registry (ค่ามาตรฐาน)
> ไฟล์: AIDA-14 | เวอร์ชัน: 1.2 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: เกณฑ์/Threshold ของแต่ละ skill ใช้ค่าเท่าไหร่, ค่ามาตรฐานมาจากไหน, Materiality คิดอย่างไร, ตาราง Priority เป็นอย่างไร, จะเปลี่ยนค่าได้อย่างไร

## สรุปสั้น
ไฟล์นี้เป็น **แหล่งค่ามาตรฐานเพียงแหล่งเดียว (single source of truth)** ของ AIDA Registry เวอร์ชัน 1.2
ทุกค่าเป็น **ค่ามาตรฐานทั่วไป** ที่ใช้ในวงการตรวจสอบ/สถิติ ไม่ใช่นโยบายที่องค์กรอนุมัติ
ทุกครั้งที่ AIDA อ้างค่าจากไฟล์นี้ ต้องแจ้งผู้ใช้ว่าเป็นค่ามาตรฐานและปรับได้ตามบริบทองค์กร
ค่าเขียนในรูปแบบ `KEY = ค่า` เพื่อให้ไฟล์อื่นอ้างอิงได้ตรงกัน
ค่าที่ recipe (โค้ดวิเคราะห์ข้อมูล ดู AIDA-17) ต้องอ่านเป็นตัวเลข อยู่ใน JSON ของหัวข้อ "Machine Config (สำหรับ recipe)" ท้ายไฟล์นี้ ซึ่งต้องตรงกับตารางเสมอ

## วิธีใช้ค่ามาตรฐาน
- **Registry version:** `REGISTRY.VERSION = 1.2` (2026-11-06)
- **ข้อความแจ้งผู้ใช้ (ใช้ทุกครั้งที่อ้างค่า):** "ค่านี้เป็นค่ามาตรฐานทั่วไป (AIDA Registry v1.2) — ปรับได้ตามบริบทองค์กร"
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
| `BEH.VELOCITY.SD_FLOOR = sqrt(mean) (Poisson)` | ค่า SD ขั้นต่ำของ baseline จำนวนรายการต่อวัน (BEH-VELOCITY): ใช้ max(SD, √ค่าเฉลี่ย) — ที่มา: ความแปรปรวนของข้อมูลนับแบบ Poisson; Machine Config "none" = ไม่ใช้ค่าขั้นต่ำ |

## 5. Temporal Anomaly (5.4)
| ค่า | ความหมาย |
|---|---|
| `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` | ช่วงเวลาที่ใช้วิเคราะห์ Period-end / Month-end / Quarter-end Spike |
| `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` | จำนวนงวดขั้นต่ำสำหรับ Trend / Change Point (ถ้าดูฤดูกาลใช้ 24) |
| `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` | นิยามช่วงเวลานอกเวลาทำการสำหรับ Time-of-day / Unusual Timing |
| `TEMP.OFF_HOURS.MIN_TX = 3` | จำนวนรายการโอนออกนอกเวลาทำการขั้นต่ำต่อบัญชีต่อเดือน จึงนับเป็นสัญญาณ (TEMP-OFFHOURS) — ที่มา: แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `TEMP.OFF_HOURS.MIN_SHARE = 80%` | สัดส่วนขั้นต่ำของรายการโอนออกนอกเวลาทำการต่อรายการโอนออกทั้งหมดของบัญชีในเดือนนั้น (ต้องครบทั้งจำนวนและสัดส่วน) — ที่มา: แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |

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
| `FOR.THRESHOLD_AVOID.BAND = 90%–99.99% ของวงเงินอนุมัติ` | ยอดที่อยู่ในช่วงนี้ใต้วงเงินอนุมัติ ใช้ใน Threshold / Approval Limit Avoidance (วงเงินอนุมัติจริงมาจากนโยบายองค์กร) | ใช้ทั่วไป |
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
| `NET.CYCLE.MAX_PATHS = 100,000` | จำนวนเส้นทางสูงสุดที่ NET-CYCLE ค้นหาต่อเดือน (เดือนของทอดแรก) ถึงขีดนี้แล้วหยุดค้นเดือนนั้นและแจ้งว่าผลของเดือนนั้นอาจไม่ครบ — ที่มา: ขีดจำกัดทางเทคนิคเพื่อป้องกันหน่วยความจำเต็ม |

## 10. Assessment Model (ดูรายละเอียดใน AIDA-10)

### ตาราง Confidence
ASSESS.CONFIDENCE — ระดับความมั่นใจ (ตารางนี้ต้องตรงกับ AIDA-10 ทุกตัวอักษร)
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

## 11. Mule Account pattern, Counterparty และ Money Flow (เพิ่มใน v1.1)
แหล่งที่มาของค่าในหมวดนี้: แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ (ค่าเริ่มต้นสำหรับการตรวจเชิงวิเคราะห์ ไม่ใช่เกณฑ์ที่หน่วยงานกำกับกำหนด) ยกเว้น `FLOW.MAX_TRAIL_ROWS` ซึ่งเป็นขีดจำกัดทางเทคนิค
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `MULE.DWELL_HOURS = 24` | เงินเข้าแล้วออกภายในกี่ชั่วโมง ถือว่า dwell สั้น | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.DWELL_MIN_PAIRS = 3` | จำนวนคู่เงินเข้า-เงินออกที่ dwell สั้นขั้นต่ำ จึงนับเป็นสัญญาณ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.NEW_ACCT_DAYS = 30` | บัญชีอายุไม่เกินกี่วันเมื่อเริ่มมีรายการมาก | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.NEW_ACCT_MIN_TX = 20` | จำนวนรายการขั้นต่ำภายใน `MULE.NEW_ACCT_DAYS` ที่ถือว่า "มีรายการมาก" | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.MIN_SIGNALS = 3 (จาก 5 สัญญาณ)` | จำนวนสัญญาณขั้นต่ำที่ถือว่าเข้ารูปแบบ Mule | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.CROSS.MIN_LINKS = 2` | collector/feeder ต้องเชื่อมกับบัญชีที่เข้ารูปแบบ Mule อย่างน้อยกี่บัญชี | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `MULE.NETWORK.MIN_SIZE = 3` | จำนวนบัญชีขั้นต่ำของกลุ่มเครือข่าย | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `CPTY.NEW_RATIO = 50%` | สัดส่วนคู่ค้าใหม่ต่อเดือนที่ถือว่าผิดปกติ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `CPTY.NEW_LARGE.MULTIPLIER = 5` | ตัวคูณ median ยอดของบัญชี สำหรับคู่ค้าใหม่ยอดสูง | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FLOW.MAX_HOPS = 4` | ไล่เส้นทางเงินสูงสุดกี่ทอด | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FLOW.WINDOW_DAYS = 7` | ช่วงเวลาที่ไล่เส้นทางเงิน | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FLOW.MIN_PASS_RATIO = 90%` | แต่ละทอดส่งต่อเงินอย่างน้อยเท่าไรจึงนับเป็น layering | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FLOW.AUTO_MAX_ENTITIES = 10` | จำนวนบัญชีที่ไล่เส้นทางเงินอัตโนมัติ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FLOW.MAX_TRAIL_ROWS = 5,000` | จำนวนแถวสูงสุดของ Money Flow trail ต่อการไล่ 1 ครั้ง ถึงขีดนี้แล้วหยุดและแจ้งว่าผลอาจไม่ครบ | ขีดจำกัดทางเทคนิคเพื่อให้ผลอ่านได้และไม่เกินเวลาประมวลผล |

## 12. การ์ดทั่วไป บัญชีเจ้าหนี้ และสินเชื่อ (เพิ่มใน v1.2)
แหล่งที่มาของค่าในหมวดนี้: แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ (ค่าเริ่มต้นสำหรับการตรวจเชิงวิเคราะห์ ไม่ใช่เกณฑ์ที่หน่วยงานกำกับกำหนด) ค่าที่ใช้ซ้ำจากหมวดอื่น (`FOR.*`, `CONC.*`, `TEMP.PERIOD_END.WINDOW`) คงเดิมและถูกใช้โดยการ์ด GEN-CONC, GEN-PERIOD-END, FOR-BENFORD, FOR-ROUND, FOR-REPEAT และ SPLIT-LIMIT
| ค่า | ความหมาย | ที่มา |
|---|---|---|
| `DUP.WINDOW_DAYS = 3` | รายการจ่ายซ้ำ (entity + คู่ค้า + ยอดเท่ากัน และเลขที่เอกสารเดียวกันถ้ามี) ที่เกิดห่างกันไม่เกินกี่วัน ถือว่าเข้าข่ายจ่ายซ้ำ (DUP-PAY) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `SPLIT.WINDOW_DAYS = 1` | รายการของ entity เดียวกันถึงคู่ค้าเดียวกันที่ห่างกันไม่เกินกี่วัน นับเป็นชุดเดียวกันเมื่อตรวจการแบ่งรายการ (SPLIT-LIMIT) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `SPLIT.MIN_TX = 2` | จำนวนรายการขั้นต่ำในชุดที่เข้าใกล้วงเงินและรวมกันเกินวงเงิน จึงนับเป็นสัญญาณแบ่งรายการ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `DUE.NEAR_DAYS = 2` | ชำระก่อนวันครบกำหนด 0 ถึงกี่วัน ถือว่าชำระใกล้วันครบกำหนด (DUE-NEAR) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `DUE.MIN_SHARE = 80%` | สัดส่วนงวดของสัญญาเดียวกันที่ชำระใกล้วันครบกำหนดขั้นต่ำ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `DUE.MIN_PERIODS = 3` | จำนวนงวดขั้นต่ำของสัญญาที่ใช้ประเมิน DUE-NEAR | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `PAYER.MIN_CONTRACTS = 3` | ผู้ชำระที่ไม่ใช่ entity ของสัญญา ชำระสัญญาที่ต่างกันตั้งแต่กี่สัญญา (PAYER-MULTI) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `INTAKE.ROLE_CONF = สูง ≥ 0.8 / กลาง ≥ 0.5` | เกณฑ์ความมั่นใจของการเสนอบทบาทคอลัมน์ (suggest_roles) ที่ต่ำกว่าค่ากลางเป็นระดับต่ำ | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `INTAKE.JOIN_MIN_PCT = 90%` | สัดส่วนขั้นต่ำของรหัสในตารางธุรกรรมที่ต้องเชื่อมกับตารางรองได้ (เช่น opened_at ในตาราง accounts/contracts) ต่ำกว่านี้ความพร้อมของข้อมูลเป็น "บางส่วน" (assess_sufficiency) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `TEMP.PERIOD_END.MIN_TX = 3` | จำนวนรายการขั้นต่ำของ entity ในช่วงสิ้นงวด (`TEMP.PERIOD_END.WINDOW`) ของงวดนั้น จึงนับเป็นสัญญาณ (GEN-PERIOD-END) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `TEMP.PERIOD_END.MIN_SHARE = 50%` | สัดส่วนขั้นต่ำของรายการช่วงสิ้นงวดต่อรายการทั้งหมดของ entity ในงวดนั้น (ต้องครบทั้งจำนวนและสัดส่วน) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |
| `FOR.ROUND.MIN_SHARE = 50%` | สัดส่วนขั้นต่ำของยอดกลม (`FOR.ROUND.UNIT`) ต่อรายการทั้งหมดของ entity จึงนับเป็นสัญญาณ (FOR-ROUND ใช้ `GATE.SAMPLE.MIN` เป็นจำนวนรายการขั้นต่ำของ entity) | แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ |

## Machine Config (สำหรับ recipe)
JSON ก้อนเดียวนี้คือค่าที่ recipe อ่านเป็น `cfg[<key>]` — key ระดับบนสุดต้องมีในตาราง/หัวข้อของไฟล์นี้ (key ที่ขึ้นต้นด้วย `_` ใช้เป็น runtime context) และ `ASSESS.PRIORITY` เรียง Confidence ก่อน แล้วจึง Materiality ตามตาราง Priority (ไม่รวมหมายเหตุ Human Review)
```json
{
  "REGISTRY.VERSION": "1.2",
  "GATE.COMPLETENESS.MIN": 0.95,
  "GATE.SAMPLE.MIN": 30,
  "STAT.MAD.THRESHOLD": 3.5,
  "BEH.BASELINE.MIN_PERIODS": {"velocity_days": 6, "spike_months": 6},
  "BEH.DEVIATION": 3,
  "BEH.VELOCITY.SD_FLOOR": "poisson",
  "TEMP.OFF_HOURS": {"start": "08:00", "end": "18:00", "weekend": true},
  "TEMP.OFF_HOURS.MIN_TX": 3,
  "TEMP.OFF_HOURS.MIN_SHARE": 0.8,
  "NET.CYCLE": {"min_len": 2, "max_len": 5, "days": 30},
  "NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7},
  "NET.CYCLE.MAX_PATHS": 100000,
  "MULE.DWELL_HOURS": 24,
  "MULE.DWELL_MIN_PAIRS": 3,
  "MULE.NEW_ACCT_DAYS": 30,
  "MULE.NEW_ACCT_MIN_TX": 20,
  "MULE.MIN_SIGNALS": 3,
  "MULE.CROSS.MIN_LINKS": 2,
  "MULE.NETWORK.MIN_SIZE": 3,
  "CPTY.NEW_RATIO": 0.5,
  "CPTY.NEW_LARGE.MULTIPLIER": 5,
  "FLOW.MAX_HOPS": 4,
  "FLOW.WINDOW_DAYS": 7,
  "FLOW.MIN_PASS_RATIO": 0.9,
  "FLOW.AUTO_MAX_ENTITIES": 10,
  "FLOW.MAX_TRAIL_ROWS": 5000,
  "CONC.HHI": {"low": 1500, "high": 2500},
  "CONC.SINGLE_ENTITY_SHARE": 0.1,
  "CONC.TOPN": 10,
  "TEMP.PERIOD_END.WINDOW": {"before_business_days": 3, "after_days": 3},
  "TEMP.PERIOD_END.MIN_TX": 3,
  "TEMP.PERIOD_END.MIN_SHARE": 0.5,
  "FOR.BENFORD.MIN_N": 1000,
  "FOR.BENFORD.MAD_1ST": {"close": 0.006, "acceptable": 0.012, "marginal": 0.015},
  "FOR.ROUND.UNIT": 1000,
  "FOR.ROUND.MIN_SHARE": 0.5,
  "FOR.THRESHOLD_AVOID.BAND": {"low": 0.9, "high": 0.9999},
  "FOR.REPEAT.MIN_COUNT": 3,
  "DUP.WINDOW_DAYS": 3,
  "SPLIT.WINDOW_DAYS": 1,
  "SPLIT.MIN_TX": 2,
  "DUE.NEAR_DAYS": 2,
  "DUE.MIN_SHARE": 0.8,
  "DUE.MIN_PERIODS": 3,
  "PAYER.MIN_CONTRACTS": 3,
  "INTAKE.ROLE_CONF": {"สูง": 0.8, "กลาง": 0.5},
  "INTAKE.JOIN_MIN_PCT": 0.9,
  "ASSESS.CLEARLY_TRIVIAL": 0.05,
  "ASSESS.PRIORITY": {
    "สูง": {"สูง": "สูง", "กลาง": "กลาง", "ต่ำ": "ต่ำ"},
    "กลาง": {"สูง": "สูง", "กลาง": "กลาง", "ต่ำ": "ต่ำ"},
    "ต่ำ": {"สูง": "กลาง", "กลาง": "ต่ำ", "ต่ำ": "ต่ำ"}
  }
}
```

## ประวัติการเปลี่ยนแปลง
| เวอร์ชัน | วันที่ | การเปลี่ยนแปลง |
|---|---|---|
| 1.0 | 2026-11-03 | ฉบับแรก: ค่ามาตรฐานทั่วไปทุก skill |
| 1.1 | 2026-11-03 | เพิ่มหมวด 11 (MULE / CPTY / FLOW รวม `MULE.DWELL_MIN_PAIRS`, `MULE.NEW_ACCT_MIN_TX`), `BEH.VELOCITY.SD_FLOOR`, `NET.CYCLE.MAX_PATHS` (ต่อเดือน), `FLOW.MAX_TRAIL_ROWS`, `TEMP.OFF_HOURS.MIN_TX`, `TEMP.OFF_HOURS.MIN_SHARE`, `REGISTRY.VERSION` และ Machine Config JSON สำหรับ recipe (ไม่เปลี่ยนค่าเดิม) |
| 1.2 | 2026-11-06 | เพิ่มหมวด 12 สำหรับการ์ดใหม่ของ engine (`DUP.WINDOW_DAYS`, `SPLIT.WINDOW_DAYS`, `SPLIT.MIN_TX`, `DUE.NEAR_DAYS`, `DUE.MIN_SHARE`, `DUE.MIN_PERIODS`, `PAYER.MIN_CONTRACTS`, `INTAKE.ROLE_CONF`, `INTAKE.JOIN_MIN_PCT`, `TEMP.PERIOD_END.MIN_TX`, `TEMP.PERIOD_END.MIN_SHARE`, `FOR.ROUND.MIN_SHARE`) และเพิ่มค่า `FOR.*`, `CONC.*`, `TEMP.PERIOD_END.WINDOW` เดิมเข้า Machine Config (ค่าเดิมไม่เปลี่ยน; แก้ข้อความ `FOR.THRESHOLD_AVOID.BAND` เป็น 90%–99.99% เท่านั้น) |

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
- AIDA-17 Data Evidence Schema (Machine Config ถูกใช้โดย recipe)
