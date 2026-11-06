"""Generate knowledge/AIDA-18-risk-library.md from the engine's RISK_LIBRARY and CHECKS.

Usage: python3 build_risk_library_md.py [pack_dir] [--check]
pack_dir defaults to the aida-knowledge/ folder that contains this script.
--check only compares (exit 1 when AIDA-18 differs from what the engine gives).

AIDA-18 is never edited by hand: the risks, check lists, roles, minimum data and registry keys come from the
engine; the Thai prose about each check lives in CHECK_TEXT below (the engine has no Thai check descriptions).
validate_pack.py regenerates the file and fails when it differs.
"""
import importlib.util
import sys
from pathlib import Path

OUT_NAME = "AIDA-18-risk-library.md"
ENGINE_REL = Path("engine") / "aida_engine.py"

TYPE_TEXT = {"E": "E โอนเงินระหว่างบัญชี", "C": "C รับชำระค่างวดสินเชื่อ", "A": "A จ่ายเงินเจ้าหนี้"}
GROUPS = [("ความเสี่ยงของข้อมูลโอนเงิน (E) — R1–R4 เดิมของ B1", ("R1", "R2", "R3", "R4")),
          ("ความเสี่ยงทั่วไป (ใช้ได้ทุกประเภทข้อมูล)", ("G-R1", "G-R2", "G-R3", "G-R4")),
          ("ความเสี่ยงสินเชื่อ / ชำระค่างวด (C)", ("C-R1", "C-R2", "C-R3")),
          ("ความเสี่ยงบัญชีเจ้าหนี้ / จ่ายผู้ขาย (A)", ("A-R1", "A-R2", "A-R3", "A-R4"))]

