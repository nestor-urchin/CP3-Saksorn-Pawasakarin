# AIDA Phase C2: Life Insurance (L3) and Fund Investor Transactions (F1). Design Spec

- **Date:** 2026-11-09
- **Status:** approved in conversation, sections 1–3
- **Builds on:** `docs/superpowers/specs/2026-11-06-aida-c1-generic-engine-design.md` (C1, engine v3.0.0). Everything in C1 stays unless this spec changes it.

## 1. Goal

Add certified checks for two new data types:
- **L, life insurance, set L3:** surrender, policy loans and beneficiary changes
- **F, funds, set F1:** investor transactions (buy, redeem, switch)

The C1 approach is unchanged: 14 roles, Intake Review, sufficiency assessment, exploratory mode and general cards.

### Roadmap
| Phase | Scope |
|---|---|
| C1 (done) | E transfers, C loans and instalments, A vendor payments |
| **C2 (this spec)** | **L3 life insurance (surrender / loans / beneficiary changes)** and **F1 fund investor transactions** |
| Later | L1 premiums, L2 claims, F2 organisational portfolios (need market prices), credit cards, foundations, cooperatives |

Until each later phase ships, its data types use the general cards plus exploratory mode.

### Agreements
| Topic | Agreement |
|---|---|
| Roles | **The 14 C1 roles, unchanged.** No new standard roles. Each type's meaning is given through presets and Thai role descriptions (§4.1, §5.1). |
| Transaction type | Use `category`. The auditor confirms the meaning of each code in the Intake Review. |
| Delivery | **Extend the existing `aida_engine.py`** (one file). Do not split it into a second module. |
| Thresholds | Default values go in AIDA-14 v1.3 with source "แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ" (common practice; no official standard). Organisations may override them. |
| Risk IDs | `L-R1`–`L-R6` and `F-R1`–`F-R6` (§4.2, §5.2) |
| Versions | `__version__ = "3.1.0"`, `REGISTRY_VERSION = "1.3"`, zip `AIDA-Knowledge-Pack-v3.1.zip` |
| Knowledge | Still exactly 20 files. Instructions ≤ 8,000 characters. |

### Success criteria
1. Samples L and F produce Findings that match the answer key, including the realistic path (brief → inspect → "ยืนยัน" → run).
2. The three column-name variants (en / th / legacy) give the same Findings for L and F.
3. Samples E, C and A give the same results as C1. Their answer keys must not change.
4. The tests pass on pandas 3 and 1.5.3. The validator passes. inspect ≤ 30 s and run ≤ 90 s on 80k rows.
5. The Copilot eval Q48–Q57 passes.

---

## 2. Engine changes shared by L and F

- **Data types.** Add `"L"` and `"F"` to `detect_dataset_type`, `PRESETS`, every `data_types` list that belongs to the general cards (STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, GEN-CONC, GEN-PERIOD-END, FOR-*), and the `ENTITY_LABELS` per type:
  - L: policy / insured / payee / beneficiary / staff
  - F: unitholder / fund / account / agent
- **Secondary event table.** `to_internal` currently accepts one transaction table plus one master table. Add support for at most one **event table**, keyed as `"events"` and holding internal columns.
  - The adapter identifies it as a table whose `record_id` and `date` roles are separate from the main table's, and which joins to the main table via `contract`.
  - In L it holds beneficiary changes.
  - The table's join rate with the main table (via `contract`) is reported in the profile and used in sufficiency. A rate below `INTAKE.JOIN_MIN_PCT` gives 🟡, as in C1.
  - An auditor can confirm which table is the event table in the Intake Review.
- **Role descriptions by data type.** Intake Review section A shows a role's type-specific meaning next to the role name (from `ROLE_MEANING_BY_TYPE`). Examples:
  - L: `limit` = มูลค่าเวนคืน (surrender value)
  - F: `due_date` = วันที่ได้ราคา NAV (NAV date)
