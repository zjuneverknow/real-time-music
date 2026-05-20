from __future__ import annotations

try:
    from ..core import FinalMusicControlState, RawUserState, UserMusicProfile, clamp01
except ImportError:
    from core import FinalMusicControlState, RawUserState, UserMusicProfile, clamp01


class ProfileManager:
    def __init__(self, profile: UserMusicProfile | None = None) -> None:
        self.profile = profile or UserMusicProfile()

    def current(self) -> UserMusicProfile:
        return self.profile

    def absorb_dialogue_preferences(self, raw_state: RawUserState) -> UserMusicProfile:
        for element in raw_state.liked_elements:
            if element in {"ambient", "lofi"} and element not in self.profile.liked_styles:
                self.profile.liked_styles.append(element)
            if element in {"piano", "soft_pad"} and element not in self.profile.preferred_instruments:
                self.profile.preferred_instruments.append(element)
        for element in raw_state.disliked_elements:
            if "drum" in element and element not in self.profile.disliked_instruments:
                self.profile.disliked_instruments.append(element)
            elif element not in self.profile.disliked_styles:
                self.profile.disliked_styles.append(element)
        return self.profile

    def apply_feedback(
        self,
        feedback_type: str,
        final_control: FinalMusicControlState | None,
        liked: bool | None = None,
    ) -> UserMusicProfile:
        if final_control is None:
            return self.profile

        positive = liked is True or feedback_type in {"like", "more_like_this"}
        negative = liked is False or feedback_type in {"dislike", "skip", "regenerate"}
        beta = 0.08 if positive else 0.04

        if positive:
            self.profile.preferred_tempo = self._toward(self.profile.preferred_tempo, final_control.tempo, beta)
            self.profile.preferred_density = self._toward(self.profile.preferred_density, final_control.density, beta)
            self.profile.preferred_brightness = self._toward(self.profile.preferred_brightness, final_control.brightness, beta)
            self.profile.preferred_volatility = self._toward(self.profile.preferred_volatility, final_control.volatility, beta)
            self.profile.preferred_wetness = self._toward(self.profile.preferred_wetness, final_control.wetness, beta)
            self.profile.policy_preferences[final_control.policy] = clamp01(
                self.profile.policy_preferences.get(final_control.policy, 0.5) + 0.05
            )
        elif negative:
            self.profile.policy_preferences[final_control.policy] = clamp01(
                self.profile.policy_preferences.get(final_control.policy, 0.5) - 0.06
            )

        if feedback_type in {"less_drums", "less_rhythm"}:
            self.profile.rhythm_salience = clamp01(self.profile.rhythm_salience - 0.08)
            if "heavy_drums" not in self.profile.disliked_instruments:
                self.profile.disliked_instruments.append("heavy_drums")
        elif feedback_type == "more_piano":
            if "piano" not in self.profile.preferred_instruments:
                self.profile.preferred_instruments.append("piano")
        elif feedback_type == "more_calm":
            self.profile.preferred_density = clamp01(self.profile.preferred_density - 0.06)
            self.profile.preferred_volatility = clamp01(self.profile.preferred_volatility - 0.06)
            self.profile.preferred_tempo = clamp01(self.profile.preferred_tempo - 0.04)

        self.profile.feedback_count += 1
        return self.profile

    @staticmethod
    def _toward(current: float, target: float, beta: float) -> float:
        return clamp01(beta * target + (1 - beta) * current)
