"""Minimal stubs for LangGraph graph APIs used by the ask pipeline."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import TypeVar

_StateT = TypeVar("_StateT")
_NodeResult = Mapping[str, object] | _StateT

START: str
END: str

class StateGraph[_StateT]:
    def __init__(self, state_schema: type[_StateT]) -> None: ...
    def add_node(
        self,
        name: str,
        action: Callable[[_StateT], Awaitable[_NodeResult[_StateT]]]
        | Callable[[_StateT], _NodeResult[_StateT]],
    ) -> None: ...
    def add_edge(self, start: str, end: str) -> None: ...
    def add_conditional_edges(
        self,
        source: str,
        path: Callable[[_StateT], str],
        path_map: Mapping[str, str] | None = None,
    ) -> None: ...
    def compile(self) -> CompiledStateGraph[_StateT]: ...

class CompiledStateGraph[_StateT]:
    async def ainvoke(
        self,
        input: _StateT,
        config: object | None = None,
    ) -> _StateT: ...
    def invoke(
        self,
        input: _StateT,
        config: object | None = None,
    ) -> _StateT: ...