- **Category codes.** A check that filters by type reads the code meanings confirmed in intake. These come from `code_values` = {`table.column`: {code: meaning}}, a structure that already exists in C1 (inspect proposes it from the brief, and `answers["code_values"]` overrides it). C2 adds a `CODE_MEANINGS` translation from the Thai or English meaning text to the internal meanings below. Each preset holds default codes.
  - L meanings: `surrender`, `loan`, `claim`, `benefit_change`
  - F meanings: `buy`, `sell`, `switch_in`, `switch_out`
  - If the code values haven't been confirmed, the check is Skipped with a Thai reason, and the Intake asks ❓.
- **Comparing identity across columns.** L-R4 and F-R2 compare `counterparty` with `entity`. If the value formats don't match on any row (for example, a national ID against a bank account number), that rule is Skipped with a reason. The "one account, many policies / unitholders" rule still runs.
- Every new check has the signature `(tables, cfg) -> DataFrame` and returns the C1 Evidence schema with `roles_used`. All thresholds come from `cfg[KEY]`. Thai wording is non-accusatory.

---

## 3. Registry AIDA-14 v1.3 (new keys)

| Key | Default value |
|---|---|
| `LIFE.EARLY_SURR.MONTHS` | 12 |
| `LIFE.BENCHG_CASH.WINDOW_DAYS` | 30 |
| `LIFE.LOAN.NEAR_PCT` | 90% |
| `LIFE.LOAN.MIN_COUNT` | 3 |
| `LIFE.LOAN.COUNT_MONTHS` | 12 |
| `LIFE.LOAN_SURR.WINDOW_DAYS` | 90 |
| `LIFE.PAYEE.MIN_POLICIES` | 3 |
| `LIFE.BENEF.MIN_POLICIES` | 3 |
| `LIFE.BENCHG.MIN_COUNT` | 2 |
| `LIFE.BENCHG.COUNT_MONTHS` | 12 |
| `FUND.ROUNDTRIP.DAYS` | 30 |
| `FUND.ROUNDTRIP.AMOUNT_BAND` | 80%–120% |
| `FUND.SHARED_ACCT.MIN_HOLDERS` | 3 |
| `FUND.FREQ.MIN_TX_MONTH` | 6 |
| `FUND.CHURN.MIN_CLIENT_SHARE` | 30% |
| `FUND.CHURN.MIN_CLIENTS` | 5 |
| `FUND.CUTOFF_TIME` | 15:30 |

- L-R6 reuses `CONC.SINGLE_ENTITY_SHARE` and `CONC.HHI` from C1.
- Every key appears in both the table and the Machine Config. The validator checks that they agree.
- Add a history row for v1.3.

---

## 4. L: life insurance (L3)

### 4.1 Tables and roles
| Table | Example columns → role | Required? |
|---|---|---|
| Policy transactions | txn_id→`record_id`, policy_no→`contract`, insured_id→`entity`, txn_date→`date`, txn_type→`category`, amount→`amount`, payee→`counterparty`, cash_value→`limit`, staff/agent→`created_by` | Required |
| Policy master | policy_no→`contract`, insured_id→`entity`, issue_date→`opened_at`, premium_mode→`category` (single premium / periodic) | Recommended (needed for L-R1) |
| Beneficiary changes (event table) | change_id→`record_id`, policy_no→`contract`, change_date→`date`, beneficiary→`counterparty` | Recommended (needed for L-R2 and L-R5) |

