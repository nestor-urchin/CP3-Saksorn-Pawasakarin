# AIDA C2 (Life Insurance L3 and Fund Investor Transactions F1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `aida_engine.py` with data types **L** (life insurance: surrender, policy loans, beneficiary changes) and **F** (fund investor transactions). The engine gets 12 certified checks, 12 risks, presets, samples with answer keys, and Knowledge Pack v3.1.

**Architecture:**
- **One engine file.** All work goes into the existing single engine file `aida-knowledge/engine/aida_engine.py`.
- **Event table.** The role adapter learns one optional **event table** (`tables["events"]`, used for L beneficiary changes).
- **Code meanings.** Checks read transaction-type meanings from the confirmed intake `code_values`, translated through `CODE_MEANINGS`.
- **Unchanged from C1:** the 14 roles, the Intake Review, sufficiency, exploratory mode and the general cards. The general cards gain L and F as data types.

**Tech Stack:** Python 3 standard library + pandas (≥ 1.5, also 3.x) + numpy + openpyxl; unittest; Thai Markdown knowledge files.

**Spec:** `docs/superpowers/specs/2026-11-09-aida-c2-life-fund-design.md`. The C1 spec (`docs/superpowers/specs/2026-11-06-aida-c1-generic-engine-design.md`) still binds wherever C2 is silent. Read both before each task.

## Global Constraints

- **Versions:** `__version__ = "3.1.0"`, `REGISTRY_VERSION = "1.3"`. AIDA-00, AIDA-19 and AIDA-14 must match them, as the validator checks.
- **Imports:** pandas, numpy, openpyxl and the standard library only. No network libraries.
- **Roles:** exactly the 14 C1 roles. Add no new standard role. Certified checks never read `custom:` roles.
- **Internal columns (C1, unchanged):** record_id→`tx_id`, date→`ts`, amount→`amount`, entity→`from_acct`, counterparty→`to_acct`. Every other role keeps its role name. The master table uses `acct_id`/`opened_at`. The new event table uses the same internal names as the transactions table.
- **Thresholds:** every threshold is read as `cfg["KEY"]` from AIDA-14. New keys and their defaults:

  | Key | Default | Key | Default |
  |---|---|---|---|
  | `LIFE.EARLY_SURR.MONTHS` | 12 | `FUND.ROUNDTRIP.DAYS` | 30 |
  | `LIFE.BENCHG_CASH.WINDOW_DAYS` | 30 | `FUND.ROUNDTRIP.AMOUNT_BAND` | 80%–120% |
  | `LIFE.LOAN.NEAR_PCT` | 90% | `FUND.SHARED_ACCT.MIN_HOLDERS` | 3 |
  | `LIFE.LOAN.MIN_COUNT` | 3 | `FUND.FREQ.MIN_TX_MONTH` | 6 |
  | `LIFE.LOAN.COUNT_MONTHS` | 12 | `FUND.CHURN.MIN_CLIENT_SHARE` | 30% |
  | `LIFE.LOAN_SURR.WINDOW_DAYS` | 90 | `FUND.CHURN.MIN_CLIENTS` | 5 |
  | `LIFE.PAYEE.MIN_POLICIES` | 3 | `FUND.CUTOFF_TIME` | 15:30 |
  | `LIFE.BENEF.MIN_POLICIES` | 3 | | |
  | `LIFE.BENCHG.MIN_COUNT` | 2 | | |
  | `LIFE.BENCHG.COUNT_MONTHS` | 12 | | |

  - Source text: "แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ".
  - L-R6 reuses `CONC.SINGLE_ENTITY_SHARE` and `CONC.HHI`.
