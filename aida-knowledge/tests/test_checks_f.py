"""Tests for the six fund certified checks F-R1..F-R6 (AIDA C2 task 4).

Sample tests run each check on the tables built from samples/F (variants/roles_en.json) with attach_meta and the
key's code_values; ids come from the F answer key. Boundary tests use small synthetic frames.
"""
import json
import sys
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import engine  # noqa: E402
import sample_common as sc  # noqa: E402

ROOT = HERE.parent
CHECKS = {"FUND-ROUNDTRIP": "F-R1", "FUND-THIRD-PARTY": "F-R2", "FUND-SHARED-ACCT": "F-R3", "FUND-FREQUENT": "F-R4",
          "FUND-CHURN": "F-R5", "FUND-LATE-TRADE": "F-R6"}
CODES = {"B": "ซื้อหน่วยลงทุน", "S": "ขายคืนหน่วยลงทุน", "I": "สับเปลี่ยนเข้า", "O": "สับเปลี่ยนออก"}
_CACHE = {}


def cfg(**over):
    e = engine()
    return {**e.load_registry(sc.REGISTRY_PATH), "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}, **over}


def load(variant="en"):
    if variant not in _CACHE:
        d = ROOT / "samples" / "F"
        roles = json.loads((d / "variants" / f"roles_{'en' if variant == 'date_only' else variant}.json").read_text(encoding="utf-8"))
        roles.pop("dataset_type", None)
        key = json.loads((d / "answer_key.json").read_text(encoding="utf-8"))
        src = d if variant == "en" else d / "variants" / variant
        frames = {t: pd.read_csv(src / f"{t}.csv", dtype=str, keep_default_na=False) for t in roles}
        e = engine()
        tables = e.to_internal(frames, roles)
        e.attach_meta(tables, {"roles": roles, "dataset_type": "F"})
        tables["meta"]["code_values"] = {tables["meta"]["category_key"]: dict(next(iter(key["code_values"].values())))}
        _CACHE[variant] = (tables, key, roles)
    t, key, roles = _CACHE[variant]
    return {k: (dict(v) if k == "meta" else v.copy() if hasattr(v, "copy") else v) for k, v in t.items()}, key


def sample(variant="en"):
    return load(variant)


def run_sample(check, variant="en", **over):
    tables, key = sample(variant)
    return engine().CHECKS[check]["func"](tables, cfg(**over)), key


def mk(tx, codes=CODES):
    """Synthetic internal tables. tx rows: (tx_id, holder, fund, ts, code, amount, account, agent, nav_date)."""
    cols = ["tx_id", "from_acct", "contract", "ts", "category", "amount", "to_acct", "channel", "due_date"]
    t = {"transactions": pd.DataFrame(tx, columns=cols)}
    t["meta"] = {"code_values": {"t.type": dict(codes)} if codes else {}, "category_key": "t.type", "dtype": "F",
                 "tx_table": "t", "events_table": None}
    return t


def row(i, holder, ts, code, amt=1000.0, fund="FX1", acct=None, agent="AG-1", nav=None):
    return (f"O{i}", holder, fund, ts, code, amt, acct or holder, agent, nav or str(ts)[:10])


def call(check, tables, **over):
    return engine().CHECKS[check]["func"](tables, cfg(**over)), tables


def make_case(check):
    def planted(self):
        ev, key = run_sample(check)
        self.assertEqual(set(ev["entity_id"]), set(key["recipes"][check]))
        self.assertEqual(set(ev["risk"]), {CHECKS[check]})
        self.assertGreater(len(ev), 0)

    def no_fp(self):
        ev, key = run_sample(check)
        self.assertEqual(set(ev["entity_id"]) - set(key["recipes"][check]), set())
        self.assertEqual(len(ev), len(set(zip(ev["entity_id"], ev["period"]))))
    return planted, no_fp


class SampleChecks(unittest.TestCase):
    def test_evidence_schema(self):
        e = engine()
        for check in CHECKS:
            ev, _ = run_sample(check)
            self.assertEqual(list(ev.columns), e.EVIDENCE_COLUMNS + ["roles_used"], check)
            self.assertTrue(ev["explanation"].str.contains("[ก-๙]").all())
            self.assertFalse(ev["explanation"].str.contains("ทุจริต|บัญชีม้า").any())
            self.assertTrue(ev["record_refs"].map(len).gt(0).all())
            self.assertTrue(ev["registry_key"].map(lambda k: k in cfg()).all())

    def test_roundtrip_period_and_refs(self):
        ev, _ = run_sample("FUND-ROUNDTRIP")
        self.assertEqual(list(ev["period"]), ["2026-05"])
        self.assertEqual(len(ev["record_refs"].iloc[0]), 2)  # the buy and the sale

    def test_third_party_does_not_report_shared_account_holders(self):
        ev, _ = run_sample("FUND-THIRD-PARTY")
        self.assertFalse({"U-0301", "U-0302", "U-0303", "U-0304"} & set(ev["entity_id"]))

    def test_findings_match_key_via_finding_view(self):
        """Every F key finding appears once Evidence goes through _finding_view (F-R6: order -> unitholder)."""
        e = engine()
        tables, key = sample()
        evs = [e.CHECKS[c]["func"](tables, cfg()) for c in CHECKS]
        ev = pd.concat(evs, ignore_index=True)
        view = e._finding_view(ev, tables["transactions"], "F")
        got = {(r["entity_type"], r["entity_id"], r["risk"], r["period"]) for _, r in view.iterrows()}
        want = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in key["findings"]}
        self.assertEqual(got, want)


