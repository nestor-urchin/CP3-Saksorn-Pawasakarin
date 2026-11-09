"""Tests for the certified checks of AIDA C1 task 5 (CHECKS registry, new C/A checks, AIDA-14 v1.2).

Each check runs on the answer-key samples (C = loan payments, A = accounts payable) through the role adapter.
Conventions used here come from each key's "conventions": DUP-PAY names the contract in C and the vendor in A
(the finding itself is keyed by invoice number later, the check reports the entity); a pattern over several
periods carries the latest period of the entity's contributing rows.
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
REGISTRY = ROOT / "knowledge" / "AIDA-14-configuration-registry.md"
NEW = ["GEN-CONC", "GEN-PERIOD-END", "DUP-PAY", "SPLIT-LIMIT", "FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT",
       "SOD-SAME-USER", "DUE-NEAR", "PAYER-MULTI"]
_CACHE = {}


def cfg():
    e = engine()
    return {**e.load_registry(REGISTRY), "_RUN": {"run_id": "T", "data_ref": "chat:test.csv#|sha256:x"}}


def dataset(name):
    if name not in _CACHE:
        d = ROOT / "samples" / name
        frames = {t: pd.read_csv(d / f"{t}.csv") for t in (("payments", "contracts") if name == "C" else ("payments",))}
        roles = json.loads((d / "variants" / "roles_en.json").read_text(encoding="utf-8"))
        key = json.loads((d / "answer_key.json").read_text(encoding="utf-8"))
        _CACHE[name] = (engine().to_internal(frames, roles), key)
    tables, key = _CACHE[name]
    return {k: v.copy() for k, v in tables.items()}, key


def run(check, name):
    tables, key = dataset(name)
    return engine().CHECKS[check]["func"](tables, cfg()), key


def can_run(check, name):
    tables, _ = dataset(name)
    plan = engine().plan_checks(tables, cfg()).set_index("recipe_id")
    return plan.loc[check, "decision"] == "Run"


def make_case(check):
    """Test methods for one check: the planted ids are found, nothing else is, on every sample that can run it."""
    def planted(self):
        seen = 0
        for name in ("C", "A"):
            if not can_run(check, name):
                continue
            ev, key = run(check, name)
            want = set(key["recipes"].get(check, []))
            seen += 1
            self.assertTrue(want <= set(ev["entity_id"]), f"{check} {name}: {want} not in {set(ev['entity_id'])}")
        self.assertGreater(seen, 0)

    def no_fp(self):
        for name in ("C", "A"):
            if not can_run(check, name):
                continue
            ev, key = run(check, name)
            want = set(key["recipes"].get(check, []))
            self.assertEqual(set(ev["entity_id"]) - want, set(), f"{check} {name}: unexpected entities")
    return planted, no_fp


class ChecksCA(unittest.TestCase):
    def test_cfg_and_th_agree(self):
        c = cfg()
        for k in ("DUP.WINDOW_DAYS", "SPLIT.WINDOW_DAYS", "SPLIT.MIN_TX", "DUE.NEAR_DAYS", "DUE.MIN_SHARE",
                  "DUE.MIN_PERIODS", "PAYER.MIN_CONTRACTS", "FOR.BENFORD.MIN_N", "FOR.ROUND.UNIT",
                  "FOR.REPEAT.MIN_COUNT", "CONC.SINGLE_ENTITY_SHARE"):
            self.assertEqual(sc.TH[k], c[k], k)
        self.assertEqual(sc.TH["SPLIT.BAND"], (c["FOR.THRESHOLD_AVOID.BAND"]["low"], c["FOR.THRESHOLD_AVOID.BAND"]["high"]))
        self.assertEqual(sc.TH["FOR.BENFORD.MAD_OK"], c["FOR.BENFORD.MAD_1ST"]["acceptable"])
        self.assertEqual(sc.TH["FOR.BENFORD.MAD_BAD"], c["FOR.BENFORD.MAD_1ST"]["marginal"])
        self.assertEqual(c["REGISTRY.VERSION"], engine().REGISTRY_VERSION)

    def test_checks_registry_keys_exist(self):
        e, c = engine(), cfg()
        for cid, spec in e.CHECKS.items():
            for k in spec["registry"]:
                self.assertIn(k, c, f"{cid}: {k}")
            for r in spec["requires"]:
                self.assertIn(r, e.ROLES, f"{cid}: {r}")
            for f in ("func", "risk", "skill_family", "requires", "registry", "data_types"):
                self.assertIn(f, spec, f"{cid}: {f}")
            self.assertTrue(callable(spec["func"]))
        for cid in NEW:
            self.assertIn(cid, e.CHECKS)

    def test_checks_cover_b1_cards(self):
        e = engine()
        for cid in e.GATE_CARDS:
            if cid == "FLOW-TRACE":  # on demand trail, not a (tables, cfg) check
                continue
            self.assertIn(cid, e.CHECKS)
        self.assertIs(e.CHECKS["STAT-MAD"]["func"], e.stat_mad)
        self.assertEqual(e.CHECKS["MULE-PATTERN"]["risk"], "R2")
        self.assertEqual(e.CHECKS["CPTY-PROFILE"]["risk"], "R4")
        self.assertIn("G-R1", e.CHECKS["STAT-MAD"]["risk_alt"])
        self.assertIn("G-R3", e.CHECKS["TEMP-OFFHOURS"]["risk_alt"])
        # the four general checks read only entity / date / amount (no counterparty) and apply to every data type
        for cid in ("STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS"):
            self.assertNotIn("counterparty", e.CHECKS[cid]["requires"])
            self.assertEqual(set(e.CHECKS[cid]["data_types"]), set(e.DATA_TYPES))
        self.assertEqual(set(e.CHECKS["STAT-MAD"]["requires"]), {"record_id", "date", "entity", "amount"})
        self.assertEqual(set(e.CHECKS["TEMP-OFFHOURS"]["requires"]), {"record_id", "date", "entity"})

    def test_every_runnable_check_flags_only_answer_key_ids(self):
        """Normal rows trip no certified check: on C and A each runnable check flags only ids named in the key."""
        e = engine()
        for name in ("C", "A"):
            tables, key = dataset(name)
            plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
            ran = 0
            for cid, spec in e.CHECKS.items():
                if plan.loc[cid, "decision"] != "Run":
                    continue
                ran += 1
                ev = spec["func"]({k: v.copy() for k, v in tables.items()}, cfg())
                flagged = set(ev["entity_id"].astype(str)) if len(ev) else set()
                self.assertLessEqual(flagged, set(key["recipes"].get(cid, [])), (name, cid, sorted(flagged)[:8]))
            self.assertGreaterEqual(ran, 10)

    def test_offhours_needs_time_of_day(self):
        tables, _ = dataset("A")  # dates only: every time is 00:00
        self.assertEqual(len(engine().CHECKS["TEMP-OFFHOURS"]["func"](tables, cfg())), 0)

    def test_checks_skip_reason_names_missing_roles(self):
        e = engine()
        tables, _ = dataset("A")
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        # A has no contract / due_date / counterparty role
        for cid, roles in (("DUE-NEAR", ["contract", "due_date"]), ("PAYER-MULTI", ["counterparty", "contract"])):
            row = plan.loc[cid]
            self.assertEqual(row["decision"], "Skip")
            for r in roles:
                self.assertIn(r, row["reason"])
            self.assertRegex(row["reason"], r"[ก-๙]")
        self.assertEqual(plan.loc["GEN-CONC", "decision"], "Run")
        tables, _ = dataset("C")
        plan = e.plan_checks(tables, cfg()).set_index("recipe_id")
        self.assertEqual(plan.loc["SOD-SAME-USER", "decision"], "Skip")
        self.assertIn("created_by", plan.loc["SOD-SAME-USER", "reason"])
        self.assertIn("approved_by", plan.loc["SOD-SAME-USER", "reason"])
        self.assertEqual(plan.loc["SPLIT-LIMIT", "decision"], "Skip")
        self.assertIn("limit", plan.loc["SPLIT-LIMIT", "reason"])
        self.assertEqual(plan.loc["DUE-NEAR", "decision"], "Run")

    def test_evidence_shape(self):
        e = engine()
        for check, name in (("DUP-PAY", "A"), ("GEN-CONC", "A"), ("DUE-NEAR", "C"), ("FOR-REPEAT", "C")):
            ev, _ = run(check, name)
            self.assertEqual(list(ev.columns), e.EVIDENCE_COLUMNS + ["roles_used"])
        ev, _ = run("SOD-SAME-USER", "A")
        row = ev.iloc[0]
        self.assertEqual(row["recipe_id"], "SOD-SAME-USER")
        self.assertEqual(row["risk"], "A-R3")
        self.assertEqual(row["registry_version"], e.REGISTRY_VERSION)
        self.assertIn("created_by", row["roles_used"])
        self.assertTrue(all(isinstance(r, list) and r for r in ev["record_refs"]))
        self.assertRegex(row["explanation"], r"[ก-๙]")
        for bad in ("บัญชีม้า", "ทุจริต"):
            self.assertNotIn(bad, row["explanation"])

    def test_empty_result_keeps_columns(self):
        e = engine()
        tables, _ = dataset("C")
        ev = e.CHECKS["GEN-CONC"]["func"](tables, cfg())
        self.assertEqual(list(ev.columns), e.EVIDENCE_COLUMNS + ["roles_used"])
        self.assertEqual(len(ev), 0)

    def test_periods_and_risks(self):
        want = {("C", "PAYER-MULTI"): ("2026-08", "C-R1"), ("C", "DUE-NEAR"): ("2026-08", "C-R2"),
                ("C", "DUP-PAY"): ("2026-05", "C-R3"), ("A", "DUP-PAY"): ("2026-04", "A-R1"),
                ("A", "SPLIT-LIMIT"): ("2026-06", "A-R2"), ("A", "SOD-SAME-USER"): ("2026-08", "A-R3"),
                ("A", "GEN-CONC"): ("2026-08", "A-R4"), ("A", "FOR-BENFORD"): ("2026-08", "G-R4"),
                ("A", "FOR-ROUND"): ("2026-08", "G-R4"), ("A", "GEN-PERIOD-END"): ("2026-08", "G-R2"),
                ("A", "FOR-REPEAT"): ("2026-06", "G-R4")}
        for (name, check), (period, risk) in want.items():
            ev, key = run(check, name)
            ids = set(key["recipes"][check])
            sub = ev[ev["entity_id"].isin(ids)]
            self.assertEqual(set(sub["period"]), {period}, (name, check))
            self.assertEqual(set(sub["risk"]), {risk}, (name, check))

    def test_dup_pay_requires_same_document_no(self):
        ev, _ = run("DUP-PAY", "A")
        self.assertNotIn("V-045", set(ev["entity_id"]))
        self.assertEqual(len(ev), 1)
        self.assertIn("INV-7781", ev.iloc[0]["explanation"])
        self.assertEqual(len(ev.iloc[0]["record_refs"]), 2)
        # without the document_no role the same rows of V-045 (same amount within the window) are duplicates
        tables, _ = dataset("A")
        tables["transactions"] = tables["transactions"].drop(columns="document_no")
        ev2 = engine().CHECKS["DUP-PAY"]["func"](tables, cfg())
        self.assertIn("V-045", set(ev2["entity_id"]))

    def test_split_limit_details(self):
        ev, _ = run("SPLIT-LIMIT", "A")
        self.assertEqual(list(ev["entity_id"]), ["V-045"])
        self.assertEqual(ev.iloc[0]["value"], 144000.0)
        self.assertEqual(len(ev.iloc[0]["record_refs"]), 3)

    def test_for_round_share_based(self):
        ev, _ = run("FOR-ROUND", "A")
        self.assertEqual(list(ev["entity_id"]), ["V-120"])
        self.assertEqual(ev.iloc[0]["value"], 1.0)

    def test_for_repeat_same_period_only(self):
        ev, _ = run("FOR-REPEAT", "C")
        self.assertEqual(len(ev), 0)  # identical instalments repeat once per month, never 3 times in one month
        ev, _ = run("FOR-REPEAT", "A")
        self.assertEqual(list(ev["entity_id"]), ["V-045"])
        self.assertEqual(ev.iloc[0]["value"], 3)

    def test_gen_conc_uses_amount_share(self):
        ev, _ = run("GEN-CONC", "A")
        self.assertEqual(list(ev["entity_id"]), ["V-077"])
        self.assertGreaterEqual(ev.iloc[0]["value"], cfg()["CONC.SINGLE_ENTITY_SHARE"])

    def test_run_with_overrides_changes_result(self):
        e = engine()
        tables, _ = dataset("A")
        c = cfg()
        c["CONC.SINGLE_ENTITY_SHARE"] = 0.9
        self.assertEqual(len(e.CHECKS["GEN-CONC"]["func"](tables, c)), 0)

    def test_b1_checks_still_run_via_registry(self):
        e = engine()
        t = pd.read_csv(ROOT / "samples" / "transactions.csv")
        tables = e.to_internal({"t": t}, {"t": {"tx_id": "record_id", "ts": "date", "amount": "amount",
                                               "from_acct": "entity", "to_acct": "counterparty"}})
        ev = e.CHECKS["STAT-MAD"]["func"](tables, cfg())
        self.assertEqual(list(ev.columns), e.EVIDENCE_COLUMNS)
        self.assertGreater(len(ev), 0)


for _c in NEW:
    _p, _n = make_case(_c)
    setattr(ChecksCA, "test_%s_finds_planted" % _c.lower().replace("-", "_"), _p)
    setattr(ChecksCA, "test_%s_no_false_positive" % _c.lower().replace("-", "_"), _n)

if __name__ == "__main__":
    unittest.main()
