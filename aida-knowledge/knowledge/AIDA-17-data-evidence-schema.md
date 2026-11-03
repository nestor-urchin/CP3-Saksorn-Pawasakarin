# AIDA-17 · Data & Evidence Schema (คอลัมน์มาตรฐาน, Evidence/Finding และความเสี่ยงใน B1)
> ไฟล์: AIDA-17 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: ไฟล์ข้อมูลธุรกรรมต้องมีคอลัมน์อะไร, Evidence / Finding / Mule Network / Money Flow trail / Run Log มีคอลัมน์อะไร, Data Reference เขียนอย่างไร, ความเสี่ยง R1–R4 ใน Phase B1 คืออะไรและการ์ดใดให้ Evidence

## สรุปสั้น
ไฟล์นี้กำหนด **รูปแบบข้อมูล** ที่ AIDA ใช้เมื่อวิเคราะห์ไฟล์ธุรกรรมที่ผู้ใช้แนบมา (Phase B1: Mule Account pattern) ได้แก่ คอลัมน์ input มาตรฐาน, Schema ของผลลัพธ์ 5 แบบ (Evidence, Finding, Mule Network, Money Flow trail, Run Log), รูปแบบ Data Reference และตารางความเสี่ยง R1–R4
ทุก Evidence ต้องย้อนกลับไปยังรายการต้นทางได้ผ่าน `record_refs` + `data_ref` ตามหลัก Traceability (AIDA-13) และบันทึก Registry version ที่ใช้ (ดู AIDA-14)
ผลทุกรายการเป็นเพียงสัญญาณว่า "ควรตรวจสอบเพิ่มเติม" และใช้ถ้อยคำตาม AIDA-11 เช่น "สอดคล้องกับ Mule Account pattern"

## 1. คอลัมน์มาตรฐาน (input)
| ตาราง | คอลัมน์ | บังคับ |
|---|---|---|
| `transactions` | tx_id, ts, from_acct, to_acct, amount, currency, channel | ใช่ (currency, channel ไม่บังคับ) |
| `accounts` | acct_id, opened_at, account_type | ไม่ |

- AIDA เสนอการจับคู่คอลัมน์ของผู้ใช้กับคอลัมน์มาตรฐาน แล้วให้ผู้ใช้ยืนยันก่อนวิเคราะห์ (จุดยืนยัน 1)
- ขาดคอลัมน์ที่การ์ดต้องใช้ → การ์ดนั้น Skip + reason (ดู AIDA-02)
- Record key: `tx_id` (transactions), `acct_id` (accounts) — ไม่มี `tx_id` → **STOP** ตาม `GATE.TRACE.REQUIRED = dataset + table + period + record key` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- ไม่มี `accounts` → MULE-NEW-ACCT ใช้วันที่พบรายการแรกของบัญชี (first_seen) แทน `opened_at`

## 2. Schema ของผลลัพธ์
| Schema | คอลัมน์ |
|---|---|
| Evidence | evidence_id, run_id, recipe_id, recipe_version, skill_family, entity_type (account / network), entity_id, risk, period (YYYY-MM), metric, value, threshold, registry_key, registry_version, explanation, record_refs (list ของ tx_id), data_ref |
| Finding | finding_id, entity_type, entity_id, risk, period, evidence_ids, skill_families, exposure, confidence, materiality, priority, review_status, review_reason, network_id (ถ้าบัญชีอยู่ในเครือข่าย) |
| Mule Network | network_id, member_accts, roles (mule / collector / feeder ต่อบัญชี), internal_tx_count, internal_amount, period_start, period_end |
| Money Flow trail | trace_id, start_acct, direction, hop, from_acct, to_acct, amount, ts, tx_id |
| Run Log | run_id, timestamp, stage (1–18), status (OK / STOP / SKIP / REVIEW), detail, recipe_id, recipe_version, registry_version, pack_version, input_sha256 |

- Evidence หนึ่งแถว = สัญญาณหนึ่งรายการของหนึ่ง entity ในหนึ่งเดือน (`period`) ผลที่ไม่พบสัญญาณ = ไม่มีแถว
- `value` เทียบกับ `threshold` และ `registry_key` ต้องชี้ค่าใน AIDA-14 เสมอ พร้อม `registry_version`
- `exposure` ของ Finding คือยอดเงินที่เกี่ยวข้อง ใช้คำนวณ Materiality ตาม AIDA-10 — ห้ามใช้คะแนน/สัญญาณเป็น Materiality โดยตรง
- Money Flow trail เป็นเส้นทางเงินเพื่อการสอบสวน ไม่ใช่ Evidence และไม่นับเป็น Finding

