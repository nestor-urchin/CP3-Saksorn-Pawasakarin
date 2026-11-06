"""Tests for the fixes from the final whole-branch review of AIDA phase C1 (findings 1-13).

Every output goes to a temporary directory. Each class names the finding it covers.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import ENGINE_PATH, engine  # noqa: E402
import test_orchestration as to  # noqa: E402
import test_variants_e2e as tv  # noqa: E402

ROOT = HERE.parent
_TMP = []


def tmp():
    d = tempfile.mkdtemp(prefix="aida-final-")
    _TMP.append(d)
    return Path(d)


def tearDownModule():
    for d in _TMP:
        shutil.rmtree(d, True)
    tv.tearDownModule()


def confirmed_a(d: Path, **answers):
    e = engine()
    ins = e.inspect(to.files("A"), to.brief("A"), draft_path=str(d / "intake_draft.json"))
    return e.confirm(ins["intake"], to.answers("A", **answers), str(d / "intake.json"))


class F1DraftResumePoint(unittest.TestCase):
    def test_inspect_writes_draft_file(self):
        d = tmp()
        p = d / "work" / "intake_draft.json"
        r = engine().inspect(to.files("A"), to.brief("A"), draft_path=str(p))
        self.assertEqual(r["draft_path"], str(p.resolve()))
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "draft")
        self.assertEqual(data["roles"], r["intake"]["roles"])
        self.assertEqual(data["risks"], r["intake"]["risks"])

    def test_default_draft_file_name(self):
        self.assertTrue(engine().DRAFT_FILE.endswith("intake_draft.json"))

    def test_confirm_from_draft_file_fresh_process(self):
        d = tmp()
        draft = d / "intake_draft.json"
        engine().inspect(to.files("A"), to.brief("A"), draft_path=str(draft))
        code = (
            "import importlib.util, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('aida_engine', {str(ENGINE_PATH)!r})\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            f"it = m.confirm({str(draft)!r}, {{}}, 'intake.json')\n"
            f"r = m.run({to.files('A')!r}, 'intake.json', 'out')\n"
            "f = r['findings']\n"
            "print(json.dumps([r['status'], sorted([list(x) for x in zip(f['entity_type'], f['entity_id'], "
            "f['risk'], f['period'])])], ensure_ascii=False))\n")
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(d), timeout=600)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        status, got = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertEqual(status, "OK")
        self.assertEqual({tuple(x) for x in got}, {("document", "INV-7781", "A-R1", "2026-04"),
                                                    ("vendor", "V-045", "A-R2", "2026-06")})
        self.assertTrue((d / "intake.json").exists())

    def test_confirm_draft_path_errors_thai(self):
        e = engine()
        with self.assertRaises(e.AidaError) as cm:
            e.confirm(str(tmp() / "nope.json"), {}, str(tmp() / "intake.json"))
        self.assertIn("inspect", str(cm.exception))
        self.assertRegex(str(cm.exception), r"[ก-๙]")

    def test_docs_describe_resume_from_draft(self):
        ins = (ROOT / "AIDA-agent-instructions.md").read_text(encoding="utf-8")
        g19 = (ROOT / "knowledge" / "AIDA-19-engine-guide.md").read_text(encoding="utf-8")
        g16 = (ROOT / "knowledge" / "AIDA-16-engine-install.md").read_text(encoding="utf-8")
        for t in (ins, g19, g16):
            self.assertIn("intake_draft.json", t)


class F2NoFalseStop(unittest.TestCase):
    def test_legacy_inspect_no_stop_then_confirm_runs(self):
        e = engine()
        for ds in ("A", "C"):
            with self.subTest(dataset=ds):
                d = tmp()
                ins = e.inspect(tv.vfiles(ds, "legacy"), draft_path=str(d / "intake_draft.json"))
                st = ins["intake"]["profile_status"] or ""
                self.assertFalse(st.startswith("STOP"), st)
                text = ins["review_th"]
                self.assertNotIn("tx_id", text)
                a = text.split("\nB. ")[0]
                self.assertTrue(any(line.startswith("❓") and "record_id" in line for line in a.splitlines()), a)
                ans = dict(tv.answers(ds, "legacy"), add_risks=sorted({k[2] for k in tv.key_set(ds)}))
                conf = e.confirm(ins["intake"], ans, str(d / "intake.json"))
                r = e.run(tv.vfiles(ds, "legacy"), conf, str(d / "out"))
                self.assertEqual(r["status"], "OK")
                self.assertEqual(tv.finding_set(r["findings"]), tv.key_set(ds))

    def test_duplicate_record_id_still_stops_with_file_column_name(self):
        d = tmp()
        p = pd.read_csv(to.files("A")["payments"], dtype=str, keep_default_na=False)
        p.loc[5, "payment_id"] = p.loc[4, "payment_id"]
        f = d / "payments.csv"
        p.to_csv(f, index=False)
        ins = engine().inspect({"payments": str(f)}, to.brief("A"), draft_path=str(d / "intake_draft.json"))
        st = ins["intake"]["profile_status"]
        self.assertTrue(st.startswith("STOP"), st)
        self.assertIn("payment_id", st)
        self.assertIn("record_id", st)
        self.assertNotIn("tx_id", st)
        self.assertNotIn("tx_id", ins["review_th"])

    def test_docs_stop_only_for_confirmed_column(self):
        g19 = (ROOT / "knowledge" / "AIDA-19-engine-guide.md").read_text(encoding="utf-8")
        self.assertIn("ยังไม่มีคอลัมน์ที่เป็น record_id", g19)


def _explore_setup():
    e = engine()
    d = tmp()
    it = confirmed_a(d)
    ip = str(d / "intake.json")
    eid = e.explore_log("ผู้ขายรายใดจ่ายวันหยุดมากที่สุด", "d['transactions'].head()", "V-010 5 รายการ", intake=ip)
    e.promote(eid, "V-010", "RX", "2026-08", "ควรทบทวนรายการวันหยุด", "ผู้ทบทวนทดสอบ", "สูง", intake=ip)
    return e, d, it, ip, eid


def _tamper(d: Path, fn):
    p = d / "explore_log.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    fn(data)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class F3PromotedRowsRebuilt(unittest.TestCase):
    def test_tampered_fields_never_reach_findings(self):
        e, d, it, ip, eid = _explore_setup()

        def bad(data):
            data["promoted"][0].update(exposure=9_999_999.0, materiality="สูง", review_status="ยืนยันแล้ว",
                                       review_reason="ทุจริต", priority="สูง", confidence="สูง",
                                       source="card", source_label=None, entity_type="บุคคล")
        _tamper(d, bad)
        r = e.run(to.files("A"), ip, str(d / "out"))
        f = r["findings"]
        row = f[f["source"] == "exploratory"].iloc[0]
        self.assertTrue(row["exposure"] is None or pd.isna(row["exposure"]))
        self.assertEqual(row["materiality"], "ไม่ได้ประเมิน")
        self.assertEqual(row["review_status"], "รอ Human Review")
        self.assertNotIn("ทุจริต", row["review_reason"])
        self.assertTrue(row["review_reason"].startswith(e.EXPLORE_LABEL))
        self.assertEqual(row["confidence"], "กลาง")
        self.assertEqual(row["priority"], "กลาง")
        self.assertEqual(row["source_label"], e.EXPLORE_LABEL)
        self.assertEqual(row["entity_id"], "V-010")
        self.assertEqual(row["explore_id"], eid)
        wb = openpyxl.load_workbook(r["paths"]["workbook"])
        cells = " ".join(str(c.value) for row_ in wb["Findings"].iter_rows() for c in row_ if c.value)
        self.assertNotIn("ทุจริต", cells)

    def test_blank_entity_refused(self):
        e, d, it, ip, eid = _explore_setup()
        _tamper(d, lambda data: data["promoted"][0].update(entity_id="  "))
        with self.assertRaises(e.AidaError) as cm:
            e.run(to.files("A"), ip, str(d / "out"))
        self.assertIn("entity", str(cm.exception))

    def test_fabricated_explore_id_refused(self):
        e, d, it, ip, eid = _explore_setup()

        def fab(data):
            row = dict(data["promoted"][0], explore_id="EXP-999", finding_id="FND-EXP-999")
            data["promoted"].append(row)
        _tamper(d, fab)
        with self.assertRaises(e.AidaError) as cm:
            e.run(to.files("A"), ip, str(d / "out"))
        self.assertIn("EXP-999", str(cm.exception))

    def test_promote_twice_is_idempotent(self):
        e, d, it, ip, eid = _explore_setup()
        again = e.promote(eid, "V-010", "RX", "2026-08", "ควรทบทวนรายการวันหยุด", "ผู้ทบทวนทดสอบ", intake=ip)
        data = json.loads((d / "explore_log.json").read_text(encoding="utf-8"))
        self.assertEqual(len(data["promoted"]), 1)
        self.assertEqual(again["finding_id"], data["promoted"][0]["finding_id"])
        other = e.promote(eid, "V-011", "RX", "2026-08", "อีกราย", "ผู้ทบทวนทดสอบ", intake=ip)
        self.assertNotEqual(other["finding_id"], again["finding_id"])

    def test_duplicate_rows_in_file_merged_with_warning(self):
        e, d, it, ip, eid = _explore_setup()
        _tamper(d, lambda data: data["promoted"].append(dict(data["promoted"][0], finding_id="FND-X")))
        r = e.run(to.files("A"), ip, str(d / "out"))
        self.assertEqual(int((r["findings"]["source"] == "exploratory").sum()), 1)
        self.assertTrue(any(eid in w and "ซ้ำ" in w for w in r["warnings"]), r["warnings"])


class F4RunCfg(unittest.TestCase):
    def test_run_id_changes_with_effective_cfg(self):
        e = engine()
        d = tmp()
        it = confirmed_a(d)
        base = e.load_registry(e.default_registry_path())
        r1 = e.run(to.files("A"), it, str(d / "o1"))
        r2 = e.run(to.files("A"), it, str(d / "o2"), cfg={**base, "CONC.TOPN": 7})
        r3 = e.run(to.files("A"), it, str(d / "o3"))
        self.assertNotEqual(r1["run_id"], r2["run_id"])
        self.assertEqual(r1["run_id"], r3["run_id"])

    def test_cfg_source_and_hash_recorded(self):
        e = engine()
        d = tmp()
        it = confirmed_a(d)
        r = e.run(to.files("A"), it, str(d / "o"))
        log = r["run_log"]
        row = log[log["detail"].str.contains("cfg_sha256")]
        self.assertEqual(len(row), 1)
        self.assertIn("AIDA-14", row["detail"].iloc[0])
        wb = openpyxl.load_workbook(r["paths"]["workbook"])
        readme = " ".join(str(c.value) for row_ in wb["README"].iter_rows() for c in row_ if c.value)
        self.assertIn("cfg_sha256", readme)

    def test_intake_cfg_differing_from_aida14_refused(self):
        e = engine()
        d = tmp()
        base = e.load_registry(e.default_registry_path())
        ins = e.inspect(to.files("A"), to.brief("A"), cfg={**base, "DUP.WINDOW_DAYS": 9},
                        draft_path=str(d / "intake_draft.json"))
        with self.assertRaises(e.AidaError) as cm:
            e.confirm(ins["intake"], to.answers("A"), str(d / "intake.json"))
        self.assertIn("DUP.WINDOW_DAYS", str(cm.exception))
        self.assertRegex(str(cm.exception), r"[ก-๙]")
        # the same value as an organisation value is allowed
        it = e.confirm(ins["intake"], to.answers("A", org_values={"DUP.WINDOW_DAYS": 9}), str(d / "intake.json"))
        r = e.run(to.files("A"), it, str(d / "o"))
        self.assertEqual(r["status"], "OK")
        # a hand-edited intake.json cfg is refused by run as well
        data = json.loads((d / "intake.json").read_text(encoding="utf-8"))
        data["cfg"]["SPLIT.MIN_TX"] = 5
        (d / "bad.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(e.AidaError) as cm:
            e.run(to.files("A"), str(d / "bad.json"), str(d / "o2"))
        self.assertIn("SPLIT.MIN_TX", str(cm.exception))

    def test_intake_cfg_equal_to_aida14_runs(self):
        e = engine()
        d = tmp()
        base = e.load_registry(e.default_registry_path())
        ins = e.inspect(to.files("A"), to.brief("A"), cfg=dict(base), draft_path=str(d / "intake_draft.json"))
        it = e.confirm(ins["intake"], to.answers("A"), str(d / "intake.json"))
        r = e.run(to.files("A"), it, str(d / "o"))
        self.assertEqual(to.finding_set(r["findings"]), to.key_set("A"))


def _conc_tables(amounts):
    rows = []
    for i, (v, a) in enumerate(amounts):
        rows.append((f"T{i}", f"2026-08-{(i % 20) + 1:02d}", float(a), v))
    tx = pd.DataFrame(rows, columns=["tx_id", "ts", "amount", "from_acct"])
    return {"transactions": tx, "_out": {}}


class F5ConcSmallPopulation(unittest.TestCase):
    def cfg(self):
        e = engine()
        c = e.load_registry(e.default_registry_path())
        return {**c, "_RUN": {"run_id": "T", "data_ref": "t"}}

    def test_eight_vendors_one_at_90pct_flagged(self):
        amounts = [("V1", 9000)] * 1 + [(f"V{i}", 1000 / 7) for i in range(2, 9)]
        tables = _conc_tables(amounts)
        ev = engine().gen_conc(tables, self.cfg())
        self.assertEqual(list(ev["entity_id"]), ["V1"])

    def test_small_even_population_skips_with_note(self):
        amounts = [(f"V{i}", 1000 + i) for i in range(1, 9)]
        tables = _conc_tables(amounts)
        ev = engine().gen_conc(tables, self.cfg())
        self.assertEqual(len(ev), 0)
        notes = tables["_out"].get("notes", [])
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["recipe_id"], "GEN-CONC")
        self.assertIn("CONC.HHI", notes[0]["detail"])
        self.assertIn("8", notes[0]["detail"])


class F6RiskLibraryCoverage(unittest.TestCase):
    def test_refund_and_early_payoff_go_exploratory(self):
        m = engine().match_concerns(["คืนเงินผิดปกติ", "มีการคืนเงินให้ลูกค้าบ่อย", "refund", "ปิดบัญชีก่อนกำหนด",
                                     "ชำระซ้ำ", "ผู้ชำระรายเดียวชำระหลายสัญญา"])
        self.assertEqual([x["risk_id"] for x in m], [None, None, None, None, "C-R3", "C-R1"])
        self.assertEqual(m[0]["mode"], "สำรวจ")

    def test_descriptions_say_what_is_not_covered(self):
        lib = engine().RISK_LIBRARY
        self.assertIn("ไม่ครอบคลุม", lib["C-R3"]["description_th"])
        self.assertIn("คืนเงิน", lib["C-R3"]["description_th"])
        self.assertIn("ไม่ครอบคลุม", lib["C-R1"]["description_th"])
        for syn in ("คืนเงิน", "คืนเงินผิดปกติ", "refund"):
            self.assertNotIn(syn, lib["C-R3"]["synonyms"])
        self.assertNotIn("ปิดบัญชีก่อนกำหนด", lib["C-R1"]["synonyms"])

    def test_aida18_regenerated(self):
        t = (ROOT / "knowledge" / "AIDA-18-risk-library.md").read_text(encoding="utf-8")
        self.assertNotIn("คืนเงิน, refund", t)
        res = subprocess.run([sys.executable, str(ROOT / "tools" / "build_risk_library_md.py"), "--check"],
                             capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)


class F7OrgValueRange(unittest.TestCase):
    def test_share_above_one_refused(self):
        e = engine()
        cfg = e.load_registry(e.default_registry_path())
        with self.assertRaises(e.AidaError) as cm:
            e._check_org_values({"DUE.MIN_SHARE": 70}, cfg)
        msg = str(cm.exception)
        self.assertIn("DUE.MIN_SHARE", msg)
        self.assertIn("0.7", msg)
        self.assertIn("70%", msg)
        self.assertEqual(e._check_org_values({"DUE.MIN_SHARE": 0.7}, cfg), {"DUE.MIN_SHARE": 0.7})
        self.assertEqual(e._check_org_values({"DUP.WINDOW_DAYS": 5}, cfg), {"DUP.WINDOW_DAYS": 5})
        with self.assertRaises(e.AidaError):
            e._check_org_values({"CONC.SINGLE_ENTITY_SHARE": 15}, cfg)

    def test_format_documented(self):
        g19 = (ROOT / "knowledge" / "AIDA-19-engine-guide.md").read_text(encoding="utf-8")
        self.assertIn("0.7 = 70%", g19)


class F8IntakeReviewWording(unittest.TestCase):
    def test_no_b1_checkpoint_wording_in_engine(self):
        src = ENGINE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("จุดยืนยัน 1", src)

    def test_skip_reason_points_to_intake_review(self):
        plan = engine().plan_checks({"transactions": pd.DataFrame(columns=["tx_id", "ts", "amount"])})
        reasons = plan[plan["decision"] == "Skip"]["reason"]
        self.assertTrue(len(reasons))
        self.assertTrue(reasons.str.contains("Intake Review").all())


class F9Reviewer(unittest.TestCase):
    def test_review_asks_for_confirmer_without_blocking(self):
        r = to.inspected("A")
        lines = r["review_th"].rstrip().splitlines()
        self.assertTrue(lines[-1] == to.CONFIRM_LINE)
        self.assertIn("ชื่อผู้ยืนยัน", r["review_th"])

    def test_docs_pass_reviewer(self):
        ins = (ROOT / "AIDA-agent-instructions.md").read_text(encoding="utf-8")
        g19 = (ROOT / "knowledge" / "AIDA-19-engine-guide.md").read_text(encoding="utf-8")
        self.assertIn('answers["reviewer"]', ins)
        self.assertIn('answers["reviewer"]', g19)
        self.assertLessEqual(len(ins), 8000)


class F10UnknownRiskIds(unittest.TestCase):
    def test_run_refuses_unknown_risk_id(self):
        e = engine()
        d = tmp()
        confirmed_a(d)
        data = json.loads((d / "intake.json").read_text(encoding="utf-8"))
        data["risks"]["requested"].append("A-R9")
        (d / "bad.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(e.AidaError) as cm:
            e.run(to.files("A"), str(d / "bad.json"), str(d / "o"))
        self.assertIn("A-R9", str(cm.exception))
        self.assertRegex(str(cm.exception), r"[ก-๙]")


class F11RealisticPath(unittest.TestCase):
    """inspect(files, brief) -> confirm(draft, {}) (a bare "ยืนยัน") -> run."""

    def bare(self, ds):
        e = engine()
        d = tmp()
        ins = e.inspect(to.files(ds), to.brief(ds), draft_path=str(d / "intake_draft.json"))
        it = e.confirm(ins["intake"], {}, str(d / "intake.json"))
        return e.run(to.files(ds), it, str(d / "out"))

    def test_e_b1_key(self):
        r = self.bare("E")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(to.finding_set(r["findings"]), to.key_set("E"))

    def test_c_requested(self):
        r = self.bare("C")
        self.assertEqual(to.finding_set(r["findings"]), {("payer", "PY01", "C-R1", "2026-08"),
                                                          ("contract", "HP-0042", "C-R2", "2026-08")})

    def test_a_requested(self):
        r = self.bare("A")
        self.assertEqual(to.finding_set(r["findings"]), {("document", "INV-7781", "A-R1", "2026-04"),
                                                          ("vendor", "V-045", "A-R2", "2026-06")})


class F12Eval(unittest.TestCase):
    def test_q33_q39_paste_only_letter(self):
        t = (HERE / "eval-questions.md").read_text(encoding="utf-8")
        for q in ("### Q33", "### Q39"):
            block = t.split(q, 1)[1].split("\n### ", 1)[0]
            self.assertIn("```json", block)
            self.assertIn("หมายเหตุสำหรับผู้พัฒนา", block)


class F13SodRow(unittest.TestCase):
    def test_sod_same_user_row_in_aida14(self):
        t = (ROOT / "knowledge" / "AIDA-14-configuration-registry.md").read_text(encoding="utf-8")
        self.assertIn("| `SOD.SAME_USER", t)


if __name__ == "__main__":
    unittest.main()
