from __future__ import annotations

import hashlib
import os
from pathlib import Path

try:
    from ..core import (
        AnalysisState,
        EffectFeatureState,
        MusicParameterState,
        MusicalFeatureState,
        VAState,
        clamp01,
        normalize_feature,
    )
    from .predict import predict_va
    from .va_to_music_feature import create_va_to_music_converter
except ImportError:
    from core import (
        AnalysisState,
        EffectFeatureState,
        MusicParameterState,
        MusicalFeatureState,
        VAState,
        clamp01,
        normalize_feature,
    )
    from services.predict import predict_va
    from services.va_to_music_feature import create_va_to_music_converter


BASE_DIR = Path(__file__).resolve().parent.parent
TEXT_TO_VA_MODEL_DIR = Path(
    os.getenv("TEXT_TO_VA_MODEL_DIR", BASE_DIR / "model" / "text_to_va")
).resolve()
VA_TO_MUSIC_MODEL_PATH = Path(
    os.getenv("VA_TO_MUSIC_MODEL_PATH", BASE_DIR / "model" / "va_to_music" / "music_va_gmm_v2.pkl")
).resolve()
MODEL_DEVICE = os.getenv("VA_MODEL_DEVICE") or None
MODEL_MAX_LENGTH = int(os.getenv("VA_MODEL_MAX_LENGTH", "256"))
MODEL_PROMPT_TEMPLATE = os.getenv(
    "VA_PROMPT_TEMPLATE",
    "Analyze the valence and arousal of the following text: {text}",
)
GMM_TEMPERATURE = float(os.getenv("VA_TO_MUSIC_TEMPERATURE", "0.12"))
GMM_DETERMINISTIC = os.getenv("VA_TO_MUSIC_DETERMINISTIC", "true").lower() != "false"


class MoodProcessor:
    """Text -> VA model -> VA-to-music model -> structured analysis state."""

    def __init__(self) -> None:
        self.text_model_dir = str(TEXT_TO_VA_MODEL_DIR)
        self.va_to_music_model_path = str(VA_TO_MUSIC_MODEL_PATH)
        self.device = MODEL_DEVICE
        self.max_length = MODEL_MAX_LENGTH
        self.prompt_template = MODEL_PROMPT_TEMPLATE
        self.temperature = GMM_TEMPERATURE
        self.deterministic_component = GMM_DETERMINISTIC
        self.converter = create_va_to_music_converter(self.va_to_music_model_path)

    def _fallback(self, mood: str) -> AnalysisState:
        text = (mood or "").strip().lower() or "neutral"
        seeds = []
        for name in ("valence", "arousal"):
            digest = hashlib.sha256(f"{name}:{text}".encode("utf-8")).digest()
            integer = int.from_bytes(digest[:8], "big")
            seeds.append(round(integer / ((1 << 64) - 1), 4))

        va = VAState(valence=seeds[0], arousal=seeds[1]).clamp()
        music = self._default_music_parameters(va)
        return AnalysisState(va=va, music=music)

    def _default_music_parameters(self, va: VAState) -> MusicParameterState:
        return MusicParameterState(
            musical=MusicalFeatureState(
                tempo=clamp01(va.arousal),
                density=clamp01(va.arousal * 0.7 + (1 - abs(va.valence - 0.5) * 2) * 0.2 + 0.1),
                mean_pitch=clamp01(va.valence * 0.55 + va.arousal * 0.2 + 0.15),
                volatility=clamp01(va.arousal * 0.6 + (1 - va.valence) * 0.25 + 0.05),
                pitch_range=0.5,
            ),
            effect=EffectFeatureState(
                brightness=clamp01(va.valence * 0.55 + va.arousal * 0.45),
                wetness=clamp01(0.55 - va.arousal * 0.2 + (1 - va.valence) * 0.15),
            ),
        ).clamp()

    def _music_parameters_from_model(self, va: VAState, mood: str) -> MusicParameterState:
        digest = hashlib.sha256((mood or "neutral").encode("utf-8")).digest()
        seed = int.from_bytes(digest[:4], "big")
        gmm_valence = 1.0 + va.valence * 8.0
        gmm_arousal = 1.0 + va.arousal * 8.0
        raw = self.converter(
            valence_mean=gmm_valence,
            arousal_mean=gmm_arousal,
            seed=seed,
            temperature=self.temperature,
            deterministic_component=self.deterministic_component,
        )
        return MusicParameterState(
            musical=MusicalFeatureState(
                tempo=1.0,
                density=normalize_feature(raw.get("density"), minimum=0, maximum=9, fallback=0.5),
                mean_pitch=normalize_feature(raw.get("mean_pitch"), minimum=0, maximum=5800.0, fallback=0.5),
                volatility=normalize_feature(raw.get("volatility"), minimum=1.1, maximum=4.1, fallback=0.5),
                pitch_range=0.5,
            ),
            effect=EffectFeatureState(
                brightness=normalize_feature(raw.get("brightness"), minimum=0, maximum=13000.0, fallback=0.5),
                wetness=normalize_feature(raw.get("wetness"), minimum=0.0, maximum=0.15, fallback=0.5),
            ),
        ).clamp()

    def process(self, mood: str) -> tuple[AnalysisState, str]:
        text = (mood or "").strip() or "neutral"
        raw_va = predict_va(
            text=text,
            model_dir=self.text_model_dir,
            max_length=self.max_length,
            prompt_template=self.prompt_template,
            device=self.device,
            clamp_output=True,
        )
        va = VAState(
            valence=raw_va["valence"],
            arousal=raw_va["arousal"],
        ).clamp()
        music = self._music_parameters_from_model(va, text)
        return AnalysisState(va=va, music=music), "local_va_models"

    def analysis_from_va(self, va: VAState, mood: str) -> AnalysisState:
        try:
            music = self._music_parameters_from_model(va.clamp(), mood)
        except Exception:
            music = self._default_music_parameters(va.clamp())
        return AnalysisState(va=va.clamp(), music=music)

    def process_safe(self, mood: str) -> tuple[AnalysisState, str]:
        try:
            return self.process(mood)
        except Exception:
            return self._fallback(mood), "fallback:model_error"


DEFAULT_ANALYSIS = AnalysisState(
    va=VAState(
        valence=0.38,
        arousal=0.42,
    ),
    music=MusicParameterState(
        musical=MusicalFeatureState(
            tempo=0.42,
            density=0.28,
            mean_pitch=0.35,
            volatility=0.24,
            pitch_range=0.4,
        ),
        effect=EffectFeatureState(
            brightness=0.34,
            wetness=0.56,
        ),
    ),
)
