"""Deterministic sample data for AIDA C2, data type L (life insurance policy transactions).

make(seed) returns (frames, key): frames = {"policy_txn", "policies", "beneficiary_changes"}. Only `seed` changes the
normal data; the planted cases and the answer key are the same for every seed.

Normal data design (why no check fires on it):
- 240 policies P-1001..P-1240, one insured each (I-1001..), issued 2018-01 .. 2024-10 (13+ months before any
  transaction, so no early surrender). policy_txn holds the money-out servicing transactions of 2026-01..10, one per
  normal policy: 90 surrenders (SURR, amount = cash value), 100 loans (LOAN, 25-70 % of the cash value) and 50 claim
  payments (CLM); 20 loan policies take a second loan 2-3 months later (two loans in 12 months is below the three of
  LIFE.LOAN.MIN_COUNT). No loan is ever followed by a surrender on the same policy. Premium rows are not in the file
  (a premium row per month would make every payout a spike against the insured's own history).
- Amounts: one stratified-Benford list (1,000-39,999, no round amount, same shape as sample C) is dealt to the rows, so
  STAT-MAD finds no outlier and no amount repeats; an insured has one (or two) rows, so no baseline check can run.
- Dates: day 5-24 of the month, months dealt evenly (steady counts), no period-end window. The payee is the insured
  (same id format). Staff: S-01..S-20; exactly 40 % of the surrender + beneficiary-change records are S-07's, the rest
  is spread over the other 19 (3.1-3.8 % each).
- 58 normal policies have one beneficiary change (a unique beneficiary B-2001..), always 45-90 days BEFORE the policy's
  money transaction, so no change is followed by money within LIFE.BENCHG_CASH.WINDOW_DAYS.

Planted cases (ids in the key):
- P-0101 single premium issued 2026-02-10, surrendered 2026-06-16 (4 months)               -> LIFE-EARLY-SURR, L-R1
- P-0202 beneficiary change 2026-07-08, surrender 2026-07-18 (10 days)                      -> LIFE-BENCHG-CASH, L-R2
- P-0303 loan of 95 % of the cash value (2026-08-12); P-0304 loan 2026-04-14 then
  surrender 2026-05-26 (42 days)                                                           -> LIFE-LOAN, L-R3
- ACC-9001 (a bank account) is the payee of surrenders of P-0401..P-0404 (4 insured);
  P-0505 (insured I-0505) is paid to I-0999, another person in the insured's id format    -> LIFE-THIRD-PAYEE, L-R4
- B-777 is the beneficiary of P-0601, P-0602, P-0603 (3 insured)                           -> LIFE-BENEF-MULTI, L-R5
- S-07 handles 64 of the 160 surrender + beneficiary-change records (40 %)                 -> LIFE-STAFF-CONC, L-R6
"""
import numpy as np
import pandas as pd

import make_sample_c as msc
import sample_common as sc

SEED = 20261109
N = 240
N_SURR, N_LOAN, N_CLM = 90, 100, 50
N_SECOND_LOAN = 20
N_BENCHG = 58
MONTHS = range(1, 11)
N_STAFF = 20
STAFF_FOCUS = "S-07"
FOCUS_SHARE_ROWS = 64          # of 160 surrender + beneficiary-change records = 40 %
PLANTED_POLICIES = ["P-0101", "P-0202", "P-0303", "P-0304", "P-0401", "P-0402", "P-0403", "P-0404", "P-0505",
                    "P-0601", "P-0602", "P-0603"]

TABLES = {"policy_txn": ["txn_id", "policy_no", "insured_id", "txn_date", "txn_type", "amount", "payee", "cash_value",
                         "staff_id"],
          "policies": ["policy_no", "insured_id", "issue_date", "premium_mode"],
          "beneficiary_changes": ["change_id", "policy_no", "change_date", "beneficiary", "staff_id"]}
