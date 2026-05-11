from __future__ import annotations

try:
    from ..core import AnalysisState, HarmonyState, MusicParameterState, VAState
except ImportError:
    from core import AnalysisState, HarmonyState, MusicParameterState, VAState


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

    def encode_all(
        self,
        analysis: AnalysisState,
        harmony: HarmonyState | None = None,
        chord_symbol: str | None = None,
    ) -> list[str]:
        tokens = self.encode_va(analysis.va)
        tokens.extend(self.encode_music_features(analysis.music))
        if harmony:
            tokens.extend(self.encode_harmony(harmony, chord_symbol))
        return tokens
