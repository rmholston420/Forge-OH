"""Unit tests for openhands_tools_ext.repograph.index."""

from __future__ import annotations

from pathlib import Path

from openhands_tools_ext.repograph.index import (
    RepoIndex,
    build_index,
    iter_source_files,
)


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestIterSourceFiles:
    def test_finds_supported_extensions_only(self, tmp_path: Path):
        _write(tmp_path, "a.py", "def a(): pass\n")
        _write(tmp_path, "b.ts", "export const x = 1;\n")
        _write(tmp_path, "c.jsx", "const y = () => 1;\n")
        _write(tmp_path, "readme.md", "# hi\n")
        _write(tmp_path, "logo.png", "\x89PNG")
        files = iter_source_files(tmp_path)
        rels = sorted(str(p.relative_to(tmp_path)) for p in files)
        assert rels == ["a.py", "b.ts", "c.jsx"]

    def test_fallback_walk_skips_blocklist(self, tmp_path: Path):
        _write(tmp_path, "keep.py", "def a(): pass\n")
        _write(tmp_path, "node_modules/lib/x.js", "1\n")
        _write(tmp_path, ".venv/lib/mod.py", "1\n")
        _write(tmp_path, ".git/hooks/x.py", "1\n")
        files = iter_source_files(tmp_path)
        rels = sorted(str(p.relative_to(tmp_path)) for p in files)
        assert rels == ["keep.py"]


class TestBuildIndex:
    def test_intra_file_call_resolves_to_same_file_def(self, tmp_path: Path):
        _write(
            tmp_path,
            "m.py",
            "def a():\n    return 1\n\ndef b():\n    return a()\n",
        )
        idx = build_index(tmp_path, compute_pagerank=False)
        assert len(idx.files) == 1
        # Two defs: a, b
        names = {s.name for s in idx.symbols.values()}
        assert {"a", "b"} <= names
        # One resolved call: b calls a
        assert len(idx.calls) == 1
        c = idx.calls[0]
        assert c.callee_name == "a"
        assert c.src_rel_path == "m.py"
        assert c.dst_symbol_key[1] == "a"
        assert not idx.unresolved_calls

    def test_cross_file_call_resolves_globally(self, tmp_path: Path):
        _write(tmp_path, "lib.py", "def hello(): return 1\n")
        _write(
            tmp_path,
            "app.py",
            "from lib import hello\n\ndef main():\n    return hello()\n",
        )
        idx = build_index(tmp_path, compute_pagerank=False)
        # hello() called from app.py should resolve to lib.py:hello
        calls_from_app = [c for c in idx.calls if c.src_rel_path == "app.py"]
        assert any(c.callee_name == "hello" and c.dst_symbol_key[0] == "lib.py"
                   for c in calls_from_app)

    def test_unresolved_call_recorded(self, tmp_path: Path):
        _write(tmp_path, "m.py", "def user():\n    return external_thing()\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        assert any(u.callee_name == "external_thing" for u in idx.unresolved_calls)

    def test_method_of_edge(self, tmp_path: Path):
        _write(
            tmp_path,
            "m.py",
            "class Widget:\n    def spin(self):\n        return 1\n",
        )
        idx = build_index(tmp_path, compute_pagerank=False)
        assert len(idx.method_edges) == 1
        e = idx.method_edges[0]
        # method key should point at spin, class key at Widget
        assert e.method_key[1] == "spin"
        assert e.class_key[1] == "Widget"

    def test_pagerank_scores_present(self, tmp_path: Path):
        _write(
            tmp_path,
            "m.py",
            "def hub(): return 1\n\ndef a(): return hub()\n\ndef b(): return hub()\n",
        )
        idx = build_index(tmp_path, compute_pagerank=True)
        hub = next(s for s in idx.symbols.values() if s.name == "hub")
        a = next(s for s in idx.symbols.values() if s.name == "a")
        # `hub` receives edges from both a and b, should out-rank them.
        assert hub.pagerank > 0
        assert hub.pagerank >= a.pagerank

    def test_ts_and_py_in_same_repo(self, tmp_path: Path):
        _write(tmp_path, "mod.ts", "export function greet(){ return 1 }\n")
        _write(tmp_path, "m.py", "def local(): return 1\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        rels = {f.rel_path for f in idx.files}
        assert {"m.py", "mod.ts"} <= rels
        names = {s.name for s in idx.symbols.values()}
        assert {"local", "greet"} <= names

    def test_repo_key_stable(self, tmp_path: Path):
        _write(tmp_path, "a.py", "def a(): pass\n")
        idx1 = build_index(tmp_path, compute_pagerank=False)
        idx2 = build_index(tmp_path, compute_pagerank=False)
        assert idx1.repo_key == idx2.repo_key
        assert len(idx1.repo_key) == 12

    def test_empty_repo(self, tmp_path: Path):
        (tmp_path / "readme.md").write_text("# hi\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        assert idx.stats == {
            "files": 0,
            "symbols": 0,
            "calls": 0,
            "unresolved_calls": 0,
            "method_edges": 0,
        }

    def test_symbol_key_uniqueness(self, tmp_path: Path):
        # Two functions with the same name at different lines must be
        # distinct symbols (Python allows redef; extractor should preserve).
        _write(
            tmp_path,
            "m.py",
            "def a(): return 1\n\ndef a(): return 2\n",
        )
        idx = build_index(tmp_path, compute_pagerank=False)
        a_syms = [s for s in idx.symbols.values() if s.name == "a"]
        assert len(a_syms) == 2
        assert {s.start_line for s in a_syms} == {1, 3}

    def test_ambiguous_cross_file_call_produces_multiple_edges(self, tmp_path: Path):
        _write(tmp_path, "one.py", "def helper(): return 1\n")
        _write(tmp_path, "two.py", "def helper(): return 2\n")
        _write(tmp_path, "app.py", "def use(): return helper()\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        # helper() in app.py should resolve to both one.py and two.py.
        app_calls = [c for c in idx.calls if c.src_rel_path == "app.py"]
        callee_files = {c.dst_symbol_key[0] for c in app_calls}
        assert callee_files == {"one.py", "two.py"}

    def test_repo_index_is_dataclass_and_stats_json_safe(self, tmp_path: Path):
        _write(tmp_path, "m.py", "def a(): return 1\n")
        idx = build_index(tmp_path, compute_pagerank=False)
        assert isinstance(idx, RepoIndex)
        # stats should be a plain dict of ints \u2014 usable in JSON responses.
        import json
        json.dumps(idx.stats)
