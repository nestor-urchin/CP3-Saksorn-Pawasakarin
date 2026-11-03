# AIDA-08 · Anomaly Skills V: Network Analysis (5.9)
> ไฟล์: AIDA-08 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Network skill ทำอะไร, ต้องมีข้อมูลอะไร, เมื่อไหร่ต้อง Skip, Shared identifier / Circular flow / Funnel account คืออะไร, ออก evidence อะไร

## สรุปสั้น
ตรวจความสัมพันธ์และรูปแบบเครือข่าย โดยต้องมี Entity และ Relationship Fields ที่เพียงพอ
Gate: Entity/Relationship ไม่พอ → Skip + Reason
ผลจาก Network pattern ต้องผ่าน Human Review ก่อนนำไปใช้ (AIDA-02)

## Universal Skill Spec
| ช่อง | รายละเอียด |
|---|---|
| Purpose | สร้าง graph ของ entity และความสัมพันธ์ แล้วหารูปแบบเครือข่ายที่ควรตรวจสอบ |
| Non-purpose | ไม่สรุปว่าเป็นการสมรู้ร่วมคิดจากความสัมพันธ์ที่พบ และไม่ระบุบุคคลว่าเป็นผู้กระทำ |
| Input | entity id + relationship identifier (บัญชีธนาคาร ที่อยู่ เบอร์โทร เลขผู้เสียภาษี ผู้ถือหุ้น/กรรมการ) และ/หรือ ธุรกรรมระหว่าง entity (ผู้โอน ผู้รับ ยอด เวลา) |
| Output | Evidence: subgraph, node/edge ที่เกี่ยวข้อง, รูปแบบที่ตรง, metric (centrality, cycle length), data reference → Network Investigation Package (Output 14) |
| Configuration | `NET.SHARED_ID.MIN = 2` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14), `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14) |
| Audit Trail | Run ID, skill version, กฎ entity resolution, identifier ที่ใช้เชื่อม, ช่วงเวลา, Registry version |
| Success | Graph construction possible และทุก edge ย้อนกลับถึง record ต้นทางได้ |
| Stop/Skip | Gate: Entity/Relationship ไม่พอ หรือสร้าง graph ไม่ได้ → Skip + Reason (ระบุ identifier ที่ขาด) |

## เทคนิค
| เทคนิค | ตรวจหาอะไร | ข้อมูลขั้นต่ำ | ค่ามาตรฐาน (Registry key) | Evidence ที่ได้ | ข้อควรระวังในการตีความ |
|---|---|---|---|---|---|
| Entity Resolution | รวม entity ที่เป็นรายเดียวกันแต่บันทึกต่างกัน | ชื่อ + identifier | กฎ matching ขององค์กร | กลุ่ม entity ที่รวม, คะแนน match | match ผิดทำให้ทุกเทคนิคถัดไปผิด ต้องบันทึกกฎ |
| Graph Construction | สร้างเครือข่าย node/edge | entity + relationship | — | graph, จำนวน node/edge | ระบุช่วงเวลาที่ใช้สร้าง graph |
| Shared Identifier Analysis | entity หลายรายใช้ identifier เดียวกัน | identifier | `NET.SHARED_ID.MIN = 2` | identifier, entity ที่ใช้ร่วม | บริษัทในเครือหรือที่อยู่อาคารสำนักงานใช้ร่วมกันได้ตามปกติ |
| Community / Centrality Analysis | กลุ่มที่เชื่อมแน่น / node ศูนย์กลาง | graph | — | community ID, centrality | ศูนย์กลางอาจเป็นคู่ค้าหลักปกติ |
| Circular Flow / Funnel Account | เงินหมุนวน / บัญชีรวมเงินแล้วโอนออก | ธุรกรรมผู้โอน-ผู้รับ-เวลา | `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน`, `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน` | เส้นทางเงิน, ยอด, ช่วงเวลา | บัญชีพักเงินขององค์กรมีรูปแบบคล้ายกันได้ |
| Hidden Controller / Related Party Pattern | ผู้ควบคุมร่วมหรือบุคคลเกี่ยวโยงที่ไม่เปิดเผย | ผู้ถือหุ้น/กรรมการ/ผู้ติดต่อ | — | เส้นทางความสัมพันธ์ | ต้องยืนยันกับข้อมูลทะเบียนทางการ |
| Fraud Ring / Mule Network Pattern | กลุ่มบัญชีที่มีรูปแบบคล้ายเครือข่ายบัญชีม้า | ธุรกรรม + identifier | `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน` | subgraph, รูปแบบที่ตรง | ชื่อรูปแบบเป็นชื่อเรียก pattern ไม่ใช่ข้อสรุป ต้อง Human Review |
| Network Evolution | การเปลี่ยนแปลงของเครือข่ายข้ามช่วงเวลา | graph หลายงวด | `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` | node/edge ใหม่หรือหายไป, ช่วงเวลา | ใช้ร่วมกับ Early Warning (AIDA-12) |

## ตัวอย่าง Skip Reason
```
Skill: Network | ผล: Skip | เหตุผล: ไม่มี relationship identifier จึงสร้าง graph ไม่ได้ | ข้อมูลที่ขาด: บัญชีธนาคาร / ที่อยู่ / เลขผู้เสียภาษีของ vendor | Registry: NET.SHARED_ID.MIN
```

## ข้อห้าม (Guardrails)
- ความสัมพันธ์ไม่ใช่หลักฐานการสมรู้ร่วมคิด ต้องใช้ภาษากลาง เช่น "พบ identifier ร่วมที่ควรตรวจสอบเพิ่มเติม"
- ห้ามเรียกบุคคลว่า "บัญชีม้า" หรือ "ผู้กระทำ" ในรายงาน ใช้ชื่อ pattern และ "Potential Risk"
- ห้ามรันต่อเมื่อ Entity Resolution ไม่ได้บันทึกกฎ matching
- ผล Network pattern ต้องผ่าน Human Review ก่อนเผยแพร่

## ไฟล์ที่เกี่ยวข้อง
- AIDA-02 Human Review, AIDA-03 Selection Matrix, AIDA-09 Hybrid, AIDA-12 Network Investigation Package, AIDA-14 Registry
