# AIDA-16 · ติดตั้ง engine ใน Code Interpreter (แนวทาง 2)
> ไฟล์: AIDA-16 | เวอร์ชัน: 3.1 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: จะโหลด `aida_engine.py` จาก SharePoint/OneDrive หรือไฟล์แนบเข้า Code Interpreter อย่างไร, ตรวจเวอร์ชันอย่างไร, ถ้าโหลดไม่ได้หรือหา AIDA-14 ไม่พบต้องบอกผู้ใช้ว่าอะไร

## สรุปสั้น
AIDA วิเคราะห์ข้อมูลด้วย engine ไฟล์เดียวที่ทดสอบแล้ว: `aida_engine.py` v3.1.0 (Registry 1.3) — AIDA ไม่เขียนโค้ดวิเคราะห์เอง
ใน Knowledge Pack ชุดนี้ (แนวทาง 2) engine **ไม่อยู่ใน Knowledge** ผู้ใช้วางไฟล์ไว้ที่ SharePoint/OneDrive ของทีม หรือแนบในแชต แล้ว AIDA โหลดเข้า Code Interpreter **ที่ต้นการสนทนาทุกครั้ง** ก่อนเรียก `inspect`
engine อ่านค่าเกณฑ์จาก `AIDA-14-configuration-registry.md` ที่อยู่ **โฟลเดอร์เดียวกับ engine** ดังนั้นให้วางหรือแนบ AIDA-14 คู่กับ engine เสมอ
- ถ้าผล spike (`6-spike-c1/` ใน zip) แสดงว่าข้อ 2 ผ่าน (Code Interpreter import ไฟล์จาก Knowledge ได้) ให้อัปโหลด `aida_engine.py` เข้า Knowledge **แทนไฟล์นี้** (แนวทาง 3) — Knowledge ยังเป็น 20 ไฟล์ และขั้นตอนตรวจเวอร์ชันข้างล่างยังใช้เหมือนเดิม

## 1. สิ่งที่ผู้ใช้เตรียม (ครั้งเดียว)
| ไฟล์ | ที่มา | วางที่ |
|---|---|---|
| `aida_engine.py` | โฟลเดอร์ `5-engine/` ใน zip | SharePoint/OneDrive ของทีม (หรือแนบในแชต) |
| `AIDA-14-configuration-registry.md` | โฟลเดอร์ `1-upload-knowledge/` ใน zip | โฟลเดอร์เดียวกับ engine (หรือแนบพร้อม engine) |

- ถ้าระบบไม่รับไฟล์ `.py` ให้เปลี่ยนชื่อเป็น `aida_engine.txt` — ขั้นตอนข้างล่างคัดลอกเป็น `.py` ให้เอง
- อย่าแก้เนื้อหา engine; ปรับค่าเกณฑ์ที่ AIDA-14 เท่านั้น (หรือระบุค่าขององค์กรที่ข้อ C ของ Intake Review)

## 2. ขั้นตอนโหลด (AIDA ทำที่ต้นการสนทนา)
1. ขอให้ผู้ใช้แนบ `aida_engine.py` + AIDA-14 หรือส่งลิงก์ SharePoint/OneDrive ของทั้งสองไฟล์ (ถ้ายังไม่ได้แนบ)
2. รันโค้ดเชื่อมต่อไปนี้ใน Code Interpreter (เป็นโค้ดโหลดไฟล์ ไม่ใช่โค้ดวิเคราะห์):
```text
import glob, os, shutil, importlib.util, sys
roots = [r for r in ("/mnt/data", os.getcwd()) if os.path.isdir(r)]
found = lambda pat: sorted(p for r in roots for p in glob.glob(os.path.join(r, "**", pat), recursive=True)
                           if "probe" not in os.path.basename(p).lower() and "aida_work" not in p)
srcs = found("aida_engine*.py") + found("aida_engine*.txt")
regs = found("AIDA-14-configuration-registry.md")
print("ENGINE:", srcs[0] if srcs else "NOT FOUND", "| AIDA-14:", regs[0] if regs else "NOT FOUND")
assert srcs, "ENGINE NOT FOUND — ขอให้ผู้ใช้แนบ aida_engine.py (AIDA-16 ข้อ 4)"
work = os.path.join(os.getcwd(), "aida_work"); os.makedirs(work, exist_ok=True)
path = os.path.join(work, "aida_engine.py"); shutil.copyfile(srcs[0], path)
if regs: shutil.copyfile(regs[0], os.path.join(work, "AIDA-14-configuration-registry.md"))
spec = importlib.util.spec_from_file_location("aida_engine", path)
aida = importlib.util.module_from_spec(spec); sys.modules["aida_engine"] = aida; spec.loader.exec_module(aida)
reg = aida.default_registry_path()
reg_ver = aida.load_registry(reg).get("REGISTRY.VERSION") if reg else "NOT FOUND"
print(aida.__version__, aida.REGISTRY_VERSION, reg_ver, reg)
```
3. **ตรวจผล** — บรรทัด ENGINE / AIDA-14 ต้องไม่เป็น `NOT FOUND` และบรรทัดสุดท้ายต้องได้ `3.1.0 1.3 1.3 <ที่อยู่ของ AIDA-14>`:
   - `__version__ == "3.1.0"` → engine ถูกรุ่น
   - `REGISTRY.VERSION` ของไฟล์ AIDA-14 ที่แนบ (ค่าที่ 3) **ต้องเท่ากับ** `aida.REGISTRY_VERSION` (ค่าที่ 2) — ไม่เท่า → หยุดและแจ้งตามข้อ 4 (engine เองก็ปฏิเสธ AIDA-14 ต่างรุ่นด้วยข้อความภาษาไทยเมื่อเรียก `inspect` / `run`)
   - ค่าที่ 3 เป็น `NOT FOUND` → ยังไม่มี AIDA-14 ข้าง engine (ดูข้อ 4)
   - ไฟล์ probe ของ spike (`aida_engine_probe.*`) ไม่ถูกเลือก
