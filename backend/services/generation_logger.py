from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = BASE_DIR / "logs" / "generation_events.jsonl"
GENERATION_LOG_PATH = Path(os.getenv("GENERATION_LOG_PATH", DEFAULT_LOG_PATH)).resolve()
GENERATION_LOG_ENABLED = os.getenv("GENERATION_LOG_ENABLED", "true").lower() != "false"


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


class GenerationLogger:
    def __init__(self, path: Path = GENERATION_LOG_PATH, enabled: bool = GENERATION_LOG_ENABLED) -> None:
        self.path = path
        self.enabled = enabled
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def write_bar(self, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **_json_ready(payload),
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