- **Risk IDs and Thai names:**
  - L-R1 เวนคืนเร็วหลังทำกรมธรรม์
  - L-R2 เปลี่ยนผู้รับผลประโยชน์แล้วมีรายการเงินตามมาเร็ว
  - L-R3 กู้ตามกรมธรรม์ผิดปกติ
  - L-R4 จ่ายเงินเข้าบัญชีบุคคลที่สาม
  - L-R5 ผู้รับผลประโยชน์ซ้ำข้ามกรมธรรม์
  - L-R6 ตัวแทนหรือพนักงานกระจุกตัว
  - F-R1 ซื้อแล้วขายคืนเร็ว
  - F-R2 ผู้ชำระหรือผู้รับเงินเป็นบุคคลที่สาม
  - F-R3 บัญชีรับเงินเดียวใช้กับผู้ถือหน่วยหลายราย
  - F-R4 ซื้อขายหรือสับเปลี่ยนถี่
  - F-R5 ตัวแทนขายชักนำให้ซื้อขายถี่
  - F-R6 ทำรายการหลังเวลาตัดรอบ
- **Check IDs:**
  - L: `LIFE-EARLY-SURR`, `LIFE-BENCHG-CASH`, `LIFE-LOAN`, `LIFE-THIRD-PAYEE`, `LIFE-BENEF-MULTI`, `LIFE-STAFF-CONC`
  - F: `FUND-ROUNDTRIP`, `FUND-THIRD-PARTY`, `FUND-SHARED-ACCT`, `FUND-FREQUENT`, `FUND-CHURN`, `FUND-LATE-TRADE`
- **Internal code meanings:**
  - L: `surrender`, `loan`, `claim`, `benefit_change`
  - F: `buy`, `sell`, `switch_in`, `switch_out`
- **Wording and errors:**
  - User-facing text is Thai and non-accusatory ("สอดคล้องกับ … pattern"). Never use บัญชีม้า or ทุจริต.
  - Errors are Thai `AidaError` messages that say how to fix the problem.
  - Every number shown comes from the engine.
- **E/C/A answer keys:** they must not change. All C1 tests must keep passing.
- **Knowledge pack:** exactly 20 files. Instructions ≤ 8,000 characters. Zip `AIDA-Knowledge-Pack-v3.1.zip`.
- **pandas venv for 1.5.3:** `/tmp/claude-0/-home-user-CP3-Saksorn-Pawasakarin/a27e31ad-493a-5ef6-87b3-fb57866bc471/scratchpad/venv-pd15/bin/python`.
  - If it is missing, recreate it with `python3 -m venv <path> && <path>/bin/pip install "pandas==1.5.3" "numpy<2" openpyxl`.
  - Run every suite on both interpreters.

## Review Focus

1. **Code values written differently from the confirmed code.** Examples: "surr ", "SURR", "Surrender", or the Thai meaning "เวนคืน". Expected: matching ignores case and spaces, and Thai and English meaning text both resolve through `CODE_MEANINGS`. Test: `test_code_meaning_normalised` (Task 1).
2. **Event-table `contract` ids that differ from the main table only by leading zeros or spaces.** Expected: the join normalises them (C1 `_norm_key`), and the profile reports the raw and normalised rates. Test: `test_event_join_normalised` (Task 1).
3. **A surrender on a policy with no master row, or no `opened_at`.** Expected: L-R1 skips that policy and adds a card note. It does not crash and does not flag the policy. Test: `test_early_surr_missing_master_row` (Task 3).
4. **Fund buy and sell on the same day, or the sale row appearing before the buy row in the file.** Expected: F-R1 pairs by timestamp order, not file order, and a sale earlier than the buy never pairs. Test: `test_roundtrip_uses_time_order` (Task 4).
5. **Order timestamps in Thai BE format with a time** ("05/03/2569 16:10"). Expected: the C1 parser keeps the time, and F-R6 applies the cut-off correctly. Test: `test_late_trade_thai_be_datetime` (Task 4).

---

