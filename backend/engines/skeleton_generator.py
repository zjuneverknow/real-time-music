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


RHYTHM_PATTERNS = {
    "sparse": [0, 8],
    "focus": [0, 6, 10],
    "lofi": [0, 3, 8, 11],
    "active": [0, 2, 6, 8, 12],
}


def _skeleton_positions(density: float, arousal: float, rhythm_salience: float) -> list[tuple[int, int]]:
    count = 1 if density < 0.28 else 2 if density < 0.6 else 3 if density < 0.82 else 4
    if rhythm_salience < 0.25:
        positions = RHYTHM_PATTERNS["sparse"]
    elif arousal > 0.6 or rhythm_salience > 0.62:
        positions = RHYTHM_PATTERNS["active"]
    elif rhythm_salience > 0.42:
        positions = RHYTHM_PATTERNS["lofi"]
    else:
        positions = RHYTHM_PATTERNS["focus"]
    return [(step, 16) for step in sorted(set(positions))[:count]]


def _nearest_pitch_class(note: int, pitch_classes: set[int], prefer_down: bool = False) -> int:
    candidates = [note + offset for offset in range(-12, 13) if (note + offset) % 12 in pitch_classes]
    if not candidates:
        return note
    return min(candidates, key=lambda candidate: (abs(candidate - note), candidate if prefer_down else -candidate))


def _motif_variant(
    phrase_motif: list[SkeletonNote],
    control: MelodyControl,
    chord_symbol: str,
    mode: str,
    bar_index: int,
) -> list[SkeletonNote]:
    if not phrase_motif:
        return []
    phrase_position = bar_index % 4
    chord_classes = {tone % 12 for tone in chord_tones(mode, chord_symbol)}
    contour_shift = [0, 2, 5, -2][phrase_position]
    duration_scale = 1.0 if control.repetition > 0.55 else 0.85
    variant: list[SkeletonNote] = []
    for index, motif_note in enumerate(phrase_motif):
        if phrase_position == 1 and index > 0 and control.density < 0.42:
            continue
        raw = apply_register(motif_note.midi + contour_shift, control.mean_pitch)
        if phrase_position == 3 and index == len(phrase_motif) - 1:
            raw = _nearest_pitch_class(raw - 2, chord_classes, prefer_down=True)
        else:
            raw = _nearest_pitch_class(raw, chord_classes)
        variant.append(
            SkeletonNote(
                midi=max(36, min(96, raw)),
                start_beats=motif_note.start_beats,
                duration_beats=round(max(0.5, motif_note.duration_beats * duration_scale), 3),
            )
        )
    return variant


def generate_skeleton_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    va: VAState,
    chord_symbol: str,
    previous_skeleton: list[SkeletonNote],
    bar_index: int,
    phrase_motif: list[SkeletonNote] | None = None,
) -> list[SkeletonNote]:
    if phrase_motif and bar_index % 4 != 0 and control.repetition > 0.45:
        return _motif_variant(phrase_motif, control, chord_symbol, harmony.mode, bar_index)

    pool = get_note_pool(harmony.mode, chord_symbol)
    stable_tones = set(chord_tones(harmony.mode, chord_symbol))
    previous_note = previous_skeleton[-1].midi if previous_skeleton else 60
    target = 60 + int(round(control.mean_pitch * 24))
    phrase_position = bar_index % 4
    phrase_lift = [0, 2, 5, -1][phrase_position]
    temperature = 0.12 + control.volatility * 0.45
    skeleton: list[SkeletonNote] = []
    structural_density = max(0.05, min(1.0, control.density * (0.65 + control.melody_salience * 0.7)))
    positions = _skeleton_positions(structural_density, va.arousal, control.rhythm_salience)

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
            leap_penalty = max(0.0, (interval - (3 + control.volatility * 8)) / 12)
            motion_score = 0.4 if interval <= 2 and control.volatility > 0.55 else 0.0
            phrase_score = 0.25 if (phrase_position == 3 and note % 12 in {0, 4, 7, 3}) else 0.0
            score = chord_score + center_score + smooth_score + motion_score + phrase_score - leap_penalty
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
