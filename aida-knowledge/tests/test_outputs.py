"""Tests for the output cards in AIDA-19 (OUT-BUNDLE, OUT-WORKBOOK, OUT-NETWORK-CSV,
OUT-DASHBOARD) and the dashboard template in AIDA-16.

The whole chain runs on the raw sample CSVs (test_pipeline.run_chain), then SELECT-AUTO-TRACE,
FLOW-TRACE (both directions), LOG-RUN and the output cards, as Copilot would at step 8.
The browser test opens the dashboard in Chromium (Playwright) when node + playwright exist.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import openpyxl
import pandas as pd

import test_pipeline as tp
import test_recipes as tr
from test_recipes import CFG, KNOWLEDGE, answer_key

R = tr.recipes
HERE = Path(__file__).resolve().parent
SHEETS = ["README", "Dataset_Profile", "Analysis_Plan", "Evidence", "Findings", "Mule_Networks",
          "Money_Flow", "Materiality", "Run_Log"]
TABS = ["สรุป", "Findings", "Mule Networks", "Money Flow", "Run Log"]
BANNER = ("ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร "
          "ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป")
TRAIL_COLUMNS = ["trace_id", "start_acct", "direction", "hop", "from_acct", "to_acct", "amount",
                 "ts", "tx_id"]
FINDING_SHEET_COLUMNS = tp.FINDING_COLUMNS + ["member_accts", "reviewer", "disposition", "review_date"]
DATA_RE = re.compile(r'<script id="aida-data" type="application/json">(.*?)</script>', re.S)


def template() -> str:
    """The ```html block of AIDA-16, as Copilot retrieves it from Knowledge."""
    text = (KNOWLEDGE / "AIDA-16-output-templates.md").read_text(encoding="utf-8")
    m = re.search(r"^```html\n(.*?)^```$", text, re.S | re.M)
    if not m:
        raise AssertionError("AIDA-16 has no ```html block")
    return m.group(1)


def build_bundle(chain=None, cfg=CFG, materiality=1_000_000.0):
    """Steps 7-8 after ASSESS-CMP: auto traces in both directions, Run Log, OUT-BUNDLE."""
    c = chain or tp.sample_chain()
    tables, findings = c["tables"], c["assessed"]
    trails = [R()["flow_trace"](tables, cfg, a, d, p)
              for a, p in R()["select_auto_trace"](findings, cfg) for d in ("forward", "backward")]
    log = R()["log_run"]([{"stage": 3, "status": "OK", "detail": c["status"], "recipe_id": "PROF-PROFILE"},
                          {"stage": 8, "status": "REVIEW", "detail": "รอ Human Review"}], cfg)
    return R()["out_bundle"](tables, c["profile"], c["plan"], c["evidence"], findings, trails, log,
                             materiality, cfg, "แบบ ก. ทดสอบ")


_B = {}


def sample_bundle():
    if not _B:
        _B.update(build_bundle())
    return _B


def write_all(bundle, folder):
    wb = R()["out_workbook"](bundle, str(Path(folder) / "AIDA-workbook.xlsx"), CFG)
    csvs = R()["out_network_csv"](bundle, str(Path(folder) / "network"), CFG)
    html = R()["out_dashboard"](bundle, template(), str(Path(folder) / "AIDA-dashboard.html"), CFG)
    return wb, csvs, html


def embedded(html_text):
    m = DATA_RE.search(html_text)
    if not m:
        raise AssertionError("no embedded data script")
    return json.loads(m.group(1))


class OutputCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)


