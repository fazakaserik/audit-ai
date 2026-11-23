"""Install pure-Python shims when AppLocker/WDAC blocks native wheels.

LangGraph pulls ``xxhash`` and ``ormsgpack``. On some Windows hosts those DLLs
fail to load under Application Control; without shims, importing ``langgraph``
hard-fails before any graph code runs. Linux containers load the real wheels.
"""

from __future__ import annotations

import hashlib
import json
import sys
import types
from collections.abc import Callable


def _module_usable(module_name: str, probe: Callable[[], object]) -> bool:
    try:
        __import__(module_name)
        probe()
    except Exception:
        sys.modules.pop(module_name, None)
        return False
    return True


def _install_xxhash() -> None:
    def probe() -> object:
        from xxhash import xxh3_128_hexdigest

        return xxh3_128_hexdigest

    if _module_usable("xxhash", probe):
        return

    mod = types.ModuleType("xxhash")

    class _Hasher:
        def __init__(self, data: bytes | str | bytearray = b"", seed: int = 0) -> None:
            payload = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
            seed_bytes = int(seed).to_bytes(8, "little", signed=False)
            self._digest = hashlib.sha256(seed_bytes + payload)

        def update(self, data: bytes | str | bytearray) -> None:
            payload = data if isinstance(data, (bytes, bytearray)) else str(data).encode()
            self._digest.update(payload)

        def digest(self) -> bytes:
            return self._digest.digest()[:16]

        def hexdigest(self) -> str:
            return self.digest().hex()

        def intdigest(self) -> int:
            return int.from_bytes(self.digest(), "big")

    def _factory(data: bytes | str | bytearray = b"", seed: int = 0) -> _Hasher:
        return _Hasher(data, seed)

    def _digest(data: bytes | str | bytearray = b"", seed: int = 0) -> bytes:
        return _Hasher(data, seed).digest()

    def _hexdigest(data: bytes | str | bytearray = b"", seed: int = 0) -> str:
        return _Hasher(data, seed).hexdigest()

    def _intdigest(data: bytes | str | bytearray = b"", seed: int = 0) -> int:
        return _Hasher(data, seed).intdigest()

    for name in ("xxh3_128", "xxh3_64", "xxh64", "xxh32"):
        setattr(mod, name, _factory)
        setattr(mod, f"{name}_digest", _digest)
        setattr(mod, f"{name}_hexdigest", _hexdigest)
        setattr(mod, f"{name}_intdigest", _intdigest)

    sys.modules["xxhash"] = mod
    sys.modules["xxhash._xxhash"] = mod


def _install_ormsgpack() -> None:
    def probe() -> object:
        import ormsgpack

        return ormsgpack.packb

    if _module_usable("ormsgpack", probe):
        return

    class _Ormsgpack(types.ModuleType):
        def __init__(self) -> None:
            super().__init__("ormsgpack")
            self._bits: dict[str, int] = {}
            self._next = 0

            class Ext:
                def __init__(self, tag: int, data: bytes) -> None:
                    self.tag = tag
                    self.data = data

            self.Ext = Ext

        def __getattr__(self, name: str) -> int:
            if name.startswith("OPT_"):
                if name not in self._bits:
                    self._bits[name] = 1 << self._next
                    self._next += 1
                return self._bits[name]
            raise AttributeError(name)

        def packb(
            self,
            obj: object,
            option: int | None = None,
            default: object | None = None,
        ) -> bytes:
            _ = default
            return b"\x00" + json.dumps(obj, default=str).encode()

        def unpackb(
            self,
            data: bytes | bytearray | memoryview,
            option: int | None = None,
            ext_hook: object | None = None,
        ) -> object:
            raw = data.tobytes() if isinstance(data, memoryview) else bytes(data)
            if raw[:1] != b"\x00":
                msg = "ormsgpack shim only understands its own packb output"
                raise ValueError(msg)
            # stdlib json stubs return Any; shim only needs an opaque object.
            return json.loads(raw[1:])  # pyright: ignore[reportAny]

    sys.modules["ormsgpack"] = _Ormsgpack()


_shims_installed = False


def ensure_native_wheel_shims() -> None:
    """Idempotently install shims when native extensions cannot load."""
    global _shims_installed
    if _shims_installed:
        return
    _install_xxhash()
    _install_ormsgpack()
    _shims_installed = True
