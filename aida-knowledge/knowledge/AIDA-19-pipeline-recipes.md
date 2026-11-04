# AIDA-19 · Pipeline Recipes (การ์ดเตรียมข้อมูล, Evidence builder, รวมผล และ Output)
> ไฟล์: AIDA-19 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: การ์ด CORE-EVIDENCE สร้างแถว Evidence อย่างไร, กฎกลางที่ทุกการ์ดวิเคราะห์ใช้ร่วมกันคืออะไร (ตัดรายการโอนเข้าบัญชีตัวเอง / ยอด ≤ 0), ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดใน AIDA-18 หรือไม่, เตรียมข้อมูล / Dataset Profile / Analysis Plan (Run/Skip) ทำอย่างไร, รวม Evidence เป็น Finding และประเมิน Confidence / Exposure / Materiality / Priority อย่างไร, เลือกบัญชีไล่เส้นทางเงินอัตโนมัติและบันทึก Run Log อย่างไร

## สรุปสั้น
ไฟล์นี้เก็บการ์ด (recipe) ระดับ pipeline ที่ Code Interpreter รันตามลำดับในข้อ 7 ของ Instructions — **ต้องรันการ์ดในไฟล์นี้ก่อนการ์ดวิเคราะห์ใน AIDA-18** เพราะการ์ดวิเคราะห์ทุกใบเรียกใช้ฟังก์ชันจาก `CORE-EVIDENCE` และ `CORE-BASELINE`
ลำดับ: CORE-EVIDENCE, CORE-BASELINE → PREP-TS, PREP-MAP → PROF-PROFILE (STOP แล้วหยุด) → GATE-CAPABILITY, GATE-VOLUME → การ์ดใน AIDA-18 ตาม Analysis Plan → UNIFY-FINDINGS → ASSESS-CMP → SELECT-AUTO-TRACE + FLOW-TRACE → LOG-RUN; การ์ด OUT-WORKBOOK, OUT-NETWORK-CSV และ OUT-DASHBOARD จะเพิ่มต่อท้ายไฟล์นี้
คอลัมน์ Evidence เป็นไปตาม Schema ใน AIDA-17 และทุกแถวบันทึก Registry version จาก AIDA-14

## การ์ด Evidence builder

### CORE-EVIDENCE
ฟังก์ชันกลางที่การ์ดวิเคราะห์ทุกใบใช้: `clean_tx` (ตัดรายการโอนเข้าบัญชีตัวเอง, ยอด ≤ 0 และรายการที่ไม่มีวันเวลา, แปลง ts, เพิ่ม period YYYY-MM), `one_per_month` (1 แถวต่อบัญชีต่อเดือน) และ `evidence_rows` (สร้างแถวตาม Evidence schema)
การ์ดนี้ไม่มีเกณฑ์ใด ๆ — อ่านเพียง `REGISTRY.VERSION` และ `cfg["_RUN"]` (run_id, data_ref)

```python
# RECIPE CORE-EVIDENCE v1.0 | Skill: - | Risk: -
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

### PREP-TS
ฟังก์ชันช่วยของ PREP-MAP: `to_naive_ts` แปลงคอลัมน์วันเวลาที่ปนหลายรูปแบบ (ข้อความรูปแบบต่าง ๆ, YYYYMMDD, เลข serial ของ Excel ทั้งที่เป็นตัวเลขและข้อความ, datetime และค่าที่มี timezone) เป็น datetime แบบไม่มี timezone ทีละค่าที่ไม่ซ้ำ
ค่าที่มี timezone ใช้เวลาท้องถิ่นตามที่บันทึก (ตัด timezone ออก ไม่แปลงเป็น UTC) เพื่อให้ TEMP-OFFHOURS เทียบเวลาทำการได้ถูก; ค่าที่แปลงไม่ได้เป็น NaT และนับใน Dataset Profile

```python
# RECIPE PREP-TS v1.0 | Skill: - | Risk: -
# Registry: - | Input: one date/time column (text in any format, YYYYMMDD, Excel serial days, datetime, tz-aware)
EXCEL_EPOCH = pd.Timestamp("1899-12-30")  # Excel serial day 0 (1900 date system)
EXCEL_MAX_SERIAL = 2958465  # 9999-12-31, the last date Excel can store
def _ts_one(x):
    if isinstance(x, str):
        x = x.strip()
        if len(x) == 8 and x.isdigit():  # YYYYMMDD
            return pd.to_datetime(x, format="%Y%m%d", errors="coerce")
        if x.replace(".", "", 1).isdigit():
            x = float(x)
    if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, (bool, np.bool_)):
        if not 0 < x <= EXCEL_MAX_SERIAL:
            return pd.NaT
        return (EXCEL_EPOCH + pd.Timedelta(days=float(x))).round("s")
    try:
        v = pd.Timestamp(x)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT
    return v.tz_localize(None) if v is not pd.NaT and v.tzinfo is not None else v
