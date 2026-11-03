# AIDA Phase B1 (Mule Accounts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let AIDA analyse real transaction files in Copilot Code Interpreter for use case 1 ("Potential Unusual Transactions across Mule Accounts"). The analysis code comes from tested, versioned recipe cards, and the run produces an Excel workbook, network CSVs and a self-contained HTML dashboard.

**Architecture:** Recipe cards are fenced ```python blocks inside the Markdown knowledge files AIDA-18 (analysis) and AIDA-19 (pipeline). `tools/extract_recipes.py` executes those exact blocks so the repo tests run the same code Copilot runs. Thresholds live in a JSON "Machine Config" block in AIDA-14 and reach recipes as `cfg`. Synthetic sample data with planted cases plus an answer key drive unit and end-to-end tests.

**Tech Stack:** Python 3, pandas (recipes must also work on pandas ≥ 1.5), numpy, openpyxl, standard-library `unittest`. Markdown knowledge files. No networkx, no scikit-learn.

**Spec:** `docs/superpowers/specs/2026-11-03-aida-phase-b1-design.md`. Read sections 4–7 before each task. The phase A spec and validator (`aida-knowledge/tools/validate_pack.py`) still apply.

## Global Constraints

- The knowledge folder holds exactly 20 files after this plan. The new files are `AIDA-16-output-templates.md`, `AIDA-17-data-evidence-schema.md`, `AIDA-18-analysis-recipes.md` and `AIDA-19-pipeline-recipes.md`.
- Each recipe is one fenced ```python block whose first two lines are exactly:
  `# RECIPE <ID> v<major.minor> | Skill: <skill> | Risk: <R1-R4 or ->` and
  `# Registry: <KEY[, KEY...] or -> | Input: <tables(columns)>`.
- The function name is the recipe ID in lower case, with `-` replaced by `_`. The code is at most 40 lines; the only exception is the dashboard template block in AIDA-16, which is a ```html block, not a recipe.
- An analysis recipe has the signature `def <name>(tables: dict, cfg: dict) -> pd.DataFrame` and returns rows in Evidence schema (spec 4.4). An empty DataFrame means nothing was found.
- Recipes contain no threshold literals. Every threshold is read as `cfg["<REGISTRY.KEY>"]`, and the runtime context is read as `cfg["_RUN"]`.
- `tables` keys are: `"transactions"` (required), `"accounts"` (optional), `"evidence"` (the DataFrame of earlier evidence, given to the MULE-* aggregators) and `"_out"` (a dict where a card may put extra frames, such as `mule_networks`).
- Recipes may only import pandas, numpy and the standard library; OUT-WORKBOOK may also import openpyxl. They must avoid pandas APIs added after 1.5.
- Wording in every user-facing string follows AIDA-11. Use "สอดคล้องกับ Mule Account pattern"; never use บัญชีม้า, ทุจริต or similar, except under a Guardrails heading. The validator already enforces this.
- Registry v1.1 uses the keys and values in spec 4.6, plus `MULE.DWELL_MIN_PAIRS = 3` and `MULE.NEW_ACCT_MIN_TX = 20` (Ruling R-1 below).
- Card count: the spec's 24 cards plus `CORE-EVIDENCE` (Ruling R-2) makes 25.

**Rulings carried from planning**
- **R-1:** The spec does not define how many inflow/outflow pairs make a "short dwell" signal, or what "many transactions" means for a new account. Two keys are added: `MULE.DWELL_MIN_PAIRS = 3` and `MULE.NEW_ACCT_MIN_TX = 20` (transactions within `MULE.NEW_ACCT_DAYS`). Task 2 updates the spec table.
- **R-2:** Every analysis card needs a shared Evidence builder. It becomes card `CORE-EVIDENCE` in AIDA-19, which is loaded first. Task 2 updates the spec card count to 25.
- **R-4:** MULE-DWELL and MULE-NEW-ACCT emit R1 signal evidence; the spec's R1 card list omits them. They are signals that MULE-PATTERN absorbs into R2, the same as NET-FUNNEL. Task 2 adds them to the spec 4.4 R1 row.
- **R-3:** Machine Config keys must exist in AIDA-14, either as a `` `KEY = value` `` reference or as a `### KEY` heading (needed for `ASSESS.PRIORITY` and `ASSESS.CONFIDENCE`).

