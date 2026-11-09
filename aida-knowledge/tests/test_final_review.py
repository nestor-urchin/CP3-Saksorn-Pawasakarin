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

    def test_dashboard_with_card_notes_opens_in_browser(self):
        b = dict(to.sample_bundle())
        b["card_notes"] = ["NET-CYCLE: เดือน 2026-01: ทดสอบหมายเหตุ <b>อาจไม่ครบ</b>"]
        case = to.TestDashboard("test_dashboard_in_browser")
        case.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, case.dir, True)
        try:
            res = to.TestDashboard._browser(case, b)
        except unittest.SkipTest as e:
            self.skipTest(str(e))
        self.assertEqual(res["errors"], [])
        self.assertEqual(res["requests"], [])

    def test_no_note_no_review_row(self):
        b = to.sample_bundle()
        self.assertEqual(b["card_notes"], [])
        self.assertFalse(((b["run_log"]["status"] == "REVIEW") & (b["run_log"]["recipe_id"] == "NET-CYCLE")).any())


def _off_rows(acct, n_off, n_day, month="2026-08"):
    """n_off transfers at 22:00 on weekdays and n_day at 10:00, all sent by `acct`."""
    days = [d for d in pd.date_range(f"{month}-01", periods=28) if d.dayofweek < 5]
    rows = [(f"{acct}-O{i}", f"{days[i]:%Y-%m-%d} 22:00", acct, "Z", 100.0) for i in range(n_off)]
    rows += [(f"{acct}-D{i}", f"{days[i]:%Y-%m-%d} 10:00", acct, "Z", 100.0) for i in range(n_day)]
    return rows


class TestOffHoursMinimum(unittest.TestCase):
    def test_registry_keys(self):
        self.assertEqual(CFG["TEMP.OFF_HOURS.MIN_TX"], 3)
        self.assertEqual(CFG["TEMP.OFF_HOURS.MIN_SHARE"], 0.8)

    def run_off(self, rows, cfg=CFG):
        return R()["temp_offhours"]({"transactions": _tx(rows), "_out": {}}, cfg)

    def test_single_offhours_transfer_not_flagged(self):
        self.assertTrue(self.run_off(_off_rows("S1", 1, 0)).empty)

    def test_count_below_minimum_not_flagged(self):
        self.assertTrue(self.run_off(_off_rows("S2", 2, 0)).empty)  # 100 % but only 2

    def test_share_below_minimum_not_flagged(self):
        self.assertTrue(self.run_off(_off_rows("S3", 3, 3)).empty)  # 3 off-hours = 50 %

    def test_count_and_share_flagged(self):
        ev = self.run_off(_off_rows("S4", 4, 1) + _off_rows("S5", 3, 0))  # 80 % and 100 %
        self.assertEqual(sorted(ev["entity_id"]), ["S4", "S5"])
        row = ev.set_index("entity_id").loc["S4"]
        self.assertEqual(row["value"], 4)
        self.assertEqual(len(row["record_refs"]), 4)  # off-hours transfers only
        for key in ("TEMP.OFF_HOURS.MIN_TX", "TEMP.OFF_HOURS.MIN_SHARE", "80%", "AIDA-14"):
            self.assertIn(key, row["explanation"])
        self.assertEqual(row["recipe_version"], "1.1")

    def test_share_is_per_account_month(self):
        rows = _off_rows("S6", 3, 0, "2026-07") + _off_rows("S6", 0, 9, "2026-08")
        ev = self.run_off(rows)
        self.assertEqual(list(ev["period"]), ["2026-07"])

    def test_thresholds_from_cfg(self):
        cfg = {**CFG, "TEMP.OFF_HOURS.MIN_TX": 1, "TEMP.OFF_HOURS.MIN_SHARE": 0.1}
        self.assertEqual(list(self.run_off(_off_rows("S7", 1, 5), cfg)["entity_id"]), ["S7"])


IDENTITY = {"transactions": {}, "accounts": {}}


def raw_with_accounts(opened_values):
    """Raw (text) sample transactions + an accounts table whose opened_at values are given."""
    tx, acc = tp.raw_samples()
    acc = acc.head(len(opened_values)).assign(opened_at=list(opened_values))
    return tx, acc