# Thai name and what each certified check looks for (no code, no numbers: thresholds stay in AIDA-14).
CHECK_TEXT = {
    "STAT-MAD": ("ยอดโดดเด่น (MAD)",
                 "เทียบยอดแต่ละรายการกับค่ากลางของกลุ่ม (แยกตาม channel ถ้ามี) ด้วย modified z-score จาก MAD "
                 "รายการที่ห่างจากค่ากลางเกินเกณฑ์เป็นสัญญาณยอดโดดเด่น"),
    "BEH-VELOCITY": ("ความถี่ผิดปกติ (Velocity)",
                     "จำนวนรายการต่อวันของ entity สูงกว่าพฤติกรรมเดิมของตนเองเกินเกณฑ์ (ต้องมี baseline หลายงวดก่อน)"),
    "BEH-SPIKE": ("ยอดพุ่งขึ้นผิดปกติ (Spike)",
                  "ยอดรวมต่องวดของ entity สูงกว่าพฤติกรรมเดิมของตนเองเกินเกณฑ์"),
    "TEMP-OFFHOURS": ("นอกเวลาทำการ",
                      "สัดส่วนรายการนอกเวลาทำการหรือวันหยุดของ entity สูงทั้งจำนวนและสัดส่วน (ต้องมีเวลาของรายการ)"),
    "NET-CYCLE": ("เงินวนกลับ (Cycle)", "เงินโอนวนกลับมาที่บัญชีเดิมภายในจำนวนทอดและช่วงเวลาที่กำหนด"),
    "NET-FUNNEL": ("รับหลายแหล่งแล้วโอนออก (Funnel)",
                   "บัญชีรับเงินจากหลายแหล่งแล้วโอนออกเกือบทั้งหมด"),
    "MULE-DWELL": ("เงินพักสั้น (Dwell)", "เงินที่รับเข้าถูกโอนออกภายในเวลาสั้นซ้ำหลายครั้ง"),
    "MULE-NEW-ACCT": ("บัญชีเปิดใหม่มีกิจกรรมสูง",
                      "บัญชีที่เปิดไม่นาน (จาก opened_at หรือวันที่พบรายการแรก) มีรายการจำนวนมาก"),
    "MULE-PATTERN": ("รูปแบบรับแล้วส่งต่อ (Mule Account pattern)",
                     "รวมสัญญาณ Funnel, Dwell, บัญชีเปิดใหม่, Velocity และนอกเวลาทำการของบัญชีเดียวกัน "
                     "ครบตามจำนวนขั้นต่ำ = สอดคล้องกับ Mule Account pattern (ไม่ใช่ข้อสรุป)"),
    "MULE-CROSS-TX": ("ธุรกรรมข้ามบัญชีที่สอดคล้องกับ pattern",
                      "ธุรกรรมระหว่างบัญชีที่สอดคล้องกับ Mule Account pattern และบัญชีที่รับ/ส่งเงินกับหลายบัญชีในกลุ่ม "
                      "(บทบาท collector / feeder เป็นบทบาทในเครือข่าย ไม่ใช่ข้อสรุป)"),
    "MULE-NETWORK": ("เครือข่ายบัญชีที่เชื่อมโยงกัน",
                     "จัดกลุ่มบัญชีที่มีธุรกรรมเชื่อมกันเป็นเครือข่ายเมื่อสมาชิกถึงจำนวนขั้นต่ำ"),
    "CPTY-PROFILE": ("สัดส่วนคู่ค้าใหม่เปลี่ยนไป", "สัดส่วนคู่ค้าใหม่ในงวดสูงกว่าพฤติกรรมเดิมของ entity"),
    "CPTY-NEW-LARGE": ("โอนยอดสูงไปคู่ค้าใหม่", "รายการแรกไปยังคู่ค้าใหม่มียอดสูงกว่าปกติของ entity หลายเท่า"),
    "FLOW-LAYERING": ("ส่งต่อเป็นทอด (Layering)",
                      "เงินถูกส่งต่อหลายทอดโดยแต่ละทอดส่งต่อเกือบทั้งหมดภายในช่วงเวลาที่กำหนด"),
    "GEN-CONC": ("การกระจุกตัว (share / HHI)",
                 "ส่วนแบ่งยอดของ entity (และ counterparty ถ้ามี) ต่อยอดรวมทั้งชุดถึงเกณฑ์ พร้อมระดับ HHI ของทั้งชุด"),
    "GEN-PERIOD-END": ("ช่วงสิ้นงวด",
                       "รายการของ entity กระจุกในช่วงวันทำการสุดท้ายของเดือนและวันแรกของเดือนถัดไป ครบทั้งจำนวนและสัดส่วน"),
    "DUP-PAY": ("จ่ายซ้ำ / ชำระซ้ำ",
                "รายการยอดเท่ากันของ entity เดียวกัน (และ counterparty / เลขที่เอกสาร ถ้ามี) ที่เกิดห่างกันไม่เกินช่วงวันที่กำหนด "
                "ข้อมูลสินเชื่อที่ไม่มีเลขที่เอกสารรายงานตามสัญญา (C-R3) ข้อมูลเจ้าหนี้รายงานเป็น A-R1"),
    "SPLIT-LIMIT": ("แบ่งรายการต่ำกว่าวงเงิน",
                    "หลายรายการของ entity เดียวกันในช่วงวันสั้น ๆ ที่แต่ละรายการใกล้วงเงินแต่ต่ำกว่า และรวมกันเกินวงเงิน"),
    "FOR-BENFORD": ("Benford หลักแรก",
                    "การกระจายตัวเลขหลักแรกของ entity ที่มีรายการมากพอ เบี่ยงจาก Benford เกินระดับที่ยอมรับได้"),
    "FOR-ROUND": ("ยอดกลม", "สัดส่วนยอดที่หารด้วยหน่วยกลมลงตัวของ entity สูงกว่าเกณฑ์"),
    "FOR-REPEAT": ("ยอดซ้ำ", "ยอดเดียวกันของ entity เดียวกันซ้ำหลายครั้งในงวดเดียวกัน"),
    "SOD-SAME-USER": ("ผู้บันทึก = ผู้อนุมัติ", "รายการที่ผู้บันทึกและผู้อนุมัติเป็นผู้ใช้คนเดียวกัน (ไม่มีค่าเกณฑ์)"),
    "DUE-NEAR": ("ชำระใกล้วันครบกำหนด",
                 "สัญญาที่ชำระก่อนวันครบกำหนดเพียงไม่กี่วันในสัดส่วนงวดสูง และมีจำนวนงวดถึงขั้นต่ำ"),
    "PAYER-MULTI": ("ผู้ชำระคนเดียวหลายสัญญา",
                    "ผู้ชำระ (counterparty) ที่ไม่ใช่ผู้กู้ของสัญญา ชำระให้สัญญาที่ต่างกันตั้งแต่จำนวนขั้นต่ำ"),
}