## Review Focus

1. **Mixed-format timestamps** (strings, Excel serials, timezone-aware) in `ts` or `opened_at`. PREP-MAP must coerce them to naive datetimes and STOP with a reason if more than (1 − `GATE.COMPLETENESS.MIN`) cannot be parsed. Test: `test_prep_map_mixed_timestamps` (Task 6).
2. **Duplicate `tx_id`.** PROF-PROFILE must report the duplicates and STOP, because the record key is not unique. Test: `test_profile_duplicate_tx_id_stops` (Task 6).
3. **Self-transfers (`from_acct == to_acct`) and zero or negative amounts.** These are excluded from network, flow and dwell analysis, and the excluded count is shown in the Dataset Profile. Test: `test_self_and_nonpositive_excluded` (Task 6).
4. **An account with no outflow at all.** MULE-DWELL and NET-FUNNEL must not divide by zero; the account gets no signal. Test: `test_no_outflow_account_no_signal` (Task 4).
5. **A recipe block truncated mid-function**, which simulates partial retrieval. `extract_recipes` must raise `RecipeError` naming the card instead of exec-ing broken code. Test: `test_truncated_recipe_raises` (Task 1).

---

### Task 1: Spike kit and recipe extraction tool

**Files:**
- Create: `aida-knowledge/spike/README.md`, `aida-knowledge/spike/AIDA-SPIKE-recipes.md`, `aida-knowledge/spike/spike-transactions.csv`
- Create: `aida-knowledge/tools/extract_recipes.py`
- Test: `aida-knowledge/tools/test_extract_recipes.py`

**Interfaces:**
- Produces:
  - `class RecipeError(Exception)`.
  - `parse_recipes(md_text: str) -> list[Recipe]`. `Recipe` is a dataclass with fields `id: str`, `version: str`, `skill: str`, `risk: str`, `registry_keys: list[str]`, `inputs: str`, `code: str` and `func_name: str`.
  - `load_recipes(paths: list[Path]) -> dict[str, Callable]`. It execs every block, in file order, into one shared namespace that already holds `pd`, `np` and `json`. It returns a map from function name to function. It raises `RecipeError` when a block fails `compile()` or does not define its expected function.
- `spike-transactions.csv`: 200 rows with columns tx_id, ts, from_acct, to_acct, amount, channel. It contains one funnel account, `F01`, which receives from 12 sources and forwards 85% within 3 days.
- `AIDA-SPIKE-recipes.md`: a temporary knowledge file uploaded only for the spike. It holds a NET-FUNNEL card (any correct version, ≤ 40 lines) and an ~120-line `html` block that ends with the marker comment `<!-- END-OF-TEMPLATE -->`.
- `spike/README.md`: 4 prompts (spec 7.1), a results table (pass/fail, pandas version, largest file size tried, notes) and the removal step after the spike.

- [ ] **Step 1: Write failing tests.** Tests:
  - `test_parse_header_fields`: a sample card parses to id `NET-FUNNEL`, version `1.0`, risk `R1` and registry_keys `["NET.FUNNEL"]`.
  - `test_load_defines_function`
  - `test_truncated_recipe_raises`: a card cut after half its lines raises `RecipeError` whose message contains `NET-FUNNEL`.
  - `test_missing_function_raises`
  - `test_shared_namespace`: block 2 can call a helper defined in block 1.
