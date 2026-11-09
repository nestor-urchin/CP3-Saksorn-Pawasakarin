# AIDA-17 · บทบาทคอลัมน์และ Schema (Phase C2)
> ไฟล์: AIDA-17 | เวอร์ชัน: 3.1 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: บทบาทคอลัมน์ 14 บทบาทมีอะไรบ้างและเพิ่มบทบาทเองได้ไหม, preset ข้อมูล E/C/A/L/F จับคู่คอลัมน์อย่างไร, บทบาทเดียวกันหมายถึงอะไรในข้อมูลประกันชีวิตและกองทุน (เช่น limit = มูลค่าเวนคืน), ตารางเหตุการณ์ (event table) คืออะไร, รหัสประเภทรายการ (`code_values`) ยืนยันอย่างไรและค่าเริ่มต้นคืออะไร, ชื่อคอลัมน์ภาษาไทย/อังกฤษแบบใดที่ engine รู้จัก, Evidence / Finding / Exploratory / Data Dictionary / Data Request / Run Log มีคอลัมน์อะไร, Workbook / CSV / Dashboard มีอะไรบ้าง, Data Reference เขียนอย่างไร

## สรุปสั้น
ตั้งแต่ C1 การ์ดรับรองทำงานตาม **บทบาทคอลัมน์ (role)** ไม่ใช่ชื่อคอลัมน์ ผู้ตรวจสอบยืนยันบทบาทของทุกคอลัมน์ที่ Intake Review (ข้อ A, AIDA-19) แล้ว engine แปลงเป็นคอลัมน์ภายในก่อนวิเคราะห์
มี **14 บทบาทคงที่** + บทบาทที่ผู้ตรวจสอบตั้งเอง `custom:<ชื่อ>` ไม่จำกัดจำนวน (การ์ดรับรองไม่อ่าน custom แต่โหมดสำรวจใช้ได้ และส่งต่อไปใน Evidence / Workbook)
Preset และพจนานุกรมชื่อคอลัมน์ใช้ **เสนอ** บทบาทเท่านั้น — ผู้ตรวจสอบยืนยันเสมอ ชื่อที่ไม่สื่อความหมาย engine ตอบ "ไม่ทราบ" (ไม่เดามั่ว)
C2 เพิ่มข้อมูล **L ประกันชีวิต** และ **F กองทุนรวม** โดย **ไม่เพิ่มบทบาทใหม่** — ใช้ 14 บทบาทเดิม และ Intake Review แสดงความหมายของบทบาทตามประเภทข้อมูลไว้ข้างชื่อบทบาท (ข้อ 2.1) การ์ดที่แยกตามประเภทรายการอ่านความหมายของรหัสที่ผู้ตรวจสอบยืนยัน (`code_values`, ข้อ 2.3)
ทุก Evidence ย้อนกลับไปยังรายการต้นทางได้ผ่าน `record_refs` + `data_ref` (AIDA-13) และบันทึก Registry version (AIDA-14)

## 1. บทบาทคอลัมน์ 14 บทบาท
| บทบาท | ความหมาย | คอลัมน์ภายใน engine |
|---|---|---|
| `record_id` | รหัสรายการ (**บังคับ**; ไม่มีหรือซ้ำ → STOP) | tx_id |
| `date` | วันเวลารายการ | ts |
| `amount` | ยอดเงิน | amount |
| `entity` | ผู้ทำรายการหลัก (บัญชีต้นทาง, ผู้กู้, ผู้ขาย, ผู้เอาประกัน, ผู้ถือหน่วย) | from_acct |
| `counterparty` | คู่รายการ (บัญชีปลายทาง, ผู้ชำระแทน, ผู้รับเงิน / ผู้รับผลประโยชน์, บัญชีชำระ/รับเงิน) | to_acct |
| `contract` | สัญญา / กรมธรรม์ / บัตร / ใบสั่งซื้อ / กองทุน | contract |
| `category` | หมวด / ประเภทรายการ (รหัสยืนยันใน `code_values`) | category |
| `channel` | ช่องทาง / สาขา / ตัวแทนขาย | channel |
| `created_by` | ผู้บันทึก | created_by |
| `approved_by` | ผู้อนุมัติ | approved_by |
| `document_no` | เลขเอกสาร (เช่น เลขที่ใบแจ้งหนี้) | document_no |
| `limit` | วงเงิน / ค่างวด / มูลค่าเวนคืน (L) | limit |
| `due_date` | วันครบกำหนด / วันที่ได้ราคา NAV (F) | due_date |
| `opened_at` | วันเปิดบัญชี/สัญญา/วันออกกรมธรรม์ (ตาราง master) | opened_at |

