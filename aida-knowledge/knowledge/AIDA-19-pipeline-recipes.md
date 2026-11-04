# AIDA-19 · Pipeline Recipes (การ์ดเตรียมข้อมูล, Evidence builder, รวมผล และ Output)
> ไฟล์: AIDA-19 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: การ์ด CORE-EVIDENCE สร้างแถว Evidence อย่างไร, กฎกลางที่ทุกการ์ดวิเคราะห์ใช้ร่วมกันคืออะไร (ตัดรายการโอนเข้าบัญชีตัวเอง / ยอด ≤ 0), ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดใน AIDA-18 หรือไม่, เตรียมข้อมูล / Dataset Profile / Analysis Plan (Run/Skip) ทำอย่างไร, รวม Evidence เป็น Finding และประเมิน Confidence / Exposure / Materiality / Priority อย่างไร, เลือกบัญชีไล่เส้นทางเงินอัตโนมัติและบันทึก Run Log อย่างไร, สร้าง Audit Workbook / Network Investigation Package (CSV) / HTML Dashboard อย่างไร

## สรุปสั้น
ไฟล์นี้เก็บการ์ด (recipe) ระดับ pipeline ที่ Code Interpreter รันตามลำดับในข้อ 7 ของ Instructions — **ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดวิเคราะห์ใน AIDA-18** เพราะการ์ดวิเคราะห์ทุกใบเรียกใช้ฟังก์ชันจาก `CORE-EVIDENCE` และ `CORE-BASELINE`
ลำดับ: CORE-EVIDENCE, CORE-BASELINE → PREP-DATE, PREP-TS, PREP-MAP → PROF-CHECKS, PROF-PROFILE (STOP แล้วหยุด) → GATE-CAPABILITY, GATE-VOLUME → การ์ดใน AIDA-18 ตาม Analysis Plan → UNIFY-REFS, UNIFY-FINDINGS → ASSESS-CMP → SELECT-AUTO-TRACE + FLOW-TRACE → LOG-RUN → OUT-BUNDLE, OUT-CELL → OUT-WORKBOOK, OUT-NETWORK-CSV, OUT-DASHBOARD (template ใน AIDA-16)
คอลัมน์ Evidence เป็นไปตาม Schema ใน AIDA-17 และทุกแถวบันทึก Registry version จาก AIDA-14

## การ์ด Evidence builder

### CORE-EVIDENCE
ฟังก์ชันกลางที่การ์ดวิเคราะห์ทุกใบใช้: `clean_tx` (ตัดรายการโอนเข้าบัญชีตัวเอง, ยอด ≤ 0 และรายการที่ไม่มีวันเวลา, แปลง ts, เพิ่ม period YYYY-MM), `one_per_month` (1 แถวต่อบัญชีต่อเดือน), `evidence_rows` (สร้างแถวตาม Evidence schema), `card_note` (หมายเหตุข้อจำกัดของการ์ดใน `tables["_out"]["notes"]` เช่น ค้นหาถึงขีดจำกัด — แจ้งได้แม้ไม่มีแถว Evidence; OUT-BUNDLE บันทึกเป็น REVIEW ใน Run Log และแสดงใน README / Dashboard) และ `core_evidence` (Evidence ว่าง ใช้เมื่อไม่มีการ์ดใดรัน)
การ์ดนี้ไม่มีเกณฑ์ใด ๆ — อ่านเพียง `REGISTRY.VERSION` และ `cfg["_RUN"]` (run_id, data_ref)

```python
# RECIPE CORE-EVIDENCE v1.1 | Skill: - | Risk: -
# Registry: REGISTRY.VERSION | Input: found(entity_id, period, metric, value, threshold, explanation, record_refs)
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
```

### CORE-BASELINE
ฟังก์ชันกลางสำหรับการ์ดที่เทียบกับ baseline ของบัญชีเดียวกัน (BEH-VELOCITY, BEH-SPIKE): `beyond_baseline` ใช้เฉพาะงวดก่อนหน้าของบัญชีนั้น และเป็นสัญญาณเมื่อค่า > ค่าเฉลี่ย + k × SD
`sd_floor = "poisson"` ใช้ max(SD, √ค่าเฉลี่ย) ตาม `BEH.VELOCITY.SD_FLOOR = sqrt(mean) (Poisson)` (เฉพาะข้อมูลนับ); `baseline_formula` เขียนสูตรที่ใช้จริงพร้อมตัวเลขลงใน explanation

```python
# RECIPE CORE-BASELINE v1.0 | Skill: - | Risk: -
# Registry: - | Input: d(acct, col) sorted by time within acct
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
```