class TestOpenedAtReadable(unittest.TestCase):
    def test_mostly_unreadable_opened_at_stops(self):
        vals = ["1 มกราคม 2569"] * 20 + ["2026-01-01 00:00:00"]  # full Thai month names
        tables = R()["prep_map"](dict(zip(("transactions", "accounts"), raw_with_accounts(vals))), IDENTITY, CFG)
        self.assertEqual(tables["_prep"]["unparsed_opened_at"], 20)
        self.assertEqual(tables["_prep"]["opened_at_rows"], 21)
        profile, status = R()["prof_profile"](tables, CFG)
        self.assertTrue(status.startswith("STOP"), status)
        self.assertIn("opened_at", status)
        self.assertIn("GATE.COMPLETENESS.MIN", status)
        self.assertIn("1 มกราคม 2569", status)  # names an example
        row = profile[profile["item"].str.contains("opened_at")]
        self.assertEqual(len(row), 1)
        self.assertEqual(row["value"].iloc[0], 20)

    def test_readable_opened_at_ok_with_profile_row(self):
        c = tp.sample_chain()
        self.assertEqual(c["status"], "OK")
        row = c["profile"][c["profile"]["item"].str.contains("opened_at")]
        self.assertEqual(row["value"].iloc[0], 0)
        self.assertEqual(c["tables"]["_prep"]["unparsed_opened_at"], 0)

    def test_no_accounts_no_opened_at_check(self):
        tables = R()["prep_map"]({"transactions": tp.raw_samples()[0]}, IDENTITY, CFG)
        self.assertEqual(tables["_prep"]["opened_at_rows"], 0)
        self.assertEqual(R()["prof_profile"](tables, CFG)[1], "OK")


class TestAmountReadable(unittest.TestCase):
    def test_mostly_unreadable_amount_stops_with_examples(self):
        tx = tp.raw_samples()[0].copy()
        tx.loc[tx.index[:600], "amount"] = "1,000 บาท"
        tables = R()["prep_map"]({"transactions": tx}, IDENTITY, CFG)
        self.assertIn("1,000 บาท", tables["_prep"]["amount_samples"])
        profile, status = R()["prof_profile"](tables, CFG)
        self.assertTrue(status.startswith("STOP"), status)
        self.assertIn("amount", status)
        self.assertIn("1,000 บาท", status)
        self.assertIn("GATE.COMPLETENESS.MIN", status)

    def test_few_unreadable_amounts_ok(self):
        tx = tp.raw_samples()[0].copy()
        tx.loc[tx.index[:10], "amount"] = "(1,000.00)"
        tables = R()["prep_map"]({"transactions": tx}, IDENTITY, CFG)
        self.assertEqual(tables["_prep"]["unparsed_amount"], 10)
        self.assertEqual(R()["prof_profile"](tables, CFG)[1], "OK")


class TestFirstSeenNotAssessed(unittest.TestCase):
    def test_gate_states_accounts_not_assessed(self):
        c = tp.sample_chain()
        tables = {k: v for k, v in c["tables"].items() if k != "accounts"}
        reason = R()["gate_capability"](tables, CFG).set_index("recipe_id").loc["MULE-NEW-ACCT", "reason"]
        t = tr.helper("clean_tx")(tables["transactions"])
        seen = pd.concat([t.groupby(s)["ts"].min() for s in ("from_acct", "to_acct")]).groupby(level=0).min()
        n = int((seen <= t["ts"].min() + pd.Timedelta(days=CFG["MULE.NEW_ACCT_DAYS"])).sum())
        self.assertGreater(n, 0)
        self.assertIn(f"ไม่ได้ประเมิน {n:,} บัญชี", reason)


class TestCrossTxPerMonth(unittest.TestCase):
    def test_mule_only_in_its_r2_month(self):
        """K1, K2 have R2 evidence in 2026-08 only: their March payments to C are not
        collector links; their August payments to D are."""
        rows = [("X1", "2026-03-02 10:00", "K1", "C", 100.0), ("X2", "2026-03-03 10:00", "K2", "C", 100.0),
                ("X3", "2026-08-04 10:00", "K1", "D", 100.0), ("X4", "2026-08-05 10:00", "K2", "D", 100.0)]
        ev = tp._ev("MULE-PATTERN", "5.10 Hybrid", "R2", [("K1", "2026-08", ["X3"]), ("K2", "2026-08", ["X4"])])
        out = R()["mule_cross_tx"]({"transactions": _tx(rows), "evidence": ev, "_out": {}}, CFG)
        self.assertEqual(set(zip(out["entity_id"], out["period"], out["value"])), {("D", "2026-08", "collector")})


