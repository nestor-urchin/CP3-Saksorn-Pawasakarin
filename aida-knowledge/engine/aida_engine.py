"""AIDA engine: the tested replacement for the B1 recipe cards (AIDA-18 / AIDA-19).

One file; pandas, numpy, openpyxl and the standard library only (no network libraries).
Every threshold is read from the AIDA-14 Machine Config dict passed as `cfg`.
"""
import datetime
import functools
import hashlib
import json
import os
import re

import numpy as np
import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE  # control characters a worksheet cannot hold

__version__ = "3.0.0"
REGISTRY_VERSION = "1.2"

ROLES = ("record_id", "date", "amount", "entity", "counterparty", "contract", "category", "channel",
         "created_by", "approved_by", "document_no", "limit", "due_date", "opened_at")
# Role -> internal column of the transaction frame (everything else keeps its role name;
# custom:<name> keeps its name). The master/accounts frame uses acct_id and opened_at.
ROLE_TO_INTERNAL = {r: r for r in ROLES}
ROLE_TO_INTERNAL.update(record_id="tx_id", date="ts", entity="from_acct", counterparty="to_acct")


# ---- CORE-EVIDENCE ----
EVIDENCE_COLUMNS = ["evidence_id", "run_id", "recipe_id", "recipe_version", "skill_family",
                    "entity_type", "entity_id", "risk", "period", "metric", "value", "threshold",
                    "registry_key", "registry_version", "explanation", "record_refs", "data_ref"]
def clean_tx(tx: pd.DataFrame) -> pd.DataFrame:
    t = tx.copy()
    t["ts"] = pd.to_datetime(t["ts"])
    t["amount"] = pd.to_numeric(t["amount"], errors="coerce")
    t["tx_id"] = t["tx_id"].astype(str)
    t = t[(t["from_acct"] != t["to_acct"]) & (t["amount"] > 0) & t["ts"].notna()]
    return t.assign(period=t["ts"].dt.strftime("%Y-%m")).sort_values("ts", kind="mergesort")
def base_tx(tables: dict) -> pd.DataFrame:
    """Clean transactions for the checks that read only entity, date and amount (STAT-MAD, BEH-VELOCITY,
    BEH-SPIKE, TEMP-OFFHOURS). With a counterparty column and no contract column (transfers, data type E) it is
    clean_tx, exactly as in B1; otherwise (loan payments, accounts payable, or no counterparty) self-pairs are
    kept, because a borrower paying their own loan is normal data."""
    tx = tables["transactions"]
    if "to_acct" in tx.columns and "contract" not in tx.columns:
        return clean_tx(tx)
    return _gen_tx(tables)
def one_per_month(f: pd.DataFrame) -> pd.DataFrame:
    if f.empty:
        return f
    keys = ["entity_id", "period"]
    refs = f.groupby(keys)["record_refs"].agg(lambda s: sorted({str(x) for r in s for x in r}))
    top = f.sort_values("value", ascending=False, kind="mergesort").drop_duplicates(keys)
    return top.drop(columns="record_refs").merge(refs.reset_index(), on=keys)
def evidence_rows(recipe_id: str, version: str, skill_family: str, risk: str,
                  registry_key: str, found: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if found is None or len(found) == 0:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    run, f = cfg["_RUN"], found.reset_index(drop=True)
    etype = f["entity_type"].fillna("account") if "entity_type" in f.columns else "account"
    return f.assign(
        evidence_id=[f"{recipe_id}-{run['run_id']}-{i + 1}" for i in range(len(f))],
        run_id=run["run_id"], recipe_id=recipe_id, recipe_version=version,
        skill_family=skill_family, entity_type=etype, risk=risk, registry_key=registry_key,
        registry_version=cfg["REGISTRY.VERSION"], data_ref=run["data_ref"],
        record_refs=[[str(x) for x in r] for r in f["record_refs"]])[EVIDENCE_COLUMNS]
def card_note(tables: dict, recipe_id: str, version: str, detail: str) -> str:
    # a limit a card hit (e.g. a search cap) even with 0 rows: OUT-BUNDLE logs REVIEW and shows it
    tables.setdefault("_out", {}).setdefault("notes", []).append(
        {"recipe_id": recipe_id, "recipe_version": version, "detail": detail})
    return detail
def core_evidence(tables: dict = None, cfg: dict = None) -> pd.DataFrame:
    return pd.DataFrame(columns=EVIDENCE_COLUMNS)  # empty Evidence frame


# ---- CORE-BASELINE ----
def beyond_baseline(d: pd.DataFrame, acct: str, col: str, need: int, k: float,
                    sd_floor: str = "none") -> pd.DataFrame:
    # baseline = this account's earlier rows only; returns flagged rows with mu, sd, thr
    by = d.groupby(acct)[col].shift().groupby(d[acct])
    n = by.transform(lambda s: s.expanding().count())
    mu = by.transform(lambda s: s.expanding().mean())
    sd = by.transform(lambda s: s.expanding().std()).fillna(0)
    sd_used = np.maximum(sd, np.sqrt(mu)) if sd_floor == "poisson" else sd
    out = d.assign(mu=mu, sd=sd, thr=mu + k * sd_used)
    return out[(n >= need) & (out[col] > out["thr"])]
def baseline_formula(mu: float, sd: float, k: float, thr: float, sd_floor: str = "none") -> str:
    if sd_floor == "poisson":
        return (f"ค่าเฉลี่ย {mu:,.2f} + {k} × max(SD {sd:,.2f}, √ค่าเฉลี่ย {np.sqrt(mu):,.2f})"
                f" = {thr:,.2f}")
    return f"ค่าเฉลี่ย {mu:,.2f} + {k} × SD {sd:,.2f} = {thr:,.2f}"
def core_baseline(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: defines beyond_baseline and baseline_formula


# ---- PREP-DATE ----
# Calendar rules (definitional, not audit thresholds, so not registry keys):
BE_MIN_YEAR = 2400          # a year >= 2400 is a Buddhist Era (พ.ศ.) year
BE_OFFSET = 543             # ค.ศ. = พ.ศ. - 543
PLAUSIBLE_MIN_YEAR = 1990   # an earlier transaction date points to a wrong format or calendar
THAI_MONTHS = {"มค": 1, "กพ": 2, "มีค": 3, "เมย": 4, "พค": 5, "มิย": 6,
               "กค": 7, "สค": 8, "กย": 9, "ตค": 10, "พย": 11, "ธค": 12}
RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(.*)$")
RE_YMD8 = re.compile(r"^(\d{4})(\d{2})(\d{2})()$")
RE_THAI = re.compile(r"^(\d{1,2})\s*([ก-๙.]+)\s*(\d{2,4})(.*)$")
RE_DMY = re.compile(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(.*)$")
RE_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?")
def date_parts(x: str):
    # -> (kind, a, b, year, rest): iso / thai give (day, month); slash gives the fields as written
    x = x.strip()
    m = RE_ISO.match(x) or RE_YMD8.match(x)
    if m:
        return "iso", int(m[3]), int(m[2]), int(m[1]), m[4]
    m = RE_THAI.match(x)
    if m and m[2].replace(".", "") in THAI_MONTHS:
        return "thai", int(m[1]), THAI_MONTHS[m[2].replace(".", "")], int(m[3]), m[4]
    m = RE_DMY.match(x)
    return ("slash", int(m[1]), int(m[2]), int(m[3]), m[4]) if m else None
def iso_text(day: int, month: int, year: int, rest: str) -> str:
    year = year + 2000 if year < 100 else year  # 2-digit year
    year = year - BE_OFFSET if year >= BE_MIN_YEAR else year
    t = RE_TIME.search(rest)
    h, mi, s = (int(t[1]), int(t[2]), int(t[3] or 0)) if t else (0, 0, 0)
    if t and t[4]:
        h = h % 12 + (12 if t[4].lower() == "pm" else 0)
    return f"{year:04d}-{month:02d}-{day:02d} {h:02d}:{mi:02d}:{s:02d}"
def prep_date(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: calendar constants, date_parts and iso_text for PREP-TS


# ---- PREP-TS ----
EXCEL_EPOCH = pd.Timestamp("1899-12-30")  # Excel serial day 0 (1900 date system)
EXCEL_MAX_SERIAL = 2958465  # 9999-12-31, the last date Excel can store
def _ts_other(x):
    if isinstance(x, str) and x.strip().replace(".", "", 1).isdigit():
        x = float(x)
    if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, (bool, np.bool_)):
        return ((EXCEL_EPOCH + pd.Timedelta(days=float(x))).round("s") if 0 < x <= EXCEL_MAX_SERIAL else pd.NaT), "excel_serial"
    try:
        v = pd.Timestamp(x)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT, "อื่น ๆ"
    return (v.tz_localize(None) if v is not pd.NaT and v.tzinfo is not None else v), "datetime"
def to_naive_ts(s: pd.Series) -> tuple:
    # ONE format per column (same result on every pandas version) -> (naive datetimes, info)
    info = {"date_format": "datetime", "be_converted": False, "ambiguous_dates": 0, "date_samples": []}
    if pd.api.types.is_datetime64_any_dtype(s):
        return (s.dt.tz_localize(None) if getattr(s.dt, "tz", None) is not None else s), info
    vals = list(s.dropna().unique())
    parts = {x: date_parts(x) for x in vals if isinstance(x, str)}
    slash = [p for p in parts.values() if p and p[0] == "slash"]
    mdy = any(p[2] > 12 for p in slash) and all(p[1] <= 12 for p in slash)  # default: day-first (Thai)
    text, out, kinds = {}, {}, set()
    for x in vals:
        p = parts.get(x)
        if p is None:
            out[x], k = _ts_other(x)
        else:
            k = {"iso": "iso", "thai": "dd เดือนไทย yyyy"}.get(p[0], "mm/dd/yyyy" if mdy else "dd/mm/yyyy")
            d, m = (p[2], p[1]) if p[0] == "slash" and mdy else (p[1], p[2])
            text[x] = iso_text(d, m, p[3], p[4])
            info["be_converted"] |= p[3] >= BE_MIN_YEAR
        kinds.add(k)
    conv = pd.to_datetime(pd.Series(list(text.values()), dtype=object), format="%Y-%m-%d %H:%M:%S", errors="coerce")
    out.update(zip(text, conv))
    amb = {x for x, p in parts.items() if p and p[0] == "slash" and p[1] <= 12 and p[2] <= 12}
    info.update(date_format=" + ".join(sorted(kinds)) or "-", ambiguous_dates=int(s.isin(amb).sum()),
                date_samples=[(str(x), "แปลงไม่ได้" if pd.isna(out[x]) else f"{out[x]:%Y-%m-%d %H:%M:%S}") for x in vals[:3]])
    return pd.to_datetime(s.map(out), errors="coerce"), info
def prep_ts(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: defines to_naive_ts for PREP-MAP


# ---- PREP-MAP ----
def prep_map(raw: dict, mapping: dict, cfg: dict) -> dict:
    tables, dates, bad = {}, {}, {}  # bad: up to 3 unreadable raw values per column (for STOP reasons)
    def unread(raw_col, conv):
        return [str(x) for x in pd.unique(raw_col[conv.isna() & raw_col.notna()])[:3]]
    for name, df in raw.items():
        t = df.rename(columns=(mapping or {}).get(name, {})).copy()
        for c in ("ts", "opened_at"):
            if c in t.columns:
                r = t[c]
                t[c], dates[c] = to_naive_ts(r)
                bad[c] = unread(r, t[c])
        for c in ("tx_id", "from_acct", "to_acct", "acct_id"):
            if c in t.columns:
                t[c] = t[c].map(lambda x: x if pd.isna(x) else str(x).strip())
        if "amount" in t.columns:
            a = t["amount"].map(lambda x: x.replace(",", "").replace("฿", "").strip()
                                if isinstance(x, str) else x)
            r, t["amount"] = t["amount"], pd.to_numeric(a, errors="coerce").astype(float)
            bad["amount"] = unread(r, t["amount"])
        tables[name] = t
    tx = tables.get("transactions", pd.DataFrame())
    def has(*cols):
        return all(c in tx.columns for c in cols)
    no_ts = {"date_format": "-", "be_converted": False, "ambiguous_dates": 0, "date_samples": []}
    acc = tables.get("accounts")
    oa = acc["opened_at"] if acc is not None and "opened_at" in acc.columns else pd.Series(dtype="datetime64[ns]")
    tables["_prep"] = {
        "unparsed_ts": int(tx["ts"].isna().sum()) if has("ts") else 0,
        "excluded_self": int((tx["from_acct"] == tx["to_acct"]).sum()) if has("from_acct", "to_acct") else 0,
        "excluded_nonpositive": int((tx["amount"] <= 0).sum()) if has("amount") else 0,
        "unparsed_amount": int(tx["amount"].isna().sum()) if has("amount") else 0,
        "amount_samples": bad.get("amount", []), "opened_at_rows": len(oa), "opened_at_samples": bad.get("opened_at", []),
        "unparsed_opened_at": int(oa.isna().sum()), **dates.get("ts", no_ts), "opened_at_info": dates.get("opened_at")}
    return tables


# ---- PROF-PROFILE ----
PROFILE_TX_COLUMNS = ["tx_id", "ts", "from_acct", "to_acct", "amount", "currency", "channel"]
def prof_profile(tables: dict, cfg: dict) -> tuple:
    tx, prep, lim = tables["transactions"], tables.get("_prep", {}), cfg["GATE.COMPLETENESS.MIN"]
    n, rows = len(tx), []
    def add(item, value, detail=""):
        rows.append({"item": item, "value": value, "detail": detail})
    add("จำนวนรายการ (transactions)", n)
    for c in PROFILE_TX_COLUMNS:
        there = c in tx.columns
        add(f"ความครบถ้วนของ {c}", round(float(tx[c].notna().mean()), 4) if there and n else None,
            f"เกณฑ์ GATE.COMPLETENESS.MIN = {lim:.0%}" if there else "ไม่มีคอลัมน์นี้")
    if "ts" in tx.columns and tx["ts"].notna().any():
        d = tx["ts"].dropna()
        add("ช่วงเวลาของข้อมูล", f"{d.min():%Y-%m-%d} ถึง {d.max():%Y-%m-%d}", f"{d.dt.strftime('%Y-%m').nunique()} เดือน")
    add("รูปแบบวันที่ของ ts", prep.get("date_format", "-"),
        f"แปลงปี พ.ศ.: {'ใช่' if prep.get('be_converted') else 'ไม่'}; วันและเดือน ≤ 12 ทั้งคู่ "
        f"{prep.get('ambiguous_dates', 0)} รายการ; ตัวอย่าง: "
        + ", ".join(f"{a} → {b}" for a, b in prep.get("date_samples", [])))
    if "from_acct" in tx.columns and "to_acct" in tx.columns:
        add("จำนวนบัญชี", int(pd.concat([tx["from_acct"], tx["to_acct"]]).nunique()))
    add("ts ที่ไม่มีหรือแปลงเป็นวันเวลาไม่ได้", prep.get("unparsed_ts", 0))
    add("amount ที่ไม่มีหรือแปลงเป็นตัวเลขไม่ได้ (ไม่นำไปวิเคราะห์)", prep.get("unparsed_amount", 0),
        "ตัวอย่างที่แปลงไม่ได้: " + (", ".join(prep.get("amount_samples", [])) or "-"))
    add("รายการโอนเข้าบัญชีตัวเอง (ไม่นำไปวิเคราะห์)", prep.get("excluded_self", 0))
    add("รายการยอด ≤ 0 (ไม่นำไปวิเคราะห์)", prep.get("excluded_nonpositive", 0))
    acc = tables.get("accounts")
    add("ตาราง accounts", "มี" if acc is not None else "ไม่มี", "" if acc is not None else "MULE-NEW-ACCT ใช้ basis=first_seen")
    if prep.get("opened_at_rows"):
        oi = prep.get("opened_at_info") or {}
        add("opened_at ที่ไม่มีหรือแปลงเป็นวันที่ไม่ได้ (accounts)", prep.get("unparsed_opened_at", 0),
            f"จาก {prep['opened_at_rows']} บัญชี; รูปแบบ {oi.get('date_format', '-')}; ตัวอย่างที่แปลงไม่ได้: "
            + (", ".join(prep.get("opened_at_samples", [])) or "-"))
    if "tx_id" in tx.columns:
        ids = tx["tx_id"]
        dup = sorted(str(x) for x in ids[ids.duplicated(keep=False) & ids.notna()].unique())
        add("tx_id ซ้ำ (จำนวนค่า)", len(dup), ", ".join(dup[:10]))
    stop = prof_checks(tx, prep, cfg)
    return pd.DataFrame(rows, columns=["item", "value", "detail"]), ("STOP: " + "; ".join(stop) if stop else "OK")


# ---- PROF-CHECKS ----
def prof_checks(tx: pd.DataFrame, prep: dict, cfg: dict) -> list:
    stop, n, lim = [], len(tx), cfg["GATE.COMPLETENESS.MIN"]
    if "tx_id" not in tx.columns:
        stop.append("ไม่มีคอลัมน์ tx_id (record key) ตาม GATE.TRACE.REQUIRED จึงอ้างอิงรายการต้นทางไม่ได้")
    else:
        ids = tx["tx_id"]
        dup = sorted(str(x) for x in ids[ids.duplicated(keep=False) & ids.notna()].unique())
        if ids.isna().any():
            stop.append(f"tx_id ว่าง {int(ids.isna().sum())} รายการ — record key ไม่ครบตาม GATE.TRACE.REQUIRED")
        if dup:
            stop.append(f"tx_id ซ้ำ {len(dup)} ค่า (เช่น {', '.join(dup[:5])}) — record key ไม่ unique ตาม GATE.TRACE.REQUIRED")
    cols = [("amount", n, prep.get("unparsed_amount", 0), "ตัดหน่วย/ข้อความ เช่น บาท หรือวงเล็บออกจากจำนวนเงิน"),
            ("accounts.opened_at", prep.get("opened_at_rows", 0), prep.get("unparsed_opened_at", 0),
             "ตรวจรูปแบบวันที่ หรือเอา opened_at ออกจาก mapping เพื่อใช้ basis=first_seen")]
    for col, rows, k, fix in cols:  # same 1 - GATE.COMPLETENESS.MIN rule as ts
        if rows and k / rows > 1 - lim:
            ex = ", ".join(f'"{x}"' for x in prep.get(col.split(".")[-1] + "_samples", []))
            stop.append(f"{col} ไม่มีหรือแปลงไม่ได้ {k / rows:.1%} มากกว่า {1 - lim:.0%} (1 − GATE.COMPLETENESS.MIN)"
                        f"{' เช่น ' + ex if ex else ''} — {fix} ที่จุดยืนยัน 1 แล้วรันใหม่")
    if "ts" not in tx.columns or not n:
        return stop
    bad = prep.get("unparsed_ts", 0) / n
    if bad > 1 - lim:
        stop.append(f"ts ไม่มีหรือแปลงเป็นวันเวลาไม่ได้ {bad:.1%} มากกว่า {1 - lim:.0%} (1 − GATE.COMPLETENESS.MIN) "
                    "— ตรวจรูปแบบวันที่ (วัน/เดือน/ปี, ปี พ.ศ.) และการจับคู่คอลัมน์ที่จุดยืนยัน 1")
    d = tx["ts"].dropna()
    run_day = pd.Timestamp(cfg["_RUN"].get("run_date") or pd.Timestamp.now()).normalize()
    cause = "อาจเป็นปี พ.ศ. ที่แปลงไม่ถูกต้อง หรือรูปแบบวัน/เดือนสลับกัน — ตรวจรูปแบบวันที่ที่จุดยืนยัน 1"
    if len(d) and d.min().year < PLAUSIBLE_MIN_YEAR:
        stop.append(f"ts มีวันที่ก่อนปี {PLAUSIBLE_MIN_YEAR} ({d.min():%Y-%m-%d}) ซึ่งไม่สมเหตุสมผล — {cause}")
    if len(d) and d.max() >= run_day + pd.Timedelta(days=1):
        stop.append(f"ts มีวันที่หลังวันที่รัน {run_day:%Y-%m-%d} ({d.max():%Y-%m-%d}) — {cause}")
    return stop


# ---- GATE-CAPABILITY ----
GATE_CARDS = ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE", "NET-FUNNEL",
              "MULE-DWELL", "MULE-NEW-ACCT", "MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK",
              "CPTY-PROFILE", "CPTY-NEW-LARGE", "FLOW-TRACE", "FLOW-LAYERING"]
GATE_BASE = ["tx_id", "ts", "from_acct", "to_acct", "amount"]  # clean_tx in every card needs all five
GATE_COL_TEXT = {"tx_id": "เลขที่รายการ", "ts": "วันเวลาของรายการ", "from_acct": "บัญชีผู้โอน",
                 "to_acct": "บัญชีผู้รับ", "amount": "จำนวนเงิน"}
GATE_SIGNALS = ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "TEMP-OFFHOURS"]
def gate_capability(tables: dict, cfg: dict) -> pd.DataFrame:
    tx, acc = tables["transactions"], tables.get("accounts")
    miss = [c for c in GATE_BASE if c not in tx.columns or tx[c].notna().sum() == 0]
    vol = gate_volume(tables, cfg) if not miss else {}
    basis = "opened_at" if acc is not None and "opened_at" in acc.columns else "first_seen"
    plan = {}
    for r in GATE_CARDS:
        if miss:
            plan[r] = ("Skip", f"ไม่มีคอลัมน์ {', '.join(miss)} หรือแปลงค่าไม่ได้ทั้งคอลัมน์ ซึ่งการ์ดนี้ต้องใช้ จึงรันไม่ได้ "
                       f"— แก้โดยจับคู่คอลัมน์{' / '.join(GATE_COL_TEXT[c] for c in miss)}ในไฟล์เป็น "
                       f"{', '.join(miss)} ที่จุดยืนยัน 1 แล้วรันใหม่", ", ".join(miss))
        elif r in vol:
            plan[r] = ("Skip", vol[r], "ปริมาณข้อมูลไม่พอ")
        else:
            plan[r] = ("Run", "มีคอลัมน์ที่ต้องใช้ครบและปริมาณข้อมูลผ่านเกณฑ์", "-")
    if not miss:
        if "channel" not in tx.columns and plan["STAT-MAD"][0] == "Run":
            plan["STAT-MAD"] = ("Run", "มี amount ครบ แต่ไม่มี channel จึงเทียบกับทั้งชุดข้อมูล", "channel")
        if plan["MULE-NEW-ACCT"][0] == "Run" and basis == "opened_at":
            plan["MULE-NEW-ACCT"] = ("Run", "basis=opened_at (มี accounts.opened_at)", "-")
        elif plan["MULE-NEW-ACCT"][0] == "Run":
            plan["MULE-NEW-ACCT"] = ("Run", "basis=first_seen (ไม่มี accounts.opened_at จึงใช้วันที่พบรายการแรกในไฟล์ ซึ่ง"
                                     f"อาจไม่ใช่วันเปิดบัญชีจริง; ไม่ได้ประเมิน {vol['_not_assessed']:,} บัญชีที่พบใน "
                                     "MULE.NEW_ACCT_DAYS วันแรกของไฟล์ เพราะอาจเปิดก่อนช่วงข้อมูล)", "accounts.opened_at")
        n_sig, need = sum(plan[r][0] == "Run" for r in GATE_SIGNALS), cfg["MULE.MIN_SIGNALS"]
        if n_sig < need:
            plan["MULE-PATTERN"] = ("Skip", f"การ์ดสัญญาณที่รันได้มี {n_sig} จาก {len(GATE_SIGNALS)} ใบ น้อยกว่า "
                                    f"MULE.MIN_SIGNALS ({need} สัญญาณ AIDA-14) จึงไม่มีบัญชีใดเข้ารูปแบบได้", "ปริมาณข้อมูลไม่พอ")
        if plan["MULE-PATTERN"][0] == "Skip":
            for r in ("MULE-CROSS-TX", "MULE-NETWORK"):
                plan[r] = ("Skip", "MULE-PATTERN ถูก Skip จึงไม่มีชุดบัญชีที่สอดคล้องกับ Mule Account pattern "
                           "ให้วิเคราะห์ข้ามบัญชี", "MULE-PATTERN")
    return pd.DataFrame([(r, *plan[r]) for r in GATE_CARDS], columns=["recipe_id", "decision", "reason", "missing"])


# ---- GATE-VOLUME ----
def vol_baseline(t: pd.DataFrame, cfg: dict) -> dict:
    """Data-volume skips shared by gate_volume (type E) and the C1 plan (any data type): checks that read each
    entity's own history (BEH-VELOCITY, BEH-SPIKE, CPTY-PROFILE, CPTY-NEW-LARGE) and STAT-MAD's group size.
    `t` is clean_tx / base_tx output. Keys are check ids, values the Thai reason."""
    if t.empty:
        return {r: "ไม่มีรายการที่วิเคราะห์ได้หลังตัดรายการโอนเข้าบัญชีตัวเอง ยอด ≤ 0 และรายการที่ไม่มีวันเวลา"
                for r in GATE_CARDS}
    mp, out, k = cfg["BEH.BASELINE.MIN_PERIODS"], {}, " ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร"
    days = int(t["ts"].dt.normalize().groupby(t["from_acct"]).nunique().max())
    months = int(t.groupby("from_acct")["period"].nunique().max())
    if days <= mp["velocity_days"]:
        out["BEH-VELOCITY"] = (f"ไม่มีบัญชีใดมีวันที่มีรายการโอนออกก่อนหน้าครบ {mp['velocity_days']} วัน (สูงสุด "
                               f"{days - 1} วัน) ตาม BEH.BASELINE.MIN_PERIODS{k} จึงสร้าง baseline ไม่ได้")
    if months <= mp["spike_months"]:
        for r in ("BEH-SPIKE", "CPTY-PROFILE"):
            out[r] = (f"ไม่มีบัญชีใดมีเดือนที่มีรายการโอนออกก่อนหน้าครบ {mp['spike_months']} เดือน (สูงสุด "
                      f"{months - 1} เดือน) ตาม BEH.BASELINE.MIN_PERIODS{k} จึงสร้าง baseline ไม่ได้")
    if months < 2:  # CPTY-NEW-LARGE ignores each account's first month in the file
        out["CPTY-NEW-LARGE"] = "ทุกบัญชีมีรายการโอนออกเพียง 1 เดือน จึงยังไม่มีประวัติให้แยกคู่ค้าใหม่ได้"
    grp = t["channel"].fillna("ไม่ระบุ") if "channel" in t.columns else pd.Series("ทั้งชุด", index=t.index)
    if int(grp.value_counts().max()) < cfg["GATE.SAMPLE.MIN"]:
        out["STAT-MAD"] = (f"ทุกกลุ่ม channel มีรายการน้อยกว่า GATE.SAMPLE.MIN ({cfg['GATE.SAMPLE.MIN']} รายการ{k}) "
                           "จึงคำนวณ Modified Z-Score ไม่ได้")
    return out


def gate_volume(tables: dict, cfg: dict) -> dict:
    t = clean_tx(tables["transactions"])
    out = vol_baseline(t, cfg)
    if t.empty:
        return out
    k = " ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร"
    src, fmin = int(t.groupby("to_acct")["from_acct"].nunique().max()), cfg["NET.FUNNEL"]["min_sources"]
    if src < fmin:
        out["NET-FUNNEL"] = f"ไม่มีบัญชีใดรับเงินจากแหล่งครบ {fmin} แหล่ง (สูงสุด {src} แหล่ง) ตาม NET.FUNNEL{k}"
    acc, span, nd = tables.get("accounts"), (t["ts"].max() - t["ts"].min()).days, cfg["MULE.NEW_ACCT_DAYS"]
    seen = pd.concat([t.groupby(c)["ts"].min() for c in ("from_acct", "to_acct")]).groupby(level=0).min()
    out["_not_assessed"] = int((seen <= t["ts"].min() + pd.Timedelta(days=nd)).sum())  # MULE-NEW-ACCT first_seen
    if (acc is None or "opened_at" not in acc.columns) and span <= nd:
        out["MULE-NEW-ACCT"] = (f"ไม่มี opened_at (basis=first_seen) และข้อมูลครอบคลุม {span} วัน ไม่เกิน "
                                f"MULE.NEW_ACCT_DAYS ({nd} วัน{k}) จึงแยกบัญชีใหม่จากบัญชีที่มีอยู่ก่อนช่วงข้อมูลไม่ได้")
    return out


# ---- UNIFY-REFS ----
def ref_list(r) -> list:
    if isinstance(r, str):
        return [p.strip(" '\"") for p in r.strip().strip("[]").split(",") if p.strip(" '\"")]
    if r is None or (isinstance(r, float) and np.isnan(r)):
        return []
    return [str(x) for x in r]
def unify_refs(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: ref_list for UNIFY-FINDINGS and ASSESS-CMP


# ---- UNIFY-FINDINGS ----
FINDING_COLUMNS = ["finding_id", "entity_type", "entity_id", "risk", "period", "evidence_ids",
                   "skill_families", "exposure", "confidence", "materiality", "priority",
                   "review_status", "review_reason", "network_id"]
FINDING_SOURCE_COLUMNS = ["source", "source_label", "explore_id", "reviewer", "promote_reason", "promoted_at"]
FINDING_WORK_COLUMNS = ["member_accts", "record_refs", "data_ref_complete", "internal_amount"]
ABSORB_SIGNALS = ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "TEMP-OFFHOURS"]
def unify_findings(evidence: pd.DataFrame, cfg: dict, networks) -> pd.DataFrame:
    cols = FINDING_COLUMNS + FINDING_WORK_COLUMNS
    if evidence is None or len(evidence) == 0:
        return pd.DataFrame(columns=cols)
    ev = evidence.reset_index(drop=True).copy()
    ev["ok"] = ev["data_ref"].fillna("").astype(str).str.strip() != ""
    nets = networks if networks is not None else pd.DataFrame(columns=["network_id", "member_accts", "internal_amount"])
    members = {n: sorted(m) for n, m in zip(nets["network_id"], nets["member_accts"])}
    if not set(ev.loc[ev["recipe_id"] == "MULE-NETWORK", "entity_id"]) <= set(members):
        raise ValueError("มี Evidence MULE-NETWORK แต่ networks ไม่มีเครือข่ายนั้น — ส่ง tables['_out']['mule_networks']")
    net_of, amount = {a: n for n, m in members.items() for a in m}, dict(zip(nets["network_id"], nets["internal_amount"]))
    pat = ev[ev["recipe_id"] == "MULE-PATTERN"]
    r2 = set(zip(pat["entity_id"], pat["period"]))
    in_r2 = pd.Series([k in r2 for k in zip(ev["entity_id"], ev["period"])], index=ev.index, dtype=bool)
    acct = ev["entity_type"] == "account"
    ev.loc[acct & (ev["risk"] == "R1") & ev["recipe_id"].isin(ABSORB_SIGNALS) & in_r2, "risk"] = "R2"
    to_net = acct & (ev["risk"] == "R3") & ev["entity_id"].isin(list(net_of))
    ev.loc[to_net, "entity_id"], ev.loc[to_net, "entity_type"] = ev.loc[to_net, "entity_id"].map(net_of), "network"
    ev["pk"] = ev["period"].where(ev["entity_type"] != "network", "")  # R3: one finding per network
    rows = []
    for (et, eid, risk, _), g in ev.groupby(["entity_type", "entity_id", "risk", "pk"], sort=True):
        mem = members.get(eid, []) if et == "network" else []
        ctx = pd.concat([g, ev[(ev["entity_type"] == "account") & ev["entity_id"].isin(mem)]]) if mem else g
        rows.append({"entity_type": et, "entity_id": eid, "risk": risk, "period": g["period"].min(),
                     "evidence_ids": list(g["evidence_id"]), "skill_families": sorted(set(ctx["skill_family"])),
                     "network_id": eid if et == "network" else net_of.get(eid), "member_accts": mem,
                     "record_refs": sorted({x for r in g["record_refs"] for x in ref_list(r)}),
                     "data_ref_complete": bool(ctx["ok"].all()), "internal_amount": amount.get(eid)})
    f = pd.DataFrame(rows).sort_values(["risk", "entity_type", "entity_id", "period"], kind="mergesort")
    f["finding_id"] = [f"FND-{cfg['_RUN']['run_id']}-{i + 1}" for i in range(len(f))]
    for c in cols:  # exposure, confidence, materiality, priority, review_* come from ASSESS-CMP
        f[c] = f[c] if c in f.columns else None
    return f[cols].reset_index(drop=True)


# ---- ASSESS-CMP ----
REVIEW_NOTES = {"R2": "บัญชีมีรูปแบบสอดคล้องกับ Mule Account pattern — ควรทบทวนรายบัญชี",
                "R3": "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern — ควรทบทวนทั้งกลุ่ม"}
def assess_cmp(findings: pd.DataFrame, tx: pd.DataFrame, materiality_amount, cfg: dict) -> pd.DataFrame:
    f, m = findings.copy().reset_index(drop=True), materiality_amount
    amt = pd.Series(pd.to_numeric(tx.get("amount", pd.Series(np.nan, index=tx.index)), errors="coerce").to_numpy(),
                    index=tx["tx_id"].astype(str))  # no amount column: no card ran, exposure 0
    amt = amt[~amt.index.duplicated()]
    found = [amt.reindex(sorted(set(ref_list(r)))) for r in f["record_refs"]]
    f["exposure"] = [round(float(v.sum()), 2) for v in found]
    ia = f["internal_amount"] if "internal_amount" in f.columns else pd.Series(None, index=f.index, dtype=object)
    net = (f["entity_type"] == "network") & ia.notna()
    f.loc[net, "exposure"] = ia[net].astype(float).round(2)  # R3 = internal_amount of the network
    n_fam = f["skill_families"].map(len)
    f["confidence"] = ["ต่ำ" if not ok else "สูง" if n >= 2 else "กลาง"  # ASSESS.CONFIDENCE: >= 2 families
                       for ok, n in zip(f["data_ref_complete"].astype(bool), n_fam)]
    if m is None:
        f["materiality"], f["priority"] = "ไม่ได้ประเมิน", f["confidence"]
    else:
        ct = cfg["ASSESS.CLEARLY_TRIVIAL"]
        f["materiality"] = ["สูง" if e >= m else "กลาง" if e >= ct * m else "ต่ำ" for e in f["exposure"]]
        f["priority"] = [cfg["ASSESS.PRIORITY"][c][x] for c, x in zip(f["confidence"], f["materiality"])]
    def reason(risk, conf, missing):
        notes = [REVIEW_NOTES[risk]] if risk in REVIEW_NOTES else []
        if conf == "ต่ำ":
            notes.append("Confidence ต่ำ เพราะ data_ref ของ Evidence ไม่ครบ — ต้องยืนยันแหล่งข้อมูลก่อนใช้ผล")
        if missing:
            notes.append("ไม่พบรายการอ้างอิงบางรายการ (tx_id ใน record_refs ไม่มีในไฟล์) จึงนับยอดเป็น 0")
        if m is None:
            notes.append("ไม่มีฐาน Materiality")
        return "; ".join(notes) if notes else "-"
    f["review_status"] = "รอ Human Review"
    f["review_reason"] = [reason(r, c, bool(v.isna().any())) for r, c, v in zip(f["risk"], f["confidence"], found)]
    return f


# ---- SELECT-AUTO-TRACE ----
PRIORITY_RANK = {"สูง": 0, "กลาง": 1, "ต่ำ": 2}
def select_auto_trace(findings: pd.DataFrame, cfg: dict) -> list:
    f = findings[findings["risk"].isin(["R2", "R3"])].copy()
    f["rank"] = f["priority"].map(PRIORITY_RANK).fillna(len(PRIORITY_RANK))
    f = f.sort_values(["rank", "exposure"], ascending=[True, False], kind="mergesort")
    out, seen, cap = [], set(), cfg["FLOW.AUTO_MAX_ENTITIES"]
    for et, eid, per, mem in zip(f["entity_type"], f["entity_id"], f["period"], f["member_accts"]):
        for a in (sorted(mem) if et == "network" else [eid]):
            if a not in seen and len(out) < cap:
                seen.add(a)
                out.append((a, per))
    return out


# ---- LOG-RUN ----
RUN_LOG_COLUMNS = ["run_id", "timestamp", "stage", "status", "detail", "recipe_id", "recipe_version",
                   "registry_version", "pack_version", "input_sha256"]
RUN_STATUSES = ["OK", "STOP", "SKIP", "REVIEW"]
RUN_STAGES = range(1, 19)  # workflow stages 1-18 (AIDA-01)
def log_run(events: list, cfg: dict) -> pd.DataFrame:
    run = cfg["_RUN"]
    ref = str(run.get("data_ref", ""))
    sha = run.get("input_sha256") or (ref.split("sha256:")[-1] if "sha256:" in ref else "-")
    rows = []
    for e in events:
        if e.get("status") not in RUN_STATUSES:
            raise ValueError(f"status ต้องเป็น OK / STOP / SKIP / REVIEW (ได้รับ {e.get('status')!r})")
        if e.get("stage") not in RUN_STAGES:
            raise ValueError(f"stage ต้องเป็นเลข 1–18 (ได้รับ {e.get('stage')!r})")
        rows.append({"run_id": run["run_id"],
                     "timestamp": e.get("timestamp") or pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S"),
                     "stage": int(e["stage"]), "status": e["status"], "detail": e.get("detail", ""),
                     "recipe_id": e.get("recipe_id", "-"), "recipe_version": e.get("recipe_version", "-"),
                     "registry_version": cfg["REGISTRY.VERSION"], "pack_version": run.get("pack_version", "-"),
                     "input_sha256": sha})
    return pd.DataFrame(rows, columns=RUN_LOG_COLUMNS)


# ---- OUT-BUNDLE ----
OUT_BANNER = ("ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร "
              "ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป")
OUT_LIMITS = ("ข้อจำกัด: การหาเครือข่ายใช้ข้อมูลธุรกรรมเท่านั้น (ไม่มีข้อมูลระบุตัวตน) จึงไม่พบกลุ่มที่เชื่อมกันด้วยข้อมูลร่วม"
              "โดยไม่มีธุรกรรมระหว่างกัน และบัญชีที่เป็นจุดผ่านเงินซึ่งทำหน้าที่ collector อาจรวมกลุ่มที่ไม่เกี่ยวข้องกัน"
              "เป็นเครือข่ายเดียว — ควรทบทวนสมาชิกของแต่ละเครือข่ายก่อนสรุปผล")
NETWORK_COLUMNS = ["network_id", "member_accts", "roles", "internal_tx_count", "internal_amount",
                   "period_start", "period_end"]
def out_bundle(tables: dict, profile, plan, evidence, findings, trails: list, run_log,
               materiality_amount, cfg: dict, materiality_basis: str = "-") -> dict:
    nets = tables.get("_out", {}).get("mule_networks")
    nets = nets if nets is not None else pd.DataFrame(columns=NETWORK_COLUMNS)
    notes = [f"{t['trace_id'].iloc[0]}: {t.attrs['note']}" for t in trails if t.attrs.get("truncated")]
    cn = [n for n in tables.get("_out", {}).get("notes", []) if n["detail"] not in set(run_log["detail"])]
    run_log = pd.concat([run_log, log_run([{"stage": 9, "status": "REVIEW", **n} for n in cn], cfg)],
                        ignore_index=True) if cn else run_log  # card limits (card_note) -> REVIEW
    full = [t for t in trails if len(t)]  # read attrs above: pd.concat drops them
    flows = pd.concat(full, ignore_index=True) if full else pd.DataFrame(columns=TRAIL_COLUMNS)
    tx = tables["transactions"]  # without a base column (e.g. no ts) no card ran: no edges
    t = clean_tx(tx) if all(c in tx.columns for c in GATE_BASE) else pd.DataFrame(columns=GATE_BASE)
    e = t[t["tx_id"].isin({x for r in findings["record_refs"] for x in ref_list(r)})].drop_duplicates("tx_id")
    net_of = {a: n for n, m in zip(nets["network_id"], nets["member_accts"]) for a in m}
    s, d = e["from_acct"].map(net_of), e["to_acct"].map(net_of)
    edges = pd.DataFrame({"source": e["from_acct"], "target": e["to_acct"], "amount": e["amount"], "ts": e["ts"],
                          "tx_id": e["tx_id"], "network_id": s.where(s == d)}).reset_index(drop=True)
    m, ct = materiality_amount, cfg["ASSESS.CLEARLY_TRIVIAL"]
    rows = [("ฐาน Materiality", "ไม่ได้ประเมิน" if m is None else m,
             "ผู้ใช้ไม่ได้ระบุฐาน — Priority = ระดับ Confidence" if m is None else materiality_basis)]
    if m is not None:
        rows += [("Materiality สูง", f"exposure ≥ {m:,.2f}", "ยอดเงินที่เกี่ยวข้องตั้งแต่ฐาน Materiality"),
                 ("Materiality กลาง", f"exposure ≥ {ct * m:,.2f}", f"ASSESS.CLEARLY_TRIVIAL = {ct:.0%} ของฐาน "
                  "(ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร)"),
                 ("Materiality ต่ำ", f"exposure < {ct * m:,.2f}", "เล็กน้อยมากเมื่อเทียบกับฐาน")]
    rows += [(f"จำนวน Finding ที่ Materiality {k}", int(v), "") for k, v in findings["materiality"].value_counts().items()]
    return {"profile": profile, "plan": plan, "evidence": evidence, "findings": findings,
            "mule_networks": nets, "flows": flows, "run_log": run_log, "run_id": cfg["_RUN"]["run_id"],
            "materiality": pd.DataFrame(rows, columns=["item", "value", "detail"]),
            "prep": tables.get("_prep", {}), "flow_notes": notes, "edges": edges,
            "card_notes": [f"{n['recipe_id']}: {n['detail']}" for n in tables.get("_out", {}).get("notes", [])]}


# ---- OUT-CELL ----
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")  # spreadsheet apps read these as the start of a formula
def no_formula(v):
    return "'" + v if isinstance(v, str) and v.startswith(FORMULA_START) and v != "-" else v
def text_cols(df: pd.DataFrame, fn) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if not (pd.api.types.is_numeric_dtype(out[c]) or pd.api.types.is_datetime64_any_dtype(out[c])):
            out[c] = out[c].map(fn)
    return out
def out_cell(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: no_formula and text_cols for OUT-WORKBOOK and OUT-NETWORK-CSV


# ---- OUT-WORKBOOK ----
EXCEL_CELL_MAX = 32767  # characters Excel can store in one cell (technical limit, not an audit threshold)
OUT_SHEETS = {"Dataset_Profile": "ภาพรวมข้อมูลและการตรวจคุณภาพ", "Analysis_Plan": "การ์ดที่รัน / Skip พร้อมเหตุผล",
              "Evidence": "สัญญาณรายการต่อการ์ด + record_refs (tx_id) และ data_ref สำหรับย้อนกลับไปยังรายการต้นทาง",
              "Findings": "ข้อสังเกตที่รวมจาก Evidence พร้อม Confidence / Materiality / Priority — กรอก reviewer, "
              "disposition, review_date หลัง Human Review", "Mule_Networks": "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกัน "
              "และบทบาทในเครือข่าย (ไม่ใช่ข้อสรุป)", "Money_Flow": "เส้นทางเงินตามทอด (hop) ของแต่ละ trace",
              "Materiality": "ฐานและเกณฑ์ที่ใช้", "Run_Log": "บันทึกการรันเพื่อทำซ้ำได้"}
def cell_text(v):
    if isinstance(v, dict):
        v = ", ".join(f"{k}: {x}" for k, x in v.items())
    elif isinstance(v, (list, tuple, set, np.ndarray)):
        v = ", ".join(str(x) for x in v)
    v = no_formula(ILLEGAL_CHARACTERS_RE.sub("", v)) if isinstance(v, str) else v
    return v[:EXCEL_CELL_MAX - 1] + "…" if isinstance(v, str) and len(v) > EXCEL_CELL_MAX else v
NOT_E_TEXT = "ไม่เกี่ยวข้องกับข้อมูลประเภทนี้"  # Mule_Networks / Money_Flow stay in the Workbook for data that is not type E
OUT_SHEETS_C1 = {"Intake_Review": "สิ่งที่ผู้ตรวจสอบยืนยันใน Intake: บริบท, Risk Concern, ความพอเพียง, ความเสี่ยงที่แนะนำ, คำตอบ",
                 "Data_Dictionary": "ความหมายคอลัมน์, บทบาท, ความหมายของค่ารหัส, ผู้ยืนยัน และวันที่",
                 "Data_Request": "ข้อมูลที่ควรขอเพิ่มเพื่อให้วิเคราะห์ความเสี่ยงที่ขอได้ครบ",
                 "Exploratory": "การวิเคราะห์ในโหมดสำรวจ (ยังไม่ผ่านการรับรอง): คำถาม โค้ดเต็ม ผล และการเลื่อนเป็น Finding"}
def out_workbook(bundle: dict, path: str, cfg: dict) -> str:
    b, p = bundle, bundle.get("prep") or {}
    c1 = "intake_review" in b  # C1 bundle: 13 sheets; a B1 bundle keeps its nine
    not_e = c1 and b.get("data_type") != "E"
    o, n = OUT_SHEETS, OUT_SHEETS_C1
    sheet_desc = ({**{k: n[k] for k in ("Intake_Review", "Data_Dictionary", "Data_Request")},
                   **{k: o[k] for k in ("Dataset_Profile", "Analysis_Plan", "Evidence", "Findings")},
                   "Exploratory": n["Exploratory"], **{k: o[k] for k in ("Mule_Networks", "Money_Flow", "Materiality", "Run_Log")}}
                  if c1 else o)
    readme = [OUT_BANNER, f"run_id: {b['run_id']} | Registry version: {cfg['REGISTRY.VERSION']}",
              *([] if not_e else [OUT_LIMITS]),
              f"รูปแบบวันที่ที่ใช้แปลง: {p.get('date_format', '-')} | แปลงปี พ.ศ.: {'ใช่' if p.get('be_converted') else 'ไม่'}"
              f" | วันและเดือน ≤ 12 ทั้งคู่ {p.get('ambiguous_dates', 0)} รายการ", *b.get("org_notes", []),
              *b.get("card_notes", []), *b["flow_notes"],
              "วิธีอ่านไฟล์ (sheet ตามลำดับ):"] + [f"{k}: {v}" for k, v in sheet_desc.items()]
    f = b["findings"]
    if c1 and (f["source"] == "exploratory").any():
        readme.insert(2, f"Finding ที่มีป้าย \"{EXPLORE_LABEL}\" มาจากโหมดสำรวจที่เลื่อนโดยผู้ตรวจสอบ ({EXPLORE_NOT_CERTIFIED}; "
                         "Confidence ไม่เกินกลาง) — ป้ายนี้ติดกับ Finding ถาวร")
    col = lambda c: f[c] if c in f.columns else None  # noqa: E731 - B1 Findings have no source columns
    fnd = f[FINDING_COLUMNS].assign(member_accts=f["member_accts"], reviewer=col("reviewer"), disposition=None,
                                    review_date=f["promoted_at"].map(lambda x: str(x)[:10] if isinstance(x, str) else None)
                                    if "promoted_at" in f.columns else None)
    if "source" in f.columns:
        fnd = fnd.assign(source=f["source"], source_label=f["source_label"], explore_id=f["explore_id"],
                         promote_reason=f["promote_reason"])
    notes = b["flow_notes"] or ["ไล่เส้นทางเงินครบทุก trace (ไม่ถึงขีดจำกัด FLOW.MAX_TRAIL_ROWS)"]
    na = pd.DataFrame({"หมายเหตุ": [NOT_E_TEXT]})
    sheets = {"README": pd.DataFrame({"README": readme})}
    if c1:
        sheets.update(Intake_Review=b["intake_review"], Data_Dictionary=b["data_dictionary"], Data_Request=b["data_request"])
    sheets.update(Dataset_Profile=b["profile"], Analysis_Plan=b["plan"], Evidence=b["evidence"], Findings=fnd)
    if c1:
        sheets["Exploratory"] = b["exploratory"]
    sheets.update(Mule_Networks=na if not_e else b["mule_networks"], Money_Flow=na if not_e else b["flows"],
                  Materiality=b["materiality"], Run_Log=b["run_log"])
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            top = len(notes) + 1 if name == "Money_Flow" and not not_e else 0
            text_cols(df, cell_text).to_excel(xw, sheet_name=name, index=False, startrow=top)
            for i, n in enumerate(notes if top else [], 1):
                xw.sheets[name].cell(row=i, column=1, value=cell_text(n))
    return path


# ---- OUT-NETWORK-CSV ----
def out_network_csv(bundle: dict, folder: str, cfg: dict) -> list:
    os.makedirs(folder, exist_ok=True)
    f, nets, e = bundle["findings"], bundle["mule_networks"], bundle["edges"]
    role, net_of, fids = {}, {}, {}
    for n, roles in zip(nets["network_id"], nets["roles"]):
        for a, r in roles.items():
            role[a], net_of[a] = r, n
    for fid, et, eid, mem in zip(f["finding_id"], f["entity_type"], f["entity_id"], f["member_accts"]):
        for a in (list(mem) if et == "network" else [eid]):
            fids.setdefault(a, []).append(fid)
    r2 = set(f.loc[(f["risk"] == "R2") & (f["entity_type"] == "account"), "entity_id"])
    accts = sorted(set(fids) | set(e["source"]) | set(e["target"]))
    nodes = pd.DataFrame({"node_id": accts, "role": [role.get(a, "mule" if a in r2 else "other") for a in accts],
                          "network_id": [net_of.get(a) for a in accts],
                          "finding_ids": ["; ".join(fids.get(a, [])) for a in accts]})
    paths = [os.path.join(folder, n) for n in ("nodes.csv", "edges.csv", "flows.csv")]
    for path, df in zip(paths, (nodes, e, bundle["flows"])):
        text_cols(df, no_formula).to_csv(path, index=False, encoding="utf-8-sig")
    return paths


# ---- OUT-DASHBOARD ----
DASH_PLACEHOLDER, DASH_END = "/*__AIDA_DATA__*/", "<!-- END-OF-TEMPLATE -->"
def out_dashboard(bundle: dict, template: str, path: str, cfg: dict) -> str:
    if template.count(DASH_PLACEHOLDER) != 1 or DASH_END not in template:
        raise ValueError(f"template Dashboard จาก AIDA-16 ไม่ครบ (ต้องมี {DASH_PLACEHOLDER} 1 จุด และบรรทัด {DASH_END}) "
                         "— ดึง template จาก AIDA-16 ใหม่ทั้งหมด ห้ามเขียนหรือแก้ template เอง")
    def rows(df):
        return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
    f, e = bundle["findings"], bundle["edges"]
    keep = [c for c in FINDING_COLUMNS + ["member_accts", "record_refs"] + FINDING_SOURCE_COLUMNS if c in f.columns]
    ui = {k: rows(bundle[k]) for k in ("profile", "plan", "evidence", "mule_networks", "flows",
                                       "materiality", "run_log")}
    ui.update(findings=rows(f[keep]), edges=rows(e[e["network_id"].notna()]), run_id=bundle["run_id"],
              flow_notes=bundle["flow_notes"], card_notes=bundle.get("card_notes", []),
              prep=bundle.get("prep", {}), limits=OUT_LIMITS if bundle.get("data_type", "E") == "E" else "",
              registry_version=cfg["REGISTRY.VERSION"])
    if "intake_review" in bundle:  # C1 bundle: Intake tab, exploratory entries, names of the risks in use
        ui.update(intake={"review": rows(bundle["intake_review"]), "dictionary": rows(bundle["data_dictionary"]),
                          "requests": rows(bundle["data_request"])},
                  exploratory=rows(bundle["exploratory"]), data_type=bundle.get("data_type") or "",
                  risk_names={r: _risk_name(r) for r in sorted(set(f["risk"]) | set(RISK_LIBRARY))})
    data = json.dumps(ui, ensure_ascii=False, default=str).replace("<", "\\u003c")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(template.replace(DASH_PLACEHOLDER, data))
    return path


# ---- STAT-MAD ----
def stat_mad(tables: dict, cfg: dict) -> pd.DataFrame:
    t = base_tx(tables)
    lim, n_min = cfg["STAT.MAD.THRESHOLD"], cfg["GATE.SAMPLE.MIN"]
    if "channel" in t.columns:
        t["grp"] = "ช่องทาง " + t["channel"].fillna("ไม่ระบุ").astype(str)
    else:
        t["grp"] = "ทั้งชุดข้อมูล"
    parts = []
    for _, g in t.groupby("grp"):
        med = g["amount"].median()
        mad = (g["amount"] - med).abs().median()
        if len(g) < n_min or mad == 0:
            continue
        z = (0.6745 * (g["amount"] - med) / mad).abs()  # 0.6745 = Modified Z constant
        parts.append(g.assign(z=z)[z > lim])
    hit = pd.concat(parts) if parts else t.iloc[0:0].assign(z=0.0)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "modified_z_amount", "value": hit["z"].round(2), "threshold": lim,
        "explanation": [
            f"รายการ {i} ยอด {a:,.2f} มี Modified Z-Score {z:.2f} ใน{g} สูงกว่าเกณฑ์ {lim} "
            f"(STAT.MAD.THRESHOLD ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for i, a, z, g in zip(hit["tx_id"], hit["amount"], hit["z"], hit["grp"])],
        "record_refs": [[i] for i in hit["tx_id"]]})
    return evidence_rows("STAT-MAD", "1.0", "5.1 Statistical", "R1",
                         "STAT.MAD.THRESHOLD", one_per_month(found), cfg)


# ---- BEH-VELOCITY ----
def beh_velocity(tables: dict, cfg: dict) -> pd.DataFrame:
    t = base_tx(tables)
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["velocity_days"]
    k, floor = cfg["BEH.DEVIATION"], cfg["BEH.VELOCITY.SD_FLOOR"]
    d = (t.assign(day=t["ts"].dt.strftime("%Y-%m-%d"))
         .groupby(["from_acct", "day", "period"])
         .agg(n=("tx_id", "size"), refs=("tx_id", list)).reset_index())
    hit = beyond_baseline(d, "from_acct", "n", need, k, floor)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "tx_per_day", "value": hit["n"], "threshold": hit["thr"].round(2),
        "explanation": [
            f"วันที่ {dy} มีรายการโอนออก {n} รายการ สูงกว่าเกณฑ์จาก baseline ของบัญชีเดียวกัน "
            f"({baseline_formula(mu, sd, k, th, floor)}; BEH.DEVIATION, BEH.VELOCITY.SD_FLOOR "
            f"และ BEH.BASELINE.MIN_PERIODS ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
            f"— ควรตรวจสอบเพิ่มเติม"
            for dy, n, mu, sd, th in zip(hit["day"], hit["n"], hit["mu"], hit["sd"], hit["thr"])],
        "record_refs": hit["refs"]})
    return evidence_rows("BEH-VELOCITY", "1.0", "5.3 Behavioral", "R1",
                         "BEH.DEVIATION", one_per_month(found), cfg)


