"""Deterministic sample data for AIDA C2, data type F (mutual fund investor transactions).

make(seed) returns (frames, key): frames = {"fund_txn", "unitholders"}. Only `seed` changes the normal data; the
planted cases and the answer key are the same for every seed.

The counterparty column (bank_account) holds the ACCOUNT OWNER: the unitholder id of the owner of the account that
pays or receives the money (U-nnnn, the same format as unitholder_id), so FUND-THIRD-PARTY can compare it with the
unitholder. A shared account whose owner is not known is written as its account number (BA-7000): a different format,
which rule F-R2 cannot compare, while F-R3 (one counterparty, many unitholders) still counts it.

Normal data design (why no check fires on it):
- 132 normal unitholders U-1001..U-1132, one fund and one fixed amount per holder (stratified uniform 3,000-9,999, no round
  amount, so no outlier inside an agent's group), 2026-01..10: 60 holders buy every month (A), 30 redeem every month (B), 30 switch out and in
  (SWO, SWI) on the same day every month (C): so 1 or 2 transactions per holder per month, the monthly total of a
  holder is flat (no spike) and no amount repeats three times in a period. 8 holders (D) buy and sell the same fund
  55+ days later at 90-110 % of the amount, 4 (E) sell 10-25 days after the purchase at 40-55 %: near misses of F-R1.
- Weekdays only, day 5-24, order time 09:00-15:00 (before the 15:30 cut-off), NAV date = order date. Five orders
  after the cut-off (15:40-16:20) are priced on the next business day: they are normal and must not be reported.
- Counterparty = the unitholder (the owner of the account is the holder). 12 agents AG-01..AG-12; AG-05 has 9 normal
  holders, the other 123 are dealt to the other 11 agents in the order of their amounts.

Planted cases (ids in the key):
- U-0101 buys FX1 on 2026-05-06 and sells it on 2026-05-15 (9 days) at 98 %                 -> FUND-ROUNDTRIP, F-R1
- U-0202 redeems FX2 on 2026-06-17 to an account whose owner is U-0999                      -> FUND-THIRD-PARTY, F-R2
- BA-7000 receives the redemptions of U-0301..U-0304                                        -> FUND-SHARED-ACCT, F-R3
- U-0404 makes 10 transactions in 2026-07                                                   -> FUND-FREQUENT, F-R4
- AG-05: 15 clients, 6 of them (U-0501..U-0506, 40 %) make 8 transactions in 2026-08         -> FUND-CHURN, F-R5
  (those six are F-R4 findings too)
- O-6006: U-0606 buys FX6 on 2026-09-16 at 16:10 with NAV date 2026-09-16                   -> FUND-LATE-TRADE, F-R6
"""
import numpy as np
import pandas as pd

import make_sample_c as msc
import sample_common as sc

SEED = 20261109
N_A, N_B, N_C, N_D, N_E = 60, 30, 30, 8, 4
N_LATE_DECOY = 5
MONTHS = range(1, 11)
AGENTS = [f"AG-{k:02d}" for k in range(1, 13)]
FOCUS_AGENT = "AG-05"
N_AG05_NORMAL = 9
FUNDS = [f"FX{k}" for k in range(1, 9)]
FREQ_HOLDERS = [f"U-05{k:02d}" for k in range(1, 7)]

TABLES = {"fund_txn": ["order_id", "unitholder_id", "fund_code", "order_datetime", "txn_type", "amount",
                       "bank_account", "agent", "nav_date"],
          "unitholders": ["unitholder_id", "open_date"]}
ROLES_EN = {"fund_txn": {"order_id": "record_id", "unitholder_id": "entity", "fund_code": "contract",
                         "order_datetime": "date", "txn_type": "category", "amount": "amount",
                         "bank_account": "counterparty", "agent": "channel", "nav_date": "due_date"},
            "unitholders": {"unitholder_id": "entity", "open_date": "opened_at"}}