def run_glue(raw_tx, folder):
    """Steps 3-11 of the Instructions as glue code: only Run cards, ev = core_evidence()
    when none runs, then outputs. Returns (plan, bundle, paths)."""
    tables = R()["prep_map"]({"transactions": raw_tx}, IDENTITY, CFG)
    profile, status = R()["prof_profile"](tables, CFG)
    assert not status.startswith("STOP"), status
    plan = R()["gate_capability"](tables, CFG)
    run = set(plan.loc[plan["decision"] == "Run", "recipe_id"])
    tables["_out"] = {}
    parts = [R()[f](tables, CFG) for f in tp.ACCOUNT_CARDS if f.upper().replace("_", "-") in run]
    ev = pd.concat(parts, ignore_index=True) if parts else R()["core_evidence"]()
    for f in ("mule_pattern", "mule_cross_tx", "mule_network"):
        if f.upper().replace("_", "-") in run:
            tables["evidence"] = ev
            ev = pd.concat([ev, R()[f](tables, CFG)], ignore_index=True)
    findings = R()["unify_findings"](ev, CFG, tables["_out"].get("mule_networks"))
    findings = R()["assess_cmp"](findings, tables["transactions"], None, CFG)
    trails = [R()["flow_trace"](tables, CFG, a, d, p) for a, p in R()["select_auto_trace"](findings, CFG)
              for d in ("forward", "backward")]
    events = [{"stage": 9, "status": "OK" if d == "Run" else "SKIP", "detail": r, "recipe_id": c}
              for c, d, r in zip(plan["recipe_id"], plan["decision"], plan["reason"])]
    log = R()["log_run"](events, CFG)
    b = R()["out_bundle"](tables, profile, plan, ev, findings, trails, log, None, CFG)
    return plan, b, to.write_all(b, folder)


class TestNoTsColumn(unittest.TestCase):
    def test_no_ts_file_yields_outputs_with_all_skips(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        plan, b, (wb, csvs, html) = run_glue(tp.raw_samples()[0].drop(columns="ts"), d)
        self.assertEqual(set(plan["decision"]), {"Skip"})
        self.assertEqual(len(b["findings"]), 0)
        self.assertEqual(len(b["edges"]), 0)
        log = pd.read_excel(wb, sheet_name="Run_Log")
        self.assertEqual(set(log["status"]), {"SKIP"})
        self.assertEqual(len(log), 15)
        for path in csvs + [html]:
            self.assertTrue(Path(path).exists(), path)

    def test_other_missing_base_columns_yield_outputs(self):
        for col in ("amount", "from_acct", "to_acct"):
            d = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, d, True)
            plan, b, (wb, _, html) = run_glue(tp.raw_samples()[0].drop(columns=col), d)
            self.assertEqual(set(plan["decision"]), {"Skip"}, col)
            self.assertTrue(Path(wb).exists() and Path(html).exists(), col)


class TestInstructions(unittest.TestCase):
    TEXT = (tr.ROOT / "AIDA-agent-instructions.md").read_text(encoding="utf-8")

    """C1 Instructions (Task 10): the 8-step engine flow and the confirmation rules."""

    def test_c1_flow_calls(self):
        for call in ("aida.inspect(", 'r["review_th"]', "aida.confirm(", "aida.run(", "aida.data(", "aida.explore_log(",
                     "aida.promote(", "aida.save_mapping(", "AIDA-16", '__version__ == "3.1.0"'):
            self.assertIn(call, self.TEXT)

    def test_confirmation_rules(self):
        for word in ('"ยืนยัน"', '"ตกลง"', '"ok"', '"ไปต่อ"', "การแก้ค่า", '{"type": "ไม่ระบุ"}', "ไม่ตอบข้อ D = ไม่เพิ่มความเสี่ยง",
                     "ในคำตอบเดียวกับที่ยืนยัน"):
            self.assertIn(word, self.TEXT)

    def test_no_numbers_and_wording(self):
        self.assertIn("ห้ามคำนวณหรือแต่งตัวเลขเอง", self.TEXT)
        self.assertIn('"บัญชีม้า"', self.TEXT)
        self.assertIn("ระบุชื่อผู้ทบทวน", self.TEXT)

    def test_stop_location_and_out_dir(self):
        self.assertIn('r["intake"]["profile_status"]', self.TEXT)
        self.assertIn("ข้อ E ของ review_th", self.TEXT)
        self.assertIn("/mnt/data/aida_out", self.TEXT)

    def test_no_b1_recipe_steps_left(self):
        for old in ("จุดยืนยัน 1", "prep_map", "card_notes", "RECIPE"):
            self.assertNotIn(old, self.TEXT)

    def test_length(self):
        self.assertLessEqual(len(self.TEXT), 8000)

    def test_log_run_uses_pack_version(self):
        cfg = {**CFG, "_RUN": {**CFG["_RUN"], "pack_version": "2.0"}}
        log = R()["log_run"]([{"stage": 1, "status": "OK", "detail": "x"}], cfg)
        self.assertEqual(log["pack_version"].iloc[0], "2.0")


