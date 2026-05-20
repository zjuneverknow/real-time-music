from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

try:
    from .model import CausalMusicTransformer
    from .symbolic_tokenizer import Vocabulary
except ImportError:
    from training.model import CausalMusicTransformer
    from training.symbolic_tokenizer import Vocabulary


DEFAULT_DATASET = Path("backend/training/data/rule_distilled_dataset.jsonl")
DEFAULT_VOCAB = Path("backend/training/data/vocab.json")
DEFAULT_OUT = Path("backend/model/transformer/rule_distilled_music_transformer.pt")


class TokenDataset(Dataset):
    def __init__(self, rows: list[list[int]], max_length: int) -> None:
        self.rows = [row[:max_length] for row in rows if len(row) >= 3]
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> list[int]:
        return self.rows[index]


def load_rows(dataset_path: Path, vocab: Vocabulary) -> list[list[int]]:
    rows: list[list[int]] = []
    with dataset_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            rows.append(vocab.encode(record["tokens"]))
    return rows


def collate_batch(batch: list[list[int]], pad_id: int) -> tuple[torch.Tensor, torch.Tensor]:
    max_len = max(len(row) for row in batch)
    input_ids = torch.full((len(batch), max_len - 1), pad_id, dtype=torch.long)
    labels = torch.full((len(batch), max_len - 1), -100, dtype=torch.long)
    for index, row in enumerate(batch):
        source = row[:-1]
        target = row[1:]
        input_ids[index, : len(source)] = torch.tensor(source, dtype=torch.long)
        labels[index, : len(target)] = torch.tensor(target, dtype=torch.long)
    return input_ids, labels


def split_rows(rows: list[list[int]], validation_ratio: float) -> tuple[list[list[int]], list[list[int]]]:
    shuffled = rows[:]
    random.shuffle(shuffled)
    validation_count = max(1, int(len(shuffled) * validation_ratio))
    return shuffled[validation_count:], shuffled[:validation_count]


def run_epoch(
    model: CausalMusicTransformer,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer | None,
    pad_id: int,
    device: torch.device,
) -> float:
    training = optimizer is not None
    model.train(training)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)
    total_loss = 0.0
    total_batches = 0
    for input_ids, labels in loader:
        input_ids = input_ids.to(device)
        labels = labels.to(device)
        logits = model(input_ids, pad_id=pad_id)
        loss = criterion(logits.reshape(-1, logits.shape[-1]), labels.reshape(-1))
        if training:
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        total_loss += float(loss.detach().cpu())
        total_batches += 1
    return total_loss / max(total_batches, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a small decoder-only symbolic music Transformer.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--epochs", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=192)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--layers", type=int, default=3)
    parser.add_argument("--heads", type=int, default=4)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    vocab = Vocabulary.load(args.vocab)
    rows = load_rows(args.dataset, vocab)
    train_rows, validation_rows = split_rows(rows, validation_ratio=0.1)
    train_dataset = TokenDataset(train_rows, args.max_length)
    validation_dataset = TokenDataset(validation_rows, args.max_length)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate_batch(batch, vocab.pad_id),
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=lambda batch: collate_batch(batch, vocab.pad_id),
    )
    device = torch.device(args.device)
    model = CausalMusicTransformer(
        vocab_size=len(vocab.token_to_id),
        d_model=args.d_model,
        nhead=args.heads,
        num_layers=args.layers,
        max_length=args.max_length,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    for epoch in range(1, args.epochs + 1):
        train_loss = run_epoch(model, train_loader, optimizer, vocab.pad_id, device)
        with torch.no_grad():
            validation_loss = run_epoch(model, validation_loader, None, vocab.pad_id, device)
        print(f"epoch={epoch} train_loss={train_loss:.4f} val_loss={validation_loss:.4f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "config": {
                "vocab_size": len(vocab.token_to_id),
                "d_model": args.d_model,
                "nhead": args.heads,
                "num_layers": args.layers,
                "max_length": args.max_length,
            },
        },
        args.out,
    )
    print(f"saved checkpoint to {args.out}")


if __name__ == "__main__":
    main()
