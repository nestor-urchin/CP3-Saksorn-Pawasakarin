"""Tests for AIDA C2 task 1: engine plumbing for data types L (life insurance) and F (funds), the event table,
code meanings and Registry v1.3."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _engine import engine  # noqa: E402
import test_orchestration as to  # noqa: E402

ROOT = HERE.parent
REGISTRY = ROOT / "knowledge" / "AIDA-14-configuration-registry.md"
E = engine

NEW_KEYS = {
    "LIFE.EARLY_SURR.MONTHS": 12, "LIFE.BENCHG_CASH.WINDOW_DAYS": 30, "LIFE.LOAN.NEAR_PCT": 0.9,
    "LIFE.LOAN.MIN_COUNT": 3, "LIFE.LOAN.COUNT_MONTHS": 12, "LIFE.LOAN_SURR.WINDOW_DAYS": 90,
    "LIFE.PAYEE.MIN_POLICIES": 3, "LIFE.BENEF.MIN_POLICIES": 3, "LIFE.BENCHG.MIN_COUNT": 2,
    "LIFE.BENCHG.COUNT_MONTHS": 12, "FUND.ROUNDTRIP.DAYS": 30, "FUND.ROUNDTRIP.AMOUNT_BAND": {"low": 0.8, "high": 1.2},
    "FUND.SHARED_ACCT.MIN_HOLDERS": 3, "FUND.FREQ.MIN_TX_MONTH": 6, "FUND.CHURN.MIN_CLIENT_SHARE": 0.3,
    "FUND.CHURN.MIN_CLIENTS": 5, "FUND.CUTOFF_TIME": "15:30"}

L_ROLES = {
    "tx": {"txn_id": "record_id", "policy_no": "contract", "insured_id": "entity", "txn_date": "date",
           "txn_type": "category", "amount": "amount", "payee": "counterparty", "cash_value": "limit",
           "staff_id": "created_by"},
    "master": {"policy_no": "contract", "insured_id": "entity", "issue_date": "opened_at", "premium_mode": "category"},
    "events": {"change_id": "record_id", "policy_no": "contract", "change_date": "date",
               "beneficiary": "counterparty", "staff_id": "created_by"}}


def l_frames(events_policy=("P1", "P2", "P3")):
    tx = pd.DataFrame({
        "txn_id": ["T1", "T2", "T3", "T4"], "policy_no": ["P1", "P2", "P3", "P1"],
        "insured_id": ["I1", "I2", "I3", "I1"], "txn_date": ["2026-01-05", "2026-02-01", "2026-03-01", "2026-04-01"],
        "txn_type": ["SURR ", "LN", "CLM", "surr"], "amount": ["100", "200", "300", "400"],
        "payee": ["I1", "X9", "I3", "I1"], "cash_value": ["500", "500", "500", "500"],
        "staff_id": ["S1", "S1", "S2", "S1"]})
    master = pd.DataFrame({"policy_no": ["P1", "P2", "P3"], "insured_id": ["I1", "I2", "I3"],
                           "issue_date": ["2025-12-01", "2024-01-01", "2023-01-01"],
                           "premium_mode": ["single", "periodic", "periodic"]})
    events = pd.DataFrame({"change_id": ["C1", "C2", "C3"], "policy_no": list(events_policy),
                           "change_date": ["2026-01-01", "2026-02-10", "2026-03-10"],
                           "beneficiary": ["B1", "B1", "B1"], "staff_id": ["S1", "S1", "S2"]})
    return {"tx": tx, "master": master, "events": events}


class Versions(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(E().__version__, "3.1.0")
        self.assertEqual(E().REGISTRY_VERSION, "1.3")
        self.assertEqual(E().load_registry(str(REGISTRY))["REGISTRY.VERSION"], "1.3")

    def test_new_registry_keys_present(self):
        cfg = E().load_registry(str(REGISTRY))
        for k, v in NEW_KEYS.items():
            self.assertIn(k, cfg)
            self.assertEqual(cfg[k], v, k)
        text = REGISTRY.read_text(encoding="utf-8")
        for k in NEW_KEYS:
            self.assertIn(f"`{k}", text)
        self.assertIn("| 1.3 |", text)

    def test_general_checks_cover_L_F(self):
        self.assertEqual(E().DATA_TYPES, ("E", "C", "A", "L", "F"))
        ch = E().CHECKS
        for cid in ("STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "GEN-CONC", "GEN-PERIOD-END",
                    "FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT"):
            self.assertTrue({"L", "F"} <= set(ch[cid]["data_types"]), cid)
        for cid in ("NET-CYCLE", "MULE-DWELL", "DUP-PAY", "SOD-SAME-USER", "SPLIT-LIMIT", "PAYER-MULTI", "DUE-NEAR"):
            self.assertFalse({"L", "F"} & set(ch[cid]["data_types"]), cid)
        for rid in ("G-R1", "G-R2", "G-R3", "G-R4"):
            self.assertTrue({"L", "F"} <= set(E().RISK_LIBRARY[rid]["data_types"]), rid)
        for rid in ("R1", "R2", "R3", "R4", "A-R1", "A-R4", "C-R1"):
            self.assertFalse({"L", "F"} & set(E().RISK_LIBRARY[rid]["data_types"]), rid)


class Presets(unittest.TestCase):
    def test_presets_L_F(self):
        p = E().PRESETS
        self.assertEqual(p["L"], {
            "txn_id": "record_id", "policy_no": "contract", "insured_id": "entity", "txn_date": "date",
            "txn_type": "category", "amount": "amount", "payee": "counterparty", "cash_value": "limit",
            "staff_id": "created_by", "issue_date": "opened_at", "premium_mode": "category",
            "change_id": "record_id", "change_date": "date", "beneficiary": "counterparty"})
        self.assertEqual(p["F"], {
            "order_id": "record_id", "unitholder_id": "entity", "fund_code": "contract",
            "order_datetime": "date", "txn_type": "category", "amount": "amount", "bank_account": "counterparty",
            "agent": "channel", "nav_date": "due_date", "open_date": "opened_at"})

    def test_labels_and_meanings(self):
        e = E()
        self.assertEqual(e.ENTITY_LABELS["L"], {"entity": "insured", "account": "policy", "counterparty": "payee"})
        self.assertEqual(e.ENTITY_LABELS["F"], {"entity": "unitholder", "account": "fund", "counterparty": "account"})
        m = e.ROLE_MEANING_BY_TYPE
        self.assertEqual(m["L"]["limit"], "มูลค่าเวนคืน")
        self.assertEqual(m["L"]["counterparty"], "ผู้รับเงิน / ผู้รับผลประโยชน์")
        self.assertEqual(m["L"]["opened_at"], "วันออกกรมธรรม์")
        self.assertEqual(m["F"]["due_date"], "วันที่ได้ราคา NAV")
        self.assertEqual(m["F"]["channel"], "ตัวแทนขาย")
        self.assertEqual(m["F"]["counterparty"], "บัญชีชำระ/รับเงิน")

    def test_detect_type_L_F(self):
        e = E()
        fr = l_frames()
        self.assertEqual(e.detect_dataset_type(e.profile_columns(fr)), "L")
        ff = {"orders": pd.DataFrame({
            "order_id": ["O1", "O2", "O3"], "unitholder_id": ["U1", "U2", "U3"], "fund_code": ["F1", "F2", "F3"],
            "order_datetime": ["2026-01-05 10:00", "2026-01-06 11:00", "2026-01-07 12:00"],
            "txn_type": ["BUY", "SELL", "BUY"], "amount": ["1000", "2000", "3000"],
            "bank_account": ["A1", "A2", "A3"], "agent": ["G1", "G2", "G3"],
            "nav_date": ["2026-01-05", "2026-01-06", "2026-01-07"]})}
        self.assertEqual(e.detect_dataset_type(e.profile_columns(ff)), "F")
        sug = e.suggest_roles(e.profile_columns(ff), None, "F")
        got = dict(zip(sug["column"], sug["role"]))
        self.assertEqual(got["nav_date"], "due_date")
        self.assertEqual(got["fund_code"], "contract")
        self.assertEqual(got["agent"], "channel")

    def test_detect_type_c1_unchanged(self):
        e = E()
        for name in ("C", "A"):
            fr = {t: pd.read_csv(p, dtype=str) for t, p in to.files(name).items()}
            self.assertEqual(e.detect_dataset_type(e.profile_columns(fr)), name)


class EventTable(unittest.TestCase):
    def test_to_internal_event_table(self):
        fr = l_frames()
        t = E().to_internal(fr, L_ROLES)
        self.assertEqual(set(t), {"transactions", "accounts", "events"})
        self.assertEqual(set(t["events"].columns), {"tx_id", "ts", "contract", "to_acct", "created_by"})
        self.assertIn("acct_id", t["accounts"].columns)
        self.assertEqual(len(t["events"]), 3)

    def test_to_internal_two_event_tables_rejected(self):
        fr = l_frames()
        fr["events2"] = fr["events"].copy()
        roles = {**L_ROLES, "events2": dict(L_ROLES["events"])}
        with self.assertRaises(E().AidaError) as cm:
            E().to_internal(fr, roles)
        self.assertRegex(str(cm.exception), r"[฀-๿]")

    def test_master_without_record_id_not_event(self):
        fr = l_frames()
        t = E().to_internal({k: fr[k] for k in ("tx", "master")}, {k: L_ROLES[k] for k in ("tx", "master")})
        self.assertNotIn("events", t)

    def test_event_join_normalised(self):
        e = E()
        fr = l_frames(events_policy=("0P1", "0P2", "0P3"))  # leading zero only
        fr["tx"]["policy_no"] = ["101", "102", "103", "101"]
        fr["events"]["policy_no"] = ["00101", "00102", "00103"]
        fr["master"]["policy_no"] = ["101", "102", "103"]
        p = e.profile_columns({"tx": fr["tx"], "events": fr["events"], "master": fr["master"]})
        r = p[(p.table == "events") & (p.column == "policy_no")].iloc[0]["join_match"]
        self.assertEqual(r["with"], "tx.policy_no")
        self.assertEqual(r["raw"], 0.0)
        self.assertEqual(r["normalized"], 100.0)
        self.assertEqual(r["by_table"]["tx"], {"raw": 0.0, "normalized": 100.0})
        ctx = e._intake_ctx(L_ROLES, p, None, None)
        self.assertEqual(ctx["joins"]["events"], ("events", 100.0))

    def test_event_join_reported_against_transactions_not_master(self):
        e = E()
        fr = l_frames()
        fr["tx"]["policy_no"] = ["P1", "P2", "P9", "P8"]       # events cover only 2 of 3 in tx
        fr["events"]["policy_no"] = ["P1", "P2", "P3"]
        p = e.profile_columns({"events": fr["events"], "master": fr["master"], "tx": fr["tx"]})
        ctx = e._intake_ctx(L_ROLES, p, None, None)
        name, rate = ctx["joins"]["events"]
        self.assertEqual(name, "events")
        self.assertAlmostEqual(rate, 66.7, places=1)

    def test_review_a_event_table_and_join_lines(self):
        e = E()
        with tempfile.TemporaryDirectory() as d:
            paths = {}
            for k, df in l_frames().items():
                paths[k] = str(Path(d) / f"{k}.csv")
                df.to_csv(paths[k], index=False)
            r = e.inspect(paths, {})
        a = to.section(r["review_th"], "A")
        self.assertEqual(r["intake"]["dataset_type"], "L")
        self.assertIn("cash_value → limit (มูลค่าเวนคืน)", a)
        self.assertIn("issue_date → opened_at (วันออกกรมธรรม์)", a)
        self.assertIn("ตารางเหตุการณ์", a)
        self.assertIn("events", a)
        for w in to.ACCUSE:
            self.assertNotIn(w, r["review_th"])


class CodeMeanings(unittest.TestCase):
    def _tables(self, cats, codes, dtype="L", name="tx"):
        e = E()
        tx = pd.DataFrame({"tx_id": [str(i) for i in range(len(cats))], "category": cats})
        intake = {"roles": {name: {"txn_id": "record_id", "txn_type": "category"}},
                  "code_values": {f"{name}.txn_type": codes} if codes is not None else {}, "dataset_type": dtype}
        return e.attach_meta({"transactions": tx}, intake)

    def test_code_meaning_normalised(self):
        e = E()
        t = self._tables(["SURR ", "ln", "x"], {"SURR ": "Surrender", "ln": "เงินกู้"})
        self.assertEqual(e.code_set(t, "surrender"), {"SURR "})
        self.assertEqual(e.code_set(t, "loan"), {"ln"})
        self.assertEqual(e.code_set(t, "claim"), set())
        self.assertEqual(e.resolve_code_meaning("Surrender"), "surrender")
        self.assertEqual(e.resolve_code_meaning("เวนคืน"), "surrender")
        self.assertEqual(e.resolve_code_meaning("  SURRENDER "), "surrender")
        self.assertEqual(e.resolve_code_meaning("Policy loan"), "loan")
        self.assertIsNone(e.resolve_code_meaning("ไม่รู้"))

    def test_data_spelling_differs_from_confirmed_code(self):
        e = E()
        t = self._tables(["surr", " SURR", "Surr ", "ln"], {"SURR ": "เวนคืน", "LN": "loan"})
        self.assertEqual(e.code_set(t, "surrender"), {"surr", " SURR", "Surr "})
        self.assertEqual(e.code_set(t, "loan"), {"ln"})
        mask = e.code_mask(t["transactions"], e.code_set(t, "surrender"))
        self.assertEqual(list(mask), [True, True, True, False])

    def test_thai_meaning_and_fund_codes(self):
        e = E()
        t = self._tables(["B", "S", "SI", "SO"], {"B": "ซื้อ", "S": "ขาย (ไถ่ถอน)", "SI": "Switch in", "SO": "สับเปลี่ยนออก"},
                         "F")
        self.assertEqual(e.code_set(t, "buy"), {"B"})
        self.assertEqual(e.code_set(t, "sell"), {"S"})
        self.assertEqual(e.code_set(t, "switch_in"), {"SI"})
        self.assertEqual(e.code_set(t, "switch_out"), {"SO"})

    def test_missing_codes_reason_thai(self):
        e = E()
        t = self._tables(["SURR"], {"SURR": "Surrender"})
        self.assertEqual(e.missing_codes(t, ["surrender", "loan"]), ["loan"])
        self.assertEqual(e.missing_codes(t, ["surrender"]), [])
        txt = e.missing_codes_reason(["loan"])
        self.assertTrue(txt.startswith("ยังไม่ได้ยืนยันความหมายรหัสประเภทรายการ: "))
        self.assertIn("loan", txt)

    def test_unconfirmed_codes_use_defaults_but_everything_missing(self):
        e = E()
        t = self._tables(["SURR", "LOAN"], None)
        self.assertEqual(e.missing_codes(t, ["surrender", "loan"]), ["surrender", "loan"])
        self.assertEqual(e.code_set(t, "surrender"), {"SURR"})  # default code, matched in the data
        t2 = self._tables(["SURR"], {})
        self.assertEqual(e.missing_codes(t2, ["surrender"]), ["surrender"])

    def test_no_meta_is_safe(self):
        e = E()
        t = {"transactions": pd.DataFrame({"tx_id": ["1"], "category": ["SURR"]})}
        self.assertEqual(e.missing_codes(t, ["surrender"]), ["surrender"])

    def test_unrecognised_meaning_is_missing(self):
        e = E()
        t = self._tables(["Z"], {"Z": "อะไรไม่รู้"})
        self.assertEqual(e.missing_codes(t, ["surrender"]), ["surrender"])

    def test_original_name_mapping_across_tables(self):
        # the confirmed key is "<file stem>.<original column>", the role adapter renames it to `category`
        e = E()
        t = self._tables(["SURR"], {"SURR": "surrender"}, name="policy_tx")
        self.assertEqual(e.code_set(t, "surrender"), {"SURR"})


class RunFillsMeta(unittest.TestCase):
    def _run_l(self, d):
        e = E()
        paths = {}
        frames = l_frames()
        tx = frames["tx"]
        extra = pd.DataFrame({"txn_id": [f"X{i}" for i in range(40)], "policy_no": ["P2"] * 40,
                              "insured_id": ["I2"] * 40, "txn_date": [f"2026-02-{1 + i % 27:02d}" for i in range(40)],
                              "txn_type": ["SURR"] * 40, "amount": ["10"] * 40, "payee": ["I2"] * 40,
                              "cash_value": ["500"] * 40, "staff_id": ["S1"] * 40})
        frames["tx"] = pd.concat([tx, extra], ignore_index=True)
        for k, df in frames.items():
            paths[k] = str(Path(d) / f"{k}.csv")
            df.to_csv(paths[k], index=False)
        ins = e.inspect(paths, {})
        it = e.confirm(ins["intake"], {"roles": L_ROLES, "code_values": {"tx.txn_type": {
            "SURR": "Surrender", "LN": "เงินกู้", "CLM": "claim"}}, "reviewer": "ทดสอบ"}, str(Path(d) / "intake.json"))
        return e, paths, it

    def test_run_and_trace_attach_meta(self):
        with tempfile.TemporaryDirectory() as d:
            e, paths, it = self._run_l(d)
            seen = []

            def spy(tables, cfg):
                seen.append((tables.get("meta"), tables.get("events")))
                return pd.DataFrame(columns=e.EVIDENCE_COLUMNS)
            lib, spec = e.RISK_LIBRARY["G-R2"], dict(e.CHECKS["GEN-PERIOD-END"])
            old_checks = list(lib["checks"])
            e.CHECKS["ZZ-SPY"] = {**spec, "func": spy, "requires": ["record_id"]}
            lib["checks"] = old_checks + ["ZZ-SPY"]
            try:
                it["risks"]["requested"] = ["G-R2"]
                e.run(paths, it, d)
            finally:
                del e.CHECKS["ZZ-SPY"]
                lib["checks"] = old_checks
            self.assertTrue(seen)
            meta, events = seen[0]
            self.assertEqual(meta["code_values"]["tx.txn_type"]["SURR"], "Surrender")
            self.assertEqual(len(events), 3)
            pre = e._prepare(paths, it, e._effective_cfg(None, it, None, {})[0])
            m = pre["tables"]["meta"]
            self.assertEqual(m["dtype"], "L")
            self.assertEqual(e.code_set(pre["tables"], "surrender"), {"SURR", "surr", "SURR "})
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(pre["tables"]["events"]["ts"]))

    def test_attach_meta_signature(self):
        e = E()
        t = e.attach_meta({"transactions": pd.DataFrame()}, {"roles": {}, "code_values": {"a.b": {"x": "buy"}}})
        self.assertEqual(t["meta"]["code_values"], {"a.b": {"x": "buy"}})


class FixesReview(unittest.TestCase):
    """Review fixes: type-exclusive anchors, confirmed dataset_type, meaning matcher."""

    def test_ap_with_order_and_bank_stays_A(self):
        e = E()
        ap = pd.DataFrame({"order_id": ["O1", "O2", "O3"], "pay_date": ["2026-01-05", "2026-01-06", "2026-01-07"],
                           "amount": ["10", "20", "30"], "vendor_id": ["V1", "V2", "V3"],
                           "bank_account": ["B1", "B2", "B3"], "created_by": ["U1", "U2", "U3"],
                           "approved_by": ["U2", "U3", "U1"], "invoice_no": ["I1", "I2", "I3"]})
        prof = e.profile_columns({"ap": ap})
        self.assertNotIn(e.detect_dataset_type(prof), ("L", "F"))
        roles = {"record_id", "date", "amount", "entity", "created_by", "approved_by", "document_no"}
        self.assertEqual(e._type_from_roles(roles, prof), "A")

    def test_e_with_accounts_open_date_stays_E(self):
        e = E()
        tx = pd.DataFrame({"tx_id": ["T1", "T2", "T3"], "ts": ["2026-01-05", "2026-01-06", "2026-01-07"],
                           "from_acct": ["A1", "A2", "A3"], "to_acct": ["A2", "A3", "A1"], "amount": ["1", "2", "3"]})
        acc = pd.DataFrame({"acct_id": ["A1", "A2", "A3"], "open_date": ["2020-01-01"] * 3,
                            "bank_account": ["B1", "B2", "B3"], "staff_id": ["S1", "S2", "S3"]})
        prof = e.profile_columns({"transactions": tx, "accounts": acc})
        self.assertEqual(e.detect_dataset_type(prof), "E")
        roles = {"record_id", "date", "amount", "entity", "counterparty"}
        self.assertEqual(e._type_from_roles(roles, prof), "E")

    def _legacy(self, d):
        """The L fixture with cryptic column names: detection alone reads it as E."""
        fr = l_frames()
        names, roles, files = {}, {}, {}
        for t, df in fr.items():
            m = {c: f"c{i}" for i, c in enumerate(df.columns)}
            roles[t] = {m[c]: r for c, r in L_ROLES[t].items()}
            files[t] = str(Path(d) / f"{t}.csv")
            df.rename(columns=m).to_csv(files[t], index=False)
            names[t] = m
        return files, roles, names

    def test_confirm_dataset_type_override_legacy_L(self):
        e = E()
        with tempfile.TemporaryDirectory() as d:
            files, roles, names = self._legacy(d)
            ins = e.inspect(files, {})
            self.assertNotEqual(ins["intake"]["dataset_type"], "L")
            self.assertIn("ประเภทข้อมูลที่ตรวจพบ", ins["review_th"])
            self.assertIn("แก้ได้ในคำตอบ", ins["review_th"])
            code_key = f"tx.{names['tx']['txn_type']}"
            it = e.confirm(ins["intake"], {"roles": roles, "dataset_type": "L", "code_values": {code_key: {"SURR": "เวนคืน"}}},
                           str(Path(d) / "intake.json"))
            self.assertEqual(it["dataset_type"], "L")
            pre = e._prepare(files, it, e._effective_cfg(None, it, None, {})[0])
            self.assertEqual(pre["tables"]["meta"]["dtype"], "L")
            self.assertEqual(e.code_set(pre["tables"], "surrender"), {"SURR", "surr", "SURR "} & set(pre["tables"]["transactions"]["category"]))
            self.assertEqual(e._type_from_roles({"entity", "counterparty", "date", "amount"}, None, "L"), "L")
            res = e.run(files, it, d)
            self.assertIn(e.TYPE_TEXT["L"], res["summary_th"])

    def test_confirm_dataset_type_invalid_thai(self):
        e = E()
        with tempfile.TemporaryDirectory() as d:
            files, roles, _ = self._legacy(d)
            ins = e.inspect(files, {})
            with self.assertRaises(e.AidaError) as cm:
                e.confirm(ins["intake"], {"roles": roles, "dataset_type": "Z"}, str(Path(d) / "i.json"))
            self.assertRegex(str(cm.exception), r"[฀-๿]")
            self.assertIn("L", str(cm.exception))

    def test_mapping_keeps_dataset_type(self):
        e = E()
        with tempfile.TemporaryDirectory() as d:
            files, roles, _ = self._legacy(d)
            ins = e.inspect(files, {})
            it = e.confirm(ins["intake"], {"roles": roles, "dataset_type": "L"}, str(Path(d) / "i.json"))
            mp = e.save_mapping(it, str(Path(d) / "mapping-l.json"))
            self.assertEqual(e.load_mapping(mp)["dataset_type"], "L")
            ins2 = e.inspect(files, {}, mapping=mp)
            self.assertEqual(ins2["intake"]["dataset_type"], "L")

    def test_meaning_table(self):
        e = E()
        rows = [("จ่ายสินไหมให้ผู้รับผลประโยชน์", "claim"), ("จ่ายเงินให้ผู้รับผลประโยชน์", None),
                ("ชำระคืนเงินกู้", None), ("คืนเงินกู้", None), ("loan repayment", None), ("ดอกเบี้ยเงินกู้", None),
                ("loan interest", None), ("รับซื้อคืน", "sell"), ("รับซื้อคืนหน่วยลงทุน", "sell"),
                ("ยกเลิกคำสั่งซื้อ", None), ("Cancel buy", None), ("เปลี่ยนผู้รับผลประโยชน์", "benefit_change"),
                ("Change beneficiary", "benefit_change"), ("redemption", "sell"), ("เงินกู้", "loan")]
        for text, want in rows:
            with self.subTest(text=text):
                self.assertEqual(e.resolve_code_meaning(text), want)

    def test_review_a_shows_resolved_meaning(self):
        e = E()
        with tempfile.TemporaryDirectory() as d:
            paths = {}
            for k, df in l_frames().items():
                paths[k] = str(Path(d) / f"{k}.csv")
                df.to_csv(paths[k], index=False)
            it = e.inspect(paths, {})["intake"]
        it["code_values"] = {"tx.txn_type": {"SURR": "Surrender", "LN": "ชำระคืนเงินกู้"}}
        a = "\n".join(e._review_a(it))
        self.assertIn("SURR = Surrender → surrender", a)
        line = [x for x in a.splitlines() if "ค่ารหัสของ tx.txn_type" in x][0]
        self.assertTrue(line.startswith("❓"))
        self.assertIn("LN = ชำระคืนเงินกู้ → ❓", line)

    def test_require_codes_guard(self):
        e = E()
        t = CodeMeanings()._tables(["SURR"], {"SURR": "Surrender"})
        self.assertIsNone(e.require_codes(t, ["surrender"]))
        self.assertTrue(e.require_codes(t, ["surrender", "loan"]).startswith("ยังไม่ได้ยืนยันความหมายรหัสประเภทรายการ: loan"))
        t0 = CodeMeanings()._tables(["SURR"], None)
        self.assertIn("surrender", e.require_codes(t0, ["surrender"]))


class CAUnchanged(unittest.TestCase):
    def test_e_c_a_unchanged(self):
        for name in ("C", "A"):
            r = to.ran(name)
            self.assertEqual(to.finding_set(r["findings"]), to.key_set(name), name)
        r = to.ran("E")
        self.assertTrue(len(r["findings"]) > 0)


if __name__ == "__main__":
    unittest.main()
