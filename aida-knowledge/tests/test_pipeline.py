"""Tests for the pipeline recipe cards in AIDA-19 (PREP-MAP, PROF-PROFILE, GATE-CAPABILITY,
UNIFY-FINDINGS, ASSESS-CMP, SELECT-AUTO-TRACE, LOG-RUN).

Cards are loaded with load_recipes exactly as Copilot's Code Interpreter would run them
(helpers from test_recipes). The whole-chain test starts from the raw sample CSVs read as
text, so PREP-MAP's type coercion is exercised too.
"""
import unittest

import pandas as pd

import test_recipes as tr
from test_recipes import CFG, SAMPLES, answer_key

R = tr.recipes
ANALYSIS_CARDS = ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE",
                  "NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "MULE-PATTERN", "MULE-CROSS-TX",
                  "MULE-NETWORK", "CPTY-PROFILE", "CPTY-NEW-LARGE", "FLOW-TRACE", "FLOW-LAYERING"]
FINDING_COLUMNS = ["finding_id", "entity_type", "entity_id", "risk", "period", "evidence_ids",
                   "skill_families", "exposure", "confidence", "materiality", "priority",
                   "review_status", "review_reason", "network_id"]
RUN_LOG_COLUMNS = ["run_id", "timestamp", "stage", "status", "detail", "recipe_id",
                   "recipe_version", "registry_version", "pack_version", "input_sha256"]
ACCOUNT_CARDS = ["stat_mad", "beh_velocity", "beh_spike", "temp_offhours", "net_cycle",
                 "net_funnel", "mule_dwell", "mule_new_acct", "cpty_profile", "cpty_new_large",
                 "flow_layering"]
IDENTITY = {"transactions": {}, "accounts": {}}


def _raw_tx(rows, cols=("tx_id", "ts", "from_acct", "to_acct", "amount", "channel")):
    return pd.DataFrame(rows, columns=list(cols))


def _prep(rows, **kw):
    return R()["prep_map"]({"transactions": _raw_tx(rows, **kw)}, IDENTITY, CFG)


def _ev(recipe_id, family, risk, rows, etype="account", data_ref=None):
    """Hand-built evidence rows: rows = [(entity_id, period, record_refs), ...]."""
    found = pd.DataFrame([{"entity_type": etype, "entity_id": a, "period": p, "metric": "m",
                           "value": 1, "threshold": 1, "explanation": "x", "record_refs": refs}
                          for a, p, refs in rows])
    cfg = CFG if data_ref is None else {**CFG, "_RUN": {**CFG["_RUN"], "data_ref": data_ref}}
    return tr.helper("evidence_rows")(recipe_id, "1.0", family, risk, "K", found, cfg)


_CHAIN = {}


def sample_chain():
    """Whole pipeline on the raw sample CSVs: PREP-MAP -> PROF-PROFILE -> GATE-CAPABILITY ->
    account-level cards -> MULE-PATTERN -> MULE-CROSS-TX -> MULE-NETWORK -> UNIFY -> ASSESS."""
    if not _CHAIN:
        raw = {"transactions": pd.read_csv(SAMPLES / "transactions.csv", dtype=str),
               "accounts": pd.read_csv(SAMPLES / "accounts.csv", dtype=str)}
        tables = R()["prep_map"](raw, IDENTITY, CFG)
        profile, status = R()["prof_profile"](tables, CFG)
        plan = R()["gate_capability"](tables, CFG)
        tables["_out"] = {}
        ev = pd.concat([R()[f](tables, CFG) for f in ACCOUNT_CARDS], ignore_index=True)
        for f in ("mule_pattern", "mule_cross_tx", "mule_network"):
            tables["evidence"] = ev
            ev = pd.concat([ev, R()[f](tables, CFG)], ignore_index=True)
        nets = tables["_out"]["mule_networks"]
        findings = R()["unify_findings"](ev, CFG, nets)
        _CHAIN.update(tables=tables, profile=profile, status=status, plan=plan, evidence=ev,
                      networks=nets, findings=findings,
                      assessed=R()["assess_cmp"](findings, tables["transactions"], 1_000_000.0, CFG))
    return _CHAIN