HEADER = """# AIDA-18 · Risk Library และการ์ดรับรอง (Phase C1)
> ไฟล์: AIDA-18 | เวอร์ชัน: 3.0 | ส่วนหนึ่งของ AIDA Knowledge Pack | สร้างจาก engine ด้วย tools/build_risk_library_md.py (ห้ามแก้ด้วยมือ)
> ไฟล์นี้ตอบคำถาม: Risk Concern ของผู้ตรวจสอบตรงกับความเสี่ยงใดใน Risk Library, ความเสี่ยงแต่ละข้อใช้การ์ดใด บทบาทคอลัมน์และข้อมูลขั้นต่ำเท่าไร ขาดแล้วต้องขออะไรเพิ่ม, การ์ดรับรองแต่ละใบตรวจอะไรและอ่านค่าเกณฑ์ key ใดใน AIDA-14

## สรุปสั้น
Risk Library คือรายการความเสี่ยงที่ engine (`aida_engine.py`) วิเคราะห์ได้ด้วย **การ์ดรับรอง** (certified check) ที่ทดสอบแล้ว
engine ใช้ข้อมูลชุดเดียวกันนี้คำนวณความพอเพียงของข้อมูล (ข้อ B ของ Intake Review) และแนะนำความเสี่ยงเพิ่ม (ข้อ D) — ไฟล์นี้ใช้เพื่อ **จับคู่ Risk Concern ภาษาธรรมชาติ** และอธิบายให้ผู้ตรวจสอบเข้าใจ
- การจับคู่ Risk Concern กับความเสี่ยงทำโดย `inspect()` จากคำในคอลัมน์ "คำที่ใช้จับคู่" ถ้าไม่ตรงข้อใด → แจ้งตั้งแต่ Intake ว่าจะใช้โหมดสำรวจ (`RX` ความเสี่ยงจากโหมดสำรวจ, ดู AIDA-19)
- การ์ดทุกใบทำงานตาม **บทบาทคอลัมน์** (AIDA-17) ไม่ใช่ชื่อคอลัมน์ บทบาทไม่ครบ → Skip พร้อมเหตุผลและบทบาทที่ขาด
- ค่าเกณฑ์ทุกค่าอ่านจาก Machine Config ของ AIDA-14 (`cfg[KEY]`) ไฟล์นี้ระบุเฉพาะชื่อ key — ค่าและที่มาอยู่ใน AIDA-14 (ค่ามาตรฐานทั่วไป ปรับได้ตามบริบทองค์กรผ่านข้อ C ของ Intake Review)
- ผลของการ์ดเป็น Evidence = สัญญาณที่ควรตรวจสอบเพิ่มเติม ไม่ใช่ข้อสรุป (AIDA-11)
- ข้อมูลประเภทที่ยังไม่มีการ์ดเฉพาะ (บัตรเครดิต, ประกันชีวิต ใน C2; กองทุน/การลงทุน, มูลนิธิ, สหกรณ์ ใน C3) ใช้ความเสี่ยงทั่วไป G-R1–G-R4 เมื่อบทบาทพอ + โหมดสำรวจ
"""