# ---- BEH-SPIKE ----
def beh_spike(tables: dict, cfg: dict) -> pd.DataFrame:
    t = base_tx(tables)
    need = cfg["BEH.BASELINE.MIN_PERIODS"]["spike_months"]
    k = cfg["BEH.DEVIATION"]
    d = (t.groupby(["from_acct", "period"])
         .agg(amt=("amount", "sum"), refs=("tx_id", list)).reset_index())
    hit = beyond_baseline(d, "from_acct", "amt", need, k)
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "amount_per_month", "value": hit["amt"].round(2),
        "threshold": hit["thr"].round(2),
        "explanation": [
            f"ยอดโอนออกเดือน {p} รวม {a:,.2f} สูงกว่าเกณฑ์จาก baseline รายเดือนของบัญชีเดียวกัน "
            f"({baseline_formula(mu, sd, k, th)}; BEH.DEVIATION และ BEH.BASELINE.MIN_PERIODS "
            f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, a, mu, sd, th in zip(hit["period"], hit["amt"], hit["mu"], hit["sd"], hit["thr"])],
        "record_refs": hit["refs"]})
    return evidence_rows("BEH-SPIKE", "1.0", "5.3 Behavioral", "R1",
                         "BEH.DEVIATION", one_per_month(found), cfg)


