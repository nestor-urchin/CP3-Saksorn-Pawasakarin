"""Tests for the fixes from the final whole-branch review of phase B1.

Each class covers one review item; cards are loaded exactly as Copilot runs them
(test_recipes.recipes). Items: 1 NET-CYCLE search budget per month + notes outside the
evidence rows, 2 TEMP-OFFHOURS minimum count / share, 3 unreadable opened_at, 4 no ts
column, 5 performance, 6 pack_version, 7 MULE-CROSS-TX per month, 8 accounts not assessed
under basis=first_seen, 10 unreadable amounts.
"""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

import test_outputs as to
import test_pipeline as tp
import test_recipes as tr
from test_recipes import CFG, EVIDENCE_COLUMNS

R = tr.recipes


def _tx(rows):
    return pd.DataFrame(rows, columns=["tx_id", "ts", "from_acct", "to_acct", "amount"])


def dense_acyclic_with_may_cycle(n=20000, seed=1):
    """The reviewer's probe: n transfers lo -> hi among 500 accounts over 150 days (no cycle)
    plus one 3-hop cycle X1 -> X2 -> X3 -> X1 planted on 2026-05-20..22."""
    rng = np.random.default_rng(seed)
    a, b = rng.integers(0, 500, n), rng.integers(0, 500, n)
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    keep = lo != hi
    ts = pd.Timestamp("2026-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 150 * 86400, keep.sum())), "s")
    tx = pd.DataFrame({"tx_id": [f"T{i}" for i in range(keep.sum())], "ts": ts,
                       "from_acct": [f"A{x:03d}" for x in lo[keep]],
                       "to_acct": [f"A{x:03d}" for x in hi[keep]], "amount": 1000.0})
    cyc = _tx([("C1", "2026-05-20 10:00", "X1", "X2", 5000.0), ("C2", "2026-05-21 10:00", "X2", "X3", 5000.0),
               ("C3", "2026-05-22 10:00", "X3", "X1", 5000.0)])
    cyc["ts"] = pd.to_datetime(cyc["ts"])
    return pd.concat([tx, cyc]).sort_values("ts").reset_index(drop=True)


def capped_without_cycle():
    """Two start edges in January, no time-ordered cycle anywhere: with a budget of 1 path
    per month January is cut short and no row is found."""
    return _tx([("E1", "2026-01-01 10:00", "A", "B", 100.0), ("E2", "2026-01-02 10:00", "A", "C", 100.0),
                ("E3", "2026-02-15 10:00", "B", "A", 100.0), ("E4", "2026-03-10 10:00", "C", "A", 100.0)])


class TestNetCycleBudget(unittest.TestCase):
    def test_planted_may_cycle_found_under_dense_traffic(self):
        tables = {"transactions": dense_acyclic_with_may_cycle(), "_out": {}}
        ev = R()["net_cycle"](tables, CFG)
        self.assertEqual(set(ev["entity_id"]), {"X1", "X2", "X3"})
        self.assertEqual(set(ev["period"]), {"2026-05"})
        self.assertEqual(tables["_out"].get("notes", []), [])  # nothing cut short

    def test_capped_month_with_no_rows_is_reported(self):
        tables = {"transactions": capped_without_cycle(), "_out": {}}
        ev = R()["net_cycle"](tables, {**CFG, "NET.CYCLE.MAX_PATHS": 1})
        self.assertTrue(ev.empty)
        self.assertEqual(list(ev.columns), EVIDENCE_COLUMNS)
        notes = tables["_out"]["notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["recipe_id"], "NET-CYCLE")
        self.assertIn("2026-01", notes[0]["detail"])
        self.assertIn("NET.CYCLE.MAX_PATHS", notes[0]["detail"])
        self.assertIn("อาจไม่ครบ", notes[0]["detail"])

    def test_budget_is_per_month(self):
        """January hits the cap; the March cycle still has its own budget and is found."""
        rows = [("E1", "2026-01-01 10:00", "A", "B", 100.0), ("E2", "2026-01-02 10:00", "A", "C", 100.0),
                ("E3", "2026-01-03 10:00", "A", "D", 100.0), ("M1", "2026-03-20 10:00", "P", "Q", 100.0),
                ("M2", "2026-03-21 10:00", "Q", "P", 100.0), ("E4", "2026-04-10 10:00", "B", "A", 100.0),
                ("E5", "2026-05-11 10:00", "C", "A", 100.0), ("E6", "2026-06-12 10:00", "D", "A", 100.0)]
        tables = {"transactions": _tx(rows), "_out": {}}
        ev = R()["net_cycle"](tables, {**CFG, "NET.CYCLE.MAX_PATHS": 2})
        self.assertEqual(set(ev["entity_id"]), {"P", "Q"})
        self.assertEqual(len(tables["_out"]["notes"]), 1)
        self.assertIn("2026-01", tables["_out"]["notes"][0]["detail"])

    def test_note_reaches_run_log_readme_and_dashboard(self):
        c = dict(tp.sample_chain())
        tables = dict(c["tables"])
        tables["_out"] = {**tables["_out"], "notes": [
            {"recipe_id": "NET-CYCLE", "recipe_version": "1.1", "detail": "เดือน 2026-01: ทดสอบหมายเหตุ อาจไม่ครบ"}]}
        c["tables"] = tables
        b = to.build_bundle(chain=c)
        log = b["run_log"]
        rev = log[(log["status"] == "REVIEW") & (log["recipe_id"] == "NET-CYCLE")]
        self.assertEqual(len(rev), 1)
        self.assertIn("ทดสอบหมายเหตุ", rev["detail"].iloc[0])
        self.assertEqual(rev["recipe_version"].iloc[0], "1.1")
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        wb, _, html = to.write_all(b, d)
        readme = " ".join(str(c.value) for row in openpyxl.load_workbook(wb)["README"].iter_rows()
                          for c in row if c.value is not None)
        self.assertIn("ทดสอบหมายเหตุ", readme)
        data = to.embedded(Path(html).read_text(encoding="utf-8"))
        self.assertTrue(any("ทดสอบหมายเหตุ" in n for n in data["card_notes"]))
        self.assertIn("D.card_notes", to.template())

    def test_no_note_no_review_row(self):
        b = to.sample_bundle()
        self.assertEqual(b["card_notes"], [])
        self.assertFalse(((b["run_log"]["status"] == "REVIEW") & (b["run_log"]["recipe_id"] == "NET-CYCLE")).any())


if __name__ == "__main__":
    unittest.main()
