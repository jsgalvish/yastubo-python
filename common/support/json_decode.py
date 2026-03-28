from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any


class JsonDecode:
    def __init__(self, data: dict | None = None) -> None:
        object.__setattr__(self, "_data", data or {})

    # ── Acceso como objeto: obj.prop ──────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        return self._data.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def __delattr__(self, name: str) -> None:
        self._data.pop(name, None)

    # ── Acceso como dict: obj["prop"] ─────────────────────────────────────────

    def __getitem__(self, key: str) -> Any:
        return self._data.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    # ── Iteración: for k, v in obj ────────────────────────────────────────────

    def __iter__(self) -> Iterator:
        return iter(self._data)

    def to_array(self) -> dict:
        return self._data

    # ── Factory: JsonDecode.get(json_string) ─────────────────────────────────

    @classmethod
    def get(cls, json_str: str | None, first_level_associative: bool = False) -> list | dict:
        if not json_str:
            return []

        json_str = json_str.strip()
        if not json_str:
            return []

        # Remover BOM UTF-8
        if json_str.startswith("\xef\xbb\xbf"):
            json_str = json_str[3:].lstrip()
            if not json_str:
                return []

        try:
            decoded = json.loads(json_str)
        except json.JSONDecodeError:
            return []

        if not isinstance(decoded, (dict, list)):
            return []

        def to_dual(value: Any) -> Any:
            if not isinstance(value, (dict, list)):
                return value
            if isinstance(value, dict):
                return cls({k: to_dual(v) for k, v in value.items()})
            return [to_dual(v) for v in value]

        if first_level_associative:
            if isinstance(decoded, dict):
                return {k: to_dual(v) for k, v in decoded.items()}
            return [to_dual(v) for v in decoded]

        result = to_dual(decoded)
        if isinstance(result, cls):
            return result.to_array()
        return result
