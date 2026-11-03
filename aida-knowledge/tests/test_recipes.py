"""Tests for the analysis recipe cards (AIDA-18) and CORE-EVIDENCE (AIDA-19).

Cards are loaded with tools/extract_recipes.load_recipes exactly as Copilot's Code
Interpreter would run them, then run on the sample data. Each card must flag at
least the planted accounts in answer_key["recipes"][ID] and no normal ("A...")
account.
"""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

from extract_recipes import load_recipes  # noqa: E402
from validate_pack import parse_machine_config  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
SAMPLES = ROOT / "samples"
MACHINE_CONFIG, _ = parse_machine_config(KNOWLEDGE / "AIDA-14-configuration-registry.md")
CFG = {**MACHINE_CONFIG, "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}}
EVIDENCE_COLUMNS = [
    "evidence_id", "run_id", "recipe_id", "recipe_version", "skill_family", "entity_type",
    "entity_id", "risk", "period", "metric", "value", "threshold", "registry_key",
    "registry_version", "explanation", "record_refs", "data_ref",
]

_CACHE = {}


def recipes():
    if "r" not in _CACHE:
        _CACHE["r"] = load_recipes([KNOWLEDGE / "AIDA-19-pipeline-recipes.md",
                                    KNOWLEDGE / "AIDA-18-analysis-recipes.md"])
    return _CACHE["r"]


def helper(name):
    """Helpers defined by CORE-EVIDENCE live in the shared recipe namespace."""
    return recipes()["core_evidence"].__globals__[name]


def sample_tables():
    if "t" not in _CACHE:
        tx = pd.read_csv(SAMPLES / "transactions.csv", dtype={"tx_id": str})
        tx["ts"] = pd.to_datetime(tx["ts"])
        acc = pd.read_csv(SAMPLES / "accounts.csv")
        acc["opened_at"] = pd.to_datetime(acc["opened_at"])
        _CACHE["t"] = {"transactions": tx, "accounts": acc}
    return _CACHE["t"]


def answer_key():
    if "k" not in _CACHE:
        _CACHE["k"] = json.loads((SAMPLES / "answer_key.json").read_text(encoding="utf-8"))
    return _CACHE["k"]


def run_card(func_name, tables=None):
    t = dict(tables if tables is not None else sample_tables())
    t["_out"] = {}
    return recipes()[func_name](t, CFG)


class CardCase:
    """Mixin: one subclass per card sets RECIPE_ID and FUNC."""
    RECIPE_ID = ""
    FUNC = ""

    @classmethod
    def setUpClass(cls):
        cls.ev = run_card(cls.FUNC)
        cls.found = set(cls.ev["entity_id"])

    def test_planted_found(self):
        planted = set(answer_key()["recipes"][self.RECIPE_ID])
        self.assertLessEqual(planted, self.found)

    def test_no_normal_account(self):
        self.assertEqual([a for a in self.found if a.startswith("A")], [])

    def test_evidence_columns(self):
        self.assertEqual(list(self.ev.columns), EVIDENCE_COLUMNS)

    def test_evidence_values(self):
        ev = self.ev
        self.assertTrue((ev["recipe_id"] == self.RECIPE_ID).all())
        self.assertTrue((ev["risk"] == "R1").all())
        self.assertTrue((ev["entity_type"] == "account").all())
        self.assertTrue(ev["period"].str.match(r"^\d{4}-\d{2}$").all())
        self.assertTrue((ev["registry_version"] == CFG["REGISTRY.VERSION"]).all())
        self.assertTrue((ev["data_ref"] == CFG["_RUN"]["data_ref"]).all())
        self.assertTrue(ev["evidence_id"].is_unique)
        known = set(sample_tables()["transactions"]["tx_id"])
        for refs in ev["record_refs"]:
            self.assertIsInstance(refs, list)
            self.assertTrue(refs)
            self.assertLessEqual(set(refs), known)
            self.assertTrue(all(isinstance(r, str) for r in refs))
        for text in ev["explanation"]:
            self.assertIn("AIDA-14", text)
        # one row per entity per month
        self.assertFalse(ev.duplicated(["entity_id", "period"]).any())


class TestStatMad(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "STAT-MAD", "stat_mad"

    def test_refs_point_to_outlier(self):
        row = self.ev[self.ev["entity_id"] == "O01"].iloc[0]
        self.assertIn("TX-OUT-1", row["record_refs"])
        self.assertGreater(row["value"], CFG["STAT.MAD.THRESHOLD"])


class TestBehVelocity(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "BEH-VELOCITY", "beh_velocity"


class TestBehSpike(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "BEH-SPIKE", "beh_spike"

    def test_short_history_not_flagged(self):
        self.assertNotIn("O01", self.found)  # fewer than spike_months of history
        self.assertNotIn("P01", self.found)  # August total equals its baseline


class TestTempOffhours(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "TEMP-OFFHOURS", "temp_offhours"


class TestNetCycle(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "NET-CYCLE", "net_cycle"


class TestNetFunnel(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "NET-FUNNEL", "net_funnel"


def _tx(rows):
    return pd.DataFrame(rows, columns=["tx_id", "ts", "from_acct", "to_acct", "amount", "channel"])


class TestEdgeCases(unittest.TestCase):
    def test_no_outflow_account_no_signal(self):
        rows = [(f"X{i}", f"2026-08-0{1 + i % 5} 10:00", f"S{i:02d}", "Z01", 1000.0, "mobile")
                for i in range(15)]
        ev = run_card("net_funnel", {"transactions": _tx(rows)})
        self.assertTrue(ev.empty)
        self.assertEqual(list(ev.columns), EVIDENCE_COLUMNS)

    def test_self_and_nonpositive_excluded_in_cycle(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q1", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q1", "Q2", 0.0, "mobile"),
                ("X3", "2026-08-03 10:00", "Q2", "Q1", -10.0, "mobile")]
        self.assertTrue(run_card("net_cycle", {"transactions": _tx(rows)}).empty)

    def test_two_hop_cycle_found(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile")]
        ev = run_card("net_cycle", {"transactions": _tx(rows)})
        self.assertEqual(set(ev["entity_id"]), {"Q1", "Q2"})
        self.assertEqual(sorted(ev["record_refs"].iloc[0]), ["X1", "X2"])

    def test_cycle_out_of_time_order_not_found(self):
        rows = [("X1", "2026-08-05 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile")]
        # X2 -> X1 is time ordered (Q2->Q1->Q2), so a cycle exists starting from X2
        self.assertEqual(set(run_card("net_cycle", {"transactions": _tx(rows)})["entity_id"]),
                         {"Q1", "Q2"})
        rows[0] = ("X1", "2026-09-20 10:00", "Q1", "Q2", 500.0, "mobile")  # beyond NET.CYCLE days
        self.assertTrue(run_card("net_cycle", {"transactions": _tx(rows)}).empty)

    def test_constant_baseline_small_increase_not_flagged(self):
        # 7 days with 2 transfers each, then 3: a constant baseline must not flag +1
        rows, n = [], 0
        for d in range(1, 9):
            for _ in range(3 if d == 8 else 2):
                n += 1
                rows.append((f"X{n}", f"2026-08-{d:02d} 10:00", "Q1", f"R{n}", 100.0, "mobile"))
        self.assertTrue(run_card("beh_velocity", {"transactions": _tx(rows)}).empty)

    def test_offhours_without_channel_column(self):
        tx = _tx([("X1", "2026-08-01 23:00", "Q1", "Q2", 500.0, "mobile")]).drop(columns="channel")
        ev = run_card("temp_offhours", {"transactions": tx})
        self.assertEqual(list(ev["entity_id"]), ["Q1"])


class TestCoreEvidence(unittest.TestCase):
    def test_empty_found(self):
        out = helper("evidence_rows")("STAT-MAD", "1.0", "5.1 Statistical", "R1",
                                         "STAT.MAD.THRESHOLD", pd.DataFrame(), CFG)
        self.assertTrue(out.empty)
        self.assertEqual(list(out.columns), EVIDENCE_COLUMNS)

    def test_fields(self):
        found = pd.DataFrame([{"entity_id": "Q1", "period": "2026-08", "metric": "m", "value": 5.0,
                               "threshold": 3.5, "explanation": "x", "record_refs": [1, "T2"]},
                              {"entity_id": "N", "period": "2026-08", "metric": "m", "value": 1,
                               "threshold": 1, "explanation": "y", "record_refs": ["T3"],
                               "entity_type": "network"}])
        out = helper("evidence_rows")("NET-CYCLE", "1.0", "5.9 Network", "R1", "NET.CYCLE",
                                         found, CFG)
        self.assertEqual(list(out.columns), EVIDENCE_COLUMNS)
        self.assertEqual(list(out["evidence_id"]), ["NET-CYCLE-T-1", "NET-CYCLE-T-2"])
        self.assertEqual(list(out["entity_type"]), ["account", "network"])
        self.assertEqual(out["record_refs"].iloc[0], ["1", "T2"])
        self.assertEqual(out["registry_version"].iloc[0], CFG["REGISTRY.VERSION"])
        self.assertEqual(out["data_ref"].iloc[0], CFG["_RUN"]["data_ref"])
        self.assertEqual(out["recipe_version"].iloc[0], "1.0")

    def test_clean_tx(self):
        tx = _tx([("X1", "2026-08-02", "Q1", "Q1", 5.0, "m"), ("X2", "2026-08-01", "Q1", "Q2", 0, "m"),
                  ("X3", "2026-08-03", "Q1", "Q2", 7.0, "m"), ("X4", "2026-08-01", "Q2", "Q1", 1.0, "m")])
        out = helper("clean_tx")(tx)
        self.assertEqual(list(out["tx_id"]), ["X4", "X3"])
        self.assertEqual(list(out["period"]), ["2026-08", "2026-08"])


if __name__ == "__main__":
    unittest.main()
