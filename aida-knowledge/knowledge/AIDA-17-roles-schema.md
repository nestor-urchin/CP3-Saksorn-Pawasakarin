# AIDA-17 · บทบาทคอลัมน์และ Schema (Phase C1)
> ไฟล์: AIDA-17 | เวอร์ชัน: 3.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: บทบาทคอลัมน์ 14 บทบาทมีอะไรบ้างและเพิ่มบทบาทเองได้ไหม, preset ข้อมูล E/C/A จับคู่คอลัมน์อย่างไร, ชื่อคอลัมน์ภาษาไทย/อังกฤษแบบใดที่ engine รู้จัก, Evidence / Finding / Exploratory / Data Dictionary / Data Request / Run Log มีคอลัมน์อะไร, Workbook / CSV / Dashboard มีอะไรบ้าง, Data Reference เขียนอย่างไร

## สรุปสั้น
ใน C1 การ์ดรับรองทำงานตาม **บทบาทคอลัมน์ (role)** ไม่ใช่ชื่อคอลัมน์ ผู้ตรวจสอบยืนยันบทบาทของทุกคอลัมน์ที่ Intake Review (ข้อ A, AIDA-19) แล้ว engine แปลงเป็นคอลัมน์ภายในก่อนวิเคราะห์
มี **14 บทบาทคงที่** + บทบาทที่ผู้ตรวจสอบตั้งเอง `custom:<ชื่อ>` ไม่จำกัดจำนวน (การ์ดรับรองไม่อ่าน custom แต่โหมดสำรวจใช้ได้ และส่งต่อไปใน Evidence / Workbook)
Preset และพจนานุกรมชื่อคอลัมน์ใช้ **เสนอ** บทบาทเท่านั้น — ผู้ตรวจสอบยืนยันเสมอ ชื่อที่ไม่สื่อความหมาย engine ตอบ "ไม่ทราบ" (ไม่เดามั่ว)
ทุก Evidence ย้อนกลับไปยังรายการต้นทางได้ผ่าน `record_refs` + `data_ref` (AIDA-13) และบันทึก Registry version (AIDA-14)

## 1. บทบาทคอลัมน์ 14 บทบาท
| บทบาท | ความหมาย | คอลัมน์ภายใน engine |
|---|---|---|
| `record_id` | รหัสรายการ (**บังคับ**; ไม่มีหรือซ้ำ → STOP) | tx_id |
| `date` | วันเวลารายการ | ts |
| `amount` | ยอดเงิน | amount |
| `entity` | ผู้ทำรายการหลัก (บัญชีต้นทาง, ผู้กู้, ผู้ขาย) | from_acct |
| `counterparty` | คู่รายการ (บัญชีปลายทาง, ผู้ชำระแทน) | to_acct |
| `contract` | สัญญา / กรมธรรม์ / บัตร / ใบสั่งซื้อ | contract |
| `category` | หมวด | category |
| `channel` | ช่องทาง / สาขา | channel |
| `created_by` | ผู้บันทึก | created_by |
| `approved_by` | ผู้อนุมัติ | approved_by |
| `document_no` | เลขเอกสาร (เช่น เลขที่ใบแจ้งหนี้) | document_no |
| `limit` | วงเงิน / ค่างวด | limit |
| `due_date` | วันครบกำหนด | due_date |
| `opened_at` | วันเปิดบัญชี/สัญญา (ตาราง master) | opened_at |

- **ตารางรอง** (master บัญชี, ตารางสัญญา): คอลัมน์รหัสใช้บทบาท `entity` (กลายเป็น acct_id) และเชื่อมกับตารางธุรกรรมด้วยรหัสนั้น — Intake Review แสดง % ของรหัสที่เชื่อมได้ ต่ำกว่า `INTAKE.JOIN_MIN_PCT` (AIDA-14) ความพร้อมเป็น "บางส่วน"
- **custom**: ใส่ในคำตอบ `confirm` เป็น `"custom:status"` หรือคู่กับบทบาทรับรองเป็น list เช่น `["entity", "custom:vendor_name"]`; `"ไม่ใช้"` = ไม่นำคอลัมน์นั้นเข้า engine
- บทบาทเดียวกันใช้ได้กับคอลัมน์เดียวต่อตาราง (ยกเว้น custom)