# ---------------------------------------------------------------- OUT-BUNDLE
class TestBundle(OutputCase):
    def test_bundle_keys(self):
        b = sample_bundle()
        for k in ("profile", "plan", "evidence", "findings", "mule_networks", "flows", "materiality",
                  "run_log", "run_id", "prep", "flow_notes", "edges"):
            self.assertIn(k, b)
        self.assertEqual(b["run_id"], CFG["_RUN"]["run_id"])
        self.assertEqual(list(b["flows"].columns), TRAIL_COLUMNS)
        self.assertGreater(len(b["flows"]), 0)
        self.assertEqual(b["flow_notes"], [])
        self.assertEqual(list(b["edges"].columns), ["source", "target", "amount", "ts", "tx_id", "network_id"])
        self.assertTrue(b["edges"]["tx_id"].is_unique)

    def test_materiality_with_and_without_base(self):
        m = sample_bundle()["materiality"]
        self.assertEqual(list(m.columns), ["item", "value", "detail"])
        self.assertIn(1_000_000.0, list(m["value"]))
        none = build_bundle(materiality=None)["materiality"]
        self.assertIn("ไม่ได้ประเมิน", " ".join(map(str, none["value"])))

    def test_truncated_trace_note_kept(self):
        cfg = {**CFG, "FLOW.MAX_TRAIL_ROWS": 2}
        b = build_bundle(cfg=cfg)
        self.assertTrue(b["flow_notes"])
        self.assertIn("FLOW.MAX_TRAIL_ROWS", b["flow_notes"][0])
        wb, _, html = write_all(b, self.dir)
        ws = openpyxl.load_workbook(wb)["Money_Flow"]
        cells = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
        self.assertIn("FLOW.MAX_TRAIL_ROWS", cells)
        data = embedded(Path(html).read_text(encoding="utf-8"))
        self.assertTrue(data["flow_notes"])


# ---------------------------------------------------------------- OUT-WORKBOOK
class TestWorkbook(OutputCase):
    def test_workbook_sheet_order(self):
        wb, _, _ = write_all(sample_bundle(), self.dir)
        book = openpyxl.load_workbook(wb)
        self.assertEqual(book.sheetnames, SHEETS)
        readme = " ".join(str(c.value) for row in book["README"].iter_rows() for c in row if c.value)
        self.assertIn(BANNER, readme)
        self.assertIn(CFG["_RUN"]["run_id"], readme)
        self.assertIn("ไม่มีข้อมูลระบุตัวตน", readme)
        for word in ("บัญชีม้า", "ทุจริต"):
            self.assertNotIn(word, readme)

    def test_findings_sheet_columns(self):
        b = sample_bundle()
        wb, _, _ = write_all(b, self.dir)
        f = pd.read_excel(wb, sheet_name="Findings")
        self.assertEqual(list(f.columns), FINDING_SHEET_COLUMNS)
        self.assertEqual(len(f), len(b["findings"]))
        self.assertTrue(f[["reviewer", "disposition", "review_date"]].isna().all().all())
        net = f[f["entity_type"] == "network"].iloc[0]
        self.assertEqual(set(net["member_accts"].split(", ")), set(answer_key()["networks"][0]["members"]))

    def test_evidence_sheet_keeps_record_refs(self):
        b = sample_bundle()
        wb, _, _ = write_all(b, self.dir)
        ev = pd.read_excel(wb, sheet_name="Evidence", dtype=str)
        self.assertEqual(list(ev.columns), list(b["evidence"].columns))
        first = b["evidence"]["record_refs"].iloc[0]
        self.assertEqual(ev["record_refs"].iloc[0], ", ".join(first))
        self.assertEqual(R()["unify_refs"].__globals__["ref_list"](ev["record_refs"].iloc[0]), first)

    def test_workbook_formula_guard(self):
        b = dict(sample_bundle())
        f = b["findings"].copy()
        f.loc[f.index[0], "entity_id"] = '=HYPERLINK("http://e","c")'
        f.loc[f.index[1], "entity_id"] = "+cmd|x"
        b["findings"] = f
        wb, _, _ = write_all(b, self.dir)
        ws = openpyxl.load_workbook(wb)["Findings"]
        self.assertEqual(ws["C2"].value, '\'=HYPERLINK("http://e","c")')
        self.assertEqual(ws["C3"].value, "'+cmd|x")
        self.assertEqual({ws["C2"].data_type, ws["C3"].data_type}, {"s"})
        plan = openpyxl.load_workbook(wb)["Analysis_Plan"]
        self.assertEqual(plan["D2"].value, "-")  # a bare "-" placeholder is not a formula

    def test_workbook_control_character(self):
        b = dict(sample_bundle())
        ev = b["evidence"].copy()
        ev.loc[ev.index[0], "explanation"] = "a\x0bb"
        b["evidence"] = ev
        wb, _, _ = write_all(b, self.dir)
        self.assertEqual(openpyxl.load_workbook(wb)["Evidence"]["O2"].value, "ab")

    def test_long_cell_capped_for_excel(self):
        b = dict(sample_bundle())
        ev = b["evidence"].copy()
        ev.at[ev.index[0], "record_refs"] = [f"T{i:06d}" for i in range(10000)]
        b["evidence"] = ev
        wb, _, _ = write_all(b, self.dir)
        cell = openpyxl.load_workbook(wb)["Evidence"]["P2"].value
        self.assertLessEqual(len(cell), 32767)
        self.assertTrue(cell.endswith("…"))