## การ์ดเตรียมข้อมูลและ Gate (ข้อ 2–4 ของขั้นตอน)

### PREP-DATE
ฟังก์ชันช่วยของ PREP-TS และค่าคงที่ของปฏิทิน (กฎนิยาม ไม่ใช่เกณฑ์ตรวจสอบ จึงไม่อยู่ใน AIDA-14): ปี ≥ 2400 ถือเป็นปี พ.ศ. และลบ 543 เป็น ค.ศ.; ชื่อเดือนย่อภาษาไทย (ม.ค. … ธ.ค. มีหรือไม่มีจุดก็ได้) แปลงเป็นเลขเดือน; วันที่ก่อนปี 1990 ในไฟล์ธุรกรรมถือว่าไม่สมเหตุสมผล (PROF-PROFILE ใช้ STOP)
`date_parts` แยกค่าข้อความเป็น (ชนิด, ช่อง 1, ช่อง 2, ปี, ส่วนเวลา) สำหรับ ISO / YYYYMMDD, วัน เดือนไทย ปี และแบบ ตัวเลข/ตัวเลข/ปี; `iso_text` เขียนกลับเป็น `YYYY-MM-DD HH:MM:SS` (ค.ศ.) เพื่อแปลงทั้งคอลัมน์ด้วยรูปแบบเดียวที่ระบุชัด

```python
# RECIPE PREP-DATE v1.0 | Skill: - | Risk: -
# Registry: - | Input: one date/time text value
import re
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
```

### PREP-TS
`to_naive_ts` แปลงคอลัมน์วันเวลาเป็น datetime แบบไม่มี timezone โดย **ตัดสินรูปแบบครั้งเดียวต่อคอลัมน์** (ไม่ใช่ทีละค่า) จึงได้ผลเหมือนกันทุกเวอร์ชันของ pandas: แบบ ตัวเลข/ตัวเลข/ปี ใช้วัน/เดือน/ปี (แบบไทย) เป็นค่าตั้งต้น และใช้เดือน/วัน/ปี เฉพาะเมื่อมีค่าที่ช่องที่ 2 > 12 และทุกค่าเข้ากับเดือน/วัน/ปีได้; ISO คงเป็น ISO; ปี พ.ศ. แปลงเป็น ค.ศ.; ชื่อเดือนไทยแปลงเป็นเลขเดือน
ค่าอื่น: เลข serial ของ Excel (ตัวเลขหรือข้อความตัวเลข) และ datetime; ค่าที่มี timezone ใช้เวลาท้องถิ่นตามที่บันทึก (ตัด timezone ไม่แปลงเป็น UTC); ค่าที่แปลงไม่ได้เป็น NaT — คืน info: date_format, be_converted, ambiguous_dates (ค่าที่วันและเดือน ≤ 12 ทั้งคู่) และ date_samples (3 คู่ ค่าเดิม → ค่าที่แปลง) ให้ผู้ใช้ยืนยันที่จุดยืนยัน 1

```python
# RECIPE PREP-TS v1.1 | Skill: - | Risk: -
# Registry: - | Input: one date/time column (dd/mm/yyyy, mm/dd/yyyy, ISO, พ.ศ., Thai month, YYYYMMDD, Excel serial, datetime)
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
```

### PREP-MAP
เปลี่ยนชื่อคอลัมน์ตาม mapping ที่ผู้ใช้ยืนยันแล้ว (จุดยืนยัน 1) เช่น `{"transactions": {"เลขที่รายการ": "tx_id"}, "accounts": {...}}`, แปลง `ts` / `opened_at` ด้วย `to_naive_ts`, `amount` เป็นตัวเลข (ตัด , ฿ และช่องว่าง) และรหัสรายการ/บัญชีเป็นข้อความ
ไม่ลบแถวใด — `tables["_prep"]` นับ ts ที่ไม่มีหรือแปลงไม่ได้, รายการโอนเข้าบัญชีตัวเอง, ยอด ≤ 0, amount ที่แปลงไม่ได้ (พร้อมตัวอย่างค่าเดิม `amount_samples` เช่น "1,000 บาท"), opened_at ของ accounts ที่ไม่มีหรือแปลงไม่ได้ (`unparsed_opened_at` จาก `opened_at_rows` บัญชี + `opened_at_samples`) และเก็บ info ของ ts (date_format, be_converted, ambiguous_dates, date_samples — แสดงให้ผู้ใช้ยืนยันที่จุดยืนยัน 1) กับ `opened_at_info` (การ์ดวิเคราะห์ตัดรายการที่ไม่ใช้เองผ่าน `clean_tx`)

