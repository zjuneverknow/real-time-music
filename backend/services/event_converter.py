from __future__ import annotations

try:
    from ..core import EffectFeatureState, MelodyNote, MusicEvent, SkeletonNote
except ImportError:
    from core import EffectFeatureState, MelodyNote, MusicEvent, SkeletonNote


def to_music_events(
    melody: list[MelodyNote],
    skeleton: list[SkeletonNote],
    bar_index: int,
    chord_symbol: str,
    effect: EffectFeatureState,
    instrument: str = "melody",
) -> list[MusicEvent]:
    skeleton_keys = {(note.midi, note.start_beats) for note in skeleton}
    events: list[MusicEvent] = [
        MusicEvent(
            bar=bar_index,
            beat=0.0,
            type="effect",
            chord=chord_symbol,
            effect={
                "brightness": round(effect.brightness, 4),
                "wetness": round(effect.wetness, 4),
            },
        )
    ]
    for note in melody:
        role = "skeleton" if (note.midi, note.start_beats) in skeleton_keys else "decoration"
        events.append(
            MusicEvent(
                bar=bar_index,
                beat=note.start_beats,
                type="note",
                pitch=note.midi,
                duration=note.duration_beats,
                velocity=note.velocity,
                chord=chord_symbol,
                instrument=instrument,
                role=role,
            )
        )
    return events
