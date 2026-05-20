from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path

try:
    from ..core import AnalysisState, EffectFeatureState, MusicParameterState, MusicalFeatureState, VAState, clamp01
    from ..engines.harmony_analysis import build_harmony, melody_control_from_musical
    from ..engines.prolongation_generator import generate_prolongation_bar
    from ..engines.skeleton_generator import generate_skeleton_bar
    from ..services.control_tokenizer import ControlTokenizer
    from ..services.evaluator import evaluate_bar
    from .symbolic_tokenizer import build_sequence, build_vocabulary
except ImportError:
    from core import AnalysisState, EffectFeatureState, MusicParameterState, MusicalFeatureState, VAState, clamp01
    from engines.harmony_analysis import build_harmony, melody_control_from_musical
    from engines.prolongation_generator import generate_prolongation_bar
    from engines.skeleton_generator import generate_skeleton_bar
    from services.control_tokenizer import ControlTokenizer
    from services.evaluator import evaluate_bar
    from training.symbolic_tokenizer import build_sequence, build_vocabulary


DEFAULT_OUT = Path("backend/training/data/rule_distilled_dataset.jsonl")
DEFAULT_VOCAB = Path("backend/training/data/vocab.json")


def _sample_va() -> VAState:
    return VAState(valence=random.random(), arousal=random.random()).clamp()


def _music_from_va(va: VAState) -> MusicParameterState:
    density_noise = random.uniform(-0.08, 0.08)
    pitch_noise = random.uniform(-0.08, 0.08)
    volatility_noise = random.uniform(-0.08, 0.08)
    return MusicParameterState(
        musical=MusicalFeatureState(
            tempo=clamp01(va.arousal + random.uniform(-0.1, 0.1)),
            density=clamp01(va.arousal * 0.68 + (1 - abs(va.valence - 0.5) * 2) * 0.18 + 0.1 + density_noise),
            mean_pitch=clamp01(va.valence * 0.55 + va.arousal * 0.18 + 0.15 + pitch_noise),
            volatility=clamp01(va.arousal * 0.58 + (1 - va.valence) * 0.24 + 0.05 + volatility_noise),
            pitch_range=clamp01(0.35 + va.arousal * 0.35 + random.uniform(-0.08, 0.08)),
        ),
        effect=EffectFeatureState(
            brightness=clamp01(va.valence * 0.55 + va.arousal * 0.45),
            wetness=clamp01(0.55 - va.arousal * 0.2 + (1 - va.valence) * 0.15),
        ),
    ).clamp()


def generate_samples(sample_count: int, bars_per_sample: int) -> list[dict[str, object]]:
    tokenizer = ControlTokenizer()
    samples: list[dict[str, object]] = []
    for sample_id in range(sample_count):
        va = _sample_va()
        music = _music_from_va(va)
        analysis = AnalysisState(va=va, music=music)
        harmony = build_harmony(va, music.musical)
        control = melody_control_from_musical(music.musical, music.effect.wetness)
        previous_skeleton = []

        for bar_offset in range(bars_per_sample):
            chord_symbol = harmony.progression[bar_offset % len(harmony.progression)]
            prefix = [
                *tokenizer.encode_all(analysis, harmony, chord_symbol),
                f"<BAR_{bar_offset + 1}>",
            ]
            skeleton = generate_skeleton_bar(
                harmony=harmony,
                control=control,
                va=va,
                chord_symbol=chord_symbol,
                previous_skeleton=previous_skeleton,
                bar_index=bar_offset,
            )
            melody = generate_prolongation_bar(
                harmony=harmony,
                control=control,
                chord_symbol=chord_symbol,
                skeleton=skeleton,
            )
            evaluation = evaluate_bar(harmony, control, chord_symbol, skeleton, melody)
            sequence = build_sequence(prefix, skeleton, melody)
            samples.append(
                {
                    "sample_id": sample_id,
                    "bar": bar_offset,
                    "va": asdict(va),
                    "music": {"musical": asdict(music.musical), "effect": asdict(music.effect)},
                    "harmony": asdict(harmony),
                    "chord": chord_symbol,
                    "prefix": prefix,
                    "tokens": sequence,
                    "skeleton": [asdict(note) for note in skeleton],
                    "melody": [asdict(note) for note in melody],
                    "evaluation": evaluation,
                }
            )
            previous_skeleton = skeleton
    return samples


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate rule-distilled symbolic music training data.")
    parser.add_argument("--samples", type=int, default=512)
    parser.add_argument("--bars", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
    args = parser.parse_args()

    random.seed(args.seed)
    rows = generate_samples(args.samples, args.bars)
    write_jsonl(args.out, rows)
    vocab = build_vocabulary([row["tokens"] for row in rows])
    vocab.save(args.vocab)
    print(f"wrote {len(rows)} rows to {args.out}")
    print(f"wrote {len(vocab.token_to_id)} tokens to {args.vocab}")


if __name__ == "__main__":
    main()