# ---------------------------------------------------------------- OUT-NETWORK-CSV
class TestNetworkCsv(OutputCase):
    def test_network_csv_columns(self):
        _, csvs, _ = write_all(sample_bundle(), self.dir)
        self.assertEqual([Path(p).name for p in csvs], ["nodes.csv", "edges.csv", "flows.csv"])
        nodes, edges, flows = (pd.read_csv(p, dtype=str) for p in csvs)
        self.assertEqual(list(nodes.columns), ["node_id", "role", "network_id", "finding_ids"])
        self.assertEqual(list(edges.columns), ["source", "target", "amount", "ts", "tx_id", "network_id"])
        self.assertEqual(list(flows.columns), TRAIL_COLUMNS)
        net = answer_key()["networks"][0]
        got = nodes[nodes["network_id"] == net["network_id"]].set_index("node_id")["role"].to_dict()
        self.assertEqual(got, net["roles"])
        self.assertTrue(set(nodes["role"]) <= {"mule", "collector", "feeder", "other"})
        self.assertTrue(nodes["node_id"].is_unique)
        self.assertLessEqual(set(edges["source"]) | set(edges["target"]), set(nodes["node_id"]))
        m01 = nodes.set_index("node_id").loc["M01"]
        self.assertEqual(m01["role"], "mule")
        self.assertTrue(pd.isna(m01["network_id"]))
        self.assertTrue(m01["finding_ids"].startswith("FND-"))

    def test_csv_formula_guard(self):
        b = dict(sample_bundle())
        e = b["edges"].copy()
        e.loc[e.index[0], "source"] = "=1+1"
        e.loc[e.index[1], "target"] = "@SUM(A1)"
        b["edges"] = e
        fl = b["flows"].copy()
        fl.loc[fl.index[0], "tx_id"] = "+cmd|x"
        fl.loc[fl.index[1], "from_acct"] = "\t-2"
        b["flows"] = fl
        f = b["findings"].copy()
        f.loc[f.index[0], "entity_id"] = "-1+2"
        b["findings"] = f
        _, csvs, _ = write_all(b, self.dir)
        nodes, edges, flows = (pd.read_csv(p, dtype=str, keep_default_na=False) for p in csvs)
        self.assertEqual(edges["source"].iloc[0], "'=1+1")
        self.assertEqual(edges["target"].iloc[1], "'@SUM(A1)")
        self.assertEqual(flows["tx_id"].iloc[0], "'+cmd|x")
        self.assertEqual(flows["from_acct"].iloc[1], "'\t-2")
        self.assertIn("'-1+2", set(nodes["node_id"]))
        for df in (nodes, edges, flows):
            for col in df.columns:
                self.assertFalse(df[col].str.match(r"^[=+@\t\r]").any(), col)

    def test_network_members_list_network_finding(self):
        _, csvs, _ = write_all(sample_bundle(), self.dir)
        nodes = pd.read_csv(csvs[0], dtype=str).set_index("node_id")
        f = sample_bundle()["findings"]
        net_fid = f.loc[f["entity_type"] == "network", "finding_id"].iloc[0]
        self.assertIn(net_fid, nodes.loc["NC1", "finding_ids"].split("; "))


