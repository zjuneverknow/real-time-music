from __future__ import annotations

import statistics

try:
    from ..core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote
    from ..engines.melody_generation import chord_tones, scale_notes
except ImportError:
    from core import HarmonyState, MelodyControl, MelodyNote, SkeletonNote
    from engines.melody_generation import chord_tones, scale_notes


def _safe_ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _intervals(notes: list[MelodyNote]) -> list[int]:
    return [abs(notes[index].midi - notes[index - 1].midi) for index in range(1, len(notes))]


def evaluate_bar(
    harmony: HarmonyState,
    control: MelodyControl,
    chord_symbol: str,
    skeleton: list[SkeletonNote],
    melody: list[MelodyNote],
) -> dict[str, float]:
    if not melody:
        return {
            "note_density": 0.0,
            "mean_pitch": 0.0,
            "interval_volatility": 0.0,
            "chord_tone_ratio": 0.0,
            "scale_tone_ratio": 0.0,
            "skeleton_coverage": 0.0,
            "density_error": round(control.density, 4),
            "pitch_error": round(control.mean_pitch, 4),
            "volatility_error": round(control.volatility, 4),
        }

    chord_classes = {note % 12 for note in chord_tones(harmony.mode, chord_symbol)}
    scale_classes = {note % 12 for note in scale_notes(harmony.mode)}
    skeleton_keys = {(note.midi, note.start_beats) for note in skeleton}
    melody_keys = {(note.midi, note.start_beats) for note in melody}
    intervals = _intervals(melody)

    actual_density = min(1.0, len(melody) / 8)
    actual_mean_pitch = min(1.0, max(0.0, (statistics.mean(note.midi for note in melody) - 48) / 36))
    actual_volatility = min(1.0, (statistics.mean(intervals) if intervals else 0.0) / 12)
    chord_count = sum(1 for note in melody if note.midi % 12 in chord_classes)
    scale_count = sum(1 for note in melody if note.midi % 12 in scale_classes)
    covered_skeleton = sum(1 for key in skeleton_keys if key in melody_keys)

    return {
        "note_density": round(actual_density, 4),
        "mean_pitch": round(actual_mean_pitch, 4),
        "interval_volatility": round(actual_volatility, 4),
        "chord_tone_ratio": _safe_ratio(chord_count, len(melody)),
        "scale_tone_ratio": _safe_ratio(scale_count, len(melody)),
        "skeleton_coverage": _safe_ratio(covered_skeleton, len(skeleton)),
        "density_error": round(abs(actual_density - control.density), 4),
        "pitch_error": round(abs(actual_mean_pitch - control.mean_pitch), 4),
        "volatility_error": round(abs(actual_volatility - control.volatility), 4),
    }
