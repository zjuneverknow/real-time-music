from __future__ import annotations

import argparse
from pathlib import Path

import torch

try:
    from .model import CausalMusicTransformer
    from .symbolic_tokenizer import Vocabulary
except ImportError:
    from training.model import CausalMusicTransformer
    from training.symbolic_tokenizer import Vocabulary


DEFAULT_CHECKPOINT = Path("backend/model/transformer/rule_distilled_music_transformer.pt")
DEFAULT_VOCAB = Path("backend/training/data/vocab.json")


def sample_next(logits: torch.Tensor, temperature: float, top_k: int) -> int:
    logits = logits / max(temperature, 0.05)
    values, indices = torch.topk(logits, min(top_k, logits.shape[-1]))
    probabilities = torch.softmax(values, dim=-1)
    selected = torch.multinomial(probabilities, 1)
    return int(indices[selected].item())


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample tokens from a trained symbolic music Transformer.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
    parser.add_argument("--max-new-tokens", type=int, default=80)
    parser.add_argument("--temperature", type=float, default=0.9)
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument(
        "--prefix",
        nargs="+",
        default=[
            "<BOS>",
            "<VALENCE_HIGH>",
            "<AROUSAL_MID>",
            "<DENSITY_MID>",
            "<MEAN_PITCH_MID>",
            "<VOLATILITY_MID>",
            "<BRIGHTNESS_BRIGHT>",
            "<WETNESS_MED>",
            "<TEMPO_FAST>",
            "<MODE_MAJOR>",
            "<CHORD_I>",
            "<BAR_1>",
            "<SEP>",
        ],
    )
    args = parser.parse_args()

    vocab = Vocabulary.load(args.vocab)
    checkpoint = torch.load(args.checkpoint, map_location=args.device)
    model = CausalMusicTransformer(**checkpoint["config"]).to(args.device)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    ids = vocab.encode(args.prefix)
    eos_id = vocab.token_to_id["<EOS>"]
    with torch.no_grad():
        for _ in range(args.max_new_tokens):
            window = ids[-checkpoint["config"]["max_length"] :]
            input_ids = torch.tensor([window], dtype=torch.long, device=args.device)
            logits = model(input_ids, pad_id=vocab.pad_id)[0, -1]
            next_id = sample_next(logits, args.temperature, args.top_k)
            ids.append(next_id)
            if next_id == eos_id:
                break

    print(" ".join(vocab.decode(ids)))


if __name__ == "__main__":
    main()
