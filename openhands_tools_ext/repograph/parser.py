"""
Tag extraction for the RepoGraph structural retrieval layer.

Given a source file, produce a list of ``Tag`` records describing every
definition (class, function, method) and every call-site reference. These
tags are the raw material the graph builder (slice D.3) turns into a
directed graph of def/ref/method edges over which the searcher and ranker
operate.

Design notes vs. upstream ``ozyyshr/RepoGraph`` (Apache-2.0):

- No ``exec()``, no ``eval()``, no ``ast.parse`` on mutated source. Upstream
  ran ``exec()`` on parsed ``import`` statements to discover the callable
  names of imported modules; that is arbitrary code execution against user
  code and is not safe. Instead this module extracts imports symbolically
  from tree-sitter nodes and treats every imported name as "external" (a
  reference edge but never a definition edge).
- Category is derived from the tree-sitter node kind, not from a substring
  check on the source line (upstream uses ``'class ' in codeline`` which
  false-positives on any docstring containing the word "class").
- Language coverage: Python, TypeScript, TSX, JavaScript. Grammars come from
  the actively-maintained ``tree-sitter-language-pack``, not the
  unmaintained ``tree_sitter_languages`` upstream depends on.
- ``Tag`` is a frozen dataclass. Upstream uses a ``namedtuple`` with a mixed
  bag of positional/attribute access and a mutable ``dict`` in some code
  paths.

This module is pure: it does not touch the filesystem beyond opening the
file it's asked to parse, and it never talks to Neo4j.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from tree_sitter_language_pack import get_parser
except ImportError:  # pragma: no cover \u2014 exercised only on broken installs
    get_parser = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TagKind(str, Enum):
    """Whether a tag is a definition or a reference."""

    DEF = "def"
    REF = "ref"


class TagCategory(str, Enum):
    """Coarse category of the symbol carried by a tag."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"  # only for kind=REF; the *usage* of an imported name


# Extension -> tree-sitter language identifier for the language pack.
# Kept intentionally small \u2014 easy to extend later without touching the parser.
SUPPORTED_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}


def language_for_path(path: str | Path) -> str | None:
    """Return the tree-sitter language id for a file path, or None."""
    return SUPPORTED_LANGUAGES.get(Path(path).suffix.lower())


