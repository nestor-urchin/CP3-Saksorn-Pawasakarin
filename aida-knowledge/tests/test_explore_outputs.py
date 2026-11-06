"""Tests for AIDA C1 task 8: exploratory mode (data, explore_log, promote) and the new Workbook / Dashboard outputs.

Every output goes to a temporary directory. The samples are read from samples/{C,A} and samples/ (E).
"""
import json
import re
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

from _engine import engine  # noqa: E402
import test_orchestration as to  # noqa: E402

SHEETS = ["README", "Intake_Review", "Data_Dictionary", "Data_Request", "Dataset_Profile", "Analysis_Plan", "Evidence",
          "Findings", "Exploratory", "Mule_Networks", "Money_Flow", "Materiality", "Run_Log"]
_TMP = {}
_CACHE = {}


def tmp(name):
    if "d" not in _TMP:
        _TMP["d"] = tempfile.mkdtemp(prefix="aida-t8-")
    p = Path(_TMP["d"]) / name
    p.mkdir(exist_ok=True)
    return p


def tearDownModule():
    if "d" in _TMP:
        shutil.rmtree(_TMP["d"], True)


def fresh(name, tag):
    """(confirmed intake, intake.json path) in its own folder, so explore logs do not leak between tests."""
    d = tmp(f"{name}-{tag}")
    path = str(d / "intake.json")
    it = engine().confirm(engine().inspect(to.files(name), to.brief(name))["intake"], to.answers(name), path)
    return it, path


XSS_CODE = "=HYPERLINK(\"http://x\")\ndf.head()  # <img src=x onerror=window.__x=1>"


class ExploreLog(unittest.TestCase):
    def test_data_internal_frames_filters_and_original_names(self):
        it, _ = fresh("C", "data")
        d = engine().data(to.files("C"), it)
        tx = d["transactions"]
        raw = pd.read_csv(to.files("C")["payments"], dtype=str)
        self.assertLess(len(tx), len(raw))  # status != C filter applied
        self.assertTrue({"tx_id", "ts", "amount", "from_acct"} <= set(tx.columns))
        names = tx.attrs["original_names"]
        self.assertEqual(names["tx_id"], "payment_id")
        self.assertEqual(names["amount"], "pay_amount")
        self.assertIn("accounts", d)
        self.assertEqual(d["accounts"].attrs["original_names"]["acct_id"], "borrower_id")
        self.assertFalse(any(k.startswith("_") for k in d))

    def test_data_accepts_intake_only(self):
        it, path = fresh("C", "data1")
        a = engine().data(it)["transactions"]
        b = engine().data(path)["transactions"]
        self.assertEqual(len(a), len(b))
        self.assertEqual(len(a), len(engine().data(to.files("C"), it)["transactions"]))

    def test_data_includes_custom_roles(self):
        d = tmp("custom")
        pd.DataFrame({"id": ["T1", "T2", "T3"], "dt": ["2026-01-02", "2026-01-03", "2026-01-04"],
                      "amt": ["10", "20", "30"], "who": ["A", "A", "B"], "memo": ["x", "y", "z"]}
                     ).to_csv(d / "t.csv", index=False)
        e = engine()
        it = e.inspect({"tx": str(d / "t.csv")}, {})["intake"]
        it = e.confirm(it, {"roles": {"id": "record_id", "dt": "date", "amt": "amount", "who": "entity",
                                      "memo": "custom:memo"}}, str(d / "intake.json"))
        tx = e.data({"tx": str(d / "t.csv")}, it)["transactions"]
        self.assertIn("custom:memo", tx.columns)
        self.assertEqual(tx.attrs["original_names"]["custom:memo"], "memo")

    def test_explore_log_persists_code_and_result(self):
        e = engine()
        it, path = fresh("C", "log")
        tx = e.data(to.files("C"), it)["transactions"]
        res = tx.groupby("from_acct", as_index=False)["amount"].sum().head(7)
        code = "res = df.groupby('from_acct', as_index=False)['amount'].sum()\nres.head(7)"
        before = len(e.EXPLORE_LOG)
        eid = e.explore_log("ผู้กู้รายใดมียอดรวมสูง", code, res, note="ลองดู", intake=it)
        self.assertRegex(eid, r"^EXP-\d+$")
        self.assertEqual(len(e.EXPLORE_LOG), before + 1)
        last = e.EXPLORE_LOG[-1]
        self.assertEqual(last["explore_id"], eid)
        self.assertEqual(last["code"], code)
        self.assertEqual(last["question"], "ผู้กู้รายใดมียอดรวมสูง")
        eid2 = e.explore_log("คำถามที่สอง", "1+1", 2, intake=it)
        self.assertEqual(int(eid2.split("-")[1]), int(eid.split("-")[1]) + 1)
        f = Path(path).parent / "explore_log.json"
        self.assertTrue(f.is_file())
        j = json.loads(f.read_text(encoding="utf-8"))
        ent = {x["explore_id"]: x for x in j["explore"]}
        self.assertEqual(ent[eid]["code"], code)
        self.assertEqual(ent[eid]["note"], "ลองดู")
        self.assertEqual(ent[eid]["result"]["rows"], 7)
        self.assertEqual(ent[eid]["result"]["columns"], ["from_acct", "amount"])
        self.assertEqual(len(ent[eid]["result"]["head"]), 5)
        self.assertTrue(ent[eid]["time"])
        self.assertEqual(j["promoted"], [])
        self.assertEqual(ent[eid2]["result"]["text"], "2")

    def test_explore_log_works_from_intake_path(self):
        e = engine()
        _, path = fresh("C", "logpath")
        eid = e.explore_log("q", "x", pd.DataFrame({"a": [1]}), intake=path)
        self.assertTrue((Path(path).parent / "explore_log.json").is_file())
        self.assertRegex(eid, r"^EXP-\d+$")

    def test_explore_log_rejects_empty_question_or_code(self):
        e = engine()
        with self.assertRaises(e.AidaError) as cm:
            e.explore_log("", "x", 1)
        self.assertRegex(str(cm.exception), "[ก-๙]")
        with self.assertRaises(e.AidaError):
            e.explore_log("q", "  ", 1)


