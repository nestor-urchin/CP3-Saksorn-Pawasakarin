# AIDA-05 · Anomaly Skills II: Behavioral (5.3) และ Temporal (5.4)
> ไฟล์: AIDA-05 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: เปรียบเทียบพฤติกรรมกับอดีตหรือ peer อย่างไร, ต้องมี baseline กี่งวด, Trend / Period-end / Change Point / Time-of-day ใช้เมื่อไหร่, ไม่มี timestamp ทำอย่างไร

## สรุปสั้น
การเปรียบเทียบต้องมี Baseline หรือช่วงเวลาที่เพียงพอ มิฉะนั้นต้อง Skip
- **5.3 Behavioral** เปรียบเทียบ entity กับประวัติของตัวเองหรือกลุ่ม peer
- **5.4 Temporal** หารูปแบบผิดปกติตามเวลา ต้องมี timestamp / period / granularity ที่รองรับ

## 5.3 Behavioral Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | ชี้การเปลี่ยนแปลงพฤติกรรมของ entity เทียบ baseline ของตัวเองหรือ peer |
| Non-purpose | ไม่อธิบายสาเหตุของการเปลี่ยนแปลง ไม่สรุปเจตนา |
| Input | entity + metric รายงวด (amount / count) + ประวัติย้อนหลัง หรือกลุ่ม peer ที่เทียบกันได้ |
| Output | Evidence: entity, metric, baseline/peer value, ส่วนเบี่ยงเบน, period, threshold, data reference |
| Configuration | `BEH.BASELINE.MIN_PERIODS = 6 งวด (แนะนำ 12)` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `BEH.PEER.MIN_SIZE = 5` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `BEH.DEVIATION = 3σ` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) |
| Audit Trail | Run ID, skill version, นิยาม baseline / peer group, ช่วงเวลา baseline, Registry version |
| Success | ทุก entity ที่ผ่าน gate มี baseline/peer และค่าเบี่ยงเบนที่อธิบายได้ |
| Stop/Skip | Gate: ไม่มีข้อมูลเปรียบเทียบเพียงพอ → Skip + Reason (ประวัติไม่ถึงขั้นต่ำ หรือ peer ไม่พอ) |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Historical Comparison | ค่าปัจจุบันต่างจากอดีตของ entity | entity + ประวัติ | `BEH.BASELINE.MIN_PERIODS = 6 งวด (แนะนำ 12)` | entity, ค่าปัจจุบัน, ค่าอดีต, % เปลี่ยน | ตรวจการเปลี่ยนนโยบาย/สัญญา |
| Baseline Comparison | ต่างจากค่าปกติที่คำนวณไว้ | entity + baseline | `BEH.DEVIATION = 3σ` | entity, baseline, ส่วนเบี่ยงเบน | baseline ต้องไม่รวมช่วงผิดปกติ |
| Peer Comparison | ต่างจากกลุ่มที่คล้ายกัน | entity + peer group | `BEH.PEER.MIN_SIZE = 5` | entity, ค่า peer, อันดับ | นิยาม peer ต้องสมเหตุสมผล |
| Frequency Shift | ความถี่เปลี่ยนไป | entity + count รายงวด | `BEH.DEVIATION = 3σ` | entity, ความถี่ก่อน/หลัง | ฤดูกาลอาจเป็นสาเหตุ |
| Activity Spike | กิจกรรมพุ่งขึ้นระยะสั้น | entity + time series | `BEH.DEVIATION = 3σ` | entity, ช่วงเวลา, ขนาด spike | ตรวจเหตุการณ์ทางธุรกิจในช่วงนั้น |
| Velocity Analysis | ความเร็วการทำรายการต่อหน่วยเวลา | entity + timestamp | `BEH.DEVIATION = 3σ` | entity, รายการ/ชั่วโมง หรือ/วัน | ระบบอัตโนมัติอาจทำรายการเร็วตามปกติ |
| Behavioral Change | รูปแบบโดยรวมเปลี่ยน | entity + หลาย metric | `BEH.DEVIATION = 3σ` | entity, metric ที่เปลี่ยน, จุดเปลี่ยน | ใช้ร่วมกับ Change Point (5.4) |

## 5.4 Temporal Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | หารูปแบบผิดปกติตามเวลา เช่น ช่วงสิ้นงวด จุดเปลี่ยนแนวโน้ม เวลาทำรายการ |
| Non-purpose | ไม่ใช้กับข้อมูลที่ไม่มีเวลาหรือ granularity ไม่พอ ไม่สรุปเจตนา |
| Input | timestamp หรือ period + metric + record key |
| Output | Evidence: ช่วงเวลา, metric, ค่าคาดหมาย, ค่าจริง, รูปแบบที่พบ, data reference |
| Configuration | `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) |
| Audit Trail | Run ID, skill version, timezone, ปฏิทินวันหยุดที่ใช้, granularity, Registry version |
| Success | ช่วงเวลาครอบคลุมตามขั้นต่ำ และทุกรูปแบบระบุช่วงเวลาและรายการที่เกี่ยวข้องได้ |
| Stop/Skip | Gate: Timestamp / period / granularity ต้องรองรับ ไม่รองรับ → Skip + reason (เช่น มีแค่วันที่ ไม่มีเวลา → Skip Time-of-day แต่ยังทำ Month-end ได้) |

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Trend Analysis | แนวโน้มผิดจากที่คาด | period + metric | `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` | ช่วงเวลา, ค่าจริง vs คาดหมาย | แยกฤดูกาลออกก่อน |
| Month-end / Quarter-end Analysis | กิจกรรมกระจุกช่วงปิดงวด | วันที่ | `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` | งวด, สัดส่วนในช่วงปิดงวด | ปิดงวดมีรายการปรับปรุงตามปกติ |
| Period-end Spike | ยอดพุ่งช่วงสิ้นงวด | วันที่ + amount | `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` | งวด, ยอดช่วงสิ้นงวด vs ปกติ | ดูรายการกลับรายการต้นงวดถัดไปประกอบ |
| Change Point Detection | จุดที่รูปแบบเปลี่ยนชัดเจน | time series | `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` | วันที่จุดเปลี่ยน, ขนาดการเปลี่ยน | เทียบกับเหตุการณ์ (ระบบใหม่ นโยบายใหม่) |
| Time-of-day Pattern | เวลาทำรายการผิดปกติ | timestamp มีเวลา | `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` | record, เวลา, ผู้ทำรายการ | งาน batch/กะกลางคืนเป็นเรื่องปกติได้ |
| Unusual Timing Pattern | วันหรือช่วงที่ไม่ควรมีรายการ | timestamp + ปฏิทิน | `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` | record, วัน/เวลา | ใช้ปฏิทินวันหยุดขององค์กร |

## ข้อห้าม (Guardrails)
- ห้ามสร้าง baseline จากข้อมูลไม่ถึงขั้นต่ำเพื่อ "ให้รันได้" — ต้อง Skip + reason
- รายการนอกเวลาหรือช่วงปิดงวดไม่ได้แปลว่าผิดเสมอไป ต้องพิจารณาบริบท
- ระบุ timezone และปฏิทินที่ใช้ทุกครั้ง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-02 Skip, AIDA-03 Selection Matrix, AIDA-06 Sequence, AIDA-09 Hybrid, AIDA-14 Registry