ROLES_EN = {"policy_txn": {"txn_id": "record_id", "policy_no": "contract", "insured_id": "entity",
                           "txn_date": "date", "txn_type": "category", "amount": "amount", "payee": "counterparty",
                           "cash_value": "limit", "staff_id": "created_by"},
            "policies": {"policy_no": "contract", "insured_id": "entity", "issue_date": "opened_at",
                         "premium_mode": "category"},
            "beneficiary_changes": {"change_id": "record_id", "policy_no": "contract", "change_date": "date",
                                    "beneficiary": "counterparty", "staff_id": "created_by"}}
VARIANT_NAMES = {
    "en": {"policy_txn": {}, "policies": {}, "beneficiary_changes": {}},
    "th": {"policy_txn": {"txn_id": "รหัสรายการ", "policy_no": "เลขที่กรมธรรม์", "insured_id": "รหัสผู้เอาประกัน",
                          "txn_date": "วันที่ทำรายการ", "txn_type": "ประเภทรายการ", "amount": "จำนวนเงิน",
                          "payee": "ผู้รับเงิน", "cash_value": "มูลค่าเวนคืน", "staff_id": "รหัสพนักงาน"},
           "policies": {"policy_no": "เลขที่กรมธรรม์", "insured_id": "รหัสผู้เอาประกัน",
                        "issue_date": "วันออกกรมธรรม์", "premium_mode": "วิธีชำระเบี้ย"},
           "beneficiary_changes": {"change_id": "รหัสการเปลี่ยน", "policy_no": "เลขที่กรมธรรม์",
                                   "change_date": "วันที่เปลี่ยน", "beneficiary": "ผู้รับผลประโยชน์ใหม่",
                                   "staff_id": "รหัสพนักงาน"}},
    "legacy": {"policy_txn": {"txn_id": "COL1", "policy_no": "COL2", "insured_id": "COL3", "txn_date": "COL4",
                              "txn_type": "TP", "amount": "AMT", "payee": "COL7", "cash_value": "CV",
                              "staff_id": "USR"},
               "policies": {"policy_no": "COL2", "insured_id": "COL3", "issue_date": "COL9", "premium_mode": "COL10"},
               "beneficiary_changes": {"change_id": "COL11", "policy_no": "COL2", "change_date": "COL12",
                                       "beneficiary": "COL13", "staff_id": "USR"}},
}
CODE_VALUES = {"policy_txn.txn_type": {"SURR": "เวนคืนกรมธรรม์", "LOAN": "กู้ยืมตามกรมธรรม์", "CLM": "จ่ายสินไหม"}}

