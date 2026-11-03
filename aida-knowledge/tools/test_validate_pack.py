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


if __name__ == "__main__":
    unittest.main()
