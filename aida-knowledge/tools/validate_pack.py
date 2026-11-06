"""Validate the AIDA Knowledge Pack.

Usage: python3 validate_pack.py [pack_dir]
pack_dir defaults to the aida-knowledge/ folder that contains this script.
Exit code 0 when every check passes, 1 otherwise.
"""
import ast
import importlib.util
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
RESERVED_IDS: set = set()  # AIDA-16..19 exist from phase C1 on

MACHINE_CONFIG_HEADING = "## Machine Config (สำหรับ recipe)"
HEADING_KEY_RE = re.compile(r"^#{2,4}\s+([A-Z][A-Z0-9_]*(?:\.[A-Z0-9_]+)+)\b", re.MULTILINE)
KNOWLEDGE_FILES = 20  # Agent Builder Knowledge holds at most 20 files; the pack uses every slot
ENGINE_NAME = "aida_engine.py"
ENGINE_REL = Path("engine") / ENGINE_NAME  # approach 2 keeps the engine outside knowledge/
ENGINE_VERSION_RE = re.compile(r"aida_engine\.py`?\s+v(\d+(?:\.\d+)+)")
ENGINE_VERSION_FILES = ("AIDA-00", "AIDA-19")  # must state the engine version
RISK_LIBRARY_NAME = "AIDA-18-risk-library.md"
# the 14 fixed roles (global constraint); certified checks and the Risk Library may use no other
ROLES = ("record_id", "date", "amount", "entity", "counterparty", "contract", "category", "channel",
         "created_by", "approved_by", "document_no", "limit", "due_date", "opened_at")
ALLOWED_IMPORTS = {"pandas", "numpy", "openpyxl"}
NETWORK_MODULES = {"requests", "urllib", "urllib3", "http", "httpx", "socket", "ssl", "ftplib", "smtplib", "poplib",
                   "imaplib", "aiohttp", "xmlrpc", "telnetlib", "websocket", "websockets", "asyncio", "webbrowser"}


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


def knowledge_files(knowledge_dir: Path) -> list[Path]:
    """Every file that would be uploaded as Knowledge (any type; hidden files are ignored)."""
    return sorted(p for p in knowledge_dir.iterdir() if p.is_file() and not p.name.startswith("."))


def check_file_count(knowledge_dir: Path, expected: int = KNOWLEDGE_FILES) -> list[str]:
    count = len(knowledge_files(knowledge_dir))
    if count != expected:
        return [f"{knowledge_dir.name}: {count} files, the pack must hold exactly {expected} (Knowledge limit)"]
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


NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)(\s*%)?")


def _numbers(text: str) -> list[float]:
    """Numbers in `text` in order; '95%' becomes 0.95 and thousands separators are dropped."""
    out = []
    for num, pct in NUMBER_RE.findall(text):
        value = float(num.replace(",", ""))
        out.append(value / 100 if pct else value)
    return out


def _leaves(value) -> list:
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _leaves(v)]
    return [value]


def check_machine_config_values(registry_path: Path) -> list[str]:
    """Machine Config numbers must equal the numbers in the matching `KEY = value` table rows."""
    config, errors = parse_machine_config(registry_path)
    registry, _ = parse_registry(registry_path)
    name = registry_path.name
    for key, value in config.items():
        if key.startswith("_") or key == "ASSESS.PRIORITY" or key not in registry or isinstance(value, bool):
            continue
        row = registry[key]
        row_numbers = _numbers(row)
        if isinstance(value, dict):
            for leaf in _leaves(value):
                if isinstance(leaf, bool):
                    continue
                if isinstance(leaf, str):
                    ok = leaf in row
                else:
                    ok = any(abs(leaf - n) < 1e-9 for n in row_numbers)
                if not ok:
                    errors.append(f"{name}: Machine Config {key} value {leaf!r} not found in table row '{row}'")
        elif isinstance(value, (int, float)):
            if not row_numbers or abs(value - row_numbers[0]) > 1e-9:
                errors.append(f"{name}: Machine Config {key} = {value} but table row says '{row}'")
    return errors


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
    errors += check_machine_config_values(registry_path)
    if "ASSESS.PRIORITY" in config:
        table = priority_from_table(_read(registry_path))
        if table is not None and config["ASSESS.PRIORITY"] != table:
            errors.append(f"{registry_path.name}: Machine Config ASSESS.PRIORITY differs from '### ตาราง Priority'")
    return errors


