from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

try:
    from ..core import MelodyNote, SkeletonNote
except ImportError:
    from core import MelodyNote, SkeletonNote


SPECIAL_TOKENS = ["<PAD>", "<BOS>", "<EOS>", "<SEP>", "<UNK>"]


def _number_token(prefix: str, value: float) -> str:
    text = f"{value:g}".replace("-", "NEG_").replace(".", "_")
    return f"<{prefix}_{text}>"


def encode_skeleton(skeleton: list[SkeletonNote]) -> list[str]:
    tokens: list[str] = ["<SKELETON>"]
    for note in skeleton:
        tokens.extend(
            [
                _number_token("BEAT", note.start_beats),
                f"<SK_NOTE_{note.midi}>",
                _number_token("DUR", note.duration_beats),
            ]
        )
    return tokens


def encode_melody(melody: list[MelodyNote]) -> list[str]:
    tokens: list[str] = ["<MELODY>"]
    for note in melody:
        velocity_bucket = int(round(note.velocity * 10)) * 10
        tokens.extend(
            [
                _number_token("BEAT", note.start_beats),
                f"<NOTE_{note.midi}>",
                _number_token("DUR", note.duration_beats),
                f"<VEL_{velocity_bucket}>",
            ]
        )
    return tokens


def build_sequence(prefix: list[str], skeleton: list[SkeletonNote], melody: list[MelodyNote]) -> list[str]:
    return ["<BOS>", *prefix, "<SEP>", *encode_skeleton(skeleton), "<SEP>", *encode_melody(melody), "<EOS>"]


@dataclass
class Vocabulary:
    token_to_id: dict[str, int]

    @property
    def id_to_token(self) -> dict[int, str]:
        return {index: token for token, index in self.token_to_id.items()}

    @property
    def pad_id(self) -> int:
        return self.token_to_id["<PAD>"]

    @property
    def unk_id(self) -> int:
        return self.token_to_id["<UNK>"]

    def encode(self, tokens: list[str]) -> list[int]:
        return [self.token_to_id.get(token, self.unk_id) for token in tokens]

    def decode(self, ids: list[int]) -> list[str]:
        id_to_token = self.id_to_token
        return [id_to_token.get(index, "<UNK>") for index in ids]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.token_to_id, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Vocabulary":
        return cls(json.loads(path.read_text(encoding="utf-8")))


def build_vocabulary(sequences: list[list[str]]) -> Vocabulary:
    tokens = set(SPECIAL_TOKENS)
    for sequence in sequences:
        tokens.update(sequence)
    ordered = SPECIAL_TOKENS + sorted(token for token in tokens if token not in SPECIAL_TOKENS)
    return Vocabulary({token: index for index, token in enumerate(ordered)})