### Task 1: Engine plumbing for L/F, event table, code meanings, Registry v1.3

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`
  - `__version__`, `REGISTRY_VERSION`
  - `_ALL` / `data_types` of the general CHECKS
  - `PRESETS`, `ROLE_SYNONYMS`, `ENTITY_LABELS`, `detect_dataset_type`, `to_internal`
  - profile join report
  - `_review_a`
- Modify: `aida-knowledge/knowledge/AIDA-14-configuration-registry.md`: the v1.3 rows for every key in Global Constraints, the Machine Config entries, the version line, and the history row.
- Modify: version references in `knowledge/AIDA-00-*.md`, `knowledge/AIDA-19-engine-guide.md`, `AIDA-agent-instructions.md` and `README.md`, only so that the validator passes.
- Create: `aida-knowledge/tests/test_c2_plumbing.py`

**Interfaces:**
- Consumes (C1): `to_internal(frames, roles) -> dict`, `_norm_key`, `profile_columns`, `load_registry`, `_finish(...)` (Evidence builder), `CHECKS`, `RISK_LIBRARY`.
- Produces:
  - `DATA_TYPES = ("E", "C", "A", "L", "F")`. General checks use `data_types=list(DATA_TYPES)`.
  - `PRESETS["L"]` and `PRESETS["F"]`, with en column names exactly as in spec §4.1 and §5.1:
    - L: txn_id, policy_no, insured_id, txn_date, txn_type, amount, payee, cash_value, staff_id; master: issue_date, premium_mode; events: change_id, change_date, beneficiary
    - F: order_id, unitholder_id, fund_code, order_datetime, txn_type, amount, bank_account, agent, nav_date; master: open_date
  - `ROLE_MEANING_BY_TYPE: dict[str, dict[str, str]]` (Thai meaning text). It includes at least:
    - L: `limit` → "มูลค่าเวนคืน", `counterparty` → "ผู้รับเงิน / ผู้รับผลประโยชน์", `opened_at` → "วันออกกรมธรรม์"
    - F: `due_date` → "วันที่ได้ราคา NAV", `channel` → "ตัวแทนขาย", `counterparty` → "บัญชีชำระ/รับเงิน"
  - `CODE_MEANINGS: dict[str, list[str]]`, mapping each internal meaning to Thai and English phrases. Examples: `surrender` → ["เวนคืน", "surrender", "surr"]; `buy` → ["ซื้อ", "buy", "subscription"].
  - `code_set(tables: dict, meaning: str) -> set[str]` returns the raw codes in `tables["transactions"]["category"]` whose confirmed meaning resolves to `meaning`, compared after casefold and strip. It reads the confirmed `code_values`, which `run` stores in `tables["meta"]["code_values"]`. It falls back to the preset default codes **only when** the intake has no `code_values` for that column. In that case the checks Skip.
  - `missing_codes(tables, meanings: list[str]) -> list[str]` returns the meanings with no matching code. Checks Skip with the Thai reason "ยังไม่ได้ยืนยันความหมายรหัสประเภทรายการ: …".
  - `to_internal` accepts at most one extra table whose roles include `record_id` + `date` + `contract` and which is not the transactions table. It is returned as `tables["events"]`, in the same internal column naming.
    - A second extra table raises a Thai `AidaError`.
  - The profile join report covers events↔transactions on `contract`, giving raw and normalised percentages, the same way as the C1 `join_match`.
  - `ENTITY_LABELS["L"]` = {"entity": "insured", "account": "policy", "counterparty": "payee"}
  - `ENTITY_LABELS["F"]` = {"entity": "unitholder", "account": "fund", "counterparty": "account"}
  - `detect_dataset_type` returns "L" or "F" from the presets and synonyms, with the C1 behaviour unchanged for E/C/A.
  - Intake Review section A prints the type-specific meaning, for example `cash_value → limit (มูลค่าเวนคืน)`.

- [ ] **Step 1: Write the failing tests** in `test_c2_plumbing.py`:
  - `test_versions`: 3.1.0 and 1.3, and `load_registry(AIDA-14)["REGISTRY.VERSION"] == "1.3"`.
  - `test_new_registry_keys_present`: every key in Global Constraints is in cfg with the stated value.
  - `test_general_checks_cover_L_F`: for STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, GEN-CONC, GEN-PERIOD-END and FOR-*, the `data_types` include L and F.
  - `test_to_internal_event_table`: three frames (tx, master, events) give `tables["events"]` with `tx_id`/`ts`/`contract`/`to_acct`.
  - `test_to_internal_two_event_tables_rejected`: raises an `AidaError` in Thai.
  - `test_event_join_normalised` (Review Focus 2): events contract "00123" against tx "123" gives raw 0% and normalised 100%.
  - `test_code_meaning_normalised` (Review Focus 1): codes {"SURR ": "Surrender", "ln": "เงินกู้"} resolve to `code_set(...,"surrender") == {"SURR "}`, and "ln" maps to loan.
  - `test_missing_codes_reason_thai`.
  - `test_detect_type_L_F`.
  - `test_review_a_shows_type_meaning`.
  - `test_e_c_a_unchanged`: the C1 E/C/A run findings still equal their keys. Reuse the `test_orchestration` helpers.
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_c2_plumbing`. Expected: FAIL.
- [ ] **Step 3: Implement the engine changes and AIDA-14 v1.3.** Update the version strings in the docs listed under Files so that `python3 aida-knowledge/tools/validate_pack.py aida-knowledge` prints `OK: 20 files validated`.
- [ ] **Step 4: Run** the full `tests/` and `tools/` suites on both interpreters, plus the validator. Expected: all pass.
- [ ] **Step 5: Commit and push.**

