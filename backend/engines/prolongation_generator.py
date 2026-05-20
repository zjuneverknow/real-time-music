from __future__ import annotations

try:
    from ..core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote, lerp
    from .melody_generation import apply_register, chord_tones, get_note_pool
except ImportError:
    from core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote, lerp
    from engines.melody_generation import apply_register, chord_tones, get_note_pool


def _closest_scale_step(start: int, target: int, pool: list[int]) -> int:
    direction = 1 if target >= start else -1
    candidates = [note for note in pool if (note - start) * direction > 0]
    if not candidates:
        return start
    return min(candidates, key=lambda note: abs(note - target))


def _nearest_chord_tone(note: int, chord_pool: list[int]) -> int:
    return min(chord_pool, key=lambda chord_note: abs(chord_note - note))


def _neighbor_note(anchor: int, target: int, pool: list[int], mean_pitch: float) -> int:
    direction = 1 if target >= anchor else -1
    candidates = [note for note in pool if 0 < (note - anchor) * direction <= 3]
    if not candidates:
        candidates = [note for note in pool if abs(note - anchor) <= 2 and note != anchor]
    if not candidates:
        return anchor
    return apply_register(min(candidates, key=lambda note: abs(note - target)), mean_pitch)


def generate_prolongation_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    chord_symbol: str,
    skeleton: list[SkeletonNote],
) -> list[MelodyNote]:
    if not skeleton:
        return []

    pool = get_note_pool(harmony.mode, chord_symbol)
    chord_pool = [apply_register(note, control.mean_pitch) for note in chord_tones(harmony.mode, chord_symbol)]
    events: list[MelodyNote] = []
    base_velocity = lerp(0.42, 0.78, control.density)

    for index, note in enumerate(skeleton):
        next_note = skeleton[index + 1] if index + 1 < len(skeleton) else None
        interval_duration = (next_note.start_beats - note.start_beats) if next_note else note.duration_beats
        ornament_density = control.density * (0.5 + control.melody_salience * 0.48) * (1.05 - control.repetition * 0.35)
        if ornament_density < 0.36 or interval_duration <= 0.5:
            events.append(
                MelodyNote(
                    midi=_nearest_chord_tone(note.midi, chord_pool) if note.start_beats in {0.0, 2.0} else note.midi,
                    start_beats=note.start_beats,
                    duration_beats=max(0.25, interval_duration),
                    velocity=round(base_velocity, 3),
                )
            )
            continue

        step = 0.5 if ornament_density < 0.72 else 0.25
        cursor = note.start_beats
        target = next_note.midi if next_note else note.midi
        current = note.midi
        while cursor < note.start_beats + interval_duration - 0.001:
            is_anchor = abs(cursor - note.start_beats) < 0.001
            strong_position = abs(cursor % 1.0) < 0.001
            if is_anchor:
                midi = _nearest_chord_tone(note.midi, chord_pool) if strong_position else note.midi
            elif control.volatility > 0.62 and int(cursor * 4) % 3 == 0:
                midi = _nearest_chord_tone(apply_register(current + (5 if target >= current else -5), control.mean_pitch), chord_pool)
            elif control.repetition > 0.72 and int(cursor * 4) % 4 == 2:
                midi = current
            elif ornament_density > 0.55 and int(cursor * 4) % 4 == 1:
                midi = _neighbor_note(note.midi, target, pool, control.mean_pitch)
            else:
                midi = _closest_scale_step(current, target, pool)
                if strong_position:
                    midi = _nearest_chord_tone(midi, chord_pool)

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
