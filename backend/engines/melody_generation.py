from __future__ import annotations

import random

try:
    from ..core import HarmonyState, MelodyControl, MelodyNote, lerp
    from .harmony_analysis import MODE_LIBRARY
except ImportError:
    from core import HarmonyState, MelodyControl, MelodyNote, lerp
    from engines.harmony_analysis import MODE_LIBRARY


def weighted_sample(candidates: list[int], weight_fn) -> int:
    weights = [max(weight_fn(value), 0.001) for value in candidates]
    total = sum(weights)
    threshold = random.random() * total
    cursor = 0.0
    for value, weight in zip(candidates, weights):
        cursor += weight
        if cursor >= threshold:
            return value
    return candidates[-1]


def generate_rhythm(density: float) -> list[tuple[int, int]]:
    notes_per_bar = max(1, min(8, int(1 + density * 7)))
    chosen = {0}

    strong_beats = [4, 8, 12]
    random.shuffle(strong_beats)
    for step in strong_beats:
        if len(chosen) >= notes_per_bar:
            break
        if random.random() < 0.45 + density * 0.35:
            chosen.add(step)

    remaining = [step for step in range(16) if step not in chosen]
    random.shuffle(remaining)
    for step in remaining:
        if len(chosen) >= notes_per_bar:
            break
        bias = 0.3 if step % 4 == 0 else 0.75
        if random.random() < bias:
            chosen.add(step)

    ordered = sorted(chosen)[:notes_per_bar]
    result: list[tuple[int, int]] = []
    for index, step in enumerate(ordered):
        next_step = ordered[index + 1] if index + 1 < len(ordered) else 16
        result.append((step, max(1, next_step - step)))
    return result


def chord_tones(mode: str, chord_symbol: str) -> list[int]:
    chord = MODE_LIBRARY[mode]["chords"][chord_symbol]
    return [60 + pitch_class for pitch_class in chord]


def scale_notes(mode: str) -> list[int]:
    pitch_classes = MODE_LIBRARY[mode]["scale_pitch_classes"]
    notes = []
    for octave in (48, 60, 72):
        notes.extend(octave + pitch_class for pitch_class in pitch_classes)
    return notes


def get_note_pool(mode: str, chord_symbol: str) -> list[int]:
    return sorted(set(chord_tones(mode, chord_symbol) + scale_notes(mode)))


def next_note(prev: int, pool: list[int], volatility: float) -> int:
    def weight(note: int) -> float:
        interval = abs(note - prev)
        if volatility > 0.5:
            return interval + 1
        return 1 / (interval + 1)

    return weighted_sample(pool, weight)


def apply_register(note: int, mean_pitch: float) -> int:
    target = 60 + int(round(mean_pitch * 24))
    while note < target - 6:
        note += 12
    while note > target + 6:
        note -= 12
    return max(36, min(96, note))


def generate_melody_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    chord_symbol: str,
    previous_note: int,
) -> tuple[list[MelodyNote], int]:
    notes: list[MelodyNote] = []
    rhythm = generate_rhythm(control.density)
    stable_tones = chord_tones(harmony.mode, chord_symbol)
    pool = get_note_pool(harmony.mode, chord_symbol)
    current_prev = previous_note

    for step, duration in rhythm:
        strong_beat = step % 4 == 0
        candidate_pool = stable_tones if strong_beat else pool
        note = next_note(current_prev, candidate_pool, control.volatility)
        note = apply_register(note, control.mean_pitch)
        notes.append(
            MelodyNote(
                midi=note,
                start_beats=round(step / 4, 3),
                duration_beats=round(duration / 4, 3),
                velocity=round(lerp(0.55, 0.9, control.density), 3),
            )
        )
        current_prev = note

    return notes, current_prev


def chord_payload(harmony: HarmonyState, chord_symbol: str) -> dict[str, object]:
    return {
        "symbol": chord_symbol,
        "tones": chord_tones(harmony.mode, chord_symbol),
        "bass_root": MODE_LIBRARY[harmony.mode]["bass"][chord_symbol],
    }