```python
# RECIPE PREP-MAP v1.2 | Skill: - | Risk: -
# Registry: - | Input: raw {table: DataFrame}, mapping {table: {user column: standard column}}
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
```

### PROF-PROFILE
สร้าง Dataset Profile (คอลัมน์ item, value, detail): จำนวนรายการ, ความครบถ้วนของคอลัมน์มาตรฐาน, ช่วงเวลา, รูปแบบวันที่ที่ใช้แปลง, จำนวนบัญชี, ts ที่แปลงไม่ได้, รายการที่ไม่นำไปวิเคราะห์ (โอนเข้าบัญชีตัวเอง / ยอด ≤ 0), tx_id ซ้ำ, มีตาราง accounts หรือไม่ และ opened_at ที่แปลงไม่ได้ (เมื่อมี accounts.opened_at)
คืน status `"OK"` หรือ `"STOP: <เหตุผล>"` ตามเงื่อนไขในการ์ด PROF-CHECKS; STOP แล้วต้องแจ้งผู้ใช้และไม่รันขั้นต่อไป

```python
# RECIPE PROF-PROFILE v1.2 | Skill: - | Risk: -
# Registry: GATE.COMPLETENESS.MIN | Input: tables from PREP-MAP (transactions, accounts, _prep)
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
```

### PROF-CHECKS
ฟังก์ชันช่วยของ PROF-PROFILE: `prof_checks` คืนรายการเหตุผล STOP — ไม่มีคอลัมน์ tx_id, tx_id ว่างหรือซ้ำ (`GATE.TRACE.REQUIRED`), ts / amount / accounts.opened_at ที่ไม่มีหรือแปลงไม่ได้เกิน 1 − `GATE.COMPLETENESS.MIN = 95%` (amount และ opened_at ระบุตัวอย่างค่าที่แปลงไม่ได้ เช่น "1,000 บาท"; opened_at ตรวจเมื่อผู้ใช้จับคู่ opened_at ไว้ที่จุดยืนยัน 1 เท่านั้น — ถ้าไม่ต้องการใช้ ให้เอาออกจาก mapping แล้ว MULE-NEW-ACCT ใช้ basis=first_seen) และช่วงวันที่ไม่สมเหตุสมผล: มีวันที่ก่อนปี 1990 (`PLAUSIBLE_MIN_YEAR` ใน PREP-DATE) หรือหลังวันที่รัน (`cfg["_RUN"]["run_date"]` ถ้ามี มิฉะนั้นวันนี้) ซึ่งมักเกิดจากปี พ.ศ. หรือรูปแบบวัน/เดือนสลับกัน

```python
# RECIPE PROF-CHECKS v1.1 | Skill: - | Risk: -
# Registry: GATE.COMPLETENESS.MIN, GATE.TRACE.REQUIRED | Input: transactions(tx_id, ts), _prep from PREP-MAP
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
```

### GATE-CAPABILITY
Analysis Plan: 1 แถวต่อการ์ดวิเคราะห์ 15 ใบ (คอลัมน์ recipe_id, decision = Run / Skip, reason, missing) ตาม Template Selection / Skip Reason ใน AIDA-03 — ไม่มีการ Skip โดยไม่มีเหตุผลและข้อมูลที่ขาด
ทุกการ์ดเรียก `clean_tx` จึงต้องมี tx_id, ts, from_acct, to_acct และ amount (ไม่มี ts → Skip ทุกการ์ด เพราะกำหนด period ของ Evidence ไม่ได้); ปริมาณข้อมูลที่ทำให้การ์ดไม่มีผลแน่นอนตรวจด้วย `gate_volume` (การ์ด GATE-VOLUME); ไม่มี accounts.opened_at → MULE-NEW-ACCT Run ด้วย reason "basis=first_seen" พร้อมจำนวนบัญชีที่ไม่ได้ประเมิน (พบในช่วง MULE.NEW_ACCT_DAYS แรกของไฟล์); การ์ดสัญญาณที่ Run น้อยกว่า `MULE.MIN_SIGNALS` → MULE-PATTERN, MULE-CROSS-TX และ MULE-NETWORK Skip

```python
# RECIPE GATE-CAPABILITY v1.2 | Skill: - | Risk: -
# Registry: MULE.MIN_SIGNALS | Input: tables from PREP-MAP (transactions, accounts ถ้ามี)
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
```

