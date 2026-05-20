from __future__ import annotations

import math

import torch
from torch import nn


class CausalMusicTransformer(nn.Module):
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 3,
        dim_feedforward: int = 512,
        max_length: int = 256,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.max_length = max_length
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.position_embedding = nn.Embedding(max_length, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.transformer = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.norm = nn.LayerNorm(d_model)
        self.output = nn.Linear(d_model, vocab_size)

    def forward(self, input_ids: torch.Tensor, pad_id: int) -> torch.Tensor:
        batch_size, seq_len = input_ids.shape
        if seq_len > self.max_length:
            raise ValueError(f"sequence length {seq_len} exceeds max_length {self.max_length}")

        positions = torch.arange(seq_len, device=input_ids.device).unsqueeze(0).expand(batch_size, seq_len)
        hidden = self.token_embedding(input_ids) + self.position_embedding(positions)
        hidden = hidden * math.sqrt(hidden.shape[-1])

        causal_mask = torch.triu(
            torch.full((seq_len, seq_len), float("-inf"), device=input_ids.device),
            diagonal=1,
        )
        padding_mask = input_ids.eq(pad_id)
        hidden = self.transformer(hidden, mask=causal_mask, src_key_padding_mask=padding_mask)
        return self.output(self.norm(hidden))
