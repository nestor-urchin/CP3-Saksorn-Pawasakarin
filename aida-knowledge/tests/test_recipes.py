"""Tests for the analysis recipe cards (AIDA-18) and CORE-EVIDENCE (AIDA-19).

Cards are loaded from the engine (tests/_engine.recipes) exactly as Copilot's Code
Interpreter would run them, then run on the sample data. Each card must flag at
least the planted accounts in answer_key["recipes"][ID] and no normal ("A...")
account.
"""
import json
import random
import sys
import time
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

import _engine  # noqa: E402
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
        _CACHE["r"] = _engine.recipes()
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


R1_FUNCS = ["stat_mad", "beh_velocity", "beh_spike", "temp_offhours", "net_cycle", "net_funnel",
            "mule_dwell", "mule_new_acct", "flow_layering"]


def sample_evidence(stage):
    """Evidence the MULE-* aggregators read, built in pipeline order on the sample data:
    "R1" = all R1 cards, "R2" = + MULE-PATTERN, "R3" = + MULE-CROSS-TX."""
    key = ("ev", stage)
    if key not in _CACHE:
        if stage == "R1":
            ev = pd.concat([run_card(f) for f in R1_FUNCS], ignore_index=True)
        else:
            prev, func = {"R2": ("R1", "mule_pattern"), "R3": ("R2", "mule_cross_tx")}[stage]
            ev = sample_evidence(prev)
            ev = pd.concat([ev, run_card(func, {**sample_tables(), "evidence": ev})],
                           ignore_index=True)
        _CACHE[key] = ev
    return _CACHE[key]


def run_card(func_name, tables=None, cfg=None):
    t = dict(tables if tables is not None else sample_tables())
    t["_out"] = {}
    return recipes()[func_name](t, cfg if cfg is not None else CFG)