VARIANT_NAMES = {
    "en": {"fund_txn": {}, "unitholders": {}},
    "th": {"fund_txn": {"order_id": "รหัสคำสั่ง", "unitholder_id": "รหัสผู้ถือหน่วย", "fund_code": "รหัสกองทุน",
                        "order_datetime": "วันเวลาที่ทำคำสั่ง", "txn_type": "ประเภทรายการ", "amount": "จำนวนเงิน",
                        "bank_account": "เจ้าของบัญชีรับจ่ายเงิน", "agent": "ตัวแทนขาย",
                        "nav_date": "วันที่ได้ราคา NAV"},
           "unitholders": {"unitholder_id": "รหัสผู้ถือหน่วย", "open_date": "วันเปิดบัญชี"}},
    "legacy": {"fund_txn": {"order_id": "COL1", "unitholder_id": "COL2", "fund_code": "COL3",
                            "order_datetime": "COL4", "txn_type": "TP", "amount": "AMT", "bank_account": "COL7",
                            "agent": "AGT", "nav_date": "COL9"},
               "unitholders": {"unitholder_id": "COL2", "open_date": "COL10"}},
}
CODE_VALUES = {"fund_txn.txn_type": {"BUY": "ซื้อหน่วยลงทุน", "SELL": "ขายคืนหน่วยลงทุน", "SWI": "สับเปลี่ยนเข้า",
                                     "SWO": "สับเปลี่ยนออก"}}

BRIEF_MD = """# หนังสือขอให้ตรวจสอบ: ธุรกรรมกองทุนรวมของผู้ถือหน่วย

เรียน ทีมวิเคราะห์ข้อมูล

ขอให้ช่วยตรวจสอบคำสั่งซื้อขายหน่วยลงทุนของกองทุนรวม ช่วงเดือนมกราคมถึงตุลาคม 2026 ไฟล์ที่ส่งมามี 2 ตาราง คือ fund_txn
(คำสั่งซื้อขาย 1 แถวต่อ 1 คำสั่ง) และ unitholders (ข้อมูลผู้ถือหน่วย) เชื่อมกันด้วยรหัสผู้ถือหน่วย

ความหมายของคอลัมน์ที่ผมทราบ: order_id คือรหัสคำสั่ง ไม่ซ้ำกัน, unitholder_id คือรหัสผู้ถือหน่วย, fund_code คือรหัสกองทุน,
order_datetime คือวันและเวลาที่ผู้ถือหน่วยทำคำสั่ง (มีเวลาเป็นชั่วโมง:นาที), txn_type คือประเภทรายการ BUY = ซื้อหน่วยลงทุน,
SELL = ขายคืนหน่วยลงทุน, SWI = สับเปลี่ยนเข้า และ SWO = สับเปลี่ยนออก, amount คือจำนวนเงินของคำสั่งนั้น, bank_account
คือเจ้าของบัญชีที่รับหรือจ่ายเงิน ระบุเป็นรหัสผู้ถือหน่วยของเจ้าของบัญชี (U-xxxx) ถ้าไม่ทราบเจ้าของบัญชีจะระบุเลขที่บัญชีธนาคาร
(BA-xxxx), agent คือรหัสตัวแทนขาย, nav_date คือวันที่ที่คำสั่งนั้นได้ราคา NAV ส่วนตาราง unitholders มี open_date
คือวันเปิดบัญชีของผู้ถือหน่วย

เวลาตัดรอบของคำสั่งคือ 15:30 น. คำสั่งที่ทำหลังเวลานี้ควรได้ราคา NAV ของวันทำการถัดไป

เงื่อนไข: ดูเฉพาะรายการระหว่าง 1 ม.ค. ถึง 31 ต.ค. 2026

สิ่งที่กังวล:
1. ผู้ถือหน่วยซื้อแล้วขายคืนกองทุนเดิมในเวลาอันสั้นด้วยจำนวนเงินใกล้เคียงกัน
2. มีการจ่ายเงินขายคืนเข้าบัญชีของบุคคลอื่นที่ไม่ใช่ผู้ถือหน่วย
3. มีคำสั่งที่ทำหลังเวลาตัดรอบแต่ได้ราคา NAV ของวันเดียวกัน

```json
{
  "context": "กองทุนรวม — คำสั่งซื้อ ขายคืน และสับเปลี่ยนหน่วยลงทุน ม.ค.–ต.ค. 2026 (fund_txn และ unitholders เชื่อมด้วยรหัสผู้ถือหน่วย)",
  "columns": {
    "order_id": "รหัสคำสั่ง ไม่ซ้ำกัน",
    "unitholder_id": "รหัสผู้ถือหน่วย",
    "fund_code": "รหัสกองทุน",
    "order_datetime": "วันและเวลาที่ผู้ถือหน่วยทำคำสั่ง มีเวลาเป็นชั่วโมง:นาที",
    "txn_type": "ประเภทรายการ BUY = ซื้อหน่วยลงทุน, SELL = ขายคืนหน่วยลงทุน, SWI = สับเปลี่ยนเข้า, SWO = สับเปลี่ยนออก",
    "amount": "จำนวนเงินของคำสั่งนั้น",
    "bank_account": "เจ้าของบัญชีที่รับหรือจ่ายเงิน เป็นรหัสผู้ถือหน่วยของเจ้าของบัญชี (U-xxxx) หรือเลขที่บัญชีธนาคาร (BA-xxxx) ถ้าไม่ทราบเจ้าของ",
    "agent": "รหัสตัวแทนขายที่ดูแลผู้ถือหน่วย",
    "nav_date": "วันที่ที่คำสั่งนั้นได้ราคา NAV",
    "open_date": "วันเปิดบัญชีของผู้ถือหน่วย"
  },
  "conditions": [
    "ดูเฉพาะรายการ 1 ม.ค. – 31 ต.ค. 2026",
    "เวลาตัดรอบของคำสั่งคือ 15:30 น."
  ],
  "concerns": [
    "ผู้ถือหน่วยซื้อแล้วขายคืนกองทุนเดิมในเวลาอันสั้นด้วยจำนวนเงินใกล้เคียงกัน",
    "มีการจ่ายเงินขายคืนเข้าบัญชีของบุคคลอื่นที่ไม่ใช่ผู้ถือหน่วย",
    "มีคำสั่งที่ทำหลังเวลาตัดรอบแต่ได้ราคา NAV ของวันเดียวกัน"
  ]
}
```
"""

