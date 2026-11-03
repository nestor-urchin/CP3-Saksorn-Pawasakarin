"""Tests for the synthetic sample data and its answer key.

The "grounding" tests re-derive every planted case from the generated rows with
small reference checks (thresholds read from the AIDA-14 Machine Config), so the
answer key is backed by the data rather than only asserted. Attribution follows
answer_key["conventions"]: per-account activity recipes look at the sending
account (from_acct).
"""
import json
import sys
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools"))

import make_sample_data as msd  # noqa: E402
from validate_pack import parse_machine_config  # noqa: E402

CFG, _ = parse_machine_config(ROOT / "knowledge" / "AIDA-14-configuration-registry.md")

RECIPE_IDS = [
    "STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE", "NET-FUNNEL",
    "MULE-DWELL", "MULE-NEW-ACCT", "MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK",
    "CPTY-PROFILE", "CPTY-NEW-LARGE", "FLOW-LAYERING",
]
MULE_SIGNALS = ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "TEMP-OFFHOURS"]
R1_RECIPES = ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE",
              "NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "FLOW-LAYERING"]

_CACHE = {}


def data():
    if "d" not in _CACHE:
        tx, accounts, key = msd.make()
        tx = tx.copy()
        tx["ts"] = pd.to_datetime(tx["ts"])
        accounts = accounts.copy()
        accounts["opened_at"] = pd.to_datetime(accounts["opened_at"])
        _CACHE["d"] = (tx, accounts, key)
    return _CACHE["d"]


def is_normal(acct):
    return acct.startswith("A")


def normal_rows(tx):
    return tx[tx["tx_id"].str.match(r"^T\d{6}$")]


# ---------------------------------------------------------------- reference checks
def ref_stat_mad(tx, by_channel):
    flagged = set()
    groups = tx.groupby("channel") if by_channel else [("all", tx)]
    for _, g in groups:
        med = g["amount"].median()
        mad = (g["amount"] - med).abs().median()
        z = 0.6745 * (g["amount"] - med) / mad
        flagged |= set(g.loc[z.abs() > CFG["STAT.MAD.THRESHOLD"], "tx_id"])
    return flagged


def _zflag(x, base, k):
    mean, std = np.mean(base), np.std(base, ddof=1)
    if std == 0:
        return x > mean
    return (x - mean) / std > k


def ref_velocity(tx, prior_window_only):
    need, k = CFG["BEH.BASELINE.MIN_PERIODS"]["velocity_days"], CFG["BEH.DEVIATION"]
    daily = tx.groupby(["from_acct", tx["ts"].dt.date]).size()
    flagged = set()
    for acct, s in daily.groupby(level=0):
        counts = s.to_numpy()
        for i in range(need, len(counts)):
            base = counts[i - need:i] if prior_window_only else counts[:i]
            if _zflag(counts[i], base, k):
                flagged.add(acct)
    return flagged


def ref_monthly_z(tx):
    """{(acct, month): z} for sender months with >= spike_months prior active months."""
    need = CFG["BEH.BASELINE.MIN_PERIODS"]["spike_months"]
    monthly = tx.groupby(["from_acct", tx["ts"].dt.strftime("%Y-%m")])["amount"].sum()
    out = {}
    for acct, s in monthly.groupby(level=0):
        vals = s.to_numpy()
        months = [m for _, m in s.index]
        for i in range(need, len(vals)):
            mean, std = vals[:i].mean(), vals[:i].std(ddof=1)
            out[(acct, months[i])] = np.inf if std == 0 and vals[i] > mean else (
                0.0 if std == 0 else (vals[i] - mean) / std)
    return out


def ref_offhours(tx):
    oh = CFG["TEMP.OFF_HOURS"]
    hhmm = tx["ts"].dt.strftime("%H:%M")
    off = (hhmm < oh["start"]) | (hhmm >= oh["end"])
    if oh["weekend"]:
        off |= tx["ts"].dt.dayofweek >= 5
    return set(tx.loc[off, "from_acct"])