### 4.2 Risks and checks
| Risk | Thai name | Check | Rule |
|---|---|---|---|
| L-R1 | เวนคืนเร็วหลังทำกรมธรรม์ | `LIFE-EARLY-SURR` | A surrender within `LIFE.EARLY_SURR.MONTHS` of `opened_at`. Single-premium policies are noted in the Evidence. |
| L-R2 | เปลี่ยนผู้รับผลประโยชน์แล้วมีรายการเงินตามมาเร็ว | `LIFE-BENCHG-CASH` | A beneficiary change followed by a surrender, loan or claim on the same policy within `LIFE.BENCHG_CASH.WINDOW_DAYS` |
| L-R3 | กู้ตามกรมธรรม์ผิดปกติ | `LIFE-LOAN` | Any one of: (a) a loan ≥ `LIFE.LOAN.NEAR_PCT` of `limit`; (b) ≥ `LIFE.LOAN.MIN_COUNT` loans within `LIFE.LOAN.COUNT_MONTHS`; (c) a loan followed by a surrender within `LIFE.LOAN_SURR.WINDOW_DAYS` |
| L-R4 | จ่ายเงินเข้าบัญชีบุคคลที่สาม | `LIFE-THIRD-PAYEE` | (a) payee ≠ insured, or (b) one payee paid from ≥ `LIFE.PAYEE.MIN_POLICIES` policies of different insured. The §2 comparison rule applies. |
| L-R5 | ผู้รับผลประโยชน์ซ้ำข้ามกรมธรรม์ | `LIFE-BENEF-MULTI` | One beneficiary on ≥ `LIFE.BENEF.MIN_POLICIES` policies of different insured, or ≥ `LIFE.BENCHG.MIN_COUNT` changes within `LIFE.BENCHG.COUNT_MONTHS` |
| L-R6 | ตัวแทนหรือพนักงานกระจุกตัว | `LIFE-STAFF-CONC` | A `created_by` whose share of surrender and beneficiary-change records meets the C1 concentration rule (share ≥ `CONC.SINGLE_ENTITY_SHARE`, together with HHI per C1) |

- Each risk has Thai and English synonyms in `RISK_LIBRARY`.
- `request_if_missing` per role, for example: "ขอข้อมูลกรมธรรม์ (วันออกกรมธรรม์)" (request policy data: issue date) and "ขอประวัติการเปลี่ยนผู้รับผลประโยชน์" (request beneficiary-change history).

---

## 5. F: fund investor transactions (F1)

### 5.1 Tables and roles
| Table | Example columns → role | Required? |
|---|---|---|
| Fund transactions | order_id→`record_id`, unitholder_id→`entity`, fund_code→`contract`, order_datetime→`date` (should include the time), txn_type→`category`, amount→`amount`, bank_account→`counterparty`, agent→`channel`, nav_date→`due_date` | Required |
| Unitholder master | unitholder_id→`entity`, open_date→`opened_at` | Optional |

### 5.2 Risks and checks
| Risk | Thai name | Check | Rule |
|---|---|---|---|
| F-R1 | ซื้อแล้วขายคืนเร็ว | `FUND-ROUNDTRIP` | Same unitholder and fund. A sale within `FUND.ROUNDTRIP.DAYS` of a purchase, with the sale amount within `FUND.ROUNDTRIP.AMOUNT_BAND` of the purchase. Switches do not count as sales. |
| F-R2 | ผู้ชำระหรือผู้รับเงินเป็นบุคคลที่สาม | `FUND-THIRD-PARTY` | The account owner (`counterparty`) ≠ the unitholder. The §2 comparison rule applies. |
| F-R3 | บัญชีรับเงินเดียวใช้กับผู้ถือหน่วยหลายราย | `FUND-SHARED-ACCT` | One `counterparty` used by ≥ `FUND.SHARED_ACCT.MIN_HOLDERS` unitholders |
| F-R4 | ซื้อขายหรือสับเปลี่ยนถี่ | `FUND-FREQUENT` | ≥ `FUND.FREQ.MIN_TX_MONTH` buy, sell or switch transactions per unitholder per month |
| F-R5 | ตัวแทนขายชักนำให้ซื้อขายถี่ | `FUND-CHURN` | An agent (`channel`) where ≥ `FUND.CHURN.MIN_CLIENT_SHARE` of its clients hit F-R4 and there are ≥ `FUND.CHURN.MIN_CLIENTS` such clients |
| F-R6 | ทำรายการหลังเวลาตัดรอบ | `FUND-LATE-TRADE` | Order time > `FUND.CUTOFF_TIME` and `due_date` (NAV date) = the order date |

- **F-R6 Skip.** Skipped with a reason when `date` has no time of day or `due_date` is missing. Sufficiency gives 🟡 plus a Data Request.
- **One cut-off per run.** C2 uses a single cut-off time per run. The auditor can override it as an organisation value.

---

## 6. Samples (fixed seed)

