from __future__ import annotations

from datetime import datetime
from typing import Any

from babel.numbers import format_currency as babel_currency
from babel.numbers import format_decimal as babel_decimal

from config.format import FORMAT_LOCALES


class FormatService:
    def __init__(self, locale: str | None = None) -> None:
        self._locale = self._resolve_locale(locale)
        self._config = self._resolve_config_for_locale(self._locale)

    def get_locale(self) -> str:
        return self._locale

    def get_config(self) -> dict:
        return self._config

    # ── Fechas ────────────────────────────────────────────────────────────────

    def date(self, value: Any, fmt: str | None = None) -> str | None:
        dt = self._to_datetime(value)
        if dt is None:
            return None
        return dt.strftime(fmt or self._config.get("date_format", "%Y-%m-%d"))

    def time(self, value: Any, fmt: str | None = None) -> str | None:
        dt = self._to_datetime(value)
        if dt is None:
            return None
        return dt.strftime(fmt or self._config.get("time_format", "%H:%M"))

    def datetime(self, value: Any, fmt: str | None = None) -> str | None:
        dt = self._to_datetime(value)
        if dt is None:
            return None
        return dt.strftime(fmt or self._config.get("datetime_format", "%Y-%m-%d %H:%M"))

    # ── Números ───────────────────────────────────────────────────────────────

    def integer(self, value: Any, nullable: bool = True) -> str | None:
        if value is None:
            return None if nullable else "0"
        numeric = int(round(float(value)))
        locale = self._config.get("number_locale", "en_US")
        return babel_decimal(numeric, format="#,##0", locale=locale)

    def decimal(self, value: Any, decimals: int = 2, nullable: bool = True) -> str | None:
        if value is None or value == "":
            if nullable:
                return None
            value = 0
        numeric = float(value)
        locale = self._config.get("number_locale", "en_US")
        fmt = "#,##0." + ("0" * decimals)
        return babel_decimal(numeric, format=fmt, locale=locale)

    def money(
        self,
        value: Any,
        currency: str = "USD",
        decimals: int = 2,
        with_code: bool = False,
    ) -> str | None:
        if value is None or value == "":
            return None
        numeric = float(value)
        locale = self._config.get("number_locale", "en_US")
        formatted = babel_currency(numeric, currency, locale=locale)
        return f"{formatted} {currency}" if with_code else formatted

    def decimal_or_dash(self, value: Any, decimals: int = 2) -> str:
        result = self.decimal(value, decimals, nullable=True)
        return "–" if result is None else result

    # ── Privados ──────────────────────────────────────────────────────────────

    def _to_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str) and value.strip():
            from dateutil.parser import parse, ParserError
            try:
                return parse(value)
            except (ParserError, ValueError):
                return None
        return None

    def _resolve_locale(self, locale: str | None) -> str:
        if locale:
            return locale
        from app.config import settings
        return settings.app_timezone and "es" or "es"

    def _resolve_config_for_locale(self, locale: str) -> dict:
        if locale in FORMAT_LOCALES:
            return FORMAT_LOCALES[locale]
        # Fallback al primer locale disponible
        if FORMAT_LOCALES:
            return next(iter(FORMAT_LOCALES.values()))
        return {
            "number_locale":   "en_US",
            "date_format":     "%Y-%m-%d",
            "time_format":     "%H:%M",
            "datetime_format": "%Y-%m-%d %H:%M",
            "js_date_format":  "yyyy-MM-dd",
        }