FOOTER = """
## การ์ดที่ไม่ใช่การ์ดรับรอง
- **FLOW-TRACE (ไล่เส้นทางเงิน)** ไม่อยู่ในรายการการ์ดรับรองและไม่สร้าง Evidence หรือ Finding — สำหรับข้อมูล E `run()` ไล่เส้นทางเงินอัตโนมัติให้บัญชีของ Finding ตามลำดับ Priority และผู้ตรวจสอบสั่งเพิ่มได้ตามต้องการด้วย `trace(files, intake, acct, direction, period)` (AIDA-19) ใช้ key `FLOW.MAX_HOPS`, `FLOW.WINDOW_DAYS`, `FLOW.MAX_TRAIL_ROWS` และ `FLOW.AUTO_MAX_ENTITIES` (จำนวนบัญชีที่ไล่อัตโนมัติ)
- **Intake** (ไม่ใช่การ์ด): `inspect()` ใช้ `INTAKE.ROLE_CONF` (ระดับความมั่นใจของบทบาทที่เดา) และ `INTAKE.JOIN_MIN_PCT` (สัดส่วนรหัสที่ต้องเชื่อมกับตารางรอง เช่น opened_at ต่ำกว่านี้ความพร้อมเป็น "บางส่วน")
- **โหมดสำรวจ** ไม่ใช่การ์ดรับรอง: ผลมีป้าย "โหมดสำรวจ — ยังไม่ผ่านการรับรอง" และ Finding ที่เลื่อนมามี Confidence ไม่เกิน "กลาง" (AIDA-19)

## ข้อห้าม (Guardrails)
- ห้ามเพิ่มความเสี่ยงที่ผู้ตรวจสอบไม่ได้ขอเอง — ความเสี่ยงที่แนะนำ (ข้อ D) เพิ่มเมื่อผู้ตรวจสอบเลือกเท่านั้น
- ห้ามรันการ์ดที่บทบาทไม่ครบ และห้ามเขียนโค้ดแทนการ์ดรับรอง — คำถามนอกการ์ดใช้โหมดสำรวจ (AIDA-19)
- ห้ามสรุปว่าผลของการ์ดเป็นการกระทำผิด ใช้ถ้อยคำ "สอดคล้องกับ … pattern ควรตรวจสอบเพิ่มเติม" (AIDA-11) และห้ามใช้คำว่า "บัญชีม้า"
- ห้ามแก้ไฟล์นี้ด้วยมือ — แก้ที่ engine หรือ tools/build_risk_library_md.py แล้วสร้างใหม่ (validator ตรวจว่าตรงกับ engine)

## ไฟล์ที่เกี่ยวข้อง
- AIDA-17 บทบาทคอลัมน์ 14 บทบาท + preset และ Schema
- AIDA-19 วิธีเรียก engine, Intake Review, โหมดสำรวจ
- AIDA-14 ค่าเกณฑ์ทุก key (Machine Config)
- AIDA-04 ถึง AIDA-09 หลักการของ skill family ที่การ์ดใช้
- AIDA-11 ถ้อยคำที่ไม่กล่าวหาและ Audit Procedure
"""