def ref_cycles(tx):
    c = CFG["NET.CYCLE"]
    window = pd.Timedelta(days=c["days"])
    out_edges = defaultdict(list)
    for r in tx.itertuples():
        out_edges[r.from_acct].append((r.ts, r.to_acct))
    found = set()
    for r in tx.itertuples():
        stack = [(r.to_acct, r.ts, [r.from_acct, r.to_acct])]
        while stack:
            node, t, path = stack.pop()
            for ts, nxt in out_edges[node]:
                if ts < t or ts - r.ts > window:
                    continue
                if nxt == path[0] and len(path) >= c["min_len"]:
                    found |= set(path)
                elif nxt not in path and len(path) < c["max_len"]:
                    stack.append((nxt, ts, path + [nxt]))
    return found


def ref_funnel(tx):
    f = CFG["NET.FUNNEL"]
    window = pd.Timedelta(days=f["days"])
    flagged = set()
    for acct, ins in tx.groupby("to_acct"):
        outs = tx[tx["from_acct"] == acct]
        for t in ins["ts"]:
            w_in = ins[(ins["ts"] >= t) & (ins["ts"] < t + window)]
            w_out = outs[(outs["ts"] >= t) & (outs["ts"] < t + window)]
            if (w_in["from_acct"].nunique() >= f["min_sources"]
                    and w_out["amount"].sum() >= f["out_ratio"] * w_in["amount"].sum()):
                flagged.add(acct)
                break
    return flagged


def ref_dwell_pairs(tx):
    """{acct: number of inflows whose next outflow follows within MULE.DWELL_HOURS}."""
    limit = pd.Timedelta(hours=CFG["MULE.DWELL_HOURS"])
    pairs = {}
    for acct in set(tx["to_acct"]) & set(tx["from_acct"]):
        outs = np.sort(tx.loc[tx["from_acct"] == acct, "ts"].to_numpy())
        n = 0
        for t in tx.loc[tx["to_acct"] == acct, "ts"].to_numpy():
            j = np.searchsorted(outs, t, side="right")
            if j < len(outs) and outs[j] - t <= limit:
                n += 1
        pairs[acct] = n
    return pairs


def ref_new_acct(tx, accounts, basis, side):
    days, need = CFG["MULE.NEW_ACCT_DAYS"], CFG["MULE.NEW_ACCT_MIN_TX"]
    if side == "sender":
        inv = tx[["from_acct", "ts"]].rename(columns={"from_acct": "acct"})
    else:
        inv = pd.concat([tx[["from_acct", "ts"]].rename(columns={"from_acct": "acct"}),
                         tx[["to_acct", "ts"]].rename(columns={"to_acct": "acct"})])
    if basis == "opened_at":
        start = accounts.set_index("acct_id")["opened_at"]
    else:
        start = inv.groupby("acct")["ts"].min()
    inv = inv.assign(start=inv["acct"].map(start))
    inv = inv[(inv["ts"] >= inv["start"]) & (inv["ts"] <= inv["start"] + pd.Timedelta(days=days))]
    counts = inv.groupby("acct").size()
    return set(counts[counts >= need].index)


def ref_cpty_profile(tx):
    need = CFG["BEH.BASELINE.MIN_PERIODS"]["spike_months"]
    t = tx.assign(month=tx["ts"].dt.strftime("%Y-%m"))
    flagged = set()
    for acct, g in t.groupby("from_acct"):
        months = sorted(g["month"].unique())
        seen = set()
        for i, m in enumerate(months):
            cps = set(g.loc[g["month"] == m, "to_acct"])
            if i >= need and len(cps - seen) / len(cps) >= CFG["CPTY.NEW_RATIO"]:
                flagged.add(acct)
            seen |= cps
    return flagged


