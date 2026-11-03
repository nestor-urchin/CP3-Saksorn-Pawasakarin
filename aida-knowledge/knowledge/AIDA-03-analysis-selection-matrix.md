# AIDA-03 · Analysis Selection Matrix และ Capability Gate
> ไฟล์: AIDA-03 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: ข้อมูลแบบนี้ใช้ skill ไหนได้, แต่ละ skill family ต้องมีข้อมูลขั้นต่ำอะไร, Decision gate ของแต่ละ skill คืออะไร, ต้องเขียน Selection / Skip Reason อย่างไร

## สรุปสั้น
Planner ใช้ Capability Gate ก่อนเรียก skill และต้องบันทึกเหตุผลทุกครั้ง
ทุก skill family มี Minimum capability (field ที่ต้องมี) และ Decision gate (เงื่อนไขคุณภาพ) ผลคือ Run, Skip หรือ Human review
Profile และ Capability Gate ต้องทำงานก่อน Analysis เสมอ

## Analysis Selection Matrix
| Skill family | Minimum capability | Decision gate | Outcome | ไฟล์ |
|---|---|---|---|---|
| Statistical | Numeric amount / count / volume | Distribution & sample adequate | Run / Skip | AIDA-04 |
| Behavioral | Entity + comparable history/peer | Baseline exists | Run / Skip + reason | AIDA-05 |
| Temporal | Timestamp + sufficient period | Granularity supports pattern | Run / Skip | AIDA-05 |
| Sequence | Event type + timestamp + entity | Order can be reconstructed | Run / Skip | AIDA-06 |
| Forensic | Amount / digit structure | Method minimum met | Run / Skip | AIDA-06 |
| Rule-based | Configured approved rule + fields | Rule version active | Run / Skip | AIDA-07 |
| ML | Features + adequate observations | Model suitability / explainability | Run / Human review | AIDA-07 |
| Network | Entity + relationship identifiers | Graph construction possible | Run / Skip + reason | AIDA-08 |

Concentration (5.2) ใช้เงื่อนไขเดียวกับ Statistical และต้องมี entity + amount (AIDA-04)
Hybrid (5.10) รันเมื่อมี Evidence จากอย่างน้อย 2 skill family (AIDA-09)

## Minimum Data Requirement (ใช้ร่วมทุก skill)
- field จำเป็นมีค่าครบ: `GATE.COMPLETENESS.MIN = 95%` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- จำนวนรายการต่อกลุ่ม: `GATE.SAMPLE.MIN = 30` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- อ้างอิงต้นทางได้: `GATE.TRACE.REQUIRED = dataset + table + period + record key` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) ไม่ครบ → Stop ทั้ง workflow
- ค่าขั้นต่ำเฉพาะวิธี (เช่น Benford, ML, Baseline) อยู่ในไฟล์ skill และ AIDA-14

## ขั้นตอนของ Planner
1. อ่าน Dataset Profile (field, type, completeness, period, จำนวนรายการ)
2. อ่าน Risk Context เพื่อเลือก skill family ที่ตอบความเสี่ยง
3. ตรวจ Minimum capability ของแต่ละ family
4. ตรวจ Decision gate (คุณภาพ / ปริมาณ / เวอร์ชันกฎ)
5. บันทึก Selection / Skip Reason ทุก family รวมถึงตัวที่ไม่ได้เลือกเพราะไม่ตรงความเสี่ยง
6. ส่ง Analysis Plan (Output 03)

## Template: Selection / Skip Reason
```
Skill: <family / เทคนิค> | ผล: Run / Skip / Human review | เหตุผล: <gate ที่ผ่านหรือไม่ผ่าน> | ข้อมูลที่ขาด: <field หรือปริมาณ หรือ "-"> | Registry: <key ที่ใช้ตัดสิน>
```

## ตัวอย่าง (Worked example)
Dataset: รายการจ่ายเงิน มี amount, vendor_id, payment_date, approver และมี record key ครบ แต่ไม่มี field ความสัมพันธ์ (บัญชีธนาคาร ที่อยู่ ผู้ถือหุ้น)
```
Skill: Statistical  | ผล: Run  | เหตุผล: มี amount และจำนวนรายการเพียงพอ | ข้อมูลที่ขาด: - | Registry: GATE.SAMPLE.MIN
Skill: Concentration| ผล: Run  | เหตุผล: มี vendor_id + amount | ข้อมูลที่ขาด: - | Registry: CONC.SINGLE_ENTITY_SHARE
Skill: Temporal     | ผล: Run  | เหตุผล: มี payment_date ครอบคลุมช่วงเวลาเพียงพอ | ข้อมูลที่ขาด: - | Registry: TEMP.TREND.MIN_PERIODS
Skill: Sequence     | ผล: Skip | เหตุผล: ไม่มี event type จึงสร้างลำดับเหตุการณ์ไม่ได้ | ข้อมูลที่ขาด: event type / vendor master change log | Registry: -
Skill: Network      | ผล: Skip | เหตุผล: ไม่มี relationship identifier จึงสร้าง graph ไม่ได้ | ข้อมูลที่ขาด: บัญชีธนาคาร / ที่อยู่ / เลขผู้เสียภาษี | Registry: NET.SHARED_ID.MIN
Skill: ML           | ผล: Human review | เหตุผล: ต้องยืนยันความเหมาะสมของโมเดลก่อน | ข้อมูลที่ขาด: - | Registry: ML.MIN_OBS
```

## ข้อห้าม (Guardrails)
- ห้ามเรียก skill ก่อนผ่าน Profile และ Capability Gate
- ห้าม Skip โดยไม่มีเหตุผลและข้อมูลที่ขาด
- ห้ามเลือก skill เพียงเพราะ "รันได้" โดยไม่เชื่อมกับ Risk Context

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Workflow Stage 5–7, AIDA-02 Decision Gates, AIDA-04 ถึง AIDA-09 Skill, AIDA-14 Registry
