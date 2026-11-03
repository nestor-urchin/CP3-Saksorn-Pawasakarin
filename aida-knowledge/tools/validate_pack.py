"""Validate the AIDA Knowledge Pack.

Usage: python3 validate_pack.py [pack_dir]
pack_dir defaults to the aida-knowledge/ folder that contains this script.
Exit code 0 when every check passes, 1 otherwise.
"""
import json
import re
import sys
from pathlib import Path

REF_RE = re.compile(r"`([A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+)\s*=\s*([^`]+)`")
XREF_RE = re.compile(r"AIDA-(\d{2})")
FILE_ID_RE = re.compile(r"^AIDA-(\d{2})-")

REGISTRY_NAME = "AIDA-14-configuration-registry.md"
INSTRUCTIONS_NAME = "AIDA-agent-instructions.md"
GUARDRAILS_HEADING = "## ข้อห้าม (Guardrails)"
REQUIRED_HEADINGS = ["## สรุปสั้น", GUARDRAILS_HEADING, "## ไฟล์ที่เกี่ยวข้อง"]
QUESTIONS_PREFIX = "> ไฟล์นี้ตอบคำถาม:"
ACCUSATORY_TERMS = ["ทุจริต", "กระทำผิด", "กระทำความผิด", "โกง", "ยักยอก", "คอร์รัปชัน",
                    "ฉ้อโกง", "สมรู้ร่วมคิด", "fraudster"]
# Tables that must be identical in AIDA-10 and AIDA-14 (heading line marks each table).
ASSESSMENT_NAME = "AIDA-10-assessment-model.md"
SHARED_TABLE_HEADINGS = ["### ตาราง Priority", "### ตาราง Confidence"]
# A negation exempts a term only when it ends within NEGATION_WINDOW characters before it.
NEGATION_RE = re.compile(r"≠|ไม่(?!ว่า)|ห้าม|\bnot\b", re.IGNORECASE)
NEGATION_WINDOW = 20
RESERVED_IDS = {"16", "17", "18", "19"}

MACHINE_CONFIG_HEADING = "## Machine Config (สำหรับ recipe)"
HEADING_KEY_RE = re.compile(r"^#{2,4}\s+([A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+)\b", re.MULTILINE)
RECIPE_FENCE_OPEN = re.compile(r"^```python\s*$")
RECIPE_FENCE_CLOSE = re.compile(r"^```\s*$")
RECIPE_H1 = re.compile(r"^#\s*RECIPE\s+(\S+)\s+v\d+\.\d+\s*\|\s*Skill:\s*.+?\s*\|\s*Risk:\s*(R[1-4]|-)\s*$")
RECIPE_H2 = re.compile(r"^#\s*Registry:\s*.+?\s*\|\s*Input:\s*.+?\s*$")
CFG_KEY_RE = re.compile(r"""cfg\[\s*["']([^"']+)["']\s*\]""")
RECIPE_MAX_LINES = 40  # code lines after the two header comment lines


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_registry(path: Path) -> tuple[dict[str, str], list[str]]:
    registry: dict[str, str] = {}
    errors: list[str] = []
    for key, value in REF_RE.findall(_read(path)):
        value = value.strip()
        if key in registry and registry[key] != value:
            errors.append(f"{path.name}: key {key} defined twice with different values "
                          f"('{registry[key]}' vs '{value}')")
            continue
        registry[key] = value
    return registry, errors


def check_file_count(knowledge_dir: Path, limit: int = 20) -> list[str]:
    count = len(list(knowledge_dir.glob("*.md")))
    if count > limit:
        return [f"{knowledge_dir.name}: {count} files, limit is {limit}"]
    return []


def check_required_sections(path: Path) -> list[str]:
    lines = _read(path).splitlines()
    errors: list[str] = []
    if not lines or not lines[0].startswith("# AIDA-"):
        errors.append(f"{path.name}: first line must start with '# AIDA-'")
    if not any(line.startswith(QUESTIONS_PREFIX) for line in lines):
        errors.append(f"{path.name}: missing line '{QUESTIONS_PREFIX}'")
    stripped = {line.strip() for line in lines}
    for heading in REQUIRED_HEADINGS:
        if heading not in stripped:
            errors.append(f"{path.name}: missing heading '{heading}'")
    return errors


