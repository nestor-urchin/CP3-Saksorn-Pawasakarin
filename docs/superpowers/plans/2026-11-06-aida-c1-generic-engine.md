# AIDA C1 (Generic Engine, Risk-Driven Intake, Exploratory Mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace B1's 34 Knowledge recipe cards with one tested Python engine (`aida_engine.py`). The engine analyses any dataset through 14 column roles. It runs a risk-driven Intake Review (profile, role suggestion, sufficiency, data request, suggested risks), certified checks for data types E, C and A, an exploratory mode with promotion to Finding, and reusable mapping profiles.

**Architecture:** A single module at `aida-knowledge/engine/aida_engine.py` exposes `inspect` → `confirm` → `run` (plus `data`, `explore_log`, `promote`, `trace`, `save_mapping`).
- B1's tested card code moves into the engine almost verbatim.
- A role adapter renames confirmed role columns to the engine's internal canonical columns, so the B1 checks keep working unchanged and the new checks use the same frame.
- `run()` rebuilds everything from the files plus the confirmed `intake.json`, and never relies on earlier Code Interpreter state.

**Tech Stack:** Python 3 standard library + pandas (≥ 1.5, also tested on 3.x) + numpy + openpyxl; unittest; Playwright/Chromium for the dashboard check. Markdown knowledge files.

**Spec:** `docs/superpowers/specs/2026-11-06-aida-c1-generic-engine-design.md`. Read §4–§7 before each task; it overrides this plan on any conflict. B1 spec/plan in `docs/superpowers/` describe the code being migrated.

## Global Constraints

- **Engine location and versions:** the engine source is `aida-knowledge/engine/aida_engine.py`, one file. It defines `__version__ = "3.0.0"` and `REGISTRY_VERSION = "1.2"`.
- **Allowed imports:** pandas, numpy, openpyxl and the standard library only. Never import network libraries (`requests`, `urllib`, `http`, `socket`).
- **Roles:** the 14 roles are fixed, exactly: `record_id, date, amount, entity, counterparty, contract, category, channel, created_by, approved_by, document_no, limit, due_date, opened_at`. Auditors may add `custom:<name>` roles. Certified checks never read custom roles.
- **Internal canonical columns:** after the role adapter, the transaction frame uses:

  | Role | Internal column |
  |---|---|
  | `record_id` | `tx_id` |
  | `date` | `ts` |
  | `amount` | `amount` |
  | `entity` | `from_acct` |
  | `counterparty` | `to_acct` |
  | everything else | its role name |
  | `custom:x` | `custom:x` |

  The master/accounts frame uses `acct_id` and `opened_at`.
- **Thresholds:** every threshold comes from the AIDA-14 Machine Config dict passed as `cfg`, read as `cfg["KEY"]`. Organisation overrides from Intake replace a key only for that run, and are recorded in the Run Log and the Workbook as "ค่าขององค์กร".
- **Numbers and wording:**
  - Every number shown to the user comes from engine output; the LLM never computes numbers.
  - User-facing text is Thai and non-accusatory ("สอดคล้องกับ … pattern"; never บัญชีม้า, ทุจริต and similar).
  - Errors are returned as Thai messages that say how to fix them, never as a raw traceback.
- **Exploratory Findings:** `source="exploratory"`, Confidence is at most "กลาง", `reviewer` is required, and the "จากโหมดสำรวจ" label is permanent. Risk is taken from the Risk Library, or `RX`.
- **Risk IDs:** the B1 IDs `R1–R4` are kept for data type E. New IDs:

  | Group | IDs and names |
  |---|---|
  | General | `G-R1` ยอดโดดเด่น · `G-R2` ช่วงสิ้นงวด · `G-R3` นอกเวลาทำการ · `G-R4` ตัวเลขผิดธรรมชาติ |
  | Loans | `C-R1` ผู้ชำระคนเดียวหลายสัญญา · `C-R2` ชำระใกล้วันครบกำหนดซ้ำ ๆ (อาจตกแต่งสถานะค้างชำระ) · `C-R3` ชำระซ้ำ/คืนเงินผิดปกติ |
  | Accounts payable | `A-R1` จ่ายซ้ำ · `A-R2` แบ่งรายการต่ำกว่าวงเงิน · `A-R3` ผู้บันทึกและผู้อนุมัติเป็นคนเดียวกัน · `A-R4` ผู้ขายกระจุกตัว |