# ---------------------------------------------------------------- PREP-MAP + PROF-PROFILE
class TestPrepProfile(unittest.TestCase):
    def test_prep_map_mixed_timestamps(self):
        epoch = pd.Timestamp("1899-12-30")
        raw = pd.DataFrame({
            "TxnNo": [1, 2, 3, 4, 5, 6, 7, 8],
            "When": ["2026-08-01 10:00:00", "2026-08-01T12:30:00+07:00", 46235.5, "46235.25",
                     pd.Timestamp("2026-08-02 09:00", tz="Asia/Bangkok"), "20260803",
                     "not a date", None],
            "Src": ["A"] * 8, "Dst": ["B"] * 8, "Amt": ["1,234.50", "10", 5, "x", 1, 2, 3, 4]})
        acc = pd.DataFrame({"id": ["A", "B"], "opened": ["2026-07-01", 46204]})
        mapping = {"transactions": {"TxnNo": "tx_id", "When": "ts", "Src": "from_acct",
                                    "Dst": "to_acct", "Amt": "amount"},
                   "accounts": {"id": "acct_id", "opened": "opened_at"}}
        t = R()["prep_map"]({"transactions": raw, "accounts": acc}, mapping, CFG)
        ts = t["transactions"]["ts"]
        self.assertTrue(pd.api.types.is_datetime64_dtype(ts))
        self.assertIsNone(getattr(ts.dt, "tz", None))
        self.assertEqual(list(ts[:6]), [pd.Timestamp("2026-08-01 10:00"),
                                        pd.Timestamp("2026-08-01 12:30"),  # wall-clock kept
                                        epoch + pd.Timedelta(days=46235.5),
                                        epoch + pd.Timedelta(days=46235.25),
                                        pd.Timestamp("2026-08-02 09:00"),
                                        pd.Timestamp("2026-08-03")])
        self.assertTrue(ts[6:].isna().all())
        self.assertEqual(t["_prep"]["unparsed_ts"], 2)
        self.assertEqual(list(t["transactions"]["tx_id"][:2]), ["1", "2"])
        amt = t["transactions"]["amount"]
        self.assertEqual(amt.dtype, float)
        self.assertEqual(amt[0], 1234.5)
        self.assertTrue(pd.isna(amt[3]))
        opened = t["accounts"]["opened_at"]
        self.assertEqual(list(opened), [pd.Timestamp("2026-07-01"), epoch + pd.Timedelta(days=46204)])
        # 2 of 8 timestamps unparsed (25 %) > 1 - GATE.COMPLETENESS.MIN -> STOP with a reason
        _, status = R()["prof_profile"](t, CFG)
        self.assertTrue(status.startswith("STOP: "), status)
        self.assertIn("ts", status)
        self.assertIn("GATE.COMPLETENESS.MIN", status)

    def test_prep_map_does_not_change_raw(self):
        raw = _raw_tx([("1", "2026-08-01", "A", "B", "10", "m")])
        R()["prep_map"]({"transactions": raw}, IDENTITY, CFG)
        self.assertEqual(raw["ts"].iloc[0], "2026-08-01")

    def test_profile_sample_ok(self):
        c = sample_chain()
        self.assertEqual(c["status"], "OK")
        self.assertEqual(list(c["profile"].columns), ["item", "value", "detail"])
        self.assertIn(len(c["tables"]["transactions"]), list(c["profile"]["value"]))

    def test_profile_duplicate_tx_id_stops(self):
        t = _prep([("T1", "2026-08-01 10:00", "A", "B", 10, "m"),
                   ("T1", "2026-08-01 11:00", "A", "C", 20, "m"),
                   ("T2", "2026-08-01 12:00", "B", "C", 30, "m")])
        profile, status = R()["prof_profile"](t, CFG)
        self.assertTrue(status.startswith("STOP: "), status)
        self.assertIn("T1", status)
        self.assertIn("ซ้ำ", status)
        row = profile[profile["item"].str.contains("tx_id ซ้ำ")].iloc[0]
        self.assertEqual(row["value"], 1)
        self.assertIn("T1", row["detail"])

    def test_profile_missing_tx_id_stops(self):
        t = _prep([("2026-08-01 10:00", "A", "B", 10)], cols=("ts", "from_acct", "to_acct", "amount"))
        _, status = R()["prof_profile"](t, CFG)
        self.assertTrue(status.startswith("STOP: "), status)
        self.assertIn("tx_id", status)
        self.assertIn("GATE.TRACE.REQUIRED", status)
        t = _prep([(None, "2026-08-01 10:00", "A", "B", 10, "m")])
        _, status = R()["prof_profile"](t, CFG)
        self.assertTrue(status.startswith("STOP: "), status)

    def test_self_and_nonpositive_excluded(self):
        rows = [("S1", "2026-08-01 10:00", "A", "A", 500, "m"),     # self-transfer
                ("Z1", "2026-08-01 11:00", "A", "B", 0, "m"),       # zero
                ("N1", "2026-08-01 12:00", "B", "A", -50, "m"),     # negative
                ("T1", "2026-08-02 10:00", "A", "B", 100, "m"),
                ("T2", "2026-08-02 11:00", "B", "C", 95, "m")]
        t = _prep(rows)
        self.assertEqual(t["_prep"]["excluded_self"], 1)
        self.assertEqual(t["_prep"]["excluded_nonpositive"], 2)
        profile, status = R()["prof_profile"](t, CFG)
        self.assertEqual(status, "OK")
        shown = dict(zip(profile["item"], profile["value"]))
        self.assertEqual(shown["รายการโอนเข้าบัญชีตัวเอง (ไม่นำไปวิเคราะห์)"], 1)
        self.assertEqual(shown["รายการยอด ≤ 0 (ไม่นำไปวิเคราะห์)"], 2)
        # excluded from flow, network and dwell analysis
        trail = R()["flow_trace"](t, CFG, "A", "forward")
        self.assertEqual(list(trail["tx_id"]), ["T1", "T2"])
        back = R()["flow_trace"](t, CFG, "A", "backward")
        self.assertTrue(back.empty)  # S1 and N1 are not followed
        self.assertTrue(R()["net_cycle"](t, CFG).empty)  # A -> B -> A only via N1 (negative)


