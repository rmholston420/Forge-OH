"""Loop Guard — detects repetitive agent action cycles and suggests escalation."""
import hashlib
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
        key = f"{fp.operation_class}:{fp.target}:{fp.approach}"
        return hashlib.md5(key.encode()).hexdigest()  # noqa: S324

    def is_looping(self, fp: ActionFingerprint) -> bool:
        """Return True when the same fingerprint has been seen `threshold` times total.

        Fix: append FIRST, then count. The previous implementation counted before
        appending, meaning it triggered on the (threshold+1)th occurrence instead
        of the threshold-th.
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
