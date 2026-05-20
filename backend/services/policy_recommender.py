from __future__ import annotations

try:
    from ..core import GenerationPolicy, SceneState, StructuredUserState, UserMusicProfile, VAState, clamp01
except ImportError:
    from core import GenerationPolicy, SceneState, StructuredUserState, UserMusicProfile, VAState, clamp01


POLICIES = {
    "emotion_matching": {
        "style": "expressive_piano",
        "target": None,
        "tempo": (0.25, 0.82),
        "density": (0.22, 0.72),
        "volatility": (0.16, 0.7),
        "brightness": (0.25, 0.75),
        "melody_salience": 0.62,
        "rhythm_salience": 0.45,
        "repetition": 0.48,
        "instruments": ["piano", "soft_pad"],
        "avoid": [],
    },
    "calm_focus": {
        "style": "soft_piano_lofi",
        "target": VAState(0.55, 0.42),
        "tempo": (0.2, 0.45),
        "density": (0.22, 0.48),
        "volatility": (0.08, 0.34),
        "brightness": (0.38, 0.62),
        "melody_salience": 0.3,
        "rhythm_salience": 0.38,
        "repetition": 0.78,
        "instruments": ["piano", "soft_pad", "light_texture"],
        "avoid": ["strong_drums", "dramatic_chord_change", "too_sleepy"],
    },
    "deep_focus": {
        "style": "minimal_focus_pad",
        "target": VAState(0.52, 0.38),
        "tempo": (0.12, 0.36),
        "density": (0.12, 0.34),
        "volatility": (0.04, 0.22),
        "brightness": (0.34, 0.56),
        "melody_salience": 0.18,
        "rhythm_salience": 0.22,
        "repetition": 0.9,
        "instruments": ["soft_pad", "sparse_piano"],
        "avoid": ["strong_melody", "complex_rhythm", "large_dynamic_change"],
    },
    "sleep_downregulation": {
        "style": "ambient_sleep",
        "target": VAState(0.5, 0.2),
        "tempo": (0.0, 0.18),
        "density": (0.06, 0.24),
        "volatility": (0.02, 0.16),
        "brightness": (0.18, 0.42),
        "melody_salience": 0.12,
        "rhythm_salience": 0.08,
        "repetition": 0.82,
        "instruments": ["soft_pad", "warm_synth", "sparse_piano"],
        "avoid": ["sharp_attack", "strong_bass", "bright_synth"],
    },
    "motivation_boost": {
        "style": "light_game_music",
        "target": VAState(0.68, 0.65),
        "tempo": (0.55, 0.82),
        "density": (0.42, 0.68),
        "volatility": (0.25, 0.6),
        "brightness": (0.52, 0.82),
        "melody_salience": 0.68,
        "rhythm_salience": 0.72,
        "repetition": 0.58,
        "instruments": ["piano", "strings", "soft_synth"],
        "avoid": ["too_sleepy", "too_sad"],
    },
    "creative_flow": {
        "style": "warm_creative_flow",
        "target": VAState(0.62, 0.55),
        "tempo": (0.34, 0.62),
        "density": (0.34, 0.64),
        "volatility": (0.22, 0.58),
        "brightness": (0.42, 0.74),
        "melody_salience": 0.5,
        "rhythm_salience": 0.42,
        "repetition": 0.55,
        "instruments": ["piano", "strings", "soft_synth"],
        "avoid": [],
    },
    "neutral_background": {
        "style": "neutral_background",
        "target": VAState(0.55, 0.45),
        "tempo": (0.24, 0.52),
        "density": (0.24, 0.5),
        "volatility": (0.1, 0.35),
        "brightness": (0.38, 0.64),
        "melody_salience": 0.28,
        "rhythm_salience": 0.35,
        "repetition": 0.74,
        "instruments": ["piano", "soft_pad"],
        "avoid": ["strong_drums"],
    },
}


class PolicyRecommender:
    def recommend(
        self,
        state: StructuredUserState,
        profile: UserMusicProfile,
        scene: SceneState,
    ) -> GenerationPolicy:
        scores = {policy_id: self._score(policy_id, state, profile, scene) for policy_id in POLICIES}
        selected = max(scores, key=scores.get)
        spec = POLICIES[selected]
        target = spec["target"] or state.va
        avoid = sorted(set(spec["avoid"] + state.active_constraints + profile.disliked_instruments))
        return GenerationPolicy(
            policy_id=selected,
            style=spec["style"],
            target_va=target,
            tempo_range=spec["tempo"],
            density_range=spec["density"],
            volatility_range=spec["volatility"],
            brightness_range=spec["brightness"],
            melody_salience=spec["melody_salience"],
            rhythm_salience=spec["rhythm_salience"],
            repetition=spec["repetition"],
            instrumentation=[item for item in spec["instruments"] if item not in profile.disliked_instruments],
            avoid=avoid,
            reason=f"intent={state.intent}, activity={state.activity}, scene={scene.scene_id}",
        )

    def _score(
        self,
        policy_id: str,
        state: StructuredUserState,
        profile: UserMusicProfile,
        scene: SceneState,
    ) -> float:
        intent_match = 0.0
        if policy_id == "calm_focus" and (
            state.intent in {"calm_down", "stay_focused"} or state.secondary_intent == "stay_focused"
        ):
            intent_match = 1.0
        elif policy_id == "deep_focus" and state.activity in {"coding", "studying"} and state.cognitive_load == "high":
            intent_match = 0.9
        elif policy_id == "sleep_downregulation" and (state.intent == "sleep" or state.activity == "sleeping"):
            intent_match = 1.0
        elif policy_id == "motivation_boost" and state.intent == "motivate":
            intent_match = 1.0
        elif policy_id == "creative_flow" and state.intent == "creative_flow":
            intent_match = 1.0
        elif policy_id == "emotion_matching" and state.regulation_mode == "emotion_matching":
            intent_match = 0.75
        elif policy_id == "neutral_background":
            intent_match = 0.45

        activity_match = 0.0
        if state.activity in {"coding", "studying", "interview_preparation"} and policy_id in {"calm_focus", "deep_focus"}:
            activity_match = 1.0
        elif state.activity == "sleeping" and policy_id == "sleep_downregulation":
            activity_match = 1.0
        elif state.activity == "exercising" and policy_id == "motivation_boost":
            activity_match = 0.9
        elif state.activity == "resting" and policy_id in {"neutral_background", "emotion_matching"}:
            activity_match = 0.6

        cognitive_match = 0.8 if state.cognitive_load == "high" and policy_id in {"calm_focus", "deep_focus"} else 0.4
        emotion_match = 1 - abs((POLICIES[policy_id]["target"] or state.va).arousal - state.target_va.arousal)
        preference_match = profile.policy_preferences.get(policy_id, 0.5)
        scene_match = 0.6
        if scene.scene_id == "study_room" and policy_id in {"calm_focus", "deep_focus"}:
            scene_match = 1.0
        elif scene.scene_id == "rainy_night" and policy_id in {"sleep_downregulation", "calm_focus"}:
            scene_match = 0.9
        elif scene.scene_id == "workout" and policy_id == "motivation_boost":
            scene_match = 1.0
        elif scene.scene_id == "creative_room" and policy_id == "creative_flow":
            scene_match = 1.0

        return clamp01(
            0.25 * intent_match
            + 0.2 * activity_match
            + 0.2 * cognitive_match
            + 0.15 * emotion_match
            + 0.15 * preference_match
            + 0.05 * scene_match
        )