- **Knowledge pack:** after Task 10 the knowledge folder holds exactly 20 files, and the Instructions are ≤ 8,000 characters.
- **Registry v1.2 new keys** (source "แนวปฏิบัติทั่วไป — ไม่มีมาตรฐานทางการ"):

  | Key | Value |
  |---|---|
  | `DUP.WINDOW_DAYS` | 3 |
  | `SPLIT.WINDOW_DAYS` | 1 |
  | `SPLIT.MIN_TX` | 2 |
  | `DUE.NEAR_DAYS` | 2 |
  | `DUE.MIN_SHARE` | 80% |
  | `DUE.MIN_PERIODS` | 3 |
  | `PAYER.MIN_CONTRACTS` | 3 |
  | `INTAKE.ROLE_CONF` | สูง ≥ 0.8 / กลาง ≥ 0.5 |

  Existing keys (FOR.*, CONC.*, TEMP.*) are reused for Benford, round and repeated amounts, concentration and period-end.

## Review Focus

1. **The same column is proposed for two roles** (for example one ID column suits both `record_id` and `document_no`). `confirm` must reject duplicate role targets, except for an explicitly confirmed `custom:` role, with a Thai message. Test: `test_confirm_rejects_duplicate_role` (Task 7).
2. **The auditor's brief names a risk with a near-synonym** ("จ่ายเงินซ้ำซ้อน", "duplicate payment"). Risk Library matching must use each risk's synonym list and report an unmatched concern as "→ โหมดสำรวจ" instead of dropping it. Test: `test_match_concerns_synonyms_and_unmatched` (Task 6).
3. **A multi-file upload where the secondary table's join column has different values** (for example leading zeros). Profiling must report the match rate of the join key, and sufficiency must mark risks that need the join as 🟡 with a reason. Test: `test_join_match_rate_reported` (Task 3) and `test_sufficiency_partial_on_poor_join` (Task 6).
4. **A mapping profile reused on a file whose columns changed** (renamed, added or dropped). `inspect(..., mapping=...)` must list exactly the changed columns and keep the rest. Test: `test_mapping_reuse_reports_only_changes` (Task 7).
5. **`run()` called in a fresh interpreter with only files and `intake.json`.** It must give the same findings as `run()` right after `confirm`. Test: `test_run_from_intake_json_fresh_process` (Task 7).

---

### Task 1: Copilot spike kit for engine loading

**Files:**
- Create: `aida-knowledge/spike-c1/README.md` (Thai), `aida-knowledge/spike-c1/aida_engine_probe.py`, `aida-knowledge/spike-c1/aida_engine_probe.txt` (identical content), `aida-knowledge/spike-c1/probe-data.csv` (50 rows)
- Test: `aida-knowledge/tests/test_spike_c1.py`

**Interfaces:**
- Produces: `aida_engine_probe.py` defining `__version__ = "probe-1"`, `hello() -> str` (returns "AIDA engine probe OK") and `summarize(path: str) -> dict` (rows, columns, sum of the `amount` column).
- The README has 5 Thai prompts (spec §7.1), a results table, the decision rule (prompt 2 passes → approach 3; else prompt 3 passes → approach 2; else stop) and the removal steps.

