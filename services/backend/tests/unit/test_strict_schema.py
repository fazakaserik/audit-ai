"""OpenAI strict JSON Schema normalization."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.application.agents.research_agent.prompts import AnswerGenerationResult
from backend.infrastructure.llm.strict_schema import openai_strict_json_schema


def test_answer_generation_requires_all_properties() -> None:
    schema = openai_strict_json_schema(AnswerGenerationResult)
    props = schema["properties"]
    assert isinstance(props, dict)
    required = schema["required"]
    assert isinstance(required, list)
    assert set(required) == set(props.keys())
    assert "answer_text" in required
    assert schema["additionalProperties"] is False


def test_nested_defs_are_normalized() -> None:
    class Nested(BaseModel):
        model_config = ConfigDict(extra="forbid")
        note: Annotated[str, Field(max_length=10)] = ""

    class Outer(BaseModel):
        model_config = ConfigDict(extra="forbid")
        item: Nested
        label: str = "x"

    schema = openai_strict_json_schema(Outer)
    assert set(cast_required(schema)) == {"item", "label"}
    defs = schema.get("$defs")
    assert isinstance(defs, dict)
    nested = defs.get("Nested")
    assert isinstance(nested, dict)
    assert set(cast_required(nested)) == {"note"}
    assert nested["additionalProperties"] is False


def cast_required(node: object) -> list[str]:
    assert isinstance(node, dict)
    required = node["required"]
    assert isinstance(required, list)
    return [str(item) for item in required]
