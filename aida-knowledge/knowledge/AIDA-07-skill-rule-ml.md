# AIDA-07 · Anomaly Skills IV: Rule-Based (5.7) และ Machine Learning (5.8)
> ไฟล์: AIDA-07 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: กฎธุรกิจต้องเก็บที่ไหน, Isolation Forest / LOF / One-Class / Clustering / Autoencoder ใช้เมื่อไหร่, ผล ML ต้องมีอะไรบ้าง, Anomaly Score แปลว่าอะไร

## สรุปสั้น
กฎและโมเดลต้องอยู่ภายใต้ Configuration / Version Control และสร้างคำอธิบายได้
- **5.7 Rule-Based** ตรวจรายการตามกฎที่อนุมัติแล้ว อ่านกฎจาก Configuration Registry เท่านั้น
- **5.8 Machine Learning** หาค่าผิดปกติหลายมิติ ผลต้องผ่าน Human Review เสมอ
- **Anomaly Score ≠ Fraud Conclusion**

## 5.7 Rule-Based Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | ตรวจรายการที่เข้าเงื่อนไขกฎที่องค์กรอนุมัติ (configured exception) |
| Non-purpose | ไม่สร้างหรือแก้กฎเอง ไม่ตีความเกินกว่าเงื่อนไขของกฎ |
| Input | กฎที่อนุมัติ + rule version + field ที่กฎต้องใช้ |
| Output | Evidence: record, rule ID, rule version, เงื่อนไขที่เข้า, ค่า field, data reference |
| Configuration | กฎทั้งหมดอยู่ใน Configuration Registry ขององค์กร (กฎเป็นเรื่องเฉพาะองค์กร จึงไม่มีค่ามาตรฐานใน AIDA-14) |
| Audit Trail | Run ID, rule ID, rule version, ผู้อนุมัติกฎ, วันที่มีผล |
| Success | ทุกกฎที่ active รันครบ และทุก exception ระบุกฎ + เวอร์ชัน |
| Stop/Skip | Gate: Rule version active — กฎไม่ active หรือ field ไม่ครบ → Skip + reason |

ข้อบังคับ: อ่านกฎจาก Configuration Registry เท่านั้น ห้าม Hard-code ใน Skill

### ประเภทกฎ
| ประเภท | ตัวอย่าง | Evidence ที่ได้ | ข้อควรระวัง |
|---|---|---|---|
| Approved Business Rules | ใบสั่งซื้อต้องอนุมัติก่อนรับของ | record, rule ID, เงื่อนไข | ใช้เฉพาะกฎที่อนุมัติแล้ว |
| Risk Rules | ผู้ขายใหม่ที่ไม่มีเลขผู้เสียภาษี | record, rule ID | ต้องเชื่อมกับ Risk Library |
| Compliance Rules | รายการที่ต้องรายงานตามกฎหมาย | record, rule ID, ข้อกฎหมาย | ตรวจเวอร์ชันกฎหมายล่าสุด |
| Transaction Rules | ผู้สร้างและผู้อนุมัติเป็นคนเดียวกัน | record, ผู้ใช้, rule ID | ตรวจสิทธิ์ระบบประกอบ |
| Exception Rules | รายการที่ข้ามขั้นตอนควบคุม | record, ขั้นตอนที่ข้าม | อาจมีการอนุมัติข้อยกเว้นไว้แล้ว |

## 5.8 Machine Learning Anomaly Detection

### Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | หารายการที่ผิดปกติเมื่อพิจารณาหลาย feature พร้อมกัน |
| Non-purpose | ไม่ให้ข้อสรุป ไม่ใช้คะแนนเป็น Materiality หรือ Priority |
| Input | feature ที่เตรียมแล้ว + observation ที่เพียงพอ + model/version |
| Output | Minimum output (ข้อถัดไป) → Human Review |
| Configuration | `ML.CONTAMINATION = 1%` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `ML.LOF.NEIGHBORS = 20` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `ML.MIN_OBS = 1,000 หรือ 10 × จำนวน feature` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) |
| Audit Trail | Run ID, model/method, model version, configuration version, feature list, random seed |
| Success | ทุกผลมี minimum output ครบและอธิบายได้ |
| Stop/Skip | Gate: Model suitability / explainability — ข้อมูลน้อยกว่าขั้นต่ำ หรืออธิบายผลไม่ได้ → ไม่ใช้ผล / Human review |

### Minimum output (ทุกรายการต้องมีครบ 8 ข้อ)
1. Record / Entity Reference
2. Anomaly Score
3. Model / Method
4. Relevant Features
5. Explanation
6. Configuration Version
7. Model Version
8. Data Reference

### เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Isolation Forest | รายการที่แยกออกจากกลุ่มได้ง่าย | feature ตัวเลข | `ML.CONTAMINATION = 1%` | minimum output 8 ข้อ | contamination กำหนดสัดส่วนผลเอง |
| Local Outlier Factor | รายการที่หนาแน่นต่ำกว่าเพื่อนบ้าน | feature ตัวเลข (scale แล้ว) | `ML.LOF.NEIGHBORS = 20` | minimum output 8 ข้อ | ไวต่อการ scale feature |
| One-Class Classification | รายการที่ต่างจากข้อมูลปกติที่เรียนรู้ | ข้อมูลที่เชื่อว่าปกติ | `ML.CONTAMINATION = 1%` | minimum output 8 ข้อ | ข้อมูลฝึกต้องสะอาด |
| Clustering-based Detection | รายการที่ไม่อยู่ในกลุ่มใดหรือกลุ่มเล็กมาก | feature ตัวเลข | `ML.MIN_OBS = 1,000 หรือ 10 × จำนวน feature` | minimum output 8 ข้อ + cluster ID | จำนวนกลุ่มมีผลต่อผลลัพธ์ |
| Autoencoder-based Detection | รายการที่สร้างกลับได้ไม่ดี (reconstruction error สูง) | feature จำนวนมาก | `ML.MIN_OBS = 1,000 หรือ 10 × จำนวน feature` | minimum output 8 ข้อ + reconstruction error | อธิบายยากที่สุด ต้องมี explanation ชัด |

## ข้อห้าม (Guardrails)
- **Anomaly Score ≠ Fraud Conclusion** — คะแนนสูงหมายถึงควรทบทวน ไม่ใช่ข้อสรุป
- ห้ามใช้ Model Score เป็น Materiality โดยตรง
- ห้ามเผยแพร่ผล ML ก่อน Human Review
- ห้าม Hard-code กฎใน skill และห้ามใช้กฎที่ไม่ active

## ไฟล์ที่เกี่ยวข้อง
- AIDA-02 Human Review, AIDA-03 Selection Matrix, AIDA-09 Hybrid, AIDA-10 Assessment, AIDA-13 Version Control, AIDA-14 Registry
