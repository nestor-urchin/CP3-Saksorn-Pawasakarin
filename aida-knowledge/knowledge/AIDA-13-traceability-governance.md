# AIDA-13 · Traceability, Governance และ Universal Skill Spec
> ไฟล์: AIDA-13 | เวอร์ชัน: 1.0 | ส่วนหนึ่งของ AIDA Knowledge Pack
> ไฟล์นี้ตอบคำถาม: Evidence Lineage มีกี่ระดับและต้องเก็บอะไร, Reproducibility test คืออะไร, Governance Control Plane มีอะไรบ้าง, ทุก skill ต้องประกาศอะไร

## สรุปสั้น
Control objective: **ไม่มีผลลัพธ์ใดที่อธิบายไม่ได้ว่า "ใช้ข้อมูลอะไร ใช้วิธีใด ใช้ค่าใด ใช้เวอร์ชันใด และใครตรวจทาน"**
Lineage 7 ระดับเป็นโครงสร้างอ้างอิงขั้นต่ำเพื่อพิสูจน์ที่มาของผลลัพธ์และทำซ้ำการวิเคราะห์
Layer 10 Governance (Configuration, Versioning, Audit Trail) ทำให้ผลตรวจสอบทำซ้ำและตรวจสอบย้อนหลังได้

## Traceability & Evidence Lineage (7 ระดับ)
| # | Reference | ต้องเก็บ |
|---|---|---|
| 1 | Data Reference | dataset • table • record • period |
| 2 | Execution Reference | run ID • timestamp • orchestrator stage |
| 3 | Skill Reference | skill name • version • method |
| 4 | Configuration Reference | rules • thresholds • weights • version |
| 5 | Evidence Reference | metric • score • explanation • source |
| 6 | Finding Reference | entity • risk • time • linked evidence |
| 7 | Review Reference | decision • reviewer • disposition |

**Reproducibility test:** ใช้ Data + Configuration + Skill/Model Version เดิม ต้องสามารถอธิบายและทำซ้ำผลลัพธ์เดิมได้ หรือบันทึกสาเหตุของความแตกต่าง

## Layer 10 · Governance Control Plane
| Capability | ความหมาย |
|---|---|
| Audit Trail ทุกขั้นตอน | บันทึกทุก Stage ของ workflow (AIDA-01) |
| Configuration Registry | แหล่งกฎ เกณฑ์ น้ำหนัก (AIDA-14) |
| Skill Version / Model Version | ระบุเวอร์ชันที่ใช้ทุกการรัน |
| Rule และ Threshold Management | จัดการกฎและเกณฑ์อย่างเป็นระบบ |
| Change Control และ Approval | การเปลี่ยนกฎ/เกณฑ์/โมเดลต้องผ่านการอนุมัติและบันทึก |
| Skill Monitoring | ติดตามผลการทำงานของ skill (อัตรา Skip, error, ผลทบทวน) |
| Error / Exception Logging | บันทึก Stop และข้อผิดพลาดทุกครั้ง |
| Reproducible Execution | ทำซ้ำผลได้ตาม Reproducibility test |

## Universal Skill Specification
ทุก Skill ต้องประกาศขอบเขต อินเทอร์เฟซ การควบคุม และเงื่อนไขการทำงานอย่างชัดเจน (ใช้เป็นโครงในไฟล์ AIDA-04 ถึง AIDA-08)
| ช่อง | คำถามที่ต้องตอบ |
|---|---|
| Purpose | Skill ทำอะไร |
| Non-purpose | Skill ไม่ทำอะไร |
| Input | รับข้อมูลจากที่ใด |
| Output | ส่งข้อมูลให้ Skill ใด |
| Configuration | ใช้ Configuration ใด |
| Audit Trail | สร้าง Log ประเภทใด |
| Success | สำเร็จเมื่อใด |
| Stop / Skip | หยุดหรือข้ามเมื่อใด |

## ข้อห้าม (Guardrails)
- ห้ามนำเสนอผลลัพธ์ที่ไม่มี Data Reference และ Configuration Reference
- ห้ามเปลี่ยนกฎหรือเกณฑ์โดยไม่ผ่าน Change Control และไม่เพิ่มเวอร์ชัน
- ห้ามทิ้งบันทึก Stop / Skip / Error

## ไฟล์ที่เกี่ยวข้อง
- AIDA-01 Workflow, AIDA-02 Decision Gates, AIDA-12 Audit Trail Report, AIDA-14 Registry, AIDA-15 Checklist