@dataclass(frozen=True)
class Tag:
    """A single definition or reference extracted from a source file.

    Attributes:
        name: The identifier the tag names (function/class/method name for
            defs; the callee name for refs).
        kind: TagKind.DEF or TagKind.REF.
        category: What sort of symbol the name refers to.
        rel_fname: Path relative to the repo root (POSIX-style forward slashes).
        fname: Absolute path on disk.
        start_line: 1-indexed line of the tag's first character.
        end_line: 1-indexed line of the tag's last character. Equals
            start_line for refs and for defs whose body is a single line.
        parent: For methods, the enclosing class name. None otherwise. Used
            by the graph builder to create ``METHOD_OF`` edges (D.3).
        info: A short human-readable snippet for the tag (function
            signature for defs; the calling line for refs). Kept short
            (<= 200 chars) so the graph builder can fold it into node
            properties without ballooning Neo4j storage.
    """

    name: str
    kind: TagKind
    category: TagCategory
    rel_fname: str
    fname: str
    start_line: int
    end_line: int
    parent: str | None = None
    info: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serializable projection for JSON logs and Neo4j properties."""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "category": self.category.value,
            "rel_fname": self.rel_fname,
            "fname": self.fname,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent": self.parent,
            "info": self.info,
        }


# --- Public entry point ------------------------------------------------------


def extract_tags(
    fname: str | Path,
    rel_fname: str | None = None,
    *,
    source: bytes | None = None,
) -> list[Tag]:
    """Extract all tags from a single source file.

    Args:
        fname: Absolute path to the file. Used verbatim in returned tags.
        rel_fname: Repo-relative POSIX path for the file. If None, defaults
            to just the file basename (callers that care about repo-relative
            paths should always pass this).
        source: If provided, use this byte string instead of reading the
            file. Lets callers avoid a second disk read when they already
            have the contents in memory.

    Returns:
        A list of Tag records. Empty on parse failure or unsupported
        language; never raises for source-level errors.
    """
    if get_parser is None:  # pragma: no cover
        logger.warning(
            "tree_sitter_language_pack is not installed; extract_tags returning an empty list"
        )
        return []

    path = Path(fname)
    rel = rel_fname if rel_fname is not None else path.name
    lang_id = language_for_path(path)
    if lang_id is None:
        logger.debug("skipping %s: unsupported extension", path)
        return []

    if source is None:
        try:
            source = path.read_bytes()
        except OSError as exc:
            logger.warning("cannot read %s: %s", path, exc)
            return []

    try:
        parser = get_parser(lang_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("no parser for language %s: %s", lang_id, exc)
        return []

    try:
        tree = parser.parse(source)
    except Exception as exc:
        logger.warning("tree-sitter parse failed for %s: %s", path, exc)
        return []

    ctx = _WalkContext(
        rel_fname=rel,
        fname=str(path),
        source=source,
        source_lines=source.splitlines(),
    )

    extractor = _EXTRACTORS.get(lang_id)
    if extractor is None:  # pragma: no cover \u2014 SUPPORTED_LANGUAGES guards this
        return []
    extractor(tree.root_node, ctx)
    return ctx.tags


# --- Internals ---------------------------------------------------------------


@dataclass
class _WalkContext:
    """Mutable bag threaded through the recursive walk. Not part of the API."""

    rel_fname: str
    fname: str
    source: bytes
    source_lines: list[bytes]
    tags: list[Tag] = field(default_factory=list)
    # Stack of enclosing class names so nested classes still record correctly.
    class_stack: list[str] = field(default_factory=list)
    # Stack of enclosing (class, function) so we can distinguish methods
    # from module-level functions in Python.
    function_stack: list[str] = field(default_factory=list)


def _text(node: Any, source: bytes) -> str:
    """Return the raw source text a tree-sitter node covers."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _line_of(node: Any, source_lines: list[bytes]) -> str:
    """Return the source line containing the node's start point, decoded."""
    row = node.start_point[0]
    if 0 <= row < len(source_lines):
        return source_lines[row].decode("utf-8", errors="replace")
    return ""


def _signature(node: Any, source_lines: list[bytes]) -> str:
    """Return a short human-readable signature snippet for a def-node."""
    line = _line_of(node, source_lines).strip()
    if len(line) > 200:
        line = line[:197] + "..."
    return line


def _find_child(node: Any, *field_names: str) -> Any | None:
    """Return the first child_by_field_name(<name>) that matches."""
    for name in field_names:
        child = node.child_by_field_name(name)
        if child is not None:
            return child
    return None


# --- Python extractor --------------------------------------------------------


def _extract_python(root: Any, ctx: _WalkContext) -> None:
    """Walk a Python tree-sitter tree and populate ctx.tags."""
    _visit_python(root, ctx)


def _visit_python(node: Any, ctx: _WalkContext) -> None:
    node_type = node.type

    if node_type == "class_definition":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            name = _text(name_node, ctx.source)
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.DEF,
                    category=TagCategory.CLASS,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=ctx.class_stack[-1] if ctx.class_stack else None,
                    info=_signature(node, ctx.source_lines),
                )
            )
            ctx.class_stack.append(name)
            for child in node.children:
                _visit_python(child, ctx)
            ctx.class_stack.pop()
            return

    if node_type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            name = _text(name_node, ctx.source)
            in_class = bool(ctx.class_stack)
            category = TagCategory.METHOD if in_class else TagCategory.FUNCTION
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.DEF,
                    category=category,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=ctx.class_stack[-1] if in_class else None,
                    info=_signature(node, ctx.source_lines),
                )
            )
            ctx.function_stack.append(name)
            for child in node.children:
                _visit_python(child, ctx)
            ctx.function_stack.pop()
            return

    if node_type == "call":
        # Extract the callee identifier. Two shapes matter:
        #   foo(...)          -> function: (identifier)
        #   obj.foo(...)      -> function: (attribute attribute: (identifier))
        fn_node = node.child_by_field_name("function")
        if fn_node is not None:
            callee = _callee_name_python(fn_node, ctx.source)
            if callee is not None:
                ctx.tags.append(
                    Tag(
                        name=callee,
                        kind=TagKind.REF,
                        category=TagCategory.FUNCTION,
                        rel_fname=ctx.rel_fname,
                        fname=ctx.fname,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=(ctx.class_stack[-1] if ctx.class_stack else None),
                        info=_signature(node, ctx.source_lines),
                    )
                )

    # Import statements produce REF tags but never DEF tags \u2014 we know the
    # name is used in this file but not defined here.
    if node_type in ("import_statement", "import_from_statement"):
        for name in _imported_names_python(node, ctx.source):
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.REF,
                    category=TagCategory.IMPORT,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=None,
                    info=_signature(node, ctx.source_lines),
                )
            )
        # No point descending into the import for further tags.
        return

    for child in node.children:
        _visit_python(child, ctx)