### GATE-VOLUME
ฟังก์ชันช่วยของ GATE-CAPABILITY: `gate_volume` ตรวจปริมาณข้อมูลที่คำนวณได้ถูก ๆ จากรายการที่วิเคราะห์ได้ (หลัง `clean_tx`) และคืน `{recipe_id: เหตุผล Skip}` สำหรับการ์ดที่จะไม่มีผลแน่นอน แทนการรันแล้วได้ผลว่างโดยไม่บอกเหตุผล
ตรวจ: วันที่มีรายการก่อนหน้า (velocity_days) และเดือนก่อนหน้า (spike_months) ตาม `BEH.BASELINE.MIN_PERIODS`, จำนวนรายการต่อ channel ตาม `GATE.SAMPLE.MIN`, จำนวนแหล่งเงินเข้าตาม `NET.FUNNEL`, ข้อมูลเพียง 1 เดือน (CPTY-NEW-LARGE) และช่วงข้อมูลไม่เกิน `MULE.NEW_ACCT_DAYS` เมื่อใช้ basis=first_seen; key `_not_assessed` = จำนวนบัญชีที่พบใน MULE.NEW_ACCT_DAYS วันแรกของไฟล์ (MULE-NEW-ACCT แบบ first_seen ไม่ประเมิน) ให้ GATE-CAPABILITY แสดงใน reason

```python
# RECIPE GATE-VOLUME v1.1 | Skill: - | Risk: -
# Registry: BEH.BASELINE.MIN_PERIODS, GATE.SAMPLE.MIN, NET.FUNNEL, MULE.NEW_ACCT_DAYS | Input: transactions(tx_id, ts, from_acct, to_acct, amount, channel), accounts(opened_at) ถ้ามี
def gate_volume(tables: dict, cfg: dict) -> dict:
    t = clean_tx(tables["transactions"])
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
```

## การ์ดรวมผลและประเมิน (ข้อ 6–7 ของขั้นตอน)

### UNIFY-REFS
ฟังก์ชันช่วยของ UNIFY-FINDINGS และ ASSESS-CMP: `ref_list` ทำให้ record_refs เป็น list ของ tx_id เสมอ แม้ค่ามาเป็นข้อความ (เช่น `"T1, T2"` หรือ `"['T1', 'T2']"` หลังผ่าน Excel) — ไม่วนอ่านข้อความทีละตัวอักษร

```python
# RECIPE UNIFY-REFS v1.0 | Skill: - | Risk: -
# Registry: - | Input: one record_refs value (list, or text such as "T1, T2" / "['T1', 'T2']")
def ref_list(r) -> list:
    if isinstance(r, str):
        return [p.strip(" '\"") for p in r.strip().strip("[]").split(",") if p.strip(" '\"")]
    if r is None or (isinstance(r, float) and np.isnan(r)):
        return []
    return [str(x) for x in r]
def unify_refs(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: ref_list for UNIFY-FINDINGS and ASSESS-CMP
```

### UNIFY-FINDINGS
รวม Evidence เป็น Finding ตาม Schema ใน AIDA-17: Evidence ที่ entity_type + entity_id + risk + period เดียวกัน → 1 Finding; **Mule absorption:** Evidence R1 จาก NET-FUNNEL, MULE-DWELL, MULE-NEW-ACCT, BEH-VELOCITY, TEMP-OFFHOURS ของบัญชีที่มี Evidence R2 (MULE-PATTERN) ในเดือนเดียวกันถูกรวมเข้า Finding R2 (Evidence R1 อื่นของบัญชี-เดือนนั้น เช่น STAT-MAD ยังเป็น R1)
`networks` **ต้องส่งทุกครั้ง** = `tables["_out"]["mule_networks"]` (ส่ง None ได้เมื่อไม่ได้รัน MULE-NETWORK; ถ้ามี Evidence MULE-NETWORK แต่ไม่มีเครือข่ายนั้นในตาราง → ValueError แทนการให้ผลผิดเงียบ ๆ) — Evidence MULE-CROSS-TX ของสมาชิกถูกจัดเข้า Finding ของเครือข่าย (entity_type network, entity_id NET-<n>, 1 Finding ต่อเครือข่าย, period = เดือนแรก) และ skill_families นับ Evidence ทุกสมาชิก; Finding ระดับบัญชีของสมาชิกยังอยู่และมี network_id
คอลัมน์ทำงาน member_accts, record_refs, data_ref_complete, internal_amount (จาก networks) ต่อท้ายคอลัมน์ Schema ให้ ASSESS-CMP / SELECT-AUTO-TRACE ใช้ (MULE-CROSS-TX ที่ไม่อยู่ในเครือข่ายใด ยังเป็น Finding R3 ระดับบัญชี)