---

### Task 2: Samples L and F with briefs, answer keys and naming variants

**Files:**
- Create: `aida-knowledge/tests/make_sample_l.py`, `aida-knowledge/tests/make_sample_f.py`, `aida-knowledge/tests/test_sample_lf.py`
- Generated (committed):
  - `aida-knowledge/samples/L/{policy_txn.csv, policies.csv, beneficiary_changes.csv, brief.md, answer_key.json}`
  - `aida-knowledge/samples/F/{fund_txn.csv, unitholders.csv, brief.md, answer_key.json}`
  - `samples/<T>/variants/{en,th,legacy}/`, `variants/roles_<v>.json`
  - `samples/F/variants/date_only/`: fund_txn with no time of day, used for the F-R6 🟡 case

**Interfaces:**
- Consumes: `tests/sample_common.py` (`TH` read from cfg, shared helpers), and the C1 generator pattern in `make_sample_c.py`.
- Produces:
  - `make(seed=20261109) -> (frames: dict, key: dict)` per module.
  - The key has the C1 schema: `findings` [{entity_type, entity_id, risk, period}], `recipes` {check_id: [ids]}, `intake` {sufficiency, data_request, suggested_risks, description_conflicts}, `conventions`.
  - Plus `code_values` {`table.column`: {code: Thai meaning}}.

| Set | Planted cases (ids are fixed) |
|---|---|
| L | **L-R1:** policy `P-0101` single premium, surrendered 4 months after issue<br>**L-R2:** policy `P-0202` beneficiary change, then a surrender 10 days later<br>**L-R3:** policy `P-0303` loan at 95% of cash value; policy `P-0304` loan, then a surrender 40 days later<br>**L-R4:** payee account `ACC-9001` receives surrenders from 4 policies of different insured<br>**L-R5:** beneficiary `B-777` named on 3 policies of different insured<br>**L-R6:** staff `S-07` handles 40% of surrenders and beneficiary changes |
| F | **F-R1:** unitholder `U-0101` buys then sells fund `FX1` 9 days later at 98% of the amount<br>**F-R2:** unitholder `U-0202` redemption paid to account `BA-5555`, which belongs to `U-0999`<br>**F-R3:** account `BA-7000` used by 4 unitholders<br>**F-R4:** unitholder `U-0404` makes 10 transactions in one month<br>**F-R5:** agent `AG-05`, with 40% of its clients (≥ 5) meeting F-R4<br>**F-R6:** order `O-6006` at 16:10 with NAV date = order date |

- **Normal rows:** they must trigger no check, general cards included.
  - Amounts are stable per entity.
  - Monthly counts are steady.
  - Times fall within 09:00–15:00 on business days.
  - Payee equals the insured or unitholder in a comparable format.
