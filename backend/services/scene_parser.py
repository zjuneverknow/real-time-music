from __future__ import annotations

try:
    from ..core import SceneState
except ImportError:
    from core import SceneState


SCENE_PRESETS = {
    "none": SceneState(),
    "study_room": SceneState(
        scene_id="study_room",
        scene_type="desk_work",
        motion_level="low",
        lighting="neutral",
        scene_valence=0.52,
        scene_arousal=0.35,
        scene_tokens=["<SCENE_STUDY_ROOM>", "<VISUAL_MOTION_LOW>"],
        control_bias={"density": -0.08, "volatility": -0.08, "repetition": 0.08},
    ),
    "rainy_night": SceneState(
        scene_id="rainy_night",
        scene_type="rainy_window",
        motion_level="low",
        lighting="dim",
        scene_valence=0.38,
        scene_arousal=0.22,
        scene_tokens=["<SCENE_RAINY>", "<SCENE_NIGHT>", "<VISUAL_MOTION_LOW>"],
        control_bias={"tempo": -0.12, "density": -0.12, "wetness": 0.22, "brightness": -0.1},
    ),
    "creative_room": SceneState(
        scene_id="creative_room",
        scene_type="creative_work",
        motion_level="medium",
        lighting="warm",
        scene_valence=0.62,
        scene_arousal=0.5,
        scene_tokens=["<SCENE_CREATIVE_ROOM>", "<VISUAL_MOTION_MED>"],
        control_bias={"brightness": 0.08, "volatility": 0.06, "melody_salience": 0.08},
    ),
    "workout": SceneState(
        scene_id="workout",
        scene_type="exercise",
        motion_level="high",
        lighting="bright",
        scene_valence=0.65,
        scene_arousal=0.75,
        scene_tokens=["<SCENE_WORKOUT>", "<VISUAL_MOTION_HIGH>"],
        control_bias={"tempo": 0.18, "density": 0.12, "rhythm_salience": 0.18, "brightness": 0.1},
    ),
}


def scene_from_id(scene_id: str | None) -> SceneState:
    return SCENE_PRESETS.get(scene_id or "none", SCENE_PRESETS["none"])
