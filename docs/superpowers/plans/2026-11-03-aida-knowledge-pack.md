# AIDA Knowledge Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 16 Markdown knowledge files, an Agent Instructions file, an eval question set, and a validator script for the AIDA Agent (Microsoft 365 Copilot Agent Builder, phase A: advisor).

**Architecture:** Files are split by the kind of question users ask; each file can be read on its own (shared skeleton). `AIDA-14` is the only source of truth for default values; other files cite them as `` `KEY = value` `` and `validate_pack.py` checks they match. Content is Thai with English technical terms, taken from the 20 slides.

**Tech Stack:** Markdown, Python 3 standard library only (`re`, `pathlib`, `unittest`, `sys`).

**Spec:** `docs/superpowers/specs/2026-11-03-aida-knowledge-pack-design.md`. Read spec sections 3–6 before every task. The slide images are in `/root/.claude/uploads/a27e31ad-493a-5ef6-87b3-fb57866bc471/*.jpg`, and spec section 7 maps each slide to its file.

## Global Constraints

- Pack root: `aida-knowledge/`. Upload folder: `aida-knowledge/knowledge/`. It holds ≤ 20 files and only `.md` files.
- File names must match spec section 3.1 exactly, for example `AIDA-04-skill-statistical-concentration.md`.
- Every knowledge file uses the skeleton from spec section 4.1. The first line is `# AIDA-XX · <title>`. It must have a line that starts with `> ไฟล์นี้ตอบคำถาม:` and the headings `## สรุปสั้น`, `## ข้อห้าม (Guardrails)` and `## ไฟล์ที่เกี่ยวข้อง`. The header line is `> ไฟล์: AIDA-XX | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack`.
- Write every default value as `` `KEY = value` `` and copy it exactly from `AIDA-14`. Do not write any threshold number in prose without its key.
- Each time a default value is cited, add a note right after it: `(ค่ามาตรฐาน — ปรับได้ตามบริบทองค์กร, ดู AIDA-14)`.
- Accusatory words (`ทุจริต`, `กระทำผิด`, `กระทำความผิด`, `โกง`, `fraudster`) may appear only under `## ข้อห้าม (Guardrails)`, or on a line that contains `≠`, `ไม่`, `ห้าม` or `not`.
- `AIDA-agent-instructions.md` must be ≤ 8,000 characters.
- Cross-references use the form `AIDA-XX`. They must point to a file that exists, or to reserved slots 16–19.
- Do not write content for files 16–19. Do not add Python dependencies.

## Review Focus

1. A registry value that contains `/`, `%`, `,`, a range or Thai text must parse and compare exactly. Test: `test_parse_registry_complex_values` (Task 1).
2. A key defined twice in `AIDA-14` with different values must be an error, not silently resolved to the last value. Test: `test_parse_registry_duplicate_conflict` (Task 1).
3. A UTF-8 file with a BOM, as saved by Windows editors, must still pass the header checks. Test: `test_required_sections_with_bom` (Task 1).
4. An accusatory word in a negated sentence must pass, and the same word in a plain sentence must fail. Test: `test_accusatory_negated_ok` / `test_accusatory_plain_fails` (Task 1).
5. A threshold written as prose (for example "Z-Score เกิน 3") instead of key form would slip past the validator. Check: the grep step in Tasks 3–5 flags bare numbers next to threshold words.

---

### Task 1: Validator script and tests

**Files:**
- Create: `aida-knowledge/tools/validate_pack.py`
- Test: `aida-knowledge/tools/test_validate_pack.py`