## 2. Preset ตามประเภทข้อมูล (ใช้เสนอบทบาทเท่านั้น)
| ประเภท | ชื่อคอลัมน์มาตรฐาน → บทบาท |
|---|---|
| E โอนเงินระหว่างบัญชี | tx_id → record_id, ts → date, from_acct → entity, to_acct → counterparty, amount → amount, channel → channel, acct_id → entity (ตาราง accounts), opened_at → opened_at |
| C รับชำระค่างวดสินเชื่อ | payment_id → record_id, pay_date → date, pay_amount → amount, borrower_id → entity, payer_id → counterparty, contract_id → contract, due_date → due_date, installment_amount → limit, channel, category, status → custom:status, opened_at → opened_at |
| A จ่ายเงินเจ้าหนี้ | payment_id → record_id, pay_date → date, amount → amount, vendor_id → entity, invoice_no → document_no, created_by, approved_by, approval_limit → limit, category, channel, po_no → contract |

ข้อมูลประเภทอื่น (บัตรเครดิต, ประกันชีวิต — C2; กองทุน/การลงทุน, มูลนิธิ, สหกรณ์ — C3) ยังไม่มี preset: engine เสนอบทบาทจากพจนานุกรมและ profile แล้วใช้การ์ดทั่วไปที่บทบาทพอ + โหมดสำรวจ

## 3. พจนานุกรมชื่อคอลัมน์ (ตัวอย่าง; เทียบแบบไม่สนตัวพิมพ์ ช่องว่าง และ _ -)
| บทบาท | ภาษาอังกฤษ / รหัสย่อ | ภาษาไทย |
|---|---|---|
| record_id | id, txid, txnid, transactionid, paymentid, recordid, trnno | รหัสรายการ, เลขที่รายการ, รหัสธุรกรรม, เลขที่รายการจ่าย |
| date | date, ts, timestamp, txdate, trndt, paydate, postingdate | วันที่, วันเวลา, วันที่ทำรายการ, วันที่ชำระ, วันที่จ่ายเงิน |
| amount | amount, amt, value, txamt, trnamt, payamount, netamount | ยอดเงิน, จำนวนเงิน, ยอด, ยอดสุทธิ, ยอดชำระ, มูลค่า |
| entity | fromacct, sender, borrowerid, customerid, vendorid, supplierid, accountid | บัญชีต้นทาง, ผู้โอน, ผู้กู้, ลูกค้า, ผู้ขาย, เลขที่บัญชี, เจ้าหนี้ |
| counterparty | toacct, receiver, beneficiary, payerid, payor, counterparty, cpty | บัญชีปลายทาง, ผู้รับ, ผู้รับโอน, ผู้ชำระ, คู่ค้า |
| contract | contractid, loanid, policyno, cardno | สัญญา, เลขที่สัญญา, กรมธรรม์, บัตร |
| category / channel | category, txtype, glcode / channel, branch, brcd | หมวด, ประเภทรายการ / ช่องทาง, สาขา |
| created_by / approved_by | createdby, maker, preparedby / approvedby, approver, checker | ผู้บันทึก, ผู้จัดทำ / ผู้อนุมัติ |
| document_no | invoiceno, docno, refno, receiptno | เลขที่เอกสาร, เลขที่ใบแจ้งหนี้, เลขอ้างอิง |
| limit | limit, creditlimit, approvallimit, installmentamount | วงเงิน, วงเงินอนุมัติ, ค่างวด |
| due_date / opened_at | duedate, maturitydate / openedat, opendate | วันครบกำหนด, กำหนดชำระ / วันเปิดบัญชี, วันที่ทำสัญญา |

รายการเต็มอยู่ใน `ROLE_SYNONYMS` ของ engine; คำอธิบายคอลัมน์ของผู้ตรวจสอบมีน้ำหนักมากกว่าชื่อคอลัมน์ และคำอธิบายที่ขัดกับข้อมูล (เช่น "ยอดสุทธิ" แต่มีค่าติดลบ) แสดงเป็น ⚠️

## 4. Schema ของผลลัพธ์
| Schema | คอลัมน์ |
|---|---|
| Evidence | evidence_id, run_id, recipe_id (รหัสการ์ด), recipe_version, skill_family, entity_type, entity_id, risk, period (YYYY-MM), metric, value, threshold, registry_key, registry_version, explanation, record_refs (list ของ record_id), data_ref |
| Finding | finding_id, entity_type, entity_id, risk, period, evidence_ids, skill_families, exposure, confidence, materiality, priority, review_status, review_reason, network_id + source, source_label, explore_id, reviewer, promote_reason, promoted_at |
| Exploratory | explore_id, question, code (โค้ดเต็ม), result_summary, note, time, promoted, promoted_by, promote_reason, promoted_finding |
| Data Dictionary | table, column, meaning, role, code_values, confirmed_by, confirmed_at |
| Data Request | no, risk_id, request |
| Intake Review (sheet) | section, item, detail |
| Mule Network (E) | network_id, member_accts, roles (mule / collector / feeder), internal_tx_count, internal_amount, period_start, period_end |
| Money Flow trail (E) | trace_id, start_acct, direction, hop, from_acct, to_acct, amount, ts, tx_id |
| Run Log | run_id, timestamp, stage (1–18), status (OK / STOP / SKIP / REVIEW), detail, recipe_id, recipe_version, registry_version, pack_version, input_sha256 |