- [ ] **Step 1: Write tests:** `test_probe_identical_py_txt`, `test_probe_hello`, `test_probe_summarize` (exact row count and sum on probe-data.csv) and `test_probe_no_network_imports`.
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_spike_c1`. Expected: FAIL (files missing).
- [ ] **Step 3: Write the kit.** Prompt 2 must try both `import` from the Knowledge file path Code Interpreter shows and `exec(open(...).read())`. Prompt 4 checks whether a variable persists to the next message.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit and push.** Do not stop for the user: the spike result is only needed in Task 10, and the controller asks the user to run it in parallel.

---

### Task 2: Engine skeleton, B1 migration and role adapter

**Files:**
- Create: `aida-knowledge/engine/aida_engine.py`, `aida-knowledge/tests/_engine.py` (test loader), `aida-knowledge/tests/test_engine_core.py`
- Modify: `aida-knowledge/tests/test_recipes.py`, `test_recipes_mule.py`, `test_pipeline.py`, `test_outputs.py`, `test_final_review.py`. Repoint their loader from the AIDA-18/19 cards to the engine through `tests/_engine.py`; test bodies stay unchanged.

**Interfaces:**
- Produces, in the engine:
  - Every function currently defined in AIDA-19 and AIDA-18 (`clean_tx` … `out_dashboard`, `stat_mad` … `flow_layering`), behaviour unchanged, copied from the card code blocks with the card header comments removed.
  - The dashboard HTML template from AIDA-16 as the module constant `DASHBOARD_TEMPLATE`.
  - `ROLES: tuple[str, ...]` (the 14 roles in Global Constraints order) and `ROLE_TO_INTERNAL: dict`.
  - `to_internal(frames: dict[str, pd.DataFrame], roles: dict[str, dict[str, str]]) -> dict`. `roles` maps a table name to {user column: role}. The function returns `tables` with `"transactions"` in internal columns and `"accounts"` if mapped.
  - `load_registry(path_or_text: str) -> dict`, the Machine Config parser moved from validate_pack.
- Produces, in `tests/_engine.py`: `engine()` returns the imported module, and `recipes()` returns a dict name → function (a drop-in for the old `load_recipes`).

- [ ] **Step 1: Write failing tests** in test_engine_core:
  - `test_version_constants` (3.0.0 and 1.2)
  - `test_roles_exact_list`
  - `test_to_internal_renames_and_keeps_custom`
  - `test_b1_answer_key_via_engine`: the B1 chain on `samples/` gives exactly `answer_key["findings"]` (19) and 1 network
  - `test_engine_no_network_imports`
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_engine_core`. Expected: FAIL.
- [ ] **Step 3: Build the engine** by concatenating the card code in the existing load order (AIDA-19 helpers → AIDA-18 → the remaining AIDA-19), with one import header. Add the constants, `to_internal`, `load_registry` and the `DASHBOARD_TEMPLATE`. Then switch the existing test files to `tests/_engine.py`.
- [ ] **Step 4: Run the full suite** on pandas 3 and on the 1.5.3 venv (`/tmp/claude-0/-home-user-CP3-Saksorn-Pawasakarin/a27e31ad-493a-5ef6-87b3-fb57866bc471/scratchpad/venv-pd15/bin/python`). Expected: every existing test passes plus the new ones, with no behaviour change.
- [ ] **Step 5: Commit.**

---