def _callee_name_python(fn_node: Any, source: bytes) -> str | None:
    """Extract the callee identifier from a Python ``call.function`` node."""
    if fn_node.type == "identifier":
        return _text(fn_node, source)
    if fn_node.type == "attribute":
        attr = fn_node.child_by_field_name("attribute")
        if attr is not None and attr.type == "identifier":
            return _text(attr, source)
    # Subscript, lambda, or something exotic \u2014 skip.
    return None


def _imported_names_python(node: Any, source: bytes) -> list[str]:
    """Extract the names introduced by a Python import statement.

    Handles the four common forms:
      import foo
      import foo as bar
      from foo import bar
      from foo import bar as baz
    """
    names: list[str] = []
    for child in _walk(node):
        if child.type == "dotted_name":
            names.append(_text(child, source))
        elif child.type == "aliased_import":
            alias = child.child_by_field_name("alias")
            if alias is not None:
                names.append(_text(alias, source))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _walk(node: Any) -> Iterable[Any]:
    """Yield node and all descendants (depth-first, pre-order)."""
    yield node
    for child in node.children:
        yield from _walk(child)


# --- TypeScript / TSX / JavaScript extractor --------------------------------


def _extract_ts(root: Any, ctx: _WalkContext) -> None:
    _visit_ts(root, ctx)


# tree-sitter-typescript uses these node types (verified against the grammar):
_TS_CLASS_TYPES = {"class_declaration", "abstract_class_declaration"}
_TS_FUNCTION_TYPES = {
    "function_declaration",
    "generator_function_declaration",
}
_TS_METHOD_TYPES = {
    "method_definition",
    "method_signature",
    "abstract_method_signature",
}
_TS_ARROW_ASSIGN_TYPES = {
    # `const x = () => {}` and `const x = function () {}` \u2014 grabbed via
    # variable_declarator when the RHS is a function/arrow_function.
    "variable_declarator",
}