- [ ] **Step 2: Run** `cd aida-knowledge/tools && python3 -m unittest test_extract_recipes -v`. Expected: an import failure.
- [ ] **Step 3: Implement `extract_recipes.py`** to the Interfaces.
- [ ] **Step 4: Run the tests again.** Expected: all pass.
- [ ] **Step 5: Build the spike files.** Check that the spike NET-FUNNEL card, loaded by `load_recipes`, flags `F01` on `spike-transactions.csv` (a one-off assertion in the README "expected result" line).
- [ ] **Step 6: Commit and push.** Then **STOP: ask the user to run the spike and report the results table.** If any item fails, write a `Ruling:` that adjusts the design (for example, splitting the template into numbered parts) before Task 2.

---

### Task 2: Registry v1.1, Machine Config, schema file and validator extensions

**Files:**
- Modify: `aida-knowledge/knowledge/AIDA-14-configuration-registry.md` (version 1.1, new key rows from spec 4.6 + R-1, `` `REGISTRY.VERSION = 1.1` ``, a `## Machine Config (สำหรับ recipe)` JSON block and a change-history row)
- Create: `aida-knowledge/knowledge/AIDA-17-data-evidence-schema.md` (spec 4.1, 4.4, the risk table and the Data Reference formats)
- Modify: `aida-knowledge/tools/validate_pack.py`, `aida-knowledge/tools/test_validate_pack.py`
- Modify: `docs/superpowers/specs/2026-11-03-aida-phase-b1-design.md` (R-1 keys in 4.6; 25 cards with CORE-EVIDENCE in 4.3)

**Interfaces:**
- Produces, in `validate_pack.py`:
  - `parse_machine_config(path: Path) -> tuple[dict, list[str]]`
  - `check_machine_config(registry_path: Path) -> list[str]`. It checks that every top-level key except `_`-prefixed keys exists per R-3.
  - `check_recipes(path: Path, registry_keys: set[str]) -> list[str]`. It checks the header format, the ≤ 40 code-line limit, and that every `cfg["X"]` key (X without a `_` prefix) is a registry key. It runs only on files that contain recipe blocks.
  - `validate()` calls all three.
- Machine Config JSON, with exactly these keys and values:
  ```json
  {"REGISTRY.VERSION": "1.1", "GATE.COMPLETENESS.MIN": 0.95, "GATE.SAMPLE.MIN": 30,
   "STAT.MAD.THRESHOLD": 3.5, "BEH.BASELINE.MIN_PERIODS": {"velocity_days": 6, "spike_months": 6},
   "BEH.DEVIATION": 3, "TEMP.OFF_HOURS": {"start": "08:00", "end": "18:00", "weekend": true},
   "NET.CYCLE": {"min_len": 2, "max_len": 5, "days": 30},
   "NET.FUNNEL": {"min_sources": 10, "out_ratio": 0.8, "days": 7},
   "MULE.DWELL_HOURS": 24, "MULE.DWELL_MIN_PAIRS": 3, "MULE.NEW_ACCT_DAYS": 30, "MULE.NEW_ACCT_MIN_TX": 20,
   "MULE.MIN_SIGNALS": 3, "MULE.CROSS.MIN_LINKS": 2, "MULE.NETWORK.MIN_SIZE": 3,
   "CPTY.NEW_RATIO": 0.5, "CPTY.NEW_LARGE.MULTIPLIER": 5,
   "FLOW.MAX_HOPS": 4, "FLOW.WINDOW_DAYS": 7, "FLOW.MIN_PASS_RATIO": 0.9, "FLOW.AUTO_MAX_ENTITIES": 10,
   "ASSESS.CLEARLY_TRIVIAL": 0.05,
   "ASSESS.PRIORITY": {"สูง": {"สูง": "สูง", "กลาง": "กลาง", "ต่ำ": "ต่ำ"},
                       "กลาง": {"สูง": "สูง", "กลาง": "กลาง", "ต่ำ": "ต่ำ"},
                       "ต่ำ": {"สูง": "กลาง", "กลาง": "ต่ำ", "ต่ำ": "ต่ำ"}}}
  ```
  `ASSESS.PRIORITY` keys are Confidence first, then Materiality. They must match the `### ตาราง Priority` markdown table, ignoring the "+ Human Review" note.