## 3. Data Reference
รูปแบบข้อความที่ใช้ในคอลัมน์ `data_ref` ของ Evidence และบันทึกใน Run Log เพื่อให้ทำซ้ำได้ (Lineage ระดับ 1 ใน AIDA-13)
- ไฟล์แนบในแชท: `chat:<ชื่อไฟล์>#<sheet>@<เวลาอัปโหลด ISO>|sha256:<hash>`
- SharePoint / OneDrive: `sp:<URL>#<sheet>@<เวอร์ชันไฟล์ ถ้ามี>|sha256:<hash>`

ตัวอย่าง: `chat:transactions.xlsx#Sheet1@2026-11-03T09:30:00|sha256:ab12…` — ค่า sha256 มาจากไฟล์ที่ผู้ใช้อัปโหลด ถ้าไฟล์เปลี่ยน hash ต้องเปลี่ยนและถือเป็น dataset ใหม่

## 4. ความเสี่ยงใน B1
| Risk | ชื่อ | entity | การ์ดที่ให้ Evidence |
|---|---|---|---|
| R1 | การเคลื่อนย้ายเงินผิดปกติ | account | STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, NET-CYCLE, NET-FUNNEL, FLOW-LAYERING, MULE-DWELL, MULE-NEW-ACCT |
| R2 | รูปแบบบัญชีรับ-ส่งต่อเงิน (Mule Account pattern) | account | MULE-PATTERN (+ สัญญาณที่ถูกรวมเข้ามา) |
| R3 | ธุรกรรมข้ามกลุ่มบัญชี Mule (Mule network) | network | MULE-CROSS-TX, MULE-NETWORK |
| R4 | ความผิดปกติของคู่ค้า (Counterparty) | account | CPTY-PROFILE, CPTY-NEW-LARGE |

- MULE-DWELL และ MULE-NEW-ACCT ให้ Evidence ระดับ R1 เป็น **สัญญาณ** ที่ MULE-PATTERN รวมเข้าเป็น R2 (แบบเดียวกับ NET-FUNNEL) — จำนวนสัญญาณขั้นต่ำอ้าง `MULE.MIN_SIGNALS = 3 (จาก 5 สัญญาณ)` (ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)
- FLOW-TRACE ไม่สร้าง Evidence — สร้าง Money Flow trail สำหรับการสอบสวน
- ความเสี่ยงทั้ง 4 ข้อเป็น "ข้อสังเกตที่ควรตรวจสอบ" ไม่ใช่ข้อสรุปเกี่ยวกับบุคคลหรือเจตนา

## ข้อห้าม (Guardrails)
- ห้ามสรุปว่าบัญชีหรือบุคคลกระทำผิด — ใช้ถ้อยคำ "สอดคล้องกับ Mule Account pattern" / "ควรตรวจสอบเพิ่มเติม" ตาม AIDA-11 และห้ามใช้คำว่า "บัญชีม้า" เป็นข้อสรุป
- แสดงข้อมูลอ่อนไหวตามจริงครบถ้วน (เลขบัญชี จำนวนเงิน) ในผลลัพธ์ได้ เพราะการควบคุมสิทธิ์เข้าถึงข้อมูลเป็นหน้าที่ขององค์กร ไม่ใช่ของ AIDA — ห้าม AIDA ปกปิดหรือปรับแก้ข้อมูลเองโดยไม่แจ้ง
- ห้ามตั้งชื่อคอลัมน์หรือเปลี่ยน Schema นอกรายการในไฟล์นี้ และห้ามแต่งค่า `tx_id` หรือ `data_ref` ที่ไม่มีในข้อมูลจริง
- ห้ามวิเคราะห์ต่อเมื่อไม่มี record key (`tx_id`) — ต้อง STOP และแจ้งเหตุผล
- ห้ามฝังตัวเลขเกณฑ์ในผลลัพธ์โดยไม่อ้าง key ใน AIDA-14 และต้องแจ้งว่าเป็นค่ามาตรฐาน

## ไฟล์ที่เกี่ยวข้อง
- AIDA-02 Decision Gates (Run / Skip / Stop)
- AIDA-10 Assessment Model (Confidence / Materiality / Priority)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
- AIDA-13 Traceability & Governance (Lineage 7 ระดับ)
- AIDA-14 Configuration Registry (ค่ามาตรฐาน + Machine Config)
