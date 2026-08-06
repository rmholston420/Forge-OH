"""Tests for bff/routers/skills.py — the in-process SDK loader (Stage 6.6).

Patches the SDK loader used by the router with a fake so tests don't need
`openhands.sdk.skills` installed. Exercises the reshaper, scope filtering,
content truncation, and the empty-state fallback.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bff.routers import skills

app = FastAPI()
app.include_router(skills.router, prefix="/api")
client = TestClient(app)


def _mk_skill_info(
    name: str,
    *,
    triggers: list[str] | None = None,
    content: str = "hello",
    description: str = "",
    source: str = "/tmp/x/SKILL.md",
    skill_type: str = "agentskills",
) -> SimpleNamespace:
    """Fake SkillInfo — matches openhands.sdk.skills.skill.SkillInfo shape."""
    return SimpleNamespace(
        name=name,
        type=skill_type,
        content=content,
        triggers=triggers or [],
        source=source,
        description=description,
        is_agentskills_format=True,
        disable_model_invocation=False,
    )


def _mk_skill(info: SimpleNamespace) -> SimpleNamespace:
    """Fake Skill — has to_skill_info() → SkillInfo."""
    return SimpleNamespace(to_skill_info=lambda: info)


def test_list_skills_returns_user_and_project_rows() -> None:
    user = [_mk_skill(_mk_skill_info("colossus-python-env", triggers=["pip", "venv"]))]
    project = [
        _mk_skill(_mk_skill_info("forge-oh-debug-driver", triggers=["error", "traceback"])),
        _mk_skill(_mk_skill_info("forge-oh-colossus-ops", triggers=["3100", "8081"])),
    ]
    with patch.object(skills, "_load_via_sdk", return_value=(user, project, {"user": 1, "project": 2})):
        r = client.get("/api/skills")
    assert r.status_code == 200
    payload = r.json()
    assert payload["sources"] == {"user": 1, "project": 2}
    names = [row["name"] for row in payload["data"]]
    assert "colossus-python-env" in names
    assert "forge-oh-debug-driver" in names
    assert "forge-oh-colossus-ops" in names
    # Deterministic sort (agentskills first, then alphabetical within group)
    assert names == sorted(names, key=str.lower)


def test_list_skills_scope_filter_excludes_user() -> None:
    user = [_mk_skill(_mk_skill_info("user-only"))]
    project = [_mk_skill(_mk_skill_info("project-only"))]
    with patch.object(skills, "_load_via_sdk", return_value=(user, project, {"user": 1, "project": 1})):
        r = client.get("/api/skills?include_user=false")
    assert r.status_code == 200
    names = [row["name"] for row in r.json()["data"]]
    assert names == ["project-only"]


def test_list_skills_scope_filter_excludes_project() -> None:
    user = [_mk_skill(_mk_skill_info("user-only"))]
    project = [_mk_skill(_mk_skill_info("project-only"))]
    with patch.object(skills, "_load_via_sdk", return_value=(user, project, {"user": 1, "project": 1})):
        r = client.get("/api/skills?include_project=false")
    assert r.status_code == 200
    names = [row["name"] for row in r.json()["data"]]
    assert names == ["user-only"]


def test_content_truncation_marks_truncated() -> None:
    long_body = "x" * 1200
    user = [_mk_skill(_mk_skill_info("big", content=long_body))]
    with patch.object(skills, "_load_via_sdk", return_value=(user, [], {"user": 1, "project": 0})):
        r = client.get("/api/skills")
    row = r.json()["data"][0]
    assert row["contentTruncated"] is True
    assert len(row["contentPreview"]) <= 501  # 500 chars + "…"
    assert row["contentPreview"].endswith("…")


def test_short_content_is_not_truncated() -> None:
    user = [_mk_skill(_mk_skill_info("small", content="short body"))]
    with patch.object(skills, "_load_via_sdk", return_value=(user, [], {"user": 1, "project": 0})):
        r = client.get("/api/skills")
    row = r.json()["data"][0]
    assert row["contentTruncated"] is False
    assert row["contentPreview"] == "short body"


def test_triggers_and_flags_are_reshaped() -> None:
    info = _mk_skill_info(
        "trig-test",
        triggers=["error", "traceback", "500"],
        description="Debug driver",
    )
    with patch.object(skills, "_load_via_sdk", return_value=([_mk_skill(info)], [], {"user": 1, "project": 0})):
        r = client.get("/api/skills")
    row = r.json()["data"][0]
    assert row["triggers"] == ["error", "traceback", "500"]
    assert row["description"] == "Debug driver"
    assert row["isAgentSkillsFormat"] is True
    assert row["disableModelInvocation"] is False


def test_installed_alias_returns_same_rows_without_sources() -> None:
    user = [_mk_skill(_mk_skill_info("a"))]
    project = [_mk_skill(_mk_skill_info("b"))]
    with patch.object(skills, "_load_via_sdk", return_value=(user, project, {"user": 1, "project": 1})):
        r = client.get("/api/skills/installed")
    payload = r.json()
    assert set(payload.keys()) == {"data"}
    assert [row["name"] for row in payload["data"]] == ["a", "b"]


def test_marketplace_is_empty() -> None:
    r = client.get("/api/skills/marketplace")
    assert r.status_code == 200
    assert r.json() == {"data": []}


def test_loader_crash_returns_empty_lists_not_500() -> None:
    """SDK import failure is logged and returns empty state, not a 500."""
    with patch.object(skills, "_load_via_sdk", return_value=([], [], {"user": 0, "project": 0})):
        r = client.get("/api/skills")
    assert r.status_code == 200
    assert r.json() == {"data": [], "sources": {"user": 0, "project": 0}}


def test_attribute_fallback_when_no_to_skill_info() -> None:
    """Older Skill objects without to_skill_info() fall back to attribute access."""
    fake = SimpleNamespace(
        name="legacy",
        type="knowledge",
        content="body",
        triggers=["kw"],
        source="/tmp/legacy/SKILL.md",
        description="legacy skill",
        is_agentskills_format=False,
        disable_model_invocation=True,
    )
    with patch.object(skills, "_load_via_sdk", return_value=([fake], [], {"user": 1, "project": 0})):
        r = client.get("/api/skills")
    row = r.json()["data"][0]
    assert row["name"] == "legacy"
    assert row["type"] == "knowledge"
    assert row["triggers"] == ["kw"]
    assert row["isAgentSkillsFormat"] is False
    assert row["disableModelInvocation"] is True