- **ตารางรอง** (master บัญชี, ตารางสัญญา): คอลัมน์รหัสใช้บทบาท `entity` (กลายเป็น acct_id) และเชื่อมกับตารางธุรกรรมด้วยรหัสนั้น — Intake Review แสดง % ของรหัสที่เชื่อมได้ ต่ำกว่า `INTAKE.JOIN_MIN_PCT` (AIDA-14) ความพร้อมเป็น "บางส่วน"
- **ตารางเหตุการณ์ (event table, ข้อมูล L / F)**: ตารางรองอีก 1 ตารางที่มีบทบาท `record_id`, `date` และ `contract` ของตัวเอง แยกจากตารางธุรกรรม เช่น ประวัติการเปลี่ยนผู้รับผลประโยชน์ (change_id → record_id, policy_no → contract, change_date → date, beneficiary → counterparty) engine ใช้ชื่อคอลัมน์ภายในเดียวกับตารางธุรกรรม และเชื่อมกับตารางธุรกรรมด้วย `contract` — Intake Review ข้อ A แสดงชื่อตารางเหตุการณ์และ % ของเลขที่กรมธรรม์ที่เชื่อมได้ (ต่ำกว่า `INTAKE.JOIN_MIN_PCT` ความพร้อมเป็น "บางส่วน") ผู้ตรวจสอบยืนยันหรือแก้บทบาทได้ที่ข้อ A; ตารางที่เข้าเงื่อนไขมีได้ **1 ตารางต่อการวิเคราะห์** (2 ตาราง → ข้อความแนะนำให้เลือกหรือรวมตาราง)
- **custom**: ใส่ในคำตอบ `confirm` เป็น `"custom:status"` หรือคู่กับบทบาทรับรองเป็น list เช่น `["entity", "custom:vendor_name"]`; `"ไม่ใช้"` = ไม่นำคอลัมน์นั้นเข้า engine
- บทบาทเดียวกันใช้ได้กับคอลัมน์เดียวต่อตาราง (ยกเว้น custom)

## 2. Preset ตามประเภทข้อมูล (ใช้เสนอบทบาทเท่านั้น)
| ประเภท | ชื่อคอลัมน์มาตรฐาน → บทบาท |
|---|---|
| E โอนเงินระหว่างบัญชี | tx_id → record_id, ts → date, from_acct → entity, to_acct → counterparty, amount → amount, channel → channel, acct_id → entity (ตาราง accounts), opened_at → opened_at |
| C รับชำระค่างวดสินเชื่อ | payment_id → record_id, pay_date → date, pay_amount → amount, borrower_id → entity, payer_id → counterparty, contract_id → contract, due_date → due_date, installment_amount → limit, channel, category, status → custom:status, opened_at → opened_at |
| A จ่ายเงินเจ้าหนี้ | payment_id → record_id, pay_date → date, amount → amount, vendor_id → entity, invoice_no → document_no, created_by, approved_by, approval_limit → limit, category, channel, po_no → contract |
| L ประกันชีวิต (L3: เวนคืน กู้ตามกรมธรรม์ เปลี่ยนผู้รับผลประโยชน์) | **รายการกรมธรรม์** (บังคับ): txn_id → record_id, policy_no → contract, insured_id → entity, txn_date → date, txn_type → category, amount → amount, payee → counterparty, cash_value → limit, staff_id → created_by · **ตารางกรมธรรม์** (แนะนำ; L-R1 ต้องใช้): policy_no → contract, insured_id → entity, issue_date → opened_at, premium_mode → category (เบี้ยเดียว / เป็นงวด) · **ประวัติเปลี่ยนผู้รับผลประโยชน์** = ตารางเหตุการณ์ (แนะนำ; L-R2, L-R5 ต้องใช้): change_id → record_id, policy_no → contract, change_date → date, beneficiary → counterparty |
| F ธุรกรรมกองทุนรวมของผู้ถือหน่วย (F1: ซื้อ ขายคืน สับเปลี่ยน) | **คำสั่งซื้อขาย** (บังคับ): order_id → record_id, unitholder_id → entity, fund_code → contract, order_datetime → date (ควรมีเวลา), txn_type → category, amount → amount, bank_account → counterparty, agent → channel, nav_date → due_date · **ตารางผู้ถือหน่วย** (ไม่บังคับ): unitholder_id → entity, open_date → opened_at |

