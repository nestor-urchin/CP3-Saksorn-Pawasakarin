"""Task 3: column profiling, role suggestion, description checks."""
import time
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from _engine import engine

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def E():
    return engine()


def sample_frames():
    return {"transactions": pd.read_csv(SAMPLES / "transactions.csv", dtype=str),
            "accounts": pd.read_csv(SAMPLES / "accounts.csv", dtype=str)}


def row(prof, table, col):
    r = prof[(prof["table"] == table) & (prof["column"] == col)]
    assert len(r) == 1, (table, col)
    return r.iloc[0]


class TestProfile(unittest.TestCase):
    def test_profile_patterns(self):
        prof = E().profile_columns(sample_frames())
        self.assertEqual(len(prof), 7 + 3)
        self.assertIn("account_like", row(prof, "transactions", "from_acct")["patterns"])
        self.assertIn("date", row(prof, "transactions", "ts")["patterns"])
        self.assertIn("datetime", row(prof, "transactions", "ts")["patterns"])
        self.assertEqual(row(prof, "transactions", "amount")["dtype_guess"], "number")
        self.assertEqual(len(row(prof, "transactions", "tx_id")["samples"]), 3)
        self.assertLessEqual(len(row(prof, "transactions", "channel")["top5"]), 5)
        self.assertIn("code", row(prof, "transactions", "channel")["patterns"])
        f = pd.DataFrame({"cid": ["1101700012345", "3100500098765", "1234567890123"],
                          "net": [100.0, -20.5, 30.0], "nm": ["สมชาย ใจดี", "สมหญิง", "มานะ"]})
        p = E().profile_columns({"t": f})
        self.assertIn("thai_id13", row(p, "t", "cid")["patterns"])
        self.assertIn("negative", row(p, "t", "net")["patterns"])
        self.assertEqual(row(p, "t", "net")["neg_count"], 1)
        self.assertIn("thai_text", row(p, "t", "nm")["patterns"])

    def test_profile_thai_dates(self):
        f = pd.DataFrame({"a": ["01/02/2569", "15/03/2569", "28/12/2568"],
                          "b": ["5 มค 2569", "6 กพ. 2569", "7 ธ.ค. 2568"],
                          "c": ["2026-01-05", "2026-02-06", "2026-03-07"]})
        p = E().profile_columns({"t": f})
        for c in "abc":
            self.assertEqual(row(p, "t", c)["dtype_guess"], "date", c)
        self.assertTrue(row(p, "t", "a")["min"].startswith("2025-12-28"))

    def test_profile_relation_difference(self):
        rng = np.random.default_rng(1)
        a = rng.integers(1000, 9000, 200).astype(float)
        b = rng.integers(10, 900, 200).astype(float)
        f = pd.DataFrame({"A_total": a, "B_paid": b, "C_balance": a - b})
        p = E().profile_columns({"loan": f})
        rels = sum((list(x) for x in p["relations"]), [])
        self.assertIn("C_balance = A_total − B_paid", rels)

    def test_profile_relation_order_and_equality(self):
        f = pd.DataFrame({"opened": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"]),
                          "paid": pd.to_datetime(["2021-01-01", "2021-02-01", "2021-03-01", "2021-04-01"]),
                          "x": [1, 2, 3, 4], "y": [1, 2, 3, 9]})
        p = E().profile_columns({"t": f})
        self.assertIn("opened ≤ paid", list(row(p, "t", "opened")["relations"]))
        self.assertIn("x == y in 75%", list(row(p, "t", "x")["relations"]))

    def test_join_match_rate_reported(self):
        tx = pd.DataFrame({"acct": ["0001", "0002", "0003", "0004", "0005"], "amt": [1.5, 2.5, 3.5, 4.5, 5.5]})
        master = pd.DataFrame({"acct_id": [" 1", "2", "3", "4", "99"], "opened": ["x"] * 5})
        p = E().profile_columns({"tx": tx, "master": master})
        jm = row(p, "tx", "acct")["join_match"]
        self.assertEqual(jm["with"], "master.acct_id")
        self.assertEqual(jm["raw"], 0.0)
        self.assertEqual(jm["normalized"], 80.0)
        self.assertIsNone(row(p, "tx", "amt")["join_match"])

    def test_join_match_sample_exact(self):
        p = E().profile_columns(sample_frames())
        jm = row(p, "transactions", "from_acct")["join_match"]
        self.assertEqual(jm["with"], "accounts.acct_id")
        self.assertGreater(jm["normalized"], 90)

    def test_profile_perf(self):
        rng = np.random.default_rng(0)
        n = 80_000
        f = pd.DataFrame({
            "id": [f"T{i:07d}" for i in range(n)],
            "ts": pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 10**7, n), unit="s"),
            "due": (pd.Timestamp("2026-02-01") + pd.to_timedelta(rng.integers(0, 10**6, n), unit="s")).astype(str),
            "a": [f"A{i:05d}" for i in rng.integers(0, 3000, n)], "b": [f"A{i:05d}" for i in rng.integers(0, 3000, n)],
            "amt": rng.normal(5000, 900, n).round(2), "fee": rng.normal(20, 5, n).round(2),
            "bal": rng.normal(9000, 100, n).round(2), "q": rng.integers(0, 50, n), "ch": rng.choice(["atm", "app"], n),
            "cat": rng.choice(list("ABCDEFG"), n), "cid": rng.integers(10**12, 10**13 - 1, n),
            "txt": rng.choice(["สมชาย", "สมหญิง"], n), "n1": rng.random(n), "n2": rng.random(n)})
        t0 = time.time()
        p = E().profile_columns({"t": f, "m": f.head(5000).copy()})
        self.assertLessEqual(time.time() - t0, 5.0)
        self.assertEqual(len(p), 30)