def to_naive_ts(s: pd.Series) -> pd.Series:
    # naive wall-clock datetimes: a time-zone offset is dropped, not converted
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.tz_localize(None) if getattr(s.dt, "tz", None) is not None else s
    parsed = {x: _ts_one(x) for x in s.dropna().unique()}
    return pd.to_datetime(s.map(parsed), errors="coerce")
def prep_ts(tables: dict = None, cfg: dict = None) -> None:
    return None  # helper card: defines to_naive_ts for PREP-MAP
```

### PREP-MAP
เปลี่ยนชื่อคอลัมน์ตาม mapping ที่ผู้ใช้ยืนยันแล้ว (จุดยืนยัน 1) เช่น `{"transactions": {"เลขที่รายการ": "tx_id"}, "accounts": {...}}`, แปลง `ts` / `opened_at` ด้วย `to_naive_ts`, `amount` เป็นตัวเลข (ตัด , ฿ และช่องว่าง) และรหัสรายการ/บัญชีเป็นข้อความ
ไม่ลบแถวใด — นับไว้ใน `tables["_prep"]`: ts ที่ไม่มีหรือแปลงไม่ได้, รายการโอนเข้าบัญชีตัวเอง, ยอด ≤ 0 และ amount ที่แปลงไม่ได้ (การ์ดวิเคราะห์ตัดรายการเหล่านี้เองผ่าน `clean_tx`)

```python
# RECIPE PREP-MAP v1.0 | Skill: - | Risk: -
# Registry: - | Input: raw {table: DataFrame}, mapping {table: {user column: standard column}}
def prep_map(raw: dict, mapping: dict, cfg: dict) -> dict:
    tables = {}
    for name, df in raw.items():
        t = df.rename(columns=(mapping or {}).get(name, {})).copy()
        for c in ("ts", "opened_at"):
            if c in t.columns:
                t[c] = to_naive_ts(t[c])
        for c in ("tx_id", "from_acct", "to_acct", "acct_id"):
            if c in t.columns:
                t[c] = t[c].map(lambda x: x if pd.isna(x) else str(x).strip())
        if "amount" in t.columns:
            a = t["amount"].map(lambda x: x.replace(",", "").replace("฿", "").strip()
                                if isinstance(x, str) else x)
            t["amount"] = pd.to_numeric(a, errors="coerce").astype(float)
        tables[name] = t
    tx = tables.get("transactions", pd.DataFrame())
    def has(*cols):
        return all(c in tx.columns for c in cols)
    tables["_prep"] = {
        "unparsed_ts": int(tx["ts"].isna().sum()) if has("ts") else 0,
        "excluded_self": int((tx["from_acct"] == tx["to_acct"]).sum()) if has("from_acct", "to_acct") else 0,
        "excluded_nonpositive": int((tx["amount"] <= 0).sum()) if has("amount") else 0,
        "unparsed_amount": int(tx["amount"].isna().sum()) if has("amount") else 0}
    return tables
