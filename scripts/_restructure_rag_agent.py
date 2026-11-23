"""One-shot: nest ingestion worker under rag; move ask agent out of rag."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "services/backend/src/backend/application"
RAG = APP / "rag"
AGENT = APP / "agent"
RAG_WORKER = RAG / "worker"


def move_agent_and_worker() -> None:
    AGENT.mkdir(exist_ok=True)
    RAG_WORKER.mkdir(exist_ok=True)

    for name in (
        "agent.py",
        "graph.py",
        "prompts.py",
        "nodes.py",
        "state.py",
        "citations.py",
        "progress.py",
    ):
        src = RAG / name
        if src.exists():
            shutil.move(str(src), str(AGENT / name))

    tools_src = RAG / "tools"
    if tools_src.exists():
        shutil.move(str(tools_src), str(AGENT / "tools"))

    old_worker = APP / "worker"
    if (old_worker / "main.py").exists():
        shutil.move(str(old_worker / "main.py"), str(RAG_WORKER / "main.py"))

    ingestion = APP / "ingestion"
    if (ingestion / "process_item.py").exists():
        shutil.move(str(ingestion / "process_item.py"), str(RAG_WORKER / "process_item.py"))

    for path in (old_worker, ingestion):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def rewrite_imports() -> None:
    # Longest prefixes first so we never double-rewrite.
    replacements = (
        ("backend.application.rag.tools", "backend.application.agent.tools"),
        ("backend.application.rag.progress", "backend.application.agent.progress"),
        ("backend.application.rag.agent", "backend.application.agent.agent"),
        ("backend.application.rag.graph", "backend.application.agent.graph"),
        ("backend.application.rag.prompts", "backend.application.agent.prompts"),
        ("backend.application.rag.nodes", "backend.application.agent.nodes"),
        ("backend.application.rag.citations", "backend.application.agent.citations"),
        ("backend.application.rag.state", "backend.application.agent.state"),
        (
            "backend.application.ingestion.process_item",
            "backend.application.rag.worker.process_item",
        ),
        ("backend.application.ingestion", "backend.application.rag.worker"),
        ("backend.application.worker", "backend.application.rag.worker"),
    )
    skip_parts = {".git", "__pycache__", ".venv", "node_modules"}
    exts = {".py", ".md", ".ini", ".toml"}
    updated = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in exts:
            continue
        if any(part in skip_parts for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        new = text
        for old, repl in replacements:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            updated += 1
            print(f"updated {path.relative_to(ROOT)}")
    print(f"rewrote {updated} files")


def main() -> None:
    move_agent_and_worker()
    rewrite_imports()
    print("agent:", sorted(p.name for p in AGENT.iterdir()))
    print("rag:", sorted(p.name for p in RAG.iterdir()))
    print("rag/worker:", sorted(p.name for p in RAG_WORKER.iterdir()))


if __name__ == "__main__":
    main()
