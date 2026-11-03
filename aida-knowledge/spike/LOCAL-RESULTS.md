# ผล spike แบบจำลองในเครื่อง (2026-11-03)

ผู้ใช้ขอให้ทดสอบภายใน session นี้ จึงจำลอง Code Interpreter ด้วย Python 3.11 + **pandas 1.5.3** (เวอร์ชันต่ำสุดที่ spec รองรับ) + numpy 1.26.4 + openpyxl 3.1.5
และเปิด HTML ด้วย Chromium (Playwright) — **ไม่ได้รันใน Copilot จริง**

| # | ทดสอบ | ผลในเครื่อง | ยังต้องยืนยันใน Copilot |
|---|---|---|---|
| 1 | การ์ด NET-FUNNEL โหลดครบและรันได้ | ✅ รันบน pandas 1.5.3 (ไม่มี FutureWarning) พบ **F01 บัญชีเดียว** sources = 12, total_in = 58,700, out_ratio = 0.85 | Copilot ดึงการ์ดจาก Knowledge มาครบหรือไม่ |
| 2 | อ่านไฟล์จาก SharePoint/OneDrive | ⏭️ ทดสอบในเครื่องไม่ได้ (อ่านจาก CSV ในเครื่องแทน) | ทั้งหมด |
| 3 | สร้าง .xlsx | ✅ openpyxl เปิดได้ 2 sheet (Summary, Findings) | การให้ลิงก์ดาวน์โหลดใน Copilot |
| 4 | สร้าง .html จาก template | ✅ template 118 บรรทัด บรรทัดสุดท้าย `<!-- END-OF-TEMPLATE -->`; Chromium เปิดได้ 3 แท็บ (สรุป, Findings, Run Log), ไม่มี JS error, ไม่มี request ภายนอก, ภาษาไทยแสดงถูกต้อง | Copilot ดึง template มาครบหรือไม่ + ลิงก์ดาวน์โหลด |

## สรุป
- โค้ดการ์ดและ template ใช้ได้กับ pandas 1.5–3.0 และเบราว์เซอร์จริง
- สิ่งที่ยังไม่ได้ยืนยัน (ทดสอบได้เฉพาะใน Copilot): การดึง recipe/template จาก Knowledge มาครบ, การอ่านไฟล์จาก SharePoint, ลิงก์ดาวน์โหลด
- จะยืนยันรวมในการทดสอบ eval ระยะ B ด้วย Knowledge Pack v2.0