```

### PROF-PROFILE
สร้าง Dataset Profile (คอลัมน์ item, value, detail): จำนวนรายการ, ความครบถ้วนของคอลัมน์มาตรฐาน, ช่วงเวลา, จำนวนบัญชี, ts ที่แปลงไม่ได้, รายการที่ไม่นำไปวิเคราะห์ (โอนเข้าบัญชีตัวเอง / ยอด ≤ 0), tx_id ซ้ำ และมีตาราง accounts หรือไม่
คืน status `"OK"` หรือ `"STOP: <เหตุผล>"` — STOP เมื่อไม่มีคอลัมน์ tx_id, tx_id ว่างหรือซ้ำ (`GATE.TRACE.REQUIRED`) หรือ ts ที่แปลงไม่ได้เกิน 1 − `GATE.COMPLETENESS.MIN = 95%`; STOP แล้วต้องแจ้งผู้ใช้และไม่รันขั้นต่อไป

```python
# RECIPE PROF-PROFILE v1.0 | Skill: - | Risk: -
# Registry: GATE.COMPLETENESS.MIN, GATE.TRACE.REQUIRED | Input: tables from PREP-MAP (transactions, accounts, _prep)
PROFILE_TX_COLUMNS = ["tx_id", "ts", "from_acct", "to_acct", "amount", "currency", "channel"]
def prof_profile(tables: dict, cfg: dict) -> tuple:
    tx, prep, lim = tables["transactions"], tables.get("_prep", {}), cfg["GATE.COMPLETENESS.MIN"]
    n, rows, stop = len(tx), [], []
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
    if "from_acct" in tx.columns and "to_acct" in tx.columns:
        add("จำนวนบัญชี", int(pd.concat([tx["from_acct"], tx["to_acct"]]).nunique()))
    add("ts ที่ไม่มีหรือแปลงเป็นวันเวลาไม่ได้", prep.get("unparsed_ts", 0))
    add("amount ที่ไม่มีหรือแปลงเป็นตัวเลขไม่ได้ (ไม่นำไปวิเคราะห์)", prep.get("unparsed_amount", 0))
    add("รายการโอนเข้าบัญชีตัวเอง (ไม่นำไปวิเคราะห์)", prep.get("excluded_self", 0))
    add("รายการยอด ≤ 0 (ไม่นำไปวิเคราะห์)", prep.get("excluded_nonpositive", 0))
    acc = tables.get("accounts")
    add("ตาราง accounts", "มี" if acc is not None else "ไม่มี", "" if acc is not None else "MULE-NEW-ACCT ใช้ basis=first_seen")
    if "tx_id" not in tx.columns:
        stop.append("ไม่มีคอลัมน์ tx_id (record key) ตาม GATE.TRACE.REQUIRED จึงอ้างอิงรายการต้นทางไม่ได้")
    else:
        ids = tx["tx_id"]
        dup = sorted(str(x) for x in ids[ids.duplicated(keep=False) & ids.notna()].unique())
        add("tx_id ซ้ำ (จำนวนค่า)", len(dup), ", ".join(dup[:10]))
        if ids.isna().any():
            stop.append(f"tx_id ว่าง {int(ids.isna().sum())} รายการ — record key ไม่ครบตาม GATE.TRACE.REQUIRED")
        if dup:
            stop.append(f"tx_id ซ้ำ {len(dup)} ค่า (เช่น {', '.join(dup[:5])}) — record key ไม่ unique ตาม GATE.TRACE.REQUIRED")
    bad = prep.get("unparsed_ts", 0) / n if n and "ts" in tx.columns else 0.0
    if bad > 1 - lim:
        stop.append(f"ts ไม่มีหรือแปลงเป็นวันเวลาไม่ได้ {bad:.1%} มากกว่า {1 - lim:.0%} (1 − GATE.COMPLETENESS.MIN)")
    return pd.DataFrame(rows, columns=["item", "value", "detail"]), ("STOP: " + "; ".join(stop) if stop else "OK")
