"""Stage 3.2 — confirmation-policy body construction.

Pure-function tests for ``_build_confirmation_policy``.

Wire shape target: openhands-sdk 1.40.0 discriminated union at
``openhands.sdk.security.confirmation_policy``. See DEBUG_LOG
2026-08-05 SDK-probe entry for the verified enum + field names.
"""

from bff.routers.runs import _build_confirmation_policy


class TestBuildConfirmationPolicy:
    def test_default_returns_confirmrisky_medium_confirm_unknown(self) -> None:
        body, label = _build_confirmation_policy(False)

        assert body == {
            "policy": {
                "kind": "ConfirmRisky",
                "threshold": "MEDIUM",
                "confirm_unknown": True,
            }
        }
        assert label == "ConfirmRisky(MEDIUM, confirm_unknown=True)"

    def test_require_approval_true_escalates_to_alwaysconfirm(self) -> None:
        body, label = _build_confirmation_policy(True)

        assert body == {"policy": {"kind": "AlwaysConfirm"}}
        assert label == "AlwaysConfirm"

    def test_policy_body_is_json_serializable(self) -> None:
        # Wire contract: httpx.AsyncClient.post(json=...) requires
        # json-serializable payload. Regression guard against future
        # sneaking a set/tuple/datetime into the policy dict.
        import json

        for require in (False, True):
            body, _ = _build_confirmation_policy(require)
            assert json.loads(json.dumps(body)) == body

    def test_confirmrisky_threshold_is_valid_enum_value(self) -> None:
        # openhands-sdk 1.40.0 accepts LOW | MEDIUM | HIGH for the
        # ConfirmRisky.threshold field. Guard against a typo drift.
        body, _ = _build_confirmation_policy(False)
        assert body["policy"]["threshold"] in {"LOW", "MEDIUM", "HIGH"}

    def test_confirm_unknown_is_boolean(self) -> None:
        body, _ = _build_confirmation_policy(False)
        assert isinstance(body["policy"]["confirm_unknown"], bool)
        assert body["policy"]["confirm_unknown"] is True

    def test_policy_labels_are_non_empty_strings(self) -> None:
        for require in (False, True):
            _, label = _build_confirmation_policy(require)
            assert isinstance(label, str) and label
