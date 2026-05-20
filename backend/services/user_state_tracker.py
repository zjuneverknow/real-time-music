from __future__ import annotations

try:
    from ..core import RawUserState, StructuredUserState, VAState, VATrackerState
except ImportError:
    from core import RawUserState, StructuredUserState, VAState, VATrackerState


TARGETS = {
    "calm_focused": VAState(0.55, 0.42),
    "sleepy_calm": VAState(0.5, 0.2),
    "motivated": VAState(0.68, 0.65),
    "creative": VAState(0.62, 0.55),
    "same_as_current": None,
}


class UserStateTracker:
    def __init__(self) -> None:
        self.previous: StructuredUserState | None = None

    def update(self, raw: RawUserState, tracker_state: VATrackerState) -> StructuredUserState:
        smoothed_va = tracker_state.as_va()
        target_va = TARGETS.get(raw.target_state)
        if target_va is None:
            target_va = smoothed_va

        intent = raw.primary_intent
        activity = raw.activity
        if self.previous:
            if raw.confidence < 0.55:
                intent = self.previous.intent
            if raw.activity == "resting" and self.previous.activity in {"coding", "studying", "interview_preparation"}:
                activity = self.previous.activity

        constraints = sorted(set(raw.soft_constraints + raw.hard_constraints))
        state = StructuredUserState(
            va=smoothed_va,
            raw_va=VAState(tracker_state.raw_valence, tracker_state.raw_arousal).clamp(),
            dominant_emotion=raw.dominant_emotion,
            intent=intent,
            secondary_intent=raw.secondary_intent,
            activity=activity,
            cognitive_load=raw.cognitive_load,
            attention_need=raw.attention_need,
            distraction_tolerance=raw.distraction_tolerance,
            music_role=raw.music_role,
            desired_effect=raw.desired_effect,
            active_constraints=constraints,
            target_va=target_va,
            regulation_mode=raw.regulation_mode,
        )
        self.previous = state
        return state