# ---- TEMP-OFFHOURS ----
def temp_offhours(tables: dict, cfg: dict) -> pd.DataFrame:
    t = base_tx(tables)
    if len(t) and (t["ts"] == t["ts"].dt.normalize()).all():
        # date only (every time is 00:00): the time of day is unknown, so nothing can be called off-hours
        card_note(tables, "TEMP-OFFHOURS", "1.1", "คอลัมน์วันที่มีเฉพาะวัน ไม่มีเวลาของรายการ จึงตัดสินรายการนอกเวลาทำการไม่ได้")
        return evidence_rows("TEMP-OFFHOURS", "1.1", "5.4 Temporal", "R1", "TEMP.OFF_HOURS", pd.DataFrame(), cfg)
    oh, k, share = cfg["TEMP.OFF_HOURS"], cfg["TEMP.OFF_HOURS.MIN_TX"], cfg["TEMP.OFF_HOURS.MIN_SHARE"]
    hhmm = t["ts"].dt.strftime("%H:%M")
    off = (hhmm < oh["start"]) | (hhmm >= oh["end"])
    rule = f"นอกเวลา {oh['start']}–{oh['end']}"
    if oh["weekend"]:
        off = off | (t["ts"].dt.dayofweek >= 5)  # 5, 6 = Saturday, Sunday
        rule += " หรือวันเสาร์-อาทิตย์"
    d = (t.assign(off=off).groupby(["from_acct", "period"])
         .agg(n=("off", "sum"), total=("tx_id", "size")).reset_index())
    refs = t[off].groupby(["from_acct", "period"])["tx_id"].agg(list)
    d = d[(d["n"] >= k) & (d["n"] / d["total"] >= share)]
    found = pd.DataFrame({
        "entity_id": d["from_acct"], "period": d["period"], "metric": "offhours_tx_count",
        "value": d["n"].astype(int), "threshold": f"≥ {k} รายการ และ ≥ {share:.0%} ของรายการโอนออก ({rule})",
        "explanation": [
            f"เดือน {p} มีรายการโอนออก {n} จาก {m} รายการ ({n / m:.0%}){rule} — ครบทั้ง "
            f"TEMP.OFF_HOURS.MIN_TX ≥ {k} รายการ และ TEMP.OFF_HOURS.MIN_SHARE ≥ {share:.0%} (TEMP.OFF_HOURS "
            f"และเกณฑ์ทั้งสองเป็นค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, n, m in zip(d["period"], d["n"], d["total"])],
        "record_refs": [refs[(a, p)] for a, p in zip(d["from_acct"], d["period"])]})
    return evidence_rows("TEMP-OFFHOURS", "1.1", "5.4 Temporal", "R1",
                         "TEMP.OFF_HOURS", found, cfg)


# ---- NET-CYCLE ----
def net_cycle(tables: dict, cfg: dict) -> pd.DataFrame:
    from bisect import bisect_left, bisect_right
    t, c, cap = clean_tx(tables["transactions"]), cfg["NET.CYCLE"], cfg["NET.CYCLE.MAX_PATHS"]
    win = pd.Timedelta(days=c["days"])
    while not (keep := t["from_acct"].isin(t["to_acct"]) & t["to_acct"].isin(t["from_acct"])).all():
        t = t[keep]  # a transfer on a cycle needs an inflow to its sender and an outflow from its receiver
    out = {a: (list(g["ts"]), list(g["to_acct"]), list(g["tx_id"])) for a, g in t.groupby("from_acct")}
    cycles, steps, capped = {}, {}, set()  # budget: NET.CYCLE.MAX_PATHS per month of the first hop
    for t0, a0, b0, x0, p0 in zip(t["ts"], t["from_acct"], t["to_acct"], t["tx_id"], t["period"]):
        stack = [(b0, t0, (a0, b0), (x0,))]
        while stack and steps.get(p0, 0) < cap:
            node, ts, path, refs = stack.pop()
            steps[p0] = steps.get(p0, 0) + 1
            tss, tos, txs = out.get(node, ([], [], []))
            seen = set()  # earliest edge per (node, next account) only
            for j in range(bisect_left(tss, ts), bisect_right(tss, t0 + win)):
                if tos[j] in seen:
                    continue
                seen.add(tos[j])
                if tos[j] == a0 and len(path) >= c["min_len"]:
                    i = path.index(min(path))  # same accounts in rotation = same cycle
                    cycles.setdefault((path[i:] + path[:i], p0), (path, refs + (txs[j],)))
                elif tos[j] not in path and len(path) < c["max_len"]:
                    stack.append((tos[j], tss[j], path + (tos[j],), refs + (txs[j],)))
        if stack:  # budget of this month used up with paths left unsearched
            capped.add(p0)
    note = {p: card_note(tables, "NET-CYCLE", "1.1", f"เดือน {p}: ค้นหาถึงขีดจำกัด NET.CYCLE.MAX_PATHS ({cap:,} "
            "เส้นทางต่อเดือน) แล้วหยุด ผลของเดือนนี้อาจไม่ครบ (ไม่พบวงไม่ได้แปลว่าไม่มีวงเงินหมุนวน) — ควรแบ่งไฟล์"
            "หรือจำกัดบัญชีให้แคบลง") for p in sorted(capped)}  # shown even when no cycle is found
    best = {}  # (account, month) -> [first cycle found, its refs, number of cycles]
    for (_, p0), (path, refs) in cycles.items():
        for a in path:
            best.setdefault((a, p0), [path, refs, 0])[2] += 1
    found = pd.DataFrame([{
        "entity_id": a, "period": p0, "metric": "cycle_length", "value": len(path), "threshold": c["max_len"],
        "record_refs": list(refs), "explanation": f"บัญชีอยู่ในวงเงินหมุนวน {' → '.join(path + (path[0],))} "
        f"({len(path)} ทอด ภายใน {c['days']} วัน; พบ {n} วงในเดือนนี้ แสดงวงแรก; NET.CYCLE {c['min_len']}–"
        f"{c['max_len']} ทอด ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
        + (f" — {note[p0]}" if p0 in note else "")} for (a, p0), (path, refs, n) in best.items()])
    return evidence_rows("NET-CYCLE", "1.1", "5.9 Network", "R1", "NET.CYCLE", found, cfg)


# ---- NET-FUNNEL ----
def net_funnel(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    f = cfg["NET.FUNNEL"]
    win = pd.Timedelta(days=f["days"]).to_timedelta64()
    outs_by = {a: g for a, g in t.groupby("from_acct")}
    rows = []
    for acct, ins in t.groupby("to_acct"):
        outs = outs_by.get(acct)
        if outs is None or ins["from_acct"].nunique() < f["min_sources"]:
            continue  # no outflow at all, or too few sources: no signal
        ti, to, src = ins["ts"].to_numpy(), outs["ts"].to_numpy(), ins["from_acct"].to_numpy()
        ai, ao = ins["amount"].to_numpy(), outs["amount"].to_numpy()
        lo, hi = np.searchsorted(ti, ti, "left"), np.searchsorted(ti, ti + win, "left")  # window [t0, t0 + days)
        olo, ohi = np.searchsorted(to, ti, "left"), np.searchsorted(to, ti + win, "left")
        ci, co = np.concatenate([[0.0], ai.cumsum()]), np.concatenate([[0.0], ao.cumsum()])
        cand = (ohi > olo) & (hi - lo >= f["min_sources"]) & (co[ohi] - co[olo] >= 0.999 * f["out_ratio"] * (ci[hi] - ci[lo]))
        for i in np.flatnonzero(cand):  # exact check on the window itself (cumulative sums only pre-filter)
            n_src, amt_in, amt_out = len(set(src[lo[i]:hi[i]])), ai[lo[i]:hi[i]].sum(), ao[olo[i]:ohi[i]].sum()
            if n_src < f["min_sources"] or amt_in <= 0 or amt_out / amt_in < f["out_ratio"]:
                continue
            ratio = amt_out / amt_in
            rows.append({"entity_id": acct, "period": ins["period"].iloc[i], "metric": "out_in_ratio",
                         "value": round(ratio, 4), "threshold": f["out_ratio"],
                         "explanation": f"รับเงินจาก {n_src} แหล่ง รวม {amt_in:,.2f} แล้วส่งต่อ "
                         f"{ratio:.0%} ภายใน {f['days']} วัน (NET.FUNNEL ≥ {f['min_sources']} แหล่ง "
                         f"และ ≥ {f['out_ratio']:.0%} ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                         f"— ควรตรวจสอบเพิ่มเติม",
                         "record_refs": list(ins["tx_id"].iloc[lo[i]:hi[i]]) + list(outs["tx_id"].iloc[olo[i]:ohi[i]])})
    found = one_per_month(pd.DataFrame(rows, columns=["entity_id", "period", "metric", "value",
                                                      "threshold", "explanation", "record_refs"]))
    return evidence_rows("NET-FUNNEL", "1.1", "5.9 Network", "R1", "NET.FUNNEL", found, cfg)


# ---- MULE-DWELL ----
def mule_dwell(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    hrs, need = cfg["MULE.DWELL_HOURS"], cfg["MULE.DWELL_MIN_PAIRS"]
    outs_by = {a: g for a, g in t.groupby("from_acct")}
    rows = []
    for acct, ins in t.groupby("to_acct"):
        outs = outs_by.get(acct)
        if outs is None:
            continue  # no outflow at all: no pair, no signal
        j = np.searchsorted(outs["ts"].to_numpy(), ins["ts"].to_numpy(), side="left")
        ok = j < len(outs)  # inflows followed by an outflow
        p = pd.DataFrame({"in_tx": ins["tx_id"].to_numpy()[ok], "in_ts": ins["ts"].to_numpy()[ok],
                          "period": ins["period"].to_numpy()[ok],
                          "out_tx": outs["tx_id"].to_numpy()[j[ok]],
                          "out_ts": outs["ts"].to_numpy()[j[ok]]})
        p = p.drop_duplicates("out_tx", keep="last")  # one outflow pairs with its latest inflow only
        p["hours"] = (p["out_ts"] - p["in_ts"]) / pd.Timedelta(hours=1)
        for per, g in p[p["hours"] <= hrs].groupby("period"):
            if len(g) < need:
                continue
            rows.append({"entity_id": acct, "period": per, "metric": "short_dwell_pairs",
                         "value": len(g), "threshold": need,
                         "explanation": f"เดือน {per} มีเงินเข้าแล้วโอนออกต่อภายใน {hrs} ชั่วโมง "
                         f"{len(g)} คู่ (median {g['hours'].median():.1f} ชั่วโมง; MULE.DWELL_HOURS และ "
                         f"MULE.DWELL_MIN_PAIRS ≥ {need} คู่ ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                         f"— ควรตรวจสอบเพิ่มเติม",
                         "record_refs": list(g["in_tx"]) + list(g["out_tx"])})
    return evidence_rows("MULE-DWELL", "1.0", "5.4 Temporal", "R1", "MULE.DWELL_HOURS",
                         pd.DataFrame(rows), cfg)


# ---- MULE-NEW-ACCT ----
def mule_new_acct(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    days, need = cfg["MULE.NEW_ACCT_DAYS"], cfg["MULE.NEW_ACCT_MIN_TX"]
    win = pd.Timedelta(days=days)
    inv = pd.concat([t[["tx_id", "ts", "period", s]].rename(columns={s: "acct"})
                     for s in ("from_acct", "to_acct")]).sort_values("ts", kind="mergesort")
    seen = inv.groupby("acct")["ts"].min()
    start = seen.where(seen > t["ts"].min() + win)  # first_seen: skip accounts seen at the file start
    basis = pd.Series("first_seen", index=seen.index)
    acc = tables.get("accounts")
    if acc is not None and "opened_at" in acc.columns:
        opened = (pd.to_datetime(acc["opened_at"], errors="coerce")
                  .groupby(acc["acct_id"]).min().reindex(seen.index))
        basis = basis.where(opened.isna(), "opened_at")
        start = opened.fillna(start)
    inv = inv.assign(start=inv["acct"].map(start)).dropna(subset=["start"])
    inv = inv[(inv["ts"] >= inv["start"]) & (inv["ts"] <= inv["start"] + win)]
    rows = []
    for acct, g in inv.groupby("acct"):
        if len(g) < need:
            continue
        hit, s0, b = g.iloc[need - 1], g["start"].iloc[0], basis[acct]
        note = "" if b == "opened_at" else (" — ไม่มี opened_at จึงใช้วันที่พบรายการแรกในไฟล์ "
                                            "ซึ่งอาจไม่ใช่วันเปิดบัญชีจริง")
        rows.append({"entity_id": acct, "period": hit["period"], "metric": "tx_within_new_acct_days",
                     "value": len(g), "threshold": need,
                     "explanation": f"บัญชีมี {len(g)} รายการ (รับและโอน) ภายใน {days} วันนับจาก "
                     f"{s0:%Y-%m-%d} (basis={b}{note}) และมีครบ {need} รายการเมื่ออายุบัญชี "
                     f"{(hit['ts'] - s0).days} วัน (MULE.NEW_ACCT_DAYS และ MULE.NEW_ACCT_MIN_TX "
                     f"ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม",
                     "record_refs": list(g["tx_id"])})
    return evidence_rows("MULE-NEW-ACCT", "1.0", "5.7 Rule-Based", "R1", "MULE.NEW_ACCT_DAYS",
                         pd.DataFrame(rows), cfg)


# ---- MULE-PATTERN ----
MULE_SIGNALS = {"NET-FUNNEL": "รับเงินหลายแหล่งแล้วโอนออกเกือบหมด",
                "MULE-DWELL": "เงินอยู่ในบัญชีช่วงสั้น",
                "MULE-NEW-ACCT": "บัญชีใหม่แล้วมีรายการมากทันที",
                "BEH-VELOCITY": "โอนถี่กว่า baseline ของบัญชี",
                "TEMP-OFFHOURS": "ทำรายการนอกเวลาทำการ"}
def mule_pattern(tables: dict, cfg: dict) -> pd.DataFrame:
    ev, need = tables.get("evidence"), cfg["MULE.MIN_SIGNALS"]
    rows = []
    if ev is not None and len(ev) > 0:
        s = ev[ev["recipe_id"].isin(list(MULE_SIGNALS)) & (ev["entity_type"] == "account")]
        for (acct, per), g in s.groupby(["entity_id", "period"]):
            sig = [r for r in MULE_SIGNALS if r in set(g["recipe_id"])]
            if len(sig) < need:
                continue
            rows.append({"entity_id": acct, "period": per, "metric": "mule_signal_count",
                         "value": len(sig), "threshold": need,
                         "explanation": f"เดือน {per} บัญชีมีสัญญาณ {len(sig)} จาก {len(MULE_SIGNALS)} "
                         "สัญญาณ: " + ", ".join(f"{r} ({MULE_SIGNALS[r]})" for r in sig)
                         + f" — สอดคล้องกับ Mule Account pattern (MULE.MIN_SIGNALS ≥ {need} สัญญาณ "
                         "ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) เป็นข้อสังเกตที่ควรตรวจสอบเพิ่มเติม "
                         "ไม่ใช่ข้อสรุปเกี่ยวกับเจ้าของบัญชี",
                         "record_refs": sorted({str(x) for r in g["record_refs"] for x in r})})
    return evidence_rows("MULE-PATTERN", "1.0", "5.10 Hybrid", "R2", "MULE.MIN_SIGNALS",
                         pd.DataFrame(rows), cfg)


# ---- MULE-CROSS-TX ----
def mule_cross_tx(tables: dict, cfg: dict) -> pd.DataFrame:
    t, ev = clean_tx(tables["transactions"]), tables.get("evidence")
    has = ev is not None and len(ev) > 0
    r2 = ev[ev["recipe_id"] == "MULE-PATTERN"] if has else pd.DataFrame(columns=["entity_id", "period"])
    mules = set(r2["entity_id"] + "|" + r2["period"])  # a mule only in the months of its R2 evidence
    need, days = cfg["MULE.CROSS.MIN_LINKS"], cfg["FLOW.WINDOW_DAYS"]
    fm, tm = (t["from_acct"] + "|" + t["period"]).isin(mules), (t["to_acct"] + "|" + t["period"]).isin(mules)
    roles = [("mule_to_mule", t[fm & tm], "from_acct", "to_acct"),
             ("mule_to_mule", t[fm & tm], "to_acct", "from_acct"),
             ("collector", t[fm & ~tm], "to_acct", "from_acct"),
             ("feeder", t[~fm & tm], "from_acct", "to_acct")]
    rows = []
    for role, e, side, other in roles:
        for acct, g in e.groupby(side):
            for t0, p0 in zip(g["ts"], g["period"]):
                w = g[(g["ts"] >= t0) & (g["ts"] <= t0 + pd.Timedelta(days=days))]
                if role == "mule_to_mule" or w[other].nunique() >= need:
                    rows.append((acct, p0, role, w[other].nunique(), list(w["tx_id"])))
    if not rows:
        return evidence_rows("MULE-CROSS-TX", "1.1", "5.9 Network", "R3", "MULE.CROSS.MIN_LINKS",
                             pd.DataFrame(), cfg)
    f = (pd.DataFrame(rows, columns=["entity_id", "period", "value", "n", "refs"])
         .groupby(["entity_id", "period", "value"], as_index=False)
         .agg(n=("n", "max"), record_refs=("refs", lambda s: sorted({x for r in s for x in r}))))
    text = {"mule_to_mule": "มีธุรกรรมกับบัญชีอื่น {n} บัญชีที่สอดคล้องกับ Mule Account pattern "
                            "เช่นเดียวกับบัญชีนี้ (บทบาท mule_to_mule ในเครือข่าย)",
            "collector": "รับเงินจากบัญชีที่สอดคล้องกับ Mule Account pattern {n} บัญชีภายใน {d} วัน "
                         "(บทบาทผู้รับรวม collector ในเครือข่าย)",
            "feeder": "โอนเงินให้บัญชีที่สอดคล้องกับ Mule Account pattern {n} บัญชีภายใน {d} วัน "
                      "(บทบาทผู้ส่งเงินเข้า feeder ในเครือข่าย)"}
    found = f.assign(metric="role", threshold=need, explanation=[
        f"เดือน {p} " + text[v].format(n=n, d=days) + " — บทบาทอธิบายตำแหน่งในเครือข่าย ไม่ใช่ข้อสรุป "
        f"(MULE.CROSS.MIN_LINKS ≥ {need} บัญชี และ FLOW.WINDOW_DAYS ค่ามาตรฐานจาก AIDA-14 "
        "ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม" for p, v, n in zip(f["period"], f["value"], f["n"])])
    return evidence_rows("MULE-CROSS-TX", "1.1", "5.9 Network", "R3", "MULE.CROSS.MIN_LINKS", found, cfg)


# ---- MULE-NETWORK ----
def mule_network(tables: dict, cfg: dict) -> pd.DataFrame:
    t, ev = clean_tx(tables["transactions"]), tables.get("evidence")
    ev = ev if ev is not None and len(ev) > 0 else pd.DataFrame(columns=EVIDENCE_COLUMNS)
    size, x = cfg["MULE.NETWORK.MIN_SIZE"], ev[ev["recipe_id"] == "MULE-CROSS-TX"]
    mules = set(ev.loc[ev["recipe_id"] == "MULE-PATTERN", "entity_id"])
    roles, parent = {}, {}
    for a, v in zip(x["entity_id"], x["value"]):
        roles.setdefault(a, set()).add("mule" if a in mules else v)
    def root(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    links = t[t["tx_id"].isin({r for refs in x["record_refs"] for r in refs})]
    for a, b in zip(links["from_acct"], links["to_acct"]):
        parent[root(a)] = root(b)
    groups = {}
    for a in list(parent):
        groups.setdefault(root(a), []).append(a)
    groups = sorted((sorted(g) for g in groups.values() if len(g) >= size), key=lambda g: (-len(g), g[0]))
    nets, rows = [], []
    for n, members in enumerate(groups, 1):
        inner = t[t["from_acct"].isin(members) & t["to_acct"].isin(members)]
        role = {a: "/".join(sorted(roles.get(a, {"mule"}))) for a in members}
        k = {r: sum(r in v for v in role.values()) for r in ("mule", "collector", "feeder")}
        d0, d1 = inner["ts"].min().strftime("%Y-%m-%d"), inner["ts"].max().strftime("%Y-%m-%d")
        nets.append([f"NET-{n}", members, role, len(inner), round(float(inner["amount"].sum()), 2), d0, d1])
        rows.append({"entity_type": "network", "entity_id": f"NET-{n}", "period": inner["period"].iloc[0],
                     "metric": "network_size", "value": len(members), "threshold": size,
                     "explanation": f"กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern: "
                     f"สมาชิก {len(members)} บัญชี (mule {k['mule']}, collector {k['collector']}, feeder "
                     f"{k['feeder']}) ธุรกรรมภายในกลุ่ม {len(inner)} รายการ รวม {inner['amount'].sum():,.2f} "
                     f"ระหว่าง {d0} ถึง {d1} — collector/feeder เป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป "
                     f"(MULE.NETWORK.MIN_SIZE ≥ {size} บัญชี ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร) "
                     f"— ควรตรวจสอบเพิ่มเติม", "record_refs": list(inner["tx_id"])})
    tables.setdefault("_out", {})["mule_networks"] = pd.DataFrame(nets, columns=[
        "network_id", "member_accts", "roles", "internal_tx_count", "internal_amount",
        "period_start", "period_end"])
    return evidence_rows("MULE-NETWORK", "1.0", "5.9 Network", "R3", "MULE.NETWORK.MIN_SIZE",
                         pd.DataFrame(rows), cfg)


# ---- CPTY-PROFILE ----
def cpty_profile(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    need, lim = cfg["BEH.BASELINE.MIN_PERIODS"]["spike_months"], cfg["CPTY.NEW_RATIO"]
    t["new"] = t["period"] == t.groupby(["from_acct", "to_acct"])["period"].transform("min")
    pair = (t.groupby(["from_acct", "period", "to_acct"])
            .agg(amt=("amount", "sum"), new=("new", "first"), refs=("tx_id", list)).reset_index())
    m = (pair.groupby(["from_acct", "period"])
         .agg(n=("to_acct", "size"), n_new=("new", "sum"), amt=("amt", "sum"), top=("amt", "max"))
         .reset_index())
    m["prior"] = m.groupby("from_acct").cumcount()  # earlier active months of this account
    m["ratio"] = m["n_new"] / m["n"]
    hit = m[(m["prior"] >= need) & (m["ratio"] >= lim)]
    refs = pair[pair["new"]].groupby(["from_acct", "period"])["refs"].agg(lambda s: [x for r in s for x in r])
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "new_counterparty_ratio", "value": hit["ratio"].round(4), "threshold": lim,
        "explanation": [
            f"เดือน {p} โอนให้คู่ค้า {n} ราย เป็นคู่ค้าใหม่ {k} ราย ({r:.0%}) และคู่ค้าสูงสุดได้รับ "
            f"{top / amt:.0%} ของยอดโอนเดือนนั้น (บัญชีมีประวัติ {pr} เดือนก่อนหน้า; CPTY.NEW_RATIO "
            f"≥ {lim:.0%} และ BEH.BASELINE.MIN_PERIODS ≥ {need} เดือน ค่ามาตรฐานจาก AIDA-14 "
            f"ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for p, n, k, r, top, amt, pr in zip(hit["period"], hit["n"], hit["n_new"], hit["ratio"],
                                               hit["top"], hit["amt"], hit["prior"])],
        "record_refs": [refs[(a, p)] for a, p in zip(hit["from_acct"], hit["period"])]})
    return evidence_rows("CPTY-PROFILE", "1.0", "5.3 Behavioral", "R4", "CPTY.NEW_RATIO",
                         found, cfg)


# ---- CPTY-NEW-LARGE ----
def cpty_new_large(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"])
    k = cfg["CPTY.NEW_LARGE.MULTIPLIER"]
    t["med"] = t.groupby("from_acct")["amount"].transform("median")
    t["first_month"] = t.groupby("from_acct")["period"].transform("min")
    first = t.drop_duplicates(["from_acct", "to_acct"])  # time-sorted: first transfer per pair
    hit = first[(first["period"] > first["first_month"]) & (first["amount"] >= k * first["med"])]
    found = pd.DataFrame({
        "entity_id": hit["from_acct"], "period": hit["period"],
        "metric": "new_counterparty_amount_x_median", "value": (hit["amount"] / hit["med"]).round(2),
        "threshold": k,
        "explanation": [
            f"รายการ {i} เป็นการโอนครั้งแรกให้คู่ค้าใหม่ {to} ยอด {a:,.2f} = {a / md:.1f} เท่าของ "
            f"median ยอดโอนของบัญชี ({md:,.2f}; CPTY.NEW_LARGE.MULTIPLIER ≥ {k} เท่า ค่ามาตรฐานจาก "
            f"AIDA-14 ปรับได้ตามบริบทองค์กร) — ควรตรวจสอบเพิ่มเติม"
            for i, to, a, md in zip(hit["tx_id"], hit["to_acct"], hit["amount"], hit["med"])],
        "record_refs": [[i] for i in hit["tx_id"]]})
    return evidence_rows("CPTY-NEW-LARGE", "1.0", "5.3 Behavioral", "R4",
                         "CPTY.NEW_LARGE.MULTIPLIER", one_per_month(found), cfg)


# ---- FLOW-TRACE ----
TRAIL_COLUMNS = ["trace_id", "start_acct", "direction", "hop", "from_acct", "to_acct", "amount",
                 "ts", "tx_id"]
def flow_trace(tables: dict, cfg: dict, start_acct: str, direction: str,
               period: str = None) -> pd.DataFrame:
    if direction not in ("forward", "backward"):
        raise ValueError(f'direction ต้องเป็น "forward" หรือ "backward" เท่านั้น (ได้รับ {direction!r})')
    t = clean_tx(tables["transactions"]).reset_index(drop=True)
    fwd, cap = direction == "forward", cfg["FLOW.MAX_TRAIL_ROWS"]
    ts, per = t["ts"].to_numpy(), t["period"].to_numpy()
    other = t["to_acct" if fwd else "from_acct"].to_numpy()
    by = t.groupby("from_acct" if fwd else "to_acct").indices  # account -> positions, time-sorted
    win = pd.Timedelta(days=cfg["FLOW.WINDOW_DAYS"]).to_timedelta64()
    seen, pos, hops, cut = np.zeros(len(t), dtype=bool), [], [], False
    frontier = [(start_acct, None, None)]
    for hop in range(1, cfg["FLOW.MAX_HOPS"] + 1):
        later = []
        for acct, last, first in frontier:
            idx = by.get(acct, np.empty(0, dtype=int))
            if last is None:
                idx = idx if period is None else idx[per[idx] == period]
            else:  # keep time order, within FLOW.WINDOW_DAYS of the first hop
                lo, hi = (last, first + win) if fwd else (first - win, last)
                idx = idx[np.searchsorted(ts[idx], lo, "left"):np.searchsorted(ts[idx], hi, "right")]
            idx = idx[~seen[idx]]
            cut = cut or len(idx) > cap - len(pos)
            idx = idx[:cap - len(pos)]
            seen[idx] = True  # each transfer is followed once
            pos += list(idx)
            hops += [hop] * len(idx)
            later += [(o, s, s if first is None else first) for o, s in zip(other[idx], ts[idx])]
        frontier = [] if cut else later
    trail = t.iloc[pos][["from_acct", "to_acct", "amount", "ts", "tx_id"]].reset_index(drop=True)
    trail = trail.assign(hop=hops, trace_id=f"TRACE-{cfg['_RUN']['run_id']}-{start_acct}-{direction}",
                         start_acct=start_acct, direction=direction)[TRAIL_COLUMNS]
    trail.attrs["truncated"] = cut
    trail.attrs["note"] = (f"ไล่เส้นทางถึงขีดจำกัด FLOW.MAX_TRAIL_ROWS ({cap:,} แถว) แล้วหยุด "
                           f"— เส้นทางเงินอาจไม่ครบ ควรระบุเดือนหรือบัญชีให้แคบลง") if cut else ""
    return trail


# ---- FLOW-LAYERING ----
def flow_layering(tables: dict, cfg: dict) -> pd.DataFrame:
    t = clean_tx(tables["transactions"]).reset_index(drop=True)
    r, w = cfg["FLOW.MIN_PASS_RATIO"], cfg["FLOW.WINDOW_DAYS"]
    day = ((t["ts"] - t["ts"].min()) / pd.Timedelta(days=1)).to_numpy()
    amt, src, dst, per, txid = (t[c].to_numpy() for c in ("amount", "from_acct", "to_acct", "period", "tx_id"))
    ins = {a: g.index.to_numpy() for a, g in t.groupby("to_acct")}
    outs = {a: g.index.to_numpy() for a, g in t.groupby("from_acct")}
    best = {}  # (account, month) -> first path (e1, m, e3) found
    for m in range(len(t)):  # m = middle hop of a 3-hop path e1 -> m -> e3
        p, s = ins.get(src[m]), outs.get(dst[m])
        if p is None or s is None:
            continue
        p = p[(day[p] <= day[m]) & (day[p] >= day[m] - w) & (amt[m] >= r * amt[p]) & (amt[m] <= amt[p])
              & (src[p] != dst[m])]  # each hop forwards >= MIN_PASS_RATIO and <= 100 % of what it got
        s = s[(day[s] >= day[m]) & (day[s] <= day[m] + w) & (amt[s] >= r * amt[m]) & (amt[s] <= amt[m])
              & (dst[s] != src[m])]
        if len(p) == 0 or len(s) == 0:
            continue
        ok = (day[s][None, :] <= day[p][:, None] + w) & (dst[s][None, :] != src[p][:, None])
        paths = [(p[i], m, s[ok[i].argmax()]) for i in np.flatnonzero(ok.any(axis=1))]
        paths += [(p[ok[:, j].argmax()], m, s[j]) for j in np.flatnonzero(ok.any(axis=0))]
        for e1, e2, e3 in paths:
            for a in (src[e1], src[e2], dst[e2], dst[e3]):
                best.setdefault((a, per[e1]), (e1, e2, e3))
    found = pd.DataFrame([{
        "entity_id": a, "period": p0, "metric": "min_pass_ratio",
        "value": round(min(amt[e2] / amt[e1], amt[e3] / amt[e2]), 4), "threshold": r,
        "explanation": f"บัญชีอยู่บนเส้นทางเงิน {src[e1]} → {src[e2]} → {dst[e2]} → {dst[e3]} (3 ทอด "
        f"ภายใน {w} วัน แต่ละทอดส่งต่อ {amt[e2] / amt[e1]:.0%} และ {amt[e3] / amt[e2]:.0%} ของยอดที่รับ "
        f"คือส่งต่ออย่างน้อย {r:.0%} และไม่เกินยอดที่รับ; "
        f"FLOW.MIN_PASS_RATIO ≥ {r:.0%} และ FLOW.WINDOW_DAYS ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร; "
        f"แสดงเส้นทางแรกที่พบ) — ควรตรวจสอบเพิ่มเติม", "record_refs": [txid[e1], txid[e2], txid[e3]]}
        for (a, p0), (e1, e2, e3) in best.items()])
    return evidence_rows("FLOW-LAYERING", "1.0", "5.9 Network", "R1", "FLOW.MIN_PASS_RATIO", found, cfg)


# ---- Dashboard template (identical to the ```html block of AIDA-16) ----
DASHBOARD_TEMPLATE = r"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIDA Dashboard</title>
<style>
:root{--bg:#f5f6f8;--card:#fff;--ink:#1f2933;--mute:#5b6676;--line:#d8dde4;--head:#eef1f5;--accent:#1d5c96;--warn:#7a4100;--warnbg:#fff3dc}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Sarabun","Noto Sans Thai","Leelawadee UI",Tahoma,"Loma",sans-serif}
.banner{background:var(--warnbg);color:var(--warn);border-bottom:2px solid #e9a94b;padding:10px 16px;font-weight:600}
header{padding:12px 16px 4px}h1{font-size:18px;margin:0}h3{font-size:15px;margin:18px 0 8px}
nav{display:flex;flex-wrap:wrap;gap:2px;padding:0 16px;border-bottom:1px solid var(--line)}
nav button{border:0;background:none;padding:10px 14px;font:inherit;color:var(--mute);cursor:pointer;border-bottom:3px solid transparent}
nav button.on{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
main{padding:16px;max-width:1280px}section{display:none}section.on{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.card b{display:block;font-size:24px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card);font-size:13px}
th,td{border:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top}th{background:var(--head)}
td{max-width:520px;overflow-wrap:break-word}
.badge{display:inline-block;background:var(--warnbg);color:var(--warn);border:1px solid #e9a94b;border-radius:10px;padding:0 8px;font-size:12px;font-weight:600;white-space:nowrap}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--head);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:12px;margin:4px 0}
.xp{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin-bottom:10px}.xp h4{margin:0 0 4px;font-size:14px}tr.click{cursor:pointer}tr.click:hover{background:#eaf3ff}
.note{color:var(--mute);font-size:13px}.warn{color:var(--warn);background:var(--warnbg);padding:6px 10px;border-radius:6px}
select,.pager button{font:inherit;margin:4px 6px 8px 0}.refs{font-family:monospace;font-size:12px;overflow-wrap:anywhere}
.legend span{display:inline-flex;align-items:center;margin:0 14px 6px 0}.dot{width:12px;height:12px;border-radius:50%;margin-right:5px}
svg{background:var(--card);border:1px solid var(--line);border-radius:8px}svg circle{cursor:pointer;stroke:#fff;stroke-width:2}
.flow{display:flex;gap:12px;overflow-x:auto;align-items:flex-start}.hop{min-width:230px;flex:0 0 230px}
.tx{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:6px;padding:6px 8px;margin-bottom:6px;font-size:12px}
</style>
</head>
<body>
<div class="banner" role="note">ไฟล์นี้มีข้อมูลส่วนบุคคล/ข้อมูลบัญชีและธุรกรรมแบบเต็ม — จำกัดการเข้าถึงตามนโยบายองค์กร ผลลัพธ์เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป</div>
<header><h1>AIDA · Potential Unusual Transactions across Mule Accounts</h1><div class="note" id="meta"></div></header>
<nav id="tabs"><button data-tab="sum" class="on">สรุป</button><button data-tab="fnd">Findings</button><button data-tab="net">Mule Networks</button><button data-tab="flow">Money Flow</button><button data-tab="log">Run Log</button></nav>
<main>
<section id="sum" class="on"></section>
<section id="fnd"><label>Priority <select id="fP"></select></label> <label>ความเสี่ยง <select id="fR"></select></label><div id="fT"></div><div id="fD"></div></section>
<section id="net"><div class="legend" id="legend"></div><div id="netV"></div><div id="netD"></div></section>
<section id="flow"><label id="tL">เลือก trace <select id="tS"></select></label><div id="tN"></div><div class="flow" id="tV"></div></section>
<section id="log"></section>
</main>
<script id="aida-data" type="application/json">/*__AIDA_DATA__*/</script>
<script>
"use strict";
const D = JSON.parse(document.getElementById("aida-data").textContent);
const PAGE = 50, HOP_CAP = 200, NET_DRAW_MAX = 40; // rows per page / transfers per hop column / members drawn as a circle
const LABEL = {finding_id: "รหัส Finding", entity_type: "ประเภท", entity_id: "บัญชี / เครือข่าย", risk: "ความเสี่ยง", period: "เดือน",
  exposure: "ยอดเงินที่เกี่ยวข้อง (Exposure)", confidence: "ความมั่นใจ (Confidence)", materiality: "สาระสำคัญ (Materiality)",
  priority: "ลำดับความสำคัญ (Priority)", network_id: "เครือข่าย", review_reason: "เหตุผลที่ต้องทบทวน", evidence_id: "รหัส Evidence",
  recipe_id: "การ์ดวิเคราะห์", skill_family: "กลุ่มวิธีวิเคราะห์", metric: "ตัวชี้วัด", value: "ค่าที่พบ", threshold: "เกณฑ์",
  explanation: "คำอธิบาย", record_refs: "รายการอ้างอิง (tx_id)", decision: "รัน / ข้าม (Run / Skip)", reason: "เหตุผล",
  missing: "ข้อมูลที่ขาด", item: "รายการ", detail: "รายละเอียด", name: "ชื่อความเสี่ยง", findings: "จำนวน Finding",
  run_id: "รหัสการรัน", timestamp: "เวลา", stage: "ขั้นตอน", status: "สถานะ", recipe_version: "เวอร์ชันการ์ด",
  registry_version: "เวอร์ชัน Registry", pack_version: "เวอร์ชัน Pack", input_sha256: "ค่า hash ของไฟล์ (sha256)",
  account: "บัญชี", role: "บทบาทในเครือข่าย", finding_ids: "Finding ที่เกี่ยวข้อง", source_label: "ที่มา", section: "หัวข้อ",
  table: "ตาราง", column: "คอลัมน์", meaning: "ความหมาย", code_values: "ความหมายของค่ารหัส", confirmed_by: "ผู้ยืนยัน",
  confirmed_at: "วันที่ยืนยัน", no: "ลำดับ", risk_id: "ความเสี่ยง", request: "ข้อมูลที่ควรขอเพิ่ม"};
const RISK = {R1: "การเคลื่อนย้ายเงินผิดปกติ", R2: "รูปแบบบัญชีรับ-ส่งต่อเงิน (สอดคล้องกับ Mule Account pattern)",
  R3: "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกัน (Mule network)", R4: "ความผิดปกติของคู่ค้า (Counterparty)"};
const ROLE = {mule: ["mule — สอดคล้องกับ Mule Account pattern", "#c2410c"],
  collector: ["collector — รับเงินจากหลายบัญชีในกลุ่ม", "#6d28d9"],
  feeder: ["feeder — ส่งเงินให้หลายบัญชีในกลุ่ม", "#0f766e"], other: ["บทบาทอื่น", "#64748b"]};
Object.assign(RISK, D.risk_names || {});
const IS_E = !("data_type" in D) || D.data_type === "E"; // Mule Networks / Money Flow only for data type E (or older bundles)
const $ = id => document.getElementById(id);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmt = v => typeof v === "number" ? v.toLocaleString("th-TH", {maximumFractionDigits: 2})
  : Array.isArray(v) ? v.join(", ") : v && typeof v === "object" ? Object.entries(v).map(([k, x]) => k + ": " + x).join(", ")
  : typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v) ? v.replace("T", " ").slice(0, 19) : v;
const roleOf = r => String(r || "other").split("/")[0];
const opts = a => a.map(o => "<option>" + esc(o) + "</option>").join("");

function tbl(el, rows, cols, click, page) {
  page = page || 0;
  const n = Math.max(1, Math.ceil(rows.length / PAGE));
  let h = '<div class="wrap"><table><tr>' + cols.map(c => '<th title="' + esc(c) + '">' + esc(LABEL[c] || c) + "</th>").join("") + "</tr>";
  rows.slice(page * PAGE, (page + 1) * PAGE).forEach((r, i) => {
    h += "<tr" + (click ? ' class="click" data-i="' + (page * PAGE + i) + '"' : "") + ">" +
      cols.map(c => "<td>" + (c === "source_label" && r[c] ? '<span class="badge">' + esc(r[c]) + "</span>" : esc(fmt(r[c]))) + "</td>").join("") + "</tr>";
  });
  if (!rows.length) h += '<tr><td colspan="' + cols.length + '" class="note">ไม่มีรายการ</td></tr>';
  h += "</table></div>";
  if (n > 1) h += '<div class="pager note">หน้า ' + (page + 1) + " / " + n + " (" + rows.length + ' แถว) <button data-p="' +
    (page - 1) + '"' + (page ? "" : " disabled") + '>ก่อนหน้า</button><button data-p="' + (page + 1) + '"' +
    (page < n - 1 ? "" : " disabled") + ">ถัดไป</button></div>";
  el.innerHTML = h;
  el.querySelectorAll("[data-p]").forEach(b => b.onclick = () => tbl(el, rows, cols, click, +b.dataset.p));
  if (click) el.querySelectorAll("tr[data-i]").forEach(tr => tr.onclick = () => click(rows[+tr.dataset.i]));
}
function count(rows, k) { const m = {}; rows.forEach(r => { m[r[k]] = (m[r[k]] || 0) + 1; }); return m; }
function showTab(t) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("on", b.dataset.tab === t));
  document.querySelectorAll("main section").forEach(s => s.classList.toggle("on", s.id === t));
}

function summary() {
  const F = D.findings, P = count(F, "priority"), Rk = count(F, "risk"), pl = count(D.plan, "decision");
  const card = (t, v) => '<div class="card">' + esc(t) + "<b>" + esc(v) + "</b></div>";
  let h = '<div class="cards">' + card("Finding ทั้งหมด", F.length) +
    ["สูง", "กลาง", "ต่ำ"].map(p => card("Priority " + p, P[p] || 0)).join("") +
    (IS_E ? card("เครือข่าย (Mule network)", D.mule_networks.length) : "") + card("การ์ดที่รัน / Skip", (pl.Run || 0) + " / " + (pl.Skip || 0)) + "</div>";
  h += "<h3>Finding ตามความเสี่ยง</h3><div id='sR'></div>";
  h += '<p class="note">ทุก Finding มีสถานะ "รอ Human Review" — Priority มาจาก Confidence (จำนวนกลุ่มวิธีวิเคราะห์ที่ให้สัญญาณตรงกัน' +
    " และความครบของแหล่งข้อมูล) ร่วมกับ Materiality (ยอดเงินที่เกี่ยวข้องเทียบกับฐานที่ผู้ใช้ยืนยัน) ตาม AIDA-14</p>";
  h += (D.limits ? '<p class="warn">' + esc(D.limits) + "</p>" : "") + (D.card_notes || []).concat(D.flow_notes).map(n => '<p class="warn">' + esc(n) + "</p>").join("");
  h += "<h3>Analysis Plan (Run / Skip พร้อมเหตุผล)</h3><div id='sP'></div><h3>Materiality</h3><div id='sM'></div>";
  $("sum").innerHTML = h;
  tbl($("sR"), (D.risk_names ? Object.keys(Rk).sort() : Object.keys(RISK)).map(r => ({risk: r, name: RISK[r], findings: Rk[r] || 0})), ["risk", "name", "findings"]);
  tbl($("sP"), D.plan, ["recipe_id", "decision", "reason", "missing"]);
  tbl($("sM"), D.materiality, ["item", "value", "detail"]);
}

function findings() {
  const all = k => ["ทั้งหมด"].concat([...new Set(D.findings.map(f => f[k]))].sort());
  $("fP").innerHTML = opts(all("priority")); $("fR").innerHTML = opts(all("risk"));
  const go = () => {
    const p = $("fP").value, r = $("fR").value;
    const rows = D.findings.filter(f => (p === "ทั้งหมด" || f.priority === p) && (r === "ทั้งหมด" || f.risk === r));
    tbl($("fT"), rows, ["finding_id", "entity_type", "entity_id", "risk", "period", "exposure", "confidence", "materiality", "priority", "network_id", "review_reason"]
      .concat(D.findings.some(f => f.source_label) ? ["source_label"] : []), showFinding);
    $("fD").innerHTML = '<p class="note">คลิกแถวเพื่อดู Evidence และ record_refs</p>';
  };
  $("fP").onchange = go; $("fR").onchange = go; go();
}
function showFinding(f) {
  showTab("fnd");
  const ids = new Set(f.evidence_ids || []), ev = D.evidence.filter(e => ids.has(e.evidence_id));
  $("fD").innerHTML = "<h3>" + esc(f.finding_id) + " · " + esc(f.entity_id) + " · " + esc(RISK[f.risk] || f.risk) + "</h3><p>" +
    esc(f.review_status) + " — " + esc(f.review_reason) + (f.source_label ? ' <span class="badge">' + esc(f.source_label) + "</span> ยังไม่ผ่านการรับรอง" : "") +
    "</p><div id='fE'></div><h3>record_refs (tx_id) " +
    (f.record_refs || []).length + " รายการ</h3><div class='refs'>" + esc((f.record_refs || []).join(", ")) + "</div>";
  tbl($("fE"), ev, ["evidence_id", "recipe_id", "skill_family", "period", "metric", "value", "threshold", "explanation", "record_refs"]);
  $("fD").scrollIntoView({block: "nearest"});
}

function networks() {
  $("legend").innerHTML = Object.values(ROLE).map(([t, c]) => '<span><i class="dot" style="background:' + c + '"></i>' + esc(t) + "</span>").join("") +
    '<span class="note">บทบาทเป็นข้อสังเกตจากธุรกรรม ไม่ใช่ข้อสรุป · คลิก node เพื่อดู Finding</span>';
  $("netV").innerHTML = D.mule_networks.length ? D.mule_networks.map((n, k) => "<h3>" + esc(n.network_id) + " · สมาชิก " + n.member_accts.length +
    " บัญชี · ธุรกรรมภายใน " + esc(fmt(n.internal_tx_count)) + " รายการ รวม " + esc(fmt(n.internal_amount)) + " · " +
    esc(n.period_start) + " ถึง " + esc(n.period_end) + "</h3>" + (n.member_accts.length > NET_DRAW_MAX ? '<p class="warn">สมาชิก ' +
    n.member_accts.length + " บัญชี มากกว่า " + NET_DRAW_MAX + " บัญชี จึงแสดงเป็นตารางแทนภาพ — ดูความเชื่อมโยงทั้งหมดใน nodes.csv / edges.csv" +
    ' (นำเข้าเครื่องมือ graph ได้)</p><div class="members" id="nm' + k + '"></div>' : netSvg(n, k))).join("") : '<p class="note">ไม่พบเครือข่าย</p>';
  D.mule_networks.forEach((n, k) => { if (n.member_accts.length > NET_DRAW_MAX) tbl($("nm" + k), n.member_accts.map(a => ({account: a,
    role: n.roles[a] || "other", finding_ids: findingsOf(a).map(f => f.finding_id)})), ["account", "role", "finding_ids"], r => showNode(n, r.account)); });
  document.querySelectorAll("circle[data-k]").forEach(c => c.onclick = () => {
    const n = D.mule_networks[+c.dataset.k]; showNode(n, n.member_accts[+c.dataset.m]);
  });
}
function netSvg(n, k) {
  const M = n.member_accts, W = 560, H = 400, R = Math.min(W, H) / 2 - 60, r = 16, pos = {}, pairs = {};
  M.forEach((a, i) => { const t = 2 * Math.PI * i / M.length - Math.PI / 2; pos[a] = [W / 2 + R * Math.cos(t), H / 2 + R * Math.sin(t)]; });
  D.edges.filter(e => e.network_id === n.network_id).forEach(e => { const key = JSON.stringify([e.source, e.target]); pairs[key] = (pairs[key] || 0) + e.amount; });
  let s = '<svg viewBox="0 0 ' + W + " " + H + '" width="100%" style="max-width:' + W + 'px" role="img" aria-label="' + esc(n.network_id) +
    '"><defs><marker id="ar' + k + '" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L8,4L0,8z" fill="#94a3b8"/></marker></defs>';
  Object.keys(pairs).forEach(key => {
    const [a, b] = JSON.parse(key); if (!pos[a] || !pos[b]) return;
    const [x1, y1] = pos[a], [x2, y2] = pos[b], d = Math.hypot(x2 - x1, y2 - y1) || 1;
    s += '<line x1="' + (x1 + (x2 - x1) * r / d) + '" y1="' + (y1 + (y2 - y1) * r / d) + '" x2="' + (x2 - (x2 - x1) * (r + 3) / d) + '" y2="' +
      (y2 - (y2 - y1) * (r + 3) / d) + '" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#ar' + k + ')"><title>' +
      esc(a + " → " + b + " รวม " + fmt(pairs[key])) + "</title></line>";
  });
  M.forEach((a, i) => {
    const [x, y] = pos[a], role = n.roles[a] || "other";
    s += '<circle data-k="' + k + '" data-m="' + i + '" cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + (ROLE[roleOf(role)] || ROLE.other)[1] +
      '"><title>' + esc(a + " · " + role) + '</title></circle><text x="' + x + '" y="' + (y + r + 14) + '" text-anchor="middle" font-size="12">' + esc(a) + "</text>";
  });
  return s + "</svg>";
}
const findingsOf = a => D.findings.filter(f => f.entity_id === a || (f.entity_type === "network" && (f.member_accts || []).includes(a)));
function showNode(n, a) {
  const F = findingsOf(a);
  const role = n.roles[a] || "other";
  $("netD").innerHTML = "<h3>บัญชี " + esc(a) + " · " + esc(n.network_id) + " · บทบาท " + esc(role) + " (" +
    esc((ROLE[roleOf(role)] || ROLE.other)[0]) + ")</h3><p class='note'>คลิก Finding เพื่อดู Evidence</p><div id='nF'></div>";
  tbl($("nF"), F, ["finding_id", "entity_id", "risk", "period", "exposure", "priority", "review_reason"], showFinding);
}

function flows() {
  const ids = [...new Set(D.flows.map(r => r.trace_id))];
  if (!ids.length) { $("tL").style.display = "none"; $("tV").innerHTML = '<p class="note">ไม่มีการไล่เส้นทางเงินในรอบนี้</p>'; return; }
  $("tS").innerHTML = opts(ids);
  const go = () => {
    const id = $("tS").value, rows = D.flows.filter(r => r.trace_id === id), f = rows[0];
    const hops = [...new Set(rows.map(r => r.hop))].sort((a, b) => a - b);
    $("tN").innerHTML = '<p class="note">' + (f.direction === "forward" ? "ไปข้างหน้า: เงินจากบัญชี " + esc(f.start_acct) + " ไปที่ใด"
      : "ย้อนกลับ: เงินที่เข้าบัญชี " + esc(f.start_acct) + " มาจากที่ใด") + " · ทอดที่ 1 อยู่ซ้ายสุด · เส้นทางเงินเป็นข้อมูลประกอบการสอบสวน ไม่ใช่ข้อสรุป</p>" +
      D.flow_notes.filter(n => n.indexOf(id + ":") === 0).map(n => '<p class="warn">' + esc(n) + "</p>").join("");
    $("tV").innerHTML = hops.map(h => {
      const hr = rows.filter(r => r.hop === h);
      return '<div class="hop"><h3>ทอดที่ ' + esc(h) + " (" + hr.length + " รายการ)</h3>" + hr.slice(0, HOP_CAP).map(r => '<div class="tx"><b>' +
        esc(r.from_acct) + " → " + esc(r.to_acct) + "</b><br>" + esc(fmt(r.amount)) + " · " + esc(fmt(r.ts)) + "<br>tx_id " + esc(r.tx_id) + "</div>").join("") +
        (hr.length > HOP_CAP ? '<p class="note">แสดง ' + HOP_CAP + " รายการแรกจาก " + hr.length + " — ดูทั้งหมดใน flows.csv หรือ sheet Money_Flow</p>" : "") + "</div>";
    }).join("");
  };
  $("tS").onchange = go; go();
}

function intake() {
  const I = D.intake;
  let h = '<p class="note">สรุปสิ่งที่ผู้ตรวจสอบยืนยันก่อนวิเคราะห์ (Intake) — ตัวเลขและข้อความมาจาก engine</p>' +
    "<h3>Intake Review</h3><div id='iR'></div><h3>Data Dictionary</h3><div id='iD'></div><h3>Data Request</h3><div id='iQ'></div>" +
    '<h3>โหมดสำรวจ <span class="badge">จากโหมดสำรวจ</span> ยังไม่ผ่านการรับรอง</h3>';
  const X = D.exploratory || [];
  h += X.length ? X.map(x => '<div class="xp"><h4>' + esc(x.explore_id) + " · " + esc(x.question) + (x.promoted === "ใช่" ? " · เลื่อนเป็น Finding โดย " +
    esc(x.promoted_by) + " (" + esc(x.promoted_finding) + ")" : "") + "</h4><pre>" + esc(x.code) + '</pre><p class="note">ผล: ' + esc(x.result_summary) +
    "</p>" + (x.note ? '<p class="note">หมายเหตุ: ' + esc(x.note) + "</p>" : "") + (x.promote_reason ? '<p class="note">เหตุผลที่เลื่อน: ' + esc(x.promote_reason) +
    "</p>" : "") + '<p class="note">เวลา ' + esc(x.time) + "</p></div>").join("") : '<p class="note">ไม่มีการวิเคราะห์ในโหมดสำรวจ</p>';
  $("intake").innerHTML = h;
  tbl($("iR"), I.review, ["section", "item", "detail"]);
  tbl($("iD"), I.dictionary, ["table", "column", "meaning", "role", "code_values", "confirmed_by", "confirmed_at"]);
  tbl($("iQ"), I.requests, ["no", "risk_id", "request"]);
}
if (D.intake) {
  const b = document.createElement("button"), s = document.createElement("section");
  b.dataset.tab = "intake"; b.textContent = "Intake"; s.id = "intake";
  document.querySelector('nav button[data-tab="sum"]').after(b); $("sum").after(s);
}
if (!IS_E) {
  document.querySelectorAll('nav button[data-tab="net"], nav button[data-tab="flow"], #net, #flow').forEach(e => e.remove());
  document.querySelector("h1").textContent = "AIDA · ข้อสังเกตที่ควรตรวจสอบเพิ่มเติมจากข้อมูลรายการ";
}
$("meta").textContent = "run_id " + D.run_id + " · Registry v" + D.registry_version + " · รูปแบบวันที่ที่ใช้แปลง " + ((D.prep || {}).date_format || "-");
document.querySelectorAll("nav button").forEach(b => b.onclick = () => showTab(b.dataset.tab));
if (D.intake) intake();
summary(); findings();
if (IS_E) { networks(); flows(); }
tbl($("log"), D.run_log, ["run_id", "timestamp", "stage", "status", "detail", "recipe_id", "recipe_version", "registry_version", "pack_version", "input_sha256"]);
</script>
</body>
</html>
<!-- END-OF-TEMPLATE -->
"""


# ---- role adapter (spec 4.1) ----
ACCOUNT_ID_ROLE = "entity"  # in a master (non-transaction) table, the entity column is the account id
TX_ROLES = ("record_id", "date", "amount")


def _check_role(role):
    if role not in ROLE_TO_INTERNAL and not (role.startswith("custom:") and len(role) > 7):
        raise ValueError(f"ไม่รู้จักบทบาทคอลัมน์ '{role}' — ใช้ได้เฉพาะ {', '.join(ROLES)} หรือ custom:<ชื่อ>")


def to_internal(frames: dict, roles: dict) -> dict:
    """Rename user columns to the internal columns the cards read.

    `roles` maps table name -> {user column: role}. Unmapped columns are dropped.
    * The transactions table is the one whose roles include record_id, date or amount (the table
      with the most of them wins); columns are renamed through ROLE_TO_INTERNAL and `custom:x`
      columns keep their name. It is returned as tables["transactions"].
    * Any other mapped table is the master table and is returned as tables["accounts"] with
      `acct_id` and `opened_at`. The roles give no separate account-id role, so, as prep_map
      does for accounts.csv (acct_id, opened_at), its account id is the column mapped as
      `entity` (-> acct_id); `opened_at` -> opened_at; custom:x columns are kept. A master table
      mapped without `entity` is rejected, because accounts cannot be joined without an id.
    Raises ValueError with a Thai message saying how to fix the mapping.
    """
    tx_name, best = None, 0
    for name, rmap in roles.items():
        score = sum(1 for r in rmap.values() if r in TX_ROLES)
        if score > best:
            tx_name, best = name, score
    if tx_name is None:
        raise ValueError("ไม่พบตารางธุรกรรม — ต้องกำหนดบทบาท record_id, date และ amount ให้คอลัมน์ในตารางธุรกรรม")
    out = {}
    for name, rmap in roles.items():
        if name not in frames:
            raise ValueError(f"ไม่พบตาราง '{name}' ในไฟล์ที่ส่งเข้ามา — ตรวจชื่อตารางหรือชื่อชีตอีกครั้ง")
        df, ren, seen = frames[name], {}, {}
        is_tx = name == tx_name
        for col, role in rmap.items():
            _check_role(role)
            if col not in df.columns:
                raise ValueError(f"ไม่พบคอลัมน์ '{col}' ในตาราง '{name}' — ตรวจชื่อคอลัมน์ให้ตรงกับไฟล์")
            if is_tx:
                target = ROLE_TO_INTERNAL.get(role, role)
            elif role == ACCOUNT_ID_ROLE:
                target = "acct_id"
            elif role == "opened_at" or role.startswith("custom:"):
                target = role
            else:
                continue  # role not used by the master table: dropped
            if target in seen:
                raise ValueError(f"ตาราง '{name}': คอลัมน์ '{seen[target]}' และ '{col}' ถูกกำหนดเป็นบทบาทเดียวกัน "
                                 f"({role}) — เลือกเพียงคอลัมน์เดียวต่อบทบาท")
            seen[target] = col
            ren[col] = target
        if not is_tx and "acct_id" not in ren.values():
            raise ValueError(f"ตาราง '{name}' ไม่มีคอลัมน์รหัสบัญชี — กำหนดบทบาท entity ให้คอลัมน์รหัสบัญชี")
        out["transactions" if is_tx else "accounts"] = df[list(ren)].rename(columns=ren).copy()
    return out


MACHINE_CONFIG_HEADING = "## Machine Config (สำหรับ recipe)"


def load_registry(path_or_text: str) -> dict:
    """Machine Config JSON of the AIDA-14 registry, from a file path or from the Markdown text.

    Copy of validate_pack.parse_machine_config (kept separate on purpose); problems raise
    ValueError with a Thai message instead of returning an error list.
    """
    s = str(path_or_text)
    if "\n" not in s and os.path.isfile(s):
        with open(s, encoding="utf-8") as fh:
            s = fh.read()
    lines = s.splitlines()
    stripped = [line.strip() for line in lines]
    if MACHINE_CONFIG_HEADING not in stripped:
        raise ValueError(f"ไม่พบหัวข้อ '{MACHINE_CONFIG_HEADING}' ใน AIDA-14 — ใช้ไฟล์ AIDA-14 ฉบับเต็มจาก Knowledge")
    i = stripped.index(MACHINE_CONFIG_HEADING) + 1
    while i < len(lines) and not stripped[i].startswith("```"):
        if stripped[i].startswith("#"):
            raise ValueError("ไม่พบบล็อก ```json ใต้หัวข้อ Machine Config ใน AIDA-14")
        i += 1
    j = i + 1
    while j < len(lines) and not stripped[j].startswith("```"):
        j += 1
    if i >= len(lines) or j >= len(lines):
        raise ValueError("บล็อก ```json ของ Machine Config ใน AIDA-14 ไม่ครบ (ไม่มีบรรทัดปิด)")
    try:
        config = json.loads("\n".join(lines[i + 1:j]))
    except json.JSONDecodeError as e:
        raise ValueError(f"Machine Config ใน AIDA-14 ไม่ใช่ JSON ที่ถูกต้อง ({e.msg}, บรรทัด {e.lineno})") from e
    if not isinstance(config, dict):
        raise ValueError("Machine Config ใน AIDA-14 ต้องเป็น JSON object")
    return config


# ---- column profiling, role suggestion, description checks (spec 4.1, 4.3 step 2) ----
PROFILE_COLUMNS = ["table", "column", "dtype_guess", "n_rows", "null_pct", "unique_pct", "min", "max", "top5",
                   "samples", "patterns", "relations", "join_match", "neg_count", "dup_count"]
PROFILE_SAMPLE = 5000       # values inspected for pattern detection (deterministic sample)
PROFILE_MAX_REL_COLS = 8    # columns of one kind compared pairwise / in triples
RE_THAI_CHAR = re.compile(r"[฀-๿]")
RE_PAT_ACCOUNT = r"^(?:[A-Za-z]{1,4}[-_]?\d{3,}|\d{6,12})$"
RE_PAT_CODE = r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,14}$"
UNKNOWN_ROLE = "ไม่ทราบ"

ROLE_SYNONYMS = {
    "record_id": ["id", "txid", "txnid", "trxid", "transactionid", "transactionno", "transactionnumber", "trnno",
                  "trnid", "recordid", "recordno", "paymentid", "payid", "rowid", "รหัสรายการ", "เลขที่รายการ",
                  "เลขรายการ", "รหัสธุรกรรม", "เลขที่ธุรกรรม"],
    "date": ["date", "ts", "dt", "timestamp", "datetime", "txdate", "txndate", "trandate", "trndate", "trndt",
             "transactiondate", "paydate", "paymentdate", "postingdate", "postdate", "txtime", "วันที่", "วันเวลา",
             "วันที่ทำรายการ", "วันที่รายการ", "วันที่ชำระ", "วันที่โอน", "เวลาทำรายการ"],
    "amount": ["amount", "amt", "value", "txamt", "trnamt", "txnamount", "transactionamount", "paymentamount",
               "payamount", "netamount", "netamt", "ยอดเงิน", "จำนวนเงิน", "ยอด", "ยอดสุทธิ", "ยอดชำระ", "มูลค่า",
               "ยอดโอน"],
    "entity": ["fromacct", "fromaccount", "sender", "srcacct", "sourceaccount", "accountfrom", "acctfr", "frmacc",
               "accfrom", "borrower", "borrowerid", "customer", "customerid", "vendor", "vendorid", "supplier",
               "supplierid", "payee", "acctid", "accountid", "accountno", "accountnumber", "บัญชีต้นทาง",
               "บัญชีผู้โอน", "ผู้โอน", "ผู้กู้", "ลูกค้า", "ผู้ขาย", "เลขที่บัญชี", "รหัสบัญชี", "รหัสผู้ขาย",
               "เจ้าหนี้"],
    "counterparty": ["toacct", "toaccount", "receiver", "beneficiary", "destacct", "destinationaccount",
                     "accountto", "acctto", "accto", "payer", "payerid", "payor", "counterparty", "cpty",
                     "บัญชีปลายทาง", "บัญชีผู้รับ", "ผู้รับ", "ผู้รับโอน", "ผู้ชำระ", "ผู้ชำระเงิน", "คู่รายการ",
                     "คู่ค้า"],
    "contract": ["contract", "contractid", "contractno", "loanid", "loanno", "loanaccount", "policy", "policyno",
                 "cardno", "สัญญา", "เลขที่สัญญา", "เลขสัญญา", "กรมธรรม์", "เลขที่กรมธรรม์", "บัตร"],
    "category": ["category", "categ", "txtype", "trantype", "transactiontype", "expensetype", "glcode", "หมวด",
                 "หมวดหมู่", "ประเภท", "ประเภทรายการ"],
    "channel": ["channel", "chnl", "chan", "branch", "branchcode", "branchid", "brcd", "ช่องทาง", "สาขา",
                "รหัสสาขา"],
    "created_by": ["createdby", "creator", "maker", "entryby", "preparedby", "createuser", "crtby", "inputby",
                   "ผู้บันทึก", "ผู้สร้าง", "ผู้ทำรายการ", "ผู้จัดทำ"],
    "approved_by": ["approvedby", "approver", "checker", "authorizedby", "authby", "apprby", "apvby", "ผู้อนุมัติ",
                    "ผู้อนุมัติรายการ"],
    "document_no": ["documentno", "docno", "docnumber", "invoiceno", "invoicenumber", "invoice", "invno", "refno",
                    "reference", "receiptno", "เลขที่เอกสาร", "เลขเอกสาร", "เลขที่ใบแจ้งหนี้", "ใบแจ้งหนี้",
                    "เลขที่ใบกำกับ", "เลขอ้างอิง"],
    "limit": ["limit", "creditlimit", "credlimit", "approvallimit", "installment", "instalment",
              "installmentamount", "scheduledamount", "วงเงิน", "ค่างวด", "ยอดค่างวด"],
    "due_date": ["duedate", "due", "duedt", "maturitydate", "paymentduedate", "วันครบกำหนด", "วันที่ครบกำหนด",
                 "กำหนดชำระ", "วันกำหนดชำระ"],
    "opened_at": ["openedat", "opendate", "openeddate", "opendt", "accountopendate", "วันเปิดบัญชี",
                  "วันที่เปิดบัญชี", "วันเปิด", "วันที่เปิด", "วันที่ทำสัญญา"],
}
# preset -> {column name: role}; used only to propose roles, the auditor confirms
PRESETS = {
    "E": {"tx_id": "record_id", "ts": "date", "from_acct": "entity", "to_acct": "counterparty", "amount": "amount",
          "channel": "channel", "acct_id": "entity", "opened_at": "opened_at"},
    "C": {"payment_id": "record_id", "pay_date": "date", "pay_amount": "amount", "borrower_id": "entity",
          "payer_id": "counterparty", "contract_id": "contract", "due_date": "due_date",
          "installment_amount": "limit", "channel": "channel", "category": "category", "status": "custom:status",
          "opened_at": "opened_at"},
    "A": {"payment_id": "record_id", "pay_date": "date", "amount": "amount", "vendor_id": "entity",
          "invoice_no": "document_no", "created_by": "created_by", "approved_by": "approved_by",
          "approval_limit": "limit", "category": "category", "channel": "channel", "po_no": "contract"},
}
ROLE_CONF_DEFAULT = (0.8, 0.5)
LEVEL_HIGH, LEVEL_MID, LEVEL_LOW = "สูง", "กลาง", "ต่ำ"


def _norm_name(s) -> str:
    return re.sub(r"[\s_\-./()\[\]:]+", "", str(s).strip().lower())


def _tokens(s) -> set:
    return {t for t in re.split(r"[^0-9a-zA-Zก-๙]+", str(s).lower()) if t}


_SYN_INDEX = None
def _syn_index():
    global _SYN_INDEX
    if _SYN_INDEX is None:
        _SYN_INDEX = [(_norm_name(w), role) for role, words in ROLE_SYNONYMS.items() for w in words]
    return _SYN_INDEX


def match_role(text):
    """(role, strength) for a column name or a free-text description, or (None, 0).

    strength: "exact" (whole text equals a synonym), "token" (a word equals one) or "part" (contains one,
    synonyms of 4+ ASCII or 3+ Thai characters only). The longest synonym wins.
    """
    whole, toks = _norm_name(text), {_norm_name(t) for t in _tokens(text)}
    best = (0, None, None)
    for syn, role in _syn_index():
        if not syn:
            continue
        thai = bool(RE_THAI_CHAR.search(syn))
        if whole == syn:
            cand = (len(syn) + 200, role, "exact")
        elif syn in toks:
            cand = (len(syn) + 100, role, "token")
        elif len(syn) >= (3 if thai else 4) and syn in whole:
            cand = (len(syn), role, "part")
        else:
            continue
        if cand[0] > best[0]:
            best = cand
    return (best[1], best[2]) if best[1] else (None, 0)


DESC_REL_EN = re.compile(r"\b(?:per|of|for)\b", re.I)  # "amount per invoice": the head is before "per"
DESC_REL_TH = ("สำหรับ", "ของ", "ต่อ", "ที่")  # Thai relational words; the head noun comes before them
DESC_WEAK = {"ยอด", "ยอดเงิน", "จำนวนเงิน", "มูลค่า", "amount", "amt", "value"}  # modifiers a named synonym outranks


def _desc_hits(text: str) -> list:
    """[(start, length, normalized synonym, role)] of every synonym in a description (same rules as match_role:
    ASCII synonyms need a whole word or 4+ characters, Thai ones 3+ characters)."""
    whole, toks = _norm_name(text), {_norm_name(t) for t in _tokens(text)}
    hits = []
    for syn, r in _syn_index():
        thai = bool(RE_THAI_CHAR.search(syn))
        if not syn or (syn not in toks and len(syn) < (3 if thai else 4)):
            continue
        pos = whole.find(syn)
        if pos >= 0:
            hits.append((pos, len(syn), syn, r))
    return hits


def match_description(text):
    """Role named by a free-text column description, or None.

    A description is a phrase: its head comes before a relational word (ต่อ / ของ / สำหรับ / ที่, per / of / for),
    so "จำนวนเงินที่จ่ายจริงต่อใบแจ้งหนี้" is an amount, not an invoice number. Only the head is matched (a relational
    word inside a matched synonym such as "วันที่" or "เลขที่" does not cut it). In the head a bare modifier
    (ยอด, จำนวนเงิน, amount, ...) is weaker than any other synonym ("ยอดวงเงิน" and "limit amount" are limits),
    then the longest synonym wins. A description equal to a synonym, or a head with no synonym, is matched as
    match_role does on the whole text."""
    role, strength = match_role(text)
    if strength == "exact" or role is None:
        return role
    head = DESC_REL_EN.split(str(text))[0].strip() or str(text)
    hits = _desc_hits(head)
    norm = _norm_name(head)
    spans = [(a, a + n) for a, n, _, _ in hits]
    cut = len(norm)
    for w in DESC_REL_TH:
        start = 0
        while True:
            k = norm.find(w, start)
            if k < 0:
                break
            if k > 0 and not any(a <= k < b for a, b in spans):
                cut = min(cut, k)
                break
            start = k + 1
    hits = [h for h in hits if h[0] + h[1] <= cut]
    if not hits:
        return role
    strong = [h for h in hits if h[2] not in {_norm_name(w) for w in DESC_WEAK}] or hits
    return max(strong, key=lambda h: (h[1], -h[0]))[3]


def _num_text(s: pd.Series):
    """Numeric view of a text column, or None when it is not (mostly) numbers or looks like zero-padded ids."""
    t = s.astype(str).str.strip()
    if t.str.match(r"^0\d").mean() > 0.05 or t.str.match(r"^\d{10,}$").mean() > 0.5:
        return None  # zero-padded or long all-digit values are identifiers, not amounts
    n = pd.to_numeric(t.str.replace(",", "", regex=False), errors="coerce")
    return n if n.notna().mean() >= 0.95 else None


def _valid_date_text(x) -> bool:
    p = date_parts(x)
    if not p:
        return False
    kind, a, b, y, _ = p
    if kind == "slash":
        return 1 <= a <= 31 and 1 <= b <= 31 and (a <= 12 or b <= 12)
    if kind == "iso" and not 1900 <= y <= 2700:
        return False
    return 1 <= a <= 31 and 1 <= b <= 12


def _parse_dates(s: pd.Series) -> pd.Series:
    """Datetime series from dates written dd/mm, ISO, Thai month names and/or Buddhist Era years (B1 rules)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.tz_localize(None) if getattr(s.dt, "tz", None) is not None else s
    txt = s.astype(str).str.strip()
    mp = {}
    for u in txt[s.notna()].unique():
        p = date_parts(u)
        if p is None or not _valid_date_text(u):
            continue
        kind, a, b, y, rest = p
        if kind == "slash" and b > 12 >= a:
            a, b = b, a
        try:
            mp[u] = pd.Timestamp(iso_text(a, b, y, rest))
        except (ValueError, OverflowError):
            pass
    return pd.to_datetime(txt.map(mp), errors="coerce")


def _top_value(v):
    return v.item() if hasattr(v, "item") else v


def _profile_one(table: str, col: str, s: pd.Series) -> tuple:
    """(row dict, aux dict with the typed views used for relations and join checks)."""
    n = len(s)
    nn = s.dropna()
    row = {"table": table, "column": col, "n_rows": n, "null_pct": round(100.0 * (n - len(nn)) / n, 2) if n else 0.0,
           "unique_pct": 0.0, "min": None, "max": None, "top5": [], "samples": [], "patterns": [],
           "relations": [], "join_match": None, "neg_count": 0, "dup_count": 0}
    aux = {"kind": "empty", "num": None, "dt": None, "text": None}
    if nn.empty:
        row["dtype_guess"] = "empty"
        return row, aux
    nun = int(nn.nunique())
    row["unique_pct"] = round(100.0 * nun / len(nn), 2)
    row["dup_count"] = int(len(nn) - nun)
    row["top5"] = [(str(_top_value(k)), int(v)) for k, v in nn.value_counts().head(5).items()]
    row["samples"] = [str(v) for v in nn.head(3)]
    pats = []
    is_num = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
    is_dt = pd.api.types.is_datetime64_any_dtype(s)
    sample = nn if len(nn) <= PROFILE_SAMPLE else nn.sample(PROFILE_SAMPLE, random_state=0)
    num = nn.astype("float64") if is_num else None
    txt = None
    if not is_num and not is_dt:
        txt = sample.astype(str).str.strip()
        if _num_text(nn) is not None:
            num = _num_text(nn)
    if is_dt or (txt is not None and num is None):
        if is_dt:
            share, has_time = 1.0, bool((nn.dt.normalize() != nn).any())
        else:
            valid = {u: _valid_date_text(u) for u in txt.unique()}
            share = txt.map(valid).mean()
            has_time = any(valid[u] and RE_TIME.search(date_parts(u)[4] or "") for u in valid)
        if share >= 0.8:
            pats += ["date"] + (["datetime"] if has_time else [])
            aux["dt"] = _parse_dates(s)
            d = aux["dt"].dropna()
            aux["kind"] = "date"
            if len(d):
                row["min"], row["max"] = str(d.min()), str(d.max())
    if aux["kind"] != "date" and num is not None:
        aux["kind"], aux["num"] = "number", num.reindex(s.index) if not is_num else s.astype("float64")
        v = num.dropna()
        row["min"], row["max"] = _top_value(v.min()), _top_value(v.max())
        row["neg_count"] = int((v < 0).sum())
        if row["neg_count"]:
            pats.append("negative")
        whole = bool((v == np.floor(v)).all())
        pats.append("integer" if whole else "decimal")
        if whole and is_num and (v.abs().between(1e12, 1e13 - 1)).all():
            pats.append("thai_id13")
    elif aux["kind"] != "date":
        aux["kind"], aux["text"] = "text", nn.astype(str).str.strip()
        t = aux["text"]
        row["min"], row["max"] = str(t.min()), str(t.max())
        if txt.str.match(r"^\d{13}$").mean() >= 0.9:
            pats.append("thai_id13")
        elif txt.str.match(RE_PAT_ACCOUNT).mean() >= 0.9:
            pats.append("account_like")
        elif txt.str.match(RE_PAT_CODE).mean() >= 0.9 and (nun <= 30 or nun / len(nn) <= 0.5):
            pats.append("code")
        if txt.map(lambda x: bool(RE_THAI_CHAR.search(x))).mean() >= 0.5:
            pats.append("thai_text")
    row["patterns"] = pats
    row["dtype_guess"] = {"date": "date", "number": "number", "text": "text"}[aux["kind"]]
    return row, aux


def _relations(cols: dict) -> dict:
    """{column: [relation text]} between the columns of one table. `cols`: name -> (kind, typed series)."""
    out = {c: [] for c in cols}
    nums = [c for c, (k, v) in cols.items() if k == "number" and v.nunique() > 2][:PROFILE_MAX_REL_COLS]
    dates = [c for c, (k, v) in cols.items() if k == "date"][:PROFILE_MAX_REL_COLS]
    texts = [c for c, (k, v) in cols.items() if k == "text" and v.nunique() > 1][:PROFILE_MAX_REL_COLS]
    order = list(cols)
    # C = A - B: the largest column is the total, the later of the other two is the result
    mag = {c: float(cols[c][1].abs().mean()) for c in nums}
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            for k in range(j + 1, len(nums)):
                a, c, b = sorted((nums[i], nums[j], nums[k]), key=lambda x: -mag[x])
                if order.index(c) < order.index(b):
                    b, c = c, b
                f = pd.concat([cols[a][1], cols[b][1], cols[c][1]], axis=1).dropna()
                if len(f) == 0:
                    continue
                head = f.head(2000)
                if not np.isclose(head.iloc[:, 0] - head.iloc[:, 1], head.iloc[:, 2], atol=0.01).all():
                    continue
                ok = np.isclose(f.iloc[:, 0] - f.iloc[:, 1], f.iloc[:, 2], atol=0.01).mean()
                if ok >= 0.98 and not np.isclose(f.iloc[:, 0], f.iloc[:, 2], atol=0.01).mean() > 0.9 \
                        and (f.iloc[:, 1] != 0).mean() > 0.1:
                    out[c].append(f"{c} = {a} − {b}")
    for group in (nums, dates):
        for i, x in enumerate(group):
            for y in group[i + 1:]:
                f = pd.concat([cols[x][1], cols[y][1]], axis=1).dropna()
                if len(f) == 0:
                    continue
                a, b = f.iloc[:, 0], f.iloc[:, 1]
                for lo, hi, ln, hn in ((x, y, a, b), (y, x, b, a)):
                    if (ln <= hn).mean() >= 0.999 and (ln < hn).any():
                        out[lo].append(f"{lo} ≤ {hi}")
                eq = float((a == b).mean())
                if 0.5 <= eq:
                    out[x].append(f"{x} == {y} in {eq * 100:.0f}%")
    for i, x in enumerate(texts):
        for y in texts[i + 1:]:
            f = pd.concat([cols[x][1], cols[y][1]], axis=1).dropna()
            if len(f):
                eq = float((f.iloc[:, 0] == f.iloc[:, 1]).mean())
                if eq >= 0.5:
                    out[x].append(f"{x} == {y} in {eq * 100:.0f}%")
    return out


def _norm_key(u: pd.Series) -> set:
    t = u.str.strip().str.casefold().str.lstrip("0")
    return set(t.where(t != "", "0"))


def _key_values(aux: dict):
    s = aux["text"] if aux["kind"] == "text" else aux["num"]
    s = s.dropna()
    if aux["kind"] == "number":
        if not (s == np.floor(s)).all():
            return None
        s = s.astype("int64")
    return s.astype(str).drop_duplicates()


def _join_matches(rows: list, auxs: list) -> None:
    cands = []
    for i, (r, a) in enumerate(zip(rows, auxs)):
        if a["kind"] in ("text", "number") and "date" not in r["patterns"] and "decimal" not in r["patterns"]:
            u = _key_values(a)
            if u is not None and len(u) >= 3:
                cands.append((i, u, set(u), _norm_key(u)))
    for i, u, raw, norm in cands:
        best = None
        for i2, u2, raw2, norm2 in cands:
            if rows[i2]["table"] == rows[i]["table"]:
                continue
            r_pct, n_pct = 100.0 * len(raw & raw2) / len(raw), 100.0 * len(norm & norm2) / len(norm)
            if n_pct >= 20 and (best is None or n_pct > best["normalized"]):
                best = {"with": f"{rows[i2]['table']}.{rows[i2]['column']}", "raw": round(r_pct, 1),
                        "normalized": round(n_pct, 1)}
        rows[i]["join_match"] = best


def profile_columns(frames: dict) -> pd.DataFrame:
    """One row per (table, column): type guess, null/unique %, range, top-5, samples, patterns, relations, join_match.

    Percentages are 0-100. join_match is None or {"with": "table.column", "raw": % of this column's distinct
    values found exactly in the other column, "normalized": the same after strip / case / leading-zero removal}.
    """
    rows, auxs = [], []
    for tname, df in frames.items():
        t_rows, t_cols = [], {}
        for col in df.columns:
            r, a = _profile_one(str(tname), str(col), df[col])
            t_rows.append(r)
            auxs.append(a)
            if a["kind"] in ("number", "date", "text"):
                t_cols[str(col)] = (a["kind"], a["num"] if a["kind"] == "number" else
                                    a["dt"] if a["kind"] == "date" else a["text"])
        rel = _relations(t_cols) if len(t_cols) > 1 else {}
        for r in t_rows:
            r["relations"] = rel.get(r["column"], [])
        rows += t_rows
    _join_matches(rows, auxs)
    return pd.DataFrame(rows, columns=PROFILE_COLUMNS)


def _role_thresholds(cfg) -> tuple:
    """(high, medium) from cfg["INTAKE.ROLE_CONF"]: a dict {"สูง": 0.8, "กลาง": 0.5} or the text
    "สูง ≥ 0.8 / กลาง ≥ 0.5" (as load_registry yields it); defaults when the key is absent or unreadable."""
    v = (cfg or {}).get("INTAKE.ROLE_CONF")
    hi, mid = ROLE_CONF_DEFAULT
    try:
        if isinstance(v, dict):
            hi, mid = float(v.get("สูง", v.get("high", hi))), float(v.get("กลาง", v.get("medium", mid)))
        elif isinstance(v, str):
            m1, m2 = re.search(r"สูง\D*?([0-9.]+)", v), re.search(r"กลาง\D*?([0-9.]+)", v)
            hi, mid = float(m1[1]) if m1 else hi, float(m2[1]) if m2 else mid
    except (TypeError, ValueError):
        hi, mid = ROLE_CONF_DEFAULT
    return hi, mid


def _level(conf: float, thr: tuple) -> str:
    return LEVEL_HIGH if conf >= thr[0] else LEVEL_MID if conf >= thr[1] else LEVEL_LOW


def _brief_text(brief, table, col):
    if not brief:
        return None
    return brief.get(f"{table}.{col}", brief.get(col))


def _profile_check(role, prow) -> tuple:
    """(confidence adjustment, Thai note) from whether the data looks like the proposed role."""
    pats, dtype, uniq = prow["patterns"], prow["dtype_guess"], prow["unique_pct"]
    if role in ("date", "due_date", "opened_at") and dtype != "date":
        return -0.4, "แต่ค่าในคอลัมน์ไม่ใช่รูปแบบวันที่"
    if role in ("amount", "limit") and dtype != "number":
        return -0.4, "แต่ค่าในคอลัมน์ไม่ใช่ตัวเลข"
    if role == "record_id" and uniq < 99:
        return -0.3, f"แต่ค่าซ้ำกัน (ไม่ซ้ำ {uniq:.1f}%)"
    return 0.0, ""


def suggest_roles(profile: pd.DataFrame, brief_columns=None, preset=None, cfg=None) -> pd.DataFrame:
    """Propose a role per column: auditor's description > preset > name dictionary > data pattern.

    Never guesses blindly: a cryptic name with no description and no strong pattern gets "ไม่ทราบ".
    Columns: table, column, role, confidence (0-1), level (สูง/กลาง/ต่ำ), reason (Thai), source.
    """
    thr = _role_thresholds(cfg)
    preset_map = {_norm_name(k): v for k, v in PRESETS.get(preset, {}).items()} if preset else {}
    out = []
    for _, p in profile.iterrows():
        table, col = p["table"], p["column"]
        role, conf, src, reason = UNKNOWN_ROLE, 0.0, "profile", ""
        said = _brief_text(brief_columns, table, col)
        r_b, st_b = (None, 0)
        if said is not None:
            r_b = said.strip() if str(said).strip() in ROLE_TO_INTERNAL or str(said).strip().startswith("custom:") \
                else match_description(said)
            st_b = "exact"
        if r_b:
            role, conf, src = r_b, 0.95, "brief"
            reason = f"ตามคำอธิบายของผู้ตรวจสอบ: \"{said}\""
        elif _norm_name(col) in preset_map:
            role, conf, src = preset_map[_norm_name(col)], 0.9, "preset"
            reason = f"ชื่อคอลัมน์ตรงกับรูปแบบมาตรฐานของข้อมูลประเภท {preset}"
        else:
            r_s, st = match_role(col)
            if r_s:
                role, src = r_s, "synonym"
                conf = {"exact": 0.85, "token": 0.7, "part": 0.6}[st]
                adj, note = _profile_check(role, p)
                conf = max(0.0, conf + adj)
                reason = f"ชื่อคอลัมน์ \"{col}\" สื่อถึงบทบาท {role}" + (f" {note} — ควรยืนยัน" if note else "")
            elif "thai_id13" in p["patterns"]:
                role, conf, src = "entity", 0.4, "profile"
                reason = "ค่าเป็นเลข 13 หลักรูปแบบเลขประจำตัวประชาชน จึงอาจเป็นรหัสผู้ทำรายการ — ควรยืนยัน"
            else:
                reason = (f"ชื่อคอลัมน์ \"{col}\" ไม่สื่อความหมาย และรูปแบบข้อมูลไม่ชี้บทบาทชัดเจน — "
                          "ขอให้ผู้ตรวจสอบระบุความหมาย")
                if said is not None:
                    reason = f"คำอธิบาย \"{said}\" ยังจับคู่กับบทบาทใดไม่ได้ — ขอให้ระบุเพิ่มเติม"
        out.append({"table": table, "column": col, "role": role, "confidence": round(conf, 2),
                    "level": _level(conf, thr) if role != UNKNOWN_ROLE else LEVEL_LOW, "reason": reason,
                    "source": src})
    res = pd.DataFrame(out, columns=["table", "column", "role", "confidence", "level", "reason", "source"])
    # one column per role in a table: keep the most confident guess (auditor's own choices are never touched)
    for (t, r), g in res[(res["role"] != UNKNOWN_ROLE) & (res["source"] != "brief")].groupby(["table", "role"]):
        taken = res[(res["table"] == t) & (res["role"] == r) & (res["source"] == "brief")]
        keep = None if len(taken) else g["confidence"].idxmax()
        for idx in g.index:
            if idx != keep:
                res.loc[idx, ["role", "confidence", "level", "source"]] = [UNKNOWN_ROLE, 0.0, LEVEL_LOW, "profile"]
                res.loc[idx, "reason"] = f"มีหลายคอลัมน์ที่อาจเป็นบทบาท {r} — ขอให้ผู้ตรวจสอบเลือกคอลัมน์ที่ใช้"
    return res.reset_index(drop=True)


NET_WORDS = ("สุทธิ", "net", "ไม่ติดลบ", "เป็นบวก", "positive", "nonnegative")
UNIQUE_WORDS = ("unique", "ไม่ซ้ำ", "primarykey", "เลขที่รายการ", "รหัสรายการ")


def check_descriptions(profile: pd.DataFrame, brief_columns=None) -> list:
    """Descriptions that disagree with the data: [{table, column, said, observed, question}] in Thai."""
    out = []
    if not brief_columns:
        return out
    for _, p in profile.iterrows():
        said = _brief_text(brief_columns, p["table"], p["column"])
        if said is None:
            continue
        low, n = str(said).lower(), max(int(p["n_rows"]), 1)
        role = match_description(said)
        item = lambda obs, q: out.append({"table": p["table"], "column": p["column"], "said": said,
                                          "observed": obs, "question": q})
        if any(w in low for w in NET_WORDS) and p["neg_count"] > 0:
            item(f"พบค่าติดลบ {p['neg_count']:,} แถว ({100.0 * p['neg_count'] / n:.1f}%)",
                 "ค่าติดลบเหล่านี้เป็นรายการคืนเงินหรือปรับปรุงที่ตั้งใจให้มีหรือไม่ หรือควรทบทวนคำอธิบายคอลัมน์")
        if (role == "record_id" or any(w in low for w in UNIQUE_WORDS)) and p["dup_count"] > 0:
            item(f"พบค่าซ้ำ {p['dup_count']:,} แถว (ไม่ซ้ำ {p['unique_pct']:.1f}%)",
                 "ค่าซ้ำเกิดจากการส่งออกข้อมูลซ้ำหรือเป็นหลายรายการที่ใช้รหัสเดียวกัน ช่วยยืนยันว่าควรใช้คอลัมน์ใดเป็นรหัสรายการ")
        if role in ("date", "due_date", "opened_at") and p["dtype_guess"] != "date":
            item(f"ค่าในคอลัมน์ไม่อยู่ในรูปแบบวันที่ (ตัวอย่าง: {', '.join(p['samples'])})",
                 "รูปแบบวันที่ในไฟล์เป็นอย่างไร (เช่น วัน/เดือน/ปี พ.ศ.) เพื่อให้แปลงได้ถูกต้อง")
        if role in ("amount", "limit") and p["dtype_guess"] not in ("number", "empty"):
            item(f"ค่าในคอลัมน์ไม่ใช่ตัวเลข (ตัวอย่าง: {', '.join(p['samples'])})",
                 "คอลัมน์นี้เป็นยอดเงินจริงหรือไม่ และมีสัญลักษณ์หรือข้อความปนอยู่หรือเปล่า")
    return out


def detect_dataset_type(profile: pd.DataFrame):
    """"E" (transactions between accounts), "C" (loan payments), "A" (accounts payable) or None, from the
    roles the column names point to. Contract + due date -> C; created/approved by or document no -> A;
    entity + counterparty + date + amount -> E."""
    if profile is None or len(profile) == 0:
        return None
    roles = {match_role(c)[0] for c in profile["column"]} - {None}
    if {"contract", "due_date"} <= roles:
        return "C"
    if {"approved_by", "created_by"} & roles and ("document_no" in roles or "amount" in roles) \
            and "counterparty" not in roles:
        return "A"
    if {"entity", "counterparty", "date", "amount"} <= roles:
        return "E"
    return None


# ---- certified checks on role columns (spec 4.2) and the CHECKS registry ----
# New checks read the internal columns the role adapter produces (ROLE_TO_INTERNAL), take every threshold from
# `cfg` and return the Evidence schema plus `roles_used` (the roles the check actually read).
STD_NOTE = "ค่ามาตรฐานจาก AIDA-14 ปรับได้ตามบริบทองค์กร"
ROLE_TEXT = {"record_id": "เลขที่รายการ", "date": "วันที่ของรายการ", "amount": "จำนวนเงิน",
             "entity": "entity เจ้าของรายการ", "counterparty": "คู่ค้า/ผู้รับ", "contract": "เลขที่สัญญา",
             "category": "หมวด", "channel": "ช่องทาง", "created_by": "ผู้บันทึก", "approved_by": "ผู้อนุมัติ",
             "document_no": "เลขที่เอกสาร", "limit": "วงเงินอนุมัติ", "due_date": "วันครบกำหนด",
             "opened_at": "วันที่เปิดบัญชี"}


def _col(role: str) -> str:
    return ROLE_TO_INTERNAL.get(role, role)


def _has(tx: pd.DataFrame, role: str) -> bool:
    c = _col(role)
    return c in tx.columns and bool(tx[c].notna().any())


def _text(tx: pd.DataFrame, role: str) -> pd.Series:
    """The role's column as stripped text, "" for a missing value."""
    return tx[_col(role)].where(tx[_col(role)].notna(), "").astype(str).str.strip()


def _gen_tx(tables: dict) -> pd.DataFrame:
    """Transactions of the role frame with a parsed date (ts), a positive numeric amount, text ids and
    `period` (YYYY-MM), in date order. Unlike clean_tx it does not drop entity == counterparty rows
    (a borrower paying their own loan is normal data) and does not need every role."""
    t = tables["transactions"].copy()
    t["ts"] = pd.to_datetime(t["ts"], errors="coerce")
    t["tx_id"] = t["tx_id"].astype(str)
    keep = t["ts"].notna()
    if "amount" in t.columns:
        t["amount"] = pd.to_numeric(t["amount"], errors="coerce")
        keep &= t["amount"] > 0
    t = t[keep]
    return t.assign(period=t["ts"].dt.strftime("%Y-%m")).sort_values("ts", kind="mergesort")


def _finish(recipe_id: str, family: str, risk: str, key: str, found: list, cfg: dict, roles: list,
            merge: bool = False) -> pd.DataFrame:
    """Evidence rows from a list of dicts (entity_type, entity_id, period, metric, value, threshold,
    explanation, record_refs) + a roles_used column."""
    f = pd.DataFrame(found, columns=["entity_type", "entity_id", "period", "metric", "value", "threshold",
                                     "explanation", "record_refs"])
    if merge and len(f):
        f = one_per_month(f)
    ev = evidence_rows(recipe_id, "1.0", family, risk, key, f, cfg)
    return ev.assign(roles_used=[list(roles) for _ in range(len(ev))])


def _chain_ids(day: pd.Series, groups: list, window: float) -> pd.Series:
    """Cluster id per row: rows of one group (rows sorted by date) whose day gap to the previous row of the
    group is <= window days stay in the same cluster."""
    gap = day.groupby(groups, sort=False).diff().dt.days
    new = ~(gap <= window)
    return new.astype(int).groupby(groups, sort=False).cumsum()


def _ids_text(ids: list, n: int = 5) -> str:
    return ", ".join(ids[:n]) + (f" และอีก {len(ids) - n} รายการ" if len(ids) > n else "")


# ---- GEN-CONC ----
def gen_conc(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    thr, topn, h = cfg["CONC.SINGLE_ENTITY_SHARE"], cfg["CONC.TOPN"], cfg["CONC.HHI"]
    dims = [("entity", "entity", "entity")]
    if _has(t, "counterparty"):
        dims.append(("counterparty", "counterparty", "คู่ค้า (counterparty)"))
    found = []
    for role, etype, label in dims:
        d = t[t[_col(role)].notna()]
        g = d.groupby(_col(role))["amount"].sum()
        if len(g) == 0 or len(g) * thr <= 1:
            continue  # with so few parties an equal split already reaches the threshold
        share = g / g.sum()
        hhi = float(((share * 100) ** 2).sum())
        level = "ต่ำ" if hhi < h["low"] else "ปานกลาง" if hhi <= h["high"] else "สูง"
        for ent in share[share >= thr].index:
            e = d[d[_col(role)] == ent]
            top = e.sort_values("amount", ascending=False, kind="mergesort").head(topn)
            found.append({
                "entity_type": etype, "entity_id": str(ent), "period": e["period"].max(),
                "metric": "amount_share", "value": round(float(share[ent]), 4), "threshold": thr,
                "explanation": (f"{label} {ent} มียอดรวม {g[ent]:,.2f} คิดเป็น {share[ent]:.1%} ของยอดรวมทั้งชุด "
                                f"({len(e):,} รายการ) ตั้งแต่ CONC.SINGLE_ENTITY_SHARE {thr:.0%} ขึ้นไป; HHI ของทั้งชุด "
                                f"{hhi:,.0f} ระดับ{level} (CONC.HHI; {STD_NOTE}) — สอดคล้องกับ pattern การกระจุกตัว "
                                f"ควรตรวจสอบเพิ่มเติม (รายการอ้างอิงคือ {len(top)} ยอดสูงสุดตาม CONC.TOPN)"),
                "record_refs": list(top["tx_id"])})
    roles = ["record_id", "date", "amount", "entity"] + (["counterparty"] if len(dims) > 1 else [])
    return _finish("GEN-CONC", "5.2 Concentration", "A-R4", "CONC.SINGLE_ENTITY_SHARE", found, cfg, roles)


# ---- GEN-PERIOD-END ----
def gen_period_end(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    w, k, share = cfg["TEMP.PERIOD_END.WINDOW"], cfg["TEMP.PERIOD_END.MIN_TX"], cfg["TEMP.PERIOD_END.MIN_SHARE"]
    t = t[t[_col("entity")].notna()]
    day = t["ts"].dt.normalize()
    d64 = day.values.astype("datetime64[D]")
    end = day.dt.to_period("M").dt.end_time.dt.normalize().values.astype("datetime64[D]")
    before = np.is_busday(d64) & (np.busday_count(d64 + ONE_DAY, end + ONE_DAY) < w["before_business_days"])
    after = (day.dt.day <= w["after_days"]).values
    prev = (day.dt.to_period("M") - 1).astype(str)
    t = t.assign(w_period=np.where(before, t["period"], np.where(after, prev, "")), w=before | after)
    ent = _col("entity")
    month_n = t.groupby([ent, "period"]).size()
    win = t[t["w"]].groupby([ent, "w_period"]).agg(n=("tx_id", "size"), refs=("tx_id", list))
    after_n = t[after & ~before].groupby([ent, "w_period"]).size()
    found = []
    for (a, p), r in win.iterrows():
        total = int(month_n.get((a, p), 0)) + int(after_n.get((a, p), 0))
        if r["n"] >= k and total and r["n"] / total >= share:
            found.append({
                "entity_type": "entity", "entity_id": str(a), "period": p, "metric": "period_end_share",
                "value": round(r["n"] / total, 4), "threshold": share,
                "explanation": (f"งวด {p} มี {r['n']} จาก {total} รายการ ({r['n'] / total:.0%}) ของ entity {a} อยู่ในช่วงสิ้นงวด "
                                f"({w['before_business_days']} วันทำการสุดท้ายของงวด + {w['after_days']} วันแรกของงวดถัดไป; "
                                f"TEMP.PERIOD_END.WINDOW) ครบทั้ง TEMP.PERIOD_END.MIN_TX ≥ {k} รายการ และ "
                                f"TEMP.PERIOD_END.MIN_SHARE ≥ {share:.0%} ({STD_NOTE}) — สอดคล้องกับ pattern "
                                f"กิจกรรมกระจุกช่วงสิ้นงวด ควรตรวจสอบเพิ่มเติม"),
                "record_refs": r["refs"]})
    return _finish("GEN-PERIOD-END", "5.4 Temporal", "G-R2", "TEMP.PERIOD_END.WINDOW", found, cfg,
                   ["record_id", "date", "amount", "entity"])


# ---- DUP-PAY ----
def dup_pay(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    win = cfg["DUP.WINDOW_DAYS"]
    t = t[t[_col("entity")].notna()].copy()
    has_cp, has_doc = _has(t, "counterparty"), _has(t, "document_no")
    use_contract = _has(t, "contract") and not has_doc  # loan style data: the contract is the reported unit
    t["_e"], t["_a"] = _text(t, "entity"), t["amount"].round(2)
    keys = ["_e", "_a"]
    if has_cp:
        t["_c"] = _text(t, "counterparty")
        keys.append("_c")
    if has_doc:
        t["_n"] = _text(t, "document_no")
        keys.append("_n")
    t["_day"] = t["ts"].dt.normalize()
    t["_cl"] = _chain_ids(t["_day"], [t[k] for k in keys], win)
    t["_u"] = _text(t, "contract") if use_contract else t["_e"]
    found = []
    for _, g in t.groupby(keys + ["_cl"], sort=False):
        if len(g) < 2:
            continue
        ids, span = list(g["tx_id"]), (g["_day"].max() - g["_day"].min()).days
        doc = f" เลขที่เอกสาร {g['_n'].iloc[0]}" if has_doc else ""
        unit = "สัญญา" if use_contract else "entity"
        found.append({
            "entity_type": "contract" if use_contract else "entity", "entity_id": g["_u"].iloc[0],
            "period": g["period"].iloc[-1], "metric": "duplicate_payment_count", "value": len(g), "threshold": win,
            "explanation": (f"{unit} {g['_u'].iloc[0]} มีรายการยอด {g['amount'].iloc[0]:,.2f} เท่ากัน {len(g)} รายการ"
                            f"{doc} ห่างกัน {span} วัน ({_ids_text(ids)}) ภายใน DUP.WINDOW_DAYS {win} วัน ({STD_NOTE}) — "
                            f"สอดคล้องกับ pattern การจ่าย/ชำระซ้ำ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": ids})
    roles = ["record_id", "date", "amount", "entity"] + (["counterparty"] if has_cp else []) \
        + (["document_no"] if has_doc else []) + (["contract"] if use_contract else [])
    return _finish("DUP-PAY", "5.6 Forensic", "C-R3" if use_contract else "A-R1", "DUP.WINDOW_DAYS", found, cfg,
                   roles, merge=True)


# ---- SPLIT-LIMIT ----
def split_limit(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    win, k, band = cfg["SPLIT.WINDOW_DAYS"], cfg["SPLIT.MIN_TX"], cfg["FOR.THRESHOLD_AVOID.BAND"]
    t = t[t[_col("entity")].notna()].copy()
    t["_lim"] = pd.to_numeric(t["limit"], errors="coerce")
    ratio = t["amount"] / t["_lim"]
    t = t[(t["_lim"] > 0) & (ratio >= band["low"]) & (ratio <= band["high"])].copy()
    has_cp = _has(t, "counterparty")
    t["_e"] = _text(t, "entity")
    keys = ["_e"] + (["_c"] if has_cp else []) + ["_lim"]
    if has_cp:
        t["_c"] = _text(t, "counterparty")
    t["_day"] = t["ts"].dt.normalize()
    found = []
    if len(t):
        t["_cl"] = _chain_ids(t["_day"], [t[c] for c in keys], win)
        for _, g in t.groupby(keys + ["_cl"], sort=False):
            lim, total = float(g["_lim"].iloc[0]), float(g["amount"].sum())
            if len(g) < k or total <= lim:
                continue
            ids = list(g["tx_id"])
            found.append({
                "entity_type": "entity", "entity_id": g["_e"].iloc[0], "period": g["period"].iloc[-1],
                "metric": "split_total", "value": round(total, 2), "threshold": lim,
                "explanation": (f"entity {g['_e'].iloc[0]} มี {len(g)} รายการ ({_ids_text(ids)}) ภายใน SPLIT.WINDOW_DAYS "
                                f"{win} วัน ซึ่งแต่ละรายการอยู่ที่ {band['low']:.0%}–{band['high']:.2%} ของวงเงิน {lim:,.2f} "
                                f"(FOR.THRESHOLD_AVOID.BAND) แต่รวมกัน {total:,.2f} เกินวงเงิน และมีอย่างน้อย SPLIT.MIN_TX "
                                f"{k} รายการ ({STD_NOTE}) — สอดคล้องกับ pattern การแบ่งรายการต่ำกว่าวงเงิน ควรตรวจสอบเพิ่มเติม"),
                "record_refs": ids})
    return _finish("SPLIT-LIMIT", "5.6 Forensic", "A-R2", "SPLIT.WINDOW_DAYS", found, cfg,
                   ["record_id", "date", "amount", "entity", "limit"] + (["counterparty"] if has_cp else []),
                   merge=True)


# ---- FOR-BENFORD ----
ONE_DAY = np.timedelta64(1, "D")
BENFORD_EXPECTED = np.log10(1 + 1 / np.arange(1, 10))


def _first_digits(a: pd.Series) -> np.ndarray:
    return np.array([int(f"{x:.10e}"[0]) for x in a])


def for_benford(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    n_min, lim = cfg["FOR.BENFORD.MIN_N"], cfg["FOR.BENFORD.MAD_1ST"]
    t = t[t[_col("entity")].notna() & (t["amount"] >= 10)]
    found = []
    for ent, g in t.groupby(_col("entity")):
        if len(g) < n_min:
            continue
        dg = _first_digits(g["amount"])
        obs = np.bincount(dg, minlength=10)[1:10] / len(g)
        mad = float(np.abs(obs - BENFORD_EXPECTED).mean())
        if mad <= lim["marginal"]:
            continue
        worst = int(np.argmax(obs - BENFORD_EXPECTED)) + 1
        found.append({
            "entity_type": "entity", "entity_id": str(ent), "period": g["period"].max(),
            "metric": "benford_mad_1st", "value": round(mad, 4), "threshold": lim["marginal"],
            "explanation": (f"entity {ent} มี {len(g):,} รายการยอดตั้งแต่ 10 (≥ FOR.BENFORD.MIN_N {n_min:,}) "
                            f"MAD หลักแรก {mad:.4f} สูงกว่า {lim['marginal']} (ระดับไม่สอดคล้อง; FOR.BENFORD.MAD_1ST "
                            f"{STD_NOTE}) หลักที่เบี่ยงมากที่สุดคือ {worst} (พบ {obs[worst - 1]:.1%} คาด "
                            f"{BENFORD_EXPECTED[worst - 1]:.1%}) — สอดคล้องกับ pattern ตัวเลขผิดธรรมชาติ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(g["tx_id"][dg == worst])})
    return _finish("FOR-BENFORD", "5.6 Forensic", "G-R4", "FOR.BENFORD.MIN_N", found, cfg,
                   ["record_id", "date", "amount", "entity"])


# ---- FOR-ROUND ----
def for_round(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    unit, share, n_min = cfg["FOR.ROUND.UNIT"], cfg["FOR.ROUND.MIN_SHARE"], cfg["GATE.SAMPLE.MIN"]
    t = t[t[_col("entity")].notna()].copy()
    t["_r"] = np.round(t["amount"] * 100).astype("int64") % int(round(unit * 100)) == 0
    found = []
    for ent, g in t.groupby(_col("entity")):
        k = int(g["_r"].sum())
        if len(g) < n_min or k == 0 or k / len(g) < share:
            continue
        r = g[g["_r"]]
        found.append({
            "entity_type": "entity", "entity_id": str(ent), "period": r["period"].max(),
            "metric": "round_amount_share", "value": round(k / len(g), 4), "threshold": share,
            "explanation": (f"entity {ent} มี {k} จาก {len(g)} รายการ ({k / len(g):.0%}) เป็นยอดกลมที่หารด้วย "
                            f"FOR.ROUND.UNIT {unit:,.0f} ลงตัว สูงกว่า FOR.ROUND.MIN_SHARE {share:.0%} และมีรายการไม่น้อยกว่า "
                            f"GATE.SAMPLE.MIN {n_min} ({STD_NOTE}) — สอดคล้องกับ pattern ตัวเลขผิดธรรมชาติ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(r["tx_id"])})
    return _finish("FOR-ROUND", "5.6 Forensic", "G-R4", "FOR.ROUND.UNIT", found, cfg,
                   ["record_id", "date", "amount", "entity"])


# ---- FOR-REPEAT ----
def for_repeat(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    need = cfg["FOR.REPEAT.MIN_COUNT"]
    t = t[t[_col("entity")].notna()].assign(_a=lambda d: d["amount"].round(2))
    found = []
    for (ent, amt, p), g in t.groupby([_col("entity"), "_a", "period"], sort=False):
        if len(g) < need:
            continue  # same entity, same amount, same period: a monthly instalment never repeats within one period
        found.append({
            "entity_type": "entity", "entity_id": str(ent), "period": p, "metric": "same_amount_count",
            "value": len(g), "threshold": need,
            "explanation": (f"entity {ent} มียอด {amt:,.2f} เท่ากัน {len(g)} รายการในงวด {p} ({_ids_text(list(g['tx_id']))}) "
                            f"ตั้งแต่ FOR.REPEAT.MIN_COUNT {need} ครั้งในงวดเดียวกัน ({STD_NOTE}) — สอดคล้องกับ pattern "
                            f"ตัวเลขผิดธรรมชาติ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(g["tx_id"])})
    return _finish("FOR-REPEAT", "5.6 Forensic", "G-R4", "FOR.REPEAT.MIN_COUNT", found, cfg,
                   ["record_id", "date", "amount", "entity"], merge=True)


# ---- SOD-SAME-USER ----
def sod_same_user(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    c, a = _text(t, "created_by"), _text(t, "approved_by")
    same = t[(c != "") & (c == a)].assign(_u=c)
    found = []
    for (u, p), g in same.groupby(["_u", "period"], sort=False):
        found.append({
            "entity_type": "user", "entity_id": u, "period": p, "metric": "same_user_count", "value": len(g),
            "threshold": 1,
            "explanation": (f"ผู้ใช้ {u} เป็นทั้งผู้บันทึกและผู้อนุมัติของ {len(g)} รายการในงวด {p} "
                            f"({_ids_text(list(g['tx_id']))}) — สอดคล้องกับ pattern การไม่แยกหน้าที่ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(g["tx_id"])})
    return _finish("SOD-SAME-USER", "5.7 Rule-Based", "A-R3", "SOD.SAME_USER", found, cfg,
                   ["record_id", "date", "created_by", "approved_by"])


# ---- DUE-NEAR ----
def due_near(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    near_d, share, n_min = cfg["DUE.NEAR_DAYS"], cfg["DUE.MIN_SHARE"], cfg["DUE.MIN_PERIODS"]
    t = t.assign(_due=pd.to_datetime(t["due_date"], errors="coerce").dt.normalize())
    t = t[t["contract"].notna() & t["_due"].notna()]
    t = t.assign(_dp=t["_due"].dt.strftime("%Y-%m"),
                 _days=(t["_due"] - t["ts"].dt.normalize()).dt.days)
    first = t.drop_duplicates(["contract", "_dp"])  # the first payment of each contract and due period
    found = []
    for con, g in first.groupby("contract"):
        near = g[(g["_days"] >= 0) & (g["_days"] <= near_d)]
        if len(g) < n_min or len(near) / len(g) < share:
            continue
        found.append({
            "entity_type": "contract", "entity_id": str(con), "period": g["_dp"].max(), "metric": "near_due_share",
            "value": round(len(near) / len(g), 4), "threshold": share,
            "explanation": (f"สัญญา {con} ชำระก่อนวันครบกำหนด 0–{near_d} วัน (DUE.NEAR_DAYS) ใน {len(near)} จาก "
                            f"{len(g)} งวด ({len(near) / len(g):.0%}) ครบทั้ง DUE.MIN_SHARE ≥ {share:.0%} และ "
                            f"DUE.MIN_PERIODS ≥ {n_min} งวด ({STD_NOTE}) — สอดคล้องกับ pattern ชำระใกล้วันครบกำหนดซ้ำ ๆ "
                            f"ซึ่งอาจเกี่ยวกับการจัดสถานะค้างชำระ ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(near["tx_id"])})
    return _finish("DUE-NEAR", "5.4 Temporal", "C-R2", "DUE.NEAR_DAYS", found, cfg,
                   ["record_id", "date", "contract", "due_date"], merge=True)


# ---- PAYER-MULTI ----
def payer_multi(tables: dict, cfg: dict) -> pd.DataFrame:
    t = _gen_tx(tables)
    need = cfg["PAYER.MIN_CONTRACTS"]
    t = t[t["to_acct"].notna() & t["from_acct"].notna() & t["contract"].notna()]
    t = t[t["to_acct"].astype(str) != t["from_acct"].astype(str)]
    found = []
    for payer, g in t.groupby("to_acct"):
        cons = sorted(g["contract"].astype(str).unique())
        if len(cons) < need:
            continue
        found.append({
            "entity_type": "counterparty", "entity_id": str(payer), "period": g["period"].max(),
            "metric": "distinct_contracts", "value": len(cons), "threshold": need,
            "explanation": (f"ผู้ชำระ {payer} ชำระ {len(cons)} สัญญาที่ต่างกัน ({_ids_text(cons)}) ซึ่ง entity ของสัญญาไม่ใช่ผู้ชำระ "
                            f"ตั้งแต่ PAYER.MIN_CONTRACTS {need} สัญญา ({STD_NOTE}) — สอดคล้องกับ pattern ผู้ชำระคนเดียวหลายสัญญา "
                            f"ควรตรวจสอบเพิ่มเติม"),
            "record_refs": list(g["tx_id"])})
    return _finish("PAYER-MULTI", "5.3 Behavioral", "C-R1", "PAYER.MIN_CONTRACTS", found, cfg,
                   ["record_id", "date", "entity", "counterparty", "contract"])


# ---- CHECKS registry ----
B1_ROLES = ["record_id", "date", "entity", "counterparty", "amount"]  # the five columns every B1 card needs


def _spec(func, risk, family, requires, registry, types, optional=(), alt=()):
    return {"func": func, "risk": risk, "risk_alt": list(alt), "skill_family": family, "requires": list(requires),
            "optional": list(optional), "registry": list(registry), "data_types": list(types)}


_GEN = ["record_id", "date", "amount", "entity"]
_ALL = ["E", "C", "A"]
CHECKS = {
    # migrated B1 cards (data type E; the general risks apply to any data type)
    "STAT-MAD": _spec(stat_mad, "R1", "5.1 Statistical", _GEN, ["STAT.MAD.THRESHOLD", "GATE.SAMPLE.MIN"], _ALL,
                      ["channel"], ["G-R1"]),
    "BEH-VELOCITY": _spec(beh_velocity, "R1", "5.3 Behavioral", _GEN,
                          ["BEH.DEVIATION", "BEH.BASELINE.MIN_PERIODS", "BEH.VELOCITY.SD_FLOOR"], _ALL, [], ["G-R1"]),
    "BEH-SPIKE": _spec(beh_spike, "R1", "5.3 Behavioral", _GEN, ["BEH.DEVIATION", "BEH.BASELINE.MIN_PERIODS"],
                       _ALL, [], ["G-R1"]),
    "TEMP-OFFHOURS": _spec(temp_offhours, "R1", "5.4 Temporal", ["record_id", "date", "entity"],
                           ["TEMP.OFF_HOURS", "TEMP.OFF_HOURS.MIN_TX", "TEMP.OFF_HOURS.MIN_SHARE"], _ALL, [], ["G-R3"]),
    "NET-CYCLE": _spec(net_cycle, "R1", "5.9 Network", B1_ROLES, ["NET.CYCLE", "NET.CYCLE.MAX_PATHS"], ["E"]),
    "NET-FUNNEL": _spec(net_funnel, "R1", "5.9 Network", B1_ROLES, ["NET.FUNNEL"], ["E"]),
    "MULE-DWELL": _spec(mule_dwell, "R1", "5.4 Temporal", B1_ROLES, ["MULE.DWELL_HOURS", "MULE.DWELL_MIN_PAIRS"], ["E"]),
    "MULE-NEW-ACCT": _spec(mule_new_acct, "R1", "5.7 Rule-Based", B1_ROLES,
                           ["MULE.NEW_ACCT_DAYS", "MULE.NEW_ACCT_MIN_TX"], ["E"], ["opened_at"]),
    "MULE-PATTERN": _spec(mule_pattern, "R2", "5.10 Hybrid", B1_ROLES, ["MULE.MIN_SIGNALS"], ["E"]),
    "MULE-CROSS-TX": _spec(mule_cross_tx, "R3", "5.9 Network", B1_ROLES, ["MULE.CROSS.MIN_LINKS", "FLOW.WINDOW_DAYS"], ["E"]),
    "MULE-NETWORK": _spec(mule_network, "R3", "5.9 Network", B1_ROLES, ["MULE.NETWORK.MIN_SIZE"], ["E"]),
    "CPTY-PROFILE": _spec(cpty_profile, "R4", "5.3 Behavioral", B1_ROLES,
                          ["CPTY.NEW_RATIO", "BEH.BASELINE.MIN_PERIODS"], ["E"]),
    "CPTY-NEW-LARGE": _spec(cpty_new_large, "R4", "5.3 Behavioral", B1_ROLES, ["CPTY.NEW_LARGE.MULTIPLIER"], ["E"]),
    "FLOW-LAYERING": _spec(flow_layering, "R1", "5.9 Network", B1_ROLES, ["FLOW.MIN_PASS_RATIO", "FLOW.WINDOW_DAYS"], ["E"]),
    # C1 checks on role columns
    "GEN-CONC": _spec(gen_conc, "A-R4", "5.2 Concentration", _GEN,
                      ["CONC.SINGLE_ENTITY_SHARE", "CONC.HHI", "CONC.TOPN"], _ALL, ["counterparty"]),
    "GEN-PERIOD-END": _spec(gen_period_end, "G-R2", "5.4 Temporal", _GEN,
                            ["TEMP.PERIOD_END.WINDOW", "TEMP.PERIOD_END.MIN_TX", "TEMP.PERIOD_END.MIN_SHARE"], _ALL),
    "DUP-PAY": _spec(dup_pay, "A-R1", "5.6 Forensic", _GEN, ["DUP.WINDOW_DAYS"], ["C", "A"],
                     ["counterparty", "document_no", "contract"], ["C-R3"]),
    "SPLIT-LIMIT": _spec(split_limit, "A-R2", "5.6 Forensic", _GEN + ["limit"],
                         ["SPLIT.WINDOW_DAYS", "SPLIT.MIN_TX", "FOR.THRESHOLD_AVOID.BAND"], ["A"], ["counterparty"]),
    "FOR-BENFORD": _spec(for_benford, "G-R4", "5.6 Forensic", _GEN, ["FOR.BENFORD.MIN_N", "FOR.BENFORD.MAD_1ST"], _ALL),
    "FOR-ROUND": _spec(for_round, "G-R4", "5.6 Forensic", _GEN,
                       ["FOR.ROUND.UNIT", "FOR.ROUND.MIN_SHARE", "GATE.SAMPLE.MIN"], _ALL),
    "FOR-REPEAT": _spec(for_repeat, "G-R4", "5.6 Forensic", _GEN, ["FOR.REPEAT.MIN_COUNT"], _ALL),
    "SOD-SAME-USER": _spec(sod_same_user, "A-R3", "5.7 Rule-Based", ["record_id", "date", "created_by", "approved_by"],
                           [], ["A"]),
    "DUE-NEAR": _spec(due_near, "C-R2", "5.4 Temporal", ["record_id", "date", "contract", "due_date"],
                      ["DUE.NEAR_DAYS", "DUE.MIN_SHARE", "DUE.MIN_PERIODS"], ["C"]),
    "PAYER-MULTI": _spec(payer_multi, "C-R1", "5.3 Behavioral", ["record_id", "date", "entity", "counterparty", "contract"],
                         ["PAYER.MIN_CONTRACTS"], ["C"]),
}


def plan_checks(tables: dict, cfg: dict = None) -> pd.DataFrame:
    """Run / Skip per certified check from the roles present in tables["transactions"] (internal columns).
    A Skip reason is Thai and names the missing roles and how to fix them."""
    tx = tables.get("transactions")
    rows = []
    for cid, spec in CHECKS.items():
        miss = [r for r in spec["requires"] if tx is None or not _has(tx, r)]
        if miss:
            what = " / ".join(f"{r} ({ROLE_TEXT.get(r, r)})" for r in miss)
            rows.append((cid, "Skip", f"ไม่มีบทบาทคอลัมน์ {what} หรือคอลัมน์ว่างทั้งคอลัมน์ ซึ่งการ์ดนี้ต้องใช้ จึงรันไม่ได้ — "
                                      f"แก้โดยกำหนดบทบาท {', '.join(miss)} ให้คอลัมน์ในไฟล์ที่จุดยืนยัน 1 แล้วรันใหม่", ", ".join(miss)))
        else:
            rows.append((cid, "Run", "มีบทบาทคอลัมน์ที่ต้องใช้ครบ", "-"))
    return pd.DataFrame(rows, columns=["recipe_id", "decision", "reason", "missing"])


# ---- Risk Library, sufficiency and risk suggestions (spec 4.3 step 2, 4.4) ----
# RISK_LIBRARY is the data the engine computes with; AIDA-18 will describe the same risks in prose for matching.
# A risk's checks are not typed in twice by hand: tests require them to equal the CHECKS entries whose "risk" or
# "risk_alt" names the risk.
# a joined master table (opened_at) must match >= cfg["INTAKE.JOIN_MIN_PCT"] (AIDA-14, 90%) of the transaction keys
JOIN_ROLES = ("opened_at",)  # roles that normally live in a secondary table joined by the entity id
NEEDS_TIME_CHECKS = {"TEMP-OFFHOURS"}  # checks that read the time of day, not only the date
TYPE_TEXT = {"E": "รายการโอนเงินระหว่างบัญชี", "C": "รับชำระค่างวดสินเชื่อ", "A": "จ่ายเงินเจ้าหนี้"}
REQ_TRANSFERS = ("รายการเงินฝากและโอนเงินของบัญชีผู้ชำระ (รหัสรายการ, วันเวลา, บัญชีต้นทาง, บัญชีปลายทาง, ยอดเงิน) "
                 "เพื่อดูการรับโอนและส่งต่อเงิน")
REQ_TIME = "วันที่ของรายการที่มีเวลา (ชั่วโมง:นาที) เพื่อดูรายการนอกเวลาทำการ"
_B1 = ["record_id", "date", "amount", "entity", "counterparty"]
_GENR = ["record_id", "date", "amount", "entity"]


def _risk(name, desc, syn, types, checks, roles, months=1, rows=30, req=None, join=()):
    return {"name_th": name, "description_th": desc, "synonyms": syn, "data_types": types, "checks": checks,
            "min_roles": roles, "min_data": {"months": months, "rows": rows},
            "request_if_missing": req or {}, "join_roles": list(join)}


_MULE_REQ = {"counterparty": REQ_TRANSFERS, "_data_type": REQ_TRANSFERS}
RISK_LIBRARY = {
    "R1": _risk("การเคลื่อนย้ายเงินผิดปกติ",
                "รายการโอนที่ยอดสูงหรือถี่ผิดปกติเมื่อเทียบกับพฤติกรรมปกติ นอกเวลาทำการ เงินวนกลับ หรือส่งต่อเป็นทอด ๆ "
                "ซึ่งสอดคล้องกับ pattern ที่ควรทบทวนเพิ่มเติม (ต้องเป็นรายการโอนระหว่างบัญชี)",
                ["การเคลื่อนย้ายเงินผิดปกติ", "เคลื่อนย้ายเงิน", "รับโอนเงินผิดปกติ", "โอนเงินผิดปกติ", "เงินวนกลับ",
                 "ส่งต่อเป็นทอด", "unusual fund movement", "abnormal transfer", "mule"],
                ["E"], ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE", "NET-FUNNEL",
                        "MULE-DWELL", "MULE-NEW-ACCT", "FLOW-LAYERING"], _B1, 1, 100, _MULE_REQ, ["opened_at"]),
    "R2": _risk("บัญชีที่รับแล้วส่งต่อเงินอย่างรวดเร็ว",
                "บัญชีที่มีหลายสัญญาณพร้อมกัน เช่น รับจากหลายแหล่งแล้วโอนออกเกือบหมดในเวลาสั้น โดยเฉพาะบัญชีเปิดใหม่ "
                "สอดคล้องกับ pattern ที่ควรทบทวนรายบัญชี",
                ["รับแล้วส่งต่อ", "ส่งต่อเงินอย่างรวดเร็ว", "บัญชีเปิดใหม่", "pass-through", "pass through",
                 "rapid onward transfer", "mule account"],
                ["E"], ["MULE-PATTERN"], _B1, 1, 100, _MULE_REQ, ["opened_at"]),
    "R3": _risk("เครือข่ายบัญชีที่เชื่อมโยงกัน",
                "ธุรกรรมระหว่างกลุ่มบัญชีที่เชื่อมโยงกันเป็นเครือข่าย ซึ่งอาจเกี่ยวข้องกับการกระจายหรือรวมเงินร่วมกัน",
                ["เครือข่าย", "กลุ่มบัญชีที่เชื่อมโยง", "เชื่อมโยงกันเป็นเครือข่าย", "linked accounts", "network of accounts"],
                ["E"], ["MULE-CROSS-TX", "MULE-NETWORK"], _B1, 1, 100, _MULE_REQ),
    "R4": _risk("ความผิดปกติของคู่ค้า",
                "การโอนไปยังคู่ค้าใหม่ด้วยยอดสูงผิดปกติ หรือสัดส่วนคู่ค้าใหม่ที่เปลี่ยนไปจากพฤติกรรมเดิม",
                ["ความผิดปกติของคู่ค้า", "คู่ค้าใหม่", "โอนไปบัญชีใหม่", "new counterparty", "counterparty anomaly"],
                ["E"], ["CPTY-PROFILE", "CPTY-NEW-LARGE"], _B1, 2, 100, _MULE_REQ),
    "G-R1": _risk("ยอดโดดเด่น",
                  "รายการหรือบัญชีที่ยอดโดดเด่นหรือถี่ผิดปกติเมื่อเทียบกับพฤติกรรมปกติของตนเองและของกลุ่ม",
                  ["ยอดโดดเด่น", "ยอดสูงผิดปกติ", "ยอดผิดปกติ", "outlier amount", "unusual amount", "amount outlier"],
                  ["E", "C", "A"], ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE"], _GENR, 1, 100),
    "G-R2": _risk("ช่วงสิ้นงวด",
                  "รายการกระจุกตัวในช่วงสิ้นเดือนหรือสิ้นงวดบัญชีมากกว่าปกติ",
                  ["ช่วงสิ้นงวด", "สิ้นงวด", "สิ้นเดือน", "ปิดงวด", "period end", "period-end", "month end", "cut-off"],
                  ["E", "C", "A"], ["GEN-PERIOD-END"], _GENR),
    "G-R3": _risk("นอกเวลาทำการ",
                  "รายการที่เกิดนอกเวลาทำการหรือวันหยุดเป็นสัดส่วนสูง (ต้องมีเวลาของรายการ ไม่ใช่เฉพาะวันที่)",
                  ["นอกเวลาทำการ", "นอกเวลางาน", "วันหยุด", "off-hours", "off hours", "after hours", "after-hours"],
                  ["E", "C", "A"], ["TEMP-OFFHOURS"], ["record_id", "date", "entity"], 1, 100,
                  {"date": REQ_TIME, "_time": REQ_TIME}),
    "G-R4": _risk("ตัวเลขผิดธรรมชาติ",
                  "การกระจายตัวเลขหลักแรกผิดจาก Benford ยอดกลมหรือยอดซ้ำถี่ผิดปกติ ซึ่งอาจเกิดจากการกำหนดตัวเลข "
                  "ไม่ใช่ธุรกรรมจริง",
                  ["ตัวเลขผิดธรรมชาติ", "ยอดกลม", "ยอดซ้ำ", "benford", "round amount", "round number", "repeated amount",
                   "unnatural number"],
                  ["E", "C", "A"], ["FOR-BENFORD", "FOR-ROUND", "FOR-REPEAT"], _GENR, 1, 100),
    "C-R1": _risk("ผู้ชำระคนเดียวหลายสัญญา",
                  "ผู้ชำระรายเดียวชำระแทนผู้กู้หลายสัญญา อาจเป็นการชำระแทนที่ไม่ได้เปิดเผยความสัมพันธ์ รวมถึง pattern "
                  "ปิดบัญชีก่อนกำหนดจากผู้ชำระอื่น (ใช้การ์ดเดียวกัน ไม่มีรหัสความเสี่ยงแยก)",
                  ["ผู้ชำระรายเดียว", "ผู้ชำระคนเดียว", "ชำระแทน", "ผู้ชำระหลายสัญญา", "ปิดบัญชีก่อนกำหนด",
                   "payer multiple contracts", "third-party payer", "third party payer", "one payer many contracts"],
                  ["C"], ["PAYER-MULTI"], ["record_id", "date", "entity", "counterparty", "contract"], 1, 50),
    "C-R2": _risk("ชำระใกล้วันครบกำหนดซ้ำ ๆ (อาจตกแต่งสถานะค้างชำระ)",
                  "ลูกหนี้ชำระก่อนวันครบกำหนดเพียงไม่กี่วันแทบทุกงวด สอดคล้องกับ pattern ที่อาจเกี่ยวกับการจัดสถานะค้างชำระ",
                  ["ชำระใกล้วันครบกำหนด", "ก่อนวันครบกำหนด", "ตกแต่งสถานะค้างชำระ", "สถานะค้างชำระ",
                   "near due date", "near the due date", "overdue status", "window dressing"],
                  ["C"], ["DUE-NEAR"], ["record_id", "date", "contract", "due_date"], 3, 50),
    "C-R3": _risk("ชำระซ้ำ/คืนเงินผิดปกติ",
                  "การชำระงวดเดียวกันซ้ำในช่วงสั้น หรือการคืนเงินที่ผิดปกติ ซึ่งควรตรวจสอบเพิ่มเติม",
                  ["ชำระซ้ำ", "คืนเงินผิดปกติ", "คืนเงิน", "refund", "double payment on contract"],
                  ["C"], ["DUP-PAY"], _GENR, 1, 50),
    "A-R1": _risk("จ่ายซ้ำ",
                  "การจ่ายเงินซ้ำสำหรับใบแจ้งหนี้หรือผู้ขายและยอดเดียวกันในช่วงเวลาใกล้กัน",
                  ["จ่ายซ้ำ", "จ่ายเงินซ้ำ", "จ่ายซ้ำซ้อน", "จ่ายเงินซ้ำซ้อน", "duplicate payment", "double payment",
                   "paid twice", "duplicate invoice"],
                  ["A"], ["DUP-PAY"], _GENR, 1, 50),
    "A-R2": _risk("แบ่งรายการต่ำกว่าวงเงิน",
                  "การแบ่งจ่ายเป็นหลายรายการให้ยอดแต่ละรายการต่ำกว่าวงเงินอนุมัติ",
                  ["แบ่งรายการ", "แบ่งจ่าย", "ต่ำกว่าวงเงิน", "หลบวงเงิน", "split payment", "split below limit",
                   "below approval limit", "threshold avoidance", "splitting"],
                  ["A"], ["SPLIT-LIMIT"], _GENR + ["limit"], 1, 50,
                  {"limit": "วงเงินอนุมัติของแต่ละรายการ (approval limit) เพื่อเทียบยอดกับวงเงิน"}),
    "A-R3": _risk("ผู้บันทึกและผู้อนุมัติเป็นคนเดียวกัน",
                  "รายการที่ผู้บันทึกและผู้อนุมัติเป็นบุคคลเดียวกัน (การแบ่งแยกหน้าที่ไม่สมบูรณ์)",
                  ["ผู้บันทึกและผู้อนุมัติ", "คนเดียวกัน", "แบ่งแยกหน้าที่", "segregation of duties", "sod",
                   "same user", "maker checker", "maker-checker"],
                  ["A"], ["SOD-SAME-USER"], ["record_id", "date", "created_by", "approved_by"], 1, 50,
                  {"created_by": "ผู้บันทึกรายการ (created_by) ของแต่ละรายการ",
                   "approved_by": "ผู้อนุมัติรายการ (approved_by) ของแต่ละรายการ"}),
    "A-R4": _risk("ผู้ขายกระจุกตัว",
                  "ยอดจ่ายกระจุกตัวอยู่ที่ผู้ขายรายเดียวหรือไม่กี่รายในสัดส่วนสูงเมื่อเทียบกับยอดรวม",
                  ["ผู้ขายกระจุกตัว", "กระจุกตัว", "พึ่งพาผู้ขายรายเดียว", "vendor concentration", "concentration",
                   "single vendor"],
                  ["A"], ["GEN-CONC"], _GENR, 1, 50),
}


def _norm_concern(s) -> str:
    return "".join(str(s).casefold().split())


def _syn_in(syn: str, concern) -> bool:
    """Does the concern contain the synonym? Thai: substring with whitespace removed (Thai is written without
    spaces). ASCII: whole words only (single-spaced, case-folded), so "sod" does not match "episode"."""
    if syn.isascii():
        words = " ".join(syn.casefold().split())
        text = " ".join(str(concern).casefold().split())
        return bool(words) and re.search(r"(?<![a-z0-9])" + re.escape(words) + r"(?![a-z0-9])", text) is not None
    n = _norm_concern(syn)
    return bool(n) and n in _norm_concern(concern)


def match_concerns(concerns: list) -> list:
    """Risk Concern text -> Risk Library. Each concern gives {concern, risk_id, matched_by, mode}. A concern matches
    the risk whose synonym (Thai or English, case and whitespace ignored) it contains; the longest synonym wins,
    a tie goes to the first risk in RISK_LIBRARY order. No match: risk_id None, matched_by None, mode "สำรวจ"
    (exploratory mode). Every concern is returned, in order."""
    out = []
    for c in concerns:
        best = None
        for rid, lib in RISK_LIBRARY.items():
            for syn in lib["synonyms"]:
                n = len(_norm_concern(syn))
                if _syn_in(syn, c) and (best is None or n > best[0]):
                    best = (n, rid, syn)
        out.append({"concern": c, "risk_id": best[1] if best else None, "matched_by": best[2] if best else None,
                    "mode": "รับรอง" if best else "สำรวจ"})
    return out


def _roles_by_table(roles_confirmed: dict) -> tuple:
    """(transaction table name, its roles {role: column}, {other table: {role: column}}) from {table: {column: role}};
    the transaction table is chosen as to_internal does (the most of record_id / date / amount)."""
    tx_name, best = None, 0
    for name, rmap in roles_confirmed.items():
        score = sum(1 for r in rmap.values() if r in TX_ROLES)
        if score > best:
            tx_name, best = name, score
    by = {n: {r: c for c, r in rmap.items()} for n, rmap in roles_confirmed.items()}
    if tx_name is None:
        merged = {}
        for d in by.values():
            merged.update(d)
        return None, merged, {}
    return tx_name, by[tx_name], {n: d for n, d in by.items() if n != tx_name}


def _type_from_roles(roles: set, profile=None):
    """Dataset type E / C / A from the confirmed roles (same rules as detect_dataset_type), else from the profile."""
    if {"contract", "due_date"} <= roles:
        return "C"
    if {"approved_by", "created_by"} & roles and ("document_no" in roles or "amount" in roles) \
            and "counterparty" not in roles:
        return "A"
    if {"entity", "counterparty", "date", "amount"} <= roles:
        return "E"
    return detect_dataset_type(profile) if profile is not None else None


def _months_between(lo, hi) -> int:
    lo, hi = pd.to_datetime(lo, errors="coerce"), pd.to_datetime(hi, errors="coerce")
    if pd.isna(lo) or pd.isna(hi):
        return 0
    return (hi.year - lo.year) * 12 + hi.month - lo.month + 1


def _intake_ctx(roles_confirmed: dict, profile=None, tables=None, cfg: dict = None) -> dict:
    """What sufficiency needs to know: the roles present, the dataset type, rows and months of the transaction
    table, whether the date carries a time of day, and how well each secondary table joins. Taken from the
    profile when given, else from the internal tables. With tables, also the data-volume skips of the checks
    (what gate_volume did in B1) and with cfg the join threshold."""
    tx_name, tx_roles, others = _roles_by_table(roles_confirmed)
    ctx = {"roles": set(tx_roles), "dtype": _type_from_roles(set(tx_roles), profile), "rows": None, "months": None,
           "has_time": None, "joins": {}, "vol": {},
           "join_min": 100.0 * cfg["INTAKE.JOIN_MIN_PCT"] if cfg else 100.0 * 0.9}
    if profile is not None and len(profile) and tx_name is not None:
        pt = profile[profile["table"] == tx_name]
        if len(pt):
            ctx["rows"] = int(pt["n_rows"].max())
        dcol = tx_roles.get("date")
        d = pt[pt["column"] == dcol]
        if len(d):
            ctx["months"] = _months_between(d.iloc[0]["min"], d.iloc[0]["max"])
            ctx["has_time"] = "datetime" in list(d.iloc[0]["patterns"])
        for role in JOIN_ROLES:
            for tname, rmap in others.items():
                if role in rmap and "entity" in rmap:
                    # coverage = share of the transaction table's entity values found in the master table's id
                    j = pt[pt["column"] == tx_roles.get("entity")]
                    jm = j.iloc[0]["join_match"] if len(j) else None
                    ok = isinstance(jm, dict) and str(jm["with"]).startswith(f"{tname}.")
                    ctx["joins"][role] = (tname, float(jm["normalized"]) if ok else 0.0)
    if profile is None and tables is not None and "transactions" in tables:
        tx = tables["transactions"]
        ctx["rows"] = int(len(tx))
        if "ts" in tx.columns:
            ts = pd.to_datetime(tx["ts"], errors="coerce").dropna()
            if len(ts):
                ctx["months"] = _months_between(ts.min(), ts.max())
                ctx["has_time"] = bool((ts != ts.dt.normalize()).any())
    if tables is not None and cfg and "transactions" in tables:
        ctx["vol"] = _volume_skips(tables, cfg)
    return ctx


def _volume_skips(tables: dict, cfg: dict) -> dict:
    """{check id: Thai reason} for checks the data is too thin for (same conditions and wording as gate_volume):
    B1 transfer data uses gate_volume itself; other data types use the entity-history / group-size conditions."""
    tx = tables["transactions"]
    try:
        if "to_acct" in tx.columns and "contract" not in tx.columns:
            out = gate_volume(tables, cfg)
        else:
            out = vol_baseline(base_tx(tables), cfg)
    except (KeyError, ValueError):  # a role the volume rules read is missing: the role rule already skips the check
        return {}
    return {c: r for c, r in out.items() if c in CHECKS}


def _missing_text(miss: list) -> str:
    return " / ".join(f"{r} ({ROLE_TEXT.get(r, r)})" for r in miss)


def _check_state(cid: str, ctx: dict, lib: dict) -> tuple:
    """(runnable, Thai reason, missing, kind) of one check for one risk. kind: role / type / time."""
    spec = CHECKS[cid]
    miss = [r for r in spec["requires"] if r not in ctx["roles"]]
    if miss:
        return (False, f"ไม่มีบทบาทคอลัมน์ {_missing_text(miss)} ซึ่งการ์ดนี้ต้องใช้ จึงรันไม่ได้ — แก้โดยกำหนดบทบาท "
                       f"{', '.join(miss)} ให้คอลัมน์ในไฟล์ที่จุดยืนยัน 1 แล้วรันใหม่", ", ".join(miss), "role")
    dt = ctx["dtype"]
    if dt is not None and (dt not in spec["data_types"] or dt not in lib["data_types"]):
        want = "/".join(TYPE_TEXT[t] for t in (set(spec["data_types"]) & set(lib["data_types"]) or spec["data_types"]))
        return (False, f"การ์ดนี้ใช้กับข้อมูลประเภท{want} แต่ข้อมูลนี้เป็นประเภท{TYPE_TEXT[dt]} "
                       f"(คอลัมน์ที่มีไม่ใช่ข้อมูลที่การ์ดนี้ออกแบบมา) จึงรันไม่ได้ — ต้องขอข้อมูลประเภทที่ตรงกับความเสี่ยงนี้เพิ่ม",
                "ประเภทข้อมูล", "type")
    if cid in NEEDS_TIME_CHECKS and ctx["has_time"] is False:
        return (False, "คอลัมน์วันที่มีเฉพาะวัน ไม่มีเวลาของรายการ ซึ่งการ์ดนี้ต้องใช้ดูรายการนอกเวลาทำการ จึงรันไม่ได้ "
                       "— ขอข้อมูลที่มีเวลาของรายการเพิ่ม", "เวลาของรายการ", "time")
    if cid in ctx["vol"]:
        return False, ctx["vol"][cid], "ปริมาณข้อมูลไม่พอ", "volume"
    return True, "มีบทบาทคอลัมน์ที่ต้องใช้ครบ", "-", ""


def _assess_one(rid: str, ctx: dict) -> dict:
    lib = RISK_LIBRARY[rid]
    run, skipped, kinds = [], {}, []
    for cid in lib["checks"]:
        ok, reason, _, kind = _check_state(cid, ctx, lib)
        if ok:
            run.append(cid)
        else:
            skipped[cid] = reason
            kinds.append((kind, cid))
    reasons, req = [], []

    def ask(t):
        if t and t not in req:
            req.append(t)
    miss_roles = [r for r in lib["min_roles"] if r not in ctx["roles"]]
    short = False
    md = lib["min_data"]
    if ctx["rows"] is not None and ctx["rows"] < md["rows"]:
        short = True
        reasons.append(f"มีข้อมูล {ctx['rows']:,} รายการ น้อยกว่าขั้นต่ำ {md['rows']:,} รายการของความเสี่ยงนี้")
        ask(f"ข้อมูลเพิ่มอย่างน้อย {md['rows']:,} รายการ")
    if ctx["months"] is not None and ctx["months"] < md["months"]:
        short = True
        reasons.append(f"ข้อมูลครอบคลุม {ctx['months']} เดือน น้อยกว่าขั้นต่ำ {md['months']} เดือน")
        ask(f"ข้อมูลย้อนหลังให้ครอบคลุมอย่างน้อย {md['months']} เดือน")
    if miss_roles:
        reasons.append(f"ขาดบทบาทคอลัมน์ {_missing_text(miss_roles)}")
        for r in miss_roles:
            ask(lib["request_if_missing"].get(r) or f"คอลัมน์{ROLE_TEXT.get(r, r)} (บทบาท {r}) ของรายการ")
    if not run or miss_roles or short:
        status = "ไม่พอ"
    elif skipped:
        status = "บางส่วน"
    else:
        status = "พร้อม"
    for kind, cid in kinds:
        if kind == "type":
            ask(lib["request_if_missing"].get("_data_type") or
                f"ข้อมูลประเภท{'/'.join(TYPE_TEXT[t] for t in lib['data_types'])}ที่ตรงกับความเสี่ยงนี้")
        elif kind == "time":
            ask(lib["request_if_missing"].get("_time") or REQ_TIME)
        elif kind == "volume":
            ask("ข้อมูลช่วงเวลายาวขึ้นหรือจำนวนรายการต่อบัญชี/กลุ่มมากขึ้น เพื่อให้สร้าง baseline หรือคำนวณได้")
        elif kind == "role":
            for r in [r for r in CHECKS[cid]["requires"] if r not in ctx["roles"]]:
                ask(lib["request_if_missing"].get(r) or f"คอลัมน์{ROLE_TEXT.get(r, r)} (บทบาท {r}) ของรายการ")
    for role in lib["join_roles"]:
        if role in ctx["joins"] and ctx["joins"][role][1] < ctx["join_min"] and run:
            tname, rate = ctx["joins"][role]
            reasons.append(f"บทบาท {role} อยู่ในตาราง {tname} ซึ่งเชื่อมกับรายการได้เพียง {rate:.1f}% ของรหัส "
                           f"(ต่ำกว่า {ctx['join_min']:.0f}% ตาม INTAKE.JOIN_MIN_PCT) ผลที่ใช้ {role} จึงอาจไม่ครบ — ตรวจรูปแบบรหัสบัญชีของสองตาราง")
            if status == "พร้อม":
                status = "บางส่วน"
    if status == "บางส่วน" and skipped:
        reasons.append(f"รันได้ {len(run)} จาก {len(lib['checks'])} การ์ด")
    if status == "ไม่พอ" and not reasons:
        reasons.append("ไม่มีการ์ดใดรันได้กับข้อมูลนี้: " + "; ".join(skipped.values()))
    if status == "พร้อม":
        reasons.append("มีบทบาทคอลัมน์และปริมาณข้อมูลตามที่ความเสี่ยงนี้ต้องใช้")
    return {"status": status, "run": run, "skipped": skipped, "request": req, "reason": " | ".join(reasons)}


def assess_sufficiency(risk_ids: list, roles_confirmed: dict, profile: pd.DataFrame, cfg: dict,
                       tables: dict = None) -> pd.DataFrame:
    """Is the data enough for each requested risk? status: พร้อม (all checks can run) / บางส่วน (some checks skipped,
    or a joined table such as opened_at matches under cfg["INTAKE.JOIN_MIN_PCT"], or too little data for a check
    when `tables` (internal columns) is given) / ไม่พอ (no check can run, a minimum role or
    minimum data is missing, or the data type is not the one the risk needs). data_request lists what to ask for.
    `roles_confirmed` is {table: {column: role}}; `profile` is profile_columns output."""
    ctx = _intake_ctx(roles_confirmed, profile, tables, cfg)
    rows = []
    for rid in risk_ids:
        if rid not in RISK_LIBRARY:
            continue
        a = _assess_one(rid, ctx)
        rows.append((rid, a["status"], a["run"], a["skipped"], a["request"], a["reason"]))
    return pd.DataFrame(rows, columns=["risk_id", "status", "runnable_checks", "skipped_checks", "data_request",
                                       "reason"])


def plan(risk_ids: list, roles_confirmed: dict, profile: pd.DataFrame, cfg: dict, tables: dict = None) -> pd.DataFrame:
    """Run / Skip per check for the confirmed risks (replaces gate_capability for C1 runs): check_id, decision,
    reason, missing. A check runs when any requested risk can run it; a Skip reason is Thai and says what is missing.
    With `tables` it also carries gate_capability's data-dependent skips (STAT-MAD group size, baseline length)."""
    ctx = _intake_ctx(roles_confirmed, profile, tables, cfg)
    rows = {}
    for rid in risk_ids:
        if rid not in RISK_LIBRARY:
            continue
        a = _assess_one(rid, ctx)
        for cid in RISK_LIBRARY[rid]["checks"]:
            if rows.get(cid, ("",))[0] == "Run":
                continue
            if cid in a["run"] and a["status"] != "ไม่พอ":
                note = "มีบทบาทคอลัมน์ที่ต้องใช้ครบและปริมาณข้อมูลผ่านเกณฑ์"
                for role in CHECKS[cid]["optional"]:
                    if role in ctx["joins"] and ctx["joins"][role][1] < ctx["join_min"]:
                        note += f" (แต่ {role} เชื่อมกับรายการได้เพียง {ctx['joins'][role][1]:.1f}%)"
                rows[cid] = ("Run", note, "-")
            elif cid in a["skipped"]:
                rows[cid] = ("Skip", a["skipped"][cid], _check_state(cid, ctx, RISK_LIBRARY[rid])[2])
            else:
                rows[cid] = ("Skip", f"ความเสี่ยง {rid} ข้อมูลไม่พอ: {a['reason']}", "ปริมาณข้อมูลไม่พอ")
    return pd.DataFrame([(c, *v) for c, v in rows.items()], columns=["check_id", "decision", "reason", "missing"])


def suggest_risks(requested_ids: list, roles_confirmed: dict, tables: dict, cfg: dict) -> pd.DataFrame:
    """Risks in the library that the data supports (status พร้อม or บางส่วน) and that were not requested, each with
    `preview` = the number of distinct entities its checks flag, counted by actually running the checks on `tables`
    (internal columns). Risks with preview 0 are not suggested. Sorted by preview desc, then risk_id."""
    ctx = _intake_ctx(roles_confirmed, None, tables, cfg)
    ask = set(requested_ids or [])
    out = []
    for rid, lib in RISK_LIBRARY.items():
        if rid in ask:
            continue
        a = _assess_one(rid, ctx)
        if a["status"] == "ไม่พอ":
            continue
        seen, hit = set(), []
        for cid in a["run"]:
            try:
                ev = CHECKS[cid]["func"](dict(tables), cfg)
            except Exception:  # a check that cannot run on this data adds nothing to the preview
                continue
            pairs = {(str(t), str(i)) for t, i in zip(ev["entity_type"], ev["entity_id"])} if len(ev) else set()
            if pairs:
                hit.append(cid)
            seen |= pairs
        if seen:
            out.append((rid, lib["name_th"],
                        f"ข้อมูลรองรับความเสี่ยงนี้และยังไม่ได้ขอ — การ์ด {', '.join(hit)} พบ {len(seen):,} รายการ/กลุ่มที่"
                        f"สอดคล้องกับ pattern นี้เบื้องต้น (ยังไม่ใช่ข้อสรุป ควรตรวจสอบเพิ่มเติม)", len(seen)))
    df = pd.DataFrame(out, columns=["risk_id", "name_th", "why_th", "preview"])
    return df.sort_values(["preview", "risk_id"], ascending=[False, True], kind="mergesort").reset_index(drop=True)


# ---- orchestration: inspect -> confirm -> run, intake.json, trace, mapping profiles (spec 4.3, 4.6, 5) ----
class AidaError(ValueError):
    """An error for the auditor: the message is Thai and says how to fix the problem (never a raw traceback)."""


INTAKE_VERSION = 1
REGISTRY_FILE = "AIDA-14-configuration-registry.md"
CONFIRM_LINE = "ยืนยันทั้งหมด หรือแก้เฉพาะข้อ ⚠️ ❓ D แล้วเริ่มวิเคราะห์"
COL_ICON = {"ok": "✅", "conflict": "⚠️", "guess": "❓", "unknown": "⚪"}
SUFF_ICON = {"พร้อม": "✅", "บางส่วน": "🟡", "ไม่พอ": "❌"}
NO_ROLE = ("", "ไม่ใช้", "none", "None", UNKNOWN_ROLE)
MATERIALITY_TYPES = ("ก", "ข", "ไม่ระบุ")
FILTER_OPS = ("==", "!=", "in", "not in", ">", ">=", "<", "<=", "between")
DATE_ROLES = ("date", "due_date", "opened_at")
SIG_PATTERNS = ("date", "datetime", "thai_id13", "account_like", "thai_text")  # stable patterns a mapping compares
MULE_STAGE = ["MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK"]  # read the Evidence of the cards before them
# entity_type names of a Finding per data type (the checks say entity / counterparty / account)
ENTITY_LABELS = {"C": {"entity": "borrower", "account": "borrower", "counterparty": "payer"},
                 "A": {"entity": "vendor", "account": "vendor", "counterparty": "payee"}}
# Evidence of these checks whose records are all records of the key check's Evidence (same entity and period) is the
# same pattern (equal split amounts repeat and are round): it joins that Finding instead of making a second one
# (AIDA-01 one pattern, one Finding). Repeats on other records of the same entity keep their own Finding.
ABSORB_C1 = {"SPLIT-LIMIT": ("FOR-REPEAT", "FOR-ROUND")}
OUT_NAMES = {"workbook": "AIDA-workbook.xlsx", "dashboard": "AIDA-dashboard.html", "csv_dir": "network"}
EXCLUDE_WORDS = ("ตัด", "ไม่รวม", "ยกเว้น", "เอาออก", "exclude", "remove", "drop")
NO_FILTER_WORDS = ("ไม่ต้องตัด", "ไม่ต้องกรอง", "ไม่ตัดรายการ", "no filter")
RE_CODE_VALUE = re.compile(r"(?<![0-9A-Za-z])([0-9A-Za-z]{1,6})\s*=\s*([^,;/\n]+)")


def _thai_errors(fn):
    """Public API wrapper: every failure reaches the auditor as an AidaError with a Thai message."""
    @functools.wraps(fn)
    def wrap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AidaError:
            raise
        except (ValueError, KeyError) as e:
            msg = str(e.args[0]) if e.args else str(e)
            if RE_THAI_CHAR.search(msg):
                raise AidaError(msg) from None
            raise AidaError(f"{fn.__name__}: ข้อมูลหรือค่าที่ส่งเข้ามาไม่ถูกต้อง ({type(e).__name__}: {msg}) — ตรวจไฟล์ "
                            "บทบาทคอลัมน์ และ intake แล้วเรียกใหม่") from None
        except OSError as e:
            raise AidaError(f"{fn.__name__}: อ่านหรือเขียนไฟล์ไม่ได้ ({e.strerror or e}: {e.filename or ''}) — ตรวจว่า"
                            "ไฟล์มีอยู่ เปิดได้ และโฟลเดอร์ output เขียนได้ แล้วเรียกใหม่") from None
        except Exception as e:  # noqa: BLE001 - the auditor never sees a raw traceback
            raise AidaError(f"{fn.__name__}: เกิดข้อผิดพลาดภายใน engine ({type(e).__name__}: {e}) — ตรวจไฟล์และ intake "
                            "แล้วลองใหม่ หรือส่งข้อความนี้ให้ผู้ดูแล AIDA") from None
    return wrap


def _plain(o):
    """JSON-safe copy: numpy / pandas scalars -> Python, NaN -> None, tuples / sets -> lists."""
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted(_plain(v) for v in o)
    if isinstance(o, np.ndarray):
        return [_plain(v) for v in o.tolist()]
    if isinstance(o, (pd.Timestamp, datetime.datetime, datetime.date)):
        return None if pd.isna(o) else o.isoformat()
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
        return None
    if o is pd.NaT or o is None:
        return None
    return o


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def default_registry_path():
    """AIDA-14 next to the engine (Knowledge), in ../knowledge (repo) or in the working folder; None if absent."""
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.environ.get("AIDA_REGISTRY_DIR"), here, os.path.join(here, "..", "knowledge"), os.getcwd(),
              os.path.join(os.getcwd(), "knowledge")):
        if d and os.path.isfile(os.path.join(d, REGISTRY_FILE)):
            return os.path.abspath(os.path.join(d, REGISTRY_FILE))
    return None


def _load_cfg(cfg=None, registry_path=None) -> tuple:
    """(Machine Config dict, registry path or None). A cfg dict passed in wins; else AIDA-14 is read."""
    if cfg is not None:
        if not isinstance(cfg, dict):
            raise AidaError("cfg ต้องเป็น dict ของ Machine Config (AIDA-14) — หรือไม่ส่ง cfg เพื่อให้ engine อ่าน AIDA-14 เอง")
        return {k: v for k, v in cfg.items() if k != "_RUN"}, None
    path = registry_path if registry_path and os.path.isfile(str(registry_path)) else default_registry_path()
    if path is None:
        raise AidaError(f"ไม่พบไฟล์ {REGISTRY_FILE} — วางไฟล์ AIDA-14 ไว้ในโฟลเดอร์เดียวกับ aida_engine.py หรือส่ง "
                        "registry_path='<ที่อยู่ไฟล์ AIDA-14>' แล้วเรียกใหม่")
    return load_registry(path), os.path.abspath(path)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _read_csv_text(path: str) -> pd.DataFrame:
    last = None
    for enc in ("utf-8-sig", "cp874"):  # UTF-8 (with or without BOM), then Thai Windows
        try:
            return pd.read_csv(path, dtype=str, encoding=enc)
        except UnicodeDecodeError as e:
            last = e
        except pd.errors.EmptyDataError:
            raise AidaError(f"ไฟล์ '{os.path.basename(path)}' ว่าง — ส่งไฟล์ที่มีหัวคอลัมน์และข้อมูล") from None
    raise AidaError(f"อ่านไฟล์ '{os.path.basename(path)}' ไม่ได้ (encoding ไม่ใช่ UTF-8 หรือ TIS-620/cp874: {last}) — "
                    "บันทึกไฟล์เป็น CSV UTF-8 แล้วส่งใหม่")


def _file_items(files) -> list:
    if files is None:
        raise AidaError("ยังไม่ได้ส่งไฟล์ข้อมูล — ส่ง files เป็น dict {ชื่อตาราง: ที่อยู่ไฟล์} หรือ list ของที่อยู่ไฟล์")
    if isinstance(files, (str, os.PathLike)):
        files = [files]
    if isinstance(files, dict):
        return [(str(k), str(v)) for k, v in files.items()]
    return [(os.path.splitext(os.path.basename(str(p)))[0], str(p)) for p in files]


def _read_files(files) -> tuple:
    """({table: text DataFrame}, {table: {path, file, sheet, sha256}}). Everything is read as text (dtype=str) so
    codes such as leading zeros survive; XLSX gives one table per sheet named <stem>.<sheet>."""
    frames, meta = {}, {}
    for name, path in _file_items(files):
        if not os.path.isfile(path):
            raise AidaError(f"ไม่พบไฟล์ '{path}' — ตรวจชื่อและที่อยู่ไฟล์ (หรือแนบไฟล์ใหม่) แล้วเรียกอีกครั้ง")
        sha, ext = _sha256(path), os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xlsm"):
            try:
                sheets = pd.read_excel(path, sheet_name=None, dtype=str, engine="openpyxl")
            except Exception as e:  # noqa: BLE001
                raise AidaError(f"เปิดไฟล์ Excel '{os.path.basename(path)}' ไม่ได้ ({e}) — บันทึกเป็น .xlsx ใหม่หรือส่งเป็น CSV") from None
            parts = [(f"{name}.{sh}", sh, df) for sh, df in sheets.items()]
        elif ext in (".csv", ".txt", ""):
            parts = [(name, None, _read_csv_text(path))]
        else:
            raise AidaError(f"ไม่รองรับไฟล์ชนิด '{ext}' ({os.path.basename(path)}) — ส่งเป็น .csv หรือ .xlsx")
        for tname, sheet, df in parts:
            if tname in frames:
                raise AidaError(f"มีตารางชื่อ '{tname}' ซ้ำกัน — ตั้งชื่อตารางให้ไม่ซ้ำ (ส่ง files เป็น dict {{ชื่อ: ไฟล์}})")
            df = df.copy()
            df.columns = [str(c).strip() for c in df.columns]
            frames[tname] = df
            meta[tname] = {"path": os.path.abspath(path), "file": os.path.basename(path), "sheet": sheet, "sha256": sha,
                           "key": name}
    if not frames:
        raise AidaError("ไม่มีตารางข้อมูลในไฟล์ที่ส่งมา — ตรวจว่าไฟล์มีข้อมูลอย่างน้อย 1 ตาราง")
    return frames, meta


def _data_ref(meta: dict) -> str:
    return "; ".join(f"chat:{m['file']}#{t}|sha256:{m['sha256']}" for t, m in meta.items())


def _input_sha(meta: dict) -> str:
    shas = sorted({(m["file"], m["sha256"]) for m in meta.values()})
    return shas[0][1] if len(shas) == 1 else "; ".join(f"{f}:{s}" for f, s in shas)


def _role_list(r) -> list:
    if r is None:
        return []
    return [str(x).strip() for x in (r if isinstance(r, (list, tuple)) else [r]) if str(x).strip() not in NO_ROLE]


def _certified(roles: list) -> list:
    return [r for r in roles if not r.startswith("custom:")]


def _split_roles(roles: dict) -> tuple:
    """({table: {column: primary role}}, [(table, column, extra custom role)]) from intake roles (a role or a list)."""
    primary, extra = {}, []
    for t, rmap in roles.items():
        primary[t] = {}
        for c, r in rmap.items():
            lst = _role_list(r)
            if not lst:
                continue
            cert = _certified(lst)
            main = cert[0] if cert else lst[0]
            primary[t][c] = main
            extra += [(t, c, x) for x in lst if x != main]
    return {t: m for t, m in primary.items() if m}, extra


def _internal(frames: dict, roles: dict) -> tuple:
    """Role adapter for intake roles: (internal tables, tx table name). Unmapped columns are dropped (to_internal);
    a custom role confirmed next to a certified one on the same column is added as its own column."""
    primary, extra = _split_roles(roles)
    tables = to_internal(frames, primary)
    tx_name = _roles_by_table(primary)[0]
    for t, c, r in extra:
        target = "transactions" if t == tx_name else "accounts"
        if target in tables:
            tables[target][r] = frames[t][c]
    return tables, tx_name


def _prep_internal(tables: dict, cfg: dict) -> dict:
    """B1 PREP-MAP on the internal frames (dates incl. พ.ศ. / dd/mm / Thai months, amounts, ids), plus due_date and
    limit with the same rules."""
    t = prep_map({k: v for k, v in tables.items() if k in ("transactions", "accounts")}, None, cfg)
    tx = t["transactions"]
    if "due_date" in tx.columns:
        tx["due_date"], _ = to_naive_ts(tx["due_date"])
    if "limit" in tx.columns:
        lim = tx["limit"].map(lambda x: x.replace(",", "").replace("฿", "").strip() if isinstance(x, str) else x)
        tx["limit"] = pd.to_numeric(lim, errors="coerce").astype(float)
    if "contract" in tx.columns or "to_acct" not in tx.columns:
        t["_prep"]["excluded_self"] = 0  # base_tx keeps borrower == payer rows: normal for loan / AP data
    return t


def _find_columns(frames: dict, name: str) -> list:
    """[(table, column)] a filter / answer column name refers to: "table.column" or a column name."""
    name = str(name)
    exact = [(t, name[len(t) + 1:]) for t in frames if name.startswith(t + ".") and name[len(t) + 1:] in frames[t].columns]
    if exact:
        return exact[:1]
    return [(t, name) for t, df in frames.items() if name in df.columns]


def _num_value(v):
    """A number from an int / float / text such as "1,000", "80%"; None when it is not one."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float, np.integer, np.floating)):
        return v.item() if isinstance(v, np.generic) else v
    if isinstance(v, str):
        s = v.replace(",", "").replace("฿", "").strip()
        pct = s.endswith("%")
        try:
            x = float(s.rstrip("%"))
        except ValueError:
            return None
        x = x / 100 if pct else x
        return int(x) if x.is_integer() and not pct and "." not in s else x
    return None


def _filter_mask(s: pd.Series, op: str, value, as_date: bool) -> pd.Series:
    txt = s.where(s.notna(), "").astype(str).str.strip()
    if op in ("==", "!="):
        m = txt == str(value).strip()
        return m if op == "==" else ~m
    if op in ("in", "not in"):
        m = txt.isin([str(v).strip() for v in value])
        return m if op == "in" else ~m
    if as_date:
        col = to_naive_ts(s)[0]
        vals = to_naive_ts(pd.Series(value if isinstance(value, list) else [value], dtype=object))[0].tolist()
    else:
        col = pd.to_numeric(txt.str.replace(",", "", regex=False), errors="coerce")
        vals = [_num_value(v) for v in (value if isinstance(value, list) else [value])]
    if op == "between":
        lo, hi = vals
        if as_date and isinstance(hi, pd.Timestamp) and hi == hi.normalize():
            hi = hi + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)  # a date as the upper bound takes the whole day
        return (col >= lo) & (col <= hi)
    v = vals[0]
    return {">": col > v, ">=": col >= v, "<": col < v, "<=": col <= v}[op]


def _is_date_col(table: str, col: str, roles: dict, profile_rows: list) -> bool:
    if set(_role_list(roles.get(table, {}).get(col))) & set(DATE_ROLES):
        return True
    return any(p["table"] == table and p["column"] == col and p["dtype_guess"] == "date" for p in profile_rows)


def _check_filters(filters, frames: dict, roles: dict, profile_rows: list) -> list:
    out = []
    for i, f in enumerate(filters or [], 1):
        if not isinstance(f, dict) or not {"column", "op", "value"} <= set(f):
            raise AidaError(f"ตัวกรองข้อ {i} ต้องเป็น {{'column': ชื่อคอลัมน์, 'op': เครื่องหมาย, 'value': ค่า}} — แก้แล้วยืนยันอีกครั้ง")
        col, op, val = f["column"], str(f["op"]).strip(), f["value"]
        if op == "=":
            op = "=="
        if op not in FILTER_OPS:
            raise AidaError(f"ตัวกรองข้อ {i}: ไม่รู้จักเครื่องหมาย '{op}' — ใช้ได้เฉพาะ {', '.join(FILTER_OPS)}")
        if not _find_columns(frames, col):
            raise AidaError(f"ตัวกรองข้อ {i}: ไม่พบคอลัมน์ '{col}' ในไฟล์ — ระบุชื่อคอลัมน์ตามไฟล์ (หรือ ตาราง.คอลัมน์)")
        if op == "between" and not (isinstance(val, (list, tuple)) and len(val) == 2):
            raise AidaError(f"ตัวกรองข้อ {i}: between ต้องมีค่า [ต่ำสุด, สูงสุด] 2 ค่า เช่น ['2026-01-01', '2026-08-31']")
        if op in ("in", "not in") and not isinstance(val, (list, tuple)):
            raise AidaError(f"ตัวกรองข้อ {i}: {op} ต้องมีค่าเป็นรายการ เช่น ['C', 'X']")
        if op in (">", ">=", "<", "<=", "between"):
            t, c = _find_columns(frames, col)[0]
            vals = list(val) if isinstance(val, (list, tuple)) else [val]
            if _is_date_col(t, c, roles, profile_rows):
                bad = [v for v in vals if pd.isna(to_naive_ts(pd.Series([v], dtype=object))[0].iloc[0])]
            else:
                bad = [v for v in vals if _num_value(v) is None]
            if bad:
                raise AidaError(f"ตัวกรองข้อ {i}: ค่า {bad} ของคอลัมน์ '{col}' เทียบไม่ได้ (ไม่ใช่วันที่หรือตัวเลข) — แก้ค่าแล้วยืนยันอีกครั้ง")
        out.append({"column": col, "op": op, "value": list(val) if isinstance(val, tuple) else val})
    return out


def _apply_filters(frames: dict, filters: list, roles: dict, profile_rows: list) -> tuple:
    """(filtered frames, [Thai log line per filter]) — the frames are copies, the files are never changed."""
    frames, log = dict(frames), []
    for f in filters or []:
        for t, c in _find_columns(frames, f["column"]):
            df = frames[t]
            keep = _filter_mask(df[c], f["op"], f["value"], _is_date_col(t, c, roles, profile_rows))
            frames[t] = df[keep.fillna(False).astype(bool)]
            log.append(f"ตัวกรอง {t}.{c} {f['op']} {f['value']}: ตัดออก {int((~keep.fillna(False).astype(bool)).sum()):,} "
                       f"จาก {len(df):,} แถว เหลือ {len(frames[t]):,} แถว")
    return frames, log


def _code_values(desc, prow) -> dict:
    """{code: meaning} written in a column description ("P = บันทึกแล้ว, C = ยกเลิก") for codes found in the column."""
    if not desc:
        return {}
    seen = {str(v) for v, _ in prow.get("top5", [])} | {str(v) for v in prow.get("samples", [])}
    return {m[1]: m[2].strip() for m in RE_CODE_VALUE.finditer(str(desc)) if m[1] in seen and m[2].strip()}


def _propose_filters(conditions: list, frames: dict) -> list:
    """Each condition -> {condition, filter or None, rows_removed, note}. Only "<column> = <value>" is converted
    (with ตัด / ไม่รวม / exclude -> !=); anything else is left for the auditor to state."""
    out = []
    for text in conditions or []:
        low, item = str(text).lower(), {"condition": text, "filter": None, "rows_removed": None, "note": ""}
        if any(w in low for w in NO_FILTER_WORDS):
            item["note"] = "ไม่ต้องใช้ตัวกรอง"
            out.append(item)
            continue
        for t, df in frames.items():
            for c in df.columns:
                m = re.search(rf"(?<![0-9A-Za-z_ก-๙]){re.escape(c)}\s*(==|=|!=|≠|<>)\s*['\"]?([^\s'\"(),]+)", str(text))
                if not m or item["filter"] is not None:
                    continue
                vals = set(df[c].dropna().astype(str).str.strip())
                if m[2] not in vals:
                    continue
                op = "!=" if m[1] in ("!=", "≠", "<>") or any(w in low for w in EXCLUDE_WORDS) else "=="
                hit = df[c].where(df[c].notna(), "").astype(str).str.strip() == m[2]
                item["filter"] = {"column": c, "op": op, "value": m[2]}
                item["rows_removed"] = int(hit.sum() if op == "!=" else (~hit).sum())
                item["table"] = t
        if item["filter"] is None and not item["note"]:
            item["note"] = "ยังแปลงเป็นตัวกรองไม่ได้ — ขอให้ระบุคอลัมน์และค่า (เช่น คอลัมน์วันที่ between [วันเริ่ม, วันสิ้นสุด]) หรือยืนยันว่าไม่ต้องกรอง"
        out.append(item)
    return out


def _signature(profile_rows: list) -> dict:
    return {f"{p['table']}.{p['column']}": {"dtype": p["dtype_guess"],
                                            "patterns": sorted(x for x in p["patterns"] if x in SIG_PATTERNS)}
            for p in profile_rows}


def _sig_text(s: dict) -> str:
    return s["dtype"] + (f" ({', '.join(s['patterns'])})" if s["patterns"] else "")


def _table_pairs(old_tables: list, new_tables: list) -> dict:
    """mapping table -> new table: same name, else the only unmatched table on each side."""
    pairs = {t: t for t in old_tables if t in new_tables}
    rest_old = [t for t in old_tables if t not in pairs]
    rest_new = [t for t in new_tables if t not in pairs.values()]
    if len(rest_old) == 1 and len(rest_new) == 1:
        pairs[rest_old[0]] = rest_new[0]
    return pairs


def _mapping_changes(m: dict, profile_rows: list) -> tuple:
    """(changes {added, removed, changed_pattern} as "table.column", mapping table -> new table)."""
    new_sig = _signature(profile_rows)
    old_sig = m.get("signature", {})
    old_tables = sorted({k.rsplit(".", 1)[0] for k in old_sig} | set(m.get("roles", {})))
    new_tables = sorted({p["table"] for p in profile_rows})
    pairs = _table_pairs(old_tables, new_tables)
    moved = {}
    for k, v in old_sig.items():
        t, c = k.rsplit(".", 1)
        moved[f"{pairs.get(t, t)}.{c}"] = v
    added = sorted(k for k in new_sig if k not in moved)
    removed = sorted(k for k in moved if k not in new_sig)
    changed = sorted(k for k in new_sig if k in moved and moved[k] != new_sig[k])
    return {"added": added, "removed": removed, "changed_pattern": changed}, pairs, moved


def _risk_order(ids: list) -> list:
    seen = []
    for r in ids:
        if r and r not in seen:
            seen.append(r)
    return seen


def _profile_records(profile: pd.DataFrame) -> list:
    return _plain(profile.to_dict(orient="records"))


def _col_status(table, col, role, source, conflicts) -> str:
    if (table, col) in conflicts:
        return "conflict"
    if role == UNKNOWN_ROLE or not role:
        return "unknown"
    if source in ("brief", "mapping", "auditor"):
        return "ok"
    return "guess"


@_thai_errors
def inspect(files, brief: dict = None, mapping=None, cfg: dict = None, registry_path: str = None) -> dict:
    """Everything in spec 4.3 step 2: read files as text (CSV / every XLSX sheet), sha256 and data_ref, B1 date and
    amount parsing, profile, suggest_roles, check_descriptions, match_concerns, assess_sufficiency, suggest_risks
    and plan -> {"intake": draft, "review_th": Thai Intake Review A-E, "changes": mapping changes or None}.
    `brief` = {context, columns {col: meaning}, conditions [..], concerns [..], materiality}; `mapping` = a mapping
    profile (path or dict from save_mapping): its roles, meanings, filters and org values are reused and only the
    columns that were added, removed or changed pattern are asked about."""
    base_cfg, reg_path = _load_cfg(cfg, registry_path)
    brief = dict(brief or {})
    m = load_mapping(mapping) if mapping is not None else None
    frames, meta = _read_files(files)
    profile = profile_columns(frames)
    prows = _profile_records(profile)
    bcols = brief.get("columns") or {}
    preset = detect_dataset_type(profile)
    sug = suggest_roles(profile, bcols, preset, base_cfg)
    conflicts = check_descriptions(profile, bcols)
    cset = {(c["table"], c["column"]) for c in conflicts}
    changes, roles, cols_meaning, codes = None, {}, {}, {}
    suggestions = []
    if m is not None:
        changes, pairs, old_sig = _mapping_changes(m, prows)
        new_sig = _signature(prows)
        for t_old, rmap in m.get("roles", {}).items():
            t = pairs.get(t_old, t_old)
            for c, r in rmap.items():
                if f"{t}.{c}" in new_sig:
                    roles.setdefault(t, {})[c] = r
        for t_old, cm in m.get("columns", {}).items():
            t = pairs.get(t_old, t_old)
            cols_meaning[t] = {c: v for c, v in cm.items() if f"{t}.{c}" in new_sig}
        for k, v in m.get("code_values", {}).items():
            t_old, c = k.rsplit(".", 1)
            if f"{pairs.get(t_old, t_old)}.{c}" in new_sig:
                codes[f"{pairs.get(t_old, t_old)}.{c}"] = v
    for _, s in sug.iterrows():
        t, c, k = s["table"], s["column"], f"{s['table']}.{s['column']}"
        if m is not None and k not in changes["added"]:
            r = roles.get(t, {}).get(c)
            st = "conflict" if k in changes["changed_pattern"] else ("ok" if r else "unchanged")
            reason = (f"รูปแบบข้อมูลเปลี่ยนจาก {_sig_text(old_sig[k])} เป็น {_sig_text(_signature(prows)[k])} — "
                      "ช่วยยืนยันว่ายังเป็นบทบาทเดิม" if st == "conflict" else "ใช้ค่าเดิมจาก mapping profile")
            suggestions.append({"table": t, "column": c, "role": r if r else UNKNOWN_ROLE, "confidence": 1.0,
                                "level": LEVEL_HIGH, "reason": reason, "source": "mapping", "status": st})
            continue
        role, src = s["role"], s["source"]
        taken = {x for cc, x in roles.get(t, {}).items() if cc != c for x in _role_list(x)}
        if m is not None and role in taken:
            role, src = UNKNOWN_ROLE, "profile"
            s = {**s, "reason": f"บทบาท {s['role']} ใช้กับคอลัมน์อื่นตาม mapping แล้ว — ขอให้ระบุความหมายของคอลัมน์ใหม่นี้"}
        if role != UNKNOWN_ROLE:
            roles.setdefault(t, {})[c] = role
        suggestions.append({"table": t, "column": c, "role": role, "confidence": float(s["confidence"]),
                            "level": s["level"], "reason": s["reason"], "source": src,
                            "status": _col_status(t, c, role, src, cset)})
    for p in prows:  # meanings and code values from the brief (the mapping's are kept for unchanged columns)
        said = _brief_text(bcols, p["table"], p["column"])
        if said is not None:
            cols_meaning.setdefault(p["table"], {})[p["column"]] = said
            cv = _code_values(said, p)
            if cv:
                codes[f"{p['table']}.{p['column']}"] = cv
    matched = match_concerns(brief.get("concerns") or [])
    requested = _risk_order([x["risk_id"] for x in matched])
    if not matched and m is not None:
        requested = _risk_order(m.get("risks", []))
    exploratory = [x["concern"] for x in matched if x["risk_id"] is None]
    proposals = _propose_filters(brief.get("conditions") or [], frames)
    filters = list(m.get("filters", [])) if m is not None else [p["filter"] for p in proposals if p["filter"]]
    if m is not None:
        filters = [f for f in filters if _find_columns(frames, f["column"])]
    org = dict(m.get("org_values", {})) if m is not None else {}
    notes, tables, suff, sugg, pl, prep, status = [], None, None, None, None, {}, None
    primary, _ = _split_roles(roles)
    run_cfg = {**base_cfg, **_merge_org(org, base_cfg), "_RUN": {"run_id": "INSPECT", "data_ref": _data_ref(meta)}}
    try:
        tables, _ = _internal(frames, roles)
        tables = _prep_internal(tables, run_cfg)
        prep = tables["_prep"]
        status = prof_profile(tables, run_cfg)[1]
    except ValueError as e:
        notes.append(f"ยังแปลงข้อมูลตามบทบาทที่เสนอไม่ได้: {e}")
        tables = None
    dtype = _type_from_roles(set(_roles_by_table(primary)[1]) if primary else set(), profile)
    suff = assess_sufficiency(requested, primary, profile, run_cfg, tables)
    pl = plan(requested, primary, profile, run_cfg, tables)
    if tables is not None:
        sugg = suggest_risks(requested, primary, {k: v for k, v in tables.items() if k != "_prep"}, run_cfg)
    else:
        sugg = pd.DataFrame(columns=["risk_id", "name_th", "why_th", "preview"])
    it = {
        "intake_version": INTAKE_VERSION, "status": "draft", "created_at": _now(), "engine_version": __version__,
        "registry_version": str(base_cfg.get("REGISTRY.VERSION", REGISTRY_VERSION)), "registry_path": reg_path,
        "cfg": base_cfg if cfg is not None else None,
        "files": meta, "data_ref": _data_ref(meta), "input_sha256": _input_sha(meta), "brief": _plain(brief),
        "dataset_type": dtype, "roles": roles, "role_suggestions": _plain(suggestions), "columns": cols_meaning,
        "code_values": codes, "filters": filters, "filter_proposals": _plain(proposals), "org_values": org,
        "risks": {"requested": requested, "added": [], "exploratory": exploratory, "concerns": _plain(matched)},
        "materiality": dict(brief.get("materiality") or {"type": "ไม่ระบุ"}), "reviewer": None,
        "description_conflicts": _plain(conflicts), "sufficiency": _plain(suff.to_dict(orient="records")),
        "suggested_risks": _plain(sugg.to_dict(orient="records")), "plan": _plain(pl.to_dict(orient="records")),
        "profile": prows, "signature": _signature(prows), "prep": _plain({k: v for k, v in prep.items()
                                                                          if k != "opened_at_info"}),
        "profile_status": status, "notes": notes, "changes": changes,
        "mapping": {"confirmed_by": m.get("confirmed_by"), "confirmed_at": m.get("confirmed_at")} if m else None}
    it = _plain(it)
    return {"intake": it, "review_th": _review_text(it), "changes": changes}


def _merge_org(org: dict, cfg: dict) -> dict:
    """Org values as cfg entries: a dict value is merged into the standard dict (only the keys given change)."""
    out = {}
    for k, v in (org or {}).items():
        out[k] = {**cfg[k], **v} if isinstance(cfg.get(k), dict) and isinstance(v, dict) else v
    return out


def _check_org_values(org, cfg: dict) -> dict:
    if not org:
        return {}
    if not isinstance(org, dict):
        raise AidaError("org_values ต้องเป็น {ชื่อ key ตาม AIDA-14: ค่า} เช่น {'DUP.WINDOW_DAYS': 5}")
    examples = ", ".join(k for k in ("DUP.WINDOW_DAYS", "SPLIT.MIN_TX", "CONC.SINGLE_ENTITY_SHARE") if k in cfg)
    out = {}
    for k, v in org.items():
        if k not in cfg or k.startswith("_") or k == "REGISTRY.VERSION":
            raise AidaError(f"ไม่รู้จักค่าเกณฑ์ '{k}' ใน Machine Config ของ AIDA-14 — ใช้ชื่อ key ตาม AIDA-14 เท่านั้น "
                            f"(เช่น {examples}) แก้ชื่อแล้วยืนยันอีกครั้ง")
        std = cfg[k]
        bad = AidaError(f"ค่าขององค์กร '{k}' = {v!r} ใช้ไม่ได้: ค่ามาตรฐาน AIDA-14 คือ {std!r} — ระบุค่าชนิดเดียวกัน "
                        f"(ตัวเลข / ข้อความ / dict ที่มี key เดียวกัน) แล้วยืนยันอีกครั้ง")
        if isinstance(std, bool):
            if not isinstance(v, bool):
                raise bad
        elif isinstance(std, (int, float)):
            v = _num_value(v)
            if v is None:
                raise bad
        elif isinstance(std, dict):
            if not isinstance(v, dict) or not set(v) <= set(std):
                raise bad
            v = {kk: (_num_value(vv) if isinstance(std[kk], (int, float)) and not isinstance(std[kk], bool) else vv)
                 for kk, vv in v.items()}
            if any(x is None for x in v.values()):
                raise bad
        elif isinstance(std, str):
            if not isinstance(v, str):
                raise bad
        elif isinstance(std, list) and not isinstance(v, list):
            raise bad
        out[k] = v
    return out


def _answer_roles(answer, frames_cols: dict) -> dict:
    """{table: {column: role list}} from a nested {table: {column: role}} or flat {column / table.column: role}."""
    out = {}
    if not answer:
        return out
    if not isinstance(answer, dict):
        raise AidaError("roles ต้องเป็น {คอลัมน์: บทบาท} หรือ {ตาราง: {คอลัมน์: บทบาท}}")
    nested = all(isinstance(v, dict) for v in answer.values())
    items = []
    if nested:
        for t, rmap in answer.items():
            if t not in frames_cols:
                raise AidaError(f"ไม่พบตาราง '{t}' ในไฟล์ที่ inspect — ใช้ชื่อตาราง {', '.join(frames_cols)}")
            items += [(t, c, r) for c, r in rmap.items()]
    else:
        for name, r in answer.items():
            hits = _find_columns({t: pd.DataFrame(columns=cs) for t, cs in frames_cols.items()}, name)
            if not hits:
                raise AidaError(f"ไม่พบคอลัมน์ '{name}' ในไฟล์ — ใช้ชื่อคอลัมน์ตามไฟล์ (หรือ ตาราง.คอลัมน์) แล้วยืนยันอีกครั้ง")
            items += [(t, c, r) for t, c in hits]
    for t, c, r in items:
        if c not in frames_cols[t]:
            raise AidaError(f"ไม่พบคอลัมน์ '{c}' ในตาราง '{t}' — ใช้ชื่อคอลัมน์ตามไฟล์ แล้วยืนยันอีกครั้ง")
        lst = _role_list(r)
        for x in lst:
            if x not in ROLE_TO_INTERNAL and not (x.startswith("custom:") and len(x) > 7):
                raise AidaError(f"ไม่รู้จักบทบาท '{x}' ของคอลัมน์ '{c}' — ใช้ได้เฉพาะ {', '.join(ROLES)} หรือ "
                                "custom:<ชื่อ> หรือ 'ไม่ใช้'")
        cert = _certified(lst)
        if len(cert) > 1:
            raise AidaError(f"คอลัมน์ '{c}' ในตาราง '{t}' ถูกกำหนดหลายบทบาทรับรอง ({', '.join(cert)}) — หนึ่งคอลัมน์มีบทบาท"
                            "รับรองได้บทบาทเดียว (เพิ่ม custom:<ชื่อ> ได้) เลือกบทบาทเดียวแล้วยืนยันอีกครั้ง")
        if len(set(lst)) != len(lst):
            raise AidaError(f"คอลัมน์ '{c}' มีบทบาทซ้ำกันในรายการ ({', '.join(lst)}) — ระบุแต่ละบทบาทครั้งเดียว")
        out.setdefault(t, {})[c] = lst
    return out


def _dup_targets(t: str, rmap: dict) -> None:
    by = {}
    for c, r in rmap.items():
        for x in _role_list(r):
            by.setdefault(x, []).append(c)
    for role, cols in by.items():
        if len(cols) > 1:
            raise AidaError(f"บทบาท {role} ถูกกำหนดให้หลายคอลัมน์ในตาราง '{t}' ({', '.join(cols)}) — แต่ละบทบาทใช้ได้"
                            f"คอลัมน์เดียวต่อตาราง: เลือกคอลัมน์เดียวเป็น {role} แล้วกำหนดคอลัมน์อื่นเป็นบทบาทอื่น "
                            "หรือ custom:<ชื่อ> หรือ 'ไม่ใช้' แล้วยืนยันอีกครั้ง")


def _final_roles(draft: dict, explicit: dict) -> dict:
    """Draft roles overridden by the auditor's answers. Answers are checked for duplicate role targets first; a role
    the auditor gives a column is taken away from the column the draft had proposed for it."""
    for t, rmap in explicit.items():
        _dup_targets(t, rmap)
    roles = {t: {c: (list(r) if isinstance(r, list) else r) for c, r in rmap.items()} for t, rmap in draft.items()}
    for t, rmap in explicit.items():
        cur = roles.setdefault(t, {})
        for c, lst in rmap.items():
            for other in [o for o in cur if o != c and o not in rmap and set(_role_list(cur[o])) & set(lst)]:
                del cur[other]
            if lst:
                cur[c] = lst[0] if len(lst) == 1 else lst
            else:
                cur.pop(c, None)
    roles = {t: rmap for t, rmap in roles.items() if rmap}
    for t, rmap in roles.items():
        _dup_targets(t, rmap)
    tx_name, tx_roles, _ = _roles_by_table(_split_roles(roles)[0])
    if tx_name is None or "record_id" not in tx_roles:
        raise AidaError("ยังไม่ได้กำหนดบทบาท record_id (รหัสรายการ) ให้คอลัมน์ในตารางธุรกรรม — record_id บังคับ "
                        "เพื่ออ้างอิงรายการต้นทาง: กำหนดคอลัมน์รหัสรายการเป็น record_id แล้วยืนยันอีกครั้ง")
    return roles


def _check_materiality(m) -> dict:
    if not m:
        return {"type": "ไม่ระบุ", "amount": None, "basis": ""}
    if not isinstance(m, dict):
        raise AidaError("Materiality ต้องเป็น {'type': 'ก' | 'ข' | 'ไม่ระบุ', 'amount': ฐานเป็นตัวเลข, 'basis': คำอธิบาย}")
    t = str(m.get("type", "ไม่ระบุ")).replace("แบบ", "").strip().rstrip(".").strip() or "ไม่ระบุ"
    if t not in MATERIALITY_TYPES:
        raise AidaError(f"Materiality type '{m.get('type')}' ใช้ไม่ได้ — เลือก ก. / ข. / ไม่ระบุ แล้วยืนยันอีกครั้ง")
    if t == "ไม่ระบุ":
        return {"type": t, "amount": None, "basis": str(m.get("basis", "") or "")}
    amt = _num_value(m.get("amount"))
    if amt is None or amt <= 0:
        raise AidaError(f"Materiality แบบ {t}. ต้องมี amount (ฐาน Materiality เป็นจำนวนเงินมากกว่า 0) — ระบุ amount "
                        "หรือเลือก 'ไม่ระบุ' แล้วยืนยันอีกครั้ง")
    return {"type": t, "amount": amt, "basis": str(m.get("basis", "") or "")}


@_thai_errors
def confirm(intake: dict, answers: dict = None, path: str = "intake.json", cfg: dict = None) -> dict:
    """Apply the auditor's answers to a draft intake and write intake.json (self-sufficient for run()).
    answers: roles {col: role} or {table: {col: role}} (a role may be a list: one certified role + custom roles;
    'ไม่ใช้' removes), filters [{column, op, value}], org_values {AIDA-14 KEY: value}, add_risks [risk_id],
    materiality {type ก|ข|ไม่ระบุ, amount, basis}, reviewer, columns {col: meaning}, code_values {table.col: {..}}.
    Duplicate role targets, unknown roles / columns / keys / risk ids are rejected with a Thai message."""
    if not isinstance(intake, dict) or "files" not in intake or "roles" not in intake:
        raise AidaError("intake ไม่ครบ — ส่ง intake ที่ได้จาก inspect(...)['intake']")
    a = dict(answers or {})
    known = {"roles", "filters", "org_values", "add_risks", "materiality", "reviewer", "columns", "code_values"}
    extra = sorted(set(a) - known)
    if extra:
        raise AidaError(f"ไม่รู้จักคำตอบ {', '.join(extra)} — ใช้ได้เฉพาะ {', '.join(sorted(known))}")
    base_cfg = _load_cfg(cfg if cfg is not None else intake.get("cfg"), intake.get("registry_path"))[0]
    frames_cols = {}
    for p in intake.get("profile", []):
        frames_cols.setdefault(p["table"], []).append(p["column"])
    roles = _final_roles(intake["roles"], _answer_roles(a.get("roles"), frames_cols))
    fake = {t: pd.DataFrame(columns=cs) for t, cs in frames_cols.items()}
    filters = _check_filters(a["filters"] if "filters" in a else intake.get("filters", []), fake, roles,
                             intake.get("profile", []))
    org = _check_org_values({**intake.get("org_values", {}), **(a.get("org_values") or {})}, base_cfg)
    add = _risk_order(list(a.get("add_risks") or []))
    for r in add:
        if r not in RISK_LIBRARY:
            raise AidaError(f"ไม่รู้จักรหัสความเสี่ยง '{r}' ใน Risk Library — เลือกจาก {', '.join(RISK_LIBRARY)} "
                            "(ความเสี่ยงที่ไม่มีในคลังใช้โหมดสำรวจ) แล้วยืนยันอีกครั้ง")
    mat = _check_materiality(a.get("materiality") if "materiality" in a else intake.get("materiality"))
    cols = {t: dict(v) for t, v in intake.get("columns", {}).items()}
    for k, v in (a.get("columns") or {}).items():
        for t, c in _find_columns(fake, k) or []:
            cols.setdefault(t, {})[c] = v
    codes = {**intake.get("code_values", {}), **(a.get("code_values") or {})}
    it = dict(intake)
    requested = list(intake["risks"]["requested"])
    it.update(status="confirmed", confirmed_at=_now(), roles=roles, filters=filters, org_values=org,
              materiality=mat, reviewer=str(a.get("reviewer") or intake.get("reviewer") or "ไม่ระบุ"),
              columns=cols, code_values=codes,
              risks={**intake["risks"], "added": [r for r in add if r not in requested]},
              registry_version=str(base_cfg.get("REGISTRY.VERSION", REGISTRY_VERSION)), engine_version=__version__)
    it = _plain(it)
    it["intake_path"] = os.path.abspath(path)  # explore_log.json (exploratory mode) is kept next to intake.json
    folder = os.path.dirname(it["intake_path"])
    os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(it, fh, ensure_ascii=False, indent=2)
    return it


def _load_intake(intake) -> dict:
    if isinstance(intake, (str, os.PathLike)):
        p = str(intake)
        if not os.path.isfile(p):
            raise AidaError(f"ไม่พบไฟล์ intake '{p}' — เรียก confirm(...) เพื่อสร้าง intake.json หรือระบุที่อยู่ไฟล์ให้ถูก")
        try:
            with open(p, encoding="utf-8") as fh:
                intake = json.load(fh)
        except json.JSONDecodeError as e:
            raise AidaError(f"ไฟล์ intake '{p}' ไม่ใช่ JSON ที่ถูกต้อง ({e.msg}) — สร้างใหม่ด้วย confirm(...)") from None
        if isinstance(intake, dict):
            intake["intake_path"] = os.path.abspath(p)
    if not isinstance(intake, dict) or intake.get("status") != "confirmed":
        raise AidaError("intake ยังไม่ได้ยืนยัน — เรียก confirm(intake, answers) ก่อน แล้วจึงเรียก run / trace")
    return intake


def _prepare(files, it: dict, cfg: dict) -> dict:
    """Read the files again, compare sha256 with the intake, apply filters, role adapter and B1 parsing."""
    if files is None:
        files = {}
        for t, m in it["files"].items():
            files.setdefault(m.get("key") or (t if not m.get("sheet") else t[:-len(m["sheet"]) - 1]), m["path"])
    frames, meta = _read_files(files)
    warnings, events = [], []
    for t, m in it["files"].items():
        if t not in meta:
            if t in it["roles"]:
                raise AidaError(f"ไม่พบตาราง '{t}' ในไฟล์ที่ส่งมา — ส่งไฟล์ชุดเดียวกับตอน inspect/confirm "
                                f"({m['file']}) หรือ inspect/confirm ใหม่")
            continue
        if meta[t]["sha256"] != m["sha256"]:
            warnings.append(f"ไฟล์ของตาราง {t} ({meta[t]['file']}) เปลี่ยนไปจากตอนยืนยัน Intake (sha256 ไม่ตรง: เดิม "
                            f"{m['sha256'][:12]}… ตอนนี้ {meta[t]['sha256'][:12]}…) — ผลอาจต่างจาก Intake Review; "
                            "ถ้าตั้งใจใช้ไฟล์ใหม่ให้เรียก inspect และ confirm ใหม่")
    events += [{"stage": 2, "status": "REVIEW", "detail": w} for w in warnings]
    events.append({"stage": 2, "status": "OK", "detail": f"อ่านไฟล์ {len(meta):,} ตาราง: " + "; ".join(
        f"{t} {len(frames[t]):,} แถว (sha256 {m['sha256'][:12]}…)" for t, m in meta.items())})
    frames, flog = _apply_filters(frames, it.get("filters", []), it["roles"], it.get("profile", []))
    events += [{"stage": 2, "status": "OK", "detail": x} for x in flog]
    tables, tx_name = _internal(frames, it["roles"])
    tables = _prep_internal(tables, cfg)
    return {"frames": frames, "meta": meta, "tables": tables, "tx_name": tx_name, "warnings": warnings,
            "events": events, "filter_log": flog}


def _run_cfg(it: dict, base_cfg: dict, meta: dict, extra: str = "") -> tuple:
    try:
        _check_org_values(it.get("org_values", {}), base_cfg)  # intake.json may be edited by hand or older than AIDA-14
    except AidaError as e:
        raise AidaError(f"intake: {e} (ค่าขององค์กรใน intake.json ต้องตรงกับ AIDA-14 ที่ใช้ตอนนี้ — แก้ด้วย confirm(...) ใหม่)") from None
    org = _merge_org(it.get("org_values", {}), base_cfg)
    core = json.dumps(_plain({k: it.get(k) for k in ("roles", "filters", "org_values", "risks", "materiality")}),
                      ensure_ascii=False, sort_keys=True) + "|" + _input_sha(meta) + extra  # extra: promoted exploratory Findings change the result, so the run_id
    run_id = "RUN-" + hashlib.sha256(core.encode("utf-8")).hexdigest()[:10].upper()
    cfg = {**base_cfg, **org, "_RUN": {"run_id": run_id, "data_ref": _data_ref(meta), "input_sha256": _input_sha(meta),
                                       "pack_version": __version__}}
    notes = [f"ค่าขององค์กร: {k} = {it['org_values'][k]!r} (แทนค่ามาตรฐาน AIDA-14 = {base_cfg[k]!r} เฉพาะ run นี้; "
             f"ผู้ยืนยัน {it.get('reviewer') or 'ไม่ระบุ'})" for k in it.get("org_values", {})]
    return cfg, notes


def _risk_for(cid: str, ev_risk: str, allowed: set) -> str:
    spec = CHECKS[cid]
    if ev_risk in allowed:
        return ev_risk
    for r in [spec["risk"]] + spec["risk_alt"]:
        if r in allowed:
            return r
    return ev_risk


def _source_cols(roles_used, tx_roles: dict) -> list:
    return [f"{tx_roles[r]} ({r})" for r in (roles_used or []) if r in tx_roles]


def _finding_view(ev: pd.DataFrame, tx: pd.DataFrame, dtype) -> pd.DataFrame:
    """Evidence as unify_findings should group it for C1 data: DUP-PAY with document numbers is keyed by the
    document, FOR-REPEAT / FOR-ROUND on a SPLIT-LIMIT entity-period join that finding, and entity types take the
    names of the data type (vendor, borrower, payer)."""
    v = ev.copy().reset_index(drop=True)
    if not len(v):
        return v
    if "document_no" in tx.columns:
        doc_of = dict(zip(tx["tx_id"].astype(str), tx["document_no"]))
        for i in v.index[(v["recipe_id"] == "DUP-PAY") & (v["entity_type"] == "entity")]:
            docs = {str(doc_of.get(r)).strip() for r in ref_list(v.at[i, "record_refs"])
                    if doc_of.get(r) is not None and not pd.isna(doc_of.get(r)) and str(doc_of.get(r)).strip()}
            if len(docs) == 1:
                v.at[i, "entity_type"], v.at[i, "entity_id"] = "document", docs.pop()
    for key_check, joins in ABSORB_C1.items():
        k = v[v["recipe_id"] == key_check]
        key_of = {}
        for a, b, c, r, refs in zip(k["entity_type"], k["entity_id"], k["period"], k["risk"], k["record_refs"]):
            key_of.setdefault((a, b, c), (r, set()))[1].update(ref_list(refs))
        for i in v.index[v["recipe_id"].isin(list(joins))]:
            hit = key_of.get((v.at[i, "entity_type"], v.at[i, "entity_id"], v.at[i, "period"]))
            refs = set(ref_list(v.at[i, "record_refs"]))
            if hit and refs and refs <= hit[1]:  # only the same records: other repeats keep their own Finding
                v.at[i, "risk"] = hit[0]
    lab = ENTITY_LABELS.get(dtype, {})
    v["entity_type"] = v["entity_type"].map(lambda x: lab.get(x, x))
    return v


def _plan_all(pl: pd.DataFrame) -> pd.DataFrame:
    rows = [(r["check_id"], r["decision"], r["reason"], r["missing"]) for _, r in pl.iterrows()]
    done = set(pl["check_id"])
    rows += [(c, "Skip", "ไม่เกี่ยวกับความเสี่ยงที่ยืนยันใน Intake (ผู้ตรวจสอบไม่ได้ขอ) จึงไม่รัน — เพิ่มความเสี่ยงที่ใช้การ์ดนี้"
                         "ที่จุดยืนยันแล้วรันใหม่", "ไม่ได้ขอ") for c in CHECKS if c not in done]
    return pd.DataFrame(rows, columns=["recipe_id", "decision", "reason", "missing"])


@_thai_errors
def run(files, intake, out_dir: str = ".", cfg: dict = None, registry_path: str = None) -> dict:
    """Analyse from the confirmed intake only (intake dict or the path of intake.json; nothing from earlier messages):
    re-read the files and verify sha256 (a Thai warning when changed), filters, org values for this run only,
    the planned checks, unified Findings, C/M/P, automatic Money Flow (E), Workbook / CSV / Dashboard and Run Log.
    Returns {status, run_id, findings, evidence, plan, run_log, paths {workbook, csv_dir, dashboard}, warnings,
    summary_th}."""
    it = _load_intake(intake)
    base_cfg = _load_cfg(cfg if cfg is not None else it.get("cfg"), registry_path or it.get("registry_path"))[0]
    warnings = []
    if str(base_cfg.get("REGISTRY.VERSION")) != str(it.get("registry_version")):
        warnings.append(f"Registry AIDA-14 เป็นรุ่น {base_cfg.get('REGISTRY.VERSION')} แต่ intake ยืนยันกับรุ่น "
                        f"{it.get('registry_version')} — ค่าเกณฑ์อาจต่างจากตอนยืนยัน")
    if it.get("engine_version") != __version__:
        warnings.append(f"engine รุ่น {__version__} แต่ intake สร้างด้วยรุ่น {it.get('engine_version')} — ตรวจผลเทียบกับรอบก่อน")
    pre = _prepare(files, it, base_cfg)
    warnings = pre["warnings"] + warnings
    ents, prom = _explore_state(it)
    cfg_run, org_notes = _run_cfg(it, base_cfg, pre["meta"], "|" + ",".join(p["finding_id"] for p in prom) if prom else "")
    events = list(pre["events"]) + [{"stage": 2, "status": "REVIEW", "detail": w} for w in warnings[len(pre["warnings"]):]]
    events += [{"stage": 6, "status": "OK", "detail": n} for n in org_notes]
    tables = pre["tables"]
    primary, _ = _split_roles(it["roles"])
    tx_name, tx_roles, _ = _roles_by_table(primary)
    profile_b1, status = prof_profile(tables, cfg_run)
    events.append({"stage": 3, "status": "STOP" if status.startswith("STOP") else "OK", "detail": status,
                   "recipe_id": "PROF-PROFILE"})
    risk_ids = _risk_order(list(it["risks"]["requested"]) + list(it["risks"].get("added", [])))
    events.append({"stage": 4, "status": "OK", "detail": "ความเสี่ยงที่ยืนยัน: " + (", ".join(risk_ids) or "ไม่มี")
                   + (f"; โหมดสำรวจ: {', '.join(it['risks'].get('exploratory', []))}" if it["risks"].get("exploratory") else "")})
    prof = profile_columns(pre["frames"])
    dtype = _type_from_roles(set(tx_roles), prof)
    pl = plan(risk_ids, primary, prof, cfg_run, tables) if not status.startswith("STOP") else \
        pd.DataFrame(columns=["check_id", "decision", "reason", "missing"])
    plan_df = _plan_all(pl)
    for _, r in plan_df[plan_df["decision"] == "Skip"].iterrows():
        events.append({"stage": 6, "status": "SKIP", "detail": f"{r['recipe_id']}: {r['reason']}", "recipe_id": r["recipe_id"]})
    tr = dict(tables)
    tr["_out"] = {}
    evs, allowed = [], set(risk_ids)
    runs = set(plan_df.loc[plan_df["decision"] == "Run", "recipe_id"])
    order = [c for c in CHECKS if c in runs and c not in MULE_STAGE] + [c for c in MULE_STAGE if c in runs]
    for cid in order:
        if cid in MULE_STAGE:
            tr["evidence"] = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame(columns=EVIDENCE_COLUMNS)
        try:
            ev = CHECKS[cid]["func"](tr, cfg_run)
        except Exception as e:  # noqa: BLE001 - one check failing does not stop the run
            events.append({"stage": 8, "status": "SKIP", "recipe_id": cid,
                           "detail": f"{cid}: รันไม่สำเร็จ ({type(e).__name__}: {e}) — ตรวจบทบาทและรูปแบบข้อมูลของคอลัมน์ที่การ์ดนี้ใช้"})
            continue
        ev = ev.copy()
        if "roles_used" not in ev.columns:
            ev["roles_used"] = [list(CHECKS[cid]["requires"]) for _ in range(len(ev))]
        ev["risk"] = [_risk_for(cid, r, allowed) for r in ev["risk"]]
        ev["source_columns"] = [_source_cols(r, tx_roles) for r in ev["roles_used"]]
        evs.append(ev)
        events.append({"stage": 8, "status": "OK", "detail": f"{cid}: Evidence {len(ev):,} แถว", "recipe_id": cid,
                       "recipe_version": ev["recipe_version"].iloc[0] if len(ev) else "-"})
    cols = EVIDENCE_COLUMNS + ["roles_used", "source_columns"]
    evidence = pd.concat(evs, ignore_index=True)[cols] if evs else pd.DataFrame(columns=cols)
    nets = tr["_out"].get("mule_networks")
    view = _finding_view(evidence, tables["transactions"], dtype)
    findings = unify_findings(view[EVIDENCE_COLUMNS] if len(view) else view, cfg_run, nets)
    mat = it.get("materiality") or {"type": "ไม่ระบุ"}
    m_amt = mat.get("amount") if mat.get("type") in ("ก", "ข") else None
    basis = f"แบบ {mat['type']}. {mat.get('basis', '')}".strip() if m_amt is not None else "-"
    assessed = assess_cmp(findings, tables["transactions"], m_amt, cfg_run)
    events.append({"stage": 12, "status": "OK", "detail": f"Unified Findings {len(assessed):,} รายการ จาก Evidence {len(evidence):,} แถว"})
    events.append({"stage": 15, "status": "OK", "detail": f"Confidence / Materiality / Priority ประเมินแล้ว (Materiality: "
                   f"{'ไม่ได้ประเมิน' if m_amt is None else f'{m_amt:,.2f} {basis}'})"})
    trails = []
    if dtype == "E" and "to_acct" in tables["transactions"].columns and len(assessed):
        trails = [flow_trace(tr, cfg_run, a, d, p) for a, p in select_auto_trace(assessed, cfg_run)
                  for d in ("forward", "backward")]
    assessed = assessed.assign(source="card", source_label=None, explore_id=None, reviewer=None, promote_reason=None,
                               promoted_at=None)
    if prom:  # promoted exploratory Findings (reviewer-confirmed, never above กลาง) join after the card Findings
        pf = _promoted_frame(prom, dtype)
        assessed = pf if not len(assessed) else pd.concat([assessed, pf[assessed.columns]], ignore_index=True)
    for e in ents:
        events.append({"stage": 8, "status": "REVIEW", "detail": f"{EXPLORE_NOT_CERTIFIED}: {e['explore_id']} \"{e['question']}\" "
                       f"({e['result']['text'][:120]})"})
    for p in prom:
        events.append({"stage": 8, "status": "REVIEW", "detail": f"{p['explore_id']} เลื่อนเป็น {p['finding_id']} "
                       f"(ความเสี่ยง {p['risk']}, Confidence {p['confidence']}) โดย {p['reviewer']} — ป้าย \"{EXPLORE_LABEL}\""})
    events.append({"stage": 8, "status": "REVIEW", "detail": "รอ Human Review — ผลเป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป"})
    log = log_run(events, cfg_run)
    bundle = out_bundle(tr, profile_b1, plan_df, evidence, assessed, trails, log, m_amt, cfg_run, basis)
    bundle["org_notes"] = org_notes
    bundle.update(_intake_frames(it), exploratory=_explore_frame(ents, prom), data_type=dtype or "")
    os.makedirs(out_dir, exist_ok=True)
    paths = {"workbook": out_workbook(bundle, os.path.join(out_dir, OUT_NAMES["workbook"]), cfg_run),
             "csv_dir": None,
             "dashboard": out_dashboard(bundle, DASHBOARD_TEMPLATE, os.path.join(out_dir, OUT_NAMES["dashboard"]), cfg_run)}
    if dtype == "E":
        folder = os.path.join(out_dir, OUT_NAMES["csv_dir"])
        out_network_csv(bundle, folder, cfg_run)
        paths["csv_dir"] = folder
    keep = [c for c in FINDING_COLUMNS + ["member_accts", "record_refs"] + FINDING_SOURCE_COLUMNS if c in assessed.columns]
    res = {"status": "STOP" if status.startswith("STOP") else "OK", "run_id": cfg_run["_RUN"]["run_id"],
           "findings": assessed[keep].reset_index(drop=True), "evidence": evidence, "plan": plan_df,
           "run_log": bundle["run_log"], "paths": paths, "warnings": warnings, "org_values": dict(it.get("org_values", {})),
           "exploratory": bundle["exploratory"], "promoted": len(prom)}
    res["summary_th"] = _summary_text(res, status, org_notes, dtype)
    return res


def _summary_text(res: dict, status: str, org_notes: list, dtype) -> str:
    f, pl = res["findings"], res["plan"]
    lines = [f"ผลการวิเคราะห์ {res['run_id']} (ข้อมูลประเภท {TYPE_TEXT.get(dtype, 'ไม่ระบุ')}): พบ Finding {len(f):,} รายการ "
             "— เป็นสัญญาณที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป"]
    if status.startswith("STOP"):
        lines.append(f"หยุดก่อนวิเคราะห์: {status[6:]}")
    for rid, n in f["risk"].value_counts().sort_index().items():
        lines.append(f"- {rid} {_risk_name(rid)}: {int(n):,} รายการ")
    if len(f):
        pr = f["priority"].value_counts()
        lines.append("Priority: " + " / ".join(f"{k} {int(pr.get(k, 0)):,}" for k in ("สูง", "กลาง", "ต่ำ")))
    lines.append(f"การ์ดที่รัน {int((pl['decision'] == 'Run').sum()):,} ใบ / ข้าม {int((pl['decision'] == 'Skip').sum()):,} ใบ "
                 "(เหตุผลอยู่ใน Analysis_Plan)")
    if res.get("promoted"):
        lines.append(f"โหมดสำรวจ: {res['promoted']:,} Finding ที่ผู้ตรวจสอบเลื่อนมา ติดป้าย \"{EXPLORE_LABEL}\" "
                     f"({EXPLORE_NOT_CERTIFIED}; Confidence ไม่เกินกลาง)")
    lines += org_notes
    lines += [f"คำเตือน: {w}" for w in res["warnings"]]
    lines.append("ไฟล์: " + ", ".join(f"{k} = {v}" for k, v in res["paths"].items() if v))
    return "\n".join(lines)


@_thai_errors
def trace(files, intake, acct: str, direction: str = "both", period: str = None, out_dir: str = ".",
          cfg: dict = None, registry_path: str = None) -> dict:
    """Money Flow on request (data type E): follow `acct` forward, backward or both from the confirmed intake.
    Returns {trails, path (CSV), summary_th}."""
    if direction not in ("forward", "backward", "both"):
        raise AidaError(f"direction ต้องเป็น 'forward' (เงินออก), 'backward' (เงินเข้า) หรือ 'both' (ได้รับ {direction!r})")
    it = _load_intake(intake)
    base_cfg = _load_cfg(cfg if cfg is not None else it.get("cfg"), registry_path or it.get("registry_path"))[0]
    pre = _prepare(files, it, base_cfg)
    cfg_run, _ = _run_cfg(it, base_cfg, pre["meta"])
    tx = pre["tables"]["transactions"]
    if "to_acct" not in tx.columns or "from_acct" not in tx.columns:
        raise AidaError("Money Flow ต้องมีบทบาท entity (บัญชีต้นทาง) และ counterparty (บัญชีปลายทาง) — ใช้ได้กับข้อมูล"
                        "โอนเงินระหว่างบัญชี (ประเภท E); กำหนดบทบาททั้งสองที่จุดยืนยันแล้วเรียกใหม่")
    acct = str(acct).strip()
    if not (tx["from_acct"].astype(str).eq(acct).any() or tx["to_acct"].astype(str).eq(acct).any()):
        raise AidaError(f"ไม่พบบัญชี '{acct}' ในข้อมูล (หลังตัวกรอง) — ตรวจเลขบัญชีอีกครั้ง")
    dirs = ["forward", "backward"] if direction == "both" else [direction]
    trails = [flow_trace(pre["tables"], cfg_run, acct, d, period) for d in dirs]
    notes = [t.attrs.get("note") for t in trails if t.attrs.get("truncated")]
    full = [t for t in trails if len(t)]
    df = pd.concat(full, ignore_index=True) if full else pd.DataFrame(columns=TRAIL_COLUMNS)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"trace-{re.sub(r'[^0-9A-Za-z_-]', '_', acct)}-{direction}.csv")
    text_cols(df, no_formula).to_csv(path, index=False, encoding="utf-8-sig")
    hops = int(df["hop"].max()) if len(df) else 0
    summary = (f"Money Flow ของบัญชี {acct} ({direction}{', งวด ' + period if period else ''}): {len(df):,} รายการ "
               f"{hops:,} ทอด — เป็นเส้นทางเงินที่ต้องตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป")
    if notes:
        summary += " | " + " | ".join(notes)
    return {"trails": df, "path": path, "summary_th": summary}


@_thai_errors
def save_mapping(intake: dict, path: str) -> str:
    """Write a mapping profile (spec 4.6): roles, column meanings, code-value meanings, filters, org values,
    confirmer and date, plus the column signature used to detect changes next time. `path` ending in .json is used
    as is; a bare name gives mapping-<name>.json. Returns the path."""
    if not isinstance(intake, dict) or intake.get("status") != "confirmed":
        raise AidaError("บันทึก mapping ได้จาก intake ที่ยืนยันแล้วเท่านั้น — เรียก confirm(...) ก่อน")
    p = str(path)
    if not p.lower().endswith(".json"):
        p = os.path.join(os.path.dirname(p), f"mapping-{os.path.basename(p)}.json")
    data = _plain({"mapping_version": 1, "engine_version": __version__, "saved_at": _now(),
                   "dataset_type": intake.get("dataset_type"), "roles": intake["roles"],
                   "columns": intake.get("columns", {}), "code_values": intake.get("code_values", {}),
                   "filters": intake.get("filters", []), "org_values": intake.get("org_values", {}),
                   "risks": _risk_order(list(intake["risks"]["requested"]) + list(intake["risks"].get("added", []))),
                   "confirmed_by": intake.get("reviewer"), "confirmed_at": intake.get("confirmed_at"),
                   "signature": intake.get("signature", {})})
    folder = os.path.dirname(os.path.abspath(p))
    os.makedirs(folder, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return p


@_thai_errors
def load_mapping(path) -> dict:
    """A mapping profile written by save_mapping (path or the dict itself), checked for its required parts."""
    if isinstance(path, dict):
        m = path
    else:
        p = str(path)
        if not os.path.isfile(p):
            raise AidaError(f"ไม่พบไฟล์ mapping '{p}' — ตรวจที่อยู่ไฟล์ (เช่น mapping-<ชื่อ>.json ใน SharePoint ของทีม)")
        try:
            with open(p, encoding="utf-8") as fh:
                m = json.load(fh)
        except json.JSONDecodeError as e:
            raise AidaError(f"ไฟล์ mapping '{p}' ไม่ใช่ JSON ที่ถูกต้อง ({e.msg}) — บันทึกใหม่ด้วย save_mapping") from None
    need = ("roles", "columns", "code_values", "filters", "org_values", "confirmed_by", "confirmed_at", "signature")
    miss = [k for k in need if k not in m]
    if miss:
        raise AidaError(f"mapping profile ไม่ครบ (ขาด {', '.join(miss)}) — บันทึกใหม่ด้วย save_mapping(intake, ชื่อ)")
    return m


# ---- Exploratory mode (spec 4.5) ----
EXPLORE_LOG = []  # entries of this session (also written to explore_log.json next to intake.json)
EXPLORE_FILE = "explore_log.json"
EXPLORE_LABEL = "จากโหมดสำรวจ"  # permanent label of a promoted Finding
EXPLORE_NOT_CERTIFIED = "โหมดสำรวจ — ยังไม่ผ่านการรับรอง"
RX_NAME = "ความเสี่ยงจากโหมดสำรวจ"
CONF_RANK = {"ต่ำ": 0, "กลาง": 1, "สูง": 2}
EXPLORE_MAX_CONFIDENCE = "กลาง"
EXPLORE_HEAD_ROWS = 5
EXPLORE_TEXT_MAX = 2000
EXPLORE_COLUMNS = ["explore_id", "question", "code", "result_summary", "note", "time", "promoted", "promoted_by",
                   "promote_reason", "promoted_finding"]


def _risk_name(rid: str) -> str:
    return RX_NAME if rid == "RX" else RISK_LIBRARY.get(rid, {}).get("name_th", "")


def _explore_path(intake):
    """explore_log.json next to intake.json for an intake dict (its `intake_path` key, set by confirm / run) or the
    path of intake.json; None when the intake has no known path (the log then stays in EXPLORE_LOG only)."""
    if intake is None:
        return None
    if isinstance(intake, (str, os.PathLike)):
        return os.path.join(os.path.dirname(os.path.abspath(str(intake))), EXPLORE_FILE)
    if isinstance(intake, dict):
        p = intake.get("intake_path")
        return os.path.join(os.path.dirname(os.path.abspath(p)), EXPLORE_FILE) if p else None
    raise AidaError("intake ต้องเป็น dict ที่ได้จาก confirm(...) หรือที่อยู่ไฟล์ intake.json")


def _read_explore(path) -> dict:
    if not path or not os.path.isfile(path):
        return {"explore": [], "promoted": []}
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except json.JSONDecodeError as e:
        raise AidaError(f"ไฟล์ {path} ไม่ใช่ JSON ที่ถูกต้อง ({e.msg}) — กู้คืนจากสำเนา หรือย้ายไฟล์ออกแล้วบันทึกโหมดสำรวจใหม่") from None
    if not isinstance(d, dict):
        raise AidaError(f"ไฟล์ {path} รูปแบบไม่ถูกต้อง — ต้องมี explore และ promoted")
    out = {"explore": d.get("explore", []), "promoted": d.get("promoted", [])}
    need = {"explore": ("explore_id", "question", "code", "result", "time"),
            "promoted": ("finding_id", "explore_id", "entity_id", "risk", "confidence", "reviewer", "promote_reason")}
    for part, keys in need.items():
        if not isinstance(out[part], list):
            raise AidaError(f"ไฟล์ {path}: '{part}' ต้องเป็นรายการ — กู้คืนจากสำเนาหรือสร้างบันทึกใหม่")
        for i, e in enumerate(out[part], 1):
            miss = [k for k in keys if not isinstance(e, dict) or k not in e]
            if not miss and part == "explore" and not (isinstance(e["result"], dict) and "text" in e["result"]):
                miss = ["result.text"]
            if miss:
                raise AidaError(f"ไฟล์ {path}: แถวที่ {i} ของ '{part}' ขาด {', '.join(miss)} — แก้ไฟล์ให้ครบหรือกู้คืนจากสำเนา")
    return out


def _write_explore(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_plain(data), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _explore_no(eid) -> int:
    m = re.fullmatch(r"EXP-(\d+)", str(eid))
    return int(m.group(1)) if m else 0


def _result_summary(res) -> dict:
    """What the Exploratory sheet shows of a result: rows, columns and the first rows for a table, else its text."""
    if isinstance(res, pd.Series):
        res = res.to_frame().reset_index()
    if isinstance(res, pd.DataFrame):
        if res.index.name is not None or isinstance(res.index, pd.MultiIndex):
            res = res.reset_index()
        head = json.loads(res.head(EXPLORE_HEAD_ROWS).to_json(orient="records", date_format="iso", force_ascii=False))
        cols = [str(c) for c in res.columns]
        text = (f"{len(res):,} แถว {len(cols):,} คอลัมน์ ({', '.join(cols)}); {min(len(res), EXPLORE_HEAD_ROWS)} แถวแรก: "
                + json.dumps(head, ensure_ascii=False))
        return {"kind": "table", "rows": int(len(res)), "columns": cols, "head": head, "text": text[:EXPLORE_TEXT_MAX]}
    return {"kind": "value", "text": str(res)[:EXPLORE_TEXT_MAX]}


def _nonblank(v, what: str, how: str) -> str:
    if v is None or not str(v).strip():
        raise AidaError(f"ต้องระบุ{what} — {how}")
    return str(v).strip()


@_thai_errors
def data(files=None, intake=None) -> dict:
    """The data for exploratory mode: internal frames {"transactions", "accounts"} after the confirmed filters and
    roles (custom roles included). df.attrs["original_names"] = {internal column: column name in the file};
    df.attrs["warnings"] = warnings such as a changed sha256. Call as data(files, intake) or data(intake)
    (an intake dict or the path of intake.json); with files=None the files recorded in the intake are read."""
    if intake is None and files is not None and (
            (isinstance(files, dict) and "roles" in files and "files" in files)
            or (isinstance(files, (str, os.PathLike)) and str(files).lower().endswith(".json"))):
        files, intake = None, files
    it = _load_intake(intake)
    base_cfg = _load_cfg(it.get("cfg"), it.get("registry_path"))[0]
    pre = _prepare(files, it, base_cfg)
    primary, extra = _split_roles(it["roles"])
    tx_name = _roles_by_table(primary)[0]
    names = {"transactions": {}, "accounts": {}}
    for t, rmap in primary.items():
        for col, role in rmap.items():
            if t == tx_name:
                names["transactions"][ROLE_TO_INTERNAL.get(role, role)] = col
            elif role == ACCOUNT_ID_ROLE:
                names["accounts"]["acct_id"] = col
            elif role == "opened_at" or role.startswith("custom:"):
                names["accounts"][role] = col
    for t, col, role in extra:
        names["transactions" if t == tx_name else "accounts"][role] = col
    out = {}
    for k, df in pre["tables"].items():
        if k.startswith("_"):
            continue
        df = df.copy()
        df.attrs["original_names"] = {c: names.get(k, {})[c] for c in df.columns if c in names.get(k, {})}
        df.attrs["warnings"] = list(pre["warnings"])
        out[k] = df
    return out


@_thai_errors
def explore_log(question: str, code: str, result, note: str = "", intake=None) -> str:
    """Record one exploratory analysis (spec 4.5): the question, the full code, a summary of the result (rows and
    columns plus the first rows of a table), a note and the time. Returns "EXP-<n>", appends to EXPLORE_LOG and,
    when `intake` (dict from confirm / run, or the path of intake.json) is given, writes explore_log.json next to
    intake.json: {"explore": [...], "promoted": [...]}. The result is shown as "โหมดสำรวจ — ยังไม่ผ่านการรับรอง"."""
    q = _nonblank(question, "คำถาม", "บอกว่าโหมดสำรวจนี้ตอบคำถามอะไร")
    c = _nonblank(code, "โค้ด", "ส่งโค้ด pandas เต็มที่ใช้หาผลนี้ เพื่อให้ผู้ตรวจสอบทำซ้ำได้")
    path = _explore_path(intake)
    data_ = _read_explore(path) if path else {"explore": [], "promoted": []}
    mine = data_["explore"] if path else [e for e in EXPLORE_LOG if not e.get("log_path")]
    eid = f"EXP-{max([_explore_no(e['explore_id']) for e in mine], default=0) + 1}"
    entry = {"explore_id": eid, "question": q, "code": str(code), "result": _result_summary(result),
             "note": str(note or ""), "time": _now()}
    if path:
        data_["explore"].append(entry)
        _write_explore(path, data_)
    EXPLORE_LOG.append({**entry, "log_path": path})
    return eid


@_thai_errors
def promote(explore_id, entity, risk, period, reason, reviewer, confidence: str = EXPLORE_MAX_CONFIDENCE,
            intake=None) -> dict:
    """Promote an exploratory result to a Finding row (spec 4.5): source="exploratory", Confidence never above กลาง
    (a higher `confidence` is capped), reviewer required, risk from the Risk Library or "RX", and the permanent
    label "จากโหมดสำรวจ". The row is saved in the `promoted` list of explore_log.json (next to intake.json) so
    run(files, intake) merges it into Findings, the Exploratory sheet and the Dashboard in this and later runs."""
    rv = _nonblank(reviewer, "ผู้ตรวจสอบ (reviewer)", "ระบุชื่อผู้ตรวจสอบที่สั่งเลื่อนก่อนเลื่อนเป็น Finding")
    if not isinstance(risk, str) or (risk != "RX" and risk not in RISK_LIBRARY):
        raise AidaError(f"ไม่รู้จักความเสี่ยง '{risk}' — เลือกจาก Risk Library ({', '.join(RISK_LIBRARY)}) "
                        "หรือใช้ RX สำหรับความเสี่ยงที่ไม่มีในคลัง แล้วเรียกใหม่")
    ent = _nonblank(entity, "entity (บัญชี/ผู้ชำระ/ผู้ขาย)", "ระบุรหัสของสิ่งที่ผลสำรวจชี้")
    why = _nonblank(reason, "เหตุผลที่เลื่อน", "อธิบายว่าทำไมผลนี้ควรทบทวนต่อ (ใช้ถ้อยคำไม่กล่าวหา)")
    if confidence not in CONF_RANK:
        raise AidaError(f"confidence ต้องเป็น ต่ำ / กลาง / สูง (ได้รับ {confidence!r}) — Finding จากโหมดสำรวจสูงสุดได้ {EXPLORE_MAX_CONFIDENCE}")
    conf = min(confidence, EXPLORE_MAX_CONFIDENCE, key=CONF_RANK.get)
    path = _explore_path(intake)
    if path:
        found = [e for e in _read_explore(path)["explore"] if e["explore_id"] == explore_id]
    else:
        found = [e for e in reversed(EXPLORE_LOG) if e["explore_id"] == explore_id][:1]
        path = found[0].get("log_path") if found else None
    if not found:
        raise AidaError(f"ไม่พบ {explore_id} ในบันทึกโหมดสำรวจ — เรียก explore_log(...) ก่อน หรือส่ง intake= ของชุดข้อมูลเดียวกัน")
    data_ = _read_explore(path) if path else {"explore": [], "promoted": []}
    n = sum(1 for p in data_["promoted"] if p["explore_id"] == explore_id)
    row = {"finding_id": f"FND-{explore_id}" + (f"-{n + 1}" if n else ""), "entity_type": "entity", "entity_id": ent,
           "risk": risk, "period": str(period).strip() if period is not None and str(period).strip() else "-",
           "evidence_ids": [], "skill_families": ["exploratory"], "exposure": None, "confidence": conf,
           "materiality": "ไม่ได้ประเมิน", "priority": conf, "review_status": "รอ Human Review",
           "review_reason": f"{EXPLORE_LABEL} ({EXPLORE_NOT_CERTIFIED}) — เหตุผลที่ผู้ตรวจสอบเลื่อน: {why}",
           "network_id": None, "member_accts": [], "record_refs": [], "data_ref_complete": False, "internal_amount": None,
           "source": "exploratory", "source_label": EXPLORE_LABEL, "explore_id": explore_id, "reviewer": rv,
           "promote_reason": why, "promoted_at": _now()}
    if path:
        data_["promoted"].append(row)
        _write_explore(path, data_)
    return row


def _explore_state(it: dict) -> tuple:
    """(entries, promoted rows) saved next to this intake, in a fixed order."""
    d = _read_explore(_explore_path(it))
    ents = sorted(d["explore"], key=lambda e: _explore_no(e["explore_id"]))
    prom = []
    for p in sorted(d["promoted"], key=lambda p: (_explore_no(p["explore_id"]), p["finding_id"])):
        where = f"แถว promoted {p['finding_id']} ({p['explore_id']}) ใน {EXPLORE_FILE}"
        if not isinstance(p["reviewer"], str) or not p["reviewer"].strip():
            raise AidaError(f"{where}: ไม่มี reviewer — Finding จากโหมดสำรวจต้องมีผู้ตรวจสอบ ใส่ชื่อผู้ตรวจสอบหรือลบแถวนี้")
        if not isinstance(p["risk"], str) or (p["risk"] != "RX" and p["risk"] not in RISK_LIBRARY):
            raise AidaError(f"{where}: ความเสี่ยง {p['risk']!r} ไม่อยู่ใน Risk Library — ใช้รหัสในคลังหรือ RX แล้วรันใหม่")
        if p["confidence"] not in CONF_RANK:
            raise AidaError(f"{where}: confidence {p['confidence']!r} ต้องเป็น ต่ำ / กลาง / สูง — แก้ไฟล์แล้วรันใหม่")
        conf = min(p["confidence"], EXPLORE_MAX_CONFIDENCE, key=CONF_RANK.get)  # never above กลาง, whatever the file says
        prom.append({**p, "reviewer": p["reviewer"].strip(), "confidence": conf, "priority": conf, "source": "exploratory",
                     "source_label": EXPLORE_LABEL})
    return ents, prom


def _explore_frame(ents: list, prom: list) -> pd.DataFrame:
    by = {}
    for p in prom:
        by.setdefault(p["explore_id"], []).append(p)
    rows = []
    for e in ents:
        ps = by.get(e["explore_id"], [])
        rows.append((e["explore_id"], e["question"], e["code"], e["result"]["text"], e.get("note", ""), e["time"],
                     "ใช่" if ps else "ไม่", "; ".join(dict.fromkeys(p["reviewer"] for p in ps)),
                     "; ".join(p["promote_reason"] for p in ps), "; ".join(p["finding_id"] for p in ps)))
    return pd.DataFrame(rows, columns=EXPLORE_COLUMNS)


def _promoted_frame(prom: list, dtype) -> pd.DataFrame:
    cols = FINDING_COLUMNS + FINDING_WORK_COLUMNS + FINDING_SOURCE_COLUMNS
    lab = ENTITY_LABELS.get(dtype, {})
    rows = [{**p, "entity_type": lab.get(p["entity_type"], p["entity_type"])} for p in prom]
    return pd.DataFrame(rows, columns=cols)


def _roles_text(r) -> str:
    return ", ".join(_role_list(r)) or "ไม่ใช้"


def _intake_frames(it: dict) -> dict:
    """Intake_Review, Data_Dictionary and Data_Request (spec 6) from the confirmed intake."""
    br, rk = it.get("brief") or {}, it["risks"]
    rows = []

    def add(section, item, detail=""):
        rows.append((section, str(item), str(detail)))
    add("บริบท", "บริบทงาน", br.get("context") or "ไม่ระบุ")
    add("บริบท", "ไฟล์", "; ".join(f"{t} ({m['file']}{' ชีต ' + m['sheet'] if m.get('sheet') else ''})" for t, m in it["files"].items()))
    nrows = {}
    for p in it.get("profile", []):
        nrows[p["table"]] = p["n_rows"]
    add("บริบท", "จำนวนแถวก่อนใช้ตัวกรอง", ", ".join(f"{t} {n:,} แถว" for t, n in nrows.items()))
    if it.get("dataset_type"):
        add("บริบท", "ประเภทข้อมูลที่ engine เห็น", f"{it['dataset_type']} ({TYPE_TEXT[it['dataset_type']]})")
    for c in rk.get("concerns", []):
        if c["risk_id"]:
            add("Risk Concern", c["concern"], f"จับคู่กับ {c['risk_id']} {_risk_name(c['risk_id'])} (โหมดรับรอง)")
        else:
            add("Risk Concern", c["concern"], f"ไม่มีใน Risk Library — วิเคราะห์ในโหมดสำรวจ ({EXPLORE_NOT_CERTIFIED})")
    for s in it.get("sufficiency", []):
        add("ความพอเพียง", f"{s['risk_id']} {_risk_name(s['risk_id'])}",
            f"{SUFF_ICON[s['status']]} {s['status']} — {_dedup_text(s['reason'])}"
            + (f" | การ์ดที่รันได้: {', '.join(s['runnable_checks'])}" if s["runnable_checks"] else ""))
    chosen = set(rk.get("requested", [])) | set(rk.get("added", []))
    for s in it.get("suggested_risks", []):
        add("ความเสี่ยงที่แนะนำ", f"{s['risk_id']} {s['name_th']}",
            s["why_th"] + (" | ผู้ตรวจสอบเลือกเพิ่มแล้ว" if s["risk_id"] in chosen else " | ยังไม่ได้เพิ่ม"))
    add("คำตอบผู้ตรวจสอบ", "ผู้ยืนยัน", it.get("reviewer") or "ไม่ระบุ")
    add("คำตอบผู้ตรวจสอบ", "ยืนยันเมื่อ", it.get("confirmed_at") or "-")
    add("คำตอบผู้ตรวจสอบ", "ความเสี่ยงที่ขอ", ", ".join(rk.get("requested", [])) or "ไม่มี")
    add("คำตอบผู้ตรวจสอบ", "ความเสี่ยงที่เพิ่มหลังคำแนะนำ", ", ".join(rk.get("added", [])) or "ไม่มี")
    for t, rmap in it["roles"].items():
        for c, r in rmap.items():
            add("คำตอบผู้ตรวจสอบ", f"บทบาท {t}.{c}", _roles_text(r))
    for f in it.get("filters", []):
        add("คำตอบผู้ตรวจสอบ", "ตัวกรอง", f"{f['column']} {f['op']} {f['value']}")
    for k, v in (it.get("org_values") or {}).items():
        add("คำตอบผู้ตรวจสอบ", f"ค่าขององค์กร {k}", f"{v!r} (แทนค่ามาตรฐาน AIDA-14 เฉพาะ run นี้)")
    mat = it.get("materiality") or {}
    add("คำตอบผู้ตรวจสอบ", "Materiality", f"แบบ {mat.get('type', 'ไม่ระบุ')}" + (
        f" ฐาน {mat['amount']:,.2f} {mat.get('basis', '')}" if mat.get("type") in ("ก", "ข") and _num_value(mat.get("amount")) is not None else ""))
    review = pd.DataFrame(rows, columns=["section", "item", "detail"])
    dd = []
    for p in it.get("profile", []):
        t, c = p["table"], p["column"]
        cv = it.get("code_values", {}).get(f"{t}.{c}") or {}
        dd.append((t, c, (it.get("columns", {}).get(t) or {}).get(c, ""), _roles_text(it["roles"].get(t, {}).get(c)),
                   ", ".join(f"{a} = {b}" for a, b in cv.items()), it.get("reviewer") or "ไม่ระบุ", it.get("confirmed_at") or "-"))
    dic = pd.DataFrame(dd, columns=["table", "column", "meaning", "role", "code_values", "confirmed_by", "confirmed_at"])
    req = []
    for s in it.get("sufficiency", []):
        for r in s["data_request"]:
            req.append((len(req) + 1, s["risk_id"], r))
    if not req:
        req = [(1, "-", "ไม่มี — ข้อมูลพอสำหรับความเสี่ยงที่ขอ")]
    return {"intake_review": review, "data_dictionary": dic,
            "data_request": pd.DataFrame(req, columns=["no", "risk_id", "request"])}


# ---- Intake Review text (spec 4.3 step 4) ----
def _review_text(it: dict) -> str:
    L = []
    files = ", ".join(f"{t} ({m['file']}{' ชีต ' + m['sheet'] if m.get('sheet') else ''})" for t, m in it["files"].items())
    rows = {}
    for p in it["profile"]:
        rows[p["table"]] = p["n_rows"]
    L.append(f"Intake Review — ไฟล์ {len(it['files']):,} ตาราง: {files}")
    L.append("จำนวนแถว: " + ", ".join(f"{t} {n:,} แถว" for t, n in rows.items()))
    if it.get("dataset_type"):
        L.append(f"ประเภทข้อมูลที่ engine เห็น: {it['dataset_type']} ({TYPE_TEXT[it['dataset_type']]})")
    if it.get("brief", {}).get("context"):
        L.append(f"บริบท: {it['brief']['context']}")
    if it.get("mapping"):
        L.append(f"ใช้ mapping profile ที่ยืนยันโดย {it['mapping'].get('confirmed_by') or 'ไม่ระบุ'} เมื่อ "
                 f"{it['mapping'].get('confirmed_at') or '-'} — ถามเฉพาะสิ่งที่เปลี่ยน")
    L += [""] + _review_a(it) + [""] + _review_b(it) + [""] + _review_c(it) + [""] + _review_d(it) + [""] + _review_e(it)
    L += ["", CONFIRM_LINE]
    return "\n".join(L)


def _review_a(it: dict) -> list:
    L = ["A. ความหมายคอลัมน์ (✅ ตรงกับคำอธิบาย / ⚠️ ขัดกับข้อมูล / ❓ เดาให้ช่วยยืนยัน / ⚪ ไม่ทราบ — เก็บเป็น custom หรือไม่ใช้)"]
    conf = {(c["table"], c["column"]): c for c in it.get("description_conflicts", [])}
    ch = it.get("changes")
    prof = {(p["table"], p["column"]): p for p in it["profile"]}
    if ch is not None:
        kept = [s for s in it["role_suggestions"] if s["source"] == "mapping" and s["status"] in ("ok", "unchanged")]
        if kept:
            L.append(f"✅ ใช้ค่าเดิมจาก mapping {len(kept):,} คอลัมน์ (ไม่ต้องยืนยันซ้ำ): " + ", ".join(
                f"{s['column']} → {s['role'] if s['role'] != UNKNOWN_ROLE else 'ไม่ใช้'}" for s in kept))
        for k in ch["removed"]:
            L.append(f"⚠️ คอลัมน์ที่หายไปจากไฟล์: {k} — การ์ดที่ใช้บทบาทของคอลัมน์นี้จะถูกข้าม ถ้าเปลี่ยนชื่อให้กำหนดบทบาทให้คอลัมน์ใหม่")
        if not (ch["added"] or ch["removed"] or ch["changed_pattern"]):
            L.append("ไม่มีคอลัมน์ใหม่ หาย หรือเปลี่ยนรูปแบบ")
    for s in it["role_suggestions"]:
        if s["source"] == "mapping" and s["status"] in ("ok", "unchanged"):
            continue
        icon = COL_ICON[s["status"]]
        p = prof.get((s["table"], s["column"]), {})
        role = s["role"] if s["role"] != UNKNOWN_ROLE else "ไม่ทราบ"
        ex = ", ".join(p.get("samples", [])[:3])
        line = f"{icon} {s['table']}.{s['column']} → {role}"
        if s["role"] != UNKNOWN_ROLE:
            line += f" (ความมั่นใจ{s['level']} {s['confidence']:.2f})"
        line += f": {s['reason']}"
        c = conf.get((s["table"], s["column"]))
        if c:
            line += f" | คำอธิบาย \"{c['said']}\" แต่{c['observed']} — {c['question']}"
        if ex:
            line += f" | ตัวอย่าง: {ex}"
        if s["status"] == "unknown":
            line += " — ระบุความหมาย หรือเก็บเป็น custom:<ชื่อ> หรือไม่ใช้"
        L.append(line)
    for k, v in it.get("code_values", {}).items():
        L.append(f"✅ ค่ารหัสของ {k}: " + ", ".join(f"{a} = {b}" for a, b in v.items()))
    for p in it["profile"]:
        jm = p.get("join_match")
        tx_name = _roles_by_table(_split_roles(it["roles"])[0])[0]
        if isinstance(jm, dict) and p["table"] == tx_name and _role_list(it["roles"].get(p["table"], {}).get(p["column"])):
            L.append(f"การเชื่อมตาราง: {p['table']}.{p['column']} พบใน {jm['with']} {jm['normalized']:.1f}% ของรหัส "
                     f"(ตรงทุกตัวอักษร {jm['raw']:.1f}%)")
    for n in it.get("notes", []):
        L.append(f"⚠️ {n}")
    return L


def _review_b(it: dict) -> list:
    L = ["B. ความพอเพียงตาม Risk Concern (✅ พร้อม / 🟡 บางส่วน / ❌ ไม่พอ)"]
    suff = {s["risk_id"]: s for s in it["sufficiency"]}
    concerns = it["risks"].get("concerns", [])
    if not concerns and not it["risks"]["requested"]:
        L.append("ยังไม่มี Risk Concern — ระบุสิ่งที่กังวล หรือเลือกความเสี่ยงจากข้อ D")
    shown = set()
    for i, c in enumerate(concerns, 1):
        rid = c["risk_id"]
        if rid is None:
            L.append(f"{i}. ❓ \"{c['concern']}\" → ไม่มีในคลังความเสี่ยง (Risk Library) จะวิเคราะห์ในโหมดสำรวจ "
                     "(ผลมีป้าย \"โหมดสำรวจ — ยังไม่ผ่านการรับรอง\")")
            continue
        L.append(_suff_line(f"{i}. \"{c['concern']}\" → ", rid, suff.get(rid)))
        shown.add(rid)
    for rid in it["risks"]["requested"]:
        if rid not in shown:
            L.append(_suff_line("- ", rid, suff.get(rid)))
    req = [r for s in it["sufficiency"] for r in s["data_request"]]
    req = _risk_order(req)
    L.append("Data Request (ข้อมูลที่ควรขอเพิ่ม):" if req else "Data Request: ไม่มี — ข้อมูลพอสำหรับความเสี่ยงที่ขอ")
    L += [f"  {i}. {r}" for i, r in enumerate(req, 1)]
    return L


def _suff_line(prefix: str, rid: str, s) -> str:
    name = RISK_LIBRARY[rid]["name_th"]
    if s is None:
        return f"{prefix}{rid} {name}"
    line = f"{prefix}{rid} {name}: {SUFF_ICON[s['status']]} {s['status']} — {_dedup_text(s['reason'])}"
    if s["runnable_checks"]:
        line += f" | การ์ดที่รันได้: {', '.join(s['runnable_checks'])}"
    return line


def _dedup_text(text: str) -> str:
    """A reason joined from several checks, each distinct part once (in order)."""
    out = []
    for part in re.split(r"; | \| |: (?=การ์ดนี้)", str(text)):
        if part and part not in out:
            out.append(part)
    return "; ".join(out)


def _review_c(it: dict) -> list:
    L = ["C. เงื่อนไขที่เข้าใจ"]
    props = it.get("filter_proposals", [])
    if it.get("mapping"):
        for f in it.get("filters", []):
            L.append(f"✅ ตัวกรองเดิมจาก mapping: {f['column']} {f['op']} {f['value']}")
    for p in props:
        if p["filter"]:
            f = p["filter"]
            L.append(f"❓ \"{p['condition']}\" → ตัวกรอง {f['column']} {f['op']} {f['value']} (ตัดออก {p['rows_removed']:,} แถว)")
        elif p["note"] == "ไม่ต้องใช้ตัวกรอง":
            L.append(f"✅ \"{p['condition']}\" → ไม่ต้องใช้ตัวกรอง")
        else:
            L.append(f"❓ \"{p['condition']}\" → {p['note']}")
    if not props and not it.get("filters"):
        L.append("ไม่มีเงื่อนไขหรือตัวกรอง — วิเคราะห์ทุกแถว")
    if it.get("org_values"):
        L += [f"ค่าขององค์กร: {k} = {v!r} (แทนค่ามาตรฐาน AIDA-14 เฉพาะ run นี้)" for k, v in it["org_values"].items()]
    else:
        L.append("ค่าเกณฑ์: ใช้ค่ามาตรฐาน AIDA-14 ทั้งหมด — ถ้าองค์กรมีค่าของตนเอง (เช่น DUP.WINDOW_DAYS) ระบุได้ จะติดป้าย \"ค่าขององค์กร\"")
    L.append("ตัวเลขใน Intake Review นี้คำนวณก่อนใช้ตัวกรอง")
    return L


def _review_d(it: dict) -> list:
    L = ["D. ความเสี่ยงที่แนะนำเพิ่ม (ยังไม่เพิ่มจนกว่าผู้ตรวจสอบเลือก)"]
    if not it["suggested_risks"]:
        L.append("ไม่มีความเสี่ยงอื่นในคลังที่ข้อมูลรองรับและพบสัญญาณเบื้องต้น")
    for s in it["suggested_risks"]:
        L.append(f"- {s['risk_id']} {s['name_th']}: {s['why_th']}")
    return L


def _review_e(it: dict) -> list:
    p = it.get("prep") or {}
    L = ["E. วันที่ / คุณภาพข้อมูล / Materiality / แผน Run-Skip"]
    if p:
        L.append(f"รูปแบบวันที่ที่แปลง: {p.get('date_format', '-')} | แปลงปี พ.ศ.: {'ใช่' if p.get('be_converted') else 'ไม่'} | "
                 f"วันและเดือน ≤ 12 ทั้งคู่ {p.get('ambiguous_dates', 0):,} รายการ | ตัวอย่าง: "
                 + ", ".join(f"{a} → {b}" for a, b in p.get("date_samples", [])))
        L.append(f"วันที่แปลงไม่ได้ {p.get('unparsed_ts', 0):,} แถว | ยอดเงินแปลงไม่ได้ {p.get('unparsed_amount', 0):,} แถว | "
                 f"ยอด ≤ 0 (ไม่นำไปวิเคราะห์) {p.get('excluded_nonpositive', 0):,} แถว")
    st = it.get("profile_status")
    if st:
        L.append("ตรวจ record_id และคุณภาพข้อมูล: " + ("ผ่าน" if st == "OK" else st))
    mat = it.get("materiality") or {}
    if mat.get("type") in ("ก", "ข"):
        amt = _num_value(mat.get("amount"))
        L.append(f"Materiality: แบบ {mat['type']}. ฐาน {amt:,.2f} {mat.get('basis', '')}".rstrip() if amt is not None
                 else f"Materiality: แบบ {mat['type']}. — ยังไม่มีฐานเป็นจำนวนเงิน ขอให้ระบุ")
    else:
        L.append("Materiality: ยังไม่ระบุ — เลือก ก. / ข. (พร้อมฐานเป็นจำนวนเงิน) หรือไม่ระบุ (Priority = Confidence)")
    pl = it.get("plan", [])
    run_ = [r["check_id"] for r in pl if r["decision"] == "Run"]
    skip = [r for r in pl if r["decision"] == "Skip"]
    L.append(f"แผน: Run {len(run_):,} การ์ด ({', '.join(run_) or '-'}) / Skip {len(skip):,} การ์ด")
    by = {}
    for r in skip:
        by.setdefault(r["reason"], []).append(r["check_id"])
    for reason, ids in by.items():
        L.append(f"  - Skip {', '.join(ids)}: {reason}")
    return L
