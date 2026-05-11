from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import asdict

from fastapi import WebSocket, WebSocketDisconnect

try:
    from ..core import AnalysisState, SessionState
    from ..engines.harmony_analysis import build_harmony, melody_control_from_musical
    from ..engines.melody_generation import chord_payload
    from ..engines.prolongation_generator import generate_prolongation_bar
    from ..engines.skeleton_generator import generate_skeleton_bar
    from ..services.control_tokenizer import ControlTokenizer
    from ..services.event_converter import to_music_events
    from ..services.mood_processing import DEFAULT_ANALYSIS, MoodProcessor
    from ..services.va_tracker import VAStateTracker, confidence_from_text
except ImportError:
    from core import AnalysisState, SessionState
    from engines.harmony_analysis import build_harmony, melody_control_from_musical
    from engines.melody_generation import chord_payload
    from engines.prolongation_generator import generate_prolongation_bar
    from engines.skeleton_generator import generate_skeleton_bar
    from services.control_tokenizer import ControlTokenizer
    from services.event_converter import to_music_events
    from services.mood_processing import DEFAULT_ANALYSIS, MoodProcessor
    from services.va_tracker import VAStateTracker, confidence_from_text


def emotion_payload(analysis: AnalysisState) -> dict[str, float]:
    return analysis.emotion_dict()


def music_feature_payload(analysis: AnalysisState) -> dict[str, float]:
    return analysis.music.flat_dict()


def session_payload(session: SessionState) -> dict[str, object]:
    return {
        "type": "session_state",
        "va": asdict(session.analysis.va),
        "music": {
            "musical": asdict(session.analysis.music.musical),
            "effect": asdict(session.analysis.music.effect),
        },
        "emotion": emotion_payload(session.analysis),
        "music_features": music_feature_payload(session.analysis),
        "control": asdict(session.control),
        "control_tokens": session.control_tokens,
        "va_tracker": asdict(session.va_tracker) if session.va_tracker else None,
        "harmony": {
            **asdict(session.harmony),
            "current_chord": session.current_chord(),
            "phrase_bar": session.phrase_bar(),
            "phrase_length": session.phrase_length,
        },
        "source": session.last_source,
    }


async def run_music_socket(websocket: WebSocket, processor: MoodProcessor) -> None:
    await websocket.accept()
    tokenizer = ControlTokenizer()
    va_tracker = VAStateTracker(DEFAULT_ANALYSIS.va)

    session = SessionState(
        analysis=DEFAULT_ANALYSIS,
        control=melody_control_from_musical(
            DEFAULT_ANALYSIS.music.musical,
            DEFAULT_ANALYSIS.music.effect.wetness,
        ),
        harmony=build_harmony(DEFAULT_ANALYSIS.va, DEFAULT_ANALYSIS.music.musical),
        va_tracker=va_tracker.current(),
    )
    session.control_tokens = tokenizer.encode_all(session.analysis, session.harmony, session.current_chord())
    update_lock = asyncio.Lock()

    async def send_session_state() -> None:
        await websocket.send_json(session_payload(session))

    async def bar_loop() -> None:
        nonlocal session
        next_wakeup = time.monotonic() + 0.2
        await send_session_state()

        while True:
            async with update_lock:
                if session.bar_index == 0 or (session.harmony_dirty and session.bar_index % session.phrase_length == 0):
                    session.harmony = build_harmony(session.analysis.va, session.analysis.music.musical)
                    session.harmony_dirty = False
                    await websocket.send_json(session_payload(session))

                chord_symbol = session.current_chord()
                session.control_tokens = tokenizer.encode_all(session.analysis, session.harmony, chord_symbol)
                skeleton = generate_skeleton_bar(
                    session.harmony,
                    session.control,
                    session.analysis.va,
                    chord_symbol,
                    session.previous_skeleton,
                    session.bar_index,
                )
                notes = generate_prolongation_bar(
                    session.harmony,
                    session.control,
                    chord_symbol,
                    skeleton,
                )
                events = to_music_events(
                    melody=notes,
                    skeleton=skeleton,
                    bar_index=session.bar_index,
                    chord_symbol=chord_symbol,
                    effect=session.analysis.music.effect,
                )
                if notes:
                    session.previous_note = notes[-1].midi
                session.previous_skeleton = skeleton
                bpm = session.harmony.bpm
                seconds_per_beat = 60 / bpm
                payload = {
                    "type": "melody_bar",
                    "bar_index": session.bar_index,
                    "bar_duration_seconds": round(seconds_per_beat * 4, 4),
                    "va": asdict(session.analysis.va),
                    "music": {
                        "musical": asdict(session.analysis.music.musical),
                        "effect": asdict(session.analysis.music.effect),
                    },
                    "harmony": {
                        **asdict(session.harmony),
                        "current_chord": chord_symbol,
                        "phrase_bar": session.phrase_bar(),
                        "phrase_length": session.phrase_length,
                        "chord": chord_payload(session.harmony, chord_symbol),
                    },
                    "control": asdict(session.control),
                    "control_tokens": session.control_tokens,
                    "va_tracker": asdict(session.va_tracker) if session.va_tracker else None,
                    "emotion": emotion_payload(session.analysis),
                    "music_features": music_feature_payload(session.analysis),
                    "skeleton": [asdict(note) for note in skeleton],
                    "events": [asdict(event) for event in events],
                    "notes": [asdict(note) for note in notes],
                }
                session.bar_index += 1

            await websocket.send_json(payload)
            next_wakeup += seconds_per_beat * 4
            await asyncio.sleep(max(0.0, next_wakeup - time.monotonic()))

    async def receive_loop() -> None:
        nonlocal session
        while True:
            message = await websocket.receive_json()
            mood = message.get("mood", "")
            raw_analysis, source = await asyncio.to_thread(processor.process_safe, mood)
            confidence = confidence_from_text(mood)
            async with update_lock:
                tracked_va = va_tracker.update(raw_analysis.va, confidence=confidence)
                next_analysis = processor.analysis_from_va(tracked_va.as_va(), mood)
                session.analysis = next_analysis
                session.control = melody_control_from_musical(
                    next_analysis.music.musical,
                    next_analysis.music.effect.wetness,
                )
                session.va_tracker = tracked_va
                session.control_tokens = tokenizer.encode_all(
                    session.analysis,
                    session.harmony,
                    session.current_chord(),
                )
                session.harmony_dirty = True
                session.last_source = source

            await websocket.send_json(
                {
                    "type": "mood_ack",
                    "mood": mood,
                    "va": asdict(next_analysis.va),
                    "music": {
                        "musical": asdict(next_analysis.music.musical),
                        "effect": asdict(next_analysis.music.effect),
                    },
                    "emotion": emotion_payload(next_analysis),
                    "music_features": music_feature_payload(next_analysis),
                    "control": asdict(session.control),
                    "control_tokens": session.control_tokens,
                    "va_tracker": asdict(tracked_va),
                    "source": source,
                    "harmony_refresh": "next_phrase",
                }
            )

    sender = asyncio.create_task(bar_loop())
    receiver = asyncio.create_task(receive_loop())
    try:
        await asyncio.gather(sender, receiver)
    except WebSocketDisconnect:
        pass
    finally:
        for task in (sender, receiver):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
