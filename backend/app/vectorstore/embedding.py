from __future__ import annotations

import importlib
import logging
from functools import cached_property
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import numpy.typing as npt
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings, Space

logger = logging.getLogger(__name__)

# Multilingual replacement for chromadb's DefaultEmbeddingFunction
# (English-only all-MiniLM-L6-v2). Built on onnxruntime + tokenizers
# directly, not sentence-transformers/torch, to avoid a heavy new dependency.
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Pinned to a specific commit so the served model can't silently drift.
_MODEL_REPO = "Xenova/paraphrase-multilingual-MiniLM-L12-v2"
_MODEL_REVISION = "2c4055b12046f11709e9df2c122e59ffbdc2f900"
_MODEL_BASE_URL = f"https://huggingface.co/{_MODEL_REPO}/resolve/{_MODEL_REVISION}"

# Per this model's sentence_bert_config.json; not the same as
# all-MiniLM-L6-v2's 256.
MAX_SEQ_LENGTH = 128

DOWNLOAD_PATH = Path.home() / ".cache" / "chroma" / "onnx_models" / MODEL_NAME
_MODEL_FILES = {
    "tokenizer.json": f"{_MODEL_BASE_URL}/tokenizer.json",
    "model.onnx": f"{_MODEL_BASE_URL}/onnx/model_quantized.onnx",
}


class MultilingualEmbeddingFunction(EmbeddingFunction[Documents]):
    """Local, offline embedding function for MODEL_NAME -- mean-pooled,
    L2-normalized sentence embeddings, same shape as ONNXMiniLM_L6_V2."""

    def __init__(self) -> None:
        try:
            self.ort = importlib.import_module("onnxruntime")
        except ImportError as exc:
            raise ValueError(
                "The onnxruntime python package is not installed. Please "
                "install it with `pip install onnxruntime`"
            ) from exc
        try:
            self.Tokenizer = importlib.import_module("tokenizers").Tokenizer
        except ImportError as exc:
            raise ValueError(
                "The tokenizers python package is not installed. Please "
                "install it with `pip install tokenizers`"
            ) from exc

    def _download_model_if_not_exists(self) -> None:
        DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)
        for filename, url in _MODEL_FILES.items():
            dest = DOWNLOAD_PATH / filename
            if dest.exists():
                continue
            logger.info("Downloading embedding model file %s from %s", filename, url)
            tmp_dest = dest.with_name(dest.name + ".part")
            with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as resp:
                resp.raise_for_status()
                with open(tmp_dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                        f.write(chunk)
            tmp_dest.rename(dest)

    @cached_property
    def tokenizer(self) -> Any:
        self._download_model_if_not_exists()
        tok = self.Tokenizer.from_file(str(DOWNLOAD_PATH / "tokenizer.json"))
        tok.enable_truncation(max_length=MAX_SEQ_LENGTH)
        tok.enable_padding(pad_id=0, pad_token="[PAD]", length=MAX_SEQ_LENGTH)
        return tok

    @cached_property
    def model(self) -> Any:
        self._download_model_if_not_exists()
        so = self.ort.SessionOptions()
        so.log_severity_level = 3
        so.graph_optimization_level = self.ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        preferred_providers = [
            p
            for p in self.ort.get_available_providers()
            if p != "CoreMLExecutionProvider"  # slower than CPU here
        ]
        return self.ort.InferenceSession(
            str(DOWNLOAD_PATH / "model.onnx"),
            providers=preferred_providers,
            sess_options=so,
        )

    def _forward(
        self, documents: list[str], batch_size: int = 32
    ) -> npt.NDArray[np.float32]:
        all_embeddings = []
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            encoded = [self.tokenizer.encode(d) for d in batch]
            input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
            attention_mask = np.array(
                [e.attention_mask for e in encoded], dtype=np.int64
            )
            token_type_ids = np.zeros_like(input_ids)

            model_output = self.model.run(
                None,
                {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                    "token_type_ids": token_type_ids,
                },
            )
            last_hidden_state = model_output[0]

            mask = np.broadcast_to(
                np.expand_dims(attention_mask, -1), last_hidden_state.shape
            )
            summed = np.sum(last_hidden_state * mask, axis=1)
            counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
            pooled = summed / counts

            norm = np.linalg.norm(pooled, axis=1)
            norm[norm == 0] = 1e-12
            all_embeddings.append((pooled / norm[:, np.newaxis]).astype(np.float32))

        return np.concatenate(all_embeddings)

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = self._forward(list(input))
        return cast(
            Embeddings,
            [np.array(embedding, dtype=np.float32) for embedding in embeddings],
        )

    @staticmethod
    def name() -> str:
        return MODEL_NAME

    def default_space(self) -> Space:
        return "cosine"

    def supported_spaces(self) -> list[Space]:
        return ["cosine", "l2", "ip"]

    def max_tokens(self) -> int:
        return MAX_SEQ_LENGTH

    def get_config(self) -> dict[str, Any]:
        return {}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> MultilingualEmbeddingFunction:
        return MultilingualEmbeddingFunction()

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        return