class Promote(unittest.TestCase):
    def setUp(self):
        self.e = engine()
        self.it, self.path = fresh("C", self._testMethodName)
        self.eid = self.e.explore_log("ผู้กู้ที่มียอดซ้ำ", "df.head()", pd.DataFrame({"a": [1]}), intake=self.it)

    def test_promote_caps_confidence(self):
        f = self.e.promote(self.eid, "B0001", "C-R1", "2026-03", "ยอดซ้ำหลายงวด ควรทบทวน", "สมชาย", intake=self.it)
        self.assertEqual(f["confidence"], "กลาง")
        self.assertEqual(f["source"], "exploratory")
        self.assertEqual(f["source_label"], "จากโหมดสำรวจ")
        self.assertEqual(f["reviewer"], "สมชาย")
        self.assertEqual(f["entity_id"], "B0001")
        self.assertEqual(f["risk"], "C-R1")
        self.assertEqual(f["explore_id"], self.eid)
        f2 = self.e.promote(self.eid, "B0002", "C-R1", "2026-03", "r", "สมชาย", confidence="สูง", intake=self.it)
        self.assertEqual(f2["confidence"], "กลาง")  # never above กลาง
        f3 = self.e.promote(self.eid, "B0003", "C-R1", "2026-03", "r", "สมชาย", confidence="ต่ำ", intake=self.it)
        self.assertEqual(f3["confidence"], "ต่ำ")
        self.assertNotEqual(len({f["finding_id"], f2["finding_id"], f3["finding_id"]}), 1)

    def test_promote_requires_reviewer(self):
        for bad in ("", "   ", None):
            with self.assertRaises(self.e.AidaError) as cm:
                self.e.promote(self.eid, "B0001", "C-R1", "2026-03", "เหตุผล", bad, intake=self.it)
            self.assertRegex(str(cm.exception), "reviewer|ผู้ตรวจสอบ")
        log = json.loads((Path(self.path).parent / "explore_log.json").read_text(encoding="utf-8"))
        self.assertEqual(log["promoted"], [])

    def test_promote_rx_allowed(self):
        f = self.e.promote(self.eid, "B0001", "RX", "2026-03", "ความเสี่ยงนอกคลัง", "สมชาย", intake=self.it)
        self.assertEqual(f["risk"], "RX")
        self.assertEqual(f["source"], "exploratory")

    def test_promote_rejects_unknown_risk_unknown_id_and_blank_fields(self):
        with self.assertRaises(self.e.AidaError) as cm:
            self.e.promote(self.eid, "B0001", "ZZ-9", "2026-03", "r", "ส", intake=self.it)
        self.assertIn("RX", str(cm.exception))
        with self.assertRaises(self.e.AidaError):
            self.e.promote("EXP-999", "B0001", "RX", "2026-03", "r", "ส", intake=self.it)
        with self.assertRaises(self.e.AidaError):
            self.e.promote(self.eid, "", "RX", "2026-03", "r", "ส", intake=self.it)
        with self.assertRaises(self.e.AidaError):
            self.e.promote(self.eid, "B0001", "RX", "2026-03", "", "ส", intake=self.it)

    def test_promote_without_intake_uses_the_log_file_of_the_entry(self):
        f = self.e.promote(self.eid, "B0001", "RX", "2026-03", "r", "ส")
        log = json.loads((Path(self.path).parent / "explore_log.json").read_text(encoding="utf-8"))
        self.assertEqual([p["finding_id"] for p in log["promoted"]], [f["finding_id"]])