```python
# RECIPE UNIFY-FINDINGS v1.1 | Skill: - | Risk: -
# Registry: - | Input: evidence(Evidence schema), networks(mule_networks: network_id, member_accts, internal_amount) or None
FINDING_COLUMNS = ["finding_id", "entity_type", "entity_id", "risk", "period", "evidence_ids",
                   "skill_families", "exposure", "confidence", "materiality", "priority",
                   "review_status", "review_reason", "network_id"]
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
    in_r2 = pd.Series([k in set(zip(pat["entity_id"], pat["period"])) for k in zip(ev["entity_id"], ev["period"])],
                      index=ev.index, dtype=bool)
    acct = ev["entity_type"] == "account"
    ev.loc[acct & (ev["risk"] == "R1") & ev["recipe_id"].isin(ABSORB_SIGNALS) & in_r2, "risk"] = "R2"
    to_net = acct & (ev["risk"] == "R3") & ev["entity_id"].isin(list(net_of))
    ev.loc[to_net, "entity_id"], ev.loc[to_net, "entity_type"] = ev.loc[to_net, "entity_id"].map(net_of), "network"
    ev["pk"] = ev["period"].where(ev["entity_type"] != "network", "")  # R3: one finding per network
    rows = []
    for (et, eid, risk, _), g in ev.groupby(["entity_type", "entity_id", "risk", "pk"], sort=True):
        mem = members.get(eid, []) if et == "network" else []
        ctx = pd.concat([g, ev[(ev["entity_type"] == "account") & ev["entity_id"].isin(mem)]])
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
```

### ASSESS-CMP
ประเมิน Finding ตาม AIDA-10 / AIDA-14: **Confidence** สูง = skill family ≥ 2 และ data_ref ครบทุก Evidence / กลาง = 1 skill family และ data_ref ครบ / ต่ำ = data_ref ไม่ครบ (`ASSESS.CONFIDENCE`); **Exposure** R1/R2/R4 = ผลรวม amount ของ tx_id ที่ไม่ซ้ำใน record_refs ของ Evidence ของ Finding (tx_id ที่หาไม่พบนับเป็น 0 และ review_reason ระบุ "ไม่พบรายการอ้างอิงบางรายการ"); R3 = internal_amount ของเครือข่ายจากตาราง mule_networks
**Materiality** เทียบ exposure กับฐานที่ผู้ใช้ยืนยัน (`materiality_amount`): สูง ≥ ฐาน, กลาง ≥ `ASSESS.CLEARLY_TRIVIAL` × ฐาน, ต่ำ = ต่ำกว่านั้น; ไม่ระบุฐาน → "ไม่ได้ประเมิน" และ Priority = ระดับ Confidence; **Priority** จากตาราง `ASSESS.PRIORITY`; ทุก Finding มี review_status "รอ Human Review" และ review_reason ระบุ R2 / R3, Confidence ต่ำ และ "ไม่มีฐาน Materiality"

```python
# RECIPE ASSESS-CMP v1.1 | Skill: - | Risk: -
# Registry: ASSESS.CONFIDENCE, ASSESS.MATERIALITY, ASSESS.CLEARLY_TRIVIAL, ASSESS.PRIORITY | Input: findings(UNIFY-FINDINGS), transactions(tx_id, amount), materiality_amount
REVIEW_NOTES = {"R2": "บัญชีมีรูปแบบสอดคล้องกับ Mule Account pattern — ควรทบทวนรายบัญชี",
                "R3": "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern — ควรทบทวนทั้งกลุ่ม"}
def assess_cmp(findings: pd.DataFrame, tx: pd.DataFrame, materiality_amount, cfg: dict) -> pd.DataFrame:
    f, m = findings.copy().reset_index(drop=True), materiality_amount
    amt = pd.Series(pd.to_numeric(tx["amount"], errors="coerce").to_numpy(), index=tx["tx_id"].astype(str))
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
```

### SELECT-AUTO-TRACE
เลือกบัญชีสำหรับ FLOW-TRACE อัตโนมัติ (ข้อ 7 ของขั้นตอน): จาก Finding R2 และ R3 ที่ประเมินแล้ว เรียงตาม Priority (สูง > กลาง > ต่ำ) แล้วตาม exposure จากมากไปน้อย; Finding R3 ให้บัญชีสมาชิกทุกบัญชี (member_accts เรียงตามรหัส) พร้อมเดือนของเครือข่าย
ไม่ซ้ำบัญชี และไม่เกิน `FLOW.AUTO_MAX_ENTITIES = 10` บัญชี — คืน list ของ (บัญชี, period) ให้เรียก `flow_trace(tables, cfg, acct, direction, period)`

