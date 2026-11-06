"""Tests for the mule, counterparty and money flow recipe cards (AIDA-18, part 2).

Uses the helpers of test_recipes (cards loaded from the engine via tests/_engine as Copilot's
Code Interpreter would run them). The module is imported as `tr` so its test classes
are not collected a second time here.
"""
import random
import time
import unittest

import numpy as np
import pandas as pd

import test_recipes as tr
from test_recipes import CFG, EVIDENCE_COLUMNS, CardCase, answer_key, run_card, sample_tables

MULE_NETWORK_COLUMNS = ["network_id", "member_accts", "roles", "internal_tx_count",
                        "internal_amount", "period_start", "period_end"]
TRAIL_COLUMNS = ["trace_id", "start_acct", "direction", "hop", "from_acct", "to_acct", "amount",
                 "ts", "tx_id"]


def _tx(rows):
    return pd.DataFrame(rows, columns=["tx_id", "ts", "from_acct", "to_acct", "amount", "channel"])


def _r2(accts, period="2026-08"):
    """Hand-built R2 evidence (MULE-PATTERN rows) marking `accts` as mule-pattern accounts."""
    found = pd.DataFrame([{"entity_id": a, "period": period, "metric": "mule_signal_count",
                           "value": 3, "threshold": 3, "explanation": "x", "record_refs": ["X0"]}
                          for a in accts])
    return tr.helper("evidence_rows")("MULE-PATTERN", "1.0", "5.10 Hybrid", "R2",
                                      "MULE.MIN_SIGNALS", found, CFG)


def _run_with_out(func, tables, cfg=CFG):
    t = dict(tables)
    ev = tr.recipes()[func](t, cfg)
    return ev, t.get("_out", {})


