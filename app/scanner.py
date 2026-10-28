"""Small, deterministic source inventory. Rules are signals, not compiler analysis."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

EXTENSIONS = {".java": "Java", ".ts": "TypeScript"}
EXCLUDED = {".git", "node_modules", "build", "dist", "target", "coverage", ".angular", "secrets"}
MAX_FILE_BYTES = 128_000
MAX_FILES_PER_LANGUAGE = 350
MAX_LINE_FINDINGS = 8


def stable_id(*parts: object) -> str:
    return hashlib.sha256("\x00".join(map(str, parts)).encode()).hexdigest()[:24]


def module_for(path: Path) -> str:
    parts = path.parts
    for marker in ("domain", "app"):
        if marker in parts:
            position = parts.index(marker)
            if position + 1 < len(parts) - 1:
                return parts[position + 1]
            return f"{marker}-root"
    return parts[0] if len(parts) > 1 else "root"


def candidate_paths(root: Path):
    by_language = {language: [] for language in EXTENSIONS.values()}
    for directory, folders, filenames in os.walk(root):
        folders[:] = sorted(name for name in folders if name not in EXCLUDED and not name.startswith("."))
        for filename in filenames:
            path = Path(directory) / filename
            if path.is_symlink() or path.suffix not in EXTENSIONS or path.stat().st_size > MAX_FILE_BYTES:
                continue
            by_language[EXTENSIONS[path.suffix]].append(path)
    for language in by_language:
        yield from sorted(by_language[language])[:MAX_FILES_PER_LANGUAGE]


def analyze_file(root: Path, path: Path, project: str):
    relative = path.relative_to(root).as_posix()
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    language = EXTENSIONS[path.suffix]
    module = module_for(Path(relative))
    file_id = stable_id(project, relative)
    findings = []

    def finding(rule: str, severity: str, line: int, excerpt: str, message: str):
        findings.append((stable_id(file_id, rule, line), {
            "project": project, "file_id": file_id, "path": relative,
            "module": module, "language": language, "rule": rule,
            "severity": severity, "line": line, "excerpt": excerpt[:300],
            "message": message,
        }))

    if len(lines) > 500:
        finding("large_file", "medium", 1, "", f"{len(lines)} soros fájl; érdemes felülvizsgálni a méretét.")

    long_lines = 0
    for number, line in enumerate(lines, 1):
        trimmed = line.strip()
        if re.search(r"\b(?:TODO|FIXME|HACK)\b", line, re.IGNORECASE):
            finding("work_marker", "low", number, trimmed, "Nyitott munkajelölő a forrásban.")
        if len(line) > 160 and long_lines < MAX_LINE_FINDINGS:
            finding("long_line", "low", number, trimmed, "160 karakternél hosszabb sor.")
            long_lines += 1
        if re.search(r"\bcatch\s*\(\s*(?:Exception|Throwable)\b", line):
            finding("broad_catch", "medium", number, trimmed, "Általános kivétel elfogása; ellenőrizd a kezelést.")

    file_doc = {
        "project": project, "path": relative, "module": module,
        "language": language, "line_count": len(lines),
        "finding_count": len(findings), "content": content,
    }
    return (file_id, file_doc), findings


def scan(root: Path, project: str):
    if not root.is_dir():
        raise FileNotFoundError(f"Forrásmappa nem található: {root}")
    files, findings = [], []
    for path in candidate_paths(root):
        file_doc, file_findings = analyze_file(root, path, project)
        files.append(file_doc)
        findings.extend(file_findings)
    if not files:
        raise ValueError("Nincs elemezhető Java vagy TypeScript fájl a forrásmappában.")
    return files, findings