- [ ] **Step 1: Write failing tests** in `test_validate_pack.py`:
  - `test_machine_config_unknown_key`: an unknown key gives 1 error.
  - `test_machine_config_heading_key_ok`: a key defined only as `### ASSESS.PRIORITY` gives `[]`.
  - `test_machine_config_underscore_exempt`
  - `test_recipe_header_malformed`
  - `test_recipe_over_40_lines`
  - `test_recipe_cfg_unknown_key`
  - `test_recipe_cfg_run_context_ok`: `cfg["_RUN"]` gives `[]`.
  - `test_priority_json_matches_table`: parses the real AIDA-14 and asserts the JSON equals the table.
- [ ] **Step 2: Run** `cd aida-knowledge/tools && python3 -m unittest test_validate_pack`. Expected: the new tests fail.
- [ ] **Step 3: Implement the validator functions,** then edit AIDA-14 and create AIDA-17 (standard skeleton; Guardrails cover "full sensitive data shown — access control is the organisation's").
- [ ] **Step 4: Run the tests** and `python3 aida-knowledge/tools/validate_pack.py aida-knowledge`. Expected: tests pass and the pack is `OK: 17 files validated`.
- [ ] **Step 5: Commit.**

---

### Task 3: Sample data generator and answer key

**Files:**
- Create: `aida-knowledge/tests/make_sample_data.py`, `aida-knowledge/tests/test_sample_data.py`
- Generated (committed): `aida-knowledge/samples/transactions.csv`, `aida-knowledge/samples/accounts.csv`, `aida-knowledge/samples/answer_key.json`

**Interfaces:**
- Produces:
  - `make(seed: int = 20261103) -> tuple[pd.DataFrame, pd.DataFrame, dict]`, which returns transactions, accounts and the answer key.
  - `main()` writes the 3 files.
- Normal data:
  - Accounts `A0001`–`A0300`; about 5,000 transactions from 2026-01-01 to 2026-08-31.
  - Weekdays, 09:00–17:00 only; amounts lognormal.
  - Each normal account has ≥ 6 active months and stable daily counts.
  - Normal accounts never meet any planted rule.
- Planted cases, all in 2026-08, with IDs fixed:
  - Funnel `F01`: sources `FS01`–`FS12`, out to `FO01`.
  - Cycle `C01`→`C02`→`C03`→`C01`.
  - Outlier transaction `TX-OUT-1` on account `O01`.
  - Velocity `V01`.
  - Off-hours `H01`.
  - Single mule `M01`: opened 2026-08-01, with dwell, funnel and velocity signals.
  - Network: mules `N01`–`N04` (each with ≥ 3 signals), feeder `NF1` → N01–N04, and N01–N04 → collector `NC1`.
  - New large counterparty: `P01` → `PX1` at 10× P01's median.
  - Layering `L01`→`L02`→`L03`→`L04`→`L05`, each hop forwarding ≥ 92% within 1 day.
- `answer_key.json` contains:
  - `{"recipes": {<RECIPE-ID>: [entity_ids]}, "mule_accounts": [...], "networks": [{"members": [...], "roles": {...}}], "unified_findings": <int>, "no_accounts_basis": "first_seen"}`.
  - Every planted case appears under every recipe that should flag it.

- [ ] **Step 1: Write failing tests:**
  - `test_deterministic`: two calls give identical frames.
  - `test_normal_accounts_business_hours`
  - `test_planted_ids_present`
  - `test_answer_key_shape`
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_sample_data`. Expected: an import failure.
- [ ] **Step 3: Implement the generator and run `main()`.**
- [ ] **Step 4: Run the tests.** Expected: they pass.
- [ ] **Step 5: Commit the generator, tests and generated samples.**

---

### Task 4: Account-level analysis recipes (AIDA-18, part 1)

**Files:**
- Create: `aida-knowledge/knowledge/AIDA-18-analysis-recipes.md` (skeleton plus cards, each under its own `### <ID>` heading with a 2-line Thai purpose note)
- Create (in AIDA-19): the `CORE-EVIDENCE` card only, so recipes can load
- Create: `aida-knowledge/knowledge/AIDA-19-pipeline-recipes.md`
- Test: `aida-knowledge/tests/test_recipes.py`