def find_engine(pack_dir: Path) -> Path | None:
    """The engine source: aida-knowledge/engine/aida_engine.py (approach 2 keeps it out of knowledge/)."""
    path = pack_dir / ENGINE_REL
    return path if path.is_file() else None


def engine_constants(engine_path: Path) -> dict:
    """Module-level string constants (__version__, REGISTRY_VERSION, ...) read with ast, without importing."""
    out = {}
    for node in ast.parse(_read(engine_path)).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = node.value.value
    return out


def check_engine_version(engine_path: Path, knowledge_dir: Path) -> list[str]:
    """`aida_engine.py` vX.Y.Z in the Knowledge files must equal __version__; AIDA-00 and AIDA-19 must state it."""
    version = engine_constants(engine_path).get("__version__")
    if not version:
        return [f"{engine_path.name}: no __version__ string"]
    errors: list[str] = []
    stated = set()
    for f in sorted(knowledge_dir.glob("*.md")):
        found = ENGINE_VERSION_RE.findall(_read(f))
        if found and (m := FILE_ID_RE.match(f.name)):
            stated.add(f"AIDA-{m.group(1)}")
        for v in dict.fromkeys(found):
            if v != version:
                errors.append(f"{f.name}: states aida_engine.py v{v} but the engine __version__ is {version}")
    for fid in ENGINE_VERSION_FILES:
        if fid not in stated:
            errors.append(f"{fid}: must state the engine version as '`aida_engine.py` v{version}'")
    return errors


def check_engine_registry_version(engine_path: Path, registry_path: Path) -> list[str]:
    registry, _ = parse_registry(registry_path)
    want = registry.get("REGISTRY.VERSION")
    got = engine_constants(engine_path).get("REGISTRY_VERSION")
    if want is None:
        return [f"{registry_path.name}: no `REGISTRY.VERSION = ...`"]
    if got != want:
        return [f"{engine_path.name}: REGISTRY_VERSION {got!r} but AIDA-14 says REGISTRY.VERSION = {want}"]
    return []


def engine_cfg_keys(engine_path: Path) -> list[str]:
    """String keys read as cfg["KEY"] (any variable whose name contains 'cfg') in the engine code."""
    keys = []
    for node in ast.walk(ast.parse(_read(engine_path))):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and "cfg" in node.value.id
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            keys.append(node.slice.value)
    return list(dict.fromkeys(keys))


def check_engine_cfg_keys(engine_path: Path, registry_path: Path) -> list[str]:
    config, errors = parse_machine_config(registry_path)
    if errors:
        return errors
    return [f"{engine_path.name}: reads cfg['{k}'] which is not in the AIDA-14 Machine Config"
            for k in engine_cfg_keys(engine_path) if not k.startswith("_") and k not in config]


def check_engine_imports(engine_path: Path) -> list[str]:
    """pandas, numpy, openpyxl and the standard library only; never a network library."""
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    errors: list[str] = []
    for node in ast.walk(ast.parse(_read(engine_path))):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names = [node.module]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top in NETWORK_MODULES:
                errors.append(f"{engine_path.name}:{node.lineno}: imports network library '{name}'")
            elif top not in ALLOWED_IMPORTS and stdlib and top not in stdlib:
                errors.append(f"{engine_path.name}:{node.lineno}: imports '{name}' (allowed: pandas, numpy, "
                              "openpyxl and the standard library)")
    return errors


