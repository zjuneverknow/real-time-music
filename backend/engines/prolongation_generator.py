from __future__ import annotations

try:
    from ..core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote, lerp
    from .melody_generation import apply_register, get_note_pool
except ImportError:
    from core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote, lerp
    from engines.melody_generation import apply_register, get_note_pool


def _closest_scale_step(start: int, target: int, pool: list[int]) -> int:
    direction = 1 if target >= start else -1
    candidates = [note for note in pool if (note - start) * direction > 0]
    if not candidates:
        return start
    return min(candidates, key=lambda note: abs(note - target))


def generate_prolongation_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    chord_symbol: str,
    skeleton: list[SkeletonNote],
) -> list[MelodyNote]:
    if not skeleton:
        return []

    pool = get_note_pool(harmony.mode, chord_symbol)
    events: list[MelodyNote] = []
    base_velocity = lerp(0.54, 0.9, control.density)

    for index, note in enumerate(skeleton):
        next_note = skeleton[index + 1] if index + 1 < len(skeleton) else None
        interval_duration = (next_note.start_beats - note.start_beats) if next_note else note.duration_beats
        if control.density < 0.36 or interval_duration <= 0.5:
            events.append(
                MelodyNote(
                    midi=note.midi,
                    start_beats=note.start_beats,
                    duration_beats=max(0.25, interval_duration),
                    velocity=round(base_velocity, 3),
                )
            )
            continue

        step = 0.5 if control.density < 0.72 else 0.25
        cursor = note.start_beats
        target = next_note.midi if next_note else note.midi
        current = note.midi
        while cursor < note.start_beats + interval_duration - 0.001:
            is_anchor = abs(cursor - note.start_beats) < 0.001
            if is_anchor:
                midi = note.midi
            elif control.volatility > 0.62 and int(cursor * 4) % 3 == 0:
                midi = apply_register(current + (7 if target >= current else -7), control.mean_pitch)
            else:
                midi = _closest_scale_step(current, target, pool)

            events.append(
                MelodyNote(
                    midi=midi,
                    start_beats=round(cursor, 3),
                    duration_beats=round(step, 3),
                    velocity=round(base_velocity * (1.0 if is_anchor else 0.82), 3),
                )
            )
            current = midi
            cursor += step

    return events