### Task 3: Column profiling, role suggestion and description checks

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`
- Create: `aida-knowledge/tests/test_profiling.py`

**Interfaces:**
- Produces:
  - `profile_columns(frames: dict[str, pd.DataFrame]) -> pd.DataFrame`. One row per (table, column) with: dtype_guess, null_pct, unique_pct, min, max, top5 (list), samples (3), patterns (list from {"account_like","thai_id13","code","date","datetime","negative","thai_text","integer","decimal"}), relations (list of strings such as "C = A − B", "X ≤ Y", "X == Y in 92%"), and join_match (for candidate join keys across tables: % of values found in the other table, after stripping and leading-zero normalisation).
  - `ROLE_SYNONYMS: dict[str, list[str]]` (Thai and English names per role) and `PRESETS: dict[str, dict[str, str]]` for E, C and A.
  - `suggest_roles(profile: pd.DataFrame, brief_columns: dict[str, str] | None, preset: str | None, cfg: dict) -> pd.DataFrame` with columns table, column, role ("ไม่ทราบ" allowed), confidence (0–1), level (สูง/กลาง/ต่ำ per `INTAKE.ROLE_CONF`), reason (Thai) and source (brief/preset/synonym/profile).
  - `check_descriptions(profile, brief_columns: dict[str, str]) -> list[dict]`. Each conflict is {column, said, observed, question} in Thai, for example "ยอดสุทธิ" but negative rows exist (with count and %), or "unique id" but duplicates.
  - `detect_dataset_type(profile) -> str | None` ("E"/"C"/"A"/None).

- [ ] **Step 1: Write failing tests:**
  - `test_profile_patterns` (account_like, thai_id13, negative, date on the samples)
  - `test_profile_relation_difference` (a frame where C = A − B is reported)
  - `test_join_match_rate_reported` (Review Focus 3: a join with leading zeros reports a match rate and a normalised rate)
  - `test_suggest_roles_from_brief_overrides_guess`
  - `test_suggest_roles_cryptic_unknown` (columns F07/COL3 → "ไม่ทราบ")
  - `test_check_descriptions_net_amount_negative`
  - `test_detect_dataset_type_e`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Profiling must be vectorised (≤ 5 s on 80k rows × 15 columns; add `test_profile_perf`).
- [ ] **Step 4: Run** the new tests plus the full suite on both pandas versions. Expected: PASS.
- [ ] **Step 5: Commit.**

---

### Task 4: Sample data C and A, auditor briefs and answer keys

**Files:**
- Create: `aida-knowledge/tests/make_sample_c.py`, `aida-knowledge/tests/make_sample_a.py`, `aida-knowledge/tests/test_sample_ca.py`
- Generated (committed): `aida-knowledge/samples/C/{payments.csv, contracts.csv, brief.md, answer_key.json}`, `aida-knowledge/samples/A/{payments.csv, brief.md, answer_key.json}`, and `aida-knowledge/samples/E/brief.md` (the E data stays in `samples/`)
- Generated: three column-naming variants per dataset under `samples/<T>/variants/{en,th,legacy}/` plus `variants/roles_<variant>.json`

**Interfaces:**
- Produces: `make(seed=20261106) -> (frames: dict, key: dict)` per module. Each key contains:
  - `findings`: list of {entity_type, entity_id, risk, period}
  - `recipes`: {check_id: [ids]}
  - `intake`:
    - `sufficiency`: {risk_id: "พร้อม"|"บางส่วน"|"ไม่พอ"}
    - `data_request`: [str]
    - `suggested_risks`: [risk_id]
    - `description_conflicts`: [column]
- Planted cases (spec §7.2):

  | Data | Planted cases |
  |---|---|
  | **C** | payer `PY01` pays 6 different contracts; contract `HP-0042` pays 1–2 days before due in every period; duplicate payment pair; negative refunds (2% of rows); status `C` = cancelled rows that the brief says to exclude |
  | **A** | duplicate invoice `INV-7781` paid twice within 2 days; split payments of 3 × 48,000 against a 50,000 limit; maker = checker user `U017`; vendor `V-099` with a digit anomaly (Benford); round amounts clustered at vendor `V-120` |

- Briefs are written in Thai like a real auditor:
  - **C brief:** describes most columns, says the amount column is "ยอดชำระสุทธิ" (the planted conflict, because refunds are negative), and lists 3 risk concerns. One of them is mule-related, so its sufficiency is "ไม่พอ" and it produces a data request for deposit transactions.
  - **A brief:** lists 2 concerns and leaves the Benford/SoD risks to be suggested.

- [ ] **Step 1: Write failing tests:**
  - `test_c_deterministic` and `test_a_deterministic`
  - `test_planted_cases_grounded` (recompute each planted case from the data, independently of the key)
  - `test_variants_same_content` (the 3 variants differ only in column names)
  - `test_brief_mentions_conflict_column`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the generators.** Normal rows must not trigger any check (business hours, stable amounts, no near-limit amounts), as in the B1 generator.
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit** the generators and the generated files.

---

### Task 5: New certified checks

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`, and `aida-knowledge/knowledge/AIDA-14-configuration-registry.md` (v1.2 rows + Machine Config keys from Global Constraints; version line; history row)
- Create: `aida-knowledge/tests/test_checks_ca.py`

**Interfaces:**
- Consumes: `to_internal` (Task 2) and `evidence_rows` (B1).
- Produces: `CHECKS: dict[str, dict]`. Its key is the check_id and its value is {func, risk, skill_family, requires: [roles], registry: [keys], data_types: [...]}, covering every certified check including the migrated B1 ones. Each new check has the signature `(tables: dict, cfg: dict) -> pd.DataFrame` and returns the Evidence schema plus `roles_used`.

  | Check | Risk | Rule |
  |---|---|---|
  | `GEN-CONC` | G/A-R4 | share/HHI by entity or counterparty (`CONC.*`) |
  | `GEN-PERIOD-END` | G-R2 | `TEMP.PERIOD_END.WINDOW` |
  | `DUP-PAY` | A-R1 / C-R3 | same entity + counterparty + amount (+ document_no if present) within `DUP.WINDOW_DAYS` |
  | `SPLIT-LIMIT` | A-R2 | ≥ `SPLIT.MIN_TX` transactions by the same entity to the same counterparty within `SPLIT.WINDOW_DAYS`, each in `FOR.THRESHOLD_AVOID.BAND` of `limit`, summing above `limit` |
  | `FOR-BENFORD` / `FOR-ROUND` / `FOR-REPEAT` | G-R4 | existing FOR.* keys |
  | `SOD-SAME-USER` | A-R3 | `created_by == approved_by` (non-empty) |
  | `DUE-NEAR` | C-R2 | per contract, share of periods paid 0–`DUE.NEAR_DAYS` days before `due_date` ≥ `DUE.MIN_SHARE`, with ≥ `DUE.MIN_PERIODS` periods |
  | `PAYER-MULTI` | C-R1 | counterparty paying ≥ `PAYER.MIN_CONTRACTS` distinct contracts whose entity differs from the counterparty |