BRIEF_MD = """# หนังสือขอให้ตรวจสอบ: รายการกรมธรรม์ประกันชีวิต

เรียน ทีมวิเคราะห์ข้อมูล

ขอให้ช่วยตรวจสอบรายการบริการกรมธรรม์ประกันชีวิต ช่วงเดือนมกราคมถึงตุลาคม 2026 ไฟล์ที่ส่งมามี 3 ตาราง คือ policy_txn
(รายการจ่ายเงินตามกรมธรรม์ 1 แถวต่อ 1 รายการ), policies (ข้อมูลกรมธรรม์) และ beneficiary_changes (ประวัติการเปลี่ยนผู้รับ
ผลประโยชน์) เชื่อมกันด้วยเลขที่กรมธรรม์

ความหมายของคอลัมน์ที่ผมทราบ: txn_id คือรหัสรายการ ไม่ซ้ำกัน, txn_date คือวันที่ทำรายการ, txn_type คือประเภทรายการ
SURR = เวนคืนกรมธรรม์, LOAN = กู้ยืมตามกรมธรรม์ และ CLM = จ่ายสินไหม, amount คือจำนวนเงินที่จ่ายหรือให้กู้ตามรายการนั้น,
payee คือผู้รับเงิน ถ้าจ่ายให้ผู้เอาประกันจะเป็นรหัสผู้เอาประกัน (I-xxxx) ถ้าจ่ายเข้าบัญชีอื่นจะเป็นเลขที่บัญชี, cash_value คือ
มูลค่าเวนคืนของกรมธรรม์ ณ วันที่ทำรายการ, staff_id คือรหัสพนักงานหรือตัวแทนที่ดูแลรายการ ส่วนตาราง policies มี issue_date
คือวันออกกรมธรรม์ และ premium_mode คือวิธีชำระเบี้ย (single = ชำระครั้งเดียว, periodic = ชำระเป็นงวด) ตาราง
beneficiary_changes มี change_date คือวันที่เปลี่ยนผู้รับผลประโยชน์ และ beneficiary คือรหัสผู้รับผลประโยชน์ใหม่

เงื่อนไข: ดูเฉพาะรายการระหว่าง 1 ม.ค. ถึง 31 ต.ค. 2026

สิ่งที่กังวล:
1. มีการเวนคืนกรมธรรม์เร็วหลังออกกรมธรรม์ โดยเฉพาะกรมธรรม์ที่ชำระเบี้ยครั้งเดียว
2. มีการเปลี่ยนผู้รับผลประโยชน์ แล้วมีการเวนคืนหรือกู้ตามกรมธรรม์ตามมาในเวลาอันสั้น
3. มีการจ่ายเงินเข้าบัญชีของบุคคลอื่นที่ไม่ใช่ผู้เอาประกัน หรือบัญชีเดียวที่รับเงินจากหลายกรมธรรม์
4. มีการเคลมเร็วหลังทำกรมธรรม์ (ผมยังไม่มีข้อมูลวันเกิดเหตุและรายละเอียดการเคลม)

```json
{
  "context": "ประกันชีวิต — รายการเวนคืน กู้ตามกรมธรรม์ และจ่ายสินไหม ม.ค.–ต.ค. 2026 (policy_txn, policies และ beneficiary_changes เชื่อมด้วยเลขที่กรมธรรม์)",
  "columns": {
    "txn_id": "รหัสรายการ ไม่ซ้ำกัน",
    "policy_no": "เลขที่กรมธรรม์",
    "insured_id": "รหัสผู้เอาประกัน",
    "txn_date": "วันที่ทำรายการ",
    "txn_type": "ประเภทรายการ SURR = เวนคืนกรมธรรม์, LOAN = กู้ยืมตามกรมธรรม์, CLM = จ่ายสินไหม",
    "amount": "จำนวนเงินที่จ่ายหรือให้กู้ตามรายการนั้น",
    "payee": "ผู้รับเงิน เป็นรหัสผู้เอาประกัน (I-xxxx) ถ้าจ่ายให้ผู้เอาประกัน หรือเลขที่บัญชีถ้าจ่ายเข้าบัญชีอื่น",
    "cash_value": "มูลค่าเวนคืนของกรมธรรม์ ณ วันที่ทำรายการ",
    "staff_id": "รหัสพนักงานหรือตัวแทนที่ดูแลรายการ",
    "issue_date": "วันออกกรมธรรม์",
    "premium_mode": "วิธีชำระเบี้ย single = ชำระครั้งเดียว, periodic = ชำระเป็นงวด",
    "change_id": "รหัสการเปลี่ยนผู้รับผลประโยชน์ ไม่ซ้ำกัน",
    "change_date": "วันที่เปลี่ยนผู้รับผลประโยชน์",
    "beneficiary": "รหัสผู้รับผลประโยชน์ใหม่"
  },
  "conditions": [
    "ดูเฉพาะรายการ 1 ม.ค. – 31 ต.ค. 2026"
  ],
  "concerns": [
    "มีการเวนคืนกรมธรรม์เร็วหลังออกกรมธรรม์ โดยเฉพาะกรมธรรม์ที่ชำระเบี้ยครั้งเดียว",
    "มีการเปลี่ยนผู้รับผลประโยชน์ แล้วมีการเวนคืนหรือกู้ตามกรมธรรม์ตามมาในเวลาอันสั้น",
    "มีการจ่ายเงินเข้าบัญชีของบุคคลอื่นที่ไม่ใช่ผู้เอาประกัน หรือบัญชีเดียวที่รับเงินจากหลายกรมธรรม์",
    "มีการเคลมเร็วหลังทำกรมธรรม์ (ผมยังไม่มีข้อมูลวันเกิดเหตุและรายละเอียดการเคลม)"
  ]
}
```
"""

