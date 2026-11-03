"""Deterministic sample data for AIDA phase B1 (use case: Mule Accounts).

make(seed) returns (transactions, accounts, answer_key); main() writes them to
aida-knowledge/samples/. Normal accounts A0001-A0300 never meet a planted rule;
the planted cases (all in 2026-08) are built so each one triggers exactly the
recipes listed in answer_key["cases"]. Only `seed` changes the normal data; the
planted cases and the answer key are the same for every seed.

Normal data design (why no recipe fires on it):
- A0001-A0100 only send, A0101-A0300 only receive -> no cycles, no dwell, no layering.
- Each sender has 3 fixed receivers, all used in January -> no new counterparties later.
- Every normal account is in at most one transaction a day (either side), weekdays 09:00-17:00.
- A sender makes the same number of transfers every month and its monthly total follows
  MONTH_PATTERN (within 3 % of the mean) -> no velocity or spike against any baseline.
- Amounts are lognormal around a per-sender median drawn from 1,000-7,000, so the
  Modified Z-Score of every amount stays far below STAT.MAD.THRESHOLD.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261103
PLANT_SEED = 1103  # planted cases use their own generator, independent of `seed`
OUT_DIR = Path(__file__).resolve().parent.parent / "samples"
PERIOD = "2026-08"
TS_FORMAT = "%Y-%m-%d %H:%M:%S"
CHANNELS = ["mobile", "internet", "branch"]
MONTH_PATTERN = [1.03, 0.97, 1.03, 0.97, 1.02, 0.98, 1.00, 1.00]  # Jan..Aug
PAYERS = [f"A{i:04d}" for i in range(1, 101)]
PAYEES = [f"A{i:04d}" for i in range(101, 301)]
MULES = ["M01", "N01", "N02", "N03", "N04"]
NETWORK = ["N01", "N02", "N03", "N04", "NF1", "NC1"]
OPENED = {"M01": "2026-08-01", "N01": "2026-07-15", "N02": "2026-07-17",
          "N03": "2026-07-20", "N04": "2026-07-22"}


def _weekdays(month):
    days = pd.date_range(f"2026-{month:02d}-01", periods=31, freq="D")
    return [d for d in days if d.month == month and d.dayofweek < 5]


def _split(rng, n, total):
    """n lognormal amounts (sigma 0.1) that add up to `total`."""
    raw = rng.lognormal(0.0, 0.1, n)
    return np.round(raw / raw.sum() * total, 2)


class _Book:
    def __init__(self):
        self.rows, self.counters = [], {}

    def add(self, tag, ts, frm, to, amount, channel="mobile", tx_id=None):
        if tx_id is None:
            self.counters[tag] = self.counters.get(tag, 0) + 1
            tx_id = f"{tag}-{self.counters[tag]:03d}"
        self.rows.append({"tx_id": tx_id, "ts": pd.Timestamp(ts), "from_acct": frm, "to_acct": to,
                          "amount": round(float(amount), 2), "currency": "THB", "channel": channel})


# ---------------------------------------------------------------- normal data
def _payee_sets(rng):
    slots = list(rng.permutation(PAYEES)) + list(rng.choice(PAYEES, 100, replace=False))
    while True:
        grid = rng.permutation(slots).reshape(len(PAYERS), 3)
        if all(len(set(row)) == 3 for row in grid):
            return {p: list(row) for p, row in zip(PAYERS, grid)}


def _normal_rows(rng):
    payees = _payee_sets(rng)
    median = {p: rng.uniform(1000, 7000) for p in PAYERS}
    per_month = {p: int(rng.choice([5, 6, 7])) for p in PAYERS}
    busy, rows = set(), []
    for month in range(1, 9):
        days = _weekdays(month)
        for payer in rng.permutation(PAYERS):
            k = per_month[payer]
            amounts = _split(rng, k, k * median[payer] * MONTH_PATTERN[month - 1])
            for j in range(k):
                mine = payees[payer]  # rotation: every receiver gets a transfer every month
                prefs = [mine[j]] if month == 1 and j < 3 else [mine[(j + i) % 3] for i in range(3)]
                day, payee = None, None
                for pe in prefs:
                    free = [d for d in days if (payer, d) not in busy and (pe, d) not in busy]
                    if free:
                        day, payee = free[int(rng.integers(len(free)))], pe
                        break
                assert day is not None, (payer, month)
                busy |= {(payer, day), (payee, day)}
                ts = day + pd.Timedelta(hours=int(rng.integers(9, 17)), minutes=int(rng.integers(0, 60)))
                rows.append({"ts": ts, "from_acct": payer, "to_acct": payee, "amount": float(amounts[j]),
                             "currency": "THB", "channel": str(rng.choice(CHANNELS, p=[0.5, 0.3, 0.2]))})
    df = pd.DataFrame(rows).sort_values(["ts", "from_acct"]).reset_index(drop=True)
    df.insert(0, "tx_id", [f"T{i:06d}" for i in range(1, len(df) + 1)])
    return df


# ---------------------------------------------------------------- planted cases
def _at(day, hhmm):
    return pd.Timestamp(f"{day} {hhmm}:00")


def _mule(book, tag, acct, days, base_in, base_out, spike_in, spike_out, amount, offset):
    """6 calm days (1 inflow, then 1 or 2 outflows 4 h later), then one burst day of
    alternating in/out transfers: dwell pairs, velocity spike and >= 20 transfers sent."""
    off = pd.Timedelta(minutes=offset)
    for day, src, sinks in zip(days[:6], base_in, base_out):
        book.add(tag, _at(day, "10:00") + off, src, acct, amount)
        for i, sink in enumerate(sinks):
            book.add(tag, _at(day, "14:00") + off + pd.Timedelta(minutes=30 * i), acct, sink,
                     round(amount * 0.92 / len(sinks), 2))
    for j, src in enumerate(spike_in):
        t = _at(days[6], "09:00") + off + pd.Timedelta(minutes=20 * j)
        book.add(tag, t, src, acct, amount)
        book.add(tag, t + pd.Timedelta(minutes=10), acct, spike_out, round(amount * 0.92, 2))


def _history(book, prng, tag, acct, cps, months, counts, unit, skip=()):
    """Regular history: per month len(counts) active days with counts[i] transfers,
    counterparties in rotation, monthly total = sum(counts) * unit * MONTH_PATTERN.
    Returns the rotation position so a caller can continue it."""
    cp = 0
    for month in months:
        free = [d for d in _weekdays(month) if d.strftime("%Y-%m-%d") not in skip]
        days = sorted(prng.choice(free, len(counts), replace=False))
        amounts = iter(_split(prng, sum(counts), sum(counts) * unit * MONTH_PATTERN[month - 1]))
        for day, n in zip(days, counts):
            for i in range(n):
                t = pd.Timestamp(day) + pd.Timedelta(hours=10 + 4 * i, minutes=int(prng.integers(0, 60)))
                book.add(tag, t, acct, cps[cp % len(cps)], next(amounts))
                cp += 1
    return cp


def _planted_rows():
    prng = np.random.default_rng(PLANT_SEED)
    book = _Book()

    # 1. Funnel: FS01-FS12 -> F01 (Mon-Tue), F01 -> FO01 90 % on Wed, > 24 h after the last inflow.
    fs = [f"FS{i:02d}" for i in range(1, 13)]
    fs_amounts = [2700 + 50 * i for i in range(1, 13)]
    for i, (src, amt) in enumerate(zip(fs, fs_amounts)):
        day = "2026-08-10" if i < 6 else "2026-08-11"
        book.add("FUN", _at(day, "09:15") + pd.Timedelta(minutes=15 * (i % 6)), src, "F01", amt)
    out = round(0.9 * sum(fs_amounts) / 4, 2)
    for i in range(4):
        book.add("FUN", _at("2026-08-12", "13:00") + pd.Timedelta(minutes=30 * i), "F01", "FO01", out)

    # 2. Cycle C01 -> C02 -> C03 -> C01 within 5 days; each hop passes only 70 % (no layering).
    book.add("CYC", _at("2026-08-17", "10:00"), "C01", "C02", 7000)
    book.add("CYC", _at("2026-08-19", "11:00"), "C02", "C03", 4900)
    book.add("CYC", _at("2026-08-21", "14:00"), "C03", "C01", 3400)

    # 3. Outlier: O01 has a short regular history (Apr-Aug, < spike_months) and one huge transfer.
    _history(book, prng, "OUT", "O01", ["OR1", "OR2"], range(4, 9), [1, 1, 1, 1], 2500, skip={"2026-08-14"})
    book.add("OUT", _at("2026-08-14", "10:15"), "O01", "OR1", 480000, channel="branch", tx_id="TX-OUT-1")

    # 4. Velocity (+ monthly spike): V01 regular since January, then 12 transfers on 2026-08-12.
    vx = [f"VX{i:02d}" for i in range(1, 13)]
    pattern = [1, 2, 1, 1, 2, 1]
    cp = _history(book, prng, "VEL", "V01", vx, range(1, 8), pattern, 3000)
    calm = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10"]
    for day, n in zip(calm, pattern):
        for i in range(n):
            book.add("VEL", _at(day, "10:20") + pd.Timedelta(hours=4 * i), "V01", vx[cp % 12], 3000)
            cp += 1
    for j in range(12):
        book.add("VEL", _at("2026-08-12", "09:00") + pd.Timedelta(minutes=30 * j), "V01", vx[j], 3000)

    # 5. Off-hours: H01 (no history) sends 5 transfers at night or on weekends.
    for ts, amt in [("2026-08-08 11:00", 3500), ("2026-08-12 21:30", 4200), ("2026-08-13 06:45", 3900),
                    ("2026-08-15 14:00", 4500), ("2026-08-18 23:10", 3800)]:
        book.add("OFF", f"{ts}:00", "H01", "HX1", amt)

    # 6. Single mule M01 (opened 2026-08-01): 18 distinct sources, sinks MO1-MO3.
    mule_days = calm + ["2026-08-11"]
    ms = [f"MS{i:02d}" for i in range(1, 19)]
    _mule(book, "MUL", "M01", mule_days, ms[:6],
          [["MO1"], ["MO1", "MO1"], ["MO1"], ["MO2", "MO2"], ["MO2"], ["MO2", "MO2"]],
          ms[6:], "MO3", 5000, 0)

    # 7. Mule network: NF1 feeds N01-N04 on day 1, N01-N04 pay NC1 on day 3.
    for k, n in enumerate(["N01", "N02", "N03", "N04"], start=1):
        no = f"NO{k}"
        _mule(book, "NET", n, mule_days, ["NF1"] + [f"NB{k}"] * 5,
              [[no], [no, no], ["NC1"], [no, no], [no], [no, no]],
              [f"NS{k}"] * 12, f"NZ{k}", 3600 + 400 * k, 5 * k)

    # 8. New large counterparty: P01 regular to PR1-PR3 since January, August only P01 -> PX1.
    _history(book, prng, "CPN", "P01", ["PR1", "PR2", "PR3"], range(1, 8), [1] * 10, 700)
    p01 = [r["amount"] for r in book.rows if r["from_acct"] == "P01"]
    book.add("CPN", _at("2026-08-19", "11:00"), "P01", "PX1", round(10 * float(np.median(p01)), 2),
             tx_id="TX-NEWCP-1")

    # 9. Layering L01 -> L02 -> L03 -> L04 -> L05: each hop forwards >= 92 % within a day.
    for ts, frm, to, amt in [("2026-08-24 09:30", "L01", "L02", 7600), ("2026-08-24 14:00", "L02", "L03", 7100),
                             ("2026-08-25 10:00", "L03", "L04", 6650), ("2026-08-25 15:30", "L04", "L05", 6200)]:
        book.add("LAY", f"{ts}:00", frm, to, amt)
    return pd.DataFrame(book.rows)


# ---------------------------------------------------------------- answer key
CASES = {
    "funnel": {
        "accounts": ["F01"], "intended_recipes": ["NET-FUNNEL"],
        "notes": "FS01-FS12 send 12 transfers to F01 on 2026-08-10/11; F01 forwards 90% to FO01 on 2026-08-12, "
                 "more than 24 h after the last inflow (no dwell). 16 transfers, 3 active days, no history: "
                 "no velocity, new-account or counterparty-profile signal. Outflows are 2.7x the account median."},
    "cycle": {
        "accounts": ["C01", "C02", "C03"], "intended_recipes": ["NET-CYCLE"],
        "notes": "C01->C02 (08-17), C02->C03 (08-19), C03->C01 (08-21), time-ordered within 30 days. "
                 "Each hop passes 70%, below FLOW.MIN_PASS_RATIO, so it is not layering."},
    "outlier": {
        "accounts": ["O01"], "intended_recipes": ["STAT-MAD"],
        "notes": "TX-OUT-1 (480,000 to its regular counterparty OR1) is the only amount with |Modified Z| > 3.5, "
                 "globally and per channel. O01 starts in April (5 months < spike_months), so BEH-SPIKE "
                 "has no baseline; OR1 is not a new counterparty."},
    "velocity": {
        "accounts": ["V01"], "intended_recipes": ["BEH-VELOCITY", "BEH-SPIKE"],
        "notes": "Regular since January (1-2 transfers per active day to VX01-VX12, stable monthly totals). "
                 "2026-08-12: 12 transfers in one day (velocity) which also lifts the August total far "
                 "above the monthly baseline (spike). All counterparties already known."},
    "offhours": {
        "accounts": ["H01"], "intended_recipes": ["TEMP-OFFHOURS"],
        "notes": "5 transfers to HX1 on Saturdays or outside 08:00-18:00. Only 5 transfers, no history."},
    "single_mule": {
        "accounts": ["M01"],
        "intended_recipes": ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "MULE-PATTERN"],
        "notes": "Opened 2026-08-01. 6 calm days (counts sent 1,2,1,2,1,2) then 12 in/12 out on 2026-08-11. "
                 "18 distinct sources MS01-MS18, out/in 0.92, inflows forwarded within 4 h, 21 transfers sent "
                 "(39 in total) within 30 days of opening: 4 of 5 mule signals. No link to other mules."},
    "mule_network": {
        "accounts": ["N01", "N02", "N03", "N04", "NF1", "NC1"],
        "intended_recipes": ["MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "MULE-PATTERN",
                             "MULE-CROSS-TX", "MULE-NETWORK"],
        "notes": "N01-N04 opened 2026-07-15..22, same shape as M01 but only 3 sources each (NF1, NBk, NSk): "
                 "dwell + new account + velocity = 3 signals. NF1 pays all four on 2026-08-03 (feeder), all "
                 "four pay NC1 on 2026-08-05 (collector). Sinks NOk/NZk receive from one mule only."},
    "new_large_counterparty": {
        "accounts": ["P01"], "intended_recipes": ["CPTY-NEW-LARGE", "CPTY-PROFILE"],
        "notes": "10 transfers a month to PR1-PR3 since January (median about 700). In August its only transfer "
                 "is TX-NEWCP-1 to PX1 at 10x the median: new counterparty with large amount, and 100% new "
                 "counterparties in a month with 7 months of history. August total equals the monthly "
                 "baseline, so no BEH-SPIKE."},
    "layering": {
        "accounts": ["L01", "L02", "L03", "L04", "L05"], "intended_recipes": ["FLOW-LAYERING"],
        "notes": "7,600 -> 7,100 -> 6,650 -> 6,200 on 2026-08-24/25: 4 hops, each forwarding >= 93% "
                 "within a day."},
}

CONVENTIONS = {
    "attribution": "STAT-MAD, BEH-VELOCITY, BEH-SPIKE, TEMP-OFFHOURS, CPTY-PROFILE and CPTY-NEW-LARGE "
                   "flag the sending account (from_acct).",
    "baselines": "BEH-VELOCITY needs >= velocity_days prior active days; BEH-SPIKE and CPTY-PROFILE need "
                 ">= spike_months prior active months.",
    "NET-CYCLE": "every account on the cycle", "FLOW-LAYERING": "every account on a qualifying path",
    "NET-FUNNEL / MULE-DWELL": "the account that receives and forwards",
    "MULE-NEW-ACCT": "same result whether transfers are counted on both sides or sent only, and for "
                     "basis opened_at or first_seen",
    "MULE-CROSS-TX": "the collector and feeder accounts (no mule-to-mule transfer is planted)",
    "MULE-NETWORK": "network ids NET-<n>",
    "period": "every planted finding is in 2026-08",
}


def _answer_key():
    recipes = {rid: [] for rid in [
        "STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE", "NET-FUNNEL",
        "MULE-DWELL", "MULE-NEW-ACCT", "MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK",
        "CPTY-PROFILE", "CPTY-NEW-LARGE", "FLOW-LAYERING"]}
    for case in CASES.values():
        for rid in case["intended_recipes"]:
            if rid == "MULE-CROSS-TX":
                recipes[rid] += ["NC1", "NF1"]
            elif rid == "MULE-NETWORK":
                recipes[rid] += ["NET-1"]
            else:
                recipes[rid] += [a for a in case["accounts"] if a not in ("NF1", "NC1")]
    recipes = {rid: sorted(set(ids)) for rid, ids in recipes.items()}
    # Hand-derived from spec 4.7/4.8: one finding per entity + risk + month; R1 mule signals of
    # M01 and N01-N04 are absorbed into their R2 finding; one R3 finding for the network.
    findings = (
        [("account", a, "R1") for a in ["F01", "C01", "C02", "C03", "O01", "V01", "H01",
                                        "L01", "L02", "L03", "L04", "L05"]]
        + [("account", a, "R2") for a in MULES]
        + [("network", "NET-1", "R3"), ("account", "P01", "R4")])
    findings = [{"entity_type": t, "entity_id": e, "risk": r, "period": PERIOD} for t, e, r in findings]
    return {
        "recipes": recipes,
        "mule_accounts": MULES,
        "networks": [{"network_id": "NET-1", "members": NETWORK,
                      "roles": {"N01": "mule", "N02": "mule", "N03": "mule", "N04": "mule",
                                "NF1": "feeder", "NC1": "collector"}}],
        "network_count": 1,
        "findings": findings,
        "unified_findings": len(findings),
        "no_accounts_basis": "first_seen",
        "cases": CASES,
        "conventions": CONVENTIONS,
    }


# ---------------------------------------------------------------- assembly
def _accounts(rng, accts):
    rows = []
    for a in sorted(accts):
        if a in OPENED:
            opened = pd.Timestamp(OPENED[a])
        else:
            opened = pd.Timestamp("2015-01-01") + pd.Timedelta(days=int(rng.integers(0, 3986)))
        kind = "business" if a in PAYEES or a in ("FO01", "NC1", "PX1") else "individual"
        rows.append({"acct_id": a, "opened_at": opened.strftime(TS_FORMAT), "account_type": kind})
    return pd.DataFrame(rows)


def make(seed: int = SEED, with_accounts: bool = True):
    """Return (transactions, accounts, answer_key). accounts is None when with_accounts=False."""
    rng = np.random.default_rng(seed)
    tx = pd.concat([_normal_rows(rng), _planted_rows()], ignore_index=True)
    tx = tx.sort_values(["ts", "tx_id"]).reset_index(drop=True)
    tx["ts"] = tx["ts"].dt.strftime(TS_FORMAT)
    tx = tx[["tx_id", "ts", "from_acct", "to_acct", "amount", "currency", "channel"]]
    accounts = None
    if with_accounts:
        accounts = _accounts(np.random.default_rng(PLANT_SEED), set(tx["from_acct"]) | set(tx["to_acct"]))
    return tx, accounts, _answer_key()


def main():
    tx, accounts, key = make()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tx.to_csv(OUT_DIR / "transactions.csv", index=False)
    accounts.to_csv(OUT_DIR / "accounts.csv", index=False)
    (OUT_DIR / "answer_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")
    print(f"wrote {len(tx)} transactions, {len(accounts)} accounts, "
          f"{key['unified_findings']} expected findings to {OUT_DIR}")


if __name__ == "__main__":
    main()