- [ ] **Step 1: Write failing tests:**
  - per check: `test_<check>_finds_planted` (C/A answer keys) and `test_<check>_no_false_positive` (no normal id flagged)
  - `test_checks_registry_keys_exist`
  - `test_checks_skip_reason_names_missing_roles`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement the checks and update AIDA-14** (validator must still pass: table rows agree with the Machine Config).
- [ ] **Step 4: Run** the full suite on both pandas versions and `python3 aida-knowledge/tools/validate_pack.py aida-knowledge`. Expected: PASS / OK.
- [ ] **Step 5: Commit.**

---

### Task 6: Risk Library, sufficiency and risk suggestions

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`
- Create: `aida-knowledge/tests/test_risk_library.py`

**Interfaces:**
- Produces:
  - `RISK_LIBRARY: dict[str, dict]`, keyed by risk_id, with {name_th, description_th, synonyms: [th/en phrases], data_types, checks: [check_id], min_roles: [roles], min_data: {months, rows}, request_if_missing: {role: Thai data request text}}. It covers every risk ID in Global Constraints.
  - `match_concerns(concerns: list[str]) -> list[dict]` returning {concern, risk_id | None, matched_by}. A concern with no match gives risk_id None and mode "สำรวจ".
  - `assess_sufficiency(risk_ids, roles_confirmed, profile, cfg) -> pd.DataFrame` with risk_id, status (พร้อม/บางส่วน/ไม่พอ), runnable_checks, skipped_checks with reasons, and data_request (list).
  - `suggest_risks(requested_ids, roles_confirmed, tables, cfg) -> pd.DataFrame` with risk_id, name_th, why_th and preview (a count computed by actually running the risk's checks on the data). The output is sorted by preview desc then risk_id and excludes the requested risks.
  - `plan(risk_ids, roles_confirmed, profile, cfg) -> pd.DataFrame` (check_id, decision Run/Skip, reason, missing). This replaces gate_capability for C1 runs and keeps its Thai reason style.

- [ ] **Step 1: Write failing tests:**
  - `test_library_covers_all_ids`
  - `test_library_checks_exist_in_CHECKS`
  - `test_match_concerns_synonyms_and_unmatched` (Review Focus 2)
  - `test_sufficiency_c_matches_key` and `test_sufficiency_a_matches_key`
  - `test_sufficiency_partial_on_poor_join` (Review Focus 3)
  - `test_data_request_c_matches_key`
  - `test_suggest_risks_a_matches_key`
  - `test_suggest_deterministic`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite on both pandas versions. Expected: PASS.
- [ ] **Step 5: Commit.**

---

### Task 7: inspect / confirm / run, intake.json and mapping profiles

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py`
- Create: `aida-knowledge/tests/test_orchestration.py`