# ---------------------------------------------------------------- answer-key tests per card
class TestMuleDwell(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "MULE-DWELL", "mule_dwell"

    def test_long_dwell_not_flagged(self):
        self.assertNotIn("F01", self.found)  # forwards > 24 h after the last inflow


class TestMuleNewAcct(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "MULE-NEW-ACCT", "mule_new_acct"

    def test_opened_at_basis(self):
        row = self.ev[self.ev["entity_id"] == "M01"].iloc[0]
        self.assertIn("basis=opened_at", row["explanation"])
        self.assertEqual(row["period"], "2026-08")


class TestCptyProfile(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC, RISK = "CPTY-PROFILE", "cpty_profile", "R4"

    def test_value_is_new_ratio(self):
        row = self.ev[self.ev["entity_id"] == "P01"].iloc[0]
        self.assertEqual(row["period"], "2026-08")
        self.assertEqual(row["value"], 1.0)
        self.assertEqual(row["record_refs"], ["TX-NEWCP-1"])


class TestCptyNewLarge(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC, RISK = "CPTY-NEW-LARGE", "cpty_new_large", "R4"

    def test_refs_point_to_new_counterparty(self):
        row = self.ev[self.ev["entity_id"] == "P01"].iloc[0]
        self.assertEqual(row["record_refs"], ["TX-NEWCP-1"])
        self.assertGreaterEqual(row["value"], CFG["CPTY.NEW_LARGE.MULTIPLIER"])

    def test_known_counterparty_not_flagged(self):
        self.assertNotIn("O01", self.found)  # TX-OUT-1 is large but OR1 is a regular counterparty


class TestFlowLayering(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC = "FLOW-LAYERING", "flow_layering"

    def test_low_pass_cycle_not_flagged(self):
        self.assertFalse({"C01", "C02", "C03"} & self.found)  # 70 % per hop


class TestMulePattern(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC, RISK, STAGE = "MULE-PATTERN", "mule_pattern", "R2", "R1"

    def test_signals_listed(self):
        row = self.ev[self.ev["entity_id"] == "M01"].iloc[0]
        self.assertEqual(row["value"], 4)
        for sig in ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY"]:
            self.assertIn(sig, row["explanation"])
        self.assertNotIn("TEMP-OFFHOURS", row["explanation"])
        self.assertEqual(set(self.ev.loc[self.ev["entity_id"] == "N01", "value"]), {3})

    def test_mule_pattern_wording(self):
        for text in self.ev["explanation"]:
            self.assertNotIn("บัญชีม้า", text)
            self.assertIn("สอดคล้องกับ Mule Account pattern", text)

    def test_matches_mule_accounts(self):
        self.assertEqual(self.found, set(answer_key()["mule_accounts"]))

    def test_no_evidence_no_rows(self):
        for tables in ({"transactions": sample_tables()["transactions"]},
                       {"transactions": sample_tables()["transactions"],
                        "evidence": pd.DataFrame(columns=EVIDENCE_COLUMNS)}):
            ev = run_card("mule_pattern", tables)
            self.assertTrue(ev.empty)
            self.assertEqual(list(ev.columns), EVIDENCE_COLUMNS)


class TestMuleCrossTx(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC, RISK, STAGE = "MULE-CROSS-TX", "mule_cross_tx", "R3", "R2"

    def test_roles(self):
        roles = dict(zip(self.ev["entity_id"], self.ev["value"]))
        self.assertEqual(roles, {"NF1": "feeder", "NC1": "collector"})
        self.assertTrue((self.ev["metric"] == "role").all())


class TestMuleNetwork(CardCase, unittest.TestCase):
    RECIPE_ID, FUNC, RISK, ENTITY_TYPE, STAGE = "MULE-NETWORK", "mule_network", "R3", "network", "R3"

    def test_mule_network_roles(self):
        ev, out = _run_with_out("mule_network", {**sample_tables(), "evidence": sample_evidence_r3()})
        nets = out["mule_networks"]
        self.assertEqual(list(nets.columns), MULE_NETWORK_COLUMNS)
        self.assertEqual(len(nets), 1)
        key = answer_key()["networks"][0]
        row = nets.iloc[0]
        self.assertEqual(row["network_id"], key["network_id"])
        self.assertEqual(sorted(row["member_accts"]), sorted(key["members"]))
        self.assertEqual(row["roles"], key["roles"])
        self.assertEqual(row["internal_tx_count"], 8)  # NF1 -> N01..N04, N01..N04 -> NC1
        self.assertEqual(list(ev["entity_id"]), ["NET-1"])
        self.assertEqual(ev["value"].iloc[0], 6)
        self.assertEqual(len(ev["record_refs"].iloc[0]), 8)
        for text in ev["explanation"]:
            self.assertIn("สอดคล้องกับ Mule Account pattern", text)

    def test_out_created_when_absent(self):
        t = {**sample_tables(), "evidence": sample_evidence_r3()}
        t.pop("_out", None)
        tr.recipes()["mule_network"](t, CFG)
        self.assertIn("mule_networks", t["_out"])


def sample_evidence_r3():
    return tr.sample_evidence("R3")


# ---------------------------------------------------------------- hand-built cases
class TestMuleEdgeCases(unittest.TestCase):
    def test_mule_new_acct_first_seen_basis(self):
        ev = run_card("mule_new_acct", {"transactions": sample_tables()["transactions"]})
        found = set(ev["entity_id"])
        self.assertLessEqual(set(answer_key()["recipes"]["MULE-NEW-ACCT"]), found)
        self.assertEqual([a for a in found if a.startswith("A")], [])
        row = ev[ev["entity_id"] == "M01"].iloc[0]
        self.assertIn("basis=first_seen", row["explanation"])

    def test_first_seen_at_data_start_not_assessed(self):
        # Q1 is active from the first day of the file: it may have existed before, so it is not new.
        rows = [(f"X{i}", f"2026-08-{1 + i % 20:02d} 10:00", "Q1", f"R{i}", 100.0, "m") for i in range(25)]
        self.assertTrue(run_card("mule_new_acct", {"transactions": _tx(rows)}).empty)
        rows = [("X0", "2026-01-02 10:00", "Q0", "R0", 100.0, "m")] + rows
        ev = run_card("mule_new_acct", {"transactions": _tx(rows)})
        self.assertEqual(list(ev["entity_id"]), ["Q1"])

    def test_dwell_no_outflow_no_signal(self):
        rows = [(f"X{i}", f"2026-08-0{1 + i % 5} 10:00", f"S{i:02d}", "Z01", 1000.0, "m") for i in range(15)]
        ev = run_card("mule_dwell", {"transactions": _tx(rows)})
        self.assertTrue(ev.empty)
        self.assertEqual(list(ev.columns), EVIDENCE_COLUMNS)

    def test_dwell_one_outflow_pairs_once(self):
        # 3 inflows followed by a single outflow = 1 pair, not 3
        rows = [(f"I{i}", f"2026-08-03 {8 + i:02d}:00", f"S{i}", "Z01", 100.0, "m") for i in range(3)]
        rows += [("O1", "2026-08-03 12:00", "Z01", "Y1", 290.0, "m")]
        self.assertTrue(run_card("mule_dwell", {"transactions": _tx(rows)}).empty)
        rows += [(f"I{i}", f"2026-08-0{1 + i} 08:00", f"S{i}", "Z01", 100.0, "m") for i in range(3, 5)]
        rows += [(f"O{i}", f"2026-08-0{1 + i} 09:00", "Z01", "Y1", 100.0, "m") for i in range(3, 5)]
        ev = run_card("mule_dwell", {"transactions": _tx(rows)})
        self.assertEqual(list(ev["value"]), [3])

    def test_cpty_profile_needs_history(self):
        rows = [(f"X{m}", f"2026-{m:02d}-10 10:00", "Q1", "R1", 100.0, "m") for m in range(1, 6)]
        rows += [("XN", "2026-06-10 10:00", "Q1", "RN", 100.0, "m")]  # 5 prior months < spike_months
        self.assertTrue(run_card("cpty_profile", {"transactions": _tx(rows)}).empty)
        rows = [("X0", "2025-12-10 10:00", "Q1", "R1", 100.0, "m")] + rows
        self.assertEqual(list(run_card("cpty_profile", {"transactions": _tx(rows)})["entity_id"]), ["Q1"])

    def test_mule_to_mule_role_and_network(self):
        rows = [("X1", "2026-08-03 10:00", "Q1", "Q2", 500.0, "m"),
                ("X2", "2026-08-04 10:00", "Q1", "Q9", 400.0, "m"),
                ("X3", "2026-08-05 10:00", "Q2", "Q9", 400.0, "m"),
                ("X4", "2026-08-05 11:00", "Q3", "Q9", 400.0, "m")]  # Q3 is not a mule
        tables = {"transactions": _tx(rows), "evidence": _r2(["Q1", "Q2"])}
        cross = run_card("mule_cross_tx", tables)
        roles = sorted(zip(cross["entity_id"], cross["value"]))
        self.assertEqual(roles, [("Q1", "mule_to_mule"), ("Q2", "mule_to_mule"), ("Q9", "collector")])
        self.assertEqual(set(cross["entity_type"]), {"account"})
        self.assertEqual(set(cross["risk"]), {"R3"})
        m2m = cross[cross["value"] == "mule_to_mule"]
        self.assertTrue(all(r == ["X1"] for r in m2m["record_refs"]))
        self.assertEqual(sorted(cross.loc[cross["entity_id"] == "Q9", "record_refs"].iloc[0]), ["X2", "X3"])
        ev, out = _run_with_out("mule_network", {**tables, "evidence": pd.concat([tables["evidence"], cross])})
        net = out["mule_networks"].iloc[0]
        self.assertEqual(net["roles"], {"Q1": "mule", "Q2": "mule", "Q9": "collector"})
        self.assertEqual(net["internal_tx_count"], 3)  # X4 comes from outside the network
        self.assertEqual(net["internal_amount"], 1300.0)
        self.assertEqual(list(ev["entity_type"]), ["network"])

    def test_network_ids_ordered_by_size(self):
        rows = [("X1", "2026-08-03 10:00", "Q1", "Q9", 1.0, "m"), ("X2", "2026-08-03 11:00", "Q2", "Q9", 1.0, "m"),
                ("Y1", "2026-08-03 10:00", "P1", "P9", 1.0, "m"), ("Y2", "2026-08-03 11:00", "P2", "P9", 1.0, "m"),
                ("Y3", "2026-08-03 12:00", "P3", "P9", 1.0, "m")]
        tables = {"transactions": _tx(rows), "evidence": _r2(["Q1", "Q2", "P1", "P2", "P3"])}
        cross = run_card("mule_cross_tx", tables)
        ev, out = _run_with_out("mule_network", {**tables, "evidence": pd.concat([tables["evidence"], cross])})
        self.assertEqual(list(ev["entity_id"]), ["NET-1", "NET-2"])
        nets = out["mule_networks"].set_index("network_id")
        self.assertEqual(sorted(nets.loc["NET-1", "member_accts"]), ["P1", "P2", "P3", "P9"])
        self.assertEqual(sorted(nets.loc["NET-2", "member_accts"]), ["Q1", "Q2", "Q9"])
        small = {**CFG, "MULE.NETWORK.MIN_SIZE": 4}
        ev, out = _run_with_out("mule_network", {**tables, "evidence": pd.concat([tables["evidence"], cross])}, small)
        self.assertEqual(list(ev["entity_id"]), ["NET-1"])

    def test_no_mules_no_network(self):
        ev, out = _run_with_out("mule_network", {"transactions": sample_tables()["transactions"],
                                                 "evidence": pd.DataFrame(columns=EVIDENCE_COLUMNS)})
        self.assertTrue(ev.empty)
        self.assertEqual(list(ev.columns), EVIDENCE_COLUMNS)
        self.assertEqual(list(out["mule_networks"].columns), MULE_NETWORK_COLUMNS)
        self.assertTrue(run_card("mule_cross_tx", {"transactions": sample_tables()["transactions"]}).empty)

    def test_no_accusatory_wording(self):
        evs = [tr.sample_evidence("R3"),
               run_card("mule_network", {**sample_tables(), "evidence": tr.sample_evidence("R3")})]
        for text in pd.concat(evs)["explanation"]:
            self.assertNotIn("บัญชีม้า", text)

    # ---- layering
    def test_layering_needs_three_hops(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 1000.0, "m"),
                ("X2", "2026-08-01 12:00", "Q2", "Q3", 950.0, "m")]
        self.assertTrue(run_card("flow_layering", {"transactions": _tx(rows)}).empty)
        rows += [("X3", "2026-08-02 12:00", "Q3", "Q4", 900.0, "m")]
        ev = run_card("flow_layering", {"transactions": _tx(rows)})
        self.assertEqual(sorted(ev["entity_id"]), ["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(sorted(ev["record_refs"].iloc[0]), ["X1", "X2", "X3"])

    def test_layering_low_pass_or_late_hop_not_flagged(self):
        low = [("X1", "2026-08-01 10:00", "Q1", "Q2", 1000.0, "m"),
               ("X2", "2026-08-01 12:00", "Q2", "Q3", 950.0, "m"),
               ("X3", "2026-08-02 12:00", "Q3", "Q4", 800.0, "m")]  # 84 % < FLOW.MIN_PASS_RATIO
        self.assertTrue(run_card("flow_layering", {"transactions": _tx(low)}).empty)
        late = low[:2] + [("X3", "2026-08-09 12:00", "Q3", "Q4", 900.0, "m")]  # beyond FLOW.WINDOW_DAYS
        self.assertTrue(run_card("flow_layering", {"transactions": _tx(late)}).empty)
        back = low[:2] + [("X3", "2026-07-30 12:00", "Q3", "Q4", 900.0, "m")]  # before the hop it follows
        self.assertTrue(run_card("flow_layering", {"transactions": _tx(back)}).empty)

    def test_layering_dense_data_is_fast(self):
        start = time.perf_counter()
        ev = run_card("flow_layering", {"transactions": _dense()})
        self.assertLess(time.perf_counter() - start, 5)
        self.assertFalse(ev.empty)

    # ---- money flow trace
    def test_flow_trace_columns(self):
        trail = tr.recipes()["flow_trace"](sample_tables(), CFG, "L01", "forward")
        self.assertEqual(list(trail.columns), TRAIL_COLUMNS)
        self.assertTrue((trail["start_acct"] == "L01").all())
        self.assertTrue((trail["direction"] == "forward").all())

    def test_flow_trace_max_hops(self):
        trail = tr.recipes()["flow_trace"](sample_tables(), CFG, "L01", "forward")
        self.assertLessEqual(trail["hop"].max(), CFG["FLOW.MAX_HOPS"])
        chain = list(zip(trail["hop"], trail["from_acct"], trail["to_acct"]))
        self.assertEqual(chain, [(1, "L01", "L02"), (2, "L02", "L03"), (3, "L03", "L04"), (4, "L04", "L05")])
        short = tr.recipes()["flow_trace"](sample_tables(), {**CFG, "FLOW.MAX_HOPS": 2}, "L01", "forward")
        self.assertEqual(short["hop"].max(), 2)

    def test_flow_trace_backward(self):
        trail = tr.recipes()["flow_trace"](sample_tables(), CFG, "L05", "backward")
        chain = list(zip(trail["hop"], trail["from_acct"], trail["to_acct"]))
        self.assertEqual(chain, [(1, "L04", "L05"), (2, "L03", "L04"), (3, "L02", "L03"), (4, "L01", "L02")])

    def test_flow_trace_respects_time_order(self):
        rows = [("X1", "2026-08-02 10:00", "Q1", "Q2", 1000.0, "m"),
                ("X2", "2026-08-01 10:00", "Q2", "Q3", 900.0, "m"),   # before X1: not part of the flow
                ("X3", "2026-08-03 10:00", "Q2", "Q4", 900.0, "m"),
                ("X4", "2026-08-15 10:00", "Q4", "Q5", 800.0, "m"),   # beyond FLOW.WINDOW_DAYS of X1
                ("X5", "2026-08-04 10:00", "Q4", "Q6", 800.0, "m"),
                ("X6", "2026-08-02 09:00", "Q4", "Q7", 800.0, "m")]   # before X3: not part of the flow
        trail = tr.recipes()["flow_trace"]({"transactions": _tx(rows)}, CFG, "Q1", "forward")
        self.assertEqual(list(trail["tx_id"]), ["X1", "X3", "X5"])
        ts = pd.to_datetime(trail["ts"])
        self.assertTrue(ts.is_monotonic_increasing)
        self.assertLessEqual(ts.max() - ts.min(), pd.Timedelta(days=CFG["FLOW.WINDOW_DAYS"]))
        back = tr.recipes()["flow_trace"]({"transactions": _tx(rows)}, CFG, "Q6", "backward")
        self.assertEqual(list(back["tx_id"]), ["X5", "X3", "X1"])

    def test_flow_trace_unknown_account_empty(self):
        trail = tr.recipes()["flow_trace"](sample_tables(), CFG, "NOPE", "forward")
        self.assertTrue(trail.empty)
        self.assertEqual(list(trail.columns), TRAIL_COLUMNS)

    def test_flow_trace_dense_data_is_fast(self):
        start = time.perf_counter()
        trail = tr.recipes()["flow_trace"]({"transactions": _dense()}, CFG, "Q0", "forward")
        self.assertLess(time.perf_counter() - start, 5)
        self.assertTrue(trail["tx_id"].is_unique)


class TestFixRound1(unittest.TestCase):
    """Task 5 fix round 1: bounded pass ratio, scalable FLOW-TRACE, direction check, CPTY family."""

    def test_layering_rising_chain_not_flagged(self):
        rows = [("X1", "2026-08-01 10:00", "Q1", "Q2", 1000.0, "m"),
                ("X2", "2026-08-01 12:00", "Q2", "Q3", 1100.0, "m"),   # forwards more than received
                ("X3", "2026-08-02 12:00", "Q3", "Q4", 1200.0, "m")]
        self.assertTrue(run_card("flow_layering", {"transactions": _tx(rows)}).empty)
        rows[1] = ("X2", "2026-08-01 12:00", "Q2", "Q3", 1000.0, "m")  # exactly 100 % is still a pass
        rows[2] = ("X3", "2026-08-02 12:00", "Q3", "Q4", 950.0, "m")
        self.assertEqual(sorted(run_card("flow_layering", {"transactions": _tx(rows)})["entity_id"]),
                         ["Q1", "Q2", "Q3", "Q4"])

    def test_layering_random_lognormal_flags_few(self):
        rng = np.random.default_rng(5)
        n, accts = 20000, 2000
        names = np.array([f"Q{i}" for i in range(accts)])
        a = rng.integers(0, accts, n)
        b = (a + rng.integers(1, accts, n)) % accts
        ts = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.uniform(0, 90, n), unit="D")
        tx = pd.DataFrame({"tx_id": [f"X{i}" for i in range(n)], "ts": ts, "from_acct": names[a],
                           "to_acct": names[b], "amount": np.round(rng.lognormal(8, 1, n), 2),
                           "channel": "m"})
        start = time.perf_counter()
        ev = run_card("flow_layering", {"transactions": tx})
        self.assertLess(time.perf_counter() - start, 30)
        self.assertLess(ev["entity_id"].nunique() / accts, 0.02)
        for text in ev["explanation"]:
            self.assertIn("ไม่เกินยอดที่รับ", text)

    def test_flow_trace_bad_direction_raises(self):
        for bad in ["forwards", "back", "", None]:
            with self.assertRaises(ValueError) as cm:
                tr.recipes()["flow_trace"](sample_tables(), CFG, "L01", bad)
            self.assertIn("forward", str(cm.exception))
            self.assertIn("backward", str(cm.exception))

    def test_flow_trace_period_limits_first_hop(self):
        rows = [("X1", "2026-07-30 10:00", "Q1", "Q2", 100.0, "m"),
                ("X2", "2026-08-30 10:00", "Q1", "Q3", 100.0, "m"),
                ("X3", "2026-09-01 10:00", "Q3", "Q4", 100.0, "m"),   # later hop may leave the month
                ("X4", "2026-09-03 10:00", "Q1", "Q5", 100.0, "m")]
        f = tr.recipes()["flow_trace"]
        self.assertEqual(list(f({"transactions": _tx(rows)}, CFG, "Q1", "forward", "2026-08")["tx_id"]),
                         ["X2", "X3"])
        self.assertEqual(list(f({"transactions": _tx(rows)}, CFG, "Q1", "forward")["tx_id"]),
                         ["X1", "X2", "X4", "X3"])

    def test_flow_trace_cap_disclosed(self):
        f = tr.recipes()["flow_trace"]
        self.assertEqual(CFG["FLOW.MAX_TRAIL_ROWS"], 5000)
        full = f({"transactions": _dense()}, CFG, "Q0", "forward")
        self.assertFalse(full.attrs["truncated"])
        self.assertEqual(full.attrs["note"], "")
        small = f({"transactions": _dense()}, {**CFG, "FLOW.MAX_TRAIL_ROWS": 10}, "Q0", "forward")
        self.assertEqual(len(small), 10)
        self.assertTrue(small.attrs["truncated"])
        self.assertIn("FLOW.MAX_TRAIL_ROWS", small.attrs["note"])
        self.assertEqual(list(small["tx_id"]), list(full["tx_id"][:10]))

    def test_flow_trace_hub_is_fast_and_capped(self):
        rng = np.random.default_rng(9)
        n, accts = 120000, 5000
        names = np.array([f"Q{i}" for i in range(accts)])
        a = rng.integers(0, accts, n)
        b = (a + rng.integers(1, accts, n)) % accts
        hub = rng.random(n) < 0.05  # 5 % of transfers come from the hub Q0
        a[hub] = 0
        b[hub] = rng.integers(1, accts, hub.sum())
        ts = pd.Timestamp("2026-06-01") + pd.to_timedelta(rng.uniform(0, 90, n), unit="D")
        tx = pd.DataFrame({"tx_id": [f"X{i}" for i in range(n)], "ts": ts, "from_acct": names[a],
                           "to_acct": names[b], "amount": 100.0, "channel": "m"})
        for period in (None, "2026-07"):
            start = time.perf_counter()
            trail = tr.recipes()["flow_trace"]({"transactions": tx}, CFG, "Q0", "forward", period)
            self.assertLess(time.perf_counter() - start, 10)
            self.assertLessEqual(len(trail), CFG["FLOW.MAX_TRAIL_ROWS"])
            self.assertTrue(trail["tx_id"].is_unique)

    def test_cpty_cards_share_one_skill_family(self):
        for func in ("cpty_profile", "cpty_new_large"):
            ev = run_card(func)
            self.assertEqual(set(ev["skill_family"]), {"5.3 Behavioral"})


def _dense(n=1000, accts=20, seed=11):
    rng = random.Random(seed)
    names = [f"Q{i}" for i in range(accts)]
    rows = []
    for i in range(n):
        a, b = rng.sample(names, 2)
        rows.append((f"X{i}", f"2026-08-{rng.randint(1, 28):02d} {rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}",
                     a, b, 100.0, "m"))  # equal amounts: every hop passes 100 %
    return _tx(rows)


if __name__ == "__main__":
    unittest.main()