- **Briefs:** Thai auditor letters plus a ```json brief block, in the C1 format.
  - The L brief lists 4 concerns. One of them needs claims data the set does not have (for example "เคลมเร็วหลังทำกรมธรรม์"). It must come out as exploratory mode or a Data Request, as the key records.
  - The F brief lists 3 concerns, and describes the time column so that F-R6 is ✅. The `date_only` variant makes it 🟡.

- [ ] **Step 1: Write the failing tests:**
  - `test_l_deterministic`, `test_f_deterministic`
  - `test_planted_cases_grounded`: recompute each planted case from the CSVs with plain pandas, independently of the engine and the key
  - `test_variants_same_content`
  - `test_brief_json_block_parses`
  - `test_code_values_cover_all_codes`
- [ ] **Step 2: Run** `python3 -m unittest test_sample_lf`. Expected: FAIL.
- [ ] **Step 3: Implement the generators and generate the files.**
- [ ] **Step 4: Run** the full suite on both interpreters. Expected: PASS.
- [ ] **Step 5: Commit and push.**

---

### Task 3: Life-insurance checks and risks L-R1..L-R6

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py` (new check functions, `CHECKS` entries, `RISK_LIBRARY` entries)
- Create: `aida-knowledge/tests/test_checks_l.py`

**Interfaces:**
- Consumes: Task 1 (`code_set`, `missing_codes`, `tables["events"]`, `ENTITY_LABELS["L"]`); C1 `_finish`, `_gen_tx`/`base_tx`, the concentration helper used by `gen_conc`.
- Produces six check functions. Each has the signature `(tables: dict, cfg: dict) -> pd.DataFrame` and returns C1 Evidence + `roles_used`, with these entity ids:
  - `LIFE-EARLY-SURR`: the policy (`contract`)
  - `LIFE-BENCHG-CASH`: the policy
  - `LIFE-LOAN`: the policy
  - `LIFE-THIRD-PAYEE`: the payee (`counterparty`) for rule (b); the policy for rule (a)
  - `LIFE-BENEF-MULTI`: the beneficiary
  - `LIFE-STAFF-CONC`: the `created_by`
- `CHECKS[...]` entries with `risk`, `requires` (roles), `registry` (keys) and `data_types=["L"]`.
- `RISK_LIBRARY["L-R1".."L-R6"]`, with `name_th` exactly as in Global Constraints, Thai and English `synonyms`, `checks`, `min_roles` and `request_if_missing`, e.g. `opened_at` → "ขอข้อมูลกรมธรรม์ (วันออกกรมธรรม์)" and events → "ขอประวัติการเปลี่ยนผู้รับผลประโยชน์".
- Rules: spec §4.2. The period is the month of the triggering record, i.e. the latest record of the pattern.
- **L-R4 rule (a):** runs only when at least one row has `to_acct` comparable to `from_acct`, meaning the same normalised value pattern as decided by `profile_columns` patterns. Otherwise it is skipped with a card note "รูปแบบผู้รับเงินกับผู้เอาประกันเทียบกันไม่ได้", and rule (b) still runs.

- [ ] **Step 1: Write the failing tests** in `test_checks_l.py`:
  - For each check, `test_<check>_finds_planted` (ids from the L key) and `test_<check>_no_false_positive`.
  - Boundary tests:
    - `test_early_surr_boundary`: exactly 12 months counts. Use a synthetic frame.
    - `test_loan_near_pct_boundary`: exactly 90% counts.
    - `test_benchg_cash_window_boundary`: day 30 counts and day 31 does not.
    - `test_payee_min_policies_boundary`: 3 counts and 2 does not.
  - `test_early_surr_missing_master_row` (Review Focus 3).
  - `test_third_payee_incomparable_skips_rule_a`.
  - `test_l_checks_skip_without_codes` (Thai reason).
  - `test_l_risks_in_library_and_checks_exist`.
  - `test_l_override_changes_result`: `LIFE.EARLY_SURR.MONTHS` = 3 drops `P-0101`.
