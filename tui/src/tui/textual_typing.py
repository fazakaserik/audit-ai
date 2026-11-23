"""Small typing helpers for Textual APIs with incomplete stubs."""

from __future__ import annotations

from typing import Protocol, cast

from textual.screen import Screen
from textual.worker import Worker, WorkerState


class WorkerStateChangedEvent(Protocol):
    state: WorkerState

    @property
    def worker(self) -> Worker[object]: ...


def worker_from_event(event: Worker.StateChanged) -> Worker[object]:
    return cast(WorkerStateChangedEvent, event).worker


class ScreenSwitcher(Protocol):
    def switch_screen(self, screen: Screen[None]) -> None: ...


def switch_screen(switcher: object, screen: Screen[None]) -> None:
    cast(ScreenSwitcher, switcher).switch_screen(screen)
