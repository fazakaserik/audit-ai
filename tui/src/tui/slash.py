"""Slash-command parsing for the chat screen."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from uuid import UUID


class SlashAction(Enum):
    QUIT = auto()
    HELP = auto()
    NEW_SESSION = auto()
    ENGAGEMENT = auto()
    SESSIONS = auto()
    RESUME_PICKER = auto()
    RESUME_ID = auto()
    DOCUMENTS = auto()
    UPLOADS_PICKER = auto()
    UPLOADS_ID = auto()
    UPLOAD = auto()
    OPEN = auto()
    UNKNOWN = auto()
    USAGE = auto()


HELP_TEXT = """Slash commands:
  /engagement     Switch engagement (clears session)
  /new            Start a new session on the next question
  /sessions       Return to the session list
  /resume [id]    Resume a session (picker if no id)
  /documents [folder]  Browse documents (optional start folder)
  /uploads [id]   List uploads or show one upload's details
  /upload <path> <folder>  Upload to the active engagement under <folder>
  /open <n>       Open citation [n] from the last answer
  /help           Show this help
  /quit           Exit
"""


@dataclass(frozen=True)
class SlashCommand:
    action: SlashAction
    arg: str | None = None
    path: str | None = None
    folder: str | None = None
    marker: int | None = None
    session_id: UUID | None = None
    upload_id: UUID | None = None
    message: str | None = None


def parse_slash(line: str) -> SlashCommand:
    parts = line.split()
    if not parts:
        return SlashCommand(action=SlashAction.UNKNOWN, message="Empty command")
    command = parts[0].lower()
    args = parts[1:]
    remainder = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) == 2 else ""

    match command:
        case "/quit" | "/exit":
            return SlashCommand(action=SlashAction.QUIT)
        case "/help":
            return SlashCommand(action=SlashAction.HELP)
        case "/new":
            return SlashCommand(action=SlashAction.NEW_SESSION)
        case "/engagement":
            return SlashCommand(action=SlashAction.ENGAGEMENT)
        case "/sessions":
            return SlashCommand(action=SlashAction.SESSIONS)
        case "/resume":
            if len(args) == 0:
                return SlashCommand(action=SlashAction.RESUME_PICKER)
            if len(args) == 1:
                try:
                    return SlashCommand(action=SlashAction.RESUME_ID, session_id=UUID(args[0]))
                except ValueError:
                    return SlashCommand(
                        action=SlashAction.USAGE,
                        message="Invalid session id.",
                    )
            return SlashCommand(action=SlashAction.USAGE, message="Usage: /resume [session_id]")
        case "/documents":
            folder = remainder.strip().strip("\"'")
            return SlashCommand(action=SlashAction.DOCUMENTS, folder=folder or None)
        case "/uploads":
            if len(args) == 0:
                return SlashCommand(action=SlashAction.UPLOADS_PICKER)
            if len(args) == 1:
                try:
                    return SlashCommand(action=SlashAction.UPLOADS_ID, upload_id=UUID(args[0]))
                except ValueError:
                    return SlashCommand(
                        action=SlashAction.USAGE,
                        message="Invalid upload id.",
                    )
            return SlashCommand(action=SlashAction.USAGE, message="Usage: /uploads [upload_id]")
        case "/upload":
            upload_parts = remainder.rsplit(maxsplit=1)
            if len(upload_parts) != 2 or not upload_parts[0] or not upload_parts[1]:
                return SlashCommand(
                    action=SlashAction.USAGE,
                    message="Usage: /upload <path> <folder>",
                )
            return SlashCommand(
                action=SlashAction.UPLOAD,
                path=upload_parts[0],
                folder=upload_parts[1],
            )
        case "/open":
            if len(args) != 1 or not args[0].isdigit():
                return SlashCommand(
                    action=SlashAction.USAGE,
                    message="Usage: /open <citation marker n>",
                )
            return SlashCommand(action=SlashAction.OPEN, marker=int(args[0]))
        case _:
            return SlashCommand(
                action=SlashAction.UNKNOWN,
                message=f"Unknown command: {command}. Type /help.",
            )