# (holder, agent, open date, [(fund, type, datetime, amount, counterparty, nav date or None = same day)])
PLANTED = [
    ("U-0101", "AG-02", [("FX1", "BUY", "2026-05-06 10:12:00", 8483.60, "U-0101"),
                         ("FX1", "SELL", "2026-05-15 11:40:00", 8313.93, "U-0101")]),
    ("U-0202", "AG-03", [("FX2", "BUY", "2026-02-10 10:05:00", 7480.10, "U-0202"),
                         ("FX2", "SELL", "2026-06-17 13:22:00", 3650.75, "U-0999")]),
    ("U-0301", "AG-04", [("FX3", "BUY", "2026-01-14 09:48:00", 8240.50, "U-0301"),
                         ("FX3", "SELL", "2026-06-10 10:30:00", 4120.25, "BA-7000")]),
    ("U-0302", "AG-04", [("FX3", "BUY", "2026-02-11 11:15:00", 9115.30, "U-0302"),
                         ("FX3", "SELL", "2026-07-15 14:05:00", 4557.65, "BA-7000")]),
    ("U-0303", "AG-04", [("FX3", "BUY", "2026-03-12 10:55:00", 6870.25, "U-0303"),
                         ("FX3", "SELL", "2026-08-12 09:35:00", 3435.10, "BA-7000")]),
    ("U-0304", "AG-04", [("FX3", "BUY", "2026-04-15 13:40:00", 7560.75, "U-0304"),
                         ("FX3", "SELL", "2026-09-16 12:10:00", 3780.40, "BA-7000")]),
    ("U-0606", "AG-07", [("FX6", "BUY", "2026-09-16 16:10:00", 7315.40, "U-0606")]),
]
LATE_PLANTED_ID = "O-6006"
FREQ_TYPES = ["BUY", "BUY", "BUY", "BUY", "SWO", "SWI", "SWO", "SWI", "SWO", "SWI"]