# ---------------------------------------------------------------- OUT-DASHBOARD + AIDA-16
class TestDashboard(OutputCase):
    def test_template_shape(self):
        t = template()
        self.assertEqual(t.count("/*__AIDA_DATA__*/"), 1)
        self.assertTrue(t.rstrip().endswith("<!-- END-OF-TEMPLATE -->"))
        self.assertLessEqual(len(t.splitlines()), 250)
        self.assertIn(BANNER, t)

    def test_dashboard_self_contained(self):
        _, _, html = write_all(sample_bundle(), self.dir)
        text = Path(html).read_text(encoding="utf-8")
        self.assertNotRegex(text, r"""(src|href)\s*=\s*["']?\s*(https?:|//)""")
        self.assertNotIn("@import", text)
        self.assertNotRegex(text, r"https?://")
        for tab in TABS:
            self.assertIn(f">{tab}</button>", text)
        self.assertIn(BANNER, text)
        self.assertNotIn("บัญชีม้า", text)
        data = embedded(text)
        self.assertEqual(data["run_id"], CFG["_RUN"]["run_id"])
        self.assertEqual(len(data["findings"]), len(sample_bundle()["findings"]))
        self.assertEqual(len(data["mule_networks"]), answer_key()["network_count"])

    def test_script_close_in_data_escaped(self):
        b = dict(sample_bundle())
        ev = b["evidence"].copy()
        ev.at[ev.index[0], "explanation"] = "x</script><script>alert(1)</script>"
        b["evidence"] = ev
        _, _, html = write_all(b, self.dir)
        text = Path(html).read_text(encoding="utf-8")
        data = embedded(text)
        self.assertEqual(data["evidence"][0]["explanation"], "x</script><script>alert(1)</script>")
        self.assertNotIn("alert(1)</script>", text)

    def test_truncated_template_rejected(self):
        t = template()
        with self.assertRaises(ValueError):
            R()["out_dashboard"](sample_bundle(), t[: len(t) // 2], str(Path(self.dir) / "x.html"), CFG)
        with self.assertRaises(ValueError):
            R()["out_dashboard"](sample_bundle(), t.replace("/*__AIDA_DATA__*/", ""),
                                 str(Path(self.dir) / "x.html"), CFG)

    def _browser(self, bundle):
        node = shutil.which("node")
        if not node or subprocess.run([node, "-e", "require('playwright')"], capture_output=True).returncode:
            self.skipTest("node + playwright not available")
        _, _, html = write_all(bundle, self.dir)
        shots = Path(os.environ.get("AIDA_SHOTS_DIR") or self.dir) / self._testMethodName
        out = subprocess.run([node, str(HERE / "dashboard_smoke.js"), html, str(shots)],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_dashboard_in_browser(self):
        """Open the dashboard in Chromium, click every tab, a node and a finding; no console
        errors and no network requests. Screenshots go to AIDA_SHOTS_DIR when set."""
        res = self._browser(sample_bundle())
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["requests"], [])
        self.assertEqual(res["tabs"], TABS)
        self.assertGreater(res["nodes"], 0)
        self.assertTrue(res["node_findings"])
        self.assertTrue(res["finding_evidence"])
        self.assertGreater(res["flow_columns"], 0)
        heads = dict((title, text) for text, title in res["finding_headers"])
        for col in ("finding_id", "entity_id", "risk", "exposure", "priority", "review_reason"):
            self.assertRegex(heads[col], "[ก-๙]", col)  # Thai label, schema name in title

    def test_dashboard_large_network_as_table(self):
        """A network above NET_DRAW_MAX members is shown as a members table, not a circle."""
        b = dict(sample_bundle())
        n = b["mule_networks"].copy()
        mem = ["N01"] + [f"A{i:05d}" for i in range(399)]  # N01 (first row) has its own R2 finding
        n.at[n.index[0], "member_accts"] = mem
        n.at[n.index[0], "roles"] = {a: "mule" for a in mem}
        b["mule_networks"] = n
        res = self._browser(b)
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["nodes"], 0)
        self.assertEqual(res["member_rows"], 50)  # first page of 400 members
        self.assertTrue(res["node_findings"])


# ---------------------------------------------------------------- end to end
class TestEndToEnd(OutputCase):
    def test_end_to_end_sample(self):
        wb, csvs, html = write_all(sample_bundle(), self.dir)
        key = answer_key()
        f = pd.read_excel(wb, sheet_name="Findings")
        self.assertEqual(len(f), key["unified_findings"])
        self.assertEqual(set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"])), tp.key_set())
        nets = pd.read_excel(wb, sheet_name="Mule_Networks")
        self.assertEqual(len(nets), key["network_count"])
        self.assertEqual((f["entity_type"] == "network").sum(), key["network_count"])
        nodes = pd.read_csv(csvs[0], dtype=str)
        self.assertEqual(nodes["network_id"].dropna().nunique(), key["network_count"])
        data = embedded(Path(html).read_text(encoding="utf-8"))
        self.assertEqual(len(data["findings"]), key["unified_findings"])
        self.assertEqual(len(data["mule_networks"]), key["network_count"])
        plan = pd.read_excel(wb, sheet_name="Analysis_Plan")
        self.assertEqual(len(plan), 15)
        log = pd.read_excel(wb, sheet_name="Run_Log")
        self.assertEqual(list(log.columns), tp.RUN_LOG_COLUMNS)


if __name__ == "__main__":
    unittest.main()