# ---------------------------------------------------------------- GATE-CAPABILITY
class TestGate(unittest.TestCase):
    def test_gate_sample_all_run(self):
        plan = sample_chain()["plan"]
        self.assertEqual(list(plan.columns), ["recipe_id", "decision", "reason", "missing"])
        self.assertEqual(list(plan["recipe_id"]), ANALYSIS_CARDS)
        self.assertEqual(set(plan["decision"]), {"Run"}, plan[plan["decision"] != "Run"])
        self.assertTrue(plan["reason"].str.len().gt(0).all())
        reason = plan.set_index("recipe_id").loc["MULE-NEW-ACCT", "reason"]
        self.assertIn("basis=opened_at", reason)

    def test_gate_no_ts_skips_time_cards(self):
        t = _prep([(f"T{i}", f"A{i % 3}", f"B{i % 4}", 100 + i, "m") for i in range(40)],
                  cols=("tx_id", "from_acct", "to_acct", "amount", "channel"))
        plan = R()["gate_capability"](t, CFG).set_index("recipe_id")
        self.assertEqual(len(plan), len(ANALYSIS_CARDS))
        for rid in ["BEH-VELOCITY", "TEMP-OFFHOURS", "MULE-DWELL", "NET-CYCLE", "NET-FUNNEL",
                    "FLOW-TRACE", "FLOW-LAYERING", "CPTY-PROFILE", "CPTY-NEW-LARGE", "BEH-SPIKE",
                    "MULE-NEW-ACCT"]:
            self.assertEqual(plan.loc[rid, "decision"], "Skip", rid)
            self.assertIn("ts", plan.loc[rid, "reason"])
            self.assertIn("ts", plan.loc[rid, "missing"])
        self.assertTrue((plan["reason"].str.len() > 0).all())

    def test_gate_no_accounts_new_acct_first_seen(self):
        tables = {k: v for k, v in sample_chain()["tables"].items() if k != "accounts"}
        plan = R()["gate_capability"](tables, CFG).set_index("recipe_id")
        self.assertEqual(plan.loc["MULE-NEW-ACCT", "decision"], "Run")
        self.assertIn("basis=first_seen", plan.loc["MULE-NEW-ACCT", "reason"])

    def test_gate_short_history_skips_baseline_cards(self):
        # one month, 3 active days per account: no baseline can be built
        rows = [(f"T{i}", f"2026-08-0{1 + i % 3} 10:00", f"A{i % 5}", f"B{i % 7}", 100 + i, "m")
                for i in range(60)]
        plan = R()["gate_capability"](_prep(rows), CFG).set_index("recipe_id")
        for rid, key in [("BEH-VELOCITY", "BEH.BASELINE.MIN_PERIODS"),
                         ("BEH-SPIKE", "BEH.BASELINE.MIN_PERIODS"),
                         ("CPTY-PROFILE", "BEH.BASELINE.MIN_PERIODS"),
                         ("CPTY-NEW-LARGE", "1 เดือน"),
                         ("NET-FUNNEL", "NET.FUNNEL"),
                         ("MULE-NEW-ACCT", "MULE.NEW_ACCT_DAYS")]:
            self.assertEqual(plan.loc[rid, "decision"], "Skip", rid)
            self.assertIn(key, plan.loc[rid, "reason"], rid)
        self.assertEqual(plan.loc["STAT-MAD", "decision"], "Run")
        # only MULE-DWELL and TEMP-OFFHOURS of the 5 signal cards can run (< MULE.MIN_SIGNALS)
        for rid in ["MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK"]:
            self.assertEqual(plan.loc[rid, "decision"], "Skip", rid)
        self.assertIn("MULE.MIN_SIGNALS", plan.loc["MULE-PATTERN", "reason"])

    def test_gate_small_sample_skips_stat_mad(self):
        rows = [(f"T{i}", f"2026-08-0{1 + i % 3} 10:00", "A", "B", 100 + i, "m") for i in range(5)]
        plan = R()["gate_capability"](_prep(rows), CFG).set_index("recipe_id")
        self.assertEqual(plan.loc["STAT-MAD", "decision"], "Skip")
        self.assertIn("GATE.SAMPLE.MIN", plan.loc["STAT-MAD", "reason"])


