from __future__ import annotations

import math
import random

try:
    from ..core import HarmonyState, MelodyControl, SkeletonNote, VAState
    from .melody_generation import apply_register, chord_tones, get_note_pool
except ImportError:
    from core import HarmonyState, MelodyControl, SkeletonNote, VAState
    from engines.melody_generation import apply_register, chord_tones, get_note_pool


def _softmax_sample(candidates: list[tuple[int, float]], temperature: float) -> int:
    if not candidates:
        return 60
    temperature = max(0.05, temperature)
    top = sorted(candidates, key=lambda item: item[1], reverse=True)[:8]
    best_score = top[0][1]
    weights = [math.exp((score - best_score) / temperature) for _, score in top]
    total = sum(weights)
    threshold = random.random() * total
    cursor = 0.0
    for (note, _), weight in zip(top, weights):
        cursor += weight
        if cursor >= threshold:
            return note
    return top[-1][0]


def _skeleton_positions(density: float, arousal: float) -> list[tuple[int, int]]:
    count = 1 if density < 0.28 else 2 if density < 0.6 else 3 if density < 0.82 else 4
    positions = [0, 8]
    if arousal > 0.55:
        positions.extend([6, 12, 14])
    else:
        positions.extend([4, 12])
    return [(step, 16) for step in sorted(set(positions))[:count]]


def generate_skeleton_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    va: VAState,
    chord_symbol: str,
    previous_skeleton: list[SkeletonNote],
    bar_index: int,
) -> list[SkeletonNote]:
    pool = get_note_pool(harmony.mode, chord_symbol)
    stable_tones = set(chord_tones(harmony.mode, chord_symbol))
    previous_note = previous_skeleton[-1].midi if previous_skeleton else 60
    target = 60 + int(round(control.mean_pitch * 24))
    phrase_position = bar_index % 4
    phrase_lift = [0, 2, 5, -1][phrase_position]
    temperature = 0.12 + control.volatility * 0.45
    skeleton: list[SkeletonNote] = []
    positions = _skeleton_positions(control.density, va.arousal)

    for index, (step, _) in enumerate(positions):
        phrase_target = target + phrase_lift + index * (1 if va.valence >= 0.5 else -1)
        candidates: list[tuple[int, float]] = []
        for raw_note in pool:
            note = apply_register(raw_note, control.mean_pitch)
            interval = abs(note - previous_note)
            center_distance = abs(note - phrase_target)
            chord_score = 1.4 if note % 12 in {tone % 12 for tone in stable_tones} else 0.35
            center_score = max(0.0, 1.0 - center_distance / 18)
            smooth_score = max(0.0, 1.0 - interval / (4 + control.volatility * 18))
            motion_score = 0.4 if interval <= 2 and control.volatility > 0.55 else 0.0
            score = chord_score + center_score + smooth_score + motion_score
            candidates.append((note, score))

        midi = _softmax_sample(candidates, temperature)
        next_step = positions[index + 1][0] if index + 1 < len(positions) else 16
        skeleton.append(
            SkeletonNote(
                midi=midi,
                start_beats=round(step / 4, 3),
                duration_beats=round(max(2, next_step - step) / 4, 3),
            )
        )
        previous_note = midi

    return skeleton
