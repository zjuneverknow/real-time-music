from __future__ import annotations

try:
    from ..core import VAState, VATrackerState, clamp01
except ImportError:
    from core import VAState, VATrackerState, clamp01


class VAStateTracker:
    """Smooths utterance-level VA into a continuous dialogue state."""

    def __init__(
        self,
        initial: VAState,
        base_alpha: float = 0.55,
        max_delta: float = 0.16,
    ) -> None:
        self.current_va = initial.clamp()
        self.base_alpha = clamp01(base_alpha)
        self.max_delta = max(0.01, min(0.5, max_delta))
        self.last_state = VATrackerState(
            valence=self.current_va.valence,
            arousal=self.current_va.arousal,
            raw_valence=self.current_va.valence,
            raw_arousal=self.current_va.arousal,
            confidence=1.0,
            smoothing_alpha=self.base_alpha,
        )

    def current(self) -> VATrackerState:
        return self.last_state

    def update(self, raw_va: VAState, confidence: float = 1.0) -> VATrackerState:
        raw = raw_va.clamp()
        confidence = max(0.2, min(1.0, confidence))
        alpha = self.base_alpha * confidence

        next_valence = self._smooth_axis(self.current_va.valence, raw.valence, alpha)
        next_arousal = self._smooth_axis(self.current_va.arousal, raw.arousal, alpha)
        self.current_va = VAState(next_valence, next_arousal).clamp()
        self.last_state = VATrackerState(
            valence=self.current_va.valence,
            arousal=self.current_va.arousal,
            raw_valence=raw.valence,
            raw_arousal=raw.arousal,
            confidence=confidence,
            smoothing_alpha=round(alpha, 4),
        )
        return self.last_state

    def _smooth_axis(self, previous: float, raw: float, alpha: float) -> float:
        target = alpha * raw + (1 - alpha) * previous
        delta = max(-self.max_delta, min(self.max_delta, target - previous))
        return clamp01(previous + delta)


def confidence_from_text(text: str) -> float:
    cleaned = (text or "").strip()
    if not cleaned:
        return 0.35
    # Short utterances are often ambiguous, so they should bend the music less.
    length_score = min(1.0, max(0.35, len(cleaned) / 80))
    punctuation_bonus = 0.08 if any(char in cleaned for char in "!?。！？") else 0.0
    return clamp01(length_score + punctuation_bonus)
