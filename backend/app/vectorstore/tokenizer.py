from __future__ import annotations

import threading
from typing import Any

_tokenizer: Any = None
_init_lock = threading.Lock()


class TokenizerUnavailableError(RuntimeError):
    """Raised when the embedding tokenizer can't be loaded, e.g. because it
    isn't cached locally yet and there's no network access to fetch it.
    Callers don't need to handle this specially: indexer._index_document()'s
    existing catch-all already turns any exception here into a per-document
    indexing failure, so a document simply fails to index rather than being
    indexed with an unverified chunk size."""


def _get_tokenizer() -> Any:
    global _tokenizer
    if _tokenizer is not None:
        return _tokenizer
    with _init_lock:
        if _tokenizer is None:
            try:
                # Reuse the embedding function's own cached model files.
                from .embedding import MultilingualEmbeddingFunction

                ef = MultilingualEmbeddingFunction()
                tok = ef.tokenizer
            except Exception as exc:
                raise TokenizerUnavailableError(
                    f"Could not load the embedding tokenizer: {exc}"
                ) from exc
            # Measure the true token count a chunk would need, not a count
            # clamped/padded to the model's fixed input length.
            tok.no_truncation()
            tok.no_padding()
            _tokenizer = tok
    return _tokenizer


def count_tokens(text: str) -> int:
    """Real token count for `text`, measured with the same tokenizer the
    embedding model uses to embed it."""
    return len(_get_tokenizer().encode(text).ids)


def token_offsets(text: str) -> list[tuple[int, int]]:
    """Per-token (char_start, char_end) offsets into `text`, for mapping a
    token-index window back to a character span."""
    return _get_tokenizer().encode(text).offsets
