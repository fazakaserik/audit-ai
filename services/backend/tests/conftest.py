"""Backend test path bootstrap."""

from __future__ import annotations

from backend.native_wheel_compat import ensure_native_wheel_shims

# Support helpers are imported as ``support.*`` (this directory is on pythonpath).
ensure_native_wheel_shims()
