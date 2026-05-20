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
    from ..services.control_fusion import MultimodalControlFusion
    from ..services.dialogue_state import parse_dialogue_state
    from ..services.event_converter import to_music_events
    from ..services.evaluator import evaluate_bar
    from ..services.generation_logger import GenerationLogger
    from ..services.mood_processing import DEFAULT_ANALYSIS, MoodProcessor
    from ..services.policy_recommender import PolicyRecommender
    from ..services.recommendation_profile import ProfileManager
    from ..services.scene_parser import scene_from_id
    from ..services.user_state_tracker import UserStateTracker
    from ..services.va_tracker import VAStateTracker, confidence_from_text
except ImportError:
    from core import AnalysisState, SessionState
    from engines.harmony_analysis import build_harmony, melody_control_from_musical
    from engines.melody_generation import chord_payload
    from engines.prolongation_generator import generate_prolongation_bar
    from engines.skeleton_generator import generate_skeleton_bar
    from services.control_tokenizer import ControlTokenizer
    from services.control_fusion import MultimodalControlFusion
    from services.dialogue_state import parse_dialogue_state
    from services.event_converter import to_music_events
    from services.evaluator import evaluate_bar
    from services.generation_logger import GenerationLogger
    from services.mood_processing import DEFAULT_ANALYSIS, MoodProcessor
    from services.policy_recommender import PolicyRecommender
    from services.recommendation_profile import ProfileManager
    from services.scene_parser import scene_from_id
    from services.user_state_tracker import UserStateTracker
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
        "raw_user_state": asdict(session.raw_user_state) if session.raw_user_state else None,
        "structured_user_state": asdict(session.structured_user_state) if session.structured_user_state else None,
        "user_profile": asdict(session.user_profile),
        "scene_state": asdict(session.scene_state),
        "selected_policy": asdict(session.selected_policy) if session.selected_policy else None,
        "final_control_state": asdict(session.final_control_state) if session.final_control_state else None,
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
    user_state_tracker = UserStateTracker()
    profile_manager = ProfileManager()
    policy_recommender = PolicyRecommender()
    control_fusion = MultimodalControlFusion()
    generation_logger = GenerationLogger()
    initial_raw_user_state = parse_dialogue_state("neutral background", DEFAULT_ANALYSIS.va, 0.7)
    initial_structured_user_state = user_state_tracker.update(initial_raw_user_state, va_tracker.current())
    initial_policy = policy_recommender.recommend(
        initial_structured_user_state,
        profile_manager.current(),
        scene_from_id("none"),
    )
    initial_final_control = control_fusion.fuse(
        DEFAULT_ANALYSIS,
        initial_structured_user_state,
        profile_manager.current(),
        scene_from_id("none"),
        initial_policy,
    )
    initial_analysis = AnalysisState(
        va=initial_structured_user_state.va,
        music=initial_final_control.to_music_parameters(),
    )

    session = SessionState(
        analysis=initial_analysis,
        control=initial_final_control.to_melody_control(),
        harmony=build_harmony(initial_analysis.va, initial_analysis.music.musical),
        raw_user_state=initial_raw_user_state,
        structured_user_state=initial_structured_user_state,
        user_profile=profile_manager.current(),
        scene_state=scene_from_id("none"),
        selected_policy=initial_policy,
        final_control_state=initial_final_control,
        va_tracker=va_tracker.current(),
    )
    session.control_tokens = tokenizer.encode_all(
        session.analysis,
        session.harmony,
        session.current_chord(),
        session.structured_user_state,
        session.user_profile,
        session.scene_state,
        session.selected_policy,
        session.final_control_state,
    )
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
                session.control_tokens = tokenizer.encode_all(
                    session.analysis,
                    session.harmony,
                    chord_symbol,
                    session.structured_user_state,
                    session.user_profile,
                    session.scene_state,
                    session.selected_policy,
                    session.final_control_state,
                )
                skeleton = generate_skeleton_bar(
                    session.harmony,
                    session.control,
                    session.analysis.va,
                    chord_symbol,
                    session.previous_skeleton,
                    session.bar_index,
                    session.phrase_motif,
                )
                if session.bar_index % session.phrase_length == 0:
                    session.phrase_motif = skeleton
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
                evaluation = evaluate_bar(
                    harmony=session.harmony,
                    control=session.control,
                    chord_symbol=chord_symbol,
                    skeleton=skeleton,
                    melody=notes,
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
                    "raw_user_state": asdict(session.raw_user_state) if session.raw_user_state else None,
                    "structured_user_state": asdict(session.structured_user_state) if session.structured_user_state else None,
                    "user_profile": asdict(session.user_profile),
                    "scene_state": asdict(session.scene_state),
                    "selected_policy": asdict(session.selected_policy) if session.selected_policy else None,
                    "final_control_state": asdict(session.final_control_state) if session.final_control_state else None,
                    "emotion": emotion_payload(session.analysis),
                    "music_features": music_feature_payload(session.analysis),
                    "evaluation": evaluation,
                    "skeleton": [asdict(note) for note in skeleton],
                    "events": [asdict(event) for event in events],
                    "notes": [asdict(note) for note in notes],
                }
                generation_logger.write_bar(
                    {
                        "bar_index": payload["bar_index"],
                        "source": session.last_source,
                        "va": payload["va"],
                        "va_tracker": payload["va_tracker"],
                        "raw_user_state": payload["raw_user_state"],
                        "structured_user_state": payload["structured_user_state"],
                        "user_profile": payload["user_profile"],
                        "scene_state": payload["scene_state"],
                        "selected_policy": payload["selected_policy"],
                        "final_control_state": payload["final_control_state"],
                        "music_features": payload["music_features"],
                        "control_tokens": payload["control_tokens"],
                        "harmony": payload["harmony"],
                        "evaluation": evaluation,
                        "skeleton": payload["skeleton"],
                        "events": payload["events"],
                    }
                )
                session.bar_index += 1

            await websocket.send_json(payload)
            next_wakeup += seconds_per_beat * 4
            await asyncio.sleep(max(0.0, next_wakeup - time.monotonic()))

    async def receive_loop() -> None:
        nonlocal session
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type", "mood")
            if message_type == "scene_update":
                async with update_lock:
                    session.scene_state = scene_from_id(message.get("scene_id"))
                    if session.structured_user_state:
                        session.selected_policy = policy_recommender.recommend(
                            session.structured_user_state,
                            session.user_profile,
                            session.scene_state,
                        )
                        session.final_control_state = control_fusion.fuse(
                            session.analysis,
                            session.structured_user_state,
                            session.user_profile,
                            session.scene_state,
                            session.selected_policy,
                        )
                        session.analysis = AnalysisState(
                            va=session.structured_user_state.va,
                            music=session.final_control_state.to_music_parameters(),
                        )
                        session.control = session.final_control_state.to_melody_control()
                        session.harmony_dirty = True
                await websocket.send_json(
                    {
                        "type": "scene_ack",
                        "scene_state": asdict(session.scene_state),
                        "selected_policy": asdict(session.selected_policy) if session.selected_policy else None,
                        "final_control_state": asdict(session.final_control_state)
                        if session.final_control_state
                        else None,
                    }
                )
                continue

            if message_type == "feedback":
                async with update_lock:
                    session.user_profile = profile_manager.apply_feedback(
                        message.get("feedback_type", "like"),
                        session.final_control_state,
                        liked=message.get("like"),
                    )
                    if session.structured_user_state and session.selected_policy:
                        session.selected_policy = policy_recommender.recommend(
                            session.structured_user_state,
                            session.user_profile,
                            session.scene_state,
                        )
                        session.final_control_state = control_fusion.fuse(
                            session.analysis,
                            session.structured_user_state,
                            session.user_profile,
                            session.scene_state,
                            session.selected_policy,
                        )
                        session.analysis = AnalysisState(
                            va=session.structured_user_state.va,
                            music=session.final_control_state.to_music_parameters(),
                        )
                        session.control = session.final_control_state.to_melody_control()
                await websocket.send_json(
                    {
                        "type": "feedback_ack",
                        "user_profile": asdict(session.user_profile),
                        "selected_policy": asdict(session.selected_policy) if session.selected_policy else None,
                        "final_control_state": asdict(session.final_control_state)
                        if session.final_control_state
                        else None,
                    }
                )
                continue

            mood = message.get("mood", "")
            raw_analysis, source = await asyncio.to_thread(processor.process_safe, mood)
            confidence = confidence_from_text(mood)
            async with update_lock:
                tracked_va = va_tracker.update(raw_analysis.va, confidence=confidence)
                raw_user_state = parse_dialogue_state(mood, raw_analysis.va, confidence)
                structured_user_state = user_state_tracker.update(raw_user_state, tracked_va)
                profile = profile_manager.absorb_dialogue_preferences(raw_user_state)
                base_analysis = processor.analysis_from_va(structured_user_state.va, mood)
                policy = policy_recommender.recommend(structured_user_state, profile, session.scene_state)
                final_control = control_fusion.fuse(
                    base_analysis,
                    structured_user_state,
                    profile,
                    session.scene_state,
                    policy,
                )
                next_analysis = AnalysisState(
                    va=structured_user_state.va,
                    music=final_control.to_music_parameters(),
                )
                session.analysis = next_analysis
                session.control = final_control.to_melody_control()
                session.raw_user_state = raw_user_state
                session.structured_user_state = structured_user_state
                session.user_profile = profile
                session.selected_policy = policy
                session.final_control_state = final_control
                session.va_tracker = tracked_va
                session.control_tokens = tokenizer.encode_all(
                    session.analysis,
                    session.harmony,
                    session.current_chord(),
                    session.structured_user_state,
                    session.user_profile,
                    session.scene_state,
                    session.selected_policy,
                    session.final_control_state,
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
                    "raw_user_state": asdict(raw_user_state),
                    "structured_user_state": asdict(structured_user_state),
                    "user_profile": asdict(session.user_profile),
                    "scene_state": asdict(session.scene_state),
                    "selected_policy": asdict(policy),
                    "final_control_state": asdict(final_control),
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
