import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import build_risk_library_md as brl
import validate_pack as vp

PACK = Path(__file__).resolve().parent.parent

SKELETON = """# AIDA-04 · Test
> ไฟล์: AIDA-04 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: ทดสอบ

## สรุปสั้น
สรุป

## เนื้อหา
{body}

## ข้อห้าม (Guardrails)
{guard}

## ไฟล์ที่เกี่ยวข้อง
- AIDA-14
"""


def write(d: Path, name: str, text: str) -> Path:
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def skeleton(body: str = "เนื้อหา", guard: str = "- ห้ามกล่าวหา") -> str:
    return SKELETON.format(body=body, guard=guard)


class ValidatePackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_required_sections_ok(self):
        p = write(self.d, "a.md", skeleton())
        self.assertEqual(vp.check_required_sections(p), [])

    def test_required_sections_missing_guardrails(self):
        p = write(self.d, "a.md", skeleton().replace("## ข้อห้าม (Guardrails)", "## อื่น"))
        errors = vp.check_required_sections(p)
        self.assertEqual(len(errors), 1)
        self.assertIn("ข้อห้าม", errors[0])

    def test_required_sections_with_bom(self):
        p = write(self.d, "a.md", "﻿" + skeleton())
        self.assertEqual(vp.check_required_sections(p), [])

    def test_parse_registry_complex_values(self):
        value = "< 1,500 ต่ำ / 1,500–2,500 ปานกลาง / > 2,500 สูง"
        p = write(self.d, "r.md", f"| `CONC.HHI = {value}` | x | y |\n")
        registry, errors = vp.parse_registry(p)
        self.assertEqual(errors, [])
        self.assertEqual(registry["CONC.HHI"], value)

    def test_parse_registry_duplicate_conflict(self):
        p = write(self.d, "r.md", "`STAT.ZSCORE.THRESHOLD = 3`\n`STAT.ZSCORE.THRESHOLD = 4`\n")
        _, errors = vp.parse_registry(p)
        self.assertEqual(len(errors), 1)

    def test_registry_ref_match(self):
        p = write(self.d, "a.md", skeleton("`STAT.ZSCORE.THRESHOLD = 3`"))
        self.assertEqual(vp.check_registry_refs(p, {"STAT.ZSCORE.THRESHOLD": "3"}), [])

    def test_registry_ref_mismatch(self):
        p = write(self.d, "a.md", skeleton("`STAT.ZSCORE.THRESHOLD = 2.5`"))
        self.assertEqual(len(vp.check_registry_refs(p, {"STAT.ZSCORE.THRESHOLD": "3"})), 1)

    def test_registry_ref_unknown_key(self):
        p = write(self.d, "a.md", skeleton("`STAT.NOPE = 3`"))
        self.assertEqual(len(vp.check_registry_refs(p, {"STAT.ZSCORE.THRESHOLD": "3"})), 1)

    def test_accusatory_plain_fails(self):
        p = write(self.d, "a.md", skeleton("พบการทุจริตในรายการนี้"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 1)

    def test_accusatory_negated_ok(self):
        p = write(self.d, "a.md", skeleton("Anomaly Score ≠ การทุจริต\nผลนี้ไม่ใช่การกระทำผิด"))
        self.assertEqual(vp.check_accusatory_terms(p), [])

    def test_accusatory_not_exempted_by_note_or_another(self):
        p = write(self.d, "a.md", skeleton("พนักงาน B ทุจริต ดู note ด้านล่าง\nSee another case: vendor is a fraudster"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 2)

    def test_accusatory_not_exempted_by_mai_wa(self):
        p = write(self.d, "a.md", skeleton("พนักงาน C โกงเงิน ไม่ว่ากรณีใด"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 1)

    def test_accusatory_negation_far_from_term_fails(self):
        p = write(self.d, "a.md", skeleton("รายการนี้ไม่มีเอกสารประกอบครบถ้วนตามระเบียบ และพนักงาน D ทุจริต"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 1)

    def test_accusatory_case_insensitive(self):
        p = write(self.d, "a.md", skeleton("ผู้ขาย A เป็น Fraudster"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 1)

    def test_registry_ref_loose_spacing_checked(self):
        p = write(self.d, "a.md", skeleton("`GATE.SAMPLE.MIN=25` และ `GATE.SAMPLE.MIN  =  20`"))
        self.assertEqual(len(vp.check_registry_refs(p, {"GATE.SAMPLE.MIN": "30"})), 2)

    def test_accusatory_extended_terms(self):
        p = write(self.d, "a.md", skeleton("พนักงาน E ยักยอกเงิน\nบริษัท F คอร์รัปชัน\nผู้ขาย G ฉ้อโกง\nผู้จัดการสมรู้ร่วมคิด"))
        self.assertEqual(len(vp.check_accusatory_terms(p)), 4)

    def _shared_pack(self, priority10: str, priority14: str, conf10: str = "| สูง | x |", conf14: str = "| สูง | x |"):
        table = "### ตาราง Priority\n| C | M |\n|---|---|\n{p}\n\n### ตาราง Confidence\n| ระดับ | เกณฑ์ |\n|---|---|\n{c}\n"
        write(self.d, "knowledge/AIDA-10-assessment-model.md", skeleton(table.format(p=priority10, c=conf10)))
        write(self.d, "knowledge/AIDA-14-configuration-registry.md", skeleton(table.format(p=priority14, c=conf14)))
        return self.d / "knowledge"

    def test_shared_tables_match(self):
        k = self._shared_pack("| สูง | สูง |", "| สูง | สูง |")
        self.assertEqual(vp.check_shared_tables(k), [])

    def test_shared_priority_table_drift(self):
        k = self._shared_pack("| สูง | กลาง |", "| สูง | สูง |")
        errors = vp.check_shared_tables(k)
        self.assertEqual(len(errors), 1)
        self.assertIn("ตาราง Priority", errors[0])

    def test_shared_confidence_table_drift(self):
        k = self._shared_pack("| สูง | สูง |", "| สูง | สูง |", conf10="| สูง | y |")
        errors = vp.check_shared_tables(k)
        self.assertEqual(len(errors), 1)
        self.assertIn("ตาราง Confidence", errors[0])

    def test_shared_table_heading_missing(self):
        k = self._shared_pack("| สูง | สูง |", "| สูง | สูง |")
        p = k / "AIDA-10-assessment-model.md"
        p.write_text(p.read_text(encoding="utf-8").replace("### ตาราง Confidence", "### อื่น"), encoding="utf-8")
        self.assertEqual(len(vp.check_shared_tables(k)), 1)

    def test_validate_checks_instructions_content(self):
        reg = skeleton("| `STAT.ZSCORE.THRESHOLD = 3` | x | y |").replace("AIDA-04 ·", "AIDA-14 ·")
        write(self.d, "knowledge/AIDA-14-configuration-registry.md", reg)
        write(self.d, "AIDA-agent-instructions.md", "ผู้ขายรายนี้ทุจริต\n`STAT.ZSCORE.THRESHOLD = 2`")
        errors = vp.validate(self.d)
        self.assertTrue(any("AIDA-agent-instructions.md" in e and "accusatory" in e for e in errors))
        self.assertTrue(any("AIDA-agent-instructions.md" in e and "STAT.ZSCORE.THRESHOLD" in e for e in errors))

    def test_accusatory_in_guardrails_ok(self):
        p = write(self.d, "a.md", skeleton(guard="| ผู้ขายรายนี้โกง | พบรูปแบบที่ควรตรวจสอบเพิ่มเติม |"))
        self.assertEqual(vp.check_accusatory_terms(p), [])

    def test_cross_ref_missing(self):
        p = write(self.d, "a.md", skeleton("ดู AIDA-21"))
        self.assertEqual(len(vp.check_cross_refs(p, {"04", "14"})), 1)

    def test_cross_ref_no_reserved_ids_after_c1(self):
        # AIDA-16..19 exist from phase C1 on, so no id is reserved any more
        p = write(self.d, "a.md", skeleton("ดู AIDA-17"))
        self.assertEqual(len(vp.check_cross_refs(p, {"04", "14"})), 1)

    def test_instructions_length(self):
        p = write(self.d, "i.md", "ก" * 8001)
        self.assertEqual(len(vp.check_instructions_length(p)), 1)
        p.write_text("ก" * 8000, encoding="utf-8")
        self.assertEqual(vp.check_instructions_length(p), [])

    def test_validate_missing_registry(self):
        write(self.d, "knowledge/AIDA-04-skill-statistical-concentration.md", skeleton())
        write(self.d, "AIDA-agent-instructions.md", "คำสั่ง")
        self.assertTrue(any("AIDA-14" in e for e in vp.validate(self.d)))

    # ---- Machine Config and recipes (B1) ----
    def _registry(self, config: dict | None = None, extra: str = "") -> Path:
        body = ("`STAT.MAD.THRESHOLD = 3.5`\n`GATE.SAMPLE.MIN = 30`\n" + extra)
        if config is not None:
            body += "\n## Machine Config (สำหรับ recipe)\n```json\n" + json.dumps(config, ensure_ascii=False) + "\n```\n"
        return write(self.d, "knowledge/AIDA-14-configuration-registry.md", body)

    def test_machine_config_unknown_key(self):
        p = self._registry({"STAT.MAD.THRESHOLD": 3.5, "NOPE.KEY": 1})
        errors = vp.check_machine_config(p)
        self.assertEqual(len(errors), 1)
        self.assertIn("NOPE.KEY", errors[0])

    def test_machine_config_heading_key_ok(self):
        p = self._registry({"ASSESS.PRIORITY": {}}, extra="\n### ASSESS.PRIORITY — ลำดับความสำคัญ\n")
        self.assertEqual(vp.check_machine_config(p), [])

    def test_machine_config_underscore_exempt(self):
        p = self._registry({"STAT.MAD.THRESHOLD": 3.5, "_comment": "x"})
        self.assertEqual(vp.check_machine_config(p), [])

    def test_machine_config_bad_json(self):
        p = write(self.d, "knowledge/AIDA-14-configuration-registry.md",
                  "## Machine Config (สำหรับ recipe)\n```json\n{not json}\n```\n")
        self.assertEqual(len(vp.check_machine_config(p)), 1)

    def test_machine_config_required_when_registry_versioned(self):
        p = self._registry(None, extra="`REGISTRY.VERSION = 1.1`\n")
        self.assertEqual(len(vp.check_machine_config(p)), 1)

    def test_priority_json_matches_table(self):
        real = Path(__file__).resolve().parent.parent / "knowledge" / vp.REGISTRY_NAME
        config, errors = vp.parse_machine_config(real)
        self.assertEqual(errors, [])
        table = vp.priority_from_table(real.read_text(encoding="utf-8"))
        self.assertEqual(config["ASSESS.PRIORITY"], table)
        self.assertEqual(vp.check_machine_config(real), [])

    def test_priority_json_drift_detected(self):
        real = Path(__file__).resolve().parent.parent / "knowledge" / vp.REGISTRY_NAME
        text = real.read_text(encoding="utf-8")
        config, _ = vp.parse_machine_config(real)
        config["ASSESS.PRIORITY"]["ต่ำ"]["สูง"] = "สูง"
        text = re.sub(r"```json\n.*?\n```", lambda m: "```json\n" + json.dumps(config, ensure_ascii=False) + "\n```",
                      text, count=1, flags=re.S)
        p = write(self.d, "knowledge/AIDA-14-configuration-registry.md", text)
        self.assertEqual(len(vp.check_machine_config(p)), 1)

    def _real_registry_text(self) -> str:
        real = Path(__file__).resolve().parent.parent / "knowledge" / vp.REGISTRY_NAME
        return real.read_text(encoding="utf-8")

    def test_machine_config_values_match_table_real(self):
        real = Path(__file__).resolve().parent.parent / "knowledge" / vp.REGISTRY_NAME
        self.assertEqual(vp.check_machine_config_values(real), [])

    def test_machine_config_scalar_drift_detected(self):
        text = self._real_registry_text()
        for old, new in (('"MULE.DWELL_HOURS": 24', '"MULE.DWELL_HOURS": 48'),
                         ('"GATE.COMPLETENESS.MIN": 0.95', '"GATE.COMPLETENESS.MIN": 0.9'),
                         ('"FLOW.MIN_PASS_RATIO": 0.9,', '"FLOW.MIN_PASS_RATIO": 0.8,')):
            self.assertIn(old, text)
            p = write(self.d, "knowledge/AIDA-14-configuration-registry.md", text.replace(old, new))
            errors = vp.check_machine_config_values(p)
            self.assertEqual(len(errors), 1, old)
            self.assertIn(old.split('"')[1], errors[0])

    def test_machine_config_structured_drift_detected(self):
        text = self._real_registry_text()
        for old, new in (('"min_sources": 10', '"min_sources": 12'),
                         ('"max_len": 5', '"max_len": 6'),
                         ('"velocity_days": 6', '"velocity_days": 7'),
                         ('"end": "18:00"', '"end": "17:00"')):
            self.assertIn(old, text)
            p = write(self.d, "knowledge/AIDA-14-configuration-registry.md", text.replace(old, new))
            self.assertEqual(len(vp.check_machine_config_values(p)), 1, old)
            self.assertEqual(len(vp.check_machine_config(p)), 1, old)

    def test_machine_config_table_drift_detected(self):
        text = self._real_registry_text().replace("`GATE.SAMPLE.MIN = 30`", "`GATE.SAMPLE.MIN = 40`")
        p = write(self.d, "knowledge/AIDA-14-configuration-registry.md", text)
        self.assertEqual(len(vp.check_machine_config_values(p)), 1)


class RealPackTests(unittest.TestCase):
    """C1 checks (spec 7.5) on a copy of the real pack: it must pass, and each drift must be caught."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.d = Path(self._tmp.name)
        shutil.copytree(PACK / "knowledge", self.d / "knowledge")
        (self.d / "engine").mkdir()
        shutil.copy(PACK / "engine" / "aida_engine.py", self.d / "engine" / "aida_engine.py")
        shutil.copy(PACK / vp.INSTRUCTIONS_NAME, self.d / vp.INSTRUCTIONS_NAME)
        self.k = self.d / "knowledge"
        self.engine = self.d / "engine" / "aida_engine.py"

    def tearDown(self):
        self._tmp.cleanup()

    def edit(self, path: Path, old: str, new: str, count: int = 1):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count), encoding="utf-8")

    def append(self, path: Path, text: str):
        path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")

    def test_real_pack_validates(self):
        self.assertEqual(vp.validate(self.d), [])

    def test_pack_has_20_files(self):
        self.assertEqual(vp.check_file_count(self.k), [])
        self.assertEqual(len([p for p in self.k.iterdir() if p.is_file()]), 20)
        write(self.k, "extra.md", "x")
        errors = vp.check_file_count(self.k)
        self.assertEqual(len(errors), 1)
        self.assertIn("21", errors[0])
        (self.k / "extra.md").unlink()
        (self.k / "AIDA-15-acceptance-checklist-faq.md").unlink()
        self.assertEqual(len(vp.check_file_count(self.k)), 1)
        write(self.k, "aida_engine.txt", "x")  # any file type counts: Knowledge holds at most 20 files
        self.assertEqual(vp.check_file_count(self.k), [])

    def test_engine_located_outside_knowledge(self):
        self.assertEqual(vp.find_engine(self.d), self.engine)
        self.engine.unlink()
        self.assertIsNone(vp.find_engine(self.d))
        self.assertTrue(any("aida_engine.py" in e for e in vp.validate(self.d)))

    def test_engine_copy_in_knowledge_must_match_source(self):
        (self.k / "AIDA-16-engine-install.md").unlink()
        shutil.copy(self.engine, self.k / "aida_engine.py")  # approach 3
        self.assertEqual(vp.validate(self.d), [])
        self.append(self.k / "aida_engine.py", "\n# drift\n")
        self.assertTrue(any("differs" in e for e in vp.validate(self.d)))

    def test_engine_version_matches_index(self):
        self.assertEqual(vp.engine_constants(self.engine)["__version__"], "3.1.0")
        self.assertEqual(vp.check_engine_version(self.engine, self.k), [])
        a00 = self.k / "AIDA-00-index-principles.md"
        self.edit(a00, "v3.1.0", "v3.1.1")
        errors = vp.check_engine_version(self.engine, self.k)
        self.assertEqual(len(errors), 1)
        self.assertIn("AIDA-00", errors[0])
        self.edit(a00, "v3.1.1", "v3.1.0")
        a19 = self.k / "AIDA-19-engine-guide.md"
        a19.write_text(re.sub(r"aida_engine\.py`?\s+v\d+(?:\.\d+)+", "engine", a19.read_text(encoding="utf-8")),
                       encoding="utf-8")
        errors = vp.check_engine_version(self.engine, self.k)
        self.assertEqual(len(errors), 1)
        self.assertIn("AIDA-19", errors[0])
        self.edit(self.engine, '__version__ = "3.1.0"', '__version__ = "3.2.0"')
        self.assertGreaterEqual(len(vp.check_engine_version(self.engine, self.k)), 1)

    def test_engine_registry_version_matches_aida14(self):
        reg = self.k / vp.REGISTRY_NAME
        self.assertEqual(vp.check_engine_registry_version(self.engine, reg), [])
        self.edit(self.engine, 'REGISTRY_VERSION = "1.3"', 'REGISTRY_VERSION = "1.4"')
        errors = vp.check_engine_registry_version(self.engine, reg)
        self.assertEqual(len(errors), 1)
        self.assertIn("1.4", errors[0])

    def test_engine_cfg_keys_exist(self):
        reg = self.k / vp.REGISTRY_NAME
        self.assertEqual(vp.check_engine_cfg_keys(self.engine, reg), [])
        self.append(self.engine, '\n\ndef _probe(cfg):\n    return cfg["NOPE.KEY"], cfg["_RUN"], cfg_run["ZZ.TOP"]\n')
        errors = vp.check_engine_cfg_keys(self.engine, reg)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any("NOPE.KEY" in e for e in errors))
        self.assertTrue(any("ZZ.TOP" in e for e in errors))

    def test_engine_no_network_imports(self):
        self.assertEqual(vp.check_engine_imports(self.engine), [])
        for line in ("import requests", "from urllib import request", "import socket", "import http.client",
                     "import yaml"):
            path = write(self.d, "e.py", "import pandas as pd\n" + line + "\n")
            self.assertEqual(len(vp.check_engine_imports(path)), 1, line)

    def test_risk_library_md_matches_engine(self):
        mod = vp.load_engine(self.engine)
        a18 = self.k / "AIDA-18-risk-library.md"
        self.assertEqual(brl.render(mod), a18.read_text(encoding="utf-8"))
        self.assertEqual(vp.check_risk_library(mod, a18), [])
        for rid in mod.RISK_LIBRARY:
            self.assertIn(f"### {rid} ", a18.read_text(encoding="utf-8"))
        for cid in mod.CHECKS:
            self.assertIn(cid, a18.read_text(encoding="utf-8"))
        self.assertNotIn("```python", a18.read_text(encoding="utf-8"))
        for key in ("TEMP.PERIOD_END.MIN_TX", "TEMP.PERIOD_END.MIN_SHARE", "FOR.ROUND.MIN_SHARE",
                    "INTAKE.JOIN_MIN_PCT", "FLOW-TRACE", "trace("):
            self.assertIn(key, a18.read_text(encoding="utf-8"))
        self.edit(a18, mod.RISK_LIBRARY["A-R1"]["name_th"], "ชื่ออื่น")
        errors = vp.check_risk_library(mod, a18)
        self.assertEqual(len(errors), 1)
        self.assertIn("build_risk_library_md", errors[0])

    def test_registry_v13_keys_documented(self):
        """Every LIFE.* and FUND.* key (the engine's and the C2 list) is in both the AIDA-14 table and Machine Config."""
        reg = self.k / vp.REGISTRY_NAME
        table, errors = vp.parse_registry(reg)
        self.assertEqual(errors, [])
        config, errors = vp.parse_machine_config(reg)
        self.assertEqual(errors, [])
        c2 = {"LIFE.EARLY_SURR.MONTHS", "LIFE.BENCHG_CASH.WINDOW_DAYS", "LIFE.LOAN.NEAR_PCT", "LIFE.LOAN.MIN_COUNT",
              "LIFE.LOAN.COUNT_MONTHS", "LIFE.LOAN_SURR.WINDOW_DAYS", "LIFE.PAYEE.MIN_POLICIES",
              "LIFE.BENEF.MIN_POLICIES", "LIFE.BENCHG.MIN_COUNT", "LIFE.BENCHG.COUNT_MONTHS", "FUND.ROUNDTRIP.DAYS",
              "FUND.ROUNDTRIP.AMOUNT_BAND", "FUND.SHARED_ACCT.MIN_HOLDERS", "FUND.FREQ.MIN_TX_MONTH",
              "FUND.CHURN.MIN_CLIENT_SHARE", "FUND.CHURN.MIN_CLIENTS", "FUND.CUTOFF_TIME"}
        prefixed = lambda keys: {k for k in keys if k.startswith(("LIFE.", "FUND."))}
        engine_keys = prefixed(vp.engine_cfg_keys(self.engine))
        self.assertTrue(engine_keys, "the engine reads no LIFE.* / FUND.* key")
        everything = c2 | engine_keys | prefixed(table) | prefixed(config)
        self.assertEqual(everything - set(table), set(), "missing from the AIDA-14 table")
        self.assertEqual(everything - set(config), set(), "missing from the Machine Config")
        self.assertEqual(table["REGISTRY.VERSION"], "1.3")
        self.assertEqual(config["FUND.CUTOFF_TIME"], "15:30")
        self.assertEqual(config["FUND.ROUNDTRIP.AMOUNT_BAND"], {"low": 0.8, "high": 1.2})

    def test_risk_references_checks_and_roles(self):
        mod = vp.load_engine(self.engine)
        self.assertEqual(vp.check_risk_references(mod.RISK_LIBRARY, mod.CHECKS), [])
        lib = json.loads(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in mod.RISK_LIBRARY.items()},
                                    ensure_ascii=False))
        lib["A-R1"]["checks"] = ["DUP-PAY", "NO-SUCH-CHECK"]
        lib["A-R2"]["min_roles"] = ["record_id", "vendor"]
        lib["R1"]["join_roles"] = ["opened"]
        errors = vp.check_risk_references(lib, mod.CHECKS)
        self.assertEqual(len(errors), 3)
        checks = {k: dict(v) for k, v in mod.CHECKS.items()}
        checks["DUP-PAY"] = {**checks["DUP-PAY"], "requires": ["record_id", "invoice"]}
        self.assertEqual(len(vp.check_risk_references(mod.RISK_LIBRARY, checks)), 1)


if __name__ == "__main__":
    unittest.main()