def _answer_key():
    findings = [("unitholder", "U-0101", "F-R1", "2026-05"), ("unitholder", "U-0202", "F-R2", "2026-06"),
                ("account", "BA-7000", "F-R3", "2026-09"), ("unitholder", "U-0404", "F-R4", "2026-07"),
                ("agent", FOCUS_AGENT, "F-R5", "2026-08"), ("unitholder", "U-0606", "F-R6", "2026-09")]
    findings += [("unitholder", u, "F-R4", "2026-08") for u in FREQ_HOLDERS]
    recipes = {"STAT-MAD": [], "BEH-VELOCITY": [], "BEH-SPIKE": [], "TEMP-OFFHOURS": [], "GEN-CONC": [],
               "GEN-PERIOD-END": [], "FOR-BENFORD": [], "FOR-ROUND": [], "FOR-REPEAT": [],
               "FUND-ROUNDTRIP": ["U-0101"], "FUND-THIRD-PARTY": ["U-0202"], "FUND-SHARED-ACCT": ["BA-7000"],
               "FUND-FREQUENT": ["U-0404"] + FREQ_HOLDERS, "FUND-CHURN": [FOCUS_AGENT],
               "FUND-LATE-TRADE": [LATE_PLANTED_ID]}
    return {
        "recipes": recipes,
        "findings": [{"entity_type": t, "entity_id": e, "risk": r, "period": p} for t, e, r, p in findings],
        "code_values": {k: dict(v) for k, v in CODE_VALUES.items()},
        "concern_risks": ["F-R1", "F-R2", "F-R6"],
        "intake": {
            "sufficiency": {"F-R1": "พร้อม", "F-R2": "พร้อม", "F-R6": "พร้อม"},
            "data_request": [],
            "suggested_risks": ["F-R3", "F-R4", "F-R5"],
            "description_conflicts": [],
        },
        "conventions": {
            "entities": "findings are keyed by the check's own entity: FUND-ROUNDTRIP, FUND-THIRD-PARTY and "
                        "FUND-FREQUENT name the unitholder (unitholder_id); FUND-SHARED-ACCT the account "
                        "(bank_account value); FUND-CHURN the agent; FUND-LATE-TRADE the order id (the finding row "
                        "of F-R6 is keyed by the unitholder U-0606 in findings, the order is O-6006). entity_type "
                        "labels: unitholder / fund / account / agent",
            "period": "the period is the month of the record that completes the pattern: the sale (F-R1, F-R2), the "
                      "transactions of the month (F-R4, F-R5), the order (F-R6); for a pattern over several records "
                      "the latest month of the contributing records (BA-7000 2026-09)",
            "counterparty": "bank_account holds the ACCOUNT OWNER: the unitholder id (U-nnnn, the unitholder_id format) "
                            "of the owner of the account paid or receiving, so FUND-THIRD-PARTY can compare it with "
                            "the unitholder. BA-5555 of the design belongs to U-0999: it is written as its owner U-0999 "
                            "on the redemption of U-0202 (F-R2 reports U-0202). The shared account of F-R3 is written "
                            "as its number BA-7000 (owner not known): F-R3 reports it, F-R2 cannot compare that format "
                            "and must not report the four holders",
            "F-R4": "U-0404 makes 10 transactions in 2026-07 (4 BUY, 3 SWO, 3 SWI in 7 funds, no SELL); the six "
                    "clients of AG-05 (U-0501..U-0506) make 8 each in 2026-08 (4 BUY, 2 SWO, 2 SWI); they are F-R4 "
                    "findings too, because FUND-FREQUENT reports every holder with 6+ transactions in a month. "
                    "Normal holders make 1 or 2 a month",
            "F-R5": "AG-05 has 15 clients, 6 of them (40 %) hit F-R4; AG-06 (U-0404's agent) has 1 frequent client "
                    "of 12 and is not reported",
            "F-R1": "U-0101 buys FX1 2026-05-06 and sells it 2026-05-15 (9 days, 98 % of the purchase). Near misses "
                    "that must not be reported: 8 holders sell the same fund 55+ days later at 90-110 %, 4 holders "
                    "sell within 10-25 days at 40-55 %. Switches are never sales",
            "F-R6": "O-6006 (U-0606) was ordered 2026-09-16 16:10 with NAV date 2026-09-16 (after the 15:30 "
                    "cut-off and priced the same day). Five normal orders after the cut-off (15:40-16:20) are priced "
                    "on the next business day and must not be reported. In variants/date_only the time of day is "
                    "missing: F-R6 cannot be judged",
            "date_only": {"sufficiency": {"F-R6": "บางส่วน"},
                          "data_request": ["วันที่ของคำสั่งซื้อขายที่มีเวลา (ชั่วโมง:นาที) เพื่อดูคำสั่งที่ทำหลังเวลาตัดรอบ"],
                          "note": "variants/date_only/fund_txn.csv has order_datetime as a date only; every other "
                                  "table and the roles are the en variant. FUND-LATE-TRADE is Skipped with a reason "
                                  "and F-R6 is 🟡 (บางส่วน) with this Data Request, as the spec says"},
            "normal": "every other holder: one fund and one fixed amount, 1-2 transactions a month for 10 months, "
                      "weekdays day 5-24, 09:00-15:00, NAV date = order date, counterparty = the holder; amounts "
                      "3,000-9,999 and never round, so the general cards (STAT-MAD per agent, BEH-VELOCITY, "
                      "BEH-SPIKE, TEMP-OFFHOURS, GEN-CONC, GEN-PERIOD-END, FOR-*) find nothing",
            "code_values": "fund_txn.txn_type: BUY buy, SELL sell, SWI switch_in, SWO switch_out",
            "intake": "sufficiency: F-R1, F-R2 and F-R6 are พร้อม (the unitholders join the transactions on 100 % of "
                      "the holders, the time of day and the NAV date are present, so F-R6 runs); the letter has no "
                      "concern without data, so data_request is empty; suggested_risks are the risks with a planted "
                      "case that the letter did not ask for: F-R3, F-R4, F-R5; the brief and the data have no "
                      "description conflict",
            "legacy_dataset_type": "variants/roles_legacy.json carries a top-level \"dataset_type\": \"F\" next to the "
                                   "{table: {column: role}} mapping; pass it as confirm answers[\"dataset_type\"] and "
                                   "drop it from the roles mapping before to_internal",
        },
        "tables": {t: list(c) for t, c in TABLES.items()},
    }