- engine ตรวจประเภทข้อมูลจากชื่อคอลัมน์เฉพาะของประเภท (เช่น policy_no, insured_id, cash_value สำหรับ L; unitholder_id, fund_code, nav_date สำหรับ F) ที่ถูกเสนอบทบาทแล้ว และแสดงว่าตรวจพบจากคอลัมน์ใดในบรรทัด "ประเภทข้อมูลที่ตรวจพบ"
- ชื่อคอลัมน์ที่ไม่สื่อความหมาย (เช่น COL1, COL2, TP) ตรวจประเภทไม่ได้ → ผู้ตรวจสอบระบุ `dataset_type` (E, C, A, L, F) ในคำตอบ confirm ค่าที่ยืนยันใช้แทนผลตรวจตลอดการรัน (AIDA-19)
- ข้อมูลประเภทที่ยังไม่มีการ์ดเฉพาะ (L1 เบี้ยประกัน, L2 สินไหม/เคลม, F2 พอร์ตลงทุนขององค์กร, บัตรเครดิต, มูลนิธิ, สหกรณ์ — เฟสถัดไป) ยังไม่มี preset: engine เสนอบทบาทจากพจนานุกรมและ profile แล้วใช้การ์ดทั่วไปที่บทบาทพอ + โหมดสำรวจ

### 2.1 ความหมายของบทบาทตามประเภทข้อมูล (`ROLE_MEANING_BY_TYPE`)
บทบาทเดิมบางบทบาทมีความหมายเฉพาะในข้อมูล L / F — Intake Review ข้อ A แสดงความหมายนี้ในวงเล็บต่อจากชื่อบทบาท เช่น `policy_txn.cash_value → limit (มูลค่าเวนคืน)` เพื่อไม่ให้สับสนกับวงเงิน
| บทบาท | L ประกันชีวิต | F กองทุนรวม |
|---|---|---|
| record_id | รหัสรายการกรมธรรม์ | รหัสคำสั่งซื้อขาย |
| date | วันที่ทำรายการ | วันเวลาที่ทำคำสั่ง |
| entity | ผู้เอาประกัน | ผู้ถือหน่วย |
| contract | เลขที่กรมธรรม์ | กองทุน |
| category | ประเภทรายการ (เช่น เวนคืน กู้ เคลม) หรือลักษณะการชำระเบี้ย | ประเภทรายการ (ซื้อ ขาย สับเปลี่ยน) |
| counterparty | ผู้รับเงิน / ผู้รับผลประโยชน์ | บัญชีชำระ/รับเงิน |
| limit | **มูลค่าเวนคืน** | — |
| due_date | — | **วันที่ได้ราคา NAV** |
| channel | — | ตัวแทนขาย |
| created_by | ตัวแทนหรือพนักงานที่ทำรายการ | — |
| opened_at | วันออกกรมธรรม์ | วันเปิดบัญชีผู้ถือหน่วย |

### 2.2 ชื่อที่ใช้ใน Finding (entity_type)
- L: policy (กรมธรรม์), insured (ผู้เอาประกัน), payee (ผู้รับเงิน), beneficiary (ผู้รับผลประโยชน์), staff (ตัวแทน/พนักงาน)
- F: unitholder (ผู้ถือหน่วย), fund (กองทุน), account (บัญชีชำระ/รับเงิน), agent (ตัวแทนขาย)