# (policy, insured, issue, mode, txn date, type, amount, cash value, payee, beneficiary change date, new beneficiary)
PLANTED = [
    ("P-0101", "I-0101", "2026-02-10", "single", "2026-06-16", "SURR", 18420.35, 18420.35, "I-0101", None, None),
    ("P-0202", "I-0202", "2020-08-17", "periodic", "2026-07-18", "SURR", 27305.60, 27305.60, "I-0202",
     "2026-07-08", "B-0202"),
    ("P-0303", "I-0303", "2019-05-20", "periodic", "2026-08-12", "LOAN", 20358.88, 21430.40, "I-0303", None, None),
    ("P-0304", "I-0304", "2019-11-04", "periodic", "2026-05-26", "SURR", 24800.40, 24800.40, "I-0304", None, None),
    ("P-0401", "I-0401", "2018-04-12", "periodic", "2026-02-17", "SURR", 14775.20, 14775.20, "ACC-9001", None, None),
    ("P-0402", "I-0402", "2019-09-23", "single", "2026-04-22", "SURR", 31260.45, 31260.45, "ACC-9001", None, None),
    ("P-0403", "I-0403", "2021-01-15", "periodic", "2026-06-23", "SURR", 8940.90, 8940.90, "ACC-9001", None, None),
    ("P-0404", "I-0404", "2022-06-30", "periodic", "2026-09-15", "SURR", 22115.75, 22115.75, "ACC-9001", None, None),
    ("P-0505", "I-0505", "2021-03-09", "periodic", "2026-05-19", "SURR", 12680.45, 12680.45, "I-0999", None, None),
    # B-777: three policies of three insured, a change each; the money transaction (a loan, 38-45 % of the cash value)
    # follows 84-98 days after the change
    ("P-0601", "I-0601", "2020-03-02", "periodic", "2026-05-12", "LOAN", 5210.30, 12400.70, "I-0601", "2026-02-10", "B-777"),
    ("P-0602", "I-0602", "2021-07-26", "periodic", "2026-07-14", "LOAN", 9380.15, 20850.35, "I-0602", "2026-04-21", "B-777"),
    ("P-0603", "I-0603", "2022-02-08", "single", "2026-09-15", "LOAN", 6745.60, 15230.20, "I-0603", "2026-06-09", "B-777"),
]
# the loan of P-0304 (L-R3 c): 40 % of the cash value, 42 days before the surrender
P0304_LOAN = ("2026-04-14", 9920.16)