| Set | Tables | Planted cases |
|---|---|---|
| L | transactions, master, beneficiary changes | **L-R1:** surrender 4 months after a single-premium policy is issued<br>**L-R2:** beneficiary change followed by a surrender within 10 days<br>**L-R3:** loan at 95% of cash value; a loan followed by a surrender<br>**L-R4:** one account receiving surrenders from 4 policies<br>**L-R5:** one beneficiary on 3 policies<br>**L-R6:** one staff member handling 40% of surrenders |
| F | transactions, master | **F-R1:** buy then sell within 9 days<br>**F-R2:** redemption paid to another person's account<br>**F-R3:** one account used by 4 unitholders<br>**F-R4:** 10 transactions in one month<br>**F-R5:** an agent with 40% of clients switching frequently<br>**F-R6:** an order at 16:10 priced at that day's NAV |

- **Normal rows.** They must not trigger any check, including the general cards. Use stable amounts per entity, steady counts per month, times inside business hours and before the cut-off.
- **Each set has:**
  - `brief.md`, a Thai auditor letter plus a ```json block
  - `answer_key.json` with findings, recipes, intake and conventions
  - three column-name variants, each with a `roles_<variant>.json`
  - the code values for `category`
- **The intake key for each set has:**
  - sufficiency
  - a Data Request: at least one concern whose data is missing. In L the brief includes a concern that needs data the set does not have. In F the set has a variant without time of day, which makes F-R6 🟡.
  - suggested risks
  - description conflicts

---

## 7. Testing

- **Every new check:** finds its planted case, has no false positives on normal rows, and has a test at each inclusive threshold boundary.
- **Every runnable check on L and F:** flags only ids that are in the key's `recipes`.
- **Realistic path for L and F:**
  - `inspect(files, brief)` → `confirm(draft, {})` → `run`, plus `confirm` with only the code values supplied.
  - This path must pass without passing the full roles json.
- **Event table:**
  - present → ✅
  - absent → ❌ / 🟡 with a Data Request
  - poor join rate → 🟡 showing the rate
- **Skips with a reason:** L-R4(a) and F-R2 when the formats can't be compared; F-R6 when there is no time or no NAV date; unconfirmed code values.
- **Three column-name variants × 2 sets:** equal Findings. en/th must reach ≥ 80% high confidence on roles.
- **Regression:** E, C and A match the C1 answer keys. All C1 tests still pass.
- **Performance:** 80k rows of L or F stay within the C1 limits.
- **pandas:** 3 and 1.5.3.

---

## 8. Documentation and release

| File | Change |
|---|---|
| AIDA-00 | Index, C2 scope, versions |
| AIDA-14 | v1.3 (§3) |
| AIDA-15 | FAQ for life insurance and funds, including the scope deferred to later phases |
| AIDA-17 | Presets L/F, type-specific role meanings, default code values |
| AIDA-18 | Regenerated from the engine with `tools/build_risk_library_md.py` |
| AIDA-19 | Attaching multiple tables (event table), confirming code values (`answers["code_values"]`), the L/F examples |
| Instructions | Scope sentence and version only (≤ 8,000 characters) |
| eval-questions | Q48–Q57: L/F intake, code values, Skip with reason, the realistic path, Data Request, variants |
| validator | Accepts the new data types and keys; existing checks unchanged |

Zip `AIDA-Knowledge-Pack-v3.1.zip` uses the v3.0 layout plus `4-samples/{L,F}/`.

---

## 9. Recorded risks

| Risk | Mitigation |
|---|---|
| Stretched role meanings (`limit` = surrender value, `due_date` = NAV date) may confuse auditors | The Intake shows the type-specific meaning; AIDA-17 explains it |
| A larger engine | Performance tests; the Copilot loading method is unchanged |
| Default thresholds are not an official standard | The Intake asks the auditor to confirm them or set organisation values; AIDA-14 cites the source |
| Code values differ by organisation | Checks Skip until the codes are confirmed; the mapping profile stores them for reuse |
| Changes to `to_internal` and type lists break E/C/A | Answer-key regression tests and the existing C1 tests |