class TamperedLog(unittest.TestCase):
    def _log(self, tag, **edit):
        e = engine()
        it, path = fresh("C", tag)
        eid = e.explore_log("q", "df.head()", 1, intake=it)
        e.promote(eid, "B0001", "RX", "2026-03", "r", "สมชาย", intake=it)
        f = Path(path).parent / "explore_log.json"
        j = json.loads(f.read_text(encoding="utf-8"))
        j["promoted"][0].update(edit)
        f.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        return e, it, tag

    def test_confidence_clamped_on_run(self):
        e, it, tag = self._log("t1", confidence="สูง", priority="สูง", source="card", source_label="")
        r = e.run(to.files("C"), it, str(tmp("o-" + tag)))
        row = r["findings"][r["findings"]["source"] == "exploratory"].iloc[0]
        self.assertEqual((row["confidence"], row["priority"], row["source_label"]), ("กลาง", "กลาง", "จากโหมดสำรวจ"))

    def test_blank_reviewer_and_bad_risk_rejected(self):
        for tag, edit, word in (("t2", {"reviewer": " "}, "reviewer"), ("t3", {"risk": "ZZ"}, "ZZ"),
                                ("t4", {"confidence": "x"}, "confidence")):
            e, it, _ = self._log(tag, **edit)
            with self.assertRaises(e.AidaError) as cm:
                e.run(to.files("C"), it, str(tmp("o-" + tag)))
            self.assertIn(word, str(cm.exception))
            self.assertIn("FND-EXP-1", str(cm.exception))

    def test_missing_keys_and_non_str_risk(self):
        e, it, tag = self._log("t5")
        f = Path(it["intake_path"]).parent / "explore_log.json"
        j = json.loads(f.read_text(encoding="utf-8"))
        del j["promoted"][0]["reviewer"]
        f.write_text(json.dumps(j), encoding="utf-8")
        with self.assertRaises(e.AidaError) as cm:
            e.run(to.files("C"), it, str(tmp("o-t5")))
        self.assertIn("reviewer", str(cm.exception))
        with self.assertRaises(e.AidaError):
            e.promote("EXP-1", "B", ["RX"], "p", "r", "ส", intake=it)


