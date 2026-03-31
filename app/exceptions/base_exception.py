r"""
Excepción base de la aplicación.

Equivale a App\Exceptions\BaseException de PHP.
Soporta error_code y context adicional para respuestas JSON detalladas.
"""

from __future__ import annotations

from typing import Any


class BaseAppException(Exception):
    """Excepción base con soporte para error_code y context."""

    def __init__(
        self,
        message: str = "",
        error_code: str | None = None,
        context: Any = None,
    ) -> None:
        super().__init__(message)
        self._error_code = error_code
        self._context = context

    # ── Accessors ────────────────────────────────────────────────────────────

    @property
    def error_code(self) -> str | None:
        return self._error_code

    @error_code.setter
    def error_code(self, value: str | None) -> None:
        self._error_code = value

    @property
    def context(self) -> Any:
        return self._context

    @context.setter
    def context(self, value: Any) -> None:
        self._context = value
