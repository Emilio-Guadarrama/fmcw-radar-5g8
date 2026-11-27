"""Stream health: update rate, lost frames and processing time."""

from collections import deque


class StreamStats:
    def __init__(self, rate_window_s: float = 3.0, history: int = 100):
        self.rate_window_s = rate_window_s
        self.received = 0
        self.dropped = 0
        self._last_seq = None
        self._done_s: deque[float] = deque()
        self._latency_s: deque[float] = deque(maxlen=history)
        self._recent_gaps: deque[tuple[float, int]] = deque()

    def add(self, seq: int, captured_s: float, done_s: float) -> None:
        """Record one processed frame. Times are in seconds on one clock."""
        gap = 0
        if self._last_seq is not None:
            # A sequence number that goes backwards means the source restarted;
            # the number of lost frames is then unknown and not counted.
            gap = max(seq - self._last_seq - 1, 0)
        self._last_seq = seq
        self.received += 1
        self.dropped += gap
        if gap:
            self._recent_gaps.append((done_s, gap))
        self._done_s.append(done_s)
        self._latency_s.append(done_s - captured_s)
        while self._done_s[0] < done_s - self.rate_window_s:
            self._done_s.popleft()
        while self._recent_gaps and self._recent_gaps[0][0] < done_s - 10.0:
            self._recent_gaps.popleft()

    @property
    def update_rate_hz(self) -> float | None:
        if len(self._done_s) < 2:
            return None
        span = self._done_s[-1] - self._done_s[0]
        return (len(self._done_s) - 1) / span if span > 0 else None

    @property
    def dropped_last_10_s(self) -> int:
        return sum(gap for _, gap in self._recent_gaps)

    @property
    def dropped_fraction(self) -> float:
        total = self.received + self.dropped
        return self.dropped / total if total else 0.0

    @property
    def processing_ms(self) -> float | None:
        """Latest time from end of capture to finished processing."""
        return self._latency_s[-1] * 1e3 if self._latency_s else None