- [ ] **Step 2: Run** `python3 -m unittest test_checks_l`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite on both interpreters and `python3 aida-knowledge/tools/build_risk_library_md.py`. Regenerate AIDA-18 so the validator stays OK. Expected: PASS / OK.
- [ ] **Step 5: Commit and push.**

---

### Task 4: Fund checks and risks F-R1..F-R6

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`
- Create: `aida-knowledge/tests/test_checks_f.py`

**Interfaces:**
- Consumes: Task 1 (`code_set`, `missing_codes`, `ENTITY_LABELS["F"]`) and the C1 helpers.
- Produces six checks with the Task 3 signature. Entity ids:
  - `FUND-ROUNDTRIP`: unitholder
  - `FUND-THIRD-PARTY`: unitholder
  - `FUND-SHARED-ACCT`: account (`counterparty`)
  - `FUND-FREQUENT`: unitholder
  - `FUND-CHURN`: agent (`channel`)
  - `FUND-LATE-TRADE`: the order (`record_id`)
- CHECKS and `RISK_LIBRARY["F-R1".."F-R6"]` follow the Task 3 pattern, with `data_types=["F"]`.
- Rules: spec §5.2.
  - **F-R1 pairing:** pair each sell with the latest earlier buy of the same unitholder and fund, ordered by `ts`, within `FUND.ROUNDTRIP.DAYS`, and with the amount ratio inside `FUND.ROUNDTRIP.AMOUNT_BAND`. Switches never count as buy or sell.
  - **F-R2 comparability:** uses the same comparability rule as L-R4 rule (a). When the formats can't be compared, it Skips with a card note. Add the test `test_third_party_incomparable_skips`.
  - **F-R6 requirements:** needs a time of day in `ts` (C1 time-of-day detection) and the `due_date` role. Otherwise Skip with a Thai reason.
  - **F-R6 cut-off:** parse `FUND.CUTOFF_TIME` "HH:MM" from cfg.

- [ ] **Step 1: Write the failing tests** in `test_checks_f.py`:
  - per check: `_finds_planted` and `_no_false_positive`
  - `test_roundtrip_uses_time_order` (Review Focus 4)
  - `test_roundtrip_band_boundary`: 80% and 120% count, 79.9% does not
  - `test_freq_boundary`: 6 counts, 5 does not
  - `test_churn_min_clients_boundary`
  - `test_late_trade_thai_be_datetime` (Review Focus 5)
  - `test_late_trade_skips_date_only`: uses the `date_only` variant, with a Thai reason
  - `test_cutoff_override`: "17:00" drops `O-6006`
  - `test_f_checks_skip_without_codes`
  - `test_f_risks_in_library_and_checks_exist`
- [ ] **Step 2: Run** `python3 -m unittest test_checks_f`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite on both interpreters. Then regenerate AIDA-18 and run the validator. Expected: PASS / OK.
- [ ] **Step 5: Commit and push.**

---

### Task 5: End to end — intake, sufficiency, realistic path, variants, regression, performance

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`. Fix any gaps found. Pass `code_values` into `tables["meta"]` inside `run` and `trace`.
- Create: `aida-knowledge/tests/test_c2_e2e.py`

**Interfaces:**
- Consumes: Tasks 1–4, and the C1 `inspect` / `confirm` / `run` / `data` / `promote`.
- Produces: no new public API.
  - `inspect` lists unconfirmed type codes as ❓ in section A.
  - Sufficiency for L/F counts the event table and the `code_values`.

