import threading
import time
from collections import defaultdict


class AttemptLimiter:
    """Sliding-window counter of failed attempts, in process memory.

    Limits: one process only. If you run several instances, each keeps its
    own counts (an attacker gets max_attempts per instance). Fine for a single
    tunnel/free-tier instance; move to the database if you scale out."""

    def __init__(self, max_attempts: int, window_seconds: float, clock=time.monotonic):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, key: str) -> list[float]:
        cutoff = self._clock() - self.window
        hits = [t for t in self._hits[key] if t > cutoff]
        if hits:
            self._hits[key] = hits
        else:
            self._hits.pop(key, None)
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key)) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._prune(key)
            self._hits[key].append(self._clock())

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


WINDOW = 15 * 60
by_email = AttemptLimiter(max_attempts=5, window_seconds=WINDOW)    # guessing one account
by_ip = AttemptLimiter(max_attempts=20, window_seconds=WINDOW)      # spraying many accounts


def clear_all() -> None:
    by_email.clear()
    by_ip.clear()
