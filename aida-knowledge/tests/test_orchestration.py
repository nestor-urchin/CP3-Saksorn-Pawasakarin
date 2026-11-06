"""Tests for AIDA C1 task 7: inspect / confirm / run, intake.json, trace and mapping profiles.

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

from _engine import ENGINE_PATH, engine  # noqa: E402
import sample_common as sc  # noqa: E402

ROOT = HERE.parent
SAMPLES = ROOT / "samples"
CONFIRM_LINE = "ยืนยันทั้งหมด หรือแก้เฉพาะข้อ ⚠️ ❓ D แล้วเริ่มวิเคราะห์"
ACCUSE = ("บัญชีม้า", "ทุจริต")
_TMP = {}
_CACHE = {}


def tmpdir():
    if "d" not in _TMP:
        _TMP["d"] = tempfile.mkdtemp(prefix="aida-t7-")
    return _TMP["d"]


def tearDownModule():
    if "d" in _TMP:
        shutil.rmtree(_TMP["d"], True)


def files(name):
    if name == "E":
        return {"transactions": str(SAMPLES / "transactions.csv"), "accounts": str(SAMPLES / "accounts.csv")}
    tables = {"C": ("payments", "contracts"), "A": ("payments",)}[name]
    return {t: str(SAMPLES / name / f"{t}.csv") for t in tables}


def brief(name):
    return sc.load_brief(SAMPLES / name / "brief.md")


def roles(name):
    return json.loads((SAMPLES / name / "variants" / "roles_en.json").read_text(encoding="utf-8"))


def key(name):
    p = SAMPLES / "answer_key.json" if name == "E" else SAMPLES / name / "answer_key.json"
    return json.loads(p.read_text(encoding="utf-8"))


def key_set(name):
    return {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key(name)["findings"]}


def finding_set(f):
    return set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"]))


def answers(name, **kw):
    a = {"roles": roles(name), "add_risks": [] if name == "E" else key(name)["intake"]["suggested_risks"],
         "filters": [{"column": "status", "op": "!=", "value": "C"}] if name == "C" else [],
         "materiality": {"type": "ก", "amount": 1_000_000, "basis": "ทดสอบ"} if name == "E" else {"type": "ไม่ระบุ"},
         "reviewer": "ผู้ตรวจสอบทดสอบ"}
    a.update(kw)
    return a


def inspected(name):
    if ("i", name) not in _CACHE:
        _CACHE[("i", name)] = engine().inspect(files(name), brief(name))
    return _CACHE[("i", name)]


def confirmed(name):
    """(confirmed intake, path of its intake.json)."""
    if ("c", name) not in _CACHE:
        path = str(Path(tmpdir()) / f"intake-{name}.json")
        _CACHE[("c", name)] = (engine().confirm(inspected(name)["intake"], answers(name), path), path)
    return _CACHE[("c", name)]


def ran(name):
    if ("r", name) not in _CACHE:
        out = Path(tmpdir()) / f"out-{name}"
        out.mkdir(exist_ok=True)
        _CACHE[("r", name)] = engine().run(files(name), confirmed(name)[0], str(out))
    return _CACHE[("r", name)]


def section(text, letter):
    """The text of section A-E of a review (up to the next section header)."""
    m = re.search(rf"^{letter}\. .*?(?=^[A-E]\. |\Z)", text, re.S | re.M)
    return m.group(0) if m else ""


class Inspect(unittest.TestCase):
    def test_inspect_c_review_sections(self):
        r = inspected("C")
        text = r["review_th"]
        heads = [text.find(f"\n{x}. ") for x in "ABCDE"]
        self.assertTrue(all(h >= 0 for h in heads), heads)
        self.assertEqual(heads, sorted(heads))
        a = section(text, "A")
        conflict = [ln for ln in a.splitlines() if "pay_amount" in ln and "⚠️" in ln]
        self.assertTrue(conflict, a)
        self.assertIn("ค่าติดลบ", a)
        b = section(text, "B")
        self.assertIn(key("C")["intake"]["data_request"][0], b)
        for rid, st in key("C")["intake"]["sufficiency"].items():
            icon = {"พร้อม": "✅", "บางส่วน": "🟡", "ไม่พอ": "❌"}[st]
            self.assertTrue(any(rid in ln and icon in ln for ln in b.splitlines()), (rid, b))
        d = section(text, "D")
        self.assertIn("C-R3", d)
        e = section(text, "E")
        self.assertIn("Materiality", e)
        self.assertIn("Run", e)
        self.assertTrue(text.rstrip().endswith(CONFIRM_LINE))
        for w in ACCUSE:
            self.assertNotIn(w, text)

    def test_inspect_numbers_come_from_engine(self):
        r = inspected("C")
        n = len(pd.read_csv(files("C")["payments"], dtype=str))
        self.assertIn(f"{n:,}", r["review_th"])
        neg = int((pd.read_csv(files("C")["payments"])["pay_amount"] < 0).sum())
        self.assertIn(f"{neg:,}", section(r["review_th"], "A"))

    def test_inspect_intake_draft(self):
        it = inspected("C")["intake"]
        self.assertEqual(it["status"], "draft")
        self.assertEqual(set(it["files"]), {"payments", "contracts"})
        for meta in it["files"].values():
            self.assertRegex(meta["sha256"], r"^[0-9a-f]{64}$")
        self.assertIn("sha256:", it["data_ref"])
        self.assertEqual(it["roles"]["payments"]["pay_amount"], "amount")
        self.assertEqual(sorted(it["risks"]["requested"]), sorted(["C-R1", "C-R2", "R1"]))
        self.assertEqual([s["risk_id"] for s in it["suggested_risks"]], ["C-R3"])
        self.assertEqual(it["risks"]["added"], [])  # D is not added until the auditor answers
        self.assertEqual([c["column"] for c in it["description_conflicts"]], key("C")["intake"]["description_conflicts"])
        json.dumps(it, ensure_ascii=False)  # serialisable as is

    def test_inspect_a_no_data_request(self):
        text = inspected("A")["review_th"]
        self.assertIn("ไม่มี", section(text, "B"))
        d = section(text, "D")
        for rid in key("A")["intake"]["suggested_risks"]:
            self.assertIn(rid, d)

    def test_unmatched_concern_goes_to_exploratory(self):
        b = dict(brief("A"))
        b["concerns"] = b["concerns"] + ["ราคาที่จ่ายสูงกว่าราคาตลาด"]
        r = engine().inspect(files("A"), b)
        bsec = section(r["review_th"], "B")
        line = [ln for ln in bsec.splitlines() if "ราคาที่จ่ายสูงกว่าราคาตลาด" in ln]
        self.assertTrue(line and "จะวิเคราะห์ในโหมดสำรวจ" in line[0], bsec)
        self.assertEqual(r["intake"]["risks"]["exploratory"], ["ราคาที่จ่ายสูงกว่าราคาตลาด"])

    def test_files_as_list_and_xlsx_sheets(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "tx"
        ws.append(["tx_id", "ts", "acct", "amount"])
        for i in range(1, 41):
            ws.append([f"{i:05d}", f"2026-0{1 + i % 8}-1{i % 9} 10:00", f"00{100 + i % 7}", f"{1000 + i * 37}.50"])
        ws2 = wb.create_sheet("acc")
        ws2.append(["acct", "opened_at"])
        for i in range(7):
            ws2.append([f"00{100 + i}", "2025-01-01"])
        p = d / "book.xlsx"
        wb.save(p)
        csv = d / "extra.csv"
        csv.write_text("code,value\n007,1\n010,2\n", encoding="utf-8")
        r = engine().inspect([str(p), str(csv)])
        it = r["intake"]
        self.assertEqual(set(it["files"]), {"book.tx", "book.acc", "extra"})
        prof = {(c["table"], c["column"]): c for c in it["profile"]}
        self.assertIn("00001", prof[("book.tx", "tx_id")]["samples"])  # leading zeros survive (read as text)
        self.assertIn("007", prof[("extra", "code")]["samples"])
        self.assertEqual(it["files"]["book.tx"]["sha256"], it["files"]["book.acc"]["sha256"])

    def test_xlsx_sheet_name_with_dot_runs_from_intake_paths(self):
        e = engine()
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "tx.2026"
        ws.append(["tx_id", "ts", "acct", "amount"])
        for i in range(1, 41):
            ws.append([f"{i:05d}", f"2026-0{1 + i % 8}-1{i % 9}", f"A{i % 5}", f"{1000 + i * 37}.50"])
        p = d / "book.v2.xlsx"
        wb.save(p)
        it = e.inspect([str(p)])["intake"]
        self.assertEqual(list(it["files"]), ["book.v2.tx.2026"])
        c = e.confirm(it, {"roles": {"book.v2.tx.2026": {"tx_id": "record_id", "ts": "date", "acct": "entity",
                                                          "amount": "amount"}}}, str(d / "intake.json"))
        r = e.run(None, str(d / "intake.json"), str(d))  # files taken from the intake
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["warnings"], [])

    def test_missing_file_thai_error(self):
        with self.assertRaises(engine().AidaError) as cm:
            engine().inspect({"payments": "/no/such/file.csv"})
        msg = str(cm.exception)
        self.assertRegex(msg, r"[ก-๙]")
        self.assertIn("file.csv", msg)
        self.assertIsInstance(cm.exception, ValueError)


class Confirm(unittest.TestCase):
    def test_confirm_rejects_duplicate_role(self):
        e = engine()
        it = inspected("A")["intake"]
        path = str(Path(tmpdir()) / "dup.json")
        bad = answers("A", roles={"payments": {**roles("A")["payments"], "invoice_no": "record_id"}})
        with self.assertRaises(e.AidaError) as cm:
            e.confirm(it, bad, path)
        msg = str(cm.exception)
        self.assertIn("record_id", msg)
        self.assertIn("payment_id", msg)
        self.assertIn("invoice_no", msg)
        self.assertRegex(msg, r"[ก-๙]")
        # one column given two certified roles
        bad2 = answers("A", roles={"payments": {**roles("A")["payments"], "invoice_no": ["record_id", "document_no"]}})
        with self.assertRaises(e.AidaError):
            e.confirm(it, bad2, path)
        self.assertFalse(Path(path).exists())
        # an explicitly confirmed custom role next to a certified one is allowed
        ok = answers("A", roles={"payments": {**roles("A")["payments"], "invoice_no": ["document_no", "custom:inv"]}})
        c = e.confirm(it, ok, path)
        self.assertEqual(c["roles"]["payments"]["invoice_no"], ["document_no", "custom:inv"])

    def test_confirm_flat_answer_cannot_duplicate_a_suggestion(self):
        """A flat {column: role} answer that takes a role the draft gave another column moves the role."""
        e = engine()
        it = inspected("A")["intake"]
        c = e.confirm(it, {"roles": {"invoice_no": "custom:inv", "approval_limit": "limit"}, "reviewer": "x"},
                      str(Path(tmpdir()) / "flat.json"))
        self.assertEqual(c["roles"]["payments"]["invoice_no"], "custom:inv")
        self.assertNotIn("document_no", c["roles"]["payments"].values())

    def test_confirm_unknown_key_message_thai(self):
        e = engine()
        it = inspected("A")["intake"]
        path = str(Path(tmpdir()) / "unknown.json")
        for bad, word in ((answers("A", org_values={"DUP.WINDOW": 5}), "DUP.WINDOW"),
                          (answers("A", add_risks=["Z-R9"]), "Z-R9"),
                          (answers("A", roles={"payments": {"payment_id": "record_key"}}), "record_key"),
                          (answers("A", roles={"payments": {"no_such_col": "amount"}}), "no_such_col"),
                          (answers("A", org_values={"DUP.WINDOW_DAYS": "สามวัน"}), "DUP.WINDOW_DAYS"),
                          (answers("A", materiality={"type": "ก"}), "Materiality"),
                          (answers("A", filters=[{"column": "nope", "op": "==", "value": 1}]), "nope")):
            with self.assertRaises(e.AidaError, msg=word) as cm:
                e.confirm(it, bad, path)
            msg = str(cm.exception)
            self.assertIn(word, msg)
            self.assertRegex(msg, r"[ก-๙]")
            self.assertNotIn("Traceback", msg)
        self.assertFalse(Path(path).exists())

    def test_intake_json_is_self_sufficient(self):
        c, path = confirmed("C")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for k in ("roles", "filters", "org_values", "risks", "materiality", "reviewer", "files", "data_ref",
                  "registry_version", "engine_version", "confirmed_at"):
            self.assertIn(k, data)
        self.assertEqual(data["status"], "confirmed")
        self.assertEqual(data["engine_version"], engine().__version__)
        self.assertEqual(data["registry_version"], engine().REGISTRY_VERSION)
        self.assertEqual(data["risks"]["added"], ["C-R3"])
        self.assertEqual(data["filters"], [{"column": "status", "op": "!=", "value": "C"}])
        self.assertEqual(data["materiality"]["type"], "ไม่ระบุ")
        self.assertEqual(data["reviewer"], "ผู้ตรวจสอบทดสอบ")

    def test_materiality_default_and_no_d(self):
        c = engine().confirm(inspected("A")["intake"], {"roles": roles("A")}, str(Path(tmpdir()) / "min.json"))
        self.assertEqual(c["materiality"]["type"], "ไม่ระบุ")
        self.assertEqual(c["risks"]["added"], [])


class Run(unittest.TestCase):
    def test_run_c_findings_match_key(self):
        r = ran("C")
        self.assertEqual(finding_set(r["findings"]), key_set("C"))
        for p in (r["paths"]["workbook"], r["paths"]["dashboard"]):
            self.assertTrue(Path(p).exists())
        self.assertTrue(r["summary_th"])
        for w in ACCUSE:
            self.assertNotIn(w, r["summary_th"])

    def test_run_a_findings_match_key(self):
        self.assertEqual(finding_set(ran("A")["findings"]), key_set("A"))

    def test_run_e_matches_b1_key(self):
        r = ran("E")
        self.assertEqual(finding_set(r["findings"]), key_set("E"))
        self.assertEqual(len(r["findings"]), 19)
        nets = r["findings"][r["findings"]["entity_type"] == "network"]
        self.assertEqual(len(nets), 1)
        self.assertEqual(sorted(nets["member_accts"].iloc[0]), sorted(key("E")["networks"][0]["members"]))
        self.assertTrue(Path(r["paths"]["csv_dir"]).is_dir())
        wb = openpyxl.load_workbook(r["paths"]["workbook"])
        self.assertGreater(wb["Money_Flow"].max_row, 2)

    def test_summary_numbers_from_findings(self):
        r = ran("A")
        self.assertIn(f"{len(r['findings']):,}", r["summary_th"])

    def test_run_from_intake_json_fresh_process(self):
        _, path = confirmed("A")
        first = ran("A")["findings"]
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        code = (
            "import importlib.util, json, sys\n"
            f"spec = importlib.util.spec_from_file_location('aida_engine', {str(ENGINE_PATH)!r})\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            f"r = m.run({files('A')!r}, {path!r}, {str(out)!r})\n"
            "f = r['findings']\n"
            "print(json.dumps(sorted([[a, b, c, d, float(x)] for a, b, c, d, x in zip(f['entity_type'], "
            "f['entity_id'], f['risk'], f['period'], f['exposure'])]), ensure_ascii=False))\n")
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(out), timeout=600)
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        got = json.loads(res.stdout.strip().splitlines()[-1])
        want = sorted([[a, b, c, d, float(x)] for a, b, c, d, x in zip(
            first["entity_type"], first["entity_id"], first["risk"], first["period"], first["exposure"])])
        self.assertEqual(got, want)
        self.assertTrue((out / "AIDA-workbook.xlsx").exists())

    def test_run_warns_when_file_changed(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        src = Path(files("A")["payments"])
        p = d / "payments.csv"
        shutil.copy(src, p)
        e = engine()
        it = e.inspect([str(p)], brief("A"))["intake"]
        c = e.confirm(it, answers("A"), str(d / "intake.json"))
        same = e.run([str(p)], str(d / "intake.json"), str(d))
        self.assertEqual(same["warnings"], [])
        lines = p.read_text(encoding="utf-8").splitlines()
        lines[5] = lines[5].replace(",U0", ",U9", 1)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = e.run([str(p)], c, str(d))
        self.assertTrue(r["warnings"])
        self.assertIn("payments", r["warnings"][0])
        self.assertIn("sha256", r["warnings"][0])
        self.assertRegex(r["warnings"][0], r"[ก-๙]")
        self.assertIn(r["warnings"][0], r["summary_th"])
        log = r["run_log"]
        self.assertTrue(((log["status"] == "REVIEW") & log["detail"].str.contains("sha256")).any())

    def test_org_value_override_recorded(self):
        e = engine()
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        c = e.confirm(inspected("A")["intake"], answers("A", org_values={"DUP.WINDOW_DAYS": 1}),
                      str(d / "intake.json"))
        self.assertEqual(c["org_values"], {"DUP.WINDOW_DAYS": 1})
        r = e.run(files("A"), str(d / "intake.json"), str(d))
        got = finding_set(r["findings"])
        self.assertNotIn(("document", "INV-7781", "A-R1", "2026-04"), got)  # 2-day gap > org window of 1 day
        self.assertEqual(got, key_set("A") - {("document", "INV-7781", "A-R1", "2026-04")})
        log = r["run_log"]
        org = log[log["detail"].str.contains("ค่าขององค์กร")]
        self.assertEqual(len(org), 1)
        self.assertIn("DUP.WINDOW_DAYS", org["detail"].iloc[0])
        self.assertIn("3", org["detail"].iloc[0])  # the AIDA-14 standard value it replaces
        wb = openpyxl.load_workbook(r["paths"]["workbook"])
        readme = " ".join(str(x.value) for row in wb["README"].iter_rows() for x in row if x.value)
        self.assertIn("ค่าขององค์กร", readme)
        self.assertIn("DUP.WINDOW_DAYS", readme)
        # the standard value is untouched for the next run
        self.assertEqual(e.load_registry(e.default_registry_path())["DUP.WINDOW_DAYS"], 3)

    def test_filters_applied_and_logged(self):
        r = ran("C")
        log = r["run_log"]
        f = log[log["detail"].str.contains("ตัวกรอง")]
        n_c = int((pd.read_csv(files("C")["payments"], dtype=str)["status"] == "C").sum())
        self.assertTrue(f["detail"].str.contains(f"{n_c:,}").any(), list(f["detail"]))

    def test_run_revalidates_org_values(self):
        _, path = confirmed("A")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        data["org_values"] = {"DUP.WINDOWS": 2}
        bad = Path(tmpdir()) / "bad-org.json"
        bad.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(engine().AidaError) as cm:
            engine().run(files("A"), str(bad), tmpdir())
        self.assertIn("DUP.WINDOWS", str(cm.exception))
        self.assertIn("AIDA-14", str(cm.exception))

    def test_run_rejects_draft_intake(self):
        with self.assertRaises(engine().AidaError) as cm:
            engine().run(files("A"), inspected("A")["intake"], tmpdir())
        self.assertIn("confirm", str(cm.exception))

    def test_trace_e(self):
        e = engine()
        c, _ = confirmed("E")
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out, True)
        r = e.trace(files("E"), c, "N01", direction="forward", out_dir=str(out))
        self.assertGreater(len(r["trails"]), 0)
        self.assertTrue(Path(r["path"]).exists())
        self.assertRegex(r["summary_th"], r"[ก-๙]")
        with self.assertRaises(e.AidaError):
            e.trace(files("E"), c, "N01", direction="sideways", out_dir=str(out))
        ca, _ = confirmed("A")
        with self.assertRaises(e.AidaError):  # no counterparty: no money flow
            e.trace(files("A"), ca, "V-031", out_dir=str(out))


class DescriptionHead(unittest.TestCase):
    """match_description matches the head of a description (fix round 1, Important 1)."""
    def test_description_head_and_weak_modifiers(self):
        e = engine()
        cases = {"vendor invoice number": "document_no", "ยอดวงเงิน": "limit", "ยอดวงเงินอนุมัติ": "limit",
                 "limit amount": "limit", "จำนวนเงินที่จ่ายจริงต่อใบแจ้งหนี้": "amount", "amount per invoice": "amount",
                 "วันครบกำหนดชำระของงวดนั้น": "due_date", "เลขที่ใบแจ้งหนี้ของผู้ขาย": "document_no",
                 "วันที่รับชำระ": "date", "เลขที่รายการจ่าย": "record_id", "วันเวลาที่ทำรายการ": "date"}
        for text, role in cases.items():
            self.assertEqual(e.match_description(text), role, text)

    def test_sample_a_amount_line(self):
        it = inspected("A")["intake"]
        self.assertEqual(it["roles"]["payments"]["amount"], "amount")
        self.assertEqual(it["roles"]["payments"]["invoice_no"], "document_no")
        st = {s["risk_id"]: s["status"] for s in it["sufficiency"]}
        self.assertEqual(st, key("A")["intake"]["sufficiency"])


class AbsorbBySharedRecords(unittest.TestCase):
    """FOR-REPEAT / FOR-ROUND fold into the SPLIT-LIMIT Finding only for the same records (Important 2)."""
    def _ev(self, rid, risk, refs, period="2026-06"):
        return {"evidence_id": f"{rid}-1", "run_id": "T", "recipe_id": rid, "recipe_version": "1.0",
                "skill_family": "f", "entity_type": "entity", "entity_id": "V-045", "risk": risk, "period": period,
                "metric": "m", "value": 1, "threshold": 1, "registry_key": "K", "registry_version": "1.2",
                "explanation": "x", "record_refs": refs, "data_ref": "d"}

    def test_unit(self):
        e = engine()
        tx = pd.DataFrame({"tx_id": ["a", "b", "c", "x", "y", "z"], "amount": [1.0] * 6})
        same = pd.DataFrame([self._ev("SPLIT-LIMIT", "A-R2", ["a", "b", "c"]), self._ev("FOR-REPEAT", "G-R4", ["a", "b", "c"])])
        self.assertEqual(list(e._finding_view(same, tx, "A")["risk"]), ["A-R2", "A-R2"])
        other = pd.DataFrame([self._ev("SPLIT-LIMIT", "A-R2", ["a", "b", "c"]), self._ev("FOR-REPEAT", "G-R4", ["x", "y", "z"])])
        self.assertEqual(list(e._finding_view(other, tx, "A")["risk"]), ["A-R2", "G-R4"])
        mixed = pd.DataFrame([self._ev("SPLIT-LIMIT", "A-R2", ["a", "b", "c"]),
                              self._ev("FOR-REPEAT", "G-R4", ["a", "b", "c", "x", "y", "z"])])
        self.assertEqual(list(e._finding_view(mixed, tx, "A")["risk"]), ["A-R2", "G-R4"])

    def test_rent_repeats_on_split_vendor_stay_g_r4(self):
        e = engine()
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        df = pd.read_csv(files("A")["payments"], dtype=str)
        rent = [{"payment_id": f"PAY-RENT-{i}", "pay_date": f"2026-06-0{i + 2}", "amount": "12345.67",
                 "vendor_id": "V-045", "invoice_no": f"INV-RENT-{i}", "created_by": "U001", "approved_by": "M001",
                 "approval_limit": "50000.0", "category": "ค่าเช่า"} for i in range(3)]
        df = pd.concat([df, pd.DataFrame(rent)], ignore_index=True)
        p = d / "payments.csv"
        df.to_csv(p, index=False)
        it = e.inspect([str(p)], brief("A"))["intake"]
        c = e.confirm(it, answers("A"), str(d / "intake.json"))
        r = e.run([str(p)], c, str(d))
        got = finding_set(r["findings"])
        self.assertIn(("vendor", "V-045", "G-R4", "2026-06"), got)
        self.assertIn(("vendor", "V-045", "A-R2", "2026-06"), got)
        f = r["findings"].set_index(["entity_id", "risk"])
        self.assertEqual(f.loc[("V-045", "A-R2"), "exposure"], 144000.0)  # the split only, no rent records
        self.assertFalse(set(f.loc[("V-045", "A-R2"), "record_refs"]) & {x["payment_id"] for x in rent})


class Mapping(unittest.TestCase):
    def test_save_and_load_mapping(self):
        e = engine()
        c, _ = confirmed("C")
        p = e.save_mapping(c, str(Path(tmpdir()) / "mapping-c.json"))
        m = e.load_mapping(p)
        for k in ("roles", "columns", "code_values", "filters", "org_values", "confirmed_by", "confirmed_at",
                  "signature"):
            self.assertIn(k, m)
        self.assertEqual(m["roles"], c["roles"])
        self.assertEqual(m["code_values"]["payments.status"], {"P": "บันทึกแล้ว", "C": "ยกเลิก"})
        self.assertEqual(m["confirmed_by"], "ผู้ตรวจสอบทดสอบ")
        with self.assertRaises(e.AidaError):
            e.load_mapping(str(Path(tmpdir()) / "none.json"))

    def test_mapping_reuse_reports_only_changes(self):
        e = engine()
        c, _ = confirmed("A")
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d, True)
        mp = e.save_mapping(c, str(d / "mapping-a.json"))
        df = pd.read_csv(files("A")["payments"], dtype=str)
        df = df.rename(columns={"invoice_no": "inv_ref"}).drop(columns=["approval_limit"])
        df["remark"] = "ปกติ"
        df["created_by"] = [str(1000 + i % 30) for i in range(len(df))]  # text user ids -> numbers
        p = d / "payments.csv"
        df.to_csv(p, index=False)
        r = e.inspect([str(p)], mapping=mp)
        ch = r["intake"]["changes"]
        self.assertEqual(sorted(ch["added"]), ["payments.inv_ref", "payments.remark"])
        self.assertEqual(sorted(ch["removed"]), ["payments.approval_limit", "payments.invoice_no"])
        self.assertEqual(ch["changed_pattern"], ["payments.created_by"])
        self.assertEqual(r["changes"], ch)
        roles_now = r["intake"]["roles"]["payments"]
        for col in ("payment_id", "pay_date", "amount", "vendor_id", "approved_by", "category"):
            self.assertEqual(roles_now[col], c["roles"]["payments"][col])  # kept from the mapping
        a = section(r["review_th"], "A")
        asked = [ln for ln in a.splitlines() if "⚠️" in ln or "❓" in ln or "⚪" in ln]
        named = {col for ln in asked for col in ("inv_ref", "remark", "created_by", "invoice_no", "approval_limit",
                                                    "payment_id", "pay_date", "vendor_id", "approved_by", "category")
                 if re.search(rf"\b{col}\b", ln)}
        self.assertTrue({"inv_ref", "remark", "created_by"} <= named, a)
        self.assertFalse(named & {"payment_id", "pay_date", "vendor_id", "approved_by", "category"}, a)
        self.assertIn("invoice_no", a)
        self.assertIn("approval_limit", a)
        self.assertTrue(r["review_th"].rstrip().endswith(CONFIRM_LINE))
        # the mapping's filters, org values and reviewer are pre-filled
        self.assertEqual(r["intake"]["org_values"], c["org_values"])
        self.assertEqual(r["intake"]["filters"], c["filters"])

    def test_mapping_same_files_no_changes(self):
        e = engine()
        c, _ = confirmed("C")
        mp = e.save_mapping(c, str(Path(tmpdir()) / "mapping-c2.json"))
        r = e.inspect(files("C"), brief("C"), mapping=mp)
        self.assertEqual(r["changes"], {"added": [], "removed": [], "changed_pattern": []})
        self.assertEqual(r["intake"]["roles"], c["roles"])
        self.assertEqual(r["intake"]["filters"], c["filters"])
        # the earlier confirmer is shown, but this round's reviewer is not pre-filled
        self.assertIsNone(r["intake"]["reviewer"])
        self.assertEqual(r["intake"]["mapping"]["confirmed_by"], "ผู้ตรวจสอบทดสอบ")
        self.assertIn("ผู้ตรวจสอบทดสอบ", r["review_th"])


if __name__ == "__main__":
    unittest.main()