### 2.3 รหัสประเภทรายการ (`code_values`)
การ์ด L / F ที่แยกตามประเภทรายการ (เวนคืน กู้ เคลม เปลี่ยนผู้รับผลประโยชน์ / ซื้อ ขาย สับเปลี่ยน) อ่านความหมายของรหัสที่ **ผู้ตรวจสอบยืนยัน** ใน Intake Review เท่านั้น
- รูปแบบ: `{"<ตาราง>.<คอลัมน์>": {"<รหัส>": "<ความหมาย>"}}` เช่น `{"policy_txn.txn_type": {"SURR": "เวนคืนกรมธรรม์", "LOAN": "กู้ยืมตามกรมธรรม์", "CLM": "จ่ายสินไหม"}}` — key เป็นชื่อตารางจุดชื่อคอลัมน์ที่มีบทบาท category ของตารางธุรกรรม
- inspect เสนอ `code_values` จากคำอธิบายคอลัมน์ในหนังสือ (รูปแบบ "SURR = เวนคืน, LOAN = กู้") ผู้ตรวจสอบแก้หรือเพิ่มได้ด้วย `answers["code_values"]` (AIDA-19)
- engine แปลข้อความความหมาย (ไทยหรืออังกฤษ) เป็นความหมายภายใน (`CODE_MEANINGS`) และ Intake Review ข้อ A แสดงผลด้วย `→` เช่น `SURR = เวนคืนกรมธรรม์ → surrender`
  - L: `surrender` (เวนคืน), `loan` (กู้ตามกรมธรรม์), `claim` (เคลม/สินไหม), `benefit_change` (เปลี่ยนผู้รับผลประโยชน์)
  - F: `buy` (ซื้อ), `sell` (ขาย/ขายคืน/ไถ่ถอน), `switch_in` (สับเปลี่ยนเข้า), `switch_out` (สับเปลี่ยนออก)
  - ความหมายที่เป็นการชำระคืนเงินกู้ ดอกเบี้ย หรือการยกเลิกคำสั่ง ไม่ถูกนับเป็นประเภทใดข้างต้น
- ❓ ในข้อ A มี 2 กรณี: (1) ยังไม่มี `code_values` ของคอลัมน์ประเภทรายการ → "ค่ารหัสของ … ยังไม่ได้ยืนยันความหมาย" พร้อมค่าที่พบบ่อย (2) ยืนยันแล้วแต่บางรหัสแปลความหมายไม่ได้ → `รหัส = ข้อความ → ❓ จับคู่ความหมายไม่ได้ — ระบุใหม่`
- **รหัสเริ่มต้นของ preset** (ใช้เพื่อเสนอเท่านั้น): L: SURR, LOAN, CLAIM, BENCHG · F: BUY, SELL, SWIN, SWOUT — ถ้ายังไม่ยืนยัน การ์ดที่ต้องใช้ประเภทรายการ **ข้าม (Skip) พร้อมเหตุผลภาษาไทย** ว่ายังไม่ได้ยืนยันความหมายรหัสใด ไม่รันด้วยค่าเริ่มต้นโดยไม่บอก
- ตารางเหตุการณ์ (ประวัติเปลี่ยนผู้รับผลประโยชน์) ไม่ต้องมีรหัส `benefit_change` เพราะทุกแถวเป็นการเปลี่ยนผู้รับผลประโยชน์อยู่แล้ว
- `code_values` บันทึกใน Data Dictionary และ mapping profile เพื่อใช้ซ้ำรอบถัดไป