def run_with_promotion(name, tag, extra_code=None):
    e = engine()
    it, path = fresh(name, tag)
    out = tmp(f"out-{name}-{tag}")
    eid = e.explore_log("คำถามนอกการ์ด", extra_code or "df.describe()", pd.DataFrame({"a": [1, 2]}), note="บันทึก", intake=it)
    eid2 = e.explore_log("ยังไม่เลื่อน", "df.shape", (3, 4), intake=it)
    ent = "B0001" if name == "C" else "A001"
    fnd = e.promote(eid, ent, "RX", "2026-03", "ผู้ตรวจสอบเห็นว่าควรทบทวน", "สมหญิง", intake=it)
    res = e.run(to.files(name), it, str(out))
    return it, path, res, fnd, eid, eid2, out


class Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = run_with_promotion("C", "main")
        cls.e = run_with_promotion("E", "main")

    def test_run_merges_promoted_finding(self):
        it, path, res, fnd, eid, eid2, out = self.c
        f = res["findings"]
        row = f[f["finding_id"] == fnd["finding_id"]]
        self.assertEqual(len(row), 1)
        r = row.iloc[0]
        self.assertEqual((r["source"], r["source_label"], r["risk"], r["confidence"]), ("exploratory", "จากโหมดสำรวจ", "RX", "กลาง"))
        self.assertEqual(r["reviewer"], "สมหญิง")
        self.assertEqual(set(f.loc[f["finding_id"] != fnd["finding_id"], "source"]), {"card"})
        self.assertIn("โหมดสำรวจ", res["summary_th"])
        self.assertTrue(any("โหมดสำรวจ" in d and eid in d for d in res["run_log"]["detail"]))

    def test_promoted_survives_a_later_run_from_intake_path(self):
        it, path, res, fnd, *_ = self.c
        out = tmp("out-C-again")
        again = engine().run(to.files("C"), path, str(out))  # fresh run from intake.json alone
        self.assertIn(fnd["finding_id"], set(again["findings"]["finding_id"]))
        self.assertEqual(again["run_id"], res["run_id"])
        wb = pd.read_excel(again["paths"]["workbook"], sheet_name="Findings")
        self.assertIn(fnd["finding_id"], set(wb["finding_id"]))

    def test_workbook_new_sheets_order(self):
        for run in (self.c, self.e):
            wb = openpyxl.load_workbook(run[2]["paths"]["workbook"])
            self.assertEqual(wb.sheetnames, SHEETS)
        wb = openpyxl.load_workbook(self.c[2]["paths"]["workbook"])
        for s in ("Mule_Networks", "Money_Flow"):
            vals = [c.value for row in wb[s].iter_rows() for c in row if c.value]
            self.assertIn("ไม่เกี่ยวข้องกับข้อมูลประเภทนี้", vals, s)
        mn = pd.read_excel(self.e[2]["paths"]["workbook"], sheet_name="Mule_Networks")
        self.assertIn("network_id", mn.columns)

    def test_workbook_sheet_contents(self):
        it, path, res, fnd, eid, eid2, out = self.c
        x = res["paths"]["workbook"]
        ex = pd.read_excel(x, sheet_name="Exploratory", dtype=str)
        for c in ("explore_id", "question", "code", "result_summary", "note", "time", "promoted", "promoted_by",
                  "promote_reason"):
            self.assertIn(c, ex.columns)
        by = ex.set_index("explore_id")
        self.assertEqual(by.loc[eid, "code"], "df.describe()")
        self.assertEqual(by.loc[eid, "promoted"], "ใช่")
        self.assertEqual(by.loc[eid, "promoted_by"], "สมหญิง")
        self.assertEqual(by.loc[eid, "promote_reason"], "ผู้ตรวจสอบเห็นว่าควรทบทวน")
        self.assertEqual(by.loc[eid2, "promoted"], "ไม่")
        self.assertIn("2", by.loc[eid, "result_summary"])
        ir = pd.read_excel(x, sheet_name="Intake_Review", dtype=str).fillna("")
        text = " ".join(ir.astype(str).to_numpy().ravel())
        for needle in ("สินเชื่อเช่าซื้อ", "C-R1", "ผู้ตรวจสอบทดสอบ"):
            self.assertIn(needle, text)
        dd = pd.read_excel(x, sheet_name="Data_Dictionary", dtype=str).fillna("")
        self.assertTrue({"column", "meaning", "role", "code_values", "confirmed_by", "confirmed_at"} <= set(dd.columns))
        row = dd[dd["column"] == "pay_amount"].iloc[0]
        self.assertEqual(row["role"], "amount")
        self.assertIn("ยอดชำระสุทธิ", row["meaning"])
        st = dd[dd["column"] == "status"].iloc[0]
        self.assertIn("C", st["code_values"])
        dr = pd.read_excel(x, sheet_name="Data_Request", dtype=str)
        self.assertGreaterEqual(len(dr), 1)
        fnd_sheet = pd.read_excel(x, sheet_name="Findings", dtype=str)
        pr = fnd_sheet[fnd_sheet["finding_id"] == fnd["finding_id"]].iloc[0]
        self.assertEqual(pr["source_label"], "จากโหมดสำรวจ")
        readme = " ".join(pd.read_excel(x, sheet_name="README").iloc[:, 0].astype(str))
        self.assertIn("จากโหมดสำรวจ", readme)

    def test_outputs_keep_xss_and_formula_guards(self):
        e = engine()
        it, path = fresh("C", "xss")
        out = tmp("out-C-xss")
        eid = e.explore_log("<img src=x onerror=window.__x=1> =SUM(1)", XSS_CODE, pd.DataFrame({"a": ["=1+1", "<b>x</b>"]}),
                            note="+cmd|' /C calc'!A0", intake=it)
        e.promote(eid, "<script>window.__x=1</script>", "RX", "2026-03", "@evil", "-reviewer", intake=it)
        res = e.run(to.files("C"), it, str(out))
        ws = openpyxl.load_workbook(res["paths"]["workbook"])["Exploratory"]
        cells = [c for row in ws.iter_rows(min_row=2) for c in row if isinstance(c.value, str)]
        starts = [c.value for c in cells if c.value[:1] in "=+-@\t\r"]
        self.assertEqual([v for v in starts if v != "-"], [])
        q = [c.value for c in cells if "img src" in c.value][0]
        self.assertTrue(q.startswith("<img"))  # text kept, not a formula
        code = [c.value for c in cells if "HYPERLINK" in c.value][0]
        self.assertTrue(code.startswith("'="))
        fw = openpyxl.load_workbook(res["paths"]["workbook"])["Findings"]
        self.assertEqual([c.value for c in fw[1]].count("reviewer"), 1)
        html = Path(res["paths"]["dashboard"]).read_text(encoding="utf-8")
        data = html.split('<script id="aida-data" type="application/json">')[1].split("</script>")[0]
        self.assertNotIn("<", data)
        self.assertNotIn("<img src=x", html)
        self._browser(res, "xss")

    def _browser(self, res, tag):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require('playwright')"], capture_output=True).returncode:
            self.skipTest("node + playwright not available")
        shots = tmp(f"shots-{tag}")
        out = subprocess.run([node, str(HERE / "explore_smoke.js"), res["paths"]["dashboard"], str(shots)],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        b = json.loads(out.stdout)
        self.assertEqual(b["errors"], [])
        self.assertEqual(b["requests"], [])
        self.assertTrue(b["xss"])
        self.assertEqual(b["injected"], 0)
        return b

    def test_dashboard_intake_tab_and_badge(self):
        b = self._browser(self.c[2], "c")
        self.assertIn("Intake", b["tabs"])
        self.assertNotIn("Mule Networks", b["tabs"])
        self.assertNotIn("Money Flow", b["tabs"])
        self.assertTrue(b["badge_visible"])
        self.assertEqual(set(b["badges"]), {"จากโหมดสำรวจ"})
        self.assertIn("สินเชื่อเช่าซื้อ", b["intake_text"])
        self.assertIn("df.describe()", b["intake_text"])
        self.assertIn("คำถามนอกการ์ด", b["intake_text"])
        self.assertGreaterEqual(b["intake_pre"], 1)
        be = self._browser(self.e[2], "e")
        self.assertIn("Intake", be["tabs"])
        self.assertIn("Mule Networks", be["tabs"])
        self.assertIn("Money Flow", be["tabs"])
        self.assertTrue(be["badge_visible"])


if __name__ == "__main__":
    unittest.main()
