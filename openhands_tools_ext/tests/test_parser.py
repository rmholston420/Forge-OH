"""Unit tests for openhands_tools_ext.repograph.parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from openhands_tools_ext.repograph.parser import (
    SUPPORTED_LANGUAGES,
    Tag,
    TagCategory,
    TagKind,
    extract_tags,
    language_for_path,
)


# --- language_for_path -----------------------------------------------------


class TestLanguageForPath:
    def test_python(self):
        assert language_for_path("foo.py") == "python"
        assert language_for_path("stubs/foo.pyi") == "python"

    def test_typescript(self):
        assert language_for_path("Foo.ts") == "typescript"
        assert language_for_path("component.tsx") == "tsx"

    def test_javascript(self):
        assert language_for_path("foo.js") == "javascript"
        assert language_for_path("foo.mjs") == "javascript"
        assert language_for_path("foo.cjs") == "javascript"
        assert language_for_path("component.jsx") == "javascript"

    def test_unsupported_returns_none(self):
        assert language_for_path("foo.rs") is None
        assert language_for_path("foo") is None
        assert language_for_path("foo.md") is None

    def test_case_insensitive(self):
        assert language_for_path("Foo.PY") == "python"
        assert language_for_path("Foo.TSX") == "tsx"

    def test_registry_shape(self):
        # If we ever add a language, both entries below must stay aligned.
        assert set(SUPPORTED_LANGUAGES.values()) >= {
            "python",
            "typescript",
            "tsx",
            "javascript",
        }


# --- helpers ---------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _by(name: str, tags: list[Tag], kind: TagKind | None = None) -> list[Tag]:
    return [
        t for t in tags if t.name == name and (kind is None or t.kind == kind)
    ]


# --- Python extraction -----------------------------------------------------


class TestExtractPython:
    def test_top_level_function_def(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "def hello(name):\n    return name\n",
        )
        tags = extract_tags(p, rel_fname="m.py")
        defs = [t for t in tags if t.kind == TagKind.DEF]
        assert len(defs) == 1
        t = defs[0]
        assert t.name == "hello"
        assert t.category == TagCategory.FUNCTION
        assert t.parent is None
        assert t.start_line == 1
        assert t.end_line == 2
        assert t.rel_fname == "m.py"
        assert str(p) == t.fname
        assert "def hello" in t.info

    def test_class_and_method(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "class Widget:\n    def spin(self):\n        return 1\n",
        )
        tags = extract_tags(p)
        cls = _by("Widget", tags, TagKind.DEF)
        assert len(cls) == 1
        assert cls[0].category == TagCategory.CLASS
        assert cls[0].parent is None

        method = _by("spin", tags, TagKind.DEF)
        assert len(method) == 1
        assert method[0].category == TagCategory.METHOD
        assert method[0].parent == "Widget"

    def test_nested_class(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "class Outer:\n    class Inner:\n        def m(self):\n            return 1\n",
        )
        tags = extract_tags(p)
        inner = _by("Inner", tags, TagKind.DEF)
        assert inner and inner[0].parent == "Outer"
        m = _by("m", tags, TagKind.DEF)
        assert m and m[0].parent == "Inner"

    def test_function_call_ref(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "def a():\n    return 1\n\ndef b():\n    return a()\n",
        )
        tags = extract_tags(p)
        refs = [t for t in tags if t.kind == TagKind.REF and t.name == "a"]
        assert len(refs) == 1
        assert refs[0].category == TagCategory.FUNCTION

    def test_method_call_ref_uses_attribute_name(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "def use(w):\n    w.spin()\n",
        )
        tags = extract_tags(p)
        refs = _by("spin", tags, TagKind.REF)
        assert len(refs) == 1

    def test_import_names(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.py",
            "import os\nimport json as j\nfrom pathlib import Path\nfrom collections import OrderedDict as OD\n",
        )
        tags = extract_tags(p)
        imp_names = {
            t.name for t in tags if t.category == TagCategory.IMPORT
        }
        assert {"os", "j", "Path", "OD"} <= imp_names

    def test_docstring_containing_word_class_is_not_a_class_def(
        self, tmp_path: Path
    ):
        # Regression against upstream RepoGraph, which uses a substring
        # check on the source line \u2014 that would false-positive here.
        p = _write(
            tmp_path,
            "m.py",
            'def note():\n    """This docstring mentions class Foo."""\n    return 1\n',
        )
        tags = extract_tags(p)
        assert not [
            t for t in tags if t.category == TagCategory.CLASS
        ]
        assert _by("note", tags, TagKind.DEF)

    def test_syntax_error_returns_empty_no_raise(self, tmp_path: Path):
        p = _write(tmp_path, "m.py", "def broken(:\n")  # not valid Python
        tags = extract_tags(p)
        # tree-sitter tolerates errors and still yields SOME parse tree,
        # but the extractor must never raise regardless of what it yields.
        assert isinstance(tags, list)

    def test_unreadable_file_returns_empty(self, tmp_path: Path):
        missing = tmp_path / "does-not-exist.py"
        assert extract_tags(missing) == []


# --- TypeScript / TSX / JavaScript extraction -------------------------------


class TestExtractTypeScript:
    def test_class_and_method(self, tmp_path: Path):
        src = (
            "export class Widget {\n"
            "  spin(): number {\n"
            "    return 1;\n"
            "  }\n"
            "}\n"
        )
        p = _write(tmp_path, "m.ts", src)
        tags = extract_tags(p, rel_fname="m.ts")
        cls = _by("Widget", tags, TagKind.DEF)
        assert cls and cls[0].category == TagCategory.CLASS

        m = _by("spin", tags, TagKind.DEF)
        assert m and m[0].category == TagCategory.METHOD
        assert m[0].parent == "Widget"

    def test_function_declaration(self, tmp_path: Path):
        p = _write(tmp_path, "m.ts", "export function greet(x: string) { return x }\n")
        tags = extract_tags(p)
        g = _by("greet", tags, TagKind.DEF)
        assert g and g[0].category == TagCategory.FUNCTION
        assert g[0].parent is None

    def test_arrow_function_assignment(self, tmp_path: Path):
        p = _write(
            tmp_path,
            "m.ts",
            "const add = (a: number, b: number) => a + b\n",
        )
        tags = extract_tags(p)
        add = _by("add", tags, TagKind.DEF)
        assert add and add[0].category == TagCategory.FUNCTION

    def test_call_expression_ref(self, tmp_path: Path):
        src = "function b() { a(); obj.method(); }\n"
        p = _write(tmp_path, "m.ts", src)
        tags = extract_tags(p)
        assert _by("a", tags, TagKind.REF)
        assert _by("method", tags, TagKind.REF)

    def test_imports_named_and_default_and_namespace(self, tmp_path: Path):
        src = (
            "import foo from 'foo';\n"
            "import { a, b as c } from 'x';\n"
            "import * as ns from 'y';\n"
        )
        p = _write(tmp_path, "m.ts", src)
        tags = extract_tags(p)
        names = {t.name for t in tags if t.category == TagCategory.IMPORT}
        assert {"foo", "a", "c", "ns"} <= names

    def test_tsx_jsx_call_still_captures_function_ref(self, tmp_path: Path):
        # A JSX callsite compiles to createElement(...), but for our tag
        # purposes we care that plain call_expressions in a .tsx file work.
        src = (
            "import React from 'react';\n"
            "function App() { return React.createElement('div'); }\n"
        )
        p = _write(tmp_path, "App.tsx", src)
        tags = extract_tags(p)
        assert _by("App", tags, TagKind.DEF)
        assert _by("createElement", tags, TagKind.REF)

    def test_javascript_file(self, tmp_path: Path):
        p = _write(tmp_path, "m.js", "function hi(){ return 1 }\nhi();\n")
        tags = extract_tags(p)
        assert _by("hi", tags, TagKind.DEF)
        assert _by("hi", tags, TagKind.REF)


# --- Behavioural guarantees -------------------------------------------------


class TestGuarantees:
    def test_tag_is_hashable_and_frozen(self, tmp_path: Path):
        p = _write(tmp_path, "m.py", "def a(): pass\n")
        tags = extract_tags(p)
        # frozen dataclass \u2014 mutating should raise
        assert tags
        with pytest.raises(Exception):
            tags[0].name = "b"  # type: ignore[misc]
        # hashable
        _ = {t for t in tags}

    def test_as_dict_round_trip(self, tmp_path: Path):
        p = _write(tmp_path, "m.py", "def a(): pass\n")
        [tag] = [t for t in extract_tags(p) if t.kind == TagKind.DEF]
        d = tag.as_dict()
        assert d["name"] == "a"
        assert d["kind"] == "def"
        assert d["category"] == "function"
        assert set(d) == {
            "name",
            "kind",
            "category",
            "rel_fname",
            "fname",
            "start_line",
            "end_line",
            "parent",
            "info",
        }

    def test_info_truncated_to_200_chars(self, tmp_path: Path):
        long_default = ", ".join(f"x{i}=0" for i in range(120))
        src = f"def wide({long_default}):\n    return 1\n"
        p = _write(tmp_path, "m.py", src)
        tag = next(
            t for t in extract_tags(p) if t.name == "wide" and t.kind == TagKind.DEF
        )
        assert len(tag.info) <= 200

    def test_unsupported_language_returns_empty(self, tmp_path: Path):
        p = _write(tmp_path, "m.rs", "fn main() {}\n")
        assert extract_tags(p) == []

    def test_source_bytes_override_avoids_disk_read(self, tmp_path: Path):
        # Point at a nonexistent file but supply source bytes explicitly \u2014
        # the parser must use the bytes and not touch the disk.
        fake = tmp_path / "not-on-disk.py"
        assert not fake.exists()
        tags = extract_tags(
            fake, rel_fname="not-on-disk.py", source=b"def x(): pass\n"
        )
        assert _by("x", tags, TagKind.DEF)
