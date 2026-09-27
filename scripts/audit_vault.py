#!/usr/bin/env python3
"""Auditoría sencilla del vault: metadatos, enlaces, huérfanos, wikilinks y posibles secretos.

Uso: python scripts/audit_vault.py   (código de salida 0 = OK, 1 = hay errores)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "vault"

REQUIRED_FIELDS = ["title", "type", "status", "owners", "tags", "created", "updated"]
TYPES = {"knowledge", "adr", "runbook", "delivery", "lesson", "artifact"}
STATUSES = {"draft", "active", "deprecated", "superseded"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xox[abpr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
]

errors = []


def error(kind, path, line, msg):
    errors.append(f"ERROR [{kind}] {path.relative_to(ROOT)}:{line} {msg}")


def is_exempt(path):
    rel = path.relative_to(VAULT)
    return rel.parts[0] == "templates" or path.name in {"Home.md", "README.md", "Index.md", "Governance.md"}


def strip_code(text):
    """Quita bloques cercados y código inline para no tratar ejemplos como enlaces reales."""
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return data
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return None


def check_frontmatter(path, text):
    meta = parse_frontmatter(text)
    if meta is None:
        error("frontmatter", path, 1, "falta frontmatter YAML")
        return
    for field in REQUIRED_FIELDS:
        if not meta.get(field) or meta[field] == "[]":
            error("frontmatter", path, 1, f"campo '{field}' ausente o vacío")
    if meta.get("type") and meta["type"] not in TYPES:
        error("frontmatter", path, 1, f"type inválido: {meta['type']}")
    if meta.get("status") and meta["status"] not in STATUSES:
        error("frontmatter", path, 1, f"status inválido: {meta['status']}")
    for field in ("created", "updated"):
        if meta.get(field) and not DATE_RE.match(meta[field]):
            error("frontmatter", path, 1, f"{field} no tiene formato YYYY-MM-DD")


def main():
    files = sorted(VAULT.rglob("*.md"))
    linked = set()

    for path in files:
        text = path.read_text(encoding="utf-8")
        if not is_exempt(path):
            check_frontmatter(path, text)

        for n, line in enumerate(strip_code(text).splitlines(), 1):
            if WIKILINK_RE.search(line):
                error("wikilink", path, n, "usa enlaces Markdown relativos, no [[wikilinks]]")
            for target in LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target_path = (path.parent / target.split("#", 1)[0]).resolve()
                if not target_path.exists():
                    error("broken-link", path, n, f"enlace roto: {target}")
                else:
                    linked.add(target_path)

        for n, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in SECRET_PATTERNS):
                error("secret", path, n, "posible secreto (valor no mostrado)")

    for path in files:
        if path.name != "Home.md" and path.resolve() not in linked:
            error("orphan", path, 1, "ninguna entrada del vault enlaza a este archivo")

    for line in errors:
        print(line)
    print(f"\n{len(files)} archivos revisados, {len(errors)} errores.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