**Interfaces:**
- Consumes: `load_recipes` (Task 1), the sample data and answer key (Task 3), and the Machine Config (Task 2). The test helper is `cfg = machine_config | {"_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}}`.
- Produces, as the CORE-EVIDENCE card:
  - `evidence_rows(recipe_id: str, version: str, skill_family: str, risk: str, registry_key: str, found: pd.DataFrame, cfg: dict) -> pd.DataFrame`.
  - `found` has the columns entity_id, period, metric, value, threshold, explanation and record_refs.
  - The output has the Evidence columns of spec 4.4, in order, with `entity_type="account"` unless `found` has `entity_type`.
  - `evidence_id` is `f"{recipe_id}-{run_id}-{i}"`, `registry_version` comes from `cfg["REGISTRY.VERSION"]` and `data_ref` from `cfg["_RUN"]["data_ref"]`.
- Produces these cards: `STAT-MAD`, `BEH-VELOCITY`, `BEH-SPIKE`, `TEMP-OFFHOURS`, `NET-CYCLE`, `NET-FUNNEL`. All are R1, use the spec 4.3 methods and use period YYYY-MM. Their functions are `stat_mad`, `beh_velocity`, `beh_spike`, `temp_offhours`, `net_cycle` and `net_funnel`.
- Shared rule: self-transfers and amount ≤ 0 are excluded inside each card.