def _visit_ts(node: Any, ctx: _WalkContext) -> None:
    node_type = node.type

    if node_type in _TS_CLASS_TYPES:
        name_node = _find_child(node, "name")
        if name_node is not None:
            name = _text(name_node, ctx.source)
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.DEF,
                    category=TagCategory.CLASS,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=ctx.class_stack[-1] if ctx.class_stack else None,
                    info=_signature(node, ctx.source_lines),
                )
            )
            ctx.class_stack.append(name)
            for child in node.children:
                _visit_ts(child, ctx)
            ctx.class_stack.pop()
            return

    if node_type in _TS_FUNCTION_TYPES:
        name_node = _find_child(node, "name")
        if name_node is not None:
            name = _text(name_node, ctx.source)
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.DEF,
                    category=TagCategory.FUNCTION,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=None,
                    info=_signature(node, ctx.source_lines),
                )
            )

    if node_type in _TS_METHOD_TYPES:
        name_node = _find_child(node, "name")
        if name_node is not None:
            name = _text(name_node, ctx.source)
            if name and not name.startswith("("):
                ctx.tags.append(
                    Tag(
                        name=name,
                        kind=TagKind.DEF,
                        category=TagCategory.METHOD,
                        rel_fname=ctx.rel_fname,
                        fname=ctx.fname,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=(ctx.class_stack[-1] if ctx.class_stack else None),
                        info=_signature(node, ctx.source_lines),
                    )
                )

    if node_type in _TS_ARROW_ASSIGN_TYPES:
        _capture_ts_arrow_or_fn_assignment(node, ctx)

    if node_type == "call_expression":
        fn_node = _find_child(node, "function")
        if fn_node is not None:
            callee = _callee_name_ts(fn_node, ctx.source)
            if callee is not None:
                ctx.tags.append(
                    Tag(
                        name=callee,
                        kind=TagKind.REF,
                        category=TagCategory.FUNCTION,
                        rel_fname=ctx.rel_fname,
                        fname=ctx.fname,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        parent=(ctx.class_stack[-1] if ctx.class_stack else None),
                        info=_signature(node, ctx.source_lines),
                    )
                )

    if node_type == "import_statement":
        for name in _imported_names_ts(node, ctx.source):
            ctx.tags.append(
                Tag(
                    name=name,
                    kind=TagKind.REF,
                    category=TagCategory.IMPORT,
                    rel_fname=ctx.rel_fname,
                    fname=ctx.fname,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=None,
                    info=_signature(node, ctx.source_lines),
                )
            )
        return

    for child in node.children:
        _visit_ts(child, ctx)


def _capture_ts_arrow_or_fn_assignment(node: Any, ctx: _WalkContext) -> None:
    """Emit a FUNCTION def for ``const foo = () => ...`` and similar."""
    name_node = _find_child(node, "name")
    value_node = _find_child(node, "value")
    if name_node is None or value_node is None:
        return
    if name_node.type != "identifier":
        return
    if value_node.type not in (
        "arrow_function",
        "function_expression",
        "function",
    ):
        return
    ctx.tags.append(
        Tag(
            name=_text(name_node, ctx.source),
            kind=TagKind.DEF,
            category=TagCategory.FUNCTION,
            rel_fname=ctx.rel_fname,
            fname=ctx.fname,
            start_line=node.start_point[0] + 1,
            end_line=value_node.end_point[0] + 1,
            parent=None,
            info=_signature(node, ctx.source_lines),
        )
    )


def _callee_name_ts(fn_node: Any, source: bytes) -> str | None:
    """Extract the callee identifier from a JS/TS ``call_expression.function``."""
    if fn_node.type == "identifier":
        return _text(fn_node, source)
    if fn_node.type == "member_expression":
        # obj.foo(...) \u2014 the `property` field is the method identifier.
        prop = fn_node.child_by_field_name("property")
        if prop is not None and prop.type in (
            "property_identifier",
            "identifier",
        ):
            return _text(prop, source)
    return None


def _imported_names_ts(node: Any, source: bytes) -> list[str]:
    """Extract the names introduced by a JS/TS ``import`` statement.

    Covers:
      import foo from '...'                (default)
      import { a, b as c } from '...'      (named + aliased)
      import * as ns from '...'            (namespace)
      import foo, { a } from '...'         (default + named)
    """
    names: list[str] = []
    for child in _walk(node):
        t = child.type
        if t == "identifier" and child.parent is not None:
            # Only capture identifiers inside import_clause / named_imports /
            # namespace_import / import_specifier, never the module string.
            parent_types = _ancestor_types_ts(child)
            if parent_types & {
                "import_clause",
                "named_imports",
                "namespace_import",
                "import_specifier",
            }:
                names.append(_text(child, source))
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _ancestor_types_ts(node: Any) -> set[str]:
    types: set[str] = set()
    cur = node.parent
    hops = 0
    while cur is not None and hops < 6:
        types.add(cur.type)
        cur = cur.parent
        hops += 1
    return types


# --- Extractor dispatch table -----------------------------------------------


_EXTRACTORS = {
    "python": _extract_python,
    "typescript": _extract_ts,
    "tsx": _extract_ts,
    "javascript": _extract_ts,
}
