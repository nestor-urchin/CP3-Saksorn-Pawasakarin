"""Validate the AIDA Knowledge Pack.

Usage: python3 validate_pack.py [pack_dir]
pack_dir defaults to the aida-knowledge/ folder that contains this script.
Exit code 0 when every check passes, 1 otherwise.
"""
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
ACCUSATORY_TERMS = ["ทุจริต", "กระทำผิด", "กระทำความผิด", "โกง", "fraudster"]
# A negation exempts a term only when it ends within NEGATION_WINDOW characters before it.
NEGATION_RE = re.compile(r"≠|ไม่(?!ว่า)|ห้าม|\bnot\b", re.IGNORECASE)
NEGATION_WINDOW = 20
RESERVED_IDS = {"16", "17", "18", "19"}


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
        for term in ACCUSATORY_TERMS:
            for hit in re.finditer(re.escape(term), lower):
                if any(0 <= hit.start() - end <= NEGATION_WINDOW for end in negation_ends):
                    continue
                errors.append(f"{path.name}:{n}: accusatory term '{term}' outside Guardrails")
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

    existing = {m.group(1) for f in files if (m := FILE_ID_RE.match(f.name))}
    for f in files:
        errors += check_required_sections(f)
        errors += check_registry_refs(f, registry)
        errors += check_accusatory_terms(f)
        errors += check_cross_refs(f, existing)

    instructions = pack_dir / INSTRUCTIONS_NAME
    if instructions.exists():
        errors += check_instructions_length(instructions)
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