def load_engine(path):
    """Import the engine from its file path under a private module name."""
    spec = importlib.util.spec_from_file_location("aida_engine_for_docs", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _codes(items) -> str:
    return ", ".join(f"`{x}`" for x in items) if items else "-"


def _types(types) -> str:
    return " / ".join(TYPE_TEXT.get(t, t) for t in types)


def _cell(text) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def render(engine) -> str:
    lib, checks = engine.RISK_LIBRARY, engine.CHECKS
    missing = [c for c in checks if c not in CHECK_TEXT]
    if missing:
        raise SystemExit(f"CHECK_TEXT has no Thai description for {', '.join(missing)} — add them and rerun")
    grouped = [rid for _, ids in GROUPS for rid in ids]
    extra = [rid for rid in lib if rid not in grouped]
    groups = GROUPS + ([("ความเสี่ยงอื่น", tuple(extra))] if extra else [])
    out = [HEADER]
    out.append("## ภาพรวม Risk Library")
    out.append(f"engine `aida_engine.py` v{engine.__version__} · Registry {engine.REGISTRY_VERSION} · "
               f"{len(lib)} ความเสี่ยง · {len(checks)} การ์ดรับรอง")
    out.append("")
    out.append("| Risk | ชื่อ | ประเภทข้อมูล | การ์ดรับรอง |")
    out.append("|---|---|---|---|")
    for title, ids in groups:
        for rid in ids:
            if rid in lib:
                r = lib[rid]
                out.append(f"| {rid} | {_cell(r['name_th'])} | {' / '.join(r['data_types'])} | {', '.join(r['checks'])} |")
    out.append("| RX | ความเสี่ยงจากโหมดสำรวจ | ทุกประเภท | ไม่มี — โหมดสำรวจ (AIDA-19) |")
    out.append("")
    for title, ids in groups:
        out.append(f"## {title}")
        for rid in ids:
            if rid not in lib:
                continue
            r = lib[rid]
            out.append(f"### {rid} · {r['name_th']}")
            out.append(f"- คำอธิบาย: {r['description_th']}")
            out.append(f"- ประเภทข้อมูล: {_types(r['data_types'])}")
            out.append(f"- การ์ดรับรอง: {', '.join(r['checks'])}")
            out.append(f"- บทบาทขั้นต่ำ: {_codes(r['min_roles'])}")
            if r.get("join_roles"):
                out.append(f"- บทบาทจากตารางรอง (เชื่อมด้วย entity): {_codes(r['join_roles'])}")
            md = r["min_data"]
            out.append(f"- ข้อมูลขั้นต่ำ: อย่างน้อย {md['months']} เดือน และ {md['rows']} รายการ")
            out.append(f"- คำที่ใช้จับคู่ Risk Concern: {', '.join(r['synonyms'])}")
            req = r.get("request_if_missing") or {}
            if req:
                for k, v in req.items():
                    what = {"_data_type": "ข้อมูลไม่ใช่ประเภทที่ความเสี่ยงนี้ต้องใช้",
                            "_time": "วันที่ไม่มีเวลา"}.get(k, f"ขาดบทบาท `{k}`")
                    out.append(f"- ถ้า{what} → ขอเพิ่ม: {v}")
            else:
                out.append("- ถ้าขาดบทบาท → ขอคอลัมน์ที่มีบทบาทนั้นเพิ่ม (Data Request ใน Intake Review)")
            out.append("")
    out.append("## การ์ดรับรอง")
    out.append("ความเสี่ยงหลักคือรหัสที่การ์ดรายงานตามปกติ ความเสี่ยงรองคือรหัสที่การ์ดรายงานแทนเมื่อผู้ตรวจสอบขอความเสี่ยงนั้น "
               "หรือเมื่อข้อมูลเป็นอีกประเภท (เช่น DUP-PAY ของข้อมูลสินเชื่อ = C-R3)")
    out.append("")
    out.append("| การ์ด | ชื่อ | ตรวจอะไร | ความเสี่ยงหลัก (รอง) | Skill family | บทบาทที่ต้องมี | บทบาทเสริม | ประเภทข้อมูล | Registry key (AIDA-14) |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for cid, spec in checks.items():
        name, what = CHECK_TEXT[cid]
        risk = spec["risk"] + (f" ({', '.join(spec['risk_alt'])})" if spec["risk_alt"] else "")
        out.append(f"| {cid} | {_cell(name)} | {_cell(what)} | {risk} | {spec['skill_family']} | "
                   f"{', '.join(spec['requires'])} | {', '.join(spec['optional']) or '-'} | "
                   f"{' / '.join(spec['data_types'])} | {_codes(spec['registry'])} |")
    return "\n".join(out) + "\n" + FOOTER


def main(argv) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    pack = Path(args[0]) if args else Path(__file__).resolve().parent.parent
    text = render(load_engine(pack / ENGINE_REL))
    target = pack / "knowledge" / OUT_NAME
    if "--check" in argv:
        same = target.exists() and target.read_text(encoding="utf-8") == text
        print("OK: AIDA-18 matches the engine" if same else "DIFF: AIDA-18 differs from the engine")
        return 0 if same else 1
    target.write_text(text, encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
