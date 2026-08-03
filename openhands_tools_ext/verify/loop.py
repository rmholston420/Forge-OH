"""Execution-verified self-debugging loop policy.

This module is the policy core of Recommendation #2 (Slice E). It does
*not* talk to the OpenHands SDK directly — the SDK integration lives in
``openhands_tools_ext.verify.hook`` as a CLI shim so it can be wired
in as a standard ``HookType.COMMAND`` STOP hook.

The policy is intentionally pure: given the current workspace, the set
of files the agent has edited since the last successful verify, and the
current retry-iteration count, decide what to do:

  * **Not yet at the retry cap** → run verification via the E.2 module
    and return a :class:`VerifyDecision` telling the caller to
    ``block=True`` (do not let the agent stop) plus the emitted
    ``VerificationStep`` record.
  * **Retry cap reached** → return ``block=False`` (agent may stop).
  * **No runner detected or no target selected** → verification was
    skipped, ``block=False`` (nothing to enforce).
  * **Verification passed** → ``block=False`` (agent may stop; loop's
    job is done).
  * **Verification failed / errored** and retries remain → ``block=True``.

Callers on the agent-server side are responsible for turning a
"``block=True``" decision into two events on the run's stream:

  1. an ``ActionEvent`` with ``tool_name="verify_step"`` and
     ``arguments={"iteration": …, "max_iterations": …}``, and
  2. a matching ``ObservationEvent`` (same ``action_id``) whose
     ``result`` is the :class:`VerificationStep` payload.

The existing BFF trace-reconstruction path (see
``bff/services/trace_reconstruction.py::_KIND_MAP``) picks these up as
``verify`` spans with no further changes required.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from openhands_tools_ext.verify.runner import run_verification
from openhands_tools_ext.verify.schema import VerificationStep, VerifyVerdict

DEFAULT_MAX_ITERATIONS: int = 3


@dataclass
class VerifyDecision:
    """The outcome of one call to :meth:`VerifyLoop.on_stop`."""

    block: bool
    step: VerificationStep | None
    reason: str
    iteration: int
    max_iterations: int

    def to_hook_json(self) -> dict[str, object]:
        """Serialise for the OpenHands SDK STOP hook contract.

        Structured hook output is Claude-Code-shaped: ``decision`` is
        either ``"block"`` (deny stop) or omitted (allow), and
        ``reason`` is a short human-readable string.
        """
        payload: dict[str, object] = {"reason": self.reason}
        if self.block:
            payload["decision"] = "block"
        if self.step is not None:
            payload["additionalContext"] = self.step.model_dump(mode="json")
        return payload


@dataclass
class VerifyLoop:
    """Stateful driver for the execution-verified self-debugging loop.

    One instance corresponds to one agent run. It tracks how many
    verification attempts have already fired and, for each new STOP
    signal from the agent, either enforces one more retry or gives up.

    The caller (typically the agent-server's STOP-hook wiring) is
    expected to:

    1. Update :attr:`edited_files_since_last_verify` whenever a
       ``file_editor`` ObservationEvent arrives.
    2. Call :meth:`on_stop` when the agent attempts to finish.
    3. Emit the ActionEvent/ObservationEvent pair returned in
       ``decision.step`` (if any) into the run's event stream.
    4. Honour ``decision.block`` — if ``True``, the agent must be told
       to continue (via ``exit 2`` from the hook, or SDK equivalent);
       if ``False``, the agent may stop.
    """

    workspace: Path
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    _iterations_used: int = 0
    edited_files_since_last_verify: list[Path] = field(default_factory=list)

    def note_edit(self, path: Path) -> None:
        """Record that a file was edited since the last verification."""
        # Deduplicate but preserve insertion order for reproducible logs.
        resolved = path.resolve() if path.is_absolute() else (self.workspace / path).resolve()
        if resolved not in self.edited_files_since_last_verify:
            self.edited_files_since_last_verify.append(resolved)

    def _reset_edits(self) -> None:
        self.edited_files_since_last_verify = []

    def on_stop(self) -> VerifyDecision:
        """React to an agent STOP.

        Runs one verification attempt and returns whether the agent
        should be blocked from stopping.
        """
        # Cap already reached: the agent has retried enough. Allow stop.
        if self._iterations_used >= self.max_iterations:
            return VerifyDecision(
                block=False,
                step=None,
                reason=(
                    f"verify-loop retry cap reached ({self._iterations_used}/{self.max_iterations})"
                ),
                iteration=self._iterations_used,
                max_iterations=self.max_iterations,
            )

        self._iterations_used += 1
        step = run_verification(
            workspace=self.workspace,
            edited_files=list(self.edited_files_since_last_verify),
            iteration=self._iterations_used,
            max_iterations=self.max_iterations,
        )

        # Compare against enum .value because VerificationStep uses
        # use_enum_values=True — step.verdict is the string form.
        verdict = step.verdict

        # Skipped means no runner or no target — nothing to enforce.
        if verdict == VerifyVerdict.SKIPPED.value:
            return VerifyDecision(
                block=False,
                step=step,
                reason="verify-loop skipped (no runner or no target)",
                iteration=self._iterations_used,
                max_iterations=self.max_iterations,
            )

        # Pass: clear the edit set so a later stop doesn't re-run the
        # same verification with no new changes; allow stop.
        if verdict == VerifyVerdict.PASS.value:
            self._reset_edits()
            return VerifyDecision(
                block=False,
                step=step,
                reason=(
                    f"verify-loop pass on iteration {self._iterations_used}/{self.max_iterations}"
                ),
                iteration=self._iterations_used,
                max_iterations=self.max_iterations,
            )

        # Fail or error, budget remaining: block the stop so the agent
        # retries.
        if self._iterations_used < self.max_iterations:
            return VerifyDecision(
                block=True,
                step=step,
                reason=(
                    f"verify-loop {verdict} on iteration "
                    f"{self._iterations_used}/{self.max_iterations}; "
                    "agent must retry"
                ),
                iteration=self._iterations_used,
                max_iterations=self.max_iterations,
            )

        # Fail or error, budget exhausted: give up and let the agent
        # stop — but surface the last verdict for the trace log.
        return VerifyDecision(
            block=False,
            step=step,
            reason=(
                f"verify-loop {verdict} after "
                f"{self._iterations_used}/{self.max_iterations} attempts; "
                "giving up"
            ),
            iteration=self._iterations_used,
            max_iterations=self.max_iterations,
        )