- [ ] **Step 1: Write the failing tests** in `test_c2_e2e.py`:
  - **Realistic path:**
    - `test_realistic_path_L`: `inspect(files, brief)` → `confirm(draft, {})` → `run` equals the L key findings.
    - `test_realistic_path_F`: the same for F.
    - `test_confirm_with_code_values_only`: answers containing only `code_values` give the key.
  - **Intake and sufficiency:**
    - `test_intake_L_matches_key` and `test_intake_F_matches_key`: sufficiency, data_request, suggested_risks and description_conflicts.
    - `test_event_table_absent_gives_request`: without beneficiary_changes, L-R2 and L-R5 are not ✅, with a Data Request.
    - `test_event_table_poor_join_partial`: shows the rate.
    - `test_date_only_variant_f_r6_partial`.
  - **Variants:** `test_variants_same_findings_L_F` (en/th/legacy × L/F, using `subTest`) and `test_suggest_roles_en_th_high_confidence_L_F` (≥ 80% สูง).
  - **Regression:**
    - `test_every_runnable_check_flags_only_key_ids_L_F`.
    - `test_e_c_a_regression`: all three keys, plus the existing C1 suites green.
  - **Performance:** `test_perf_80k_L_and_F`: inspect ≤ 30 s, run ≤ 90 s.
  - **Exploration:** `test_explore_promote_on_L`: an RX finding promoted on L data carries the label and Confidence ≤ กลาง.
- [ ] **Step 2: Run** `python3 -m unittest test_c2_e2e`. Expected: FAIL where gaps exist. Fix them in the engine. Do not change tests or answer keys to make them pass; if a key looks wrong, stop and report.
- [ ] **Step 3: Run** the full `tests/` and `tools/` suites on both interpreters and the validator. Expected: all pass.
- [ ] **Step 4: Commit and push.**

---

### Task 6: Knowledge Pack v3.1, docs, eval and zip

**Files:**
- Modify:
  - `knowledge/AIDA-00-*`: index, C2 scope, versions
  - `AIDA-15`: FAQ for life insurance and funds; deferred scope (L1, L2, F2, credit cards, foundations, cooperatives)
  - `AIDA-17-roles-schema.md`: presets L/F, `ROLE_MEANING_BY_TYPE`, default codes, `code_values` format
  - `AIDA-18`: regenerated
  - `AIDA-19-engine-guide.md`: attaching an event table, confirming `code_values`, L/F examples
  - `AIDA-agent-instructions.md`: scope sentence and version only; must stay ≤ 8,000 chars
  - `README.md`
  - `tests/eval-questions.md`: add Q48–Q57
- Modify: `tools/validate_pack.py` and its tests, only if the new data types or keys need it. Keep the existing checks.

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: the release zip `/tmp/claude-0/-home-user-CP3-Saksorn-Pawasakarin/a27e31ad-493a-5ef6-87b3-fb57866bc471/scratchpad/AIDA-Knowledge-Pack-v3.1.zip`.
  - It uses the v3.0 layout (`1-upload-knowledge` (20), `2-paste-instructions`, `3-test`, `4-samples/{E,C,A,L,F}`, `5-engine`, `6-spike-c1`, `README.md`).
  - The README states what is new in v3.1 and how to upgrade from v3.0 (replace the engine and the AIDA-14 together).

Eval Q48–Q57 each carry a question, expected behaviour, pass criteria and a checklist tag. They cover:
- L intake with 3 tables
- unconfirmed codes → ❓
- a confirmed realistic run on L
- L-R4 incomparable payee → Skip with reason
- a missing event table → Data Request
- F intake
- F date-only → F-R6 🟡
- F cut-off org override
- an L concern outside the library → exploratory mode
- a variant with Thai column names

Each item says which `4-samples/` path to use, and that only the letter part of the brief is pasted.

- [ ] **Step 1: Write failing validator or docs tests**, if the validator changes: `test_pack_has_20_files` and the version tests already exist. Add `test_registry_v13_keys_documented`.
- [ ] **Step 2: Write the docs and eval. Regenerate AIDA-18.**
- [ ] **Step 3: Run** the validator (expect `OK: 20 files validated`), the `tools/` and `tests/` suites on both interpreters, and an Instructions char count.
- [ ] **Step 4: Build the zip, list it, and check that the knowledge files, Instructions and engine are byte-identical to HEAD.**
- [ ] **Step 5: Commit and push.**
