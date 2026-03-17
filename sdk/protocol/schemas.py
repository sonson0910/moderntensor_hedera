"""
Pydantic Validation Schemas for Miner I/O

Provides type-safe validation for task inputs and miner outputs.
Used by the orchestrator to validate data before/after miner calls.

Usage:
    from sdk.protocol.schemas import TaskInput, MinerOutput, CodeReviewInput

    task = TaskInput(task_type="code_review", payload={"code": "..."})
    output = MinerOutput.model_validate(miner_response)
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────
# Task Input Models
# ──────────────────────────────────────────────────────────────


class TaskInput(BaseModel):
    """Generic task input wrapper."""

    task_type: str = Field(..., min_length=1, description="Type of task: code_review, sentiment_analysis, etc.")
    payload: dict = Field(default_factory=dict, description="Task-specific payload data")
    subnet_id: int = Field(default=0, ge=0, description="Target subnet ID")

    @field_validator("task_type")
    @classmethod
    def validate_task_type(cls, v: str) -> str:
        allowed = {"code_review", "sentiment_analysis", "text_generation", "general"}
        if v not in allowed:
            raise ValueError(f"task_type must be one of {allowed}, got '{v}'")
        return v


class CodeReviewInput(BaseModel):
    """Payload schema for code_review tasks."""

    code: str = Field(..., min_length=1, description="Source code to review")
    language: str = Field(default="python", description="Programming language")
    context: str = Field(default="", description="Additional context for review")


class SentimentInput(BaseModel):
    """Payload schema for sentiment_analysis tasks."""

    text: str = Field(..., min_length=1, description="Text to analyze")
    language: str = Field(default="en", description="Text language code")


class TextGenerationInput(BaseModel):
    """Payload schema for text_generation tasks."""

    prompt: str = Field(..., min_length=1, description="Generation prompt")
    max_tokens: int = Field(default=512, ge=1, le=4096, description="Max tokens to generate")


# ──────────────────────────────────────────────────────────────
# Miner Output Models
# ──────────────────────────────────────────────────────────────


class MinerOutput(BaseModel):
    """Generic miner output — all miners must produce this shape."""

    analysis: str = Field(default="", description="Textual analysis / result")
    findings: list[dict] = Field(default_factory=list, description="Structured findings list")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall quality score")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Result confidence")


class SentimentOutput(BaseModel):
    """Output schema for sentiment_analysis tasks."""

    sentiment: Literal["positive", "negative", "neutral"] = Field(
        ..., description="Detected sentiment"
    )
    score: float = Field(..., ge=0.0, le=1.0, description="Sentiment strength")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Result confidence")


class CodeReviewOutput(BaseModel):
    """Output schema for code_review tasks."""

    analysis: str = Field(default="", description="Code review analysis")
    findings: list[dict] = Field(default_factory=list, description="Code issues found")
    score: float = Field(default=0.0, ge=0.0, le=1.0, description="Code quality score")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Review confidence")


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "code_review": CodeReviewInput,
    "sentiment_analysis": SentimentInput,
    "text_generation": TextGenerationInput,
}


def get_input_schema(task_type: str) -> type[BaseModel] | None:
    """Get the specific input schema for a task type, or None for generic."""
    return _INPUT_SCHEMAS.get(task_type)


def validate_task_input(task_type: str, payload: dict) -> BaseModel | None:
    """
    Validate payload against the task-type-specific schema.

    Returns the validated model, or None if no specific schema exists.
    Raises pydantic.ValidationError on invalid data.
    """
    schema = get_input_schema(task_type)
    if schema is None:
        return None
    return schema.model_validate(payload)


def validate_miner_output(result: dict) -> MinerOutput:
    """
    Validate miner output against MinerOutput schema.

    Raises pydantic.ValidationError on invalid data.
    """
    return MinerOutput.model_validate(result)
