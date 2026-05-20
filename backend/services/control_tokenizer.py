from __future__ import annotations

try:
    from ..core import (
        AnalysisState,
        FinalMusicControlState,
        GenerationPolicy,
        HarmonyState,
        MusicParameterState,
        SceneState,
        StructuredUserState,
        UserMusicProfile,
        VAState,
    )
except ImportError:
    from core import (
        AnalysisState,
        FinalMusicControlState,
        GenerationPolicy,
        HarmonyState,
        MusicParameterState,
        SceneState,
        StructuredUserState,
        UserMusicProfile,
        VAState,
    )


def _bucket(value: float, low: str, mid: str, high: str) -> str:
    if value < 0.34:
        return low
    if value < 0.67:
        return mid
    return high


class ControlTokenizer:
    """Turns continuous VA and GMM features into Transformer-ready condition tokens."""

    def encode_va(self, va: VAState) -> list[str]:
        return [
            _bucket(va.valence, "<VALENCE_LOW>", "<VALENCE_MID>", "<VALENCE_HIGH>"),
            _bucket(va.arousal, "<AROUSAL_LOW>", "<AROUSAL_MID>", "<AROUSAL_HIGH>"),
        ]

    def encode_music_features(self, music: MusicParameterState) -> list[str]:
        musical = music.musical
        effect = music.effect
        return [
            _bucket(musical.density, "<DENSITY_LOW>", "<DENSITY_MID>", "<DENSITY_HIGH>"),
            _bucket(musical.mean_pitch, "<MEAN_PITCH_LOW>", "<MEAN_PITCH_MID>", "<MEAN_PITCH_HIGH>"),
            _bucket(musical.volatility, "<VOLATILITY_LOW>", "<VOLATILITY_MID>", "<VOLATILITY_HIGH>"),
            _bucket(effect.brightness, "<BRIGHTNESS_DARK>", "<BRIGHTNESS_NEUTRAL>", "<BRIGHTNESS_BRIGHT>"),
            _bucket(effect.wetness, "<WETNESS_DRY>", "<WETNESS_MED>", "<WETNESS_WET>"),
            _bucket(musical.tempo, "<TEMPO_SLOW>", "<TEMPO_MID>", "<TEMPO_FAST>"),
        ]

    def encode_harmony(self, harmony: HarmonyState, chord_symbol: str | None = None) -> list[str]:
        tokens = [f"<MODE_{harmony.mode.upper()}>"]
        if chord_symbol:
            tokens.append(f"<CHORD_{chord_symbol}>")
        return tokens

    def encode_user_state(self, state: StructuredUserState | None) -> list[str]:
        if state is None:
            return []
        tokens = [
            f"<INTENT_{state.intent.upper()}>",
            f"<ACTIVITY_{state.activity.upper()}>",
            f"<ROLE_{state.music_role.upper()}>",
            f"<COGNITIVE_{state.cognitive_load.upper()}>",
            _bucket(state.target_va.valence, "<TARGET_VALENCE_LOW>", "<TARGET_VALENCE_MID>", "<TARGET_VALENCE_HIGH>"),
            _bucket(state.target_va.arousal, "<TARGET_AROUSAL_LOW>", "<TARGET_AROUSAL_MID>", "<TARGET_AROUSAL_HIGH>"),
        ]
        tokens.extend(f"<{constraint.upper()}>" for constraint in state.active_constraints[:4])
        return tokens

    def encode_policy(self, policy: GenerationPolicy | None) -> list[str]:
        if policy is None:
            return []
        tokens = [
            f"<POLICY_{policy.policy_id.upper()}>",
            f"<STYLE_{policy.style.upper()}>",
        ]
        tokens.extend(f"<INSTR_{instrument.upper()}>" for instrument in policy.instrumentation[:3])
        tokens.extend(f"<AVOID_{item.upper()}>" for item in policy.avoid[:3])
        return tokens

    def encode_profile(self, profile: UserMusicProfile | None) -> list[str]:
        if profile is None:
            return []
        tokens: list[str] = []
        tokens.extend(f"<PREF_{instrument.upper()}>" for instrument in profile.preferred_instruments[:3])
        tokens.extend(f"<DISLIKE_{instrument.upper()}>" for instrument in profile.disliked_instruments[:2])
        tokens.append(_bucket(profile.preferred_density, "<PREF_DENSITY_LOW>", "<PREF_DENSITY_MID>", "<PREF_DENSITY_HIGH>"))
        tokens.append(_bucket(profile.repetition, "<PREF_REPETITION_LOW>", "<PREF_REPETITION_MID>", "<PREF_REPETITION_HIGH>"))
        return tokens

    def encode_scene(self, scene: SceneState | None) -> list[str]:
        if scene is None:
            return []
        return scene.scene_tokens or [f"<SCENE_{scene.scene_id.upper()}>"]

    def encode_final_control(self, control: FinalMusicControlState | None) -> list[str]:
        if control is None:
            return []
        return [
            _bucket(control.melody_salience, "<MELODY_SALIENCE_LOW>", "<MELODY_SALIENCE_MID>", "<MELODY_SALIENCE_HIGH>"),
            _bucket(control.rhythm_salience, "<RHYTHM_SALIENCE_LOW>", "<RHYTHM_SALIENCE_MID>", "<RHYTHM_SALIENCE_HIGH>"),
            _bucket(control.repetition, "<REPETITION_LOW>", "<REPETITION_MID>", "<REPETITION_HIGH>"),
            f"<CONTROL_MODE_{control.mode.upper()}>",
        ]

    def encode_all(
        self,
        analysis: AnalysisState,
        harmony: HarmonyState | None = None,
        chord_symbol: str | None = None,
        user_state: StructuredUserState | None = None,
        profile: UserMusicProfile | None = None,
        scene: SceneState | None = None,
        policy: GenerationPolicy | None = None,
        final_control: FinalMusicControlState | None = None,
    ) -> list[str]:
        tokens = self.encode_va(analysis.va)
        tokens.extend(self.encode_user_state(user_state))
        tokens.extend(self.encode_policy(policy))
        tokens.extend(self.encode_profile(profile))
        tokens.extend(self.encode_scene(scene))
        tokens.extend(self.encode_music_features(analysis.music))
        tokens.extend(self.encode_final_control(final_control))
        if harmony:
            tokens.extend(self.encode_harmony(harmony, chord_symbol))
        return tokens