class CardCase:
    """Mixin: one subclass per card sets RECIPE_ID and FUNC (and RISK / ENTITY_TYPE / STAGE
    when they differ from an R1 account card that needs no earlier evidence)."""
    RECIPE_ID = ""
    FUNC = ""
    RISK = "R1"
    ENTITY_TYPE = "account"
    STAGE = None  # evidence stage the card reads (see sample_evidence)

    @classmethod
    def setUpClass(cls):
        tables = sample_tables()
        if cls.STAGE:
            tables = {**tables, "evidence": sample_evidence(cls.STAGE)}
        cls.ev = run_card(cls.FUNC, tables)
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
        self.assertTrue((ev["risk"] == self.RISK).all())
        self.assertTrue((ev["entity_type"] == self.ENTITY_TYPE).all())
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

    def test_cycle_time_ordered_from_later_listed_edge_found(self):
        rows = [("X1", "2026-08-05 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile")]
        # X2 then X1 is time ordered (Q2->Q1->Q2), so a cycle exists starting from X2
        self.assertEqual(set(run_card("net_cycle", {"transactions": _tx(rows)})["entity_id"]),
                         {"Q1", "Q2"})

    def test_cycle_beyond_window_not_found(self):
        rows = [("X1", "2026-09-20 10:00", "Q1", "Q2", 500.0, "mobile"),  # beyond NET.CYCLE days
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile")]
        self.assertTrue(run_card("net_cycle", {"transactions": _tx(rows)}).empty)

    def test_cycle_out_of_time_order_not_found(self):
        rows = [("X1", "2026-08-05 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q3", 400.0, "mobile"),
                ("X3", "2026-08-06 10:00", "Q3", "Q1", 300.0, "mobile")]
        self.assertTrue(run_card("net_cycle", {"transactions": _tx(rows)}).empty)

    def test_undated_transfer_does_not_close_cycle(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", None, "Q2", "Q1", 400.0, "mobile")]
        self.assertTrue(run_card("net_cycle", {"transactions": _tx(rows)}).empty)

    def test_cycle_refs_describe_reported_cycle_only(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile"),
                ("X3", "2026-08-03 10:00", "Q1", "Q3", 500.0, "mobile"),
                ("X4", "2026-08-04 10:00", "Q3", "Q4", 400.0, "mobile"),
                ("X5", "2026-08-05 10:00", "Q4", "Q1", 300.0, "mobile")]
        ev = run_card("net_cycle", {"transactions": _tx(rows)}).set_index("entity_id")
        cycles = {("Q1", "Q2"): {"X1", "X2"}, ("Q1", "Q3", "Q4"): {"X3", "X4", "X5"}}
        q1 = ev.loc["Q1"]
        named = [c for c in cycles if " → ".join(c + (c[0],)) in q1["explanation"]]
        self.assertEqual(len(named), 1)
        self.assertEqual(set(q1["record_refs"]), cycles[named[0]])
        self.assertEqual(q1["value"], len(named[0]))
        self.assertEqual(set(ev.loc["Q3", "record_refs"]), {"X3", "X4", "X5"})
        self.assertEqual(set(ev.loc["Q2", "record_refs"]), {"X1", "X2"})

    def test_parallel_edges_one_cycle(self):
        rows = [(f"X{i}", f"2026-08-01 1{i % 10}:00", "Q1", "Q2", 100.0, "m") for i in range(10)]
        rows += [(f"Y{i}", f"2026-08-02 1{i % 10}:00", "Q2", "Q1", 100.0, "m") for i in range(10)]
        ev = run_card("net_cycle", {"transactions": _tx(rows)})
        self.assertEqual(sorted(ev["entity_id"]), ["Q1", "Q2"])
        for refs in ev["record_refs"]:
            self.assertEqual(len(refs), 2)

    def test_cycle_dense_data_is_fast(self):
        rng = random.Random(7)
        accts = [f"Q{i}" for i in range(10)]
        rows = []
        for i in range(300):
            a, b = rng.sample(accts, 2)
            rows.append((f"X{i}", f"2026-08-{rng.randint(1, 28):02d} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}",
                         a, b, 100.0, "m"))
        start = time.perf_counter()
        ev = run_card("net_cycle", {"transactions": _tx(rows)})
        self.assertLess(time.perf_counter() - start, 5)
        self.assertFalse(ev.empty)

    def test_cycle_search_cap_reported(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 500.0, "mobile"),
                ("X2", "2026-08-02 10:00", "Q2", "Q1", 400.0, "mobile"),
                ("X3", "2026-08-03 10:00", "Q1", "Q3", 400.0, "mobile"),
                ("X4", "2026-07-01 10:00", "Q3", "Q1", 400.0, "mobile")]  # Q1->Q3->Q1 not time ordered
        ev = run_card("net_cycle", {"transactions": _tx(rows)}, {**CFG, "NET.CYCLE.MAX_PATHS": 2})
        self.assertEqual(sorted(ev["entity_id"]), ["Q1", "Q2"])  # found before the cap
        for text in ev["explanation"]:
            self.assertIn("NET.CYCLE.MAX_PATHS", text)
        ev = run_card("net_cycle", {"transactions": _tx(rows)})
        for text in ev["explanation"]:
            self.assertNotIn("NET.CYCLE.MAX_PATHS", text)

    # ---- baselines (I-1): BEH-VELOCITY has the registered Poisson SD floor, BEH-SPIKE has none
    @staticmethod
    def _daily(counts):
        rows, n = [], 0
        for d, c in enumerate(counts, 1):
            for _ in range(c):
                n += 1
                rows.append((f"X{n}", f"2026-08-{d:02d} 10:00", "Q1", f"R{n}", 100.0, "m"))
        return {"transactions": _tx(rows)}

    @staticmethod
    def _monthly(totals):
        rows = [(f"X{i}", f"2026-{i + 1:02d}-10 10:00", "Q1", f"R{i}", float(a), "m")
                for i, a in enumerate(totals)]
        return {"transactions": _tx(rows)}

    def test_velocity_poisson_floor_registered(self):
        self.assertEqual(CFG["BEH.VELOCITY.SD_FLOOR"], "poisson")
        # constant 2/day: threshold = 2 + 3 * max(0, sqrt 2) = 6.24
        self.assertTrue(run_card("beh_velocity", self._daily([2] * 7 + [6])).empty)
        ev = run_card("beh_velocity", self._daily([2] * 7 + [7]))
        self.assertEqual(list(ev["value"]), [7])
        self.assertAlmostEqual(ev["threshold"].iloc[0], 6.24, places=2)
        self.assertIn("ค่าเฉลี่ย 2.00 + 3 × max(SD 0.00, √ค่าเฉลี่ย 1.41) = 6.24",
                      ev["explanation"].iloc[0])

    def test_velocity_floor_disabled_by_config(self):
        cfg = {**CFG, "BEH.VELOCITY.SD_FLOOR": "none"}
        ev = run_card("beh_velocity", self._daily([2] * 7 + [3]), cfg)
        self.assertEqual(list(ev["value"]), [3])
        self.assertIn("ค่าเฉลี่ย 2.00 + 3 × SD 0.00 = 2.00", ev["explanation"].iloc[0])

    def test_velocity_std_breach_flagged(self):
        # baseline 2,6,2,6,2,6: mean 4, SD 2.19 > sqrt(4) -> threshold 10.57
        self.assertTrue(run_card("beh_velocity", self._daily([2, 6] * 3 + [10])).empty)
        ev = run_card("beh_velocity", self._daily([2, 6] * 3 + [11]))
        self.assertEqual(list(ev["value"]), [11])
        self.assertIn("ค่าเฉลี่ย 4.00 + 3 × max(SD 2.19, √ค่าเฉลี่ย 2.00) = 10.57",
                      ev["explanation"].iloc[0])

    def test_spike_std_breach_flagged(self):
        # baseline 1000,3000 x3: mean 2000, SD 1095.45 -> threshold 5286.34
        self.assertTrue(run_card("beh_spike", self._monthly([1000, 3000] * 3 + [5200])).empty)
        ev = run_card("beh_spike", self._monthly([1000, 3000] * 3 + [5400]))
        self.assertEqual(list(ev["period"]), ["2026-07"])
        self.assertIn("ค่าเฉลี่ย 2,000.00 + 3 × SD 1,095.45 = 5,286.34", ev["explanation"].iloc[0])

    def test_spike_has_no_floor(self):
        ev = run_card("beh_spike", self._monthly([1000] * 6 + [1001]))
        self.assertEqual(list(ev["value"]), [1001])
        self.assertIn("ค่าเฉลี่ย 1,000.00 + 3 × SD 0.00 = 1,000.00", ev["explanation"].iloc[0])

    def test_offhours_without_channel_column(self):
        tx = _tx([(f"X{d}", f"2026-08-0{d} 23:00", "Q1", "Q2", 500.0, "mobile")
                  for d in range(1, 1 + CFG["TEMP.OFF_HOURS.MIN_TX"])]).drop(columns="channel")
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
                  ("X3", "2026-08-03", "Q1", "Q2", 7.0, "m"), ("X4", "2026-08-01", "Q2", "Q1", 1.0, "m"),
                  ("X5", None, "Q1", "Q2", 9.0, "m")])
        out = helper("clean_tx")(tx)
        self.assertEqual(list(out["tx_id"]), ["X4", "X3"])
        self.assertEqual(list(out["period"]), ["2026-08", "2026-08"])


if __name__ == "__main__":
    unittest.main()