**Interfaces:**
- Produces (all in `validate_pack.py`; each `check_*` returns `list[str]` of error messages that start with the file name, and an empty list means pass):
  - `REF_RE = re.compile(r"`([A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+) = ([^`]+)`")`
  - `parse_registry(path: Path) -> tuple[dict[str, str], list[str]]`. Returns all `KEY = value` pairs in the file, with the value stripped. If one key has two different values, it adds an error.
  - `check_file_count(knowledge_dir: Path, limit: int = 20) -> list[str]`
  - `check_required_sections(path: Path) -> list[str]`. Reads with `encoding="utf-8-sig"`.
  - `check_registry_refs(path: Path, registry: dict[str, str]) -> list[str]`. Errors on an unknown key or a mismatched value.
  - `check_accusatory_terms(path: Path) -> list[str]`. Tracks the current `## ` heading. Lines under `## ข้อห้าม (Guardrails)` are exempt, and lines that contain a negation marker are exempt.
  - `check_cross_refs(path: Path, existing: set[str], reserved: set[str] = {"16","17","18","19"}) -> list[str]`
  - `check_instructions_length(path: Path, limit: int = 8000) -> list[str]`
  - `validate(pack_dir: Path) -> list[str]`. Runs every check. The registry is `knowledge/AIDA-14-configuration-registry.md` (if it is missing, that is an error). Instructions are `AIDA-agent-instructions.md`, and that file is checked only for length.
  - `main(argv: list[str]) -> int`. Usage: `python3 validate_pack.py [pack_dir]`, where `pack_dir` defaults to the script's parent's parent. It prints each error, or `OK: <n> files validated`, and returns 1 or 0.

- [ ] **Step 1: Write failing tests** in `test_validate_pack.py` using `unittest` and `tempfile.TemporaryDirectory`, with a helper `write(dir, name, text)`. The tests:
  - `test_file_count_limit`: 21 `.md` files gives 1 error, and 20 gives `[]`.
  - `test_required_sections_ok`: a minimal valid skeleton gives `[]`.
  - `test_required_sections_missing_guardrails`: an error message contains `ข้อห้าม`.
  - `test_required_sections_with_bom`: a valid skeleton prefixed with `﻿` gives `[]`.
  - `test_parse_registry_complex_values`: the text `` `CONC.HHI = < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง` `` parses to that exact value.
  - `test_parse_registry_duplicate_conflict`: the same key with values `3` and `4` gives 1 error.
  - `test_registry_ref_match` / `test_registry_ref_mismatch` / `test_registry_ref_unknown_key`.
  - `test_accusatory_plain_fails`: `พบการทุจริตในรายการนี้` gives 1 error.
  - `test_accusatory_negated_ok`: `Anomaly Score ≠ การทุจริต` and `ไม่ใช่การกระทำผิด` give `[]`.
  - `test_accusatory_in_guardrails_ok`: the word under `## ข้อห้าม (Guardrails)` gives `[]`.
  - `test_cross_ref_missing` (`AIDA-21` gives an error) / `test_cross_ref_reserved_ok` (`AIDA-17` gives `[]`).
  - `test_instructions_length`: 8,001 characters gives an error, and 8,000 gives `[]`.
  - `test_validate_end_to_end`: a temp pack with a registry, one skill file citing it, and instructions gives `[]`.

- [ ] **Step 2: Run the tests and confirm they fail**
  Run: `cd aida-knowledge/tools && python3 -m unittest test_validate_pack -v`
  Expected: the import fails (`No module named validate_pack`) or every test fails.

- [ ] **Step 3: Implement `validate_pack.py`** using the Interfaces above.

- [ ] **Step 4: Run the tests and confirm they pass**
  Run: same command. Expected: `OK` with all tests passing.

- [ ] **Step 5: Commit**
  `git add aida-knowledge/tools && git commit -m "Add AIDA knowledge pack validator with tests"`

---

### Task 2: Configuration Registry (AIDA-14)

**Files:**
- Create: `aida-knowledge/knowledge/AIDA-14-configuration-registry.md`

**Interfaces:**
- Consumes: `validate_pack.py` (Task 1).
- Produces: the key set that every later task cites. Use exactly the keys and values in spec section 5. Write each as one table row: `` | `KEY = value` | ความหมาย | ที่มา | ``. Use these exact strings:
  - `` `GATE.COMPLETENESS.MIN = 95%` ``, `` `GATE.SAMPLE.MIN = 30` ``, `` `GATE.TRACE.REQUIRED = dataset + table + period + record key` ``
  - `` `STAT.ZSCORE.THRESHOLD = 3` ``, `` `STAT.IQR.K = 1.5 (mild) / 3.0 (extreme)` ``, `` `STAT.MAD.THRESHOLD = 3.5` ``, `` `STAT.PERCENTILE = P99 / P1` ``
  - `` `CONC.HHI = < 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง` ``, `` `CONC.SINGLE_ENTITY_SHARE = 10%` ``, `` `CONC.TOPN = 10` ``
  - `` `BEH.BASELINE.MIN_PERIODS = 6 งวด (แนะนำ 12)` ``, `` `BEH.PEER.MIN_SIZE = 5` ``, `` `BEH.DEVIATION = 3σ` ``
  - `` `TEMP.PERIOD_END.WINDOW = 3 วันทำการก่อนสิ้นงวด + 3 วันแรกของงวดถัดไป` ``, `` `TEMP.TREND.MIN_PERIODS = 12 งวด (seasonality 24)` ``, `` `TEMP.OFF_HOURS = นอก 08:00–18:00 และวันหยุด` ``
  - `` `SEQ.CREATE_TO_PAY.DAYS = 30` ``, `` `SEQ.CHANGE_TO_TRANSFER.DAYS = 7` ``
  - `` `FOR.BENFORD.MIN_N = 1,000 (ยอด ≥ 10)` ``, `` `FOR.BENFORD.MAD_1ST = ≤ 0.006 / ≤ 0.012 / ≤ 0.015 / > 0.015` ``, `` `FOR.ROUND.UNIT = 1,000` ``, `` `FOR.THRESHOLD_AVOID.BAND = 90–99.99% ของวงเงินอนุมัติ` ``, `` `FOR.REPEAT.MIN_COUNT = 3` ``
  - `` `ML.CONTAMINATION = 1%` ``, `` `ML.LOF.NEIGHBORS = 20` ``, `` `ML.MIN_OBS = 1,000 หรือ 10 × จำนวน feature` ``
  - `` `NET.SHARED_ID.MIN = 2` ``, `` `NET.CYCLE = 2–5 ทอด ภายใน 30 วัน` ``, `` `NET.FUNNEL = รับ ≥ 10 แหล่ง, โอนออก ≥ 80% ภายใน 7 วัน` ``
  - `ASSESS.CONFIDENCE`, `ASSESS.MATERIALITY`, `ASSESS.PRIORITY`: write these as headed subsections with the full criteria from spec section 5.5. Each one also gets a single summary key line: `` `ASSESS.MATERIALITY = 5% กำไรก่อนภาษี / 0.5–1% รายได้ / 1–2% สินทรัพย์รวม` ``, `` `ASSESS.CLEARLY_TRIVIAL = < 5% ของ Materiality` ``, and the full 3×3 Priority table, in which a value of C×M of สูง×สูง gives สูง, and so on.

- [ ] **Step 1: Write AIDA-14** with the skeleton. Add a section `## วิธีใช้ค่ามาตรฐาน`, which explains that these values are general standards, that AIDA must tell users so whenever it cites one, how to override them (the organisation's own value plus version), and the version `1.0`. The Guardrails section says never to present a default as the organisation's approved policy.
- [ ] **Step 2: Run the validator.** Run: `python3 aida-knowledge/tools/validate_pack.py aida-knowledge`. Expected: the only error is the missing `AIDA-agent-instructions.md` (it is created in Task 6). There must be no registry or section errors.
- [ ] **Step 3: Commit** `"Add AIDA-14 configuration registry"`

---

### Task 3: Core framework files (AIDA-00, 01, 02, 03)

**Files:** Create `aida-knowledge/knowledge/AIDA-00-index-principles.md`, `AIDA-01-orchestration-workflow.md`, `AIDA-02-decision-gates.md` and `AIDA-03-analysis-selection-matrix.md`.

**Interfaces:** Consumes the AIDA-14 keys (Task 2).

Required content (each item must appear):
- **00**: an index table of all 16 files plus reserved slots 16–19 (planned name and status `สงวนไว้ระยะ B`); the Target State sentence; the 6 principles with the Thai definitions from the slide; Layers 1–10 at one line each (Layers 7, 8, 9 and 10 come from the slides; for Layers 1–6 use the orchestration and skill groupings, and label them as "ตามโครงสร้าง workflow"); a glossary of ≥ 15 terms (Evidence, Finding, Unified Finding, Alert, Capability Gate, Skip Reason, Lineage, Registry, Confidence, Materiality, Priority, Human Review, Disposition, Run ID, Drill Down); the AIDA tagline.
- **01**: all 18 stages, each with Input → Output, Decision Gate and Next stage. The I/O comes from the 3 workflow slides (for example Stage 9 is `completeness / lineage / validity → Accept • Re-run • Review`). Group them into Workflow I, II and III.
- **02**: Stop, Skip and Human Review, each with its triggers, its action and what goes into the Audit Trail. Cite `` `GATE.TRACE.REQUIRED = …` `` for Stop and `` `GATE.COMPLETENESS.MIN = 95%` `` for Skip. Include the sentence "การหยุดและการข้ามเป็นผลลัพธ์ที่ถูกต้อง เมื่อระบบอธิบายเหตุผลและบันทึก Audit Trail".
- **03**: the 8-row matrix (skill family, minimum capability, decision gate, outcome) copied from the slide; a Selection/Skip Reason template (`Skill: … | ผล: Run/Skip/Human review | เหตุผล: … | ข้อมูลที่ขาด: …`); the ML outcome is `Run / Human review`; a worked example (a dataset with amount + vendor + date but no relationship field gives Network = Skip + reason).

- [ ] **Step 1: Write the 4 files.**
- [ ] **Step 2: Run the validator.** Expected: only the missing-instructions error.
- [ ] **Step 3: Prose-threshold check.** Run: `grep -nE "(เกิน|มากกว่า|ต่ำกว่า|>|<|≥|≤) ?[0-9]" aida-knowledge/knowledge/AIDA-0[0-3]*.md | grep -v '`[A-Z]'`. Expected: no output, or only lines that are not thresholds. Fix anything else.
- [ ] **Step 4: Commit** `"Add AIDA core framework knowledge files (00-03)"`

---

### Task 4: Skill family files (AIDA-04 to 08)

**Files:** Create `AIDA-04-skill-statistical-concentration.md`, `AIDA-05-skill-behavioral-temporal.md`, `AIDA-06-skill-sequence-forensic.md`, `AIDA-07-skill-rule-ml.md` and `AIDA-08-skill-network.md` under `aida-knowledge/knowledge/`.

**Interfaces:** Consumes the AIDA-14 keys.

Required content: for each skill family (5.1–5.9), write the 8-field Universal Skill Spec (Purpose, Non-purpose, Input, Output, Configuration, Audit Trail, Success, Stop/Skip). Then add the technique table (spec section 4.2) with **every technique listed on the slide** (for example 5.1 has 7 techniques and 5.9 has 8). Map the keys like this:
- 5.1 → `STAT.*`, `GATE.SAMPLE.MIN`; 5.2 → `CONC.*`
- 5.3 → `BEH.*`; 5.4 → `TEMP.*`
- 5.5 → `SEQ.*`; 5.6 → `FOR.*`
- 5.7: no numeric key. Add the rule "อ่านกฎจาก Configuration Registry เท่านั้น ห้าม Hard-code ใน Skill", and say that rules are organisation-specific.
- 5.8 → `ML.*`. List the 8 minimum output fields from the slide and include `Anomaly Score ≠ Fraud Conclusion`.
- 5.9 → `NET.*`. Gate: if entities or relationships are insufficient, the result is Skip + reason.
- Copy the slide subtitles in as interpretation notes, for example 5.1–5.2 "ใช้เพื่อชี้ค่าที่เด่นหรือการพึ่งพิงที่สูง ไม่ใช่เพื่อชี้การกระทำผิด". That line passes the accusatory check because it contains `ไม่`.
- The Evidence output for 5.1–5.2 lists: record/entity, metric, benchmark/distribution, threshold/configuration and data reference.

- [ ] **Step 1: Write the 5 files.**
- [ ] **Step 2: Run the validator.** Expected: only the missing-instructions error.
- [ ] **Step 3: Coverage check.** Run: `grep -c "Purpose\|Non-purpose\|Stop/Skip" aida-knowledge/knowledge/AIDA-0[4-8]*.md`. Expected: each file has ≥ 6 matches (2 families × 3 fields; AIDA-08 has ≥ 3). Then check by eye that every technique name on the slide appears.
- [ ] **Step 4: Prose-threshold check** (same command as in Task 3, with glob `AIDA-0[4-8]*`).
- [ ] **Step 5: Commit** `"Add AIDA anomaly skill knowledge files (04-08)"`

---

### Task 5: Assessment, procedures, output and governance (AIDA-09 to 13)

**Files:** Create `AIDA-09-hybrid-assessment.md`, `AIDA-10-assessment-model.md`, `AIDA-11-audit-procedures-language.md`, `AIDA-12-output-framework.md` and `AIDA-13-traceability-governance.md`.

Required content:
- **09**: the 4 evidence types (each with its meaning); the 6 Hybrid Logic rules; the 4 Assessment Output items; the rule "ไม่ทำให้ Statistical Score, Model Score และ Business Priority มีความหมายเดียวกัน"; a worked example of 2 independent sources corroborating (Confidence สูง per `ASSESS.CONFIDENCE`) versus a conflict (Human Review).
- **10**: 3 sections (Confidence, Materiality, Priority), each with its question and considerations from the slide; the criteria and the `` `ASSESS.MATERIALITY = …` `` and `` `ASSESS.CLEARLY_TRIVIAL = …` `` keys; the 3×3 Priority table, identical to the one in AIDA-14; both prohibitions copied verbatim from the slide footer.
- **11**: Audit Procedures 1–8 (name and Thai description); the Layer 7 Interpretation items; a table of non-accusatory wording with ≥ 10 rows, written as `หลีกเลี่ยง` → `ใช้แทน` (for example "ผู้ขายรายนี้ทุจริต" → "พบรูปแบบที่ควรตรวจสอบเพิ่มเติม"). The `หลีกเลี่ยง` column contains accusatory words, so place that table under `## ข้อห้าม (Guardrails)`.
- **12**: Output 01–16 as a table (Output, หน้าที่, ผู้ใช้หลัก, drill down to); the Layer 8 and Layer 9 lists; the Executive Output rules (7 bullets from the slide footer); the rule "ทุก Output ต้อง Drill Down ไปยัง Finding และ Evidence ได้".
- **13**: Lineage 1–7 with their fields; the Reproducibility test sentence; the 8 Layer 10 capabilities; the control objective sentence quoted verbatim; the 8 fields of the Universal Skill Spec, each with its guiding question.

- [ ] **Step 1: Write the 5 files.**
- [ ] **Step 2: Run the validator.** Expected: only the missing-instructions error.
- [ ] **Step 3: Priority table consistency.** Run: `diff <(sed -n '/ตาราง Priority/,/^$/p' aida-knowledge/knowledge/AIDA-10*.md | grep '^|') <(sed -n '/ตาราง Priority/,/^$/p' aida-knowledge/knowledge/AIDA-14*.md | grep '^|')`. Expected: no output. Both files must head the table with the line `### ตาราง Priority`.
- [ ] **Step 4: Prose-threshold check** (glob `AIDA-09* AIDA-1[0-3]*`).
- [ ] **Step 5: Commit** `"Add AIDA assessment, procedure, output and governance files (09-13)"`

---

### Task 6: Checklist/FAQ, Agent Instructions, eval questions and README

**Files:**
- Create: `aida-knowledge/knowledge/AIDA-15-acceptance-checklist-faq.md`
- Create: `aida-knowledge/AIDA-agent-instructions.md`
- Create: `aida-knowledge/tests/eval-questions.md`
- Create: `aida-knowledge/README.md`

Required content:
- **15**: the 12 checklist items, verbatim from the slide, each with "ตรวจอย่างไร" and "ไฟล์อ้างอิง"; an FAQ with ≥ 10 Q&A pairs drawn from the eval set.
- **Instructions** (≤ 8,000 characters): role ("AIDA ที่ปรึกษาด้านวิธีการตรวจสอบเชิงข้อมูล ระยะ A"); the 7 rules from spec section 4.4; the answer format (summary → details → default-value notice → reference files); a routing table from question type to file `AIDA-XX`; the phase A scope refusal plus the Analysis Plan alternative.
- **eval-questions.md**: ≥ 20 questions. Each has `ต้องมี`, `ต้องไม่มี`, `ไฟล์ที่ควรถูกอ้าง` and `Checklist ข้อ`. All 12 checklist items must be covered, along with the 5 examples in spec section 6.2. End with a result tick table.
- **README**: what the pack is; upload steps (test 1 `.md` file first, then upload `knowledge/`, then paste the instructions); the reserved slots 16–19 table from spec section 3.2; how to change a default (edit AIDA-14, bump the version, run the validator); how to run the validator and the tests.

- [ ] **Step 1: Write the 4 files.**
- [ ] **Step 2: Run the full validator.** Run: `python3 aida-knowledge/tools/validate_pack.py aida-knowledge`. Expected: `OK: 16 files validated` and exit code 0.
- [ ] **Step 3: Run the unit tests.** Run: `cd aida-knowledge/tools && python3 -m unittest test_validate_pack -v`. Expected: `OK`.
- [ ] **Step 4: Checklist coverage.** Run: `grep -o "Checklist ข้อ [0-9]*" aida-knowledge/tests/eval-questions.md | sort -u | wc -l`. Expected: `12`.
- [ ] **Step 5: Commit and push** `"Add AIDA checklist/FAQ, agent instructions, eval set and README"`, then `git push -u origin ccr-92eeb8e7-1qaymh`.
