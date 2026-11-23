"""Return the current wall-clock time in the host timezone."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.application.dto import ToolSpec
from backend.application.tools.base import ToolContext, ToolResult, tool_spec_from_model

_CFG = ConfigDict(frozen=True, strict=True, extra="forbid")


class GetCurrentTimeArgs(BaseModel):
    model_config = _CFG


class GetCurrentTimeTool:
    name = "get_current_time"
    description = (
        "Return the current date and time in the host machine's local timezone, "
        "including the timezone name/offset. Use when the question depends on "
        "'now', today, deadlines, or relative dates."
    )
    args_model = GetCurrentTimeArgs

    def spec(self) -> ToolSpec:
        return tool_spec_from_model(
            name=self.name,
            description=self.description,
            args_model=self.args_model,
        )

    async def run(self, ctx: ToolContext, args: BaseModel) -> ToolResult:
        if not isinstance(args, GetCurrentTimeArgs):
            msg = "invalid args for get_current_time"
            raise TypeError(msg)
        now = datetime.now().astimezone()
        tz = now.tzinfo
        tz_name = tz.tzname(now) if tz is not None else "unknown"
        offset = now.strftime("%z")
        offset_fmt = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
        iso = now.isoformat(timespec="seconds")
        content = (
            f"current_time={iso}\n"
            f"timezone={tz_name} (UTC{offset_fmt})\n"
            f"weekday={now.strftime('%A')}"
        )
        summary = f"get_current_time → {iso} ({tz_name})"
        return ToolResult(content=content, summary=summary)