def ref_cpty_new_large(tx, median_basis):
    mult = CFG["CPTY.NEW_LARGE.MULTIPLIER"]
    flagged = set()
    for acct, g in tx.sort_values("ts").groupby("from_acct"):
        if median_basis == "sent":
            med = g["amount"].median()
        else:
            med = tx.loc[(tx["from_acct"] == acct) | (tx["to_acct"] == acct), "amount"].median()
        first = g.drop_duplicates("to_acct")
        if (first["amount"] >= mult * med).any():
            flagged.add(acct)
    return flagged


def ref_layering(tx):
    window = pd.Timedelta(days=CFG["FLOW.WINDOW_DAYS"])
    ratio, max_hops = CFG["FLOW.MIN_PASS_RATIO"], CFG["FLOW.MAX_HOPS"]
    out_edges = defaultdict(list)
    for r in tx.itertuples():
        out_edges[r.from_acct].append(r)
    found = set()
    for r in tx.itertuples():
        stack = [(r, [r.from_acct, r.to_acct])]
        while stack:
            last, path = stack.pop()
            if len(path) - 1 >= 3:
                found |= set(path)
            if len(path) - 1 >= max_hops:
                continue
            for nxt in out_edges[last.to_acct]:
                if (nxt.ts >= last.ts and nxt.ts - r.ts <= window
                        and nxt.amount >= ratio * last.amount and nxt.to_acct not in path):
                    stack.append((nxt, path + [nxt.to_acct]))
    return found


def ref_signals(tx, accounts):
    dwell = {a for a, n in ref_dwell_pairs(tx).items() if n >= CFG["MULE.DWELL_MIN_PAIRS"]}
    return {
        "NET-FUNNEL": ref_funnel(tx),
        "MULE-DWELL": dwell,
        "MULE-NEW-ACCT": ref_new_acct(tx, accounts, "opened_at", "any"),
        "BEH-VELOCITY": ref_velocity(tx, prior_window_only=False),
        "TEMP-OFFHOURS": ref_offhours(tx),
    }


def ref_network(tx, mules):
    window = pd.Timedelta(days=CFG["FLOW.WINDOW_DAYS"])
    links = CFG["MULE.CROSS.MIN_LINKS"]
    edges, roles = [], {m: "mule" for m in mules}
    for role, me, other in (("collector", "to_acct", "from_acct"), ("feeder", "from_acct", "to_acct")):
        cand = tx[tx[other].isin(mules) & ~tx[me].isin(mules)]
        for acct, g in cand.groupby(me):
            for t in g["ts"]:
                w = g[(g["ts"] >= t) & (g["ts"] < t + window)]
                if w[other].nunique() >= links:
                    roles[acct] = role
                    edges += [(acct, m) for m in w[other]]
                    break
    mm = tx[tx["from_acct"].isin(mules) & tx["to_acct"].isin(mules)]
    edges += list(zip(mm["from_acct"], mm["to_acct"]))
    parent = {a: a for a in roles}

    def find(a):
        while parent[a] != a:
            a = parent[a]
        return a
    for a, b in edges:
        parent[find(a)] = find(b)
    groups = defaultdict(set)
    for a in roles:
        groups[find(a)].add(a)
    nets = [g for g in groups.values() if len(g) >= CFG["MULE.NETWORK.MIN_SIZE"]]
    return nets, roles


