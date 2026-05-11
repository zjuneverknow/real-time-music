from __future__ import annotations

from dataclasses import asdict, dataclass, field


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def normalize_feature(
    value: float,
    minimum: float,
    maximum: float,
    fallback: float = 0.5,
) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback

    span = maximum - minimum
    if span <= 0:
        return fallback
    return clamp01((numeric - minimum) / span)


@dataclass
class VAState:
    valence: float
    arousal: float

    def clamp(self) -> "VAState":
        return VAState(
            valence=clamp01(self.valence),
            arousal=clamp01(self.arousal),
        )


@dataclass
class VATrackerState:
    valence: float
    arousal: float
    raw_valence: float
    raw_arousal: float
    confidence: float
    smoothing_alpha: float

    def as_va(self) -> VAState:
        return VAState(valence=self.valence, arousal=self.arousal).clamp()


@dataclass
class MusicalFeatureState:
    tempo: float
    density: float
    mean_pitch: float
    volatility: float
    pitch_range: float = 0.5

    def clamp(self) -> "MusicalFeatureState":
        return MusicalFeatureState(
            tempo=clamp01(self.tempo),
            density=clamp01(self.density),
            mean_pitch=clamp01(self.mean_pitch),
            volatility=clamp01(self.volatility),
            pitch_range=clamp01(self.pitch_range),
        )


@dataclass
class EffectFeatureState:
    brightness: float
    wetness: float

    def clamp(self) -> "EffectFeatureState":
        return EffectFeatureState(
            brightness=clamp01(self.brightness),
            wetness=clamp01(self.wetness),
        )


@dataclass
class MusicParameterState:
    musical: MusicalFeatureState
    effect: EffectFeatureState

    def clamp(self) -> "MusicParameterState":
        return MusicParameterState(
            musical=self.musical.clamp(),
            effect=self.effect.clamp(),
        )

    def flat_dict(self) -> dict[str, float]:
        return {
            **asdict(self.musical),
            **asdict(self.effect),
        }


@dataclass
class AnalysisState:
    va: VAState
    music: MusicParameterState

    def emotion_dict(self) -> dict[str, float]:
        return {
            "valence": self.va.valence,
            "arousal": self.va.arousal,
            "brightness": self.music.effect.brightness,
            "density": self.music.musical.density,
            "volatility": self.music.musical.volatility,
            "mean_pitch": self.music.musical.mean_pitch,
        }


@dataclass
class MelodyControl:
    density: float
    volatility: float
    mean_pitch: float
    pitch_range: float = 0.5
    wetness: float = 0.5

    def clamp(self) -> "MelodyControl":
        return MelodyControl(
            density=clamp01(self.density),
            volatility=clamp01(self.volatility),
            mean_pitch=clamp01(self.mean_pitch),
            pitch_range=clamp01(self.pitch_range),
            wetness=clamp01(self.wetness),
        )


@dataclass
class HarmonyState:
    key: str
    mode: str
    bpm: int
    progression: list[str]
    scale: str


@dataclass
class MelodyNote:
    midi: int
    start_beats: float
    duration_beats: float
    velocity: float


@dataclass
class SkeletonNote:
    midi: int
    start_beats: float
    duration_beats: float
    role: str = "skeleton"


@dataclass
class MusicEvent:
    bar: int
    beat: float
    type: str
    pitch: int | None = None
    duration: float | None = None
    velocity: float | None = None
    chord: str | None = None
    instrument: str | None = None
    role: str | None = None
    effect: dict[str, float] | None = None


@dataclass
class SessionState:
    analysis: AnalysisState
    control: MelodyControl
    harmony: HarmonyState
    previous_note: int = 60
    previous_skeleton: list[SkeletonNote] = field(default_factory=list)
    control_tokens: list[str] = field(default_factory=list)
    va_tracker: VATrackerState | None = None
    bar_index: int = 0
    phrase_length: int = 4
    harmony_dirty: bool = False
    last_source: str = "default"

    def current_chord(self) -> str:
        return self.harmony.progression[self.bar_index % len(self.harmony.progression)]

    def phrase_bar(self) -> int:
        return (self.bar_index % self.phrase_length) + 1
