"""Product Context Loader — injects ADR context into agent planning phase.

Reads .openhands/context/ directory and scores documents by keyword overlap
with the current task. Injecting relevant architectural docs increases agent
compliance from ~46% to ~95%.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple


class ContextDoc(NamedTuple):
    path: str
    content: str
    score: float


class ContextLoader:
    def __init__(self, context_dir: str = ".openhands/context") -> None:
        self.context_dir = Path(context_dir)

    def _load_docs(self) -> list[ContextDoc]:
        docs: list[ContextDoc] = []
        if not self.context_dir.exists():
            return docs
        for fpath in self.context_dir.rglob("*.md"):
            try:
                content = fpath.read_text(encoding="utf-8")
                docs.append(ContextDoc(path=str(fpath), content=content, score=0.0))
            except OSError:
                pass
        return docs

    def _score(self, doc: ContextDoc, task: str) -> float:
        task_words = set(task.lower().split())
        doc_words = set(doc.content.lower().split())
        overlap = task_words & doc_words
        return len(overlap) / max(len(task_words), 1)

    def get_relevant_context(self, task: str, top_k: int = 3) -> list[ContextDoc]:
        """Return top-k most relevant context docs for the given task."""
        docs = self._load_docs()
        scored = [ContextDoc(d.path, d.content, self._score(d, task)) for d in docs]
        return sorted(scored, key=lambda d: d.score, reverse=True)[:top_k]

    def build_context_preamble(self, task: str) -> str:
        """Build a context preamble string to prepend to agent prompts."""
        docs = self.get_relevant_context(task)
        if not docs:
            return ""
        parts = ["## Project Context\n"]
        for doc in docs:
            parts.append(f"### {os.path.basename(doc.path)}\n{doc.content}\n")
        return "\n".join(parts)
