"""Tests for the engine skeleton: constants, role adapter, registry loader and the B1 regression."""
import ast
import re
import sys
import unittest
from pathlib import Path

import pandas as pd

import test_pipeline as tp
from _engine import ENGINE_PATH, engine, recipes
from test_recipes import KNOWLEDGE, answer_key

ROLES = ["record_id", "date", "amount", "entity", "counterparty", "contract", "category", "channel",
         "created_by", "approved_by", "document_no", "limit", "due_date", "opened_at"]
FORBIDDEN = {"requests", "urllib", "urllib3", "http", "httpx", "socket", "ftplib", "smtplib",
             "aiohttp", "xmlrpc", "telnetlib", "websocket", "websockets"}


class EngineCore(unittest.TestCase):
    def test_version_constants(self):
        e = engine()
        self.assertEqual(e.__version__, "3.0.0")
        self.assertEqual(e.REGISTRY_VERSION, "1.2")

    def test_roles_exact_list(self):
        e = engine()
        self.assertEqual(list(e.ROLES), ROLES)
        self.assertEqual(e.ROLE_TO_INTERNAL["record_id"], "tx_id")
        self.assertEqual(e.ROLE_TO_INTERNAL["date"], "ts")
        self.assertEqual(e.ROLE_TO_INTERNAL["entity"], "from_acct")
        self.assertEqual(e.ROLE_TO_INTERNAL["counterparty"], "to_acct")
        self.assertEqual(e.ROLE_TO_INTERNAL["amount"], "amount")
        for r in ROLES:
            self.assertIn(r, e.ROLE_TO_INTERNAL)
        for r in ROLES[5:]:
            if r != "opened_at":
                self.assertEqual(e.ROLE_TO_INTERNAL[r], r)

    def test_to_internal_renames_and_keeps_custom(self):
        e = engine()
        tx = pd.DataFrame({"เลขที่": ["1", "2"], "วันที่": ["2026-01-01", "2026-01-02"],
                           "จำนวน": [10.0, 20.0], "ผู้โอน": ["a", "b"], "ผู้รับ": ["b", "a"],
                           "สาขา": ["x", "y"], "ลับ": [1, 2], "หมายเหตุ": ["p", "q"]})
        acc = pd.DataFrame({"รหัส": ["a", "b"], "เปิด": ["2020-01-01", "2021-01-01"], "อื่น": [1, 2]})
        out = e.to_internal({"t": tx, "m": acc}, {
            "t": {"เลขที่": "record_id", "วันที่": "date", "จำนวน": "amount", "ผู้โอน": "entity",
                  "ผู้รับ": "counterparty", "สาขา": "channel", "หมายเหตุ": "custom:note"},
            "m": {"รหัส": "entity", "เปิด": "opened_at"}})
        self.assertEqual(list(out["transactions"].columns),
                         ["tx_id", "ts", "amount", "from_acct", "to_acct", "channel", "custom:note"])
        self.assertEqual(list(out["accounts"].columns), ["acct_id", "opened_at"])
        self.assertEqual(out["transactions"]["custom:note"].tolist(), ["p", "q"])
        self.assertNotIn("ลับ", out["transactions"].columns)

    def test_to_internal_without_accounts(self):
        e = engine()
        tx = pd.DataFrame({"a": ["1"], "b": ["2026-01-01"], "c": [1.0]})
        out = e.to_internal({"t": tx}, {"t": {"a": "record_id", "b": "date", "c": "amount"}})
        self.assertEqual(set(out), {"transactions"})

    def test_to_internal_thai_errors(self):
        e = engine()
        tx = pd.DataFrame({"a": ["1"]})
        with self.assertRaises(ValueError) as cm:
            e.to_internal({"t": tx}, {"t": {"a": "ไม่มีบทบาทนี้"}})
        self.assertRegex(str(cm.exception), r"[ก-๙]")
        with self.assertRaises(ValueError):
            e.to_internal({"t": tx}, {"t": {"zzz": "record_id"}})
        with self.assertRaises(ValueError):
            e.to_internal({"t": tx}, {"t": {"a": "opened_at"}})  # no transactions table

    def test_load_registry(self):
        e = engine()
        reg = e.load_registry(KNOWLEDGE / "AIDA-14-configuration-registry.md")
        self.assertIn("REGISTRY.VERSION", reg)
        same = e.load_registry((KNOWLEDGE / "AIDA-14-configuration-registry.md").read_text(encoding="utf-8"))
        self.assertEqual(reg, same)
        with self.assertRaises(ValueError):
            e.load_registry("# ไม่มีหัวข้อ")

    def test_dashboard_template_lives_in_engine(self):
        # C1: the template is carried by the engine only; no Knowledge file holds a copy any more
        t = engine().DASHBOARD_TEMPLATE
        self.assertEqual(t.count(engine().DASH_PLACEHOLDER), 1)
        self.assertTrue(t.rstrip().endswith(engine().DASH_END))
        for f in KNOWLEDGE.glob("*.md"):
            self.assertNotRegex(f.read_text(encoding="utf-8"), r"(?m)^```html", f.name)

    def test_recipes_loader_exposes_cards(self):
        r = recipes()
        for name in ("clean_tx", "core_evidence", "out_dashboard", "stat_mad", "flow_layering"):
            self.assertIn(name, r)
        self.assertNotIn("to_internal_missing", r)

    def test_b1_answer_key_via_engine(self):
        key = answer_key()
        chain = tp.sample_chain()
        self.assertEqual(len(key["findings"]), 19)
        self.assertEqual(tp.finding_set(chain["assessed"]), tp.key_set())
        self.assertEqual(len(chain["assessed"]), 19)
        self.assertEqual(len(chain["networks"]), 1)

    def test_engine_no_network_imports(self):
        tree = ast.parse(ENGINE_PATH.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertFalse(names & FORBIDDEN, names)
        allowed = set(sys.stdlib_module_names) | {"pandas", "numpy", "openpyxl"}
        self.assertTrue(names <= allowed, names - allowed)


if __name__ == "__main__":
    unittest.main()
