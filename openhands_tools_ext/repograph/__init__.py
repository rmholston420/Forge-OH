"""
Repository-Aware Structural Retrieval Layer (Recommendation #1).

This is a STRUCTURAL PORT of the pattern from ozyyshr/RepoGraph@6c3977d8
(Apache-2.0). The upstream implementation uses exec()/eval() on parsed
`import` statements and mangles source with string .replace() before AST
parse, which is unsafe against arbitrary user repos. This module
reimplements the same tags -> graph -> ranked-context pattern from scratch
with clean tree-sitter queries and no code execution during construction.

See:
- forge-oh-improvements-research.md \u00a7 Recommendation 1
- PORTING_LEDGER.md (RepoGraph entry, landed in slice D.5)
- docs/adr/0006-repograph-storage.md (Neo4j / DozerDB decision, D.5)
"""

from openhands_tools_ext.repograph.parser import (
    SUPPORTED_LANGUAGES,
    Tag,
    TagKind,
    extract_tags,
    language_for_path,
)

__all__ = [
    "SUPPORTED_LANGUAGES",
    "Tag",
    "TagKind",
    "extract_tags",
    "language_for_path",
]