def load_engine(engine_path: Path):
    """Import the engine by path under a private name (needs pandas, numpy and openpyxl)."""
    spec = importlib.util.spec_from_file_location("aida_engine_validate", str(engine_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _risk_builder():
    spec = importlib.util.spec_from_file_location(
        "build_risk_library_md", str(Path(__file__).resolve().parent / "build_risk_library_md.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_risk_references(risk_library: dict, checks: dict) -> list[str]:
    """Each risk names checks that exist and roles among the 14; each check requires roles among the 14."""
    errors: list[str] = []
    for rid, r in risk_library.items():
        for c in r.get("checks", []):
            if c not in checks:
                errors.append(f"Risk Library {rid}: check {c} does not exist in the engine CHECKS")
        bad = [x for x in list(r.get("min_roles", [])) + list(r.get("join_roles", [])) if x not in ROLES]
        if bad:
            errors.append(f"Risk Library {rid}: roles {', '.join(bad)} are not among the 14 roles")
    for cid, spec in checks.items():
        bad = [x for x in list(spec.get("requires", [])) + list(spec.get("optional", [])) if x not in ROLES]
        if bad:
            errors.append(f"check {cid}: roles {', '.join(bad)} are not among the 14 roles")
    return errors


def check_risk_library(engine, aida18_path: Path) -> list[str]:
    """AIDA-18 must be exactly what tools/build_risk_library_md.py makes from the engine."""
    want = _risk_builder().render(engine)
    if not aida18_path.exists():
        return [f"{aida18_path.name} is missing — run tools/build_risk_library_md.py"]
    have = _read(aida18_path)
    if have == want:
        return []
    a, b = have.splitlines(), want.splitlines()
    n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return [f"{aida18_path.name}:{n + 1}: differs from the engine Risk Library / CHECKS — "
            "run tools/build_risk_library_md.py (never edit AIDA-18 by hand)"]


def check_engine(pack_dir: Path, knowledge: Path, registry_path: Path) -> list[str]:
    engine_path = find_engine(pack_dir)
    if engine_path is None:
        return [f"{ENGINE_REL.as_posix()} is missing (the validator reads the engine from aida-knowledge/engine/)"]
    errors: list[str] = []
    copy = knowledge / ENGINE_NAME
    if copy.exists() and copy.read_bytes() != engine_path.read_bytes():
        errors.append(f"knowledge/{ENGINE_NAME} differs from {ENGINE_REL.as_posix()} — copy the engine again")
    errors += check_engine_imports(engine_path)
    errors += check_engine_version(engine_path, knowledge)
    if registry_path.exists():
        errors += check_engine_registry_version(engine_path, registry_path)
        errors += check_engine_cfg_keys(engine_path, registry_path)
    try:
        engine = load_engine(engine_path)
    except Exception as e:  # noqa: BLE001 - report, do not crash the validator
        return errors + [f"{engine_path.name}: cannot be imported ({type(e).__name__}: {e}) — needs pandas, numpy, openpyxl"]
    errors += check_risk_references(engine.RISK_LIBRARY, engine.CHECKS)
    errors += check_risk_library(engine, knowledge / RISK_LIBRARY_NAME)
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

    if registry_path.exists():
        errors += check_machine_config(registry_path)

    existing = {m.group(1) for f in files if (m := FILE_ID_RE.match(f.name))}
    if (knowledge / ENGINE_NAME).exists():  # approach 3: the engine itself takes slot 16 (engine install doc)
        existing.add("16")
    for f in files:
        errors += check_required_sections(f)
        errors += check_registry_refs(f, registry)
        errors += check_accusatory_terms(f)
        errors += check_cross_refs(f, existing)
    errors += check_shared_tables(knowledge)
    errors += check_engine(pack_dir, knowledge, registry_path)

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
    print(f"OK: {len(knowledge_files(pack_dir / 'knowledge'))} files validated")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