**Interfaces:**
- Produces:
  - `inspect(files: dict[str, str] | list[str], brief: dict | None = None, mapping: str | dict | None = None, cfg: dict | None = None, registry_path: str | None = None) -> dict`.
    - `brief` = {context: str, columns: {col: meaning}, conditions: [str], concerns: [str], materiality: {...}|None}. It is structured by the LLM from free text; see Task 10 Instructions.
    - It reads files as text (CSV/XLSX, every sheet), computes the sha256 and data_ref, applies B1 date/amount parsing, and runs profile, suggest_roles, check_descriptions, match_concerns, assess_sufficiency, suggest_risks and plan.
    - It returns `{"intake": draft, "review_th": str}`. `review_th` is the Thai Intake Review text with sections A–E exactly as spec §4.3, every number from the engine, ending with the confirmation line.
  - `confirm(intake: dict, answers: dict, path: str = "intake.json") -> dict`. `answers` keys: roles {col: role}, filters [{column, op, value}], org_values {KEY: value}, add_risks [risk_id], materiality {"type": "ก"|"ข"|"ไม่ระบุ", ...}, reviewer str. It validates the answers, rejecting duplicate role targets (Review Focus 1) and an unknown KEY or risk_id with Thai messages, writes `intake.json` and returns the confirmed intake.
  - `run(files, intake: dict | str, out_dir: str = ".") -> dict`. It re-reads the files, verifies their sha256 against the intake (and warns in Thai if they changed), applies filters and org_values, runs the planned checks, unify, assess, auto money flow (E), outputs and the run log, and returns {findings, paths: {workbook, csv_dir, dashboard}, summary_th}.
  - `trace(files, intake, acct, direction="both", period=None, out_dir=".") -> dict`.
  - `save_mapping(intake, path: str) -> str` and `load_mapping(path) -> dict`. In `inspect(..., mapping=...)` the result has `changes: {added: [...], removed: [...], changed_pattern: [...]}`, and the review asks only about those.

- [ ] **Step 1: Write failing tests:**
  - `test_inspect_c_review_sections` (A–E present; the conflict on the amount column listed; the C data request present)
  - `test_confirm_rejects_duplicate_role` (Review Focus 1)
  - `test_confirm_unknown_key_message_thai`
  - `test_run_c_findings_match_key` and `test_run_a_findings_match_key`
  - `test_run_e_matches_b1_key`
  - `test_run_from_intake_json_fresh_process` (Review Focus 5: a subprocess runs `run(files, "intake.json")`, with equal findings)
  - `test_run_warns_when_file_changed`
  - `test_org_value_override_recorded`
  - `test_mapping_reuse_reports_only_changes` (Review Focus 4)
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Reuse B1 `prep_*`, `prof_*`, `unify_findings`, `assess_cmp`, `select_auto_trace`, `flow_trace`, `out_*` and `log_run` through the role adapter.
- [ ] **Step 4: Run** the full suite on both pandas versions. Expected: PASS.
- [ ] **Step 5: Commit.**

---

### Task 8: Exploratory mode, promotion and new outputs

**Files:**
- Modify: `aida-knowledge/engine/aida_engine.py` (including the `DASHBOARD_TEMPLATE` Intake tab and the exploratory badge)
- Create: `aida-knowledge/tests/test_explore_outputs.py`

**Interfaces:**
- Produces:
  - `data(files, intake) -> dict[str, pd.DataFrame]`: internal frames with filters applied, custom roles included, and original column names available via `df.attrs["original_names"]`.
  - `explore_log(question: str, code: str, result, note: str = "", intake=None) -> str`. It returns `explore_id` ("EXP-<n>"), appends to the module-level `EXPLORE_LOG`, and persists to `explore_log.json` next to `intake.json`.
  - `promote(explore_id, entity, risk, period, reason, reviewer) -> dict` (Finding row). It enforces Confidence ≤ "กลาง", requires a non-empty `reviewer` and a risk in RISK_LIBRARY or "RX", and sets `source="exploratory"` and the label.
  - `run` merges promoted findings and writes the new Workbook sheets `Intake_Review`, `Data_Dictionary`, `Data_Request` and `Exploratory` (spec §6). The order is README, Intake_Review, Data_Dictionary, Data_Request, Dataset_Profile, Analysis_Plan, Evidence, Findings, Exploratory, Mule_Networks, Money_Flow, Materiality, Run_Log.
  - The dashboard gains an "Intake" tab and the badge "จากโหมดสำรวจ". The Mule Networks and Money Flow tabs are hidden when the data is not type E.

- [ ] **Step 1: Write failing tests:**
  - `test_explore_log_persists_code_and_result`
  - `test_promote_caps_confidence`
  - `test_promote_requires_reviewer`
  - `test_promote_rx_allowed`
  - `test_workbook_new_sheets_order`
  - `test_dashboard_intake_tab_and_badge` (Playwright: no console errors, no external requests, badge visible)
  - `test_outputs_keep_xss_and_formula_guards`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full suite on both pandas versions. Expected: PASS.
- [ ] **Step 5: Commit.**

---

### Task 9: Column-name variants, end-to-end regression and performance

**Files:**
- Create: `aida-knowledge/tests/test_variants_e2e.py`

