from __future__ import annotations

try:
    from ..core import RawUserState, VAState
except ImportError:
    from core import RawUserState, VAState


def _contains(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def infer_dominant_emotion(va: VAState, text: str) -> str:
    if _contains(text, ["焦虑", "紧张", "慌", "压力", "stress", "anxious"]):
        return "anxious"
    if _contains(text, ["困", "累", "疲惫", "sleepy", "tired"]):
        return "tired"
    if _contains(text, ["开心", "兴奋", "激动", "happy", "excited"]):
        return "positive"
    if va.valence < 0.35 and va.arousal > 0.6:
        return "anxious"
    if va.valence < 0.35:
        return "sad"
    if va.arousal < 0.3:
        return "calm"
    return "neutral"


def parse_dialogue_state(text: str, va: VAState, confidence: float = 0.7) -> RawUserState:
    normalized = (text or "").strip().lower()
    dominant_emotion = infer_dominant_emotion(va, normalized)

    activity = "resting"
    if _contains(normalized, ["代码", "coding", "编程", "开发"]):
        activity = "coding"
    elif _contains(normalized, ["学习", "读书", "论文", "study", "reading"]):
        activity = "studying"
    elif _contains(normalized, ["面试", "interview"]):
        activity = "interview_preparation"
    elif _contains(normalized, ["睡", "sleep", "bed"]):
        activity = "sleeping"
    elif _contains(normalized, ["运动", "跑步", "workout", "exercise"]):
        activity = "exercising"
    elif _contains(normalized, ["聊天", "陪我", "conversation"]):
        activity = "chatting"

    primary_intent = "neutral_background"
    secondary_intent = None
    if _contains(normalized, ["冷静", "平静", "放松", "calm", "relax"]):
        primary_intent = "calm_down"
    if _contains(normalized, ["专注", "集中", "继续", "focus", "study", "工作"]):
        secondary_intent = "stay_focused"
        if primary_intent == "neutral_background":
            primary_intent = "stay_focused"
    if activity == "sleeping":
        primary_intent = "sleep"
    elif _contains(normalized, ["动力", "振作", "motiv", "打起精神"]):
        primary_intent = "motivate"
    elif _contains(normalized, ["表达", "沉浸", "贴合", "matching"]):
        primary_intent = "express_emotion"
    elif _contains(normalized, ["创作", "写作", "设计", "creative"]):
        primary_intent = "creative_flow"

    cognitive_load = "medium"
    attention_need = "medium"
    distraction_tolerance = "medium"
    if activity in {"coding", "studying", "interview_preparation"}:
        cognitive_load = "high"
        attention_need = "high"
        distraction_tolerance = "low"
    elif activity == "sleeping":
        cognitive_load = "low"
        attention_need = "low"
        distraction_tolerance = "very_low"

    music_role = "background_support"
    desired_effect = "stable_background"
    regulation_mode = "emotion_matching"
    target_state = "same_as_current"
    if primary_intent in {"calm_down", "sleep"}:
        music_role = "emotional_regulation"
        regulation_mode = "emotion_regulation"
        target_state = "sleepy_calm" if primary_intent == "sleep" else "calm_focused"
        desired_effect = "reduce_arousal"
    if secondary_intent == "stay_focused" or primary_intent == "stay_focused":
        music_role = "focus_assistance"
        regulation_mode = "emotion_regulation"
        target_state = "calm_focused"
        desired_effect = "reduce_anxiety_without_sleepiness"

    liked_elements = []
    disliked_elements = []
    for element, keywords in {
        "piano": ["钢琴", "piano"],
        "soft_pad": ["pad", "氛围", "铺底"],
        "lofi": ["lofi", "lo-fi"],
        "ambient": ["ambient", "环境"],
    }.items():
        if _contains(normalized, keywords):
            liked_elements.append(element)
    for element, keywords in {
        "heavy_drums": ["鼓太", "鼓点太", "强鼓", "heavy drum", "strong drum"],
        "sharp_synth": ["刺耳", "尖锐", "sharp"],
        "too_sleepy": ["太催眠", "太困"],
        "too_sad": ["太丧", "太悲伤", "too sad"],
        "too_busy": ["太乱", "太复杂", "too busy"],
    }.items():
        if _contains(normalized, keywords):
            disliked_elements.append(element)

    soft_constraints = [f"avoid_{element}" for element in disliked_elements]
    return RawUserState(
        dominant_emotion=dominant_emotion,
        primary_intent=primary_intent,
        secondary_intent=secondary_intent,
        activity=activity,
        cognitive_load=cognitive_load,
        attention_need=attention_need,
        distraction_tolerance=distraction_tolerance,
        music_role=music_role,
        desired_effect=desired_effect,
        liked_elements=liked_elements,
        disliked_elements=disliked_elements,
        soft_constraints=soft_constraints,
        regulation_mode=regulation_mode,
        target_state=target_state,
        confidence=confidence,
    )