```

### GATE-CAPABILITY
Analysis Plan: 1 แถวต่อการ์ดวิเคราะห์ 15 ใบ (คอลัมน์ recipe_id, decision = Run / Skip, reason, missing) ตาม Template Selection / Skip Reason ใน AIDA-03 — ไม่มีการ Skip โดยไม่มีเหตุผลและข้อมูลที่ขาด
ทุกการ์ดเรียก `clean_tx` จึงต้องมี tx_id, ts, from_acct, to_acct และ amount (ไม่มี ts → Skip ทุกการ์ด เพราะกำหนด period ของ Evidence ไม่ได้); ปริมาณข้อมูลที่ทำให้การ์ดไม่มีผลแน่นอนตรวจด้วย `gate_volume` (การ์ด GATE-VOLUME); ไม่มี accounts.opened_at → MULE-NEW-ACCT Run ด้วย reason "basis=first_seen"; การ์ดสัญญาณที่ Run น้อยกว่า `MULE.MIN_SIGNALS` → MULE-PATTERN, MULE-CROSS-TX และ MULE-NETWORK Skip

```python
# RECIPE GATE-CAPABILITY v1.0 | Skill: - | Risk: -
# Registry: MULE.MIN_SIGNALS | Input: tables from PREP-MAP (transactions, accounts ถ้ามี)
GATE_CARDS = ["STAT-MAD", "BEH-VELOCITY", "BEH-SPIKE", "TEMP-OFFHOURS", "NET-CYCLE", "NET-FUNNEL",
              "MULE-DWELL", "MULE-NEW-ACCT", "MULE-PATTERN", "MULE-CROSS-TX", "MULE-NETWORK",
              "CPTY-PROFILE", "CPTY-NEW-LARGE", "FLOW-TRACE", "FLOW-LAYERING"]
GATE_BASE = ["tx_id", "ts", "from_acct", "to_acct", "amount"]  # clean_tx in every card needs all five
GATE_SIGNALS = ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "TEMP-OFFHOURS"]
def gate_capability(tables: dict, cfg: dict) -> pd.DataFrame:
    tx, acc = tables["transactions"], tables.get("accounts")
    miss = [c for c in GATE_BASE if c not in tx.columns or tx[c].notna().sum() == 0]
    vol = gate_volume(tables, cfg) if not miss else {}
    basis = "opened_at" if acc is not None and "opened_at" in acc.columns else "first_seen"
    plan = {}
    for r in GATE_CARDS:
        if miss:
            plan[r] = ("Skip", f"ไม่มีคอลัมน์ {', '.join(miss)} ซึ่งการ์ดต้องใช้ (ts ใช้เรียงลำดับเวลาและกำหนด period "
                       "ของ Evidence; tx_id ใช้อ้างอิงรายการต้นทาง) จึงรันการ์ดนี้ไม่ได้", ", ".join(miss))
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
            plan["MULE-NEW-ACCT"] = ("Run", "basis=first_seen (ไม่มี accounts.opened_at จึงใช้วันที่พบรายการแรก"
                                     "ในไฟล์ ซึ่งอาจไม่ใช่วันเปิดบัญชีจริง)", "accounts.opened_at")
        n_sig, need = sum(plan[r][0] == "Run" for r in GATE_SIGNALS), cfg["MULE.MIN_SIGNALS"]
        if n_sig < need:
            plan["MULE-PATTERN"] = ("Skip", f"การ์ดสัญญาณที่รันได้มี {n_sig} จาก {len(GATE_SIGNALS)} ใบ น้อยกว่า "
                                    f"MULE.MIN_SIGNALS ({need} สัญญาณ ค่ามาตรฐานจาก AIDA-14) จึงไม่มีบัญชีใดเข้ารูปแบบได้",
                                    "ปริมาณข้อมูลไม่พอ")
        if plan["MULE-PATTERN"][0] == "Skip":
            for r in ("MULE-CROSS-TX", "MULE-NETWORK"):
                plan[r] = ("Skip", "MULE-PATTERN ถูก Skip จึงไม่มีชุดบัญชีที่สอดคล้องกับ Mule Account pattern "
                           "ให้วิเคราะห์ข้ามบัญชี", "MULE-PATTERN")
    return pd.DataFrame([(r, *plan[r]) for r in GATE_CARDS], columns=["recipe_id", "decision", "reason", "missing"])