# ---------------------------------------------------------------- brief tests
class TestSampleData(unittest.TestCase):
    def test_deterministic(self):
        tx1, acc1, key1 = msd.make()
        tx2, acc2, key2 = msd.make()
        pd.testing.assert_frame_equal(tx1, tx2)
        pd.testing.assert_frame_equal(acc1, acc2)
        self.assertEqual(key1, key2)

    def test_seed_changes_normal_data_only(self):
        tx1, _, key1 = msd.make()
        tx2, _, key2 = msd.make(seed=7)
        self.assertEqual(key1, key2)
        self.assertFalse(tx1.equals(tx2))
        planted = [t[~t["tx_id"].isin(normal_rows(t)["tx_id"])].reset_index(drop=True) for t in (tx1, tx2)]
        pd.testing.assert_frame_equal(*planted)

    def test_columns_and_formats(self):
        tx, acc, _ = msd.make()
        self.assertEqual(list(tx.columns),
                         ["tx_id", "ts", "from_acct", "to_acct", "amount", "currency", "channel"])
        self.assertEqual(list(acc.columns), ["acct_id", "opened_at", "account_type"])
        iso = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
        self.assertTrue(tx["ts"].str.match(iso).all())
        self.assertTrue(acc["opened_at"].str.match(iso).all())
        self.assertTrue(tx["tx_id"].is_unique)
        self.assertTrue(acc["acct_id"].is_unique)
        self.assertTrue((tx["amount"] > 0).all())
        self.assertFalse((tx["from_acct"] == tx["to_acct"]).any())
        self.assertTrue(set(tx["from_acct"]) | set(tx["to_acct"]) <= set(acc["acct_id"]))

    def test_volume_and_window(self):
        tx, _ = data()[:2]
        normal = normal_rows(tx)
        self.assertTrue(4500 <= len(normal) <= 5500, len(normal))
        self.assertGreaterEqual(tx["ts"].min(), pd.Timestamp("2026-01-01"))
        self.assertLess(tx["ts"].max(), pd.Timestamp("2026-09-01"))
        accts = set(tx["from_acct"]) | set(tx["to_acct"])
        self.assertEqual({a for a in accts if is_normal(a)}, {f"A{i:04d}" for i in range(1, 301)})

    def test_normal_accounts_business_hours(self):
        tx = data()[0]
        normal = tx[tx["from_acct"].map(is_normal) | tx["to_acct"].map(is_normal)]
        self.assertTrue(normal["tx_id"].str.match(r"^T\d{6}$").all())
        self.assertTrue((normal["ts"].dt.dayofweek < 5).all())
        self.assertTrue((normal["ts"].dt.hour >= 9).all())
        self.assertTrue((normal["ts"].dt.hour < 17).all())

    def test_normal_accounts_stable_history(self):
        tx = data()[0]
        normal = normal_rows(tx)
        inv = pd.concat([normal[["from_acct", "ts"]].rename(columns={"from_acct": "a"}),
                         normal[["to_acct", "ts"]].rename(columns={"to_acct": "a"})])
        months = inv.groupby("a")["ts"].apply(lambda s: s.dt.month.nunique())
        self.assertGreaterEqual(months.min(), 6)
        per_day = inv.groupby(["a", inv["ts"].dt.date]).size()
        self.assertEqual(per_day.max(), 1)  # at most one transaction a day, either side

    def test_planted_ids_present(self):
        tx, acc, _ = data()
        ids = set(tx["from_acct"]) | set(tx["to_acct"])
        planted = (["F01", "FO01", "C01", "C02", "C03", "O01", "V01", "H01", "M01",
                    "N01", "N02", "N03", "N04", "NF1", "NC1", "P01", "PX1",
                    "L01", "L02", "L03", "L04", "L05"]
                   + [f"FS{i:02d}" for i in range(1, 13)])
        self.assertTrue(set(planted) <= ids)
        self.assertIn("TX-OUT-1", set(tx["tx_id"]))
        self.assertEqual(tx.loc[tx["tx_id"] == "TX-OUT-1", "from_acct"].item(), "O01")
        opened = acc.set_index("acct_id")["opened_at"]
        self.assertEqual(opened["M01"], pd.Timestamp("2026-08-01"))
        for n in ["N01", "N02", "N03", "N04"]:
            first = tx.loc[(tx["from_acct"] == n) | (tx["to_acct"] == n), "ts"].min()
            self.assertEqual(first.month, 8)
            self.assertTrue(pd.Timedelta(0) < first - opened[n] <= pd.Timedelta(days=30))
        cases = data()[2]["cases"]
        for name in cases:
            for a in cases[name]["accounts"]:
                self.assertIn(a, ids)

    def test_answer_key_shape(self):
        key = data()[2]
        for field in ["recipes", "mule_accounts", "networks", "unified_findings",
                      "no_accounts_basis", "findings", "cases", "conventions"]:
            self.assertIn(field, key)
        self.assertEqual(sorted(key["recipes"]), sorted(RECIPE_IDS))
        self.assertEqual(key["no_accounts_basis"], "first_seen")
        self.assertEqual(key["unified_findings"], len(key["findings"]))
        for f in key["findings"]:
            self.assertEqual(set(f), {"entity_type", "entity_id", "risk", "period"})
        net = key["networks"][0]
        self.assertEqual(set(net["roles"]), set(net["members"]))
        self.assertTrue(set(key["mule_accounts"]) <= set(net["members"]) | {"M01"})
        for case in key["cases"].values():
            self.assertEqual(set(case), {"accounts", "intended_recipes", "notes"})
            self.assertTrue(set(case["intended_recipes"]) <= set(RECIPE_IDS))
        # recipes map == union of the cases' intentions
        from_cases = defaultdict(set)
        for case in key["cases"].values():
            for rid in case["intended_recipes"]:
                from_cases[rid] |= set(case["accounts"])
        for rid, ids in key["recipes"].items():
            self.assertTrue(set(ids) <= from_cases[rid] | {"NET-1"}, rid)
        json.dumps(key)

    def test_no_accounts_variant(self):
        tx, acc, key = msd.make(with_accounts=False)
        self.assertIsNone(acc)
        self.assertEqual(key["no_accounts_basis"], "first_seen")
        tx = tx.assign(ts=pd.to_datetime(tx["ts"]))
        for side in ("any", "sender"):
            self.assertEqual(ref_new_acct(tx, None, "first_seen", side), set(key["recipes"]["MULE-NEW-ACCT"]))

    def test_written_files_match_make(self):
        samples = ROOT / "samples"
        tx, acc, key = msd.make()
        pd.testing.assert_frame_equal(pd.read_csv(samples / "transactions.csv", dtype=str),
                                      tx.astype(str), check_dtype=False)
        self.assertEqual(len(pd.read_csv(samples / "accounts.csv")), len(acc))
        self.assertEqual(json.loads((samples / "answer_key.json").read_text(encoding="utf-8")), key)