- **entity_type ของ Finding** ใช้ชื่อตามประเภทข้อมูล: C → borrower (ผู้กู้), payer (ผู้ชำระ), contract (สัญญา); A → vendor (ผู้ขาย), payee, document (เลขที่เอกสาร), user (ผู้ใช้ที่บันทึก/อนุมัติ); E → account, network
- Finding จากการ์ดรับรองมี `source = "card"`; Finding ที่เลื่อนจากโหมดสำรวจมี `source = "exploratory"`, ป้าย "จากโหมดสำรวจ" ถาวร, `reviewer` บังคับ และ Confidence ไม่เกิน "กลาง"
- `exposure` คือยอดเงินที่เกี่ยวข้อง ใช้คำนวณ Materiality ตาม AIDA-10 — ห้ามใช้คะแนน/จำนวนสัญญาณเป็น Materiality
- Money Flow trail เป็นเส้นทางเงินเพื่อการสอบสวน ไม่ใช่ Evidence และไม่นับเป็น Finding

## 5. Data Reference
- engine คำนวณ sha256 ของทุกไฟล์และเขียน `data_ref` เอง: `chat:<ชื่อไฟล์>#<ตาราง>|sha256:<hash>` (หลายตารางคั่นด้วย "; ") — AIDA ไม่แต่งค่าเอง
- `run()` อ่านไฟล์ใหม่และเทียบ sha256 กับตอนยืนยัน ไฟล์เปลี่ยน → คำเตือนภาษาไทยใน `warnings` และ Run Log (ถือเป็นข้อมูลชุดใหม่)

## 6. Output (สร้างโดย `run()`)
| ไฟล์ | เนื้อหา |
|---|---|
| `AIDA-workbook.xlsx` | sheet ตามลำดับ: README, Intake_Review, Data_Dictionary, Data_Request, Dataset_Profile, Analysis_Plan, Evidence, Findings, Exploratory, Mule_Networks, Money_Flow, Materiality, Run_Log (ข้อมูลที่ไม่ใช่ E: Mule_Networks / Money_Flow ระบุว่าไม่เกี่ยวข้อง) |
| `network/nodes.csv`, `edges.csv`, `flows.csv` (เฉพาะข้อมูล E) | nodes: node_id, role, network_id, finding_ids · edges: source, target, amount, ts, tx_id, network_id · flows: Money Flow trail |
| `AIDA-dashboard.html` | ไฟล์เดียว ไม่โหลดสิ่งใดจากภายนอก: แท็บ สรุป · Intake · Findings (ป้าย "จากโหมดสำรวจ" บน Finding ที่เลื่อนมา) · Mule Networks · Money Flow (สองแท็บหลังเฉพาะข้อมูล E) · Run Log |

- ทุก output มีป้ายเตือน: "ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป"
- ข้อความที่ขึ้นต้นด้วย = + - @ ถูกเติม `'` ข้างหน้า (กันสูตร) และ template Dashboard อยู่ภายใน engine (ไม่ต้องดึงจาก Knowledge)
- Findings sheet มีคอลัมน์ว่าง reviewer, disposition, review_date ให้ผู้ตรวจสอบกรอกหลัง Human Review

## ข้อห้าม (Guardrails)
- ห้ามสรุปว่าบัญชีหรือบุคคลกระทำผิด — ใช้ "สอดคล้องกับ … pattern" / "ควรตรวจสอบเพิ่มเติม" (AIDA-11) และห้ามใช้คำว่า "บัญชีม้า"
- ห้ามกำหนดบทบาทแทนผู้ตรวจสอบโดยไม่ผ่าน Intake Review และห้ามเดาความหมายของคอลัมน์ที่ engine ตอบ "ไม่ทราบ"
- ห้ามแต่ง record_id หรือ data_ref ที่ไม่มีในข้อมูลจริง และห้ามวิเคราะห์ต่อเมื่อไม่มี record_id (STOP)
- แสดงข้อมูลเต็มตามที่องค์กรตัดสินใจ พร้อมป้ายเตือน — ห้ามปกปิดหรือแก้ข้อมูลเองโดยไม่แจ้ง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-18 Risk Library และบทบาทที่การ์ดแต่ละใบต้องใช้
- AIDA-19 วิธีเรียก engine และ Intake Review
- AIDA-10 Assessment Model (Confidence / Materiality / Priority)
- AIDA-13 Traceability (Lineage, Data Reference)
- AIDA-14 Configuration Registry