for _c in CHECKS:
    _p, _f = make_case(_c)
    setattr(SampleChecks, "test_" + _c.lower().replace("-", "_") + "_finds_planted", _p)
    setattr(SampleChecks, "test_" + _c.lower().replace("-", "_") + "_no_false_positive", _f)


class Boundaries(unittest.TestCase):
    def test_roundtrip_uses_time_order(self):
        # the sale row is first in the file but happens after the buy; and a sale before the buy never pairs
        tx = [row(1, "U-1", "2026-03-10 14:00:00", "S", 1000.0), row(2, "U-1", "2026-03-10 09:00:00", "B", 1000.0),
              row(3, "U-2", "2026-03-10 09:00:00", "S", 1000.0), row(4, "U-2", "2026-03-10 14:00:00", "B", 1000.0)]
        ev, _ = call("FUND-ROUNDTRIP", mk(tx))
        self.assertEqual(list(ev["entity_id"]), ["U-1"])

    def test_roundtrip_same_day_date_only_pairs(self):
        tx = [row(1, "U-1", "2026-03-10", "B"), row(2, "U-1", "2026-03-10", "S")]
        ev, _ = call("FUND-ROUNDTRIP", mk(tx))
        self.assertEqual(list(ev["entity_id"]), ["U-1"])

    def test_roundtrip_band_boundary(self):
        def hit(amt):
            tx = [row(1, "U-1", "2026-03-01", "B", 1000.0), row(2, "U-1", "2026-03-05", "S", amt)]
            return len(call("FUND-ROUNDTRIP", mk(tx))[0])
        self.assertEqual(hit(800.0), 1)
        self.assertEqual(hit(1200.0), 1)
        self.assertEqual(hit(799.0), 0)  # 79.9%
        self.assertEqual(hit(1201.0), 0)

    def test_roundtrip_days_boundary_and_other_fund(self):
        def hit(day, fund="FX1"):
            tx = [row(1, "U-1", "2026-03-01", "B"), row(2, "U-1", day, "S", fund=fund)]
            return len(call("FUND-ROUNDTRIP", mk(tx))[0])
        self.assertEqual(hit("2026-03-31"), 1)   # 30 days
        self.assertEqual(hit("2026-04-01"), 0)   # 31 days
        self.assertEqual(hit("2026-03-05", "FX2"), 0)  # another fund

    def test_roundtrip_pairs_latest_earlier_buy(self):
        # the latest earlier buy (amount 5000) is the pair, not the older one (1000): ratio 0.2 -> no finding
        tx = [row(1, "U-1", "2026-03-01", "B", 1000.0), row(2, "U-1", "2026-03-05", "B", 5000.0),
              row(3, "U-1", "2026-03-06", "S", 1000.0)]
        self.assertEqual(len(call("FUND-ROUNDTRIP", mk(tx))[0]), 0)

    def test_roundtrip_switch_never_counts(self):
        tx = [row(1, "U-1", "2026-03-01", "B"), row(2, "U-1", "2026-03-03", "O"), row(3, "U-1", "2026-03-04", "I")]
        self.assertEqual(len(call("FUND-ROUNDTRIP", mk(tx))[0]), 0)

    def test_third_party_basic_and_per_row_comparability(self):
        tx = [row(1, "U-1", "2026-03-01", "S", acct="U-9"), row(2, "U-2", "2026-03-01", "S", acct="BA-7000"),
              row(3, "U-3", "2026-03-01", "S")]
        t = mk(tx)
        ev, _ = call("FUND-THIRD-PARTY", t)
        self.assertEqual(list(ev["entity_id"]), ["U-1"])  # BA-7000 vs U-2 is not comparable, so not reported

    def test_third_party_incomparable_skips(self):
        tx = [row(i, f"U-{i}", "2026-03-01", "S", acct="BA-7000") for i in range(1, 4)]
        t = mk(tx)
        ev, _ = call("FUND-THIRD-PARTY", t)
        self.assertEqual(len(ev), 0)
        self.assertIn("เทียบกันไม่ได้", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def test_shared_acct_min_holders_boundary(self):
        def tx(n):
            return [row(i, f"U-{i}", "2026-03-01", "S", acct="BA-7000") for i in range(1, n + 1)]
        self.assertEqual(list(call("FUND-SHARED-ACCT", mk(tx(3)))[0]["entity_id"]), ["BA-7000"])
        self.assertEqual(len(call("FUND-SHARED-ACCT", mk(tx(2)))[0]), 0)

    def test_shared_acct_one_holder_many_rows_not_counted(self):
        tx = [row(i, "U-1", f"2026-03-0{i}", "S", acct="BA-7000") for i in range(1, 6)]
        self.assertEqual(len(call("FUND-SHARED-ACCT", mk(tx))[0]), 0)

    def test_freq_boundary(self):
        def month(n, code_cycle="BSIO"):
            return [row(i, "U-1", f"2026-03-{i:02d}", code_cycle[i % 4], amt=100.0 + i) for i in range(1, n + 1)]
        ev, _ = call("FUND-FREQUENT", mk(month(6)))
        self.assertEqual(list(ev["entity_id"]), ["U-1"])
        self.assertEqual(ev["value"].iloc[0], 6)
        self.assertEqual(len(call("FUND-FREQUENT", mk(month(5)))[0]), 0)

    def test_freq_counts_switches_and_splits_months(self):
        tx = [row(i, "U-1", f"2026-03-{i:02d}", "O") for i in range(1, 4)] + \
             [row(10 + i, "U-1", f"2026-04-{i:02d}", "B") for i in range(1, 4)]
        self.assertEqual(len(call("FUND-FREQUENT", mk(tx))[0]), 0)  # 3 + 3 in two months
        tx = [row(i, "U-1", f"2026-03-{i:02d}", "O" if i % 2 else "I") for i in range(1, 7)]
        self.assertEqual(len(call("FUND-FREQUENT", mk(tx))[0]), 1)

    def test_freq_runs_with_partial_codes_and_notes_missing(self):
        e = engine()
        tx = [row(i, "U-1", f"2026-03-{i:02d}", "B") for i in range(1, 7)]
        t = mk(tx, codes={"B": CODES["B"], "S": CODES["S"]})
        self.assertEqual(e.plan_checks(t, cfg()).set_index("recipe_id").loc["FUND-FREQUENT", "decision"], "Run")
        self.assertEqual(len(call("FUND-FREQUENT", t)[0]), 1)
        self.assertIn("switch_in", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def _churn_tables(self, clients, frequent, agent="AG-1"):
        tx, n = [], 0
        for c in range(clients):
            holder = f"U-{c}"
            k = 6 if c < frequent else 1
            for d in range(1, k + 1):
                n += 1
                tx.append(row(n, holder, f"2026-03-{d:02d}", "B", agent=agent))
        return mk(tx)

    def test_churn_min_clients_boundary(self):
        # share is 50% in both cases; only the number of frequent clients (5 vs 4) differs
        self.assertEqual(list(call("FUND-CHURN", self._churn_tables(10, 5))[0]["entity_id"]), ["AG-1"])
        self.assertEqual(len(call("FUND-CHURN", self._churn_tables(8, 4))[0]), 0)

    def test_churn_share_boundary(self):
        self.assertEqual(len(call("FUND-CHURN", self._churn_tables(16, 5))[0]), 1)   # 31.25%
        self.assertEqual(len(call("FUND-CHURN", self._churn_tables(17, 5))[0]), 0)   # 29.4%
        self.assertEqual(len(call("FUND-CHURN", self._churn_tables(20, 6))[0]), 1)   # exactly 30%

    def test_churn_multi_agent_attribution(self):
        tx, n = [], 0
        for c in range(5):  # 1 trade each with AG-Y in January, then 6 trades each with AG-X in July
            n += 1
            tx.append(row(n, f"U-{c}", "2026-01-05", "B", agent="AG-Y"))
            for d in range(1, 7):
                n += 1
                tx.append(row(n, f"U-{c}", f"2026-07-{d:02d}", "B", agent="AG-X"))
        ev, _ = call("FUND-CHURN", mk(tx))
        self.assertEqual(list(ev["entity_id"]), ["AG-X"])

    def test_churn_period_is_the_month_of_frequent_clients(self):
        ev, _ = call("FUND-CHURN", self._churn_tables(10, 5))
        self.assertEqual(ev["period"].iloc[0], "2026-03")

    def test_late_trade_cutoff_boundary(self):
        tx = [row(1, "U-1", "2026-03-10 15:30:00", "B", nav="2026-03-10"), row(2, "U-2", "2026-03-10 15:31:00", "B", nav="2026-03-10"),
              row(3, "U-3", "2026-03-10 15:31:00", "B", nav="2026-03-11")]
        ev, _ = call("FUND-LATE-TRADE", mk(tx))
        self.assertEqual(list(ev["entity_id"]), ["O2"])  # 15:30 is on time; same-day NAV only
        self.assertEqual(ev["period"].iloc[0], "2026-03")

    def test_cutoff_override(self):
        ev, _ = run_sample("FUND-LATE-TRADE")
        self.assertEqual(list(ev["entity_id"]), ["O-6006"])
        ev, _ = run_sample("FUND-LATE-TRADE", **{"FUND.CUTOFF_TIME": "17:00"})
        self.assertNotIn("O-6006", set(ev["entity_id"]))

    def test_late_trade_thai_be_datetime(self):
        e = engine()
        raw = pd.DataFrame({"tx_id": ["O1", "O2", "O3"], "from_acct": ["U-1", "U-2", "U-3"], "contract": ["FX1"] * 3,
                            "ts": ["05/03/2569 16:10", "05/03/2569 15:10", "05/03/2569"], "category": ["B"] * 3,
                            "amount": ["1000"] * 3, "to_acct": ["U-1", "U-2", "U-3"], "channel": ["AG-1"] * 3,
                            "due_date": ["05/03/2569"] * 3})
        t = e._prep_internal({"transactions": raw}, cfg())
        t["meta"] = {"code_values": {"t.type": dict(CODES)}, "category_key": "t.type", "dtype": "F", "tx_table": "t",
                     "events_table": None}
        ev = e.CHECKS["FUND-LATE-TRADE"]["func"](t, cfg())
        self.assertEqual(list(ev["entity_id"]), ["O1"])  # 16:10 is after 15:30; 15:10 is not; no time of day is not judged
        self.assertEqual(ev["period"].iloc[0], "2026-03")  # 2569 BE = 2026

    def test_late_trade_needs_no_codes(self):
        tx = [row(1, "U-1", "2026-03-10 16:00:00", "B")]
        t = mk(tx, codes={})
        self.assertEqual(len(call("FUND-LATE-TRADE", t)[0]), 1)

    def test_late_trade_skips_date_only(self):
        e = engine()
        tables, _ = sample("date_only")
        ev = e.CHECKS["FUND-LATE-TRADE"]["func"](tables, cfg())
        self.assertEqual(len(ev), 0)
        notes = " ".join(n["detail"] for n in tables["_out"]["notes"])
        self.assertRegex(notes, "เวลา")
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["FUND-LATE-TRADE", "decision"], "Run")  # roles present; the run itself skips with a reason

    def test_late_trade_without_due_date_skips(self):
        tx = [row(1, "U-1", "2026-03-10 16:00:00", "B")]
        t = mk(tx)
        t["transactions"] = t["transactions"].drop(columns="due_date")
        ev = engine().CHECKS["FUND-LATE-TRADE"]["func"](t, cfg())
        self.assertEqual(len(ev), 0)
        self.assertRegex(" ".join(n["detail"] for n in t["_out"]["notes"]), "due_date|NAV")
        plan = engine().plan_checks(t, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["FUND-LATE-TRADE", "decision"], "Skip")


class FindingMapping(unittest.TestCase):
    def test_late_trade_finding_is_keyed_by_unitholder(self):
        e = engine()
        tables, key = sample()
        ev = e.CHECKS["FUND-LATE-TRADE"]["func"](tables, cfg())
        view = e._finding_view(ev, tables["transactions"], "F")
        self.assertEqual([(r["entity_type"], r["entity_id"], r["risk"], r["period"]) for _, r in view.iterrows()],
                         [("unitholder", "U-0606", "F-R6", "2026-09")])

    def test_two_late_orders_of_one_holder_make_one_finding(self):
        e = engine()
        tx = [row(1, "U-1", "2026-03-10 16:00:00", "B"), row(2, "U-1", "2026-03-12 16:30:00", "B")]
        t = mk(tx)
        ev = e.CHECKS["FUND-LATE-TRADE"]["func"](t, cfg())
        view = e._finding_view(ev, t["transactions"], "F")
        f = e.unify_findings(view[e.EVIDENCE_COLUMNS], cfg(), None)
        self.assertEqual(len(f), 1)
        self.assertEqual(f["entity_id"].iloc[0], "U-1")

    def test_other_checks_unchanged(self):
        e = engine()
        tables, _ = sample()
        ev = e.CHECKS["FUND-FREQUENT"]["func"](tables, cfg())
        view = e._finding_view(ev, tables["transactions"], "F")
        self.assertEqual(set(view["entity_id"]), set(ev["entity_id"]))


class SufficiencyDateOnly(unittest.TestCase):
    def _assess(self, variant):
        e = engine()
        d = ROOT / "samples" / "F"
        roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
        src = d / "variants" / "date_only" if variant == "date_only" else d
        frames = {t: pd.read_csv(src / f"{t}.csv", dtype=str, keep_default_na=False) for t in roles}
        profile = e.profile_columns(frames)
        return e.assess_sufficiency(["F-R6"], roles, profile, cfg()).iloc[0]

    def test_date_only_f_r6_partial(self):
        _, key = sample()
        conv = key["conventions"]["date_only"]
        r = self._assess("date_only")
        self.assertEqual(r["status"], conv["sufficiency"]["F-R6"])
        self.assertEqual(list(r["data_request"]), conv["data_request"])
        self.assertIn("FUND-LATE-TRADE", r["skipped_checks"])

    def test_date_only_plan_reason_names_cutoff_not_offhours(self):
        _, key = sample()
        d = ROOT / "samples" / "F"
        roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
        frames = {t: pd.read_csv(d / "variants" / "date_only" / f"{t}.csv", dtype=str, keep_default_na=False) for t in roles}
        e = engine()
        pl = e.plan(["F-R6", "G-R3"], roles, e.profile_columns(frames), cfg()).set_index("check_id")
        self.assertIn("หลังเวลาตัดรอบ", pl.loc["FUND-LATE-TRADE", "reason"])
        self.assertNotIn("นอกเวลาทำการ", pl.loc["FUND-LATE-TRADE", "reason"])
        self.assertIn("นอกเวลาทำการ", pl.loc["TEMP-OFFHOURS", "reason"])

    def test_time_partial_is_a_library_attribute(self):
        lib = engine().RISK_LIBRARY
        self.assertTrue(lib["F-R6"]["time_partial"])
        self.assertFalse(any(v.get("time_partial") for k, v in lib.items() if k != "F-R6"))

    def test_with_time_f_r6_ready(self):
        _, key = sample()
        r = self._assess("en")
        self.assertEqual(r["status"], key["intake"]["sufficiency"]["F-R6"])
        self.assertEqual(list(r["data_request"]), [])


class Guards(unittest.TestCase):
    def test_f_risks_in_library_and_checks_exist(self):
        e = engine()
        names = {"F-R1": "ซื้อแล้วขายคืนเร็ว", "F-R2": "ผู้ชำระหรือผู้รับเงินเป็นบุคคลที่สาม",
                 "F-R3": "บัญชีรับเงินเดียวใช้กับผู้ถือหน่วยหลายราย", "F-R4": "ซื้อขายหรือสับเปลี่ยนถี่",
                 "F-R5": "ตัวแทนขายชักนำให้ซื้อขายถี่", "F-R6": "ทำรายการหลังเวลาตัดรอบ"}
        for check, risk in CHECKS.items():
            self.assertIn(check, e.CHECKS)
            self.assertEqual(e.CHECKS[check]["risk"], risk)
            self.assertEqual(e.CHECKS[check]["data_types"], ["F"])
            self.assertEqual(e.RISK_LIBRARY[risk]["checks"], [check])
            self.assertEqual(e.RISK_LIBRARY[risk]["name_th"], names[risk])
            self.assertEqual(e.RISK_LIBRARY[risk]["data_types"], ["F"])
            self.assertTrue(e.RISK_LIBRARY[risk]["synonyms"])
            for k in e.CHECKS[check]["registry"]:
                self.assertIn(k, cfg())

    def test_f_checks_skip_without_codes(self):
        e = engine()
        tables, _ = sample()
        tables["meta"] = {"code_values": {}, "category_key": "fund_txn.txn_type", "dtype": "F"}
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        for check in ("FUND-ROUNDTRIP", "FUND-FREQUENT", "FUND-CHURN"):
            self.assertEqual(plan.loc[check, "decision"], "Skip", check)
            self.assertRegex(plan.loc[check, "reason"], "ความหมายรหัสประเภทรายการ")
            ev = e.CHECKS[check]["func"](tables, cfg())
            self.assertEqual(len(ev), 0)
            self.assertIn("ความหมายรหัสประเภทรายการ", " ".join(n["detail"] for n in tables["_out"]["notes"]))
        for check in ("FUND-THIRD-PARTY", "FUND-SHARED-ACCT", "FUND-LATE-TRADE"):  # these need no codes
            self.assertEqual(plan.loc[check, "decision"], "Run", check)

    def test_roundtrip_needs_both_buy_and_sell(self):
        e = engine()
        tables, key = sample()
        cv = {k: v for k, v in key["code_values"]["fund_txn.txn_type"].items() if k != "SELL"}
        tables["meta"]["code_values"] = {"fund_txn.txn_type": cv}
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["FUND-ROUNDTRIP", "decision"], "Skip")
        self.assertEqual(len(e.CHECKS["FUND-ROUNDTRIP"]["func"](tables, cfg())), 0)

    def test_f_checks_skip_on_other_data_type(self):
        e = engine()
        tables, _ = sample()
        tables["meta"]["dtype"] = "E"
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        for check in CHECKS:
            self.assertEqual(plan.loc[check, "decision"], "Skip", check)

    def test_variants_give_same_evidence(self):
        base = {c: set(run_sample(c)[0]["entity_id"]) for c in CHECKS}
        for v in ("th", "legacy"):
            tables, _ = sample(v)
            for c in CHECKS:
                self.assertEqual(set(engine().CHECKS[c]["func"](tables, cfg())["entity_id"]), base[c], (v, c))


if __name__ == "__main__":
    unittest.main()