# ---------------------------------------------------------------- UNIFY-FINDINGS
class TestUnify(unittest.TestCase):
    def test_unify_absorbs_r1_into_r2(self):
        ev = pd.concat([
            _ev("MULE-PATTERN", "5.10 Hybrid", "R2", [("A1", "2026-08", ["T1", "T2"])]),
            _ev("BEH-VELOCITY", "5.3 Behavioral", "R1", [("A1", "2026-08", ["T1"])]),
            _ev("MULE-DWELL", "5.4 Temporal", "R1", [("A1", "2026-08", ["T2"]),
                                                     ("A1", "2026-07", ["T0"])]),
            _ev("STAT-MAD", "5.1 Statistical", "R1", [("A1", "2026-08", ["T3"])]),
            _ev("NET-FUNNEL", "5.9 Network", "R1", [("B1", "2026-08", ["T4"])]),
        ], ignore_index=True)
        f = R()["unify_findings"](ev, CFG)
        self.assertEqual(list(f.columns[:len(FINDING_COLUMNS)]), FINDING_COLUMNS)
        got = {(r.entity_id, r.risk, r.period): r for r in f.itertuples()}
        self.assertEqual(set(got), {("A1", "R2", "2026-08"), ("A1", "R1", "2026-08"),
                                    ("A1", "R1", "2026-07"), ("B1", "R1", "2026-08")})
        r2 = got[("A1", "R2", "2026-08")]
        self.assertEqual(sorted(r2.evidence_ids), ["BEH-VELOCITY-T-1", "MULE-DWELL-T-1",
                                                   "MULE-PATTERN-T-1"])
        self.assertEqual(r2.skill_families, ["5.10 Hybrid", "5.3 Behavioral", "5.4 Temporal"])
        self.assertEqual(got[("A1", "R1", "2026-08")].evidence_ids, ["STAT-MAD-T-1"])
        self.assertEqual(got[("A1", "R1", "2026-07")].evidence_ids, ["MULE-DWELL-T-2"])
        self.assertTrue(f["finding_id"].is_unique)

    def test_unify_groups_r3_by_network(self):
        f = sample_chain()["findings"].set_index("entity_id")
        net = f.loc["NET-1"]
        self.assertEqual(net["entity_type"], "network")
        self.assertEqual(net["network_id"], "NET-1")
        ids = net["evidence_ids"]
        self.assertTrue(any(i.startswith("MULE-CROSS-TX") for i in ids))
        self.assertTrue(any(i.startswith("MULE-NETWORK") for i in ids))
        self.assertEqual(sorted(net["member_accts"]), sorted(answer_key()["networks"][0]["members"]))
        # R3 counts the skill families of every member's evidence
        self.assertIn("5.10 Hybrid", net["skill_families"])
        self.assertIn("5.9 Network", net["skill_families"])
        self.assertNotIn("NC1", f.index)  # collector / feeder rows folded into NET-1
        for a in ["N01", "N02", "N03", "N04"]:
            self.assertEqual(f.loc[a, "risk"], "R2")
            self.assertEqual(f.loc[a, "network_id"], "NET-1")
        self.assertTrue(pd.isna(f.loc["M01", "network_id"]))

    def test_unify_empty(self):
        f = R()["unify_findings"](pd.DataFrame(columns=tr.EVIDENCE_COLUMNS), CFG)
        self.assertTrue(f.empty)
        self.assertEqual(list(f.columns[:len(FINDING_COLUMNS)]), FINDING_COLUMNS)

    def test_finding_count_matches_key(self):
        f = sample_chain()["findings"]
        key = answer_key()
        self.assertEqual(len(f), key["unified_findings"])
        got = set(zip(f["entity_type"], f["entity_id"], f["risk"], f["period"]))
        want = {(x["entity_type"], x["entity_id"], x["risk"], x["period"]) for x in key["findings"]}
        self.assertEqual(got, want)
        self.assertEqual((f["entity_type"] == "network").sum(), key["network_count"])