4. ใช้ `aida.inspect(...)`, `aida.confirm(...)`, `aida.run(...)` ต่อตาม AIDA-19

ทางสำรอง (ถ้า importlib ใช้ไม่ได้): โหลดด้วย `exec` โดยกำหนด `__file__` ให้ engine หา AIDA-14 ข้างตัวเองได้
```text
import types, sys
aida = types.ModuleType("aida_engine"); aida.__file__ = path; sys.modules["aida_engine"] = aida
exec(compile(open(path, encoding="utf-8").read(), path, "exec"), aida.__dict__)
```

## 3. ตัวแปรหายระหว่างข้อความ
ถ้าเรียก `aida.` แล้วได้ `NameError` (Code Interpreter ไม่จำตัวแปรข้ามข้อความ) → รันขั้นตอนข้อ 2 ใหม่โดยไม่ถามผู้ใช้ แล้วเรียกต่อ:
- หลังยืนยันแล้ว: จาก `intake.json` (`run`, `data`, `trace` อ่านจาก intake ที่ยืนยันแล้ว ไม่ต้องยืนยันซ้ำ — AIDA-19)
- ก่อนยืนยัน: จากร่าง `intake_draft.json` ที่ `inspect` บันทึกไว้ในโฟลเดอร์ทำงานเดียวกับ `intake.json` → `aida.confirm("intake_draft.json", answers, "intake.json")` (หรือเรียก `inspect` เดิมใหม่ ได้ผลเดิม)

## 4. ถ้าโหลดไม่ได้ — สิ่งที่ต้องบอกผู้ใช้
| อาการ | บอกผู้ใช้ว่า |
|---|---|
| ไม่พบไฟล์ `aida_engine*` (`ENGINE: NOT FOUND`) | "ยังไม่พบไฟล์ aida_engine.py — กรุณาแนบไฟล์จากโฟลเดอร์ 5-engine ของชุด Knowledge Pack หรือส่งลิงก์ SharePoint/OneDrive ที่เปิดสิทธิ์อ่านได้" |
| `__version__` ไม่ใช่ 3.1.0 | "engine ที่แนบเป็นรุ่น X แต่ Knowledge Pack นี้ใช้รุ่น 3.1.0 — กรุณาแนบ aida_engine.py จาก Knowledge Pack ชุดเดียวกัน" แล้วหยุด ไม่วิเคราะห์ด้วยรุ่นที่ไม่ตรง |
| ไม่พบ AIDA-14 (`NOT FOUND`) | "ยังไม่พบ AIDA-14-configuration-registry.md ข้าง engine — กรุณาแนบไฟล์นี้จากโฟลเดอร์ 1-upload-knowledge หรือวางไว้ในโฟลเดอร์เดียวกับ engine" |
| `REGISTRY.VERSION` ของ AIDA-14 ที่แนบไม่เท่ากับ `aida.REGISTRY_VERSION` | "AIDA-14 ที่แนบเป็นรุ่น X — กรุณาแนบ AIDA-14 จาก Knowledge Pack ชุดเดียวกัน" แล้วหยุด ไม่วิเคราะห์ด้วยค่าเกณฑ์ต่างรุ่น |
| `SyntaxError` / ไฟล์ถูกตัด | "ไฟล์ engine ไม่ครบ (อาจถูกตัดระหว่างอัปโหลด) — กรุณาแนบไฟล์ใหม่" |
| `ModuleNotFoundError` (pandas / numpy / openpyxl) | "Code Interpreter ไม่มีไลบรารีที่ engine ต้องใช้ — วิเคราะห์ข้อมูลไม่ได้ในสภาพแวดล้อมนี้" แล้วให้คำปรึกษาแบบระยะ A |
| อ่านลิงก์ SharePoint/OneDrive ไม่ได้ | ขอให้ผู้ใช้แนบไฟล์ในแชตแทนครั้งเดียว |

- ห้ามวิเคราะห์ข้อมูลต่อโดยไม่มี engine และห้ามเขียนโค้ดวิเคราะห์ขึ้นเองแทน engine
- ระหว่างที่โหลด engine ไม่ได้ AIDA ยังให้คำปรึกษาแบบระยะ A ได้ (เลือก skill, gate, ข้อมูลที่ต้องมี — AIDA-03)

## ข้อห้าม (Guardrails)
- ห้ามแก้ไข เพิ่ม หรือตัดโค้ดใน engine และห้ามคัดลอกเฉพาะบางฟังก์ชันมาใช้
- ห้ามใช้ engine รุ่นอื่นที่ไม่ใช่ 3.1.0 กับ Knowledge Pack ชุดนี้
- ห้ามเดาค่าเกณฑ์เมื่อหา AIDA-14 ไม่พบ — ขอให้ผู้ใช้แนบ AIDA-14
- ห้ามแสดงผลวิเคราะห์ที่ไม่ได้มาจาก engine

## ไฟล์ที่เกี่ยวข้อง
- AIDA-19 วิธีเรียก engine และ Intake Review
- AIDA-14 ค่าเกณฑ์ (Machine Config) ที่ engine อ่าน
- AIDA-00 สารบัญและเวอร์ชัน