- [ ] **Step 1: Write failing tests,** one class per card. Each test asserts:
  - `set(answer_key["recipes"][ID]) <= found_ids`
  - no found id starts with `"A"`
  - the evidence columns equal the spec 4.4 list.
  Also write `test_no_outflow_account_no_signal`: for NET-FUNNEL, an account with 15 inflows and 0 outflows produces no row.
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_recipes`. Expected: `RecipeError` or a missing function.
- [ ] **Step 3: Write the 6 cards and CORE-EVIDENCE.** NET-CYCLE uses an iterative DFS bounded by `max_len` and by a time window of `days` from the first edge.
- [ ] **Step 4: Run the tests and the validator.** Expected: tests pass and the validator is OK.
- [ ] **Step 5: Commit.**

---

### Task 5: Mule, counterparty and money flow recipes (AIDA-18, part 2)

**Files:** Modify `AIDA-18-analysis-recipes.md`; Test `aida-knowledge/tests/test_recipes.py`

**Interfaces:**
- Consumes: CORE-EVIDENCE and the Task 4 cards.
- Produces these cards:
  - `MULE-DWELL` (`mule_dwell`), `MULE-NEW-ACCT` (`mule_new_acct`), `CPTY-PROFILE` (`cpty_profile`, R4) and `CPTY-NEW-LARGE` (`cpty_new_large`, R4). These are analysis signature; MULE-DWELL and MULE-NEW-ACCT are risk R1 signals.
  - `MULE-PATTERN` (`mule_pattern`, R2). It reads `tables["evidence"]`. Its signals are NET-FUNNEL, MULE-DWELL, MULE-NEW-ACCT, BEH-VELOCITY and TEMP-OFFHOURS evidence, counted per account and month. It emits when the count is ≥ `MULE.MIN_SIGNALS`, with `value` = count and `explanation` listing the signal names.
  - `MULE-CROSS-TX` (`mule_cross_tx`, R3, entity_type `"account"`, metric `role`, value `mule_to_mule` / `collector` / `feeder`). It follows spec 4.7.
  - `MULE-NETWORK` (`mule_network`, R3). It returns Evidence rows with `entity_type="network"` and entity_id `NET-<n>` ordered by size, then lowest member id. It also returns a second frame through `tables["_out"]["mule_networks"]`, matching the Mule Network schema.
  - `FLOW-TRACE` (`flow_trace(tables, cfg, start_acct: str, direction: str) -> pd.DataFrame`). It returns trail rows in the Money Flow trail schema, not evidence. Each hop's ts must be ≥ the previous hop's ts and within `FLOW.WINDOW_DAYS` of the first.
  - `FLOW-LAYERING` (`flow_layering`, R1). It requires ≥ 3 consecutive hops, each passing ≥ `FLOW.MIN_PASS_RATIO`.
- MULE-NEW-ACCT `basis`: it uses `opened_at` when `tables["accounts"]` exists and has `opened_at`, and `first_seen` otherwise. The basis is written into `explanation` as `basis=opened_at|first_seen`.

- [ ] **Step 1: Write failing tests:**
  - per-card answer-key tests as in Task 4
  - `test_mule_new_acct_first_seen_basis`: with accounts removed, M01 is still flagged and the explanation contains `basis=first_seen`
  - `test_mule_network_roles`: one network with members N01–N04, NF1 and NC1, and roles as in the key
  - `test_flow_trace_respects_time_order`
  - `test_flow_trace_max_hops`: a trace from L01 forward has ≤ 4 hops
  - `test_mule_pattern_wording`: no explanation contains `บัญชีม้า`.
- [ ] **Step 2: Run the tests.** Expected: they fail.
- [ ] **Step 3: Write the cards.** MULE-NETWORK uses union-find over mule_to_mule, collector and feeder edges.
- [ ] **Step 4: Run the tests and the validator.** Expected: they pass.
- [ ] **Step 5: Commit.**

---

### Task 6: Pipeline recipes (AIDA-19)

**Files:** Modify `AIDA-19-pipeline-recipes.md`; Test `aida-knowledge/tests/test_pipeline.py`

**Interfaces:**
- Produces these cards (Risk `-`):
  - `prep_map(raw: dict[str, pd.DataFrame], mapping: dict[str, dict[str, str]], cfg) -> dict`. It renames columns, coerces `ts`/`opened_at` to naive datetime and `amount` to float, and returns `tables` plus `tables["_prep"] = {"unparsed_ts": int, "excluded_self": int, "excluded_nonpositive": int}`.
  - `prof_profile(tables, cfg) -> tuple[pd.DataFrame, str]`. It returns a profile table and a status of `"OK"` or `"STOP: <reason>"`. It STOPs when `tx_id` is missing or duplicated, or when the unparsed-ts share is > 1 − `GATE.COMPLETENESS.MIN`.
  - `gate_capability(tables, cfg) -> pd.DataFrame`. Its columns are recipe_id, decision (Run/Skip), reason and missing. It has one row per analysis card, Skip reasons follow AIDA-03 wording, and an absent `accounts` table still gives MULE-NEW-ACCT a Run with the reason "basis=first_seen".
  - `unify_findings(evidence: pd.DataFrame, cfg) -> pd.DataFrame`. It implements spec 4.8 Unify and Mule absorption.
  - `assess_cmp(findings, tx: pd.DataFrame, materiality_amount: float | None, cfg) -> pd.DataFrame`. It implements spec 4.8 Confidence, Exposure, Materiality and Priority. When `materiality_amount` is None, materiality is "ไม่ได้ประเมิน".
  - `log_run(events: list[dict], cfg) -> pd.DataFrame`. It produces the Run Log schema.

- [ ] **Step 1: Write failing tests:**
  - `test_prep_map_mixed_timestamps`
  - `test_profile_duplicate_tx_id_stops`
  - `test_profile_missing_tx_id_stops`
  - `test_self_and_nonpositive_excluded`
  - `test_gate_no_ts_skips_time_cards`: VELOCITY, OFFHOURS, DWELL, CYCLE, FUNNEL, FLOW-* and CPTY-* are Skipped, each with a reason
  - `test_unify_absorbs_r1_into_r2`
  - `test_assess_priority_table`
  - `test_assess_no_materiality`
  - `test_finding_count_matches_key`: running the whole chain on the sample data gives `answer_key["unified_findings"]` findings.
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_pipeline`. Expected: it fails.
- [ ] **Step 3: Write the cards.**
- [ ] **Step 4: Run all tests and the validator.** Expected: they pass.
- [ ] **Step 5: Commit.**

