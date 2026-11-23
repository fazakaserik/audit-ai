# Manual smoke only — not part of `just check`.
"""One-shot smoke: stream ask with CLI render helpers."""

from __future__ import annotations

from rich.console import Console
from rich.status import Status
from rich.text import Text

from backend.application.api.contracts.v1.responses import AskResponse
from backend.domain.engagement import EngagementId, validate_engagement_id
from cli.ask_stream import AskStreamHandlers, consume_ask_stream
from cli.client import AuditApiClient, unwrap_answer
from cli.formatting.labels import stage_label
from cli.formatting.tool_progress import ToolProgressCorrelator
from cli.render import (
    render_ask_response,
    render_progress_stage,
    render_speaker,
    render_thinking_delta,
    render_thinking_done,
)


def main() -> None:
    console = Console()
    engagement_id: EngagementId = validate_engagement_id("northwind-fy2025")
    question = "Are there any meal limitations?"
    render_speaker(console, "you")
    console.print(question)
    render_speaker(console, "agent")

    thinking_at_line_start = True
    saw_thinking = False
    response: AskResponse | None = None
    status = Status("Thinking…", console=console)
    status.start()
    tools = ToolProgressCorrelator()

    def on_stage(stage: str) -> None:
        nonlocal thinking_at_line_start
        status.stop()
        if saw_thinking and not thinking_at_line_start:
            console.print()
            thinking_at_line_start = True
        render_progress_stage(console, stage)
        if not saw_thinking:
            status.update(stage_label(stage))
            status.start()

    def on_thinking_delta(text: str) -> None:
        nonlocal thinking_at_line_start, saw_thinking
        if not saw_thinking:
            status.stop()
            console.print()
            saw_thinking = True
        thinking_at_line_start = render_thinking_delta(
            console,
            text,
            at_line_start=thinking_at_line_start,
        )

    def on_thinking_done(duration: float) -> None:
        nonlocal thinking_at_line_start
        status.stop()
        render_thinking_done(console, duration)
        thinking_at_line_start = True

    def on_tool_call(line: str) -> None:
        status.stop()
        console.print(Text(line, style="dim"))

    def on_tool_result_lines(lines: list[str]) -> None:
        status.stop()
        for line in lines:
            console.print(Text(line, style="dim"))

    handlers = AskStreamHandlers(
        on_stage=on_stage,
        on_thinking_delta=on_thinking_delta,
        on_thinking_done=on_thinking_done,
        on_tool_call=on_tool_call,
        on_tool_result_lines=on_tool_result_lines,
    )

    with AuditApiClient.from_env() as client:
        try:
            response = consume_ask_stream(
                client.ask_stream(engagement_id, question=question),
                handlers=handlers,
                tools=tools,
            )
        finally:
            status.stop()

    if response is None:
        raise SystemExit("no final response")
    render_ask_response(console, response)
    answered = unwrap_answer(response)
    if answered is None:
        raise SystemExit(f"unexpected status: {response.status}")
    print("--- smoke ok ---", flush=True)


if __name__ == "__main__":
    main()
