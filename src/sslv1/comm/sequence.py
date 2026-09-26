"""Bounded modular sequence tracking shared by both bus receivers."""
from dataclasses import dataclass
from typing import Dict, Optional
from ..errors import ValidationError

#: Sequence numbers occupy a 16-bit modular space (the window is smaller).
_SEQUENCE_MODULUS = 0x10000

#: A frame whose sequence number is more than this far behind the newest one
#: seen from the same source is treated as a replay of an already-processed
#: frame rather than as new information (``PR-COMM-005``).
_DEFAULT_SEQUENCE_WINDOW = 32


@dataclass
class SequenceTracker:
    """Per-source incoming sequence-number tracking (``PR-COMM-005``).

    The receiver must be able to tell a genuinely new frame from a duplicate
    delivery or a replay of an old one. Sequence numbers are 16-bit and wrap,
    so "newest" is tracked explicitly and distance is measured modulo the
    sequence space rather than by a plain integer comparison.
    """

    window: int = _DEFAULT_SEQUENCE_WINDOW

    def __post_init__(self) -> None:
        if type(self.window) is not int or not 0 < self.window < _SEQUENCE_MODULUS // 2:
            raise ValidationError("sequence window must be inside the modular half-space")
        self._seen: Dict[int, int] = {}
        self._newest: Optional[int] = None

    @property
    def newest(self) -> Optional[int]:
        return self._newest

    #: Half of the sequence space. A distance of at least this much means the
    #: frame is *behind* the newest marker rather than ahead of it.
    _HALF_SPACE = _SEQUENCE_MODULUS // 2

    def classify(self, sequence: int) -> str:
        """Classify an incoming sequence number.

        Returns ``"new"`` for a frame to process, ``"duplicate"`` for a
        repeat of an already-processed number, and ``"stale"`` for a number
        that lags outside the tracking window (a replay of old traffic).

        Sequence numbers are 16-bit and wrap, so "ahead" and "behind" are
        decided by the modular distance rather than by an integer
        comparison: a distance below half the sequence space means ahead.
        """
        if not 0 <= sequence < _SEQUENCE_MODULUS:
            return "invalid"
        if self._newest is None:
            return "new"
        if sequence in self._seen:
            return "duplicate"
        ahead = (sequence - self._newest) % _SEQUENCE_MODULUS
        if ahead == 0:
            return "duplicate"
        if ahead < self._HALF_SPACE:
            return "new"
        # Behind the newest marker. A small lag is a retransmission of a
        # recent frame; a large lag is a replay of traffic outside the window.
        behind = _SEQUENCE_MODULUS - ahead
        return "duplicate" if behind <= self.window else "stale"

    def record(self, sequence: int) -> None:
        """Record ``sequence`` as processed and advance the newest marker."""
        self._seen[sequence] = self._seen.get(sequence, 0) + 1
        if self._newest is None:
            self._newest = sequence
            return
        # Only advance when the frame is genuinely ahead, so a stale or
        # duplicate frame can never drag the newest marker backwards.
        ahead = (sequence - self._newest) % _SEQUENCE_MODULUS
        if 0 < ahead < self._HALF_SPACE:
            self._newest = sequence
        self._seen = {s: n for s, n in self._seen.items()
                      if (self._newest - s) % _SEQUENCE_MODULUS <= self.window}

    def counts(self) -> Dict[int, int]:
        return dict(self._seen)