def _answer_key():
    findings = [("policy", "P-0101", "L-R1", "2026-06"), ("policy", "P-0202", "L-R2", "2026-07"),
                ("policy", "P-0303", "L-R3", "2026-08"), ("policy", "P-0304", "L-R3", "2026-05"),
                ("payee", "ACC-9001", "L-R4", "2026-09"), ("policy", "P-0505", "L-R4", "2026-05"),
                ("beneficiary", "B-777", "L-R5", "2026-06"), ("staff", STAFF_FOCUS, "L-R6", "2026-10")]
    recipes = {"STAT-MAD": [], "BEH-VELOCITY": [], "BEH-SPIKE": [], "TEMP-OFFHOURS": [], "GEN-CONC": [],
               "GEN-PERIOD-END": [], "FOR-BENFORD": [], "FOR-ROUND": [], "FOR-REPEAT": [],
               "LIFE-EARLY-SURR": ["P-0101"], "LIFE-BENCHG-CASH": ["P-0202"], "LIFE-LOAN": ["P-0303", "P-0304"],
               "LIFE-THIRD-PAYEE": ["ACC-9001", "P-0505"], "LIFE-BENEF-MULTI": ["B-777"],
               "LIFE-STAFF-CONC": [STAFF_FOCUS]}
    return {
        "recipes": recipes,
        "findings": [{"entity_type": t, "entity_id": e, "risk": r, "period": p} for t, e, r, p in findings],
        "code_values": {k: dict(v) for k, v in CODE_VALUES.items()},
        "concern_risks": ["L-R1", "L-R2", "L-R4"],
        "intake": {
            "sufficiency": {"L-R1": "พร้อม", "L-R2": "พร้อม", "L-R4": "พร้อม"},
            "data_request": ["ข้อมูลการเคลม (วันที่เกิดเหตุ วันที่เรียกร้องสินไหม ประเภทและสาเหตุของการเคลม ผลการพิจารณา) "
                             "ของแต่ละกรมธรรม์ เพื่อดูการเคลมเร็วหลังทำกรมธรรม์"],
            "suggested_risks": ["L-R3", "L-R5", "L-R6"],
            "description_conflicts": [],
        },
        "conventions": {
            "entities": "findings are keyed by the check's own entity: LIFE-EARLY-SURR, LIFE-BENCHG-CASH and LIFE-LOAN "
                        "name the policy (policy_no); LIFE-THIRD-PAYEE names the payee for rule (b) (ACC-9001) and the "
                        "policy for rule (a) (P-0505); LIFE-BENEF-MULTI the beneficiary; LIFE-STAFF-CONC the staff id. "
                        "entity_type labels: policy / payee / beneficiary / staff",
            "period": "the period is the month of the record that completes the pattern: the surrender (L-R1, L-R2, "
                      "L-R3 c, L-R4 a), the loan (L-R3 a), and, for a pattern over several records, the latest month "
                      "of the contributing records (ACC-9001 2026-09, B-777 2026-06, S-07 2026-10)",
            "L-R3": "P-0303 meets rule (a) (95 % of the cash value, the normal maximum is 70 %); P-0304 meets rule (c) "
                    "(loan 2026-04-14, surrender 2026-05-26, 42 days); no policy meets rule (b), 20 policies have two "
                    "loans (below LIFE.LOAN.MIN_COUNT 3), so (b) must not report anything",
            "L-R4": "ACC-9001 is a bank account number, a different id format from the insured id, so rule (a) cannot "
                    "compare it; rule (b) (4 policies of 4 insured) reports it. P-0505 is paid to I-0999, another "
                    "person in the insured id format (I-nnnn): rule (a) reports the policy. Every other payee is "
                    "the insured (I-nnnn = insured_id)",
            "L-R5": "B-777 is named by one change on each of 3 policies of 3 insured; no policy and no other "
                    "beneficiary has two changes, so the LIFE.BENCHG.MIN_COUNT rule reports nothing. After each "
                    "change the policy has a loan 84-98 days later (outside LIFE.BENCHG_CASH.WINDOW_DAYS)",
            "L-R6": "S-07 handles 64 of the 160 surrender + beneficiary-change records (40 %; the other 19 staff "
                    "3.1-3.8 % each). Loans and claims are spread over all 20 staff and are not counted",
            "normal": "every other policy: one money transaction (two for 20 loan policies), payee = insured, issued "
                      "13+ months before, loan at most 70 % of the cash value, a beneficiary change (58 policies) "
                      "always 45-90 days before the transaction; dates day 5-24 (no period-end window)",
            "date_format": "txn_date, issue_date and change_date are dates without a time of day (TEMP-OFFHOURS "
                           "reads nothing); the general cards STAT-MAD, BEH-VELOCITY, BEH-SPIKE, GEN-CONC, "
                           "GEN-PERIOD-END, FOR-BENFORD (no entity reaches FOR.BENFORD.MIN_N), FOR-ROUND and "
                           "FOR-REPEAT find nothing",
            "code_values": "policy_txn.txn_type: SURR surrender, LOAN loan, CLM claim; the beneficiary changes are the "
                           "events table (no category column), so benefit_change needs no code. premium_mode values "
                           "are self-describing words (single / periodic), described in the brief",
            "exploratory": "concern 4 (early claims) needs claim dates, incident dates and claim reasons that the "
                           "file does not have: no library risk has a runnable check for it, so the engine answers it "
                           "with exploratory mode or a Data Request (data_request above); CLM rows only say a claim "
                           "was paid. It has no entry in intake.sufficiency",
            "intake": "sufficiency: L-R1, L-R2 and L-R4 are พร้อม (policies join the transactions on 100 % of the "
                      "insured ids, the beneficiary changes on 100 % of the policy numbers, every role of the "
                      "checks is mapped); suggested_risks are the risks with a planted case that the letter did not "
                      "ask for: L-R3, L-R5, L-R6; the brief and the data have no description conflict",
            "legacy_dataset_type": "variants/roles_legacy.json carries a top-level \"dataset_type\": \"L\" next to the "
                                   "{table: {column: role}} mapping; pass it as confirm answers[\"dataset_type\"] and "
                                   "drop it from the roles mapping before to_internal",
        },
        "tables": {t: list(c) for t, c in TABLES.items()},
    }