def messy_tx(n, n_accts, seed=0):
    """Realistic-looking raw (text) transfers like the reviewer's gen.py: heavy-tailed account
    activity, a hub that receives 8 % and sends 3 % of all transfers, day-time-weighted hours,
    lognormal amounts written "1,234.56", dd/mm/พ.ศ. timestamps, a few self-transfers."""
    rng = np.random.default_rng(seed)
    accts = np.array([f"{1000000000 + i}" for i in range(n_accts)])
    w = rng.pareto(1.5, n_accts) + 1
    src, dst = rng.choice(n_accts, n, p=w / w.sum()), rng.choice(n_accts, n, p=w / w.sum())
    m = rng.random(n)
    dst[m < .08], src[(m >= .08) & (m < .11)] = 0, 0
    hw = np.array([1, .6, .4, .3, .3, .5, 1.5, 3, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5.5, 5, 4.5, 4, 3, 2])
    ts = (pd.Timestamp("2026-03-01") + pd.to_timedelta(rng.integers(0, 183, n), "D")
          + pd.to_timedelta(rng.choice(24, n, p=hw / hw.sum()), "h") + pd.to_timedelta(rng.integers(0, 3600, n), "s"))
    df = pd.DataFrame({"tx_id": [f"TX{i:07d}" for i in range(n)], "ts": ts, "from_acct": accts[src],
                       "to_acct": accts[dst], "amount": np.round(np.exp(rng.normal(7.5, 1.6, n)), 2),
                       "channel": rng.choice(["mobile", "internet", "atm", "branch"], n, p=[.7, .15, .1, .05])})
    df = df.sort_values("ts")
    df["ts"] = [f"{t.day:02d}/{t.month:02d}/{t.year + 543} {t:%H:%M:%S}" for t in df["ts"]]
    df["amount"] = [f"{a:,.2f}" for a in df["amount"]]
    i = df.sample(frac=.003, random_state=2).index
    df.loc[i, "to_acct"] = df.loc[i, "from_acct"]
    return df.reset_index(drop=True)


class TestPerformance(unittest.TestCase):
    """Tested ceiling (README / spike/LOCAL-RESULTS.md): one run of 20,000 rows end to end
    well inside a minute on a laptop-class CPU."""

    def test_funnel_hub_is_not_quadratic(self):
        rng = np.random.default_rng(3)
        n = 12000  # one account receiving 12,000 transfers from 500 sources and forwarding them
        ts = pd.Timestamp("2026-03-01") + pd.to_timedelta(np.sort(rng.integers(0, 180 * 86400, n)), "s")
        ins = pd.DataFrame({"tx_id": [f"I{i}" for i in range(n)], "ts": ts, "from_acct": [f"S{i % 500}" for i in range(n)],
                            "to_acct": "HUB", "amount": 1000.0})
        outs = ins.assign(tx_id=[f"O{i}" for i in range(n)], ts=ts + pd.Timedelta(hours=1), from_acct="HUB",
                          to_acct="SINK", amount=950.0)
        s = time.time()
        ev = R()["net_funnel"]({"transactions": pd.concat([ins, outs]), "_out": {}}, CFG)
        self.assertLess(time.time() - s, 8)  # the old per-inflow window scan took ~20 s here
        self.assertEqual(set(ev["entity_id"]), {"HUB"})

    def test_20k_rows_end_to_end_under_60s(self):
        raw = messy_tx(20000, 1500)
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        s = time.time()
        plan, b, (wb, _, html) = run_glue(raw, d)
        took = time.time() - s
        self.assertLess(took, 60, f"20k rows took {took:.0f} s")
        self.assertTrue(Path(wb).exists() and Path(html).exists())
        self.assertGreater(len(b["findings"]), 0)

    def test_tested_ceiling_published(self):
        for doc in (tr.ROOT / "README.md", tr.ROOT / "spike" / "LOCAL-RESULTS.md"):
            text = doc.read_text(encoding="utf-8")
            self.assertIn("80,000", text, doc.name)
            self.assertIn("แบ่งไฟล์ตามเดือน", text, doc.name)


if __name__ == "__main__":
    unittest.main()