# ---------------------------------------------------------------- ASSESS-CMP
class TestAssess(unittest.TestCase):
    @staticmethod
    def _findings(n_families, data_ref_ok=True, risk="R1", refs=("T1",)):
        fam = ["5.1 Statistical", "5.9 Network"][:n_families]
        return pd.DataFrame([{"finding_id": "F1", "entity_type": "account", "entity_id": "A1",
                              "risk": risk, "period": "2026-08", "evidence_ids": ["E1"],
                              "skill_families": fam, "network_id": None, "member_accts": [],
                              "record_refs": list(refs), "data_ref_complete": data_ref_ok}])

    TX = pd.DataFrame({"tx_id": ["T1", "T2", "T3"], "amount": [100.0, 50.0, 4.0]})

    def test_assess_priority_table(self):
        table = CFG["ASSESS.PRIORITY"]
        ct = CFG["ASSESS.CLEARLY_TRIVIAL"]
        cases = {"สูง": 100.0, "กลาง": 100.0 / ct, "ต่ำ": 100.0 / ct + 1}  # materiality amounts
        confs = {"สูง": (2, True), "กลาง": (1, True), "ต่ำ": (2, False)}
        for conf, (nf, ok) in confs.items():
            for mat, base in cases.items():
                a = R()["assess_cmp"](self._findings(nf, ok), self.TX, base, CFG).iloc[0]
                self.assertEqual(a["confidence"], conf)
                self.assertEqual(a["materiality"], mat, (conf, mat, base))
                self.assertEqual(a["priority"], table[conf][mat], (conf, mat))
                self.assertEqual(a["review_status"], "รอ Human Review")
        low = R()["assess_cmp"](self._findings(2, False), self.TX, 100.0, CFG).iloc[0]
        self.assertIn("Confidence ต่ำ", low["review_reason"])

    def test_assess_no_materiality(self):
        for nf, conf in [(2, "สูง"), (1, "กลาง")]:
            a = R()["assess_cmp"](self._findings(nf), self.TX, None, CFG).iloc[0]
            self.assertEqual(a["materiality"], "ไม่ได้ประเมิน")
            self.assertEqual(a["priority"], conf)
            self.assertIn("ไม่มีฐาน Materiality", a["review_reason"])

    def test_assess_exposure_unique_refs(self):
        a = R()["assess_cmp"](self._findings(1, refs=("T1", "T2", "T1")), self.TX, None, CFG).iloc[0]
        self.assertEqual(a["exposure"], 150.0)

    def test_assess_sample(self):
        c = sample_chain()
        a = c["assessed"].set_index("entity_id")
        self.assertEqual(list(c["assessed"].columns[:len(FINDING_COLUMNS)]), FINDING_COLUMNS)
        self.assertEqual(a.loc["NET-1", "exposure"], c["networks"]["internal_amount"].iloc[0])
        self.assertEqual(a.loc["NET-1", "confidence"], "สูง")
        self.assertIn("Mule Account pattern", a.loc["NET-1", "review_reason"])
        self.assertIn("Mule Account pattern", a.loc["M01", "review_reason"])
        self.assertEqual(a.loc["O01", "confidence"], "กลาง")  # STAT-MAD only
        self.assertEqual(a.loc["V01", "confidence"], "กลาง")  # velocity + spike = 5.3 only
        self.assertEqual(a.loc["M01", "confidence"], "สูง")
        self.assertTrue((c["assessed"]["review_status"] == "รอ Human Review").all())
        for text in c["assessed"]["review_reason"]:
            self.assertNotIn("บัญชีม้า", text)


