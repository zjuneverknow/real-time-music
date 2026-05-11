from __future__ import annotations

try:
    from ..core import HarmonyState, MelodyControl, MusicalFeatureState, VAState, clamp01, lerp
except ImportError:
    from core import HarmonyState, MelodyControl, MusicalFeatureState, VAState, clamp01, lerp


MODE_LIBRARY = {
    "major": {
        "scale": "ionian",
        "progression": ["I", "V", "vi", "IV"],
        "scale_pitch_classes": [0, 2, 4, 5, 7, 9, 11],
        "chords": {
            "I": [0, 4, 7],
            "V": [7, 11, 14],
            "vi": [9, 12, 16],
            "IV": [5, 9, 12],
        },
        "bass": {
            "I": 36,
            "V": 43,
            "vi": 45,
            "IV": 41,
        },
    },
    "minor": {
        "scale": "aeolian",
        "progression": ["i", "VI", "III", "VII"],
        "scale_pitch_classes": [0, 2, 3, 5, 7, 8, 10],
        "chords": {
            "i": [0, 3, 7],
            "VI": [8, 12, 15],
            "III": [3, 7, 10],
            "VII": [10, 14, 17],
        },
        "bass": {
            "i": 36,
            "VI": 44,
            "III": 39,
            "VII": 46,
        },
    },
    "dorian": {
        "scale": "dorian",
        "progression": ["i", "IV", "v", "VII"],
        "scale_pitch_classes": [0, 2, 3, 5, 7, 9, 10],
        "chords": {
            "i": [0, 3, 7],
            "IV": [5, 9, 12],
            "v": [7, 10, 14],
            "VII": [10, 14, 17],
        },
        "bass": {
            "i": 38,
            "IV": 43,
            "v": 45,
            "VII": 36,
        },
    },
}


def build_harmony(va: VAState, musical: MusicalFeatureState) -> HarmonyState:
    major_score = va.valence
    minor_score = 1 - va.valence
    dorian_score = (1 - abs(va.valence - 0.5) * 2) * (0.75 + va.arousal * 0.25)
    scores = {"major": major_score, "minor": minor_score, "dorian": dorian_score}
    mode = max(scores, key=scores.get)
    tempo_driver = clamp01(va.arousal * 0.55 + musical.tempo * 0.45)
    bpm = int(round(lerp(68, 148, tempo_driver)))
    spec = MODE_LIBRARY[mode]
    return HarmonyState(
        key="C",
        mode=mode,
        bpm=bpm,
        progression=spec["progression"],
        scale=spec["scale"],
    )


def melody_control_from_musical(musical: MusicalFeatureState, wetness: float) -> MelodyControl:
    return MelodyControl(
        density=musical.density,
        volatility=musical.volatility,
        mean_pitch=musical.mean_pitch,
        pitch_range=musical.pitch_range,
        wetness=wetness,
    ).clamp()
