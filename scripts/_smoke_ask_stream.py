"""One-shot smoke: stream ask with CLI render helpers."""

from __future__ import annotations

from rich.console import Console
from rich.status import Status

from backend.api.contracts.v1.responses import AskResponse
from cli.client import AuditApiClient, unwrap_answer
from cli.render import (
    render_ask_response,
    render_progress_sources,
    render_progress_stage,
    render_speaker,
    render_thinking_delta,
    render_thinking_done,
    stage_label,
)
from domain.engagement import EngagementId


def main() -> None:
    console = Console()
    engagement_id = EngagementId("northwind-fy2025")
    question = "Are there any meal limitations?"
    render_speaker(console, "you")
    console.print(question)
    render_speaker(console, "agent")

    thinking_at_line_start = True
    saw_thinking = False
    response: AskResponse | None = None
    status = Status("Thinking…", console=console)
    status.start()
    with AuditApiClient.from_env() as client:
        try:
            for event in client.ask_stream(engagement_id, question=question):
                event_type = event.get("type")
                if event_type == "stage":
                    stage = str(event.get("stage", ""))
                    status.stop()
                    if saw_thinking and not thinking_at_line_start:
                        console.print()
                        thinking_at_line_start = True
                    render_progress_stage(console, stage)
                    if not saw_thinking:
                        status.update(stage_label(stage))
                        status.start()
                elif event_type == "sources":
                    sources = event.get("sources")
                    if isinstance(sources, list):
                        status.stop()
                        render_progress_sources(console, sources)
                        if not saw_thinking:
                            status.start()
                elif event_type == "thinking_delta":
                    text = event.get("text")
                    if isinstance(text, str) and text:
                        if not saw_thinking:
                            status.stop()
                            console.print()
                            saw_thinking = True
                        thinking_at_line_start = render_thinking_delta(
                            console,
                            text,
                            at_line_start=thinking_at_line_start,
                        )
                elif event_type == "thinking_done":
                    status.stop()
                    raw = event.get("duration_seconds", 0)
                    duration = float(raw) if isinstance(raw, (int, float, str)) else 0.0
                    render_thinking_done(console, duration)
                    thinking_at_line_start = True
                elif event_type == "final":
                    status.stop()
                    final = event.get("response")
                    if isinstance(final, AskResponse):
                        response = final
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
