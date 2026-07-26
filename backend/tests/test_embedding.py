from __future__ import annotations

import numpy as np
import pytest
from backend.app.vectorstore.embedding import (
    MAX_SEQ_LENGTH,
    MultilingualEmbeddingFunction,
)

# A paraphrase pair should score higher than an unrelated pair.
_KOREAN_SIMILAR = (
    "고양이가 매트 위에 앉아 있다.",
    "매트 위에 고양이 한 마리가 앉아있다.",
)
_KOREAN_DISSIMILAR = "오늘 주식 시장이 큰 폭으로 하락했다."

_ENGLISH_SIMILAR = (
    "The cat sat on the mat.",
    "A cat is sitting on a mat.",
)
_ENGLISH_DISSIMILAR = "Stock markets fell sharply today."


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@pytest.fixture(scope="module")
def embedding_function() -> MultilingualEmbeddingFunction:
    return MultilingualEmbeddingFunction()


def test_call_returns_vectors_of_expected_dimension(embedding_function):
    vectors = embedding_function(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384


def test_korean_similar_pair_scores_higher_than_dissimilar_pair(embedding_function):
    sim_a, sim_b = _KOREAN_SIMILAR
    vec_sim_a, vec_sim_b, vec_dissim = embedding_function(
        [sim_a, sim_b, _KOREAN_DISSIMILAR]
    )
    similar_score = _cosine(vec_sim_a, vec_sim_b)
    dissimilar_score = _cosine(vec_sim_a, vec_dissim)
    assert similar_score > dissimilar_score


def test_english_similar_pair_scores_higher_than_dissimilar_pair(embedding_function):
    sim_a, sim_b = _ENGLISH_SIMILAR
    vec_sim_a, vec_sim_b, vec_dissim = embedding_function(
        [sim_a, sim_b, _ENGLISH_DISSIMILAR]
    )
    similar_score = _cosine(vec_sim_a, vec_sim_b)
    dissimilar_score = _cosine(vec_sim_a, vec_dissim)
    assert similar_score > dissimilar_score


def test_name_and_max_tokens(embedding_function):
    assert embedding_function.name() == "paraphrase-multilingual-MiniLM-L12-v2"
    assert embedding_function.max_tokens() == MAX_SEQ_LENGTH
