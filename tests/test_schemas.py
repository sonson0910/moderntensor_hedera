"""
Tests for sdk/protocol/schemas.py — Pydantic validation schemas
"""

import pytest
from pydantic import ValidationError
from sdk.protocol.schemas import (
    TaskInput,
    CodeReviewInput,
    SentimentInput,
    TextGenerationInput,
    MinerOutput,
    SentimentOutput,
    validate_task_input,
    validate_miner_output,
)


# ──────────────────────────────────────────────────────────────
# TaskInput Tests
# ──────────────────────────────────────────────────────────────


def test_task_input_valid():
    t = TaskInput(task_type="code_review", payload={"code": "print('hi')"})
    assert t.task_type == "code_review"
    assert t.subnet_id == 0


def test_task_input_invalid_type():
    with pytest.raises(ValidationError):
        TaskInput(task_type="unknown_type", payload={})


def test_task_input_empty_type():
    with pytest.raises(ValidationError):
        TaskInput(task_type="", payload={})


# ──────────────────────────────────────────────────────────────
# CodeReviewInput Tests
# ──────────────────────────────────────────────────────────────


def test_code_review_input_valid():
    cr = CodeReviewInput(code="def foo(): pass")
    assert cr.language == "python"


def test_code_review_input_empty_code():
    with pytest.raises(ValidationError):
        CodeReviewInput(code="")


# ──────────────────────────────────────────────────────────────
# SentimentInput Tests
# ──────────────────────────────────────────────────────────────


def test_sentiment_input_valid():
    s = SentimentInput(text="I love this product")
    assert s.language == "en"


def test_sentiment_input_empty():
    with pytest.raises(ValidationError):
        SentimentInput(text="")


# ──────────────────────────────────────────────────────────────
# MinerOutput Tests
# ──────────────────────────────────────────────────────────────


def test_miner_output_valid():
    out = MinerOutput(analysis="looks good", score=0.8, confidence=0.9)
    assert out.score == 0.8


def test_miner_output_score_out_of_range():
    with pytest.raises(ValidationError):
        MinerOutput(score=1.5)


def test_miner_output_defaults():
    out = MinerOutput()
    assert out.score == 0.0
    assert out.confidence == 0.5


# ──────────────────────────────────────────────────────────────
# SentimentOutput Tests
# ──────────────────────────────────────────────────────────────


def test_sentiment_output_valid():
    s = SentimentOutput(sentiment="positive", score=0.95)
    assert s.sentiment == "positive"


def test_sentiment_output_invalid_sentiment():
    with pytest.raises(ValidationError):
        SentimentOutput(sentiment="angry", score=0.5)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def test_validate_task_input_known_type():
    result = validate_task_input("code_review", {"code": "x = 1"})
    assert result is not None
    assert isinstance(result, CodeReviewInput)


def test_validate_task_input_unknown_type():
    result = validate_task_input("general", {"any": "data"})
    assert result is None


def test_validate_miner_output_valid():
    out = validate_miner_output({"analysis": "ok", "score": 0.7, "confidence": 0.8})
    assert out.score == 0.7


def test_validate_miner_output_invalid():
    with pytest.raises(ValidationError):
        validate_miner_output({"score": 2.0})
