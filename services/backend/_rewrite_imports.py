from __future__ import annotations

import re
from pathlib import Path

root = Path(__file__).resolve().parent

PROTOCOL_MAP = {
    "ChatModel": "backend.application.llm.chat_model",
    "Embedder": "backend.application.llm.embedder",
    "DocumentParser": "backend.application.parsing.document_parser",
    "DocumentChunker": "backend.application.parsing.document_chunker",
    "ArchiveExtractor": "backend.application.parsing.archive_extractor",
    "EngagementRepository": "backend.application.repositories.engagement",
    "DocumentRepository": "backend.application.repositories.document",
    "SessionRepository": "backend.application.repositories.session",
    "UploadRepository": "backend.application.repositories.upload",
    "AskSessionBound": "backend.application.repositories.ask_session_bound",
    "VectorIndex": "backend.application.storage.vector_index",
    "DocumentStorage": "backend.application.storage.document_storage",
    "JobQueue": "backend.application.storage.job_queue",
}

DTO_NAMES = {
    "AskResult",
    "ChatMessage",
    "EmbedResult",
    "IncompleteStructuredOutputError",
    "ParsedChunk",
    "ParsedDocument",
    "RetrievalScope",
    "ScoredChunk",
    "StoredFile",
    "StructuredResult",
    "ThinkingCallbacks",
    "ToolCall",
    "ToolSpec",
    "ToolTurnResult",
}

PG_REPO_MAP = {
    "PostgresEngagementRepository": "backend.infrastructure.postgres.repositories.engagement",
    "PostgresDocumentRepository": "backend.infrastructure.postgres.repositories.document",
    "PostgresSessionRepository": "backend.infrastructure.postgres.repositories.session",
    "PostgresUploadRepository": "backend.infrastructure.postgres.repositories.upload",
}

IMPORT_RE = re.compile(
    r"from\s+(backend\.application\.ports(?:\.\w+)?)\s+import\s+\((.*?)\)|"
    r"from\s+(backend\.application\.ports(?:\.\w+)?)\s+import\s+([^\n]+)",
    re.S,
)

PARSING_PKG_RE = re.compile(
    r"from\s+backend\.infrastructure\.parsing\s+import\s+\((.*?)\)|"
    r"from\s+backend\.infrastructure\.parsing\s+import\s+([^\n]+)",
    re.S,
)

PG_REPOS_RE = re.compile(
    r"from\s+backend\.infrastructure\.postgres\.repositories\s+import\s+\((.*?)\)|"
    r"from\s+backend\.infrastructure\.postgres\.repositories\s+import\s+([^\n]+)",
    re.S,
)


def split_names(blob: str) -> list[str]:
    names: list[str] = []
    for part in blob.replace("\n", ",").split(","):
        name = part.strip().rstrip(",")
        if not name:
            continue
        name = name.split("#", 1)[0].strip()
        if " as " in name:
            name = name.split(" as ", 1)[0].strip()
        if name:
            names.append(name)
    return names


def format_imports(module_to_names: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for module in sorted(module_to_names):
        names = sorted(set(module_to_names[module]))
        if len(names) == 1:
            lines.append(f"from {module} import {names[0]}")
        else:
            inner = ",\n".join(f"    {n}" for n in names)
            lines.append(f"from {module} import (\n{inner},\n)")
    return "\n".join(lines)


def rewrite_ports_import(match: re.Match[str]) -> str:
    names = split_names(match.group(2) if match.group(1) is not None else match.group(4))
    modules: dict[str, list[str]] = {}
    for name in names:
        if name in PROTOCOL_MAP:
            modules.setdefault(PROTOCOL_MAP[name], []).append(name)
        elif name in DTO_NAMES:
            modules.setdefault("backend.application.dto", []).append(name)
        else:
            raise SystemExit(f"Unknown ports import name: {name} in {match.group(0)!r}")
    return format_imports(modules)


def rewrite_parsing_pkg(match: re.Match[str]) -> str:
    names = split_names(match.group(1) or match.group(2))
    mapping = {
        "build_document_parser": "backend.infrastructure.parsing.parsers.default",
        "build_document_chunker": "backend.infrastructure.parsing.chunking",
        "build_archive_extractor": "backend.infrastructure.parsing.archive",
    }
    modules: dict[str, list[str]] = {}
    for name in names:
        if name not in mapping:
            raise SystemExit(f"Unknown parsing import: {name}")
        modules.setdefault(mapping[name], []).append(name)
    return format_imports(modules)


def rewrite_pg_repos(match: re.Match[str]) -> str:
    names = split_names(match.group(1) or match.group(2))
    modules: dict[str, list[str]] = {}
    for name in names:
        if name not in PG_REPO_MAP:
            raise SystemExit(f"Unknown pg repo import: {name}")
        modules.setdefault(PG_REPO_MAP[name], []).append(name)
    return format_imports(modules)


changed: list[str] = []
for path in root.rglob("*.py"):
    if path.name == "_rewrite_imports.py":
        continue
    text = path.read_text(encoding="utf-8")
    new = text
    new = IMPORT_RE.sub(rewrite_ports_import, new)
    new = PARSING_PKG_RE.sub(rewrite_parsing_pkg, new)
    new = PG_REPOS_RE.sub(rewrite_pg_repos, new)
    new = new.replace(
        "from backend.application.ports.parsing import ArchiveExtractor",
        "from backend.application.parsing.archive_extractor import ArchiveExtractor",
    )
    new = new.replace(
        "from backend.application.ports.parsing import DocumentChunker",
        "from backend.application.parsing.document_chunker import DocumentChunker",
    )
    new = new.replace(
        "from backend.application.ports.parsing import DocumentParser",
        "from backend.application.parsing.document_parser import DocumentParser",
    )
    if new != text:
        path.write_text(new, encoding="utf-8", newline="\n")
        changed.append(str(path.relative_to(root)))

print(f"updated {len(changed)} files")
for item in changed:
    print(item)
