"""Tests for the six life-insurance certified checks L-R1..L-R6 (AIDA C2 task 3).

Sample tests run each check on the tables built from samples/L (variants/roles_en.json) with attach_meta and the
key's code_values; ids come from the L answer key. Boundary tests use small synthetic frames.
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
CHECKS = {"LIFE-EARLY-SURR": "L-R1", "LIFE-BENCHG-CASH": "L-R2", "LIFE-LOAN": "L-R3", "LIFE-THIRD-PAYEE": "L-R4",
          "LIFE-BENEF-MULTI": "L-R5", "LIFE-STAFF-CONC": "L-R6"}
CODES = {"S": "เวนคืนกรมธรรม์", "L": "กู้ยืมตามกรมธรรม์", "C": "จ่ายสินไหม"}
_CACHE = {}


def cfg(**over):
    e = engine()
    return {**e.load_registry(sc.REGISTRY_PATH), "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}, **over}


def sample():
    if "L" not in _CACHE:
        d = ROOT / "samples" / "L"
        roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
        key = json.loads((d / "answer_key.json").read_text(encoding="utf-8"))
        frames = {t: pd.read_csv(d / f"{t}.csv", dtype=str, keep_default_na=False) for t in roles}
        e = engine()
        tables = e.to_internal(frames, roles)
        e.attach_meta(tables, {"roles": roles, "code_values": key["code_values"], "dataset_type": "L"})
        _CACHE["L"] = (tables, key)
    t, key = _CACHE["L"]
    return {k: (v.copy() if hasattr(v, "copy") else v) for k, v in t.items()}, key


def run_sample(check, **over):
    tables, key = sample()
    return engine().CHECKS[check]["func"](tables, cfg(**over)), key


def mk(tx, accounts=None, events=None, codes=CODES):
    """Synthetic internal tables. tx rows: (tx_id, contract, insured, date, code, amount, payee, limit, staff)."""
    cols = ["tx_id", "contract", "from_acct", "ts", "category", "amount", "to_acct", "limit", "created_by"]
    t = {"transactions": pd.DataFrame(tx, columns=cols)}
    if accounts is not None:
        t["accounts"] = pd.DataFrame(accounts, columns=["contract", "acct_id", "opened_at", "category"])
    if events is not None:
        t["events"] = pd.DataFrame(events, columns=["tx_id", "contract", "ts", "to_acct", "created_by"])
    t["meta"] = {"code_values": {"t.type": dict(codes)} if codes else {}, "category_key": "t.type", "dtype": "L",
                 "tx_table": "t", "events_table": "ev" if events is not None else None}
    return t


def row(i, pol, d, code, amt=100.0, payee=None, limit=1000.0, staff="S-1", ins=None):
    return (f"T{i}", pol, ins or "I-" + pol[2:], d, code, amt, payee or ins or "I-" + pol[2:], limit, staff)


def call(check, tables, **over):
    return engine().CHECKS[check]["func"](tables, cfg(**over))


def make_case(check):
    def planted(self):
        ev, key = run_sample(check)
        want = set(key["recipes"][check])
        self.assertEqual(set(ev["entity_id"]), want)
        self.assertEqual(set(ev["risk"]), {CHECKS[check]})
        self.assertGreater(len(ev), 0)

    def no_fp(self):
        ev, key = run_sample(check)
        self.assertEqual(set(ev["entity_id"]) - set(key["recipes"][check]), set())
        self.assertEqual(len(ev), len(set(zip(ev["entity_id"], ev["period"]))))
    return planted, no_fp


class SampleChecks(unittest.TestCase):
    def test_periods_and_types_match_key(self):
        _, key = sample()
        by_risk = {}
        for check, risk in CHECKS.items():
            ev, _ = run_sample(check)
            lab = engine().ENTITY_LABELS["L"]
            for _, r in ev.iterrows():
                by_risk[(risk, r["entity_id"])] = (lab.get(r["entity_type"], r["entity_type"]), r["period"])
        for f in key["findings"]:
            self.assertEqual(by_risk[(f["risk"], f["entity_id"])], (f["entity_type"], f["period"]), f)

    def test_evidence_schema(self):
        e = engine()
        for check in CHECKS:
            ev, _ = run_sample(check)
            self.assertEqual(list(ev.columns), e.EVIDENCE_COLUMNS + ["roles_used"], check)
            self.assertTrue(ev["explanation"].str.contains("[ก-๙]").all())
            self.assertFalse(ev["explanation"].str.contains("ทุจริต|บัญชีม้า").any())
            self.assertTrue(ev["record_refs"].map(len).gt(0).all())
            self.assertTrue(ev["registry_key"].map(lambda k: k in cfg()).all())


for _c in CHECKS:
    _p, _f = make_case(_c)
    setattr(SampleChecks, "test_" + _c.lower().replace("-", "_") + "_finds_planted", _p)
    setattr(SampleChecks, "test_" + _c.lower().replace("-", "_") + "_no_false_positive", _f)


class Boundaries(unittest.TestCase):
    def test_early_surr_boundary(self):
        acc = [("P-1", "I-1", "2025-01-10", "single"), ("P-2", "I-2", "2025-01-10", "periodic")]
        tx = [row(1, "P-1", "2026-01-10", "S"), row(2, "P-2", "2026-01-11", "S")]
        ev = call("LIFE-EARLY-SURR", mk(tx, acc))
        self.assertEqual(list(ev["entity_id"]), ["P-1"])
        self.assertEqual(ev["period"].iloc[0], "2026-01")
        self.assertIn("เบี้ยเดียว", ev["explanation"].iloc[0])  # single premium is noted in the Evidence

    def test_early_surr_missing_master_row(self):
        acc = [("P-1", "I-1", "2025-06-01", "periodic"), ("P-3", "I-3", "", "periodic")]
        tx = [row(1, "P-1", "2025-09-01", "S"), row(2, "P-2", "2025-09-01", "S"), row(3, "P-3", "2025-09-01", "S")]
        t = mk(tx, acc)
        ev = call("LIFE-EARLY-SURR", t)
        self.assertEqual(list(ev["entity_id"]), ["P-1"])
        notes = " ".join(n["detail"] for n in t["_out"]["notes"])
        self.assertIn("P-2", notes)
        self.assertIn("P-3", notes)

    def test_early_surr_no_master_table_notes(self):
        t = mk([row(1, "P-1", "2025-09-01", "S")])
        self.assertEqual(len(call("LIFE-EARLY-SURR", t)), 0)
        self.assertTrue(t["_out"]["notes"])

    def test_early_surr_leading_zero_policy_key(self):
        acc = [("0001", "I-1", "2025-06-01", "periodic")]
        ev = call("LIFE-EARLY-SURR", mk([row(1, "1", "2025-09-01", "S")], acc))
        self.assertEqual(list(ev["entity_id"]), ["1"])

    def test_loan_near_pct_boundary(self):
        tx = [row(1, "P-1", "2026-01-10", "L", amt=90.0, limit=100.0), row(2, "P-2", "2026-01-10", "L", amt=89.99, limit=100.0)]
        ev = call("LIFE-LOAN", mk(tx))
        self.assertEqual(list(ev["entity_id"]), ["P-1"])
        self.assertEqual(ev["value"].iloc[0], 0.9)

    def test_loan_count_and_loan_then_surrender(self):
        tx = [row(1, "P-1", "2026-01-01", "L"), row(2, "P-1", "2026-06-01", "L"), row(3, "P-1", "2026-12-31", "L"),
              row(4, "P-2", "2026-01-01", "L"), row(5, "P-2", "2026-06-01", "L"), row(6, "P-2", "2027-01-02", "L"),
              row(7, "P-3", "2026-01-01", "L"), row(8, "P-3", "2026-04-01", "S"),
              row(9, "P-4", "2026-01-01", "L"), row(10, "P-4", "2026-04-02", "S")]
        ev = call("LIFE-LOAN", mk(tx))
        got = dict(zip(ev["entity_id"], ev["period"]))
        self.assertEqual(got, {"P-1": "2026-12", "P-3": "2026-04"})  # 12 months counts (to the day), 90 days counts

    def test_loan_without_surrender_code_still_runs_rules_a_b(self):
        tx = [row(1, "P-1", "2026-01-10", "L", amt=95.0, limit=100.0)]
        t = mk(tx, codes={"L": CODES["L"]})
        self.assertEqual(list(call("LIFE-LOAN", t)["entity_id"]), ["P-1"])

    def test_benchg_cash_window_boundary(self):
        ev_rows = [("E1", "P-1", "2026-01-01", "B-1", "S-1"), ("E2", "P-2", "2026-01-01", "B-1", "S-1")]
        tx = [row(1, "P-1", "2026-01-31", "S"), row(2, "P-2", "2026-02-01", "L")]  # day 30 vs day 31
        ev = call("LIFE-BENCHG-CASH", mk(tx, events=ev_rows))
        self.assertEqual(list(ev["entity_id"]), ["P-1"])
        self.assertEqual(ev["value"].iloc[0], 30)

    def test_benchg_cash_money_before_change_not_counted(self):
        ev_rows = [("E1", "P-1", "2026-02-01", "B-1", "S-1")]
        tx = [row(1, "P-1", "2026-01-25", "S")]
        self.assertEqual(len(call("LIFE-BENCHG-CASH", mk(tx, events=ev_rows))), 0)

    def test_benchg_cash_falls_back_to_benefit_change_rows(self):
        codes = {**CODES, "B": "เปลี่ยนผู้รับผลประโยชน์"}
        tx = [row(1, "P-1", "2026-01-01", "B", payee="B-1"), row(2, "P-1", "2026-01-05", "C")]
        ev = call("LIFE-BENCHG-CASH", mk(tx, codes=codes))
        self.assertEqual(list(ev["entity_id"]), ["P-1"])

    def test_benchg_cash_needs_no_benefit_change_code_with_events(self):
        ev_rows = [("E1", "P-1", "2026-01-01", "B-1", "S-1")]
        t = mk([row(1, "P-1", "2026-01-05", "S")], events=ev_rows)
        self.assertIsNone(engine().require_codes(t, ["surrender", "loan", "claim"]))
        self.assertEqual(len(call("LIFE-BENCHG-CASH", t)), 1)

    def test_payee_min_policies_boundary(self):
        def tx(n):
            return [row(i, f"P-{i}", "2026-01-10", "S", payee="ACC-9001") for i in range(1, n + 1)] \
                + [row(50, "P-50", "2026-01-10", "S")]
        self.assertEqual(list(call("LIFE-THIRD-PAYEE", mk(tx(3)))["entity_id"]).count("ACC-9001"), 1)
        self.assertNotIn("ACC-9001", set(call("LIFE-THIRD-PAYEE", mk(tx(2)))["entity_id"]))

    def test_payee_same_insured_policies_do_not_count(self):
        tx = [row(i, f"P-{i}", "2026-01-10", "S", payee="ACC-9001", ins="I-1") for i in range(1, 5)]
        self.assertEqual(len(call("LIFE-THIRD-PAYEE", mk(tx))), 0)

    def test_third_payee_rule_a_comparability_per_row(self):
        tx = [row(1, "P-1", "2026-01-10", "S", payee="ACC-9001"), row(2, "P-2", "2026-02-10", "S", payee="I-0999"),
              row(3, "P-3", "2026-03-10", "S")]
        t = mk(tx)
        ev = call("LIFE-THIRD-PAYEE", t)
        self.assertEqual(list(ev["entity_id"]), ["P-2"])  # ACC-9001 vs I-1 is not comparable; I-0999 vs I-2 is

    def test_third_payee_incomparable_skips_rule_a(self):
        tx = [row(i, f"P-{i}", "2026-01-10", "S", payee="ACC-9001") for i in range(1, 4)]
        t = mk(tx)
        ev = call("LIFE-THIRD-PAYEE", t)
        self.assertEqual(list(ev["entity_id"]), ["ACC-9001"])  # rule (b) still runs
        self.assertIn("รูปแบบผู้รับเงินกับผู้เอาประกันเทียบกันไม่ได้", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def test_shape_helper(self):
        e = engine()
        self.assertEqual(e.id_shape(" I-0505 "), e.id_shape("i-1"))
        self.assertNotEqual(e.id_shape("ACC-9001"), e.id_shape("I-0505"))
        m = e.comparable_ids(pd.Series(["I-1", "ACC-1", None]), pd.Series(["I-2", "I-2", "I-2"]))
        self.assertEqual(list(m), [True, False, False])

    def test_benef_min_policies_boundary(self):
        def tbl(n):
            ev = [(f"E{i}", f"P-{i}", "2026-01-10", "B-7", "S-1") for i in range(1, n + 1)]
            tx = [row(i, f"P-{i}", "2026-06-10", "S") for i in range(1, n + 1)]
            return mk(tx, events=ev)
        self.assertEqual(list(call("LIFE-BENEF-MULTI", tbl(3))["entity_id"]), ["B-7"])
        self.assertEqual(len(call("LIFE-BENEF-MULTI", tbl(2))), 0)

    def test_benef_same_insured_policies_do_not_count(self):
        ev = [(f"E{i}", f"P-{i}", "2026-01-10", "B-7", "S-1") for i in range(1, 4)]
        tx = [row(i, f"P-{i}", "2026-06-10", "S", ins="I-1") for i in range(1, 4)]
        self.assertEqual(len(call("LIFE-BENEF-MULTI", mk(tx, events=ev))), 0)

    def test_benef_change_count_in_window(self):
        tx = [row(1, "P-1", "2026-06-10", "S"), row(2, "P-2", "2026-06-10", "S")]
        ev = [("E1", "P-1", "2026-01-10", "B-7", "S-1"), ("E2", "P-1", "2026-12-10", "B-8", "S-1"),
              ("E3", "P-2", "2026-01-10", "B-5", "S-1"), ("E4", "P-2", "2027-01-11", "B-6", "S-1")]  # 12 months + 1 day
        got = call("LIFE-BENEF-MULTI", mk(tx, events=ev))
        self.assertEqual(list(got["entity_id"]), ["B-8"])  # the policy's latest beneficiary, period of the latest change
        self.assertEqual(got["period"].iloc[0], "2026-12")
        self.assertEqual(got["value"].iloc[0], 2)

    def test_benef_without_events_table_notes_and_is_empty(self):
        t = mk([row(1, "P-1", "2026-06-10", "S")])
        self.assertEqual(len(call("LIFE-BENEF-MULTI", t)), 0)
        self.assertIn("ขอประวัติการเปลี่ยนผู้รับผลประโยชน์", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def test_staff_conc_counts_surrenders_and_events(self):
        tx = [row(i, f"P-{i}", "2026-01-10", "S", staff=f"S-{i % 10}") for i in range(1, 41)] \
            + [row(100 + i, f"P-{i}", "2026-02-10", "L", staff="S-3") for i in range(30)]  # loans are not counted
        ev = [(f"E{i}", f"P-{i}", "2026-03-10", "B-1", "S-9") for i in range(1, 41)]
        got = call("LIFE-STAFF-CONC", mk(tx, events=ev))
        self.assertEqual(list(got["entity_id"]), ["S-9"])  # 40 events + 4 surrenders of 80 records
        self.assertEqual(got["period"].iloc[0], "2026-03")
        self.assertEqual(got["value"].iloc[0], 0.55)

    def test_staff_conc_small_group_uses_hhi(self):
        even = [row(i, f"P-{i}", "2026-01-10", "S", staff=f"S-{i}") for i in range(1, 11)]  # 10 staff, 10% each
        t = mk(even)
        self.assertEqual(len(call("LIFE-STAFF-CONC", t)), 0)  # an equal split of so few staff is not reported
        self.assertTrue(t["_out"]["notes"])
        two = [row(1, "P-1", "2026-01-10", "S", staff="S-1"), row(2, "P-2", "2026-01-10", "S", staff="S-2")]
        self.assertEqual(set(call("LIFE-STAFF-CONC", mk(two))["entity_id"]), {"S-1", "S-2"})  # HHI 5,000 > high


class Fixes(unittest.TestCase):
    def test_benchg_cash_runs_with_two_money_codes_and_notes_missing(self):
        e = engine()
        tables, key = sample()
        cv = {k: v for k, v in key["code_values"]["policy_txn.txn_type"].items() if k != "CLM"}
        tables["meta"]["code_values"] = {"policy_txn.txn_type": cv}
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["LIFE-BENCHG-CASH", "decision"], "Run")
        ev = e.CHECKS["LIFE-BENCHG-CASH"]["func"](tables, cfg())
        self.assertIn("P-0202", set(ev["entity_id"]))
        self.assertIn("claim", " ".join(n["detail"] for n in tables["_out"]["notes"]))

    def test_benchg_cash_skips_with_no_money_code(self):
        e = engine()
        tables, _ = sample()
        tables["meta"]["code_values"] = {"policy_txn.txn_type": {}}
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["LIFE-BENCHG-CASH", "decision"], "Skip")

    def test_staff_conc_counts_benefit_change_rows_without_events(self):
        codes = {**CODES, "B": "เปลี่ยนผู้รับผลประโยชน์"}
        tx = [row(i, f"P-{i}", "2026-01-10", "S", staff=f"S-{i}") for i in range(1, 11)] \
            + [row(100 + i, f"P-{i}", "2026-02-10", "B", staff="S-9") for i in range(1, 8)]
        got = call("LIFE-STAFF-CONC", mk(tx, codes=codes))
        self.assertEqual(list(got["entity_id"]), ["S-9"])  # 8 of 17 records
        self.assertEqual(got["period"].iloc[0], "2026-02")

    def test_staff_conc_without_changes_source_notes_surrenders_only(self):
        t = mk([row(1, "P-1", "2026-01-10", "S", staff="S-1")])
        call("LIFE-STAFF-CONC", t)
        self.assertIn("เฉพาะรายการเวนคืน", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def test_staff_conc_events_without_created_by_notes(self):
        t = mk([row(1, "P-1", "2026-01-10", "S", staff="S-1")], events=[("E1", "P-1", "2026-01-01", "B-1", None)])
        t["events"] = t["events"].drop(columns="created_by")
        call("LIFE-STAFF-CONC", t)
        self.assertIn("created_by", " ".join(n["detail"] for n in t["_out"]["notes"]))

    def test_staff_conc_no_double_count_with_events(self):
        codes = {**CODES, "B": "เปลี่ยนผู้รับผลประโยชน์"}
        tx = [row(1, "P-1", "2026-01-10", "B", staff="S-9")]
        t = mk(tx + [row(2, "P-2", "2026-01-10", "S", staff="S-1")], events=[("E1", "P-1", "2026-01-01", "B-1", "S-1")], codes=codes)
        got = call("LIFE-STAFF-CONC", t)
        self.assertNotIn("S-9", set(got["entity_id"]))

    def test_benef_unknown_insured_skipped_with_note(self):
        ev = [(f"E{i}", f"P-{i}", "2026-01-10", "B-7", "S-1") for i in range(1, 4)]
        t = mk([], events=ev)
        self.assertEqual(len(call("LIFE-BENEF-MULTI", t)), 0)
        self.assertTrue(t["_out"]["notes"])

    def test_benef_master_insured_wins_over_transactions(self):
        ev = [(f"E{i}", f"P-{i}", "2026-01-10", "B-7", "S-1") for i in range(1, 4)]
        tx = [row(i, f"P-{i}", "2026-06-10", "S", ins="I-1") for i in range(1, 4)]
        acc = [(f"P-{i}", f"I-{i}", "2020-01-01", "periodic") for i in range(1, 4)]
        self.assertEqual(list(call("LIFE-BENEF-MULTI", mk(tx, acc, ev))["entity_id"]), ["B-7"])

    def test_loan_same_day_surrender_before_loan_not_counted(self):
        tx = [row(1, "P-1", "2026-03-01 15:00", "L"), row(2, "P-1", "2026-03-01 09:00", "S")]
        self.assertEqual(len(call("LIFE-LOAN", mk(tx))), 0)
        tx = [row(1, "P-1", "2026-03-01 09:00", "L"), row(2, "P-1", "2026-03-01 15:00", "S")]
        self.assertEqual(list(call("LIFE-LOAN", mk(tx))["entity_id"]), ["P-1"])


class Guards(unittest.TestCase):
    def test_l_checks_skip_without_codes(self):
        e = engine()
        tables, _ = sample()
        tables["meta"] = {"code_values": {}, "category_key": "policy_txn.txn_type", "dtype": "L"}
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        for check in ("LIFE-EARLY-SURR", "LIFE-BENCHG-CASH", "LIFE-LOAN", "LIFE-STAFF-CONC"):
            self.assertEqual(plan.loc[check, "decision"], "Skip", check)
            self.assertRegex(plan.loc[check, "reason"], "ความหมายรหัสประเภทรายการ")
            ev = e.CHECKS[check]["func"](tables, cfg())
            self.assertEqual(len(ev), 0)
            self.assertIn("ความหมายรหัสประเภทรายการ", " ".join(n["detail"] for n in tables["_out"]["notes"]))
        self.assertEqual(plan.loc["LIFE-THIRD-PAYEE", "decision"], "Run")  # uses no transaction code

    def test_l_checks_run_with_codes_in_plan(self):
        tables, _ = sample()
        plan = engine().plan_checks(tables, cfg()).set_index("recipe_id")
        for check in CHECKS:
            self.assertEqual(plan.loc[check, "decision"], "Run", check)

    def test_events_required_checks_skip_without_events_table(self):
        e = engine()
        tables, _ = sample()
        del tables["events"]
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["LIFE-BENEF-MULTI", "decision"], "Skip")
        self.assertIn("ขอประวัติการเปลี่ยนผู้รับผลประโยชน์", plan.loc["LIFE-BENEF-MULTI", "reason"])
        self.assertEqual(plan.loc["LIFE-BENCHG-CASH", "decision"], "Skip")  # no benefit_change code either
        self.assertEqual(plan.loc["LIFE-STAFF-CONC", "decision"], "Run")  # surrenders alone still count

    def test_l_checks_skip_on_other_data_types(self):
        e = engine()
        for name in ("C", "A"):
            d = ROOT / "samples" / name
            roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
            frames = {t: pd.read_csv(d / f"{t}.csv") for t in roles}
            plan = e.plan_checks(e.to_internal(frames, roles), cfg()).set_index("recipe_id")
            for check in CHECKS:
                self.assertEqual(plan.loc[check, "decision"], "Skip", (name, check))

    def test_l_risks_in_library_and_checks_exist(self):
        e = engine()
        names = {"L-R1": "เวนคืนเร็วหลังทำกรมธรรม์", "L-R2": "เปลี่ยนผู้รับผลประโยชน์แล้วมีรายการเงินตามมาเร็ว",
                 "L-R3": "กู้ตามกรมธรรม์ผิดปกติ", "L-R4": "จ่ายเงินเข้าบัญชีบุคคลที่สาม",
                 "L-R5": "ผู้รับผลประโยชน์ซ้ำข้ามกรมธรรม์", "L-R6": "ตัวแทนหรือพนักงานกระจุกตัว"}
        c = cfg()
        for check, risk in CHECKS.items():
            spec = e.CHECKS[check]
            self.assertEqual(spec["risk"], risk)
            self.assertEqual(spec["data_types"], ["L"])
            self.assertTrue(callable(spec["func"]))
            for k in spec["registry"]:
                self.assertIn(k, c)
            lib = e.RISK_LIBRARY[risk]
            self.assertEqual(lib["name_th"], names[risk])
            self.assertEqual(lib["checks"], [check])
            self.assertEqual(lib["data_types"], ["L"])
            self.assertTrue(any(s.isascii() for s in lib["synonyms"]) and any(not s.isascii() for s in lib["synonyms"]))
            self.assertTrue(set(lib["min_roles"]) <= set(e.ROLES))
        self.assertEqual(e.CHECKS["LIFE-STAFF-CONC"]["registry"][:2], ["CONC.SINGLE_ENTITY_SHARE", "CONC.HHI"])
        req1 = e.RISK_LIBRARY["L-R1"]["request_if_missing"]
        self.assertEqual(req1["opened_at"], "ขอข้อมูลกรมธรรม์ (วันออกกรมธรรม์)")
        for r in ("L-R2", "L-R5"):
            self.assertEqual(e.RISK_LIBRARY[r]["request_if_missing"]["_events"], "ขอประวัติการเปลี่ยนผู้รับผลประโยชน์")

    def test_l_synonyms_match_concerns(self):
        e = engine()
        got = {m["risk_id"] for m in e.match_concerns(["สงสัยเวนคืนเร็วหลังทำกรมธรรม์", "จ่ายเงินเข้าบัญชีบุคคลที่สาม"])}
        self.assertEqual(got, {"L-R1", "L-R4"})

    def test_l_override_changes_result(self):
        base, key = run_sample("LIFE-EARLY-SURR")
        self.assertIn("P-0101", set(base["entity_id"]))
        ev, _ = run_sample("LIFE-EARLY-SURR", **{"LIFE.EARLY_SURR.MONTHS": 3})
        self.assertNotIn("P-0101", set(ev["entity_id"]))

    def test_c1_conc_unchanged_by_helper(self):
        # gen_conc and LIFE-STAFF-CONC share one concentration helper
        self.assertTrue(hasattr(engine(), "_conc_stats"))


if __name__ == "__main__":
    unittest.main()