def _day(rng, month, lo=5, hi=24):
    return pd.Timestamp(2026, month, int(rng.integers(lo, hi + 1)))


def _fmt(ts):
    return ts.strftime("%Y-%m-%d")


def _amount_list(n, rng):
    return msc._fix_round(np.round(msc._instalments(n, rng), 2))


def make(seed: int = SEED):
    """Return (frames, answer_key)."""
    rng = np.random.default_rng(seed)
    pol_no = [f"P-{1001 + i}" for i in range(N)]
    ins = [f"I-{1001 + i}" for i in range(N)]
    types = np.array(["SURR"] * N_SURR + ["LOAN"] * N_LOAN + ["CLM"] * N_CLM)
    rng.shuffle(types)
    # months dealt evenly over the ten months (steady counts), then shuffled
    months = np.tile(np.arange(1, 11), N // 10 + 1)[:N]
    rng.shuffle(months)
    amounts = _amount_list(N + N_SECOND_LOAN, rng)
    issue = [pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(d)) for d in rng.integers(0, 2495, N)]  # to 2024-10
    mode = rng.choice(["single", "periodic"], N, p=[0.3, 0.7])

    rows, policies = [], []   # rows: dict per txn; policies: dict per policy
    for i in range(N):
        t, a = types[i], float(amounts[i])
        if t == "SURR":
            cv = a
        elif t == "LOAN":
            cv = round(a / float(rng.uniform(0.25, 0.7)), 2)
        else:
            cv = round(a * float(rng.uniform(1.5, 6.0)), 2)
        rows.append({"policy_no": pol_no[i], "insured_id": ins[i], "d": _day(rng, int(months[i])), "txn_type": t,
                     "amount": round(a, 2), "payee": ins[i], "cash_value": cv, "kind": "normal"})
        policies.append({"policy_no": pol_no[i], "insured_id": ins[i], "issue_date": _fmt(issue[i]),
                         "premium_mode": str(mode[i])})
    # second loans: 20 loan policies whose first loan is in month <= 7, again 2-3 months later, another amount
    loans = [k for k in range(N) if types[k] == "LOAN" and months[k] <= 7][:N_SECOND_LOAN]
    for n, k in enumerate(loans):
        a = float(amounts[N + n])
        rows.append({"policy_no": pol_no[k], "insured_id": ins[k], "d": _day(rng, int(months[k]) + int(rng.integers(2, 4))),
                     "txn_type": "LOAN", "amount": round(a, 2), "payee": ins[k],
                     "cash_value": rows[k]["cash_value"], "kind": "normal"})
        rows[-1]["cash_value"] = round(max(rows[k]["cash_value"], a / 0.6), 2)
    # beneficiary changes: 58 normal policies with a money transaction from April on, change 45-90 days earlier
    cand = [k for k in range(N) if months[k] >= 4 and k not in set(loans)]
    chosen = [cand[j] for j in rng.permutation(len(cand))[:N_BENCHG]]
    changes = []
    for n, k in enumerate(chosen):
        changes.append({"policy_no": pol_no[k], "d": rows[k]["d"] - pd.Timedelta(days=int(rng.integers(45, 91))),
                        "beneficiary": f"B-{2001 + n}", "kind": "normal"})

    # planted
    for pol, insd, iss, md, td, ty, am, cv, payee, cd, ben in PLANTED:
        policies.append({"policy_no": pol, "insured_id": insd, "issue_date": iss, "premium_mode": md})
        rows.append({"policy_no": pol, "insured_id": insd, "d": pd.Timestamp(td), "txn_type": ty, "amount": am,
                     "payee": payee, "cash_value": cv, "kind": pol})
        if cd:
            changes.append({"policy_no": pol, "d": pd.Timestamp(cd), "beneficiary": ben, "kind": pol})
    rows.append({"policy_no": "P-0304", "insured_id": "I-0304", "d": pd.Timestamp(P0304_LOAN[0]), "txn_type": "LOAN",
                 "amount": P0304_LOAN[1], "payee": "I-0304", "cash_value": 24800.40, "kind": "P-0304"})

    # staff: S-07 holds 64 of the 160 surrender + beneficiary-change records, the other 19 share the rest evenly
    others = [f"S-{k:02d}" for k in range(1, N_STAFF + 1) if f"S-{k:02d}" != STAFF_FOCUS]
    recs = [("t", k) for k, r in enumerate(rows) if r["txn_type"] == "SURR"] + [("c", k) for k in range(len(changes))]
    assert len(recs) == 160
    forced = [r for r in recs if (r[0] == "t" and rows[r[1]]["kind"] == "P-0202")
              or (r[0] == "c" and changes[r[1]]["kind"] == "P-0202")]
    # the latest surrender (in October) is S-07's, so S-07's pattern period is 2026-10 for every seed
    oct_surr = max((r for r in recs if r[0] == "t"), key=lambda r: (rows[r[1]]["d"], r[1]))
    forced.append(oct_surr)
    free = [r for r in recs if r not in forced]
    pick = {free[j] for j in rng.permutation(len(free))[:FOCUS_SHARE_ROWS - len(forced)]}
    rest = [r for r in free if r not in pick]
    staff = {r: STAFF_FOCUS for r in forced + sorted(pick)}
    deal = [others[j % len(others)] for j in range(len(rest))]
    rng.shuffle(deal)
    staff.update(dict(zip(rest, deal)))
    all_staff = [f"S-{k:02d}" for k in range(1, N_STAFF + 1)]
    for k, r in enumerate(rows):
        r["staff_id"] = staff[("t", k)] if r["txn_type"] == "SURR" else all_staff[int(rng.integers(0, N_STAFF))]
    for k, c in enumerate(changes):
        c["staff_id"] = staff[("c", k)]

    tx = pd.DataFrame(rows).sort_values(["d", "policy_no", "txn_type"], kind="stable").reset_index(drop=True)
    tx.insert(0, "txn_id", [f"T-{k:06d}" for k in range(1, len(tx) + 1)])
    tx["txn_date"] = tx["d"].map(_fmt)
    tx = tx[TABLES["policy_txn"]]
    pol = pd.DataFrame(policies).sort_values("policy_no", kind="stable").reset_index(drop=True)[TABLES["policies"]]
    ch = pd.DataFrame(changes).sort_values(["d", "policy_no"], kind="stable").reset_index(drop=True)
    ch.insert(0, "change_id", [f"BC-{k:04d}" for k in range(1, len(ch) + 1)])
    ch["change_date"] = ch["d"].map(_fmt)
    ch = ch[TABLES["beneficiary_changes"]]
    return {"policy_txn": tx, "policies": pol, "beneficiary_changes": ch}, _answer_key()


def main():
    frames, key = make()
    sc.write_dataset(sc.SAMPLES / "L", frames, key, BRIEF_MD, VARIANT_NAMES, ROLES_EN, legacy_dataset_type="L")
    t = frames["policy_txn"]
    print(f"wrote {len(t)} policy transactions, {len(frames['policies'])} policies, "
          f"{len(frames['beneficiary_changes'])} beneficiary changes, {len(key['findings'])} expected findings "
          f"to {sc.SAMPLES / 'L'}")


if __name__ == "__main__":
    main()