---

### Task 7: Outputs, dashboard template and end-to-end test

**Files:**
- Create: `aida-knowledge/knowledge/AIDA-16-output-templates.md` (workbook sheet specs from spec 6.1; CSV specs from spec 6.2; one ```html dashboard template with the placeholder `/*__AIDA_DATA__*/` and the sensitive-data banner text)
- Modify: `AIDA-19-pipeline-recipes.md` (`OUT-WORKBOOK`, `OUT-NETWORK-CSV`, `OUT-DASHBOARD`)
- Test: `aida-knowledge/tests/test_outputs.py`

**Interfaces:**
- Produces:
  - `out_workbook(bundle: dict, path: str, cfg) -> str`. The sheets follow spec 6.1, in order.
  - `out_network_csv(bundle, folder: str, cfg) -> list[str]`, which writes nodes.csv, edges.csv and flows.csv.
  - `out_dashboard(bundle, template: str, path: str, cfg) -> str`, which replaces the placeholder with `json.dumps(bundle_for_ui, ensure_ascii=False)`.
- `bundle` is a dict with the keys profile, plan, evidence, findings, mule_networks, flows, materiality, run_log and run_id.
- Dashboard behaviour:
  - It has 5 tabs (spec 6.3) and uses vanilla JS with an SVG circle layout for each network.
  - Node colour follows role.
  - The Money Flow view puts hops in columns from left to right.
  - It loads nothing external.

- [ ] **Step 1: Write failing tests:**
  - `test_workbook_sheet_order`: openpyxl reads the 9 sheets, and the README sheet contains the warning text
  - `test_network_csv_columns`
  - `test_dashboard_self_contained`: no `http://` or `https://` src/href, the embedded JSON parses, and there are 5 tab labels
  - `test_end_to_end_sample`: running the full chain on the samples produces files whose finding and network counts match the answer key.
- [ ] **Step 2: Run** `cd aida-knowledge/tests && python3 -m unittest test_outputs`. Expected: it fails.
- [ ] **Step 3: Write the template and the 3 cards.** Then open the generated HTML with Playwright (preinstalled Chromium), screenshot each tab and check that no JS console errors occur.
- [ ] **Step 4: Run all tests and the validator.** Expected: they pass, and the validator shows `OK: 20 files validated`.
- [ ] **Step 5: Commit.**

---

### Task 8: Instructions, index, README, eval and release zip

**Files:**
- Modify: `aida-knowledge/AIDA-agent-instructions.md` (rule 7 becomes the spec 5 flow with both confirmation points, verbatim-recipe use, the truncated-card rule, the B1 scope list and FLOW-TRACE on demand; routing rows for files 16–19; must stay ≤ 8,000 characters)
- Modify: `AIDA-00-index-principles.md` (files 16–19 no longer reserved), `aida-knowledge/README.md` (phase B steps, the PCI DSS/PDPA risk note, running the tests, removing the spike file), `aida-knowledge/tests/eval-questions.md` (Q22–Q31 from spec 7.5, each tagged with its Checklist item)

- [ ] **Step 1: Make the edits.**
- [ ] **Step 2: Run the full suite:**
  `python3 aida-knowledge/tools/validate_pack.py aida-knowledge && cd aida-knowledge/tools && python3 -m unittest && cd ../tests && python3 -m unittest`. Expected: everything passes, and the validator shows `OK: 20 files validated`.
- [ ] **Step 3: Build** `AIDA-Knowledge-Pack-v2.0.zip` in the scratchpad, using the same folder layout as v1.1, plus `4-samples/` (samples and answer key).
- [ ] **Step 4: Commit and push.**