## 3. พจนานุกรมชื่อคอลัมน์ (ตัวอย่าง; เทียบแบบไม่สนตัวพิมพ์ ช่องว่าง และ _ -)
| บทบาท | ภาษาอังกฤษ / รหัสย่อ | ภาษาไทย |
|---|---|---|
| record_id | id, txid, txnid, transactionid, paymentid, recordid, trnno, orderid, changeid | รหัสรายการ, เลขที่รายการ, รหัสธุรกรรม, เลขที่รายการจ่าย, รหัสคำสั่ง |
| date | date, ts, timestamp, txdate, trndt, paydate, postingdate, orderdatetime, changedate | วันที่, วันเวลา, วันที่ทำรายการ, วันที่ชำระ, วันที่จ่ายเงิน, วันที่เปลี่ยนผู้รับผลประโยชน์ |
| amount | amount, amt, value, txamt, trnamt, payamount, netamount | ยอดเงิน, จำนวนเงิน, ยอด, ยอดสุทธิ, ยอดชำระ, มูลค่า |
| entity | fromacct, sender, borrowerid, customerid, vendorid, supplierid, accountid, insuredid, unitholderid | บัญชีต้นทาง, ผู้โอน, ผู้กู้, ลูกค้า, ผู้ขาย, เลขที่บัญชี, เจ้าหนี้, ผู้เอาประกัน, ผู้ถือหน่วย |
| counterparty | toacct, receiver, beneficiary, payerid, payor, counterparty, cpty, bankaccount | บัญชีปลายทาง, ผู้รับ, ผู้รับโอน, ผู้ชำระ, คู่ค้า, ผู้รับเงิน, ผู้รับผลประโยชน์, บัญชีรับเงิน |
| contract | contractid, loanid, policyno, cardno, fundcode | สัญญา, เลขที่สัญญา, กรมธรรม์, เลขที่กรมธรรม์, บัตร, กองทุน, รหัสกองทุน |
| category / channel | category, txtype, txntype, glcode, premiummode / channel, branch, brcd, agent | หมวด, ประเภทรายการ, วิธีชำระเบี้ย / ช่องทาง, สาขา, ตัวแทนขาย |
| created_by / approved_by | createdby, maker, preparedby, staffid / approvedby, approver, checker | ผู้บันทึก, ผู้จัดทำ, รหัสพนักงาน / ผู้อนุมัติ |
| document_no | invoiceno, docno, refno, receiptno | เลขที่เอกสาร, เลขที่ใบแจ้งหนี้, เลขอ้างอิง |
| limit | limit, creditlimit, approvallimit, installmentamount, cashvalue, surrendervalue | วงเงิน, วงเงินอนุมัติ, ค่างวด, มูลค่าเวนคืน |
| due_date / opened_at | duedate, maturitydate, navdate / openedat, opendate, issuedate | วันครบกำหนด, กำหนดชำระ, วันที่ได้ราคา NAV / วันเปิดบัญชี, วันที่ทำสัญญา, วันออกกรมธรรม์ |

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

- **entity_type ของ Finding** ใช้ชื่อตามประเภทข้อมูล: C → borrower (ผู้กู้), payer (ผู้ชำระ), contract (สัญญา); A → vendor (ผู้ขาย), payee, document (เลขที่เอกสาร), user (ผู้ใช้ที่บันทึก/อนุมัติ); E → account, network; L / F → ข้อ 2.2
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
- ห้ามเดาความหมายของรหัสประเภทรายการแทนผู้ตรวจสอบ — รหัสที่ยังไม่ยืนยันต้องถาม ❓ และการ์ดที่ใช้รหัสนั้นข้ามพร้อมเหตุผล
- ห้ามแต่ง record_id หรือ data_ref ที่ไม่มีในข้อมูลจริง และห้ามวิเคราะห์ต่อเมื่อไม่มี record_id (STOP)
- แสดงข้อมูลเต็มตามที่องค์กรตัดสินใจ พร้อมป้ายเตือน — ห้ามปกปิดหรือแก้ข้อมูลเองโดยไม่แจ้ง

## ไฟล์ที่เกี่ยวข้อง
- AIDA-18 Risk Library และบทบาทที่การ์ดแต่ละใบต้องใช้ (รวม L-R1–L-R6, F-R1–F-R6)
- AIDA-19 วิธีเรียก engine และ Intake Review
- AIDA-10 Assessment Model (Confidence / Materiality / Priority)
- AIDA-13 Traceability (Lineage, Data Reference)
- AIDA-14 Configuration Registry
