from __future__ import annotations

try:
    from ..core import (
        AnalysisState,
        FinalMusicControlState,
        GenerationPolicy,
        SceneState,
        StructuredUserState,
        UserMusicProfile,
        clamp01,
    )
except ImportError:
    from core import (
        AnalysisState,
        FinalMusicControlState,
        GenerationPolicy,
        SceneState,
        StructuredUserState,
        UserMusicProfile,
        clamp01,
    )


def _midpoint(bounds: tuple[float, float]) -> float:
    return (bounds[0] + bounds[1]) / 2


def _clamp_range(value: float, bounds: tuple[float, float]) -> float:
    return max(bounds[0], min(bounds[1], value))


class MultimodalControlFusion:
    def fuse(
        self,
        base_analysis: AnalysisState,
        user_state: StructuredUserState,
        profile: UserMusicProfile,
        scene: SceneState,
        policy: GenerationPolicy,
    ) -> FinalMusicControlState:
        musical = base_analysis.music.musical
        effect = base_analysis.music.effect
        bias = scene.control_bias

        tempo = (
            0.2 * musical.tempo
            + 0.25 * _midpoint(policy.tempo_range)
            + 0.2 * profile.preferred_tempo
            + 0.2 * user_state.target_va.arousal
            + 0.15 * self._cognitive_tempo(user_state.cognitive_load)
            + bias.get("tempo", 0.0)
        )
        density = (
            0.15 * musical.density
            + 0.25 * _midpoint(policy.density_range)
            + 0.2 * profile.preferred_density
            + 0.25 * self._density_from_cognitive(user_state)
            + 0.15 * self._density_from_role(user_state.music_role)
            + bias.get("density", 0.0)
        )
        brightness = (
            0.25 * effect.brightness
            + 0.25 * _midpoint(policy.brightness_range)
            + 0.2 * profile.preferred_brightness
            + 0.2 * user_state.target_va.valence
            + 0.1 * scene.scene_valence
            + bias.get("brightness", 0.0)
        )
        volatility = (
            0.2 * musical.volatility
            + 0.3 * _midpoint(policy.volatility_range)
            + 0.2 * profile.preferred_volatility
            + 0.2 * self._volatility_from_cognitive(user_state)
            + 0.1 * user_state.target_va.arousal
            + bias.get("volatility", 0.0)
        )
        mean_pitch = (
            0.35 * musical.mean_pitch
            + 0.3 * profile.preferred_mean_pitch
            + 0.25 * user_state.target_va.valence
            + 0.1 * brightness
        )
        wetness = 0.55 * effect.wetness + 0.35 * profile.preferred_wetness + bias.get("wetness", 0.0)
        melody_salience = (
            0.35 * policy.melody_salience
            + 0.25 * self._salience_from_role(user_state.music_role)
            + 0.2 * profile.melody_salience
            + 0.2 * self._salience_from_attention(user_state.attention_need)
            + bias.get("melody_salience", 0.0)
        )
        rhythm_salience = (
            0.35 * policy.rhythm_salience
            + 0.25 * self._rhythm_from_activity(user_state.activity)
            + 0.2 * profile.rhythm_salience
            + 0.2 * user_state.target_va.arousal
            + bias.get("rhythm_salience", 0.0)
        )
        repetition = 0.45 * policy.repetition + 0.35 * profile.repetition + 0.2 * self._repetition_from_state(user_state)
        repetition += bias.get("repetition", 0.0)

        return FinalMusicControlState(
            target_va=policy.target_va,
            policy=policy.policy_id,
            style=policy.style,
            tempo=clamp01(_clamp_range(tempo, policy.tempo_range)),
            density=clamp01(_clamp_range(density, policy.density_range)),
            brightness=clamp01(_clamp_range(brightness, policy.brightness_range)),
            volatility=clamp01(_clamp_range(volatility, policy.volatility_range)),
            mean_pitch=clamp01(mean_pitch),
            wetness=clamp01(wetness),
            mode="major" if policy.target_va.valence >= 0.5 else "minor",
            chord_progression_type="warm_loop" if policy.target_va.valence >= 0.5 else "reflective_loop",
            instrumentation=policy.instrumentation or profile.preferred_instruments,
            melody_salience=clamp01(melody_salience),
            rhythm_salience=clamp01(rhythm_salience),
            repetition=clamp01(repetition),
            transition_curve=self._transition_curve(policy.policy_id),
        )

    @staticmethod
    def _cognitive_tempo(load: str) -> float:
        return {"high": 0.32, "medium": 0.45, "low": 0.35}.get(load, 0.42)

    @staticmethod
    def _density_from_cognitive(state: StructuredUserState) -> float:
        if state.distraction_tolerance in {"low", "very_low"}:
            return 0.22
        return {"high": 0.28, "medium": 0.45, "low": 0.34}.get(state.cognitive_load, 0.38)

    @staticmethod
    def _density_from_role(role: str) -> float:
        return {
            "focus_assistance": 0.28,
            "emotional_regulation": 0.3,
            "background_support": 0.38,
        }.get(role, 0.36)

    @staticmethod
    def _volatility_from_cognitive(state: StructuredUserState) -> float:
        if state.distraction_tolerance in {"low", "very_low"}:
            return 0.12
        return 0.32

    @staticmethod
    def _salience_from_role(role: str) -> float:
        return {
            "focus_assistance": 0.22,
            "emotional_regulation": 0.32,
            "background_support": 0.28,
        }.get(role, 0.35)

    @staticmethod
    def _salience_from_attention(attention_need: str) -> float:
        return {"high": 0.16, "medium": 0.35, "low": 0.5}.get(attention_need, 0.35)

    @staticmethod
    def _rhythm_from_activity(activity: str) -> float:
        return {
            "coding": 0.26,
            "studying": 0.28,
            "interview_preparation": 0.34,
            "sleeping": 0.08,
            "exercising": 0.82,
        }.get(activity, 0.36)

    @staticmethod
    def _repetition_from_state(state: StructuredUserState) -> float:
        return 0.86 if state.cognitive_load == "high" else 0.65

    @staticmethod
    def _transition_curve(policy_id: str) -> dict[str, str]:
        if policy_id in {"calm_focus", "sleep_downregulation"}:
            return {"tempo": "slow_decrease", "density": "slow_decrease", "volatility": "decrease"}
        if policy_id == "motivation_boost":
            return {"tempo": "slight_increase", "density": "slight_increase", "brightness": "increase"}
        return {"tempo": "stable", "density": "stable", "brightness": "stable"}