# ---------------------------------------------------------------- SELECT-AUTO-TRACE + LOG-RUN
class TestSelectAndLog(unittest.TestCase):
    def test_select_auto_trace(self):
        f = pd.DataFrame([
            {"entity_type": "account", "entity_id": "A1", "risk": "R2", "period": "2026-08",
             "priority": "กลาง", "exposure": 900.0, "member_accts": []},
            {"entity_type": "network", "entity_id": "NET-1", "risk": "R3", "period": "2026-07",
             "priority": "สูง", "exposure": 10.0, "member_accts": ["N2", "A1", "N1"]},
            {"entity_type": "account", "entity_id": "A2", "risk": "R2", "period": "2026-08",
             "priority": "กลาง", "exposure": 950.0, "member_accts": []},
            {"entity_type": "account", "entity_id": "B1", "risk": "R1", "period": "2026-08",
             "priority": "สูง", "exposure": 9e9, "member_accts": []},
            {"entity_type": "account", "entity_id": "A3", "risk": "R2", "period": "2026-08",
             "priority": "ต่ำ", "exposure": 9e9, "member_accts": []}])
        got = R()["select_auto_trace"](f, CFG)
        self.assertEqual(got, [("A1", "2026-07"), ("N1", "2026-07"), ("N2", "2026-07"),
                               ("A2", "2026-08"), ("A3", "2026-08")])
        cfg = {**CFG, "FLOW.AUTO_MAX_ENTITIES": 2}
        self.assertEqual(R()["select_auto_trace"](f, cfg), [("A1", "2026-07"), ("N1", "2026-07")])
        self.assertEqual(R()["select_auto_trace"](f.iloc[0:0], CFG), [])

    def test_select_auto_trace_sample(self):
        got = R()["select_auto_trace"](sample_chain()["assessed"], CFG)
        accts = [a for a, _ in got]
        self.assertLessEqual(len(got), CFG["FLOW.AUTO_MAX_ENTITIES"])
        self.assertEqual(len(accts), len(set(accts)))
        self.assertEqual(set(accts), {"M01", "N01", "N02", "N03", "N04", "NC1", "NF1"})

    def test_log_run(self):
        cfg = {**CFG, "_RUN": {**CFG["_RUN"], "pack_version": "B1"}}
        log = R()["log_run"]([
            {"stage": 3, "status": "OK", "detail": "Dataset Profile ผ่าน", "recipe_id": "PROF-PROFILE",
             "recipe_version": "1.0"},
            {"stage": 7, "status": "SKIP", "detail": "ไม่มีคอลัมน์ ts", "recipe_id": "BEH-VELOCITY"}], cfg)
        self.assertEqual(list(log.columns), RUN_LOG_COLUMNS)
        self.assertEqual(list(log["status"]), ["OK", "SKIP"])
        self.assertTrue((log["run_id"] == "T").all())
        self.assertTrue((log["registry_version"] == CFG["REGISTRY.VERSION"]).all())
        self.assertTrue((log["pack_version"] == "B1").all())
        self.assertTrue((log["input_sha256"] == "x").all())  # from data_ref "...|sha256:x"
        self.assertEqual(log["recipe_version"].iloc[1], "-")
        self.assertTrue(log["timestamp"].str.match(r"^\d{4}-\d{2}-\d{2}T").all())
        with self.assertRaises(ValueError):
            R()["log_run"]([{"stage": 3, "status": "DONE"}], CFG)
        with self.assertRaises(ValueError):
            R()["log_run"]([{"stage": 19, "status": "OK"}], CFG)
        self.assertEqual(list(R()["log_run"]([], CFG).columns), RUN_LOG_COLUMNS)


if __name__ == "__main__":
    unittest.main()