class TestRoles(unittest.TestCase):
    def prof(self, **cols):
        return E().profile_columns({"t": pd.DataFrame(cols)})

    def test_suggest_roles_from_brief_overrides_guess(self):
        p = self.prof(amount=["a1", "a2", "a3"], F07=[10.5, -2.0, 7.25])
        r = E().suggest_roles(p, {"amount": "ผู้อนุมัติรายการ", "F07": "ยอดสุทธิ"}, None, {})
        a = r[r["column"] == "amount"].iloc[0]
        f = r[r["column"] == "F07"].iloc[0]
        self.assertEqual((a["role"], a["source"]), ("approved_by", "brief"))
        self.assertEqual((f["role"], f["source"], f["level"]), ("amount", "brief", "สูง"))

    def test_suggest_roles_cryptic_unknown(self):
        p = self.prof(F07=["k1x", "q92", "zz3", "k1x"], COL3=[5.5, 6.25, 1.0, 9.75])
        r = E().suggest_roles(p, None, None, {})
        self.assertEqual(list(r["role"]), ["ไม่ทราบ", "ไม่ทราบ"])
        self.assertTrue(all(r["reason"].str.contains("ผู้ตรวจสอบ")))

    def test_suggest_roles_names_levels(self):
        p = E().profile_columns(sample_frames())
        r = E().suggest_roles(p, None, None, {}).set_index(["table", "column"])
        self.assertEqual(r.loc[("transactions", "from_acct")]["role"], "entity")
        self.assertEqual(r.loc[("transactions", "to_acct")]["role"], "counterparty")
        self.assertEqual(r.loc[("transactions", "tx_id")]["role"], "record_id")
        self.assertEqual(r.loc[("transactions", "amount")]["level"], "สูง")
        self.assertEqual(r.loc[("accounts", "opened_at")]["role"], "opened_at")
        t = E().suggest_roles(self.prof(**{"ยอดเงิน": [1.5, 2.5], "วันที่ครบกำหนด": ["2026-01-01", "2026-02-01"]}), None, None, {})
        self.assertEqual(list(t["role"]), ["amount", "due_date"])
        leg = E().suggest_roles(self.prof(TRN_NO=["a1", "a2"], ACCT_FR=["A001", "A002"], BR_CD=["b", "c"]),
                                None, None, {})
        self.assertEqual(list(leg["role"]), ["record_id", "entity", "channel"])

    def test_suggest_roles_preset_and_profile_only(self):
        p = self.prof(pay_date=["2026-01-01", "2026-01-02"], cid=["1101700012345", "3100500098765"])
        r = E().suggest_roles(p, None, "C", {}).set_index("column")
        self.assertEqual((r.loc["pay_date"]["role"], r.loc["pay_date"]["source"]), ("date", "preset"))
        self.assertEqual(r.loc["cid"]["source"], "profile")
        self.assertIn(r.loc["cid"]["level"], ("ต่ำ", "กลาง"))
        self.assertLess(r.loc["cid"]["confidence"], 0.8)

    def test_role_conf_thresholds_forms(self):
        p = self.prof(F=["a", "b"], amount=[1.5, 2.5])
        for cfg in ({}, {"INTAKE.ROLE_CONF": {"สูง": 0.8, "กลาง": 0.5}},
                    {"INTAKE.ROLE_CONF": "สูง ≥ 0.8 / กลาง ≥ 0.5"}):
            r = E().suggest_roles(p, None, None, cfg).set_index("column")
            self.assertEqual(r.loc["amount"]["level"], "สูง")
        r = E().suggest_roles(p, None, None, {"INTAKE.ROLE_CONF": "สูง ≥ 0.9 / กลาง ≥ 0.5"}).set_index("column")
        self.assertEqual(r.loc["amount"]["level"], "กลาง")
        self.assertEqual(E()._role_thresholds({"INTAKE.ROLE_CONF": {"สูง": 0.7, "กลาง": 0.4}}), (0.7, 0.4))

    def test_check_descriptions_net_amount_negative(self):
        p = self.prof(amt=[100.0, -50.0, 20.0, 30.0], txid=["a", "b", "b", "c"])
        c = E().check_descriptions(p, {"amt": "ยอดสุทธิ", "txid": "รหัสรายการที่ไม่ซ้ำ"})
        by = {x["column"]: x for x in c}
        self.assertEqual(set(by), {"amt", "txid"})
        self.assertIn("1", by["amt"]["observed"])
        self.assertIn("25.0%", by["amt"]["observed"])
        self.assertEqual(by["amt"]["said"], "ยอดสุทธิ")
        self.assertIn("ซ้ำ 1", by["txid"]["observed"])
        self.assertTrue(all(x["question"] for x in c))
        self.assertEqual(E().check_descriptions(self.prof(amt=[1.0, 2.0]), {"amt": "ยอดสุทธิ"}), [])


class TestDatasetType(unittest.TestCase):
    def test_detect_dataset_type_e(self):
        self.assertEqual(E().detect_dataset_type(E().profile_columns(sample_frames())), "E")

    def test_detect_dataset_type_c_a_none(self):
        mk = lambda *cols: E().profile_columns({"t": pd.DataFrame({c: ["x1", "x2"] for c in cols})})
        self.assertEqual(E().detect_dataset_type(mk("contract_id", "due_date", "pay_date", "amount")), "C")
        self.assertEqual(E().detect_dataset_type(mk("invoice_no", "created_by", "approved_by", "amount")), "A")
        self.assertIsNone(E().detect_dataset_type(mk("F07", "COL3")))


if __name__ == "__main__":
    unittest.main()