```python
# RECIPE SELECT-AUTO-TRACE v1.0 | Skill: - | Risk: -
# Registry: FLOW.AUTO_MAX_ENTITIES | Input: findings(ASSESS-CMP: entity_type, entity_id, risk, period, priority, exposure, member_accts)
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
```

## การ์ด Log (ข้อ 8 ของขั้นตอน)

### LOG-RUN
สร้าง Run Log ตาม Schema ใน AIDA-17 จากรายการเหตุการณ์ `[{stage, status, detail, recipe_id, recipe_version, timestamp}]`: run_id, pack_version และ input_sha256 มาจาก `cfg["_RUN"]` (input_sha256 อ่านจาก data_ref ส่วน `|sha256:` ถ้าไม่ได้ระบุ), registry_version จาก `REGISTRY.VERSION`
status ต้องเป็น OK / STOP / SKIP / REVIEW และ stage ต้องเป็น 1–18 มิฉะนั้น ValueError; ไม่ระบุ timestamp → เวลาขณะบันทึก

```python
# RECIPE LOG-RUN v1.0 | Skill: - | Risk: -
# Registry: REGISTRY.VERSION | Input: events [{stage, status, detail, recipe_id, recipe_version, timestamp}]
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
```

## การ์ด Output (ข้อ 8 ของขั้นตอน)
รันหลัง LOG-RUN ตามลำดับ OUT-BUNDLE, OUT-CELL → OUT-WORKBOOK, OUT-NETWORK-CSV, OUT-DASHBOARD — โครง sheet, คอลัมน์ CSV และ template Dashboard อยู่ใน AIDA-16
ทุก output แสดงข้อมูลเต็มตามที่ผู้ใช้/องค์กรกำหนด พร้อมป้ายเตือนข้อมูลอ่อนไหวข้อความเดียวกัน (`OUT_BANNER`) และข้อจำกัดของการหาเครือข่าย (`OUT_LIMITS`) — ถ้าองค์กรต้องการปิดบังข้อมูล แก้ที่การ์ด OUT-* จุดเดียว

### OUT-BUNDLE
รวมผลทุกขั้นเป็น `bundle` (dict) ที่การ์ด Output ทั้ง 3 ใบใช้: profile, plan, evidence, findings (ASSESS-CMP), mule_networks (`tables["_out"]`), flows (Money Flow trail ทุก trace ต่อกัน), materiality (ตาราง item / value / detail), run_log, run_id และเพิ่ม 4 key: `card_notes` (หมายเหตุข้อจำกัดของการ์ดจาก `tables["_out"]["notes"]` เช่น NET-CYCLE ค้นหาถึงขีดจำกัดในเดือนใด — ต่อท้าย Run Log เป็นแถว REVIEW stage 9 ให้เองถ้ายังไม่มี และแสดงใน README / Dashboard), `prep` (info วันที่จาก PREP-MAP), `flow_notes` (ข้อความ trace ที่ถึง `FLOW.MAX_TRAIL_ROWS` — **อ่าน `trail.attrs` ของแต่ละ trail ก่อนต่อกัน** เพราะ attrs หายเมื่อ `pd.concat`) และ `edges` (รายการใน record_refs ของ Finding = subgraph ที่เกี่ยวกับ Finding; network_id เมื่อผู้โอนและผู้รับอยู่ในเครือข่ายเดียวกัน)
`trails` = list ของผล `flow_trace` ทุกครั้ง (อัตโนมัติ + ตามคำสั่ง); `materiality_amount` = ฐานที่ผู้ใช้ยืนยันที่จุดยืนยัน 1 (None = ไม่ได้ระบุ → "ไม่ได้ประเมิน") และ `materiality_basis` = ข้อความอธิบายฐาน (แบบ ก. / ข.)

```python
# RECIPE OUT-BUNDLE v1.1 | Skill: - | Risk: -
# Registry: ASSESS.CLEARLY_TRIVIAL | Input: tables(transactions, _prep, _out), profile, plan, evidence, findings(ASSESS-CMP), trails(FLOW-TRACE), run_log, materiality_amount
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
    t = clean_tx(tables["transactions"])
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
```