def check_registry_refs(path: Path, registry: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key, value in REF_RE.findall(_read(path)):
        value = value.strip()
        if key not in registry:
            errors.append(f"{path.name}: unknown registry key {key}")
        elif registry[key] != value:
            errors.append(f"{path.name}: {key} = '{value}' but AIDA-14 says '{registry[key]}'")
    return errors


def check_accusatory_terms(path: Path) -> list[str]:
    errors: list[str] = []
    heading = ""
    for n, line in enumerate(_read(path).splitlines(), 1):
        if line.startswith("## "):
            heading = line.strip()
            continue
        if heading == GUARDRAILS_HEADING:
            continue
        lower = line.lower()
        negation_ends = [m.end() for m in NEGATION_RE.finditer(line)]
        found = [term for term in ACCUSATORY_TERMS
                 for hit in re.finditer(re.escape(term), lower)
                 if not any(0 <= hit.start() - end <= NEGATION_WINDOW for end in negation_ends)]
        if found:  # one error per line, even when terms overlap (ฉ้อโกง contains โกง)
            terms = ", ".join(dict.fromkeys(found))
            errors.append(f"{path.name}:{n}: accusatory term '{terms}' outside Guardrails")
    return errors


def check_cross_refs(path: Path, existing: set[str], reserved: set[str] = RESERVED_IDS) -> list[str]:
    errors: list[str] = []
    for ref in sorted(set(XREF_RE.findall(_read(path)))):
        if ref not in existing and ref not in reserved:
            errors.append(f"{path.name}: reference AIDA-{ref} points to no file")
    return errors


def check_instructions_length(path: Path, limit: int = 8000) -> list[str]:
    length = len(_read(path))
    if length > limit:
        return [f"{path.name}: {length} characters, limit is {limit}"]
    return []


def _table_after(text: str, heading: str) -> list[str] | None:
    """Return the table rows that follow `heading`, or None when the heading is absent."""
    lines = text.splitlines()
    stripped = [line.strip() for line in lines]
    if heading not in stripped:
        return None
    rows: list[str] = []
    for line in stripped[stripped.index(heading) + 1:]:
        if line.startswith("|"):
            rows.append(line)
        elif rows or line.startswith("#"):
            break
    return rows


def check_shared_tables(knowledge_dir: Path) -> list[str]:
    """AIDA-10 and AIDA-14 must carry identical copies of each shared table."""
    a10, a14 = knowledge_dir / ASSESSMENT_NAME, knowledge_dir / REGISTRY_NAME
    if not (a10.exists() and a14.exists()):
        return []
    text10, text14 = _read(a10), _read(a14)
    errors: list[str] = []
    for heading in SHARED_TABLE_HEADINGS:
        t10, t14 = _table_after(text10, heading), _table_after(text14, heading)
        if t10 is None or t14 is None:
            missing = a10.name if t10 is None else a14.name
            errors.append(f"{missing}: missing heading '{heading}'")
        elif t10 != t14:
            errors.append(f"{a10.name}: '{heading}' differs from the copy in {a14.name}")
    return errors


def registry_key_names(path: Path) -> set[str]:
    """Every key AIDA-14 defines: as a `KEY = value` reference or as a `### KEY` heading (R-3)."""
    registry, _ = parse_registry(path)
    return set(registry) | set(HEADING_KEY_RE.findall(_read(path)))


def parse_machine_config(path: Path) -> tuple[dict, list[str]]:
    """Return the Machine Config JSON from AIDA-14. ({}, []) when the heading is absent."""
    lines = _read(path).splitlines()
    stripped = [line.strip() for line in lines]
    if MACHINE_CONFIG_HEADING not in stripped:
        return {}, []
    i = stripped.index(MACHINE_CONFIG_HEADING) + 1
    while i < len(lines) and not stripped[i].startswith("```"):
        if stripped[i].startswith("#"):
            return {}, [f"{path.name}: no ```json block under '{MACHINE_CONFIG_HEADING}'"]
        i += 1
    j = i + 1
    while j < len(lines) and not stripped[j].startswith("```"):
        j += 1
    if i >= len(lines) or j >= len(lines):
        return {}, [f"{path.name}: no closed ```json block under '{MACHINE_CONFIG_HEADING}'"]
    try:
        config = json.loads("\n".join(lines[i + 1:j]))
    except json.JSONDecodeError as e:
        return {}, [f"{path.name}: Machine Config is not valid JSON ({e.msg}, line {e.lineno})"]
    if not isinstance(config, dict):
        return {}, [f"{path.name}: Machine Config must be a JSON object"]
    return config, []


def priority_from_table(text: str) -> dict | None:
    """Parse '### ตาราง Priority' into {Confidence: {Materiality: Priority}} (note '+ Human Review' dropped)."""
    rows = _table_after(text, "### ตาราง Priority")
    if not rows or len(rows) < 3:
        return None
    cells = lambda row: [c.strip() for c in row.strip("|").split("|")]
    header = cells(rows[0])[1:]
    table: dict = {}
    for row in rows[2:]:
        c = cells(row)
        table[c[0]] = {m: v.split("+")[0].strip() for m, v in zip(header, c[1:])}
    return table


def check_machine_config(registry_path: Path) -> list[str]:
    config, errors = parse_machine_config(registry_path)
    if errors:
        return errors
    registry, _ = parse_registry(registry_path)
    if not config:
        if "REGISTRY.VERSION" in registry:
            return [f"{registry_path.name}: missing '{MACHINE_CONFIG_HEADING}' JSON block"]
        return []
    known = registry_key_names(registry_path)
    for key in config:
        if not key.startswith("_") and key not in known:
            errors.append(f"{registry_path.name}: Machine Config key {key} is not in the AIDA-14 tables")
    if "REGISTRY.VERSION" in registry and config.get("REGISTRY.VERSION") != registry["REGISTRY.VERSION"]:
        errors.append(f"{registry_path.name}: Machine Config REGISTRY.VERSION "
                      f"'{config.get('REGISTRY.VERSION')}' != '{registry['REGISTRY.VERSION']}'")
    if "ASSESS.PRIORITY" in config:
        table = priority_from_table(_read(registry_path))
        if table is not None and config["ASSESS.PRIORITY"] != table:
            errors.append(f"{registry_path.name}: Machine Config ASSESS.PRIORITY differs from '### ตาราง Priority'")
    return errors


def check_recipes(path: Path, registry_keys: set[str]) -> list[str]:
    """Check recipe cards (```python blocks starting with '# RECIPE'): header, length, cfg keys."""
    lines = _read(path).splitlines()
    errors: list[str] = []
    i = 0
    while i < len(lines):
        if not RECIPE_FENCE_OPEN.match(lines[i]):
            i += 1
            continue
        start = i + 1
        j = start
        while j < len(lines) and not RECIPE_FENCE_CLOSE.match(lines[j]):
            j += 1
        block = lines[start:j]
        i = j + 1
        if not (block and block[0].startswith("# RECIPE")):
            continue
        where = f"{path.name}:{start + 1}"
        if j >= len(lines):
            errors.append(f"{where}: recipe code fence never closed")
            continue
        m1 = RECIPE_H1.match(block[0])
        if not (m1 and len(block) > 1 and RECIPE_H2.match(block[1])):
            errors.append(f"{where}: malformed recipe header")
            continue
        rid = m1.group(1)
        if len(block) - 2 > RECIPE_MAX_LINES:
            errors.append(f"{where}: recipe {rid} has {len(block) - 2} code lines, limit is {RECIPE_MAX_LINES}")
        for key in dict.fromkeys(CFG_KEY_RE.findall("\n".join(block[2:]))):
            if not key.startswith("_") and key not in registry_keys:
                errors.append(f"{where}: recipe {rid} reads cfg['{key}'] which is not an AIDA-14 key")
    return errors


def validate(pack_dir: Path) -> list[str]:
    knowledge = pack_dir / "knowledge"
    files = sorted(knowledge.glob("*.md"))
    errors = check_file_count(knowledge)

    registry: dict[str, str] = {}
    registry_path = knowledge / REGISTRY_NAME
    if registry_path.exists():
        registry, reg_errors = parse_registry(registry_path)
        errors += reg_errors
    else:
        errors.append(f"knowledge/{REGISTRY_NAME} (AIDA-14) is missing")

    registry_keys = registry_key_names(registry_path) if registry_path.exists() else set()
    if registry_path.exists():
        errors += check_machine_config(registry_path)

    existing = {m.group(1) for f in files if (m := FILE_ID_RE.match(f.name))}
    for f in files:
        errors += check_required_sections(f)
        errors += check_registry_refs(f, registry)
        errors += check_accusatory_terms(f)
        errors += check_cross_refs(f, existing)
        errors += check_recipes(f, registry_keys)
    errors += check_shared_tables(knowledge)

    instructions = pack_dir / INSTRUCTIONS_NAME
    if instructions.exists():
        errors += check_instructions_length(instructions)
        errors += check_registry_refs(instructions, registry)
        errors += check_accusatory_terms(instructions)
        errors += check_cross_refs(instructions, existing)
    else:
        errors.append(f"{INSTRUCTIONS_NAME} is missing")
    return errors


def main(argv: list[str]) -> int:
    pack_dir = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errors = validate(pack_dir)
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        return 1
    print(f"OK: {len(list((pack_dir / 'knowledge').glob('*.md')))} files validated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