```

### GATE-VOLUME
ฟังก์ชันช่วยของ GATE-CAPABILITY: `gate_volume` ตรวจปริมาณข้อมูลที่คำนวณได้ถูก ๆ จากรายการที่วิเคราะห์ได้ (หลัง `clean_tx`) และคืน `{recipe_id: เหตุผล Skip}` สำหรับการ์ดที่จะไม่มีผลแน่นอน แทนการรันแล้วได้ผลว่างโดยไม่บอกเหตุผล
ตรวจ: วันที่มีรายการก่อนหน้า (velocity_days) และเดือนก่อนหน้า (spike_months) ตาม `BEH.BASELINE.MIN_PERIODS`, จำนวนรายการต่อ channel ตาม `GATE.SAMPLE.MIN`, จำนวนแหล่งเงินเข้าตาม `NET.FUNNEL`, ข้อมูลเพียง 1 เดือน (CPTY-NEW-LARGE) และช่วงข้อมูลไม่เกิน `MULE.NEW_ACCT_DAYS` เมื่อใช้ basis=first_seen

```python
# RECIPE GATE-VOLUME v1.0 | Skill: - | Risk: -
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
    if (acc is None or "opened_at" not in acc.columns) and span <= nd:
        out["MULE-NEW-ACCT"] = (f"ไม่มี opened_at (basis=first_seen) และข้อมูลครอบคลุม {span} วัน ไม่เกิน "
                                f"MULE.NEW_ACCT_DAYS ({nd} วัน{k}) จึงแยกบัญชีใหม่จากบัญชีที่มีอยู่ก่อนช่วงข้อมูลไม่ได้")
    return out
```

## การ์ดรวมผลและประเมิน (ข้อ 6–7 ของขั้นตอน)

### UNIFY-FINDINGS
รวม Evidence เป็น Finding ตาม Schema ใน AIDA-17: Evidence ที่ entity_type + entity_id + risk + period เดียวกัน → 1 Finding; **Mule absorption:** Evidence R1 จาก NET-FUNNEL, MULE-DWELL, MULE-NEW-ACCT, BEH-VELOCITY, TEMP-OFFHOURS ของบัญชีที่มี Evidence R2 (MULE-PATTERN) ในเดือนเดียวกันถูกรวมเข้า Finding R2 (Evidence R1 อื่นของบัญชี-เดือนนั้น เช่น STAT-MAD ยังเป็น R1)
R3: ส่ง `networks` = `tables["_out"]["mule_networks"]` — Evidence MULE-CROSS-TX ของสมาชิกถูกจัดเข้า Finding ของเครือข่าย (entity_type network, entity_id NET-<n>, 1 Finding ต่อเครือข่าย, period = เดือนแรก) และ skill_families นับ Evidence ทุกสมาชิก; Finding ระดับบัญชีของสมาชิกยังอยู่และมี network_id; คอลัมน์ทำงาน member_accts, record_refs, data_ref_complete ต่อท้ายคอลัมน์ Schema ให้ ASSESS-CMP / SELECT-AUTO-TRACE ใช้ (MULE-CROSS-TX ที่ไม่อยู่ในเครือข่ายใด ยังเป็น Finding R3 ระดับบัญชี)

```python
# RECIPE UNIFY-FINDINGS v1.0 | Skill: - | Risk: -
# Registry: - | Input: evidence(Evidence schema), networks(mule_networks: network_id, member_accts) ถ้ามี
FINDING_COLUMNS = ["finding_id", "entity_type", "entity_id", "risk", "period", "evidence_ids",
                   "skill_families", "exposure", "confidence", "materiality", "priority",
                   "review_status", "review_reason", "network_id"]