### OUT-CELL
กฎกลางของค่าในไฟล์ที่เปิดด้วยโปรแกรมตารางคำนวณ (ใช้ร่วมใน OUT-WORKBOOK และ OUT-NETWORK-CSV): ข้อความที่ขึ้นต้นด้วย `=` `+` `-` `@` แท็บ หรือ carriage return ถูกเติม `'` ข้างหน้า เพื่อไม่ให้ Excel อ่านข้อมูลจากไฟล์ผู้ใช้เป็นสูตร (เช่น `=HYPERLINK(...)`) — ยกเว้นค่า `-` ตัวเดียวซึ่งเป็นค่าว่างของตาราง ไม่ใช่สูตร
`text_cols(df, fn)` ใช้ `fn` กับทุกคอลัมน์ที่ไม่ใช่ตัวเลขหรือวันเวลา

```python
# RECIPE OUT-CELL v1.0 | Skill: - | Risk: -
# Registry: - | Input: one output cell value / a DataFrame to write
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
```

### OUT-WORKBOOK
เขียน Audit Workbook (.xlsx) ด้วย openpyxl ตามโครง sheet ใน AIDA-16 ตามลำดับ: README, Dataset_Profile, Analysis_Plan, Evidence, Findings, Mule_Networks, Money_Flow, Materiality, Run_Log
Findings แสดง 14 คอลัมน์ตาม Schema + member_accts + คอลัมน์ว่าง reviewer, disposition, review_date ให้ผู้ตรวจกรอก (record_refs ดูได้ใน sheet Evidence); list / dict เขียนเป็นข้อความคั่นด้วย ", "; ตัดอักขระควบคุมที่ Excel เก็บไม่ได้ (เช่น \x0b) และกันสูตรด้วย `no_formula` (OUT-CELL); ข้อความยาวเกินที่ Excel เก็บได้ใน 1 ช่องถูกตัดและลงท้าย "…" (ดูฉบับเต็มใน CSV); Money_Flow แสดงหมายเหตุการไล่เส้นทาง (flow_notes) เหนือตาราง

```python
# RECIPE OUT-WORKBOOK v1.1 | Skill: - | Risk: -
# Registry: REGISTRY.VERSION | Input: bundle from OUT-BUNDLE, path of the .xlsx
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE  # control characters a worksheet cannot hold
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
def out_workbook(bundle: dict, path: str, cfg: dict) -> str:
    b, p = bundle, bundle.get("prep") or {}
    readme = [OUT_BANNER, f"run_id: {b['run_id']} | Registry version: {cfg['REGISTRY.VERSION']}", OUT_LIMITS,
              f"รูปแบบวันที่ที่ใช้แปลง: {p.get('date_format', '-')} | แปลงปี พ.ศ.: {'ใช่' if p.get('be_converted') else 'ไม่'}"
              f" | วันและเดือน ≤ 12 ทั้งคู่ {p.get('ambiguous_dates', 0)} รายการ", *b.get("card_notes", []), *b["flow_notes"],
              "วิธีอ่านไฟล์ (sheet ตามลำดับ):"] + [f"{k}: {v}" for k, v in OUT_SHEETS.items()]
    f = b["findings"]
    fnd = f[FINDING_COLUMNS].assign(member_accts=f["member_accts"], reviewer=None, disposition=None, review_date=None)
    notes = b["flow_notes"] or ["ไล่เส้นทางเงินครบทุก trace (ไม่ถึงขีดจำกัด FLOW.MAX_TRAIL_ROWS)"]
    sheets = {"README": pd.DataFrame({"README": readme}), "Dataset_Profile": b["profile"], "Analysis_Plan": b["plan"],
              "Evidence": b["evidence"], "Findings": fnd, "Mule_Networks": b["mule_networks"],
              "Money_Flow": b["flows"], "Materiality": b["materiality"], "Run_Log": b["run_log"]}
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            top = len(notes) + 1 if name == "Money_Flow" else 0
            text_cols(df, cell_text).to_excel(xw, sheet_name=name, index=False, startrow=top)
            for i, n in enumerate(notes if top else [], 1):
                xw.sheets[name].cell(row=i, column=1, value=cell_text(n))
    return path
```

### OUT-NETWORK-CSV
เขียน Network Investigation Package ลงโฟลเดอร์ `folder` (UTF-8 with BOM ให้ Excel อ่านภาษาไทยได้; ข้อความกันสูตรด้วย `no_formula` ของ OUT-CELL): `nodes.csv` (node_id, role, network_id, finding_ids), `edges.csv` (source, target, amount, ts, tx_id, network_id) และ `flows.csv` (Money Flow trail) — คอลัมน์ตาม AIDA-16
เฉพาะ subgraph ที่เกี่ยวกับ Finding: node = บัญชีที่มี Finding หรืออยู่บน edge; role จาก mule_networks.roles (สมาชิกเครือข่าย), "mule" สำหรับบัญชีที่มี Finding R2 นอกเครือข่าย และ "other" สำหรับบัญชีอื่น; finding_ids คั่นด้วย "; " (สมาชิกเครือข่ายมี Finding R3 ของเครือข่ายด้วย)

