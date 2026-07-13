"""Loop Guard — detects repetitive agent action cycles and suggests escalation."""
from collections import deque
from dataclasses import dataclass
from typing import Deque


@dataclass
class ActionFingerprint:
    operation_class: str   # "edit_file", "run_test", "rewrite_func"
    target: str            # normalized file path or function name
    approach: str          # "syntax", "logic", "structural"


class LoopGuard:
    def __init__(self, window: int = 5, threshold: int = 3) -> None:
        self.history: Deque[str] = deque(maxlen=window)
        self.threshold = threshold

    def fingerprint(self, fp: ActionFingerprint) -> str:
        # Raw colon-joined key — no hash needed. The key space is small and
        # deterministic; hashing adds collision risk with zero benefit here.
        return f"{fp.operation_class}:{fp.target}:{fp.approach}"

    def is_looping(self, fp: ActionFingerprint) -> bool:
        """Return True when the same fingerprint has been seen `threshold` times total.

        Append FIRST, then count — ensures detection triggers on the threshold-th
        occurrence, not the (threshold+1)-th.
        """
        h = self.fingerprint(fp)
        self.history.append(h)          # append first
        count = sum(1 for x in self.history if x == h)  # then count
        return count >= self.threshold

    def suggest_escalation(self, fp: ActionFingerprint) -> str:
        escalation_map = {
            "syntax": "structural",
            "structural": "rewrite",
            "rewrite": "delegate_to_human",
        }
        return escalation_map.get(fp.approach, "delegate_to_human")

    def reset(self) -> None:
        self.history.clear()
