"""Chat screen: transcript + prompt input."""

from __future__ import annotations

from typing import ClassVar, Literal, assert_never, cast
from uuid import UUID

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Input
from textual.worker import Worker, WorkerState

from backend.application.api.contracts.v1.responses import UploadAcceptedResponse
from cli.client import CliApiError
from tui.chat_render import (
    error_panel,
    replay_session_detail,
    speaker_label,
)
from tui.render_text import renderable_to_text
from tui.screens.base import ChromeScreen
from tui.screens.document_view import DocumentViewScreen
from tui.slash import HELP_TEXT, SlashAction, parse_slash
from tui.streaming import ThinkingAppend, ThinkingFinished, ThinkingStarted, run_ask_stream
from tui.textual_typing import worker_from_event
from tui.widgets.chat_input import ChatInput
from tui.widgets.selectable import SelectableStatic
from tui.widgets.thinking import LiveThoughtProcess, make_thinking_collapsible


class ChatScreen(ChromeScreen):
    """Ask questions and view streamed answers."""

    ALLOW_SELECT = True
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "back_sessions", "Sessions"),
        Binding("ctrl+e", "back_engagement", "Engagement"),
        Binding("q", "app.quit", "Quit", show=False),
        Binding("ctrl+c", "copy_text", "Copy", show=False),
    ]

    def action_copy_text(self) -> None:
        selected = self.get_selected_text()
        if selected:
            self.app.copy_to_clipboard(selected)
            self.notify("Copied", timeout=1.5)
            return
        self.app.exit()

    def __init__(self, resume_session_id: UUID | None = None) -> None:
        super().__init__()
        self._resume_session_id = resume_session_id
        self._asking = False
        self._last_speaker: Literal["you", "agent"] | None = None
        self._live_thinking: LiveThoughtProcess | None = None

    def compose_main(self) -> ComposeResult:
        yield VerticalScroll(id="chat-log")
        yield ChatInput(
            placeholder="Ask a question or /help  ·  Esc sessions",
            id="chat-input",
        )

    def on_mount(self) -> None:
        self.aiditor.set_header_compact(True)
        self.aiditor.refresh_status()
        self._clear_chat()
        if self._resume_session_id is not None:
            self._load_session(self._resume_session_id)
        else:
            self._mount_line(Text("New session — ask a question to begin.", style="dim"))
        self.query_one("#chat-input", ChatInput).focus()

    def write_renderable(self, content: object) -> None:
        self._append_content(content)

    def append_speaker(self, role: Literal["you", "agent"]) -> None:
        self._append_speaker(role)

    def mount_line(self, content: RenderableType) -> None:
        self._mount_line(content)

    def mount_thinking(self, *, body: str, duration_seconds: float | None) -> None:
        self._mount_widget(make_thinking_collapsible(body, duration_seconds=duration_seconds))

    def _chat_log(self) -> VerticalScroll:
        return self.query_one("#chat-log", VerticalScroll)

    def _clear_chat(self) -> None:
        self._chat_log().remove_children()
        self._last_speaker = None
        self._live_thinking = None

    def _scroll_end(self) -> None:
        self._chat_log().scroll_end(animate=False)

    def _mount_widget(self, widget: Widget) -> None:
        self._chat_log().mount(widget)
        self._scroll_end()

    def _mount_line(self, content: RenderableType) -> None:
        # Textual selection offsets only attach to Text/Content visuals.
        self._mount_widget(SelectableStatic(renderable_to_text(content), markup=False))

    def _mount_blank(self) -> None:
        self._mount_widget(SelectableStatic(""))

    def _append_speaker(self, role: Literal["you", "agent"]) -> None:
        switched = self._last_speaker is not None and self._last_speaker != role
        leading = self._last_speaker is None and len(self._chat_log().children) > 0
        if switched or leading:
            self._mount_blank()
        self._mount_line(speaker_label(role))
        self._last_speaker = role

    def _ensure_live_thinking(self) -> LiveThoughtProcess:
        live = self._live_thinking
        if live is not None:
            return live
        live = LiveThoughtProcess()
        self._live_thinking = live
        self._mount_widget(live)
        return live

    def _append_content(self, content: object) -> None:
        if isinstance(content, ThinkingStarted):
            live = self._live_thinking
            if live is not None:
                live.reset()
            else:
                self._ensure_live_thinking()
            return
        if isinstance(content, ThinkingAppend):
            self._ensure_live_thinking().append_text(content.text)
            self._scroll_end()
            return
        if isinstance(content, ThinkingFinished):
            live = self._live_thinking
            if live is not None:
                live.finish(duration_seconds=content.duration_seconds)
                self._live_thinking = None
                self._scroll_end()
            return
        if isinstance(content, Widget):
            self._mount_widget(content)
            return
        self._mount_line(cast(RenderableType, content))

    def _load_session(self, session_id: UUID) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            self._mount_line(Text("No engagement selected.", style="red"))
            return
        try:
            detail = self.aiditor.api_client.get_session(engagement_id, session_id)
        except CliApiError as exc:
            self._mount_line(error_panel(exc))
            return
        self.aiditor.state.session_id = detail.id
        self.aiditor.state.session_title = detail.title
        if detail.turns:
            last = detail.turns[-1].answer
            self.aiditor.state.last_answer = last
            self.aiditor.state.last_citations = self.aiditor.state.collect_citations(last)
            self.aiditor.state.apply_usage_from_answer(last)
        else:
            self.aiditor.state.last_answer = None
            self.aiditor.state.last_citations = ()
            self.aiditor.state.clear_usage()
        self.aiditor.refresh_status()
        replay_session_detail(detail, _SessionReplaySink(self))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        line = event.value.strip()
        event.input.value = ""
        if not line or self._asking:
            return
        if line.startswith("/"):
            self._handle_slash(line)
            return
        self._ask(line)

    def _handle_slash(self, line: str) -> None:
        cmd = parse_slash(line)
        action = cmd.action

        if action is SlashAction.QUIT:
            self.aiditor.exit()
            return
        if action is SlashAction.HELP:
            self._mount_line(Text(HELP_TEXT))
            return
        if action is SlashAction.NEW_SESSION:
            self.aiditor.state.clear_session()
            self.aiditor.refresh_status()
            self._mount_line(Text("Next question starts a new session.", style="dim"))
            return
        if action is SlashAction.ENGAGEMENT:
            self.aiditor.open_engagements()
            return
        if action is SlashAction.SESSIONS or action is SlashAction.RESUME_PICKER:
            self.aiditor.open_sessions()
            return
        if action is SlashAction.RESUME_ID:
            assert cmd.session_id is not None
            self.aiditor.resume_session(cmd.session_id)
            return
        if action is SlashAction.DOCUMENTS:
            self.aiditor.show_documents_modal(start_folder=cmd.folder or "")
            return
        if action is SlashAction.UPLOADS_PICKER:
            self.aiditor.show_uploads_modal()
            return
        if action is SlashAction.UPLOADS_ID:
            self.aiditor.show_uploads_modal(upload_id=cmd.upload_id)
            return
        if action is SlashAction.UPLOAD:
            assert cmd.path is not None
            self._run_upload(cmd.path, cmd.folder)
            return
        if action is SlashAction.OPEN:
            assert cmd.marker is not None
            self._open_citation(cmd.marker)
            return
        if action is SlashAction.USAGE or action is SlashAction.UNKNOWN:
            self._mount_line(Text(cmd.message or "Unknown command.", style="red"))
            return
        assert_never(action)

    def _open_citation(self, marker: int) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            self._mount_line(Text("No engagement selected.", style="red"))
            return
        citation = next(
            (c for c in self.aiditor.state.last_citations if c.marker == marker),
            None,
        )
        if citation is None:
            self._mount_line(Text(f"No citation [{marker}] in the last answer.", style="red"))
            return
        try:
            content = self.aiditor.api_client.get_document_content(
                engagement_id, citation.document_path
            )
        except CliApiError as exc:
            self._mount_line(error_panel(exc))
            return
        self.app.push_screen(DocumentViewScreen(citation.document_path, content))

    def _run_upload(self, raw_path: str, folder: str | None) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            self._mount_line(Text("No engagement selected.", style="red"))
            return
        if folder is None:
            self.aiditor.pick_upload_folder(
                callback=lambda selected: self._on_upload_folder_picked(raw_path, selected),
            )
            return
        self._start_upload(raw_path, folder)

    def _on_upload_folder_picked(self, raw_path: str, folder: str | None) -> None:
        if folder is None:
            return
        self._start_upload(raw_path, folder)

    def _start_upload(self, raw_path: str, folder: str) -> None:
        def work() -> UploadAcceptedResponse:
            return self.aiditor.upload_path(raw_path, folder)

        self.notify(
            f"Sending upload to '{folder}'…",
            title="Upload",
            timeout=2.5,
        )
        # Non-exclusive so chat/ask stays usable; we only wait for API accept, not ingest.
        self.run_worker(work, exclusive=False, thread=True, name="upload")

    def _ask(self, question: str) -> None:
        engagement_id = self.aiditor.state.engagement_id
        if engagement_id is None:
            self._mount_line(Text("No engagement selected.", style="red"))
            return
        self._append_speaker("you")
        self._mount_line(question)
        self._append_speaker("agent")
        state = self.aiditor.state
        client = self.aiditor.api_client

        def work() -> None:
            def write(content: object) -> None:
                self.aiditor.call_from_thread(self._append_content, content)

            try:
                run_ask_stream(
                    client,
                    state,
                    engagement_id=engagement_id,
                    question=question,
                    session_id=state.session_id,
                    write=write,
                )
            except CliApiError as exc:
                write(error_panel(exc))

        self._asking = True
        self.query_one("#chat-input", ChatInput).disabled = True
        self.run_worker(work, exclusive=True, thread=True, name="ask")

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        worker = worker_from_event(event)
        name = cast(str | None, worker.name)
        if name == "upload":
            self._on_upload_worker_done(event, worker)
            return
        if name == "ask":
            self._asking = False
            chat_input = self.query_one("#chat-input", ChatInput)
            chat_input.disabled = False
            chat_input.focus()
            self.aiditor.refresh_status()
            if event.state is WorkerState.ERROR:
                error = worker.error
                if error is not None:
                    if isinstance(error, CliApiError):
                        self._mount_line(error_panel(error))
                    else:
                        self._mount_line(Text(str(error), style="red"))

    def _on_upload_worker_done(
        self,
        event: Worker.StateChanged,
        worker: Worker[object],
    ) -> None:
        if event.state is WorkerState.ERROR:
            error = worker.error
            detail = str(error) if error is not None else "Upload failed"
            if isinstance(error, CliApiError):
                detail = error.detail
            self.notify(detail, title="Upload failed", severity="error", timeout=6)
            return
        if event.state is not WorkerState.SUCCESS:
            return
        accepted = cast(UploadAcceptedResponse | None, worker.result)
        if accepted is None:
            return
        self.notify(
            f"Accepted - processing in the background.\n"
            f"Use /uploads (or /uploads {accepted.upload_id}) to inspect.",
            title="Upload",
            timeout=5,
        )

    def action_back_sessions(self) -> None:
        if self._asking:
            return
        self.aiditor.open_sessions()

    def action_back_engagement(self) -> None:
        if self._asking:
            return
        self.aiditor.open_engagements()


class _SessionReplaySink:
    def __init__(self, screen: ChatScreen) -> None:
        self._screen = screen

    def append_speaker(self, role: Literal["you", "agent"]) -> None:
        self._screen.append_speaker(role)

    def mount_line(self, content: RenderableType) -> None:
        self._screen.mount_line(content)

    def mount_thinking(self, *, body: str, duration_seconds: float | None) -> None:
        self._screen.mount_thinking(body=body, duration_seconds=duration_seconds)