# ---------------------------------------------------------------- grounding tests
class TestAnswerKeyGrounded(unittest.TestCase):
    def setUp(self):
        self.tx, self.acc, self.key = data()
        self.r = {k: set(v) for k, v in self.key["recipes"].items()}

    def test_stat_mad(self):
        for by_channel in (False, True):
            self.assertEqual(ref_stat_mad(self.tx, by_channel), {"TX-OUT-1"})
        self.assertEqual(self.r["STAT-MAD"], {"O01"})

    def test_velocity(self):
        for prior_only in (True, False):
            self.assertEqual(ref_velocity(self.tx, prior_only), self.r["BEH-VELOCITY"])

    def test_spike(self):
        z = ref_monthly_z(self.tx)
        flagged = {a for (a, _), v in z.items() if v > CFG["BEH.DEVIATION"]}
        self.assertEqual(flagged, self.r["BEH-SPIKE"])
        self.assertLess(abs(z[("P01", "2026-08")]), CFG["BEH.DEVIATION"])
        self.assertNotIn(("O01", "2026-08"), z)  # O01 has < spike_months of history

    def test_offhours(self):
        self.assertEqual(ref_offhours(self.tx), self.r["TEMP-OFFHOURS"])

    def test_cycle(self):
        self.assertEqual(ref_cycles(self.tx), self.r["NET-CYCLE"])

    def test_funnel(self):
        self.assertEqual(ref_funnel(self.tx), self.r["NET-FUNNEL"])
        f01_in = self.tx[self.tx["to_acct"] == "F01"]
        f01_out = self.tx[self.tx["from_acct"] == "F01"]
        self.assertGreaterEqual(f01_in["from_acct"].nunique(), 10)
        self.assertLessEqual(f01_out["ts"].max() - f01_in["ts"].min(), pd.Timedelta(days=7))
        self.assertGreaterEqual(f01_out["amount"].sum() / f01_in["amount"].sum(), 0.8)

    def test_dwell(self):
        pairs = ref_dwell_pairs(self.tx)
        flagged = {a for a, n in pairs.items() if n >= CFG["MULE.DWELL_MIN_PAIRS"]}
        self.assertEqual(flagged, self.r["MULE-DWELL"])

    def test_new_acct_all_bases(self):
        for side in ("any", "sender"):
            for basis in ("opened_at", "first_seen"):
                self.assertEqual(ref_new_acct(self.tx, self.acc, basis, side),
                                 self.r["MULE-NEW-ACCT"], (basis, side))

    def test_cpty(self):
        self.assertEqual(ref_cpty_profile(self.tx), self.r["CPTY-PROFILE"])
        for basis in ("sent", "all"):
            self.assertEqual(ref_cpty_new_large(self.tx, basis), self.r["CPTY-NEW-LARGE"])
        p01 = self.tx[self.tx["from_acct"] == "P01"]
        px1 = p01[p01["to_acct"] == "PX1"]
        self.assertEqual(len(px1), 1)
        self.assertGreaterEqual(px1["amount"].item(), 5 * p01["amount"].median())

    def test_layering(self):
        self.assertEqual(ref_layering(self.tx), self.r["FLOW-LAYERING"])
        chain = ["L01", "L02", "L03", "L04", "L05"]
        hops = [self.tx[(self.tx["from_acct"] == a) & (self.tx["to_acct"] == b)].iloc[0]
                for a, b in zip(chain, chain[1:])]
        for prev, nxt in zip(hops, hops[1:]):
            self.assertGreaterEqual(nxt["amount"] / prev["amount"], 0.92)
            self.assertLessEqual(nxt["ts"] - prev["ts"], pd.Timedelta(days=1))

    def test_mule_pattern_and_network(self):
        sig = ref_signals(self.tx, self.acc)
        for rid in MULE_SIGNALS:
            self.assertEqual(sig[rid], self.r[rid], rid)
        count = defaultdict(int)
        for ids in sig.values():
            for a in ids:
                count[a] += 1
        mules = {a for a, n in count.items() if n >= CFG["MULE.MIN_SIGNALS"]}
        self.assertEqual(mules, self.r["MULE-PATTERN"])
        self.assertEqual(mules, set(self.key["mule_accounts"]))
        nets, roles = ref_network(self.tx, mules)
        self.assertEqual(len(nets), len(self.key["networks"]))
        self.assertEqual(nets[0], set(self.key["networks"][0]["members"]))
        self.assertEqual({a: roles[a] for a in nets[0]}, self.key["networks"][0]["roles"])
        self.assertEqual({a for a, r in roles.items() if r != "mule"}, self.r["MULE-CROSS-TX"])

    def test_no_normal_account_flagged(self):
        flagged = set().union(*self.r.values())
        self.assertFalse({a for a in flagged if is_normal(a)})

    def test_findings_follow_unify_rules(self):
        """Unify on entity + risk + month, absorb mule signals into R2, one R3 per network."""
        risk = {rid: "R1" for rid in R1_RECIPES}
        risk.update({"MULE-PATTERN": "R2", "CPTY-PROFILE": "R4", "CPTY-NEW-LARGE": "R4"})
        mules = set(self.key["mule_accounts"])
        expected = set()
        for rid, ids in self.r.items():
            if rid in ("MULE-CROSS-TX", "MULE-NETWORK"):
                continue
            for a in ids:
                if risk[rid] == "R1" and a in mules and rid in MULE_SIGNALS:
                    continue  # absorbed into the R2 finding of the same month
                expected.add(("account", a, risk[rid], "2026-08"))
        for net in self.key["networks"]:
            expected.add(("network", net["network_id"], "R3", "2026-08"))
        got = {(f["entity_type"], f["entity_id"], f["risk"], f["period"]) for f in self.key["findings"]}
        self.assertEqual(got, expected)
        self.assertEqual(len(self.key["findings"]), len(got))


if __name__ == "__main__":
    unittest.main()