FINDING_WORK_COLUMNS = ["member_accts", "record_refs", "data_ref_complete"]  # for ASSESS-CMP / SELECT-AUTO-TRACE
ABSORB_SIGNALS = ["NET-FUNNEL", "MULE-DWELL", "MULE-NEW-ACCT", "BEH-VELOCITY", "TEMP-OFFHOURS"]
def unify_findings(evidence: pd.DataFrame, cfg: dict, networks: pd.DataFrame = None) -> pd.DataFrame:
    cols = FINDING_COLUMNS + FINDING_WORK_COLUMNS
    if evidence is None or len(evidence) == 0:
        return pd.DataFrame(columns=cols)
    ev = evidence.reset_index(drop=True).copy()
    ev["ok"] = ev["data_ref"].fillna("").astype(str).str.strip() != ""
    nets = networks if networks is not None else pd.DataFrame(columns=["network_id", "member_accts"])
    members = {n: sorted(m) for n, m in zip(nets["network_id"], nets["member_accts"])}
    net_of = {a: n for n, m in members.items() for a in m}
    pat = ev[ev["recipe_id"] == "MULE-PATTERN"]
    r2 = set(zip(pat["entity_id"], pat["period"]))
    acct = ev["entity_type"] == "account"
    in_r2 = pd.Series([k in r2 for k in zip(ev["entity_id"], ev["period"])], index=ev.index, dtype=bool)
    ev.loc[acct & (ev["risk"] == "R1") & ev["recipe_id"].isin(ABSORB_SIGNALS) & in_r2, "risk"] = "R2"
    to_net = acct & (ev["risk"] == "R3") & ev["entity_id"].isin(list(net_of))
    ev.loc[to_net, "entity_id"] = ev.loc[to_net, "entity_id"].map(net_of)
    ev.loc[to_net, "entity_type"] = "network"
    ev["pk"] = ev["period"].where(ev["entity_type"] != "network", "")  # R3: one finding per network
    rows = []
    for (et, eid, risk, _), g in ev.groupby(["entity_type", "entity_id", "risk", "pk"], sort=True):
        mem = members.get(eid, []) if et == "network" else []
        ctx = pd.concat([g, ev[(ev["entity_type"] == "account") & ev["entity_id"].isin(mem)]])
        rows.append({"entity_type": et, "entity_id": eid, "risk": risk, "period": g["period"].min(),
                     "evidence_ids": list(g["evidence_id"]), "skill_families": sorted(set(ctx["skill_family"])),
                     "network_id": eid if et == "network" else net_of.get(eid), "member_accts": mem,
                     "record_refs": sorted({str(x) for r in g["record_refs"] for x in r}),
                     "data_ref_complete": bool(ctx["ok"].all())})
    f = pd.DataFrame(rows).sort_values(["risk", "entity_type", "entity_id", "period"], kind="mergesort")
    f["finding_id"] = [f"FND-{cfg['_RUN']['run_id']}-{i + 1}" for i in range(len(f))]
    for c in cols:  # exposure, confidence, materiality, priority, review_* come from ASSESS-CMP
        if c not in f.columns:
            f[c] = None
    return f[cols].reset_index(drop=True)
```

### ASSESS-CMP
ประเมิน Finding ตาม AIDA-10 / AIDA-14: **Confidence** สูง = skill family ≥ 2 และ data_ref ครบทุก Evidence / กลาง = 1 skill family และ data_ref ครบ / ต่ำ = data_ref ไม่ครบ (`ASSESS.CONFIDENCE`); **Exposure** = ผลรวม amount ของ tx_id ที่ไม่ซ้ำใน record_refs ของ Evidence ของ Finding (R3 = ธุรกรรมภายในเครือข่ายทั้งหมดใน Evidence MULE-NETWORK จึงเท่ากับ internal_amount)
**Materiality** เทียบ exposure กับฐานที่ผู้ใช้ยืนยัน (`materiality_amount`): สูง ≥ ฐาน, กลาง ≥ `ASSESS.CLEARLY_TRIVIAL` × ฐาน, ต่ำ = ต่ำกว่านั้น; ไม่ระบุฐาน → "ไม่ได้ประเมิน" และ Priority = ระดับ Confidence; **Priority** จากตาราง `ASSESS.PRIORITY`; ทุก Finding มี review_status "รอ Human Review" และ review_reason ระบุ R2 / R3, Confidence ต่ำ และ "ไม่มีฐาน Materiality"

```python
# RECIPE ASSESS-CMP v1.0 | Skill: - | Risk: -
# Registry: ASSESS.CONFIDENCE, ASSESS.MATERIALITY, ASSESS.CLEARLY_TRIVIAL, ASSESS.PRIORITY | Input: findings(UNIFY-FINDINGS), transactions(tx_id, amount), materiality_amount
REVIEW_NOTES = {"R2": "บัญชีมีรูปแบบสอดคล้องกับ Mule Account pattern — ควรทบทวนรายบัญชี",
                "R3": "กลุ่มบัญชีที่มีธุรกรรมเชื่อมโยงกันและสอดคล้องกับ Mule Account pattern — ควรทบทวนทั้งกลุ่ม"}
