from __future__ import annotations

import json
from typing import Any


class HasTranslatableJson:
    """
    Mixin para modelos con campos JSON traducibles.

    Los campos traducibles se almacenan como dicts: {"es": "...", "en": "..."}.
    Equivale al cast TranslatableJson de PHP.
    """

    def translate(self, data: Any, locale: str = "es") -> str | None:
        """
        Retorna el valor traducido para el locale indicado.

        Prioridad: locale solicitado → "es" → primer valor disponible.
        """
        if data is None:
            return None
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, ValueError):
                return data
        if isinstance(data, dict):
            return data.get(locale) or data.get("es") or next(iter(data.values()), None)
        return str(data)
