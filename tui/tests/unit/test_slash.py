"""Unit tests for slash command parsing."""

from __future__ import annotations

from uuid import uuid4

from tui.slash import SlashAction, parse_slash


def test_parse_help_and_quit() -> None:
    assert parse_slash("/help").action is SlashAction.HELP
    assert parse_slash("/quit").action is SlashAction.QUIT
    assert parse_slash("/exit").action is SlashAction.QUIT


def test_parse_resume_id() -> None:
    session_id = uuid4()
    cmd = parse_slash(f"/resume {session_id}")
    assert cmd.action is SlashAction.RESUME_ID
    assert cmd.session_id == session_id


def test_parse_upload() -> None:
    cmd = parse_slash('/upload "C:/docs/a" finance')
    assert cmd.action is SlashAction.UPLOAD
    assert cmd.path == '"C:/docs/a"'
    assert cmd.folder == "finance"


def test_parse_upload_path_only() -> None:
    cmd = parse_slash("/upload ./docs/policies")
    assert cmd.action is SlashAction.UPLOAD
    assert cmd.path == "./docs/policies"
    assert cmd.folder is None


def test_parse_upload_requires_path() -> None:
    cmd = parse_slash("/upload")
    assert cmd.action is SlashAction.USAGE


def test_parse_unknown() -> None:
    cmd = parse_slash("/nope")
    assert cmd.action is SlashAction.UNKNOWN
    assert cmd.message is not None