**Interfaces:**
- Consumes: Tasks 3–8.

- [ ] **Step 1: Write failing tests:**
  - `test_variants_same_findings[C/A/E × en/th/legacy]`: each variant goes through inspect, then confirm with that variant's roles json, then run, and gives findings equal to the key.
  - `test_suggest_roles_en_th_high_confidence` (≥ 80% of mapped columns at level สูง for en/th)
  - `test_legacy_requires_confirmation` (cryptic columns "ไม่ทราบ" or ต่ำ)
  - `test_perf_80k_e_inspect_run` (inspect + run on 80k E rows: inspect ≤ 30 s, run ≤ 90 s locally)
  - `test_thai_dates_be_variants_still_match`
- [ ] **Step 2: Run them.** Expected: FAIL where gaps exist. Fix in the engine; the tests are not changed to pass.
- [ ] **Step 3: Run** the full suite on both pandas versions. Expected: PASS.
- [ ] **Step 4: Commit.**

---

### Task 10: Knowledge pack v3.0, Instructions, validator, eval and release

**Files:**
- Create/replace in `aida-knowledge/knowledge/`:
  - `AIDA-16`: `aida_engine.py` (approach 3) or `AIDA-16-engine-install.md` (approach 2), per the spike result.
  - `AIDA-17-roles-schema.md` (replaces AIDA-17-data-evidence-schema.md)
  - `AIDA-18-risk-library.md` (replaces the analysis recipes; generated from `RISK_LIBRARY` + `CHECKS`)
  - `AIDA-19-engine-guide.md` (replaces the pipeline recipes)
  - Delete `AIDA-16-output-templates.md` (the template now lives in the engine).
- Modify:
  - `AIDA-00` (index, C1), `AIDA-15` (FAQ for C1), `AIDA-agent-instructions.md` (new flow; ≤ 8,000 characters)
  - `aida-knowledge/README.md`, `aida-knowledge/tests/eval-questions.md` (Q33–Q47)
  - `aida-knowledge/tools/validate_pack.py` + tests: engine checks per spec §7.5; remove the recipe-card checks that no longer apply; check that the Risk Library in AIDA-18 matches the engine.
- Create: `aida-knowledge/tools/build_risk_library_md.py` (generates the AIDA-18 tables from the engine)

**Interfaces:**
- Consumes: the spike result. If it is still unknown when this task starts, build approach 2 (the SharePoint install doc) and also ship `aida_engine.py` in the zip under `5-engine/`. The controller rules on the switch once results arrive.
- Instructions flow:
  1. The auditor's free text → `brief` dict.
  2. `inspect` → show `review_th` verbatim.
  3. Confirmation rules (accept words or edits = confirm; missing materiality = ไม่ระบุ; unanswered D = add none).
  4. `confirm` → `run` in the same reply.
  5. Questions outside the cards → exploratory mode steps (spec §4.5).
  6. `promote` only on an explicit auditor request naming the reviewer.
  7. `save_mapping` when the auditor asks.
  8. Never compute numbers in the LLM.

  Keep phase-A rules 1–6.

- [ ] **Step 1: Write failing validator tests:**
  - `test_engine_version_matches_index`
  - `test_engine_registry_version_matches_aida14`
  - `test_engine_cfg_keys_exist`
  - `test_engine_no_network_imports`
  - `test_risk_library_md_matches_engine`
  - `test_pack_has_20_files`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the docs, Instructions and validator changes.** Add eval Q33–Q47 per spec §7.4, using the briefs in `samples/*/brief.md`, each tagged with its Checklist item.
- [ ] **Step 4: Run** the validator (expect `OK: 20 files validated`), and the tools and tests suites on both pandas versions.
- [ ] **Step 5: Build the release zip** `/tmp/claude-0/-home-user-CP3-Saksorn-Pawasakarin/a27e31ad-493a-5ef6-87b3-fb57866bc471/scratchpad/AIDA-Knowledge-Pack-v3.0.zip`:
  - `1-upload-knowledge/` (20 files)
  - `2-paste-instructions/`
  - `3-test/eval-questions.md`
  - `4-samples/{E,C,A}/` (data, brief.md, answer_key.json)
  - `5-engine/aida_engine.py`
  - `6-spike-c1/`
  - `README.md`

  List it.
- [ ] **Step 6: Commit and push.**
