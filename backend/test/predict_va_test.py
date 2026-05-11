from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.predict import predict_va


TEXT_TO_VA_MODEL_DIR = ROOT / "backend" / "model" / "text_to_va"
SAMPLES = [
    "calm and peaceful morning",
    "tense and chaotic downtown at midnight",
    "deep sadness after a loss",
    "bright hopeful celebration with friends",
    "neutral daily routine",
]


def to_scale_1_9(value: float) -> float:
    return 1.0 + value * 8.0


if __name__ == "__main__":
    print(f"Model dir: {TEXT_TO_VA_MODEL_DIR}")
    print()

    for text in SAMPLES:
        result = predict_va(
            text=text,
            model_dir=str(TEXT_TO_VA_MODEL_DIR),
            clamp_output=True,
        )
        valence = result["valence"]
        arousal = result["arousal"]
        print(f"Text: {text}")
        print(f"  raw -> valence={valence:.4f}, arousal={arousal:.4f}")
        print(
            "  mapped 1-9 -> "
            f"valence={to_scale_1_9(valence):.4f}, arousal={to_scale_1_9(arousal):.4f}"
        )
        print()
