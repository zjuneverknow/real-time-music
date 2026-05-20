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
    melody_salience: float = 0.5
    rhythm_salience: float = 0.5
    repetition: float = 0.5

    def clamp(self) -> "MelodyControl":
        return MelodyControl(
            density=clamp01(self.density),
            volatility=clamp01(self.volatility),
            mean_pitch=clamp01(self.mean_pitch),
            pitch_range=clamp01(self.pitch_range),
            wetness=clamp01(self.wetness),
            melody_salience=clamp01(self.melody_salience),
            rhythm_salience=clamp01(self.rhythm_salience),
            repetition=clamp01(self.repetition),
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
class RawUserState:
    dominant_emotion: str
    primary_intent: str
    secondary_intent: str | None
    activity: str
    cognitive_load: str
    attention_need: str
    distraction_tolerance: str
    music_role: str
    desired_effect: str
    liked_elements: list[str] = field(default_factory=list)
    disliked_elements: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    soft_constraints: list[str] = field(default_factory=list)
    regulation_mode: str = "emotion_matching"
    target_state: str = "same_as_current"
    confidence: float = 0.7


@dataclass
class StructuredUserState:
    va: VAState
    raw_va: VAState
    dominant_emotion: str
    intent: str
    secondary_intent: str | None
    activity: str
    cognitive_load: str
    attention_need: str
    distraction_tolerance: str
    music_role: str
    desired_effect: str
    active_constraints: list[str] = field(default_factory=list)
    target_va: VAState = field(default_factory=lambda: VAState(0.55, 0.4))
    regulation_mode: str = "emotion_regulation"


@dataclass
class UserMusicProfile:
    user_id: str = "default"
    liked_styles: list[str] = field(default_factory=lambda: ["ambient", "soft_piano"])
    disliked_styles: list[str] = field(default_factory=list)
    preferred_instruments: list[str] = field(default_factory=lambda: ["piano", "soft_pad"])
    disliked_instruments: list[str] = field(default_factory=lambda: ["heavy_drums"])
    preferred_tempo: float = 0.42
    preferred_density: float = 0.38
    preferred_brightness: float = 0.52
    preferred_volatility: float = 0.3
    preferred_mean_pitch: float = 0.48
    preferred_wetness: float = 0.62
    melody_salience: float = 0.35
    rhythm_salience: float = 0.38
    repetition: float = 0.72
    policy_preferences: dict[str, float] = field(
        default_factory=lambda: {
            "calm_focus": 0.72,
            "deep_focus": 0.66,
            "neutral_background": 0.55,
            "emotion_matching": 0.45,
        }
    )
    feedback_count: int = 0


@dataclass
class SceneState:
    scene_id: str = "none"
    scene_type: str = "none"
    motion_level: str = "medium"
    lighting: str = "neutral"
    scene_valence: float = 0.5
    scene_arousal: float = 0.45
    scene_tokens: list[str] = field(default_factory=list)
    control_bias: dict[str, float] = field(default_factory=dict)


@dataclass
class GenerationPolicy:
    policy_id: str
    style: str
    target_va: VAState
    tempo_range: tuple[float, float]
    density_range: tuple[float, float]
    volatility_range: tuple[float, float]
    brightness_range: tuple[float, float]
    melody_salience: float
    rhythm_salience: float
    repetition: float
    instrumentation: list[str]
    avoid: list[str]
    reason: str


@dataclass
class FinalMusicControlState:
    target_va: VAState
    policy: str
    style: str
    tempo: float
    density: float
    brightness: float
    volatility: float
    mean_pitch: float
    wetness: float
    mode: str
    chord_progression_type: str
    instrumentation: list[str]
    melody_salience: float
    rhythm_salience: float
    repetition: float
    transition_curve: dict[str, str] = field(default_factory=dict)

    def to_music_parameters(self) -> MusicParameterState:
        return MusicParameterState(
            musical=MusicalFeatureState(
                tempo=clamp01(self.tempo),
                density=clamp01(self.density),
                mean_pitch=clamp01(self.mean_pitch),
                volatility=clamp01(self.volatility),
                pitch_range=clamp01(0.35 + self.volatility * 0.35),
            ),
            effect=EffectFeatureState(
                brightness=clamp01(self.brightness),
                wetness=clamp01(self.wetness),
            ),
        ).clamp()

    def to_melody_control(self) -> MelodyControl:
        return MelodyControl(
            density=self.density,
            volatility=self.volatility,
            mean_pitch=self.mean_pitch,
            pitch_range=0.35 + self.volatility * 0.35,
            wetness=self.wetness,
            melody_salience=self.melody_salience,
            rhythm_salience=self.rhythm_salience,
            repetition=self.repetition,
        ).clamp()


@dataclass
class SessionState:
    analysis: AnalysisState
    control: MelodyControl
    harmony: HarmonyState
    raw_user_state: RawUserState | None = None
    structured_user_state: StructuredUserState | None = None
    user_profile: UserMusicProfile = field(default_factory=UserMusicProfile)
    scene_state: SceneState = field(default_factory=SceneState)
    selected_policy: GenerationPolicy | None = None
    final_control_state: FinalMusicControlState | None = None
    previous_note: int = 60
    previous_skeleton: list[SkeletonNote] = field(default_factory=list)
    phrase_motif: list[SkeletonNote] = field(default_factory=list)
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