def assess_cmp(findings: pd.DataFrame, tx: pd.DataFrame, materiality_amount, cfg: dict) -> pd.DataFrame:
    f, m = findings.copy().reset_index(drop=True), materiality_amount
    amt = pd.Series(pd.to_numeric(tx["amount"], errors="coerce").to_numpy(), index=tx["tx_id"].astype(str))
    amt = amt[~amt.index.duplicated()]
    f["exposure"] = [round(float(amt.reindex(sorted({str(x) for x in r})).sum()), 2) for r in f["record_refs"]]
    n_fam = f["skill_families"].map(len)
    f["confidence"] = ["ต่ำ" if not ok else "สูง" if n >= 2 else "กลาง"  # ASSESS.CONFIDENCE: >= 2 families
                       for ok, n in zip(f["data_ref_complete"].astype(bool), n_fam)]
    if m is None:
        f["materiality"], f["priority"] = "ไม่ได้ประเมิน", f["confidence"]
    else:
        ct = cfg["ASSESS.CLEARLY_TRIVIAL"]
        f["materiality"] = ["สูง" if e >= m else "กลาง" if e >= ct * m else "ต่ำ" for e in f["exposure"]]
        f["priority"] = [cfg["ASSESS.PRIORITY"][c][x] for c, x in zip(f["confidence"], f["materiality"])]
    def reason(risk, conf):
        notes = [REVIEW_NOTES[risk]] if risk in REVIEW_NOTES else []
        if conf == "ต่ำ":
            notes.append("Confidence ต่ำ เพราะ data_ref ของ Evidence ไม่ครบ — ต้องยืนยันแหล่งข้อมูลก่อนใช้ผล")
        if m is None:
            notes.append("ไม่มีฐาน Materiality")
        return "; ".join(notes) if notes else "-"
    f["review_status"] = "รอ Human Review"
    f["review_reason"] = [reason(r, c) for r, c in zip(f["risk"], f["confidence"])]
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

## ข้อห้าม (Guardrails)
- รันการ์ดตามที่เขียนไว้ทุกตัวอักษร (verbatim) ห้ามแก้โค้ด ห้ามเขียนการ์ดขึ้นเอง และต้องรัน CORE-EVIDENCE และ CORE-BASELINE ก่อนการ์ดใน AIDA-18
- ถ้าดึงการ์ดมาไม่ครบ (โค้ดถูกตัด, ไม่มีบรรทัดปิด) ห้ามรันส่วนที่ได้มา — Skip การ์ดนั้นพร้อม reason "ดึง recipe ไม่ครบ"
- ผลของการ์ดเป็นสัญญาณให้ตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุปว่าบัญชีหรือบุคคลกระทำผิด — ใช้ถ้อยคำตาม AIDA-11
- ห้ามแต่งค่า `tx_id` หรือ `data_ref` ที่ไม่มีในข้อมูลจริง และห้ามเปลี่ยนคอลัมน์ Evidence นอก Schema ใน AIDA-17

## ไฟล์ที่เกี่ยวข้อง
- AIDA-18 Analysis Recipes (การ์ดวิเคราะห์ที่เรียกใช้ CORE-EVIDENCE)
- AIDA-17 Data & Evidence Schema (คอลัมน์ Evidence)
- AIDA-14 Configuration Registry (Machine Config, `REGISTRY.VERSION = 1.1`)
- AIDA-11 Audit Procedures & Language (ถ้อยคำที่ใช้)
- AIDA-13 Traceability & Governance (record_refs + data_ref)