def _fmt(ts):
    return ts.strftime("%Y-%m-%d")


def _bday(ts):
    """The date itself on a weekday, else the next Monday."""
    return ts + pd.Timedelta(days=(7 - ts.dayofweek) % 7) if ts.dayofweek >= 5 else ts


def _next_bday(ts):
    n = ts.normalize() + pd.Timedelta(days=1)
    return n + pd.Timedelta(days=(7 - n.dayofweek) % 7) if n.dayofweek >= 5 else n


def _at(day, rng, lo=9 * 60, hi=14 * 60 + 40):
    """day at a random minute between lo and hi (minutes after midnight)."""
    return day + pd.Timedelta(minutes=int(rng.integers(lo, hi + 1)))


def make(seed: int = SEED):
    """Return (frames, answer_key)."""
    rng = np.random.default_rng(seed)
    n_norm = N_A + N_B + N_C + N_D + N_E
    n_amt = n_norm + 80
    base = (np.arange(n_amt) + rng.uniform(0.2, 0.8, n_amt)) / n_amt     # stratified uniform: no outlier in an agent group
    rng.shuffle(base)
    base = msc._fix_round(np.round(3000 + 6999 * base, 2))
    holders = [f"U-{1001 + i}" for i in range(n_norm)]
    fund = [FUNDS[int(rng.integers(0, len(FUNDS)))] for _ in holders]
    other_agents = [a for a in AGENTS if a != FOCUS_AGENT]
    # agents are dealt in the order of the holders' amounts, so every agent's group spans the whole amount range
    # (STAT-MAD compares an amount with the median / MAD of the agent's group): every 14th holder is AG-05's (9 holders)
    agent = [None] * n_norm
    nxt = 0
    for r, i in enumerate(np.argsort(base[:n_norm], kind="stable")):
        if r % 14 == 7 and sum(a == FOCUS_AGENT for a in agent) < N_AG05_NORMAL:
            agent[i] = FOCUS_AGENT
        else:
            agent[i] = other_agents[nxt % len(other_agents)]
            nxt += 1
    day = rng.integers(5, 25, n_norm)
    kind = ["A"] * N_A + ["B"] * N_B + ["C"] * N_C + ["D"] * N_D + ["E"] * N_E

    rows = []

    def add(u, ag, fd, ty, dt, amt, cp=None, nav=None):
        rows.append({"unitholder_id": u, "fund_code": fd, "dt": dt, "txn_type": ty, "amount": round(float(amt), 2),
                     "bank_account": cp or u, "agent": ag, "nav": nav if nav is not None else dt.normalize()})

    late_decoys = set(range(N_AG05_NORMAL, N_AG05_NORMAL + N_LATE_DECOY))  # type A holders, 2026-03
    for i, u in enumerate(holders):
        k, a = kind[i], float(base[i])
        if k in ("A", "B", "C"):
            for m in MONTHS:
                d = _bday(pd.Timestamp(2026, m, int(day[i])))
                if k == "A":
                    if i in late_decoys and m == 3:  # after the cut-off, priced on the next business day
                        dt = d + pd.Timedelta(minutes=int(rng.integers(15 * 60 + 40, 16 * 60 + 21)))
                        add(u, agent[i], fund[i], "BUY", dt, a, nav=_next_bday(dt))
                    else:
                        add(u, agent[i], fund[i], "BUY", _at(d, rng), a)
                elif k == "B":
                    add(u, agent[i], fund[i], "SELL", _at(d, rng), a)
                else:
                    t1 = _at(d, rng)
                    other = FUNDS[(FUNDS.index(fund[i]) + 3) % len(FUNDS)]
                    add(u, agent[i], fund[i], "SWO", t1, a)
                    add(u, agent[i], other, "SWI", t1 + pd.Timedelta(minutes=int(rng.integers(5, 21))), a)
        elif k == "D":   # slow round trip: the sale 55+ days after the purchase at 90-110 %
            m = int(rng.integers(1, 6))
            d = _bday(pd.Timestamp(2026, m, int(day[i])))
            add(u, agent[i], fund[i], "BUY", _at(d, rng), a)
            d2 = _bday(pd.Timestamp(2026, m + 3, int(day[i])))
            sell = float(msc._fix_round([round(a * float(rng.uniform(0.9, 1.1)), 2)])[0])
            add(u, agent[i], fund[i], "SELL", _at(d2, rng), sell)
        else:            # quick sale of a part: 10-25 days after the purchase at 40-55 %
            m = int(rng.integers(1, 9))
            d = _bday(pd.Timestamp(2026, m, int(day[i]) % 12 + 5))
            s = float(msc._fix_round([round(3000 + (a - 3000) * 0.14, 2)])[0])
            buy = float(msc._fix_round([round(s / float(rng.uniform(0.4, 0.55)), 2)])[0])
            add(u, agent[i], fund[i], "BUY", _at(d, rng), buy)
            add(u, agent[i], fund[i], "SELL", _at(_bday(d + pd.Timedelta(days=int(rng.integers(10, 26)))), rng), s)

    # planted
    for u, ag, items in PLANTED:
        for fd, ty, dt, amt, cp in items:
            ts = pd.Timestamp(dt)
            add(u, ag, fd, ty, ts, amt, cp)
    pool = iter(base[n_norm:])
    d404 = [pd.Timestamp(2026, 7, dd) for dd in (6, 7, 8, 9, 10, 13, 14, 15, 16, 17)]
    f404 = ["FX2", "FX3", "FX4", "FX5", "FX2", "FX6", "FX3", "FX7", "FX4", "FX8"]
    for dd, fd, ty in zip(d404, f404, FREQ_TYPES):
        add("U-0404", "AG-06", fd, ty, _at(dd, rng), next(pool))
    aug = [pd.Timestamp(2026, 8, dd) for dd in range(5, 25) if pd.Timestamp(2026, 8, dd).dayofweek < 5]
    for u in FREQ_HOLDERS:
        picks = sorted(int(x) for x in rng.permutation(len(aug))[:8])
        funds = [FUNDS[int(x)] for x in rng.permutation(len(FUNDS))]
        for n, p in enumerate(picks):
            ty = ["BUY", "BUY", "BUY", "BUY", "SWO", "SWI", "SWO", "SWI"][n]
            add(u, FOCUS_AGENT, funds[n], ty, _at(aug[p], rng), next(pool))

    tx = pd.DataFrame(rows).sort_values(["dt", "unitholder_id", "txn_type"], kind="stable").reset_index(drop=True)
    ids = [f"O-{100001 + k}" for k in range(len(tx))]
    tx.insert(0, "order_id", ids)
    late = tx.index[(tx["unitholder_id"] == "U-0606") & (tx["txn_type"] == "BUY")][0]
    tx.loc[late, "order_id"] = LATE_PLANTED_ID
    tx["order_datetime"] = tx["dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    tx["nav_date"] = tx["nav"].map(_fmt)
    tx = tx[TABLES["fund_txn"]]

    people = sorted(set(tx["unitholder_id"]) | {"U-0999"})
    opened = [_fmt(pd.Timestamp("2015-01-01") + pd.Timedelta(days=int(d))) for d in rng.integers(0, 3800, len(people))]
    uh = pd.DataFrame({"unitholder_id": people, "open_date": opened})
    # the planted holders' accounts were opened long before; every account is older than its first order
    return {"fund_txn": tx, "unitholders": uh[TABLES["unitholders"]]}, _answer_key()


def date_only(frames):
    """fund_txn with the time of day removed from order_datetime (the F-R6 yellow case); every other table is unchanged."""
    out = {t: df.copy() for t, df in frames.items()}
    out["fund_txn"]["order_datetime"] = out["fund_txn"]["order_datetime"].str[:10]
    return out


def main():
    import json
    frames, key = make()
    sc.write_dataset(sc.SAMPLES / "F", frames, key, BRIEF_MD, VARIANT_NAMES, ROLES_EN, legacy_dataset_type="F")
    d = sc.SAMPLES / "F" / "variants" / "date_only"
    d.mkdir(parents=True, exist_ok=True)
    for t, df in date_only(frames).items():
        df.to_csv(d / f"{t}.csv", index=False)
    brief = sc.load_brief(sc.SAMPLES / "F" / "brief.md")
    brief["columns"] = {**brief["columns"], "order_datetime": "วันที่ที่ผู้ถือหน่วยทำคำสั่ง (ไม่มีเวลาของรายการ)"}
    (d / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d.parent / "roles_date_only.json").write_text(json.dumps(sc.variant_roles(ROLES_EN, VARIANT_NAMES["en"]),
                                                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    t = frames["fund_txn"]
    print(f"wrote {len(t)} fund transactions, {len(frames['unitholders'])} unitholders, {len(key['findings'])} "
          f"expected findings to {sc.SAMPLES / 'F'}")


if __name__ == "__main__":
    main()