```python
# RECIPE OUT-NETWORK-CSV v1.0 | Skill: - | Risk: -
# Registry: - | Input: bundle from OUT-BUNDLE (findings, mule_networks, edges, flows), output folder
import os
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
```

### OUT-DASHBOARD
สร้าง HTML Interactive Dashboard ไฟล์เดียวจาก template ใน AIDA-16 (ส่ง `template` = ข้อความใน block ```html ของ AIDA-16 ทั้งหมด ตามตัวอักษร): แทน placeholder `/*__AIDA_DATA__*/` ด้วย JSON ของ bundle (ตาราง → list ของแถว, วันเวลาเป็น ISO) โดยแปลง "<" เป็น `<` เพื่อไม่ให้ข้อมูลปิดแท็ก script ได้
template ไม่ครบ (ไม่มี placeholder 1 จุด หรือไม่มีบรรทัด `<!-- END-OF-TEMPLATE -->`) → ValueError — ห้ามเขียน template เอง ให้ดึง AIDA-16 ใหม่

```python
# RECIPE OUT-DASHBOARD v1.1 | Skill: - | Risk: -
# Registry: REGISTRY.VERSION | Input: bundle from OUT-BUNDLE, template (```html block of AIDA-16), path of the .html
DASH_PLACEHOLDER, DASH_END = "/*__AIDA_DATA__*/", "<!-- END-OF-TEMPLATE -->"
def out_dashboard(bundle: dict, template: str, path: str, cfg: dict) -> str:
    if template.count(DASH_PLACEHOLDER) != 1 or DASH_END not in template:
        raise ValueError(f"template Dashboard จาก AIDA-16 ไม่ครบ (ต้องมี {DASH_PLACEHOLDER} 1 จุด และบรรทัด {DASH_END}) "
                         "— ดึง template จาก AIDA-16 ใหม่ทั้งหมด ห้ามเขียนหรือแก้ template เอง")
    def rows(df):
        return json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
    f, e = bundle["findings"], bundle["edges"]
    keep = [c for c in FINDING_COLUMNS + ["member_accts", "record_refs"] if c in f.columns]
    ui = {k: rows(bundle[k]) for k in ("profile", "plan", "evidence", "mule_networks", "flows",
                                       "materiality", "run_log")}
    ui.update(findings=rows(f[keep]), edges=rows(e[e["network_id"].notna()]), run_id=bundle["run_id"],
              flow_notes=bundle["flow_notes"], card_notes=bundle.get("card_notes", []),
              prep=bundle.get("prep", {}), limits=OUT_LIMITS,
              registry_version=cfg["REGISTRY.VERSION"])
    data = json.dumps(ui, ensure_ascii=False, default=str).replace("<", "\\u003c")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(template.replace(DASH_PLACEHOLDER, data))
    return path
```

## ข้อห้าม (Guardrails)
- รันการ์ดตามที่เขียนไว้ทุกตัวอักษร (verbatim) ห้ามแก้โค้ด ห้ามเขียนการ์ดขึ้นเอง และต้องรัน CORE-EVIDENCE และ CORE-BASELINE ก่อนการ์ดใน AIDA-18
- ถ้าดึงการ์ดมาไม่ครบ (โค้ดถูกตัด, ไม่มีบรรทัดปิด) ห้ามรันส่วนที่ได้มา — Skip การ์ดนั้นพร้อม reason "ดึง recipe ไม่ครบ"
- ผลของการ์ดเป็นสัญญาณให้ตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุปว่าบัญชีหรือบุคคลกระทำผิด — ใช้ถ้อยคำตาม AIDA-11
- ห้ามแต่งค่า `tx_id` หรือ `data_ref` ที่ไม่มีในข้อมูลจริง และห้ามเปลี่ยนคอลัมน์ Evidence นอก Schema ใน AIDA-17

## ไฟล์ที่เกี่ยวข้อง
- AIDA-18 Analysis Recipes (การ์ดวิเคราะห์ที่เรียกใช้ CORE-EVIDENCE)
- AIDA-16 Output Templates (โครง sheet, คอลัมน์ CSV และ template Dashboard ที่การ์ด OUT-* ใช้)
- AIDA-17 Data & Evidence Schema (คอลัมน์ Evidence)
- AIDA-14 Configuration Registry (Machine Config, `REGISTRY.VERSION = 1.1`)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
- AIDA-13 Traceability & Governance (record_refs + data_ref)
