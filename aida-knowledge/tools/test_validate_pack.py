import json
import re
import tempfile
import unittest
from pathlib import Path

import validate_pack as vp

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

    def test_file_count_limit(self):
        for i in range(21):
            write(self.d, f"f{i:02d}.md", "x")
        self.assertEqual(len(vp.check_file_count(self.d)), 1)
        (self.d / "f20.md").unlink()
        self.assertEqual(vp.check_file_count(self.d), [])

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

    def test_cross_ref_reserved_ok(self):
        p = write(self.d, "a.md", skeleton("ดู AIDA-17"))
        self.assertEqual(vp.check_cross_refs(p, {"04", "14"}), [])

    def test_instructions_length(self):
        p = write(self.d, "i.md", "ก" * 8001)
        self.assertEqual(len(vp.check_instructions_length(p)), 1)
        p.write_text("ก" * 8000, encoding="utf-8")
        self.assertEqual(vp.check_instructions_length(p), [])

    def test_validate_end_to_end(self):
        reg = skeleton("| `STAT.ZSCORE.THRESHOLD = 3` | ความหมาย | 3-sigma |").replace("AIDA-04 ·", "AIDA-14 ·")
        write(self.d, "knowledge/AIDA-14-configuration-registry.md", reg)
        write(self.d, "knowledge/AIDA-04-skill-statistical-concentration.md", skeleton("`STAT.ZSCORE.THRESHOLD = 3`"))
        write(self.d, "AIDA-agent-instructions.md", "คำสั่ง")
        self.assertEqual(vp.validate(self.d), [])

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

    RECIPE_OK = (
        "# AIDA-18 · t\n\n```python\n"
        "# RECIPE NET-FUNNEL v1.0 | Skill: 5.9 Network | Risk: R1\n"
        "# Registry: NET.FUNNEL | Input: transactions(from_acct, to_acct)\n"
        "{body}\n```\n")

    def _recipe(self, body: str = "def net_funnel(tables, cfg):\n    return cfg[\"NET.FUNNEL\"]") -> Path:
        return write(self.d, "r.md", self.RECIPE_OK.format(body=body))

    KEYS = {"NET.FUNNEL", "GATE.SAMPLE.MIN"}

    def test_recipe_ok(self):
        self.assertEqual(vp.check_recipes(self._recipe(), self.KEYS), [])

    def test_recipe_none_in_file_skipped(self):
        p = write(self.d, "r.md", skeleton("```python\nprint(cfg[\"ZZ.QQ\"])\n```"))
        self.assertEqual(vp.check_recipes(p, self.KEYS), [])

    def test_recipe_header_malformed(self):
        p = write(self.d, "r.md", "```python\n# RECIPE NET-FUNNEL 1.0 Skill 5.9\n# Registry: - | Input: x\ndef f(): pass\n```\n")
        errors = vp.check_recipes(p, self.KEYS)
        self.assertEqual(len(errors), 1)
        self.assertIn("header", errors[0])

    def test_recipe_over_40_lines(self):
        body = "def net_funnel(tables, cfg):\n" + "\n".join(f"    x{i} = {i}" for i in range(40))
        errors = vp.check_recipes(self._recipe(body), self.KEYS)
        self.assertEqual(len(errors), 1)
        self.assertIn("NET-FUNNEL", errors[0])

    def test_recipe_exactly_40_lines_ok(self):
        body = "def net_funnel(tables, cfg):\n" + "\n".join(f"    x{i} = {i}" for i in range(39))
        self.assertEqual(vp.check_recipes(self._recipe(body), self.KEYS), [])

    def test_recipe_cfg_unknown_key(self):
        errors = vp.check_recipes(self._recipe("def net_funnel(tables, cfg):\n    return cfg['NOPE.KEY']"), self.KEYS)
        self.assertEqual(len(errors), 1)
        self.assertIn("NOPE.KEY", errors[0])

    def test_recipe_cfg_run_context_ok(self):
        body = "def net_funnel(tables, cfg):\n    return cfg[\"_RUN\"], cfg[\"GATE.SAMPLE.MIN\"]"
        self.assertEqual(vp.check_recipes(self._recipe(body), self.KEYS), [])

    def test_recipe_unclosed_fence(self):
        p = write(self.d, "r.md", "```python\n# RECIPE A-B v1.0 | Skill: s | Risk: -\n# Registry: - | Input: x\ndef a_b(): pass\n")
        self.assertEqual(len(vp.check_recipes(p, self.KEYS)), 1)


if __name__ == "__main__":
    unittest.main()
