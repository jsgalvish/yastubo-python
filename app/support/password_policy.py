from __future__ import annotations

import re

from config.password_policy import PASSWORD_POLICY


class PasswordPolicy:
    def validate(self, password: str, context: dict | None = None) -> list[str]:
        """Valida la contraseña y retorna lista de errores (vacía = válida)."""
        cfg = PASSWORD_POLICY
        context = context or {}
        errors: list[str] = []
        pwd_lower = password.lower()

        if len(password) < cfg["min"]:
            errors.append(f"Debe tener al menos {cfg['min']} caracteres.")

        max_len = cfg.get("max", 0)
        if max_len and len(password) > max_len:
            errors.append(f"No debe exceder {max_len} caracteres.")

        req = cfg.get("require", {})
        if req.get("uppercase") and not re.search(r"[A-Z]", password):
            errors.append("Debe incluir al menos una mayúscula.")

        if req.get("lowercase") and not re.search(r"[a-z]", password):
            errors.append("Debe incluir al menos una minúscula.")

        if req.get("numbers") and not re.search(r"\d", password):
            errors.append("Debe incluir al menos un número.")

        if req.get("symbols") and not re.search(r"[^a-zA-Z0-9]", password):
            errors.append("Debe incluir al menos un símbolo.")

        # Palabras prohibidas
        for bad in cfg.get("banned", []):
            if bad and bad.lower() in pwd_lower:
                errors.append("La contraseña contiene patrones inseguros.")
                break

        # Partes del usuario prohibidas
        email = context.get("email", "")
        field_map = {
            "first_name":    context.get("first_name", ""),
            "last_name":     context.get("last_name", ""),
            "display_name":  context.get("display_name", ""),
            "email_local":   email.split("@")[0] if email else "",
        }
        for key in cfg.get("forbid_user_parts", []):
            candidate = field_map.get(key, "").lower()
            if candidate and candidate in pwd_lower:
                errors.append("La contraseña no debe incluir información personal (nombre, email, etc.).")
                break

        return errors

    def for_frontend(self) -> dict:
        """Estructura para el frontend (sin secretos)."""
        cfg = PASSWORD_POLICY
        req = cfg.get("require", {})
        return {
            "min": cfg["min"],
            "max": cfg.get("max", 128),
            "require": {
                "uppercase":  bool(req.get("uppercase")),
                "lowercase":  bool(req.get("lowercase")),
                "numbers":    bool(req.get("numbers")),
                "symbols":    bool(req.get("symbols")),
                "mixed_case": bool(req.get("mixed_case")),
            },
            "messages": {
                "min":        f"Debe tener al menos {cfg['min']} caracteres.",
                "uppercase":  "Debe incluir al menos una mayúscula.",
                "lowercase":  "Debe incluir al menos una minúscula.",
                "numbers":    "Debe incluir al menos un número.",
                "symbols":    "Debe incluir al menos un símbolo.",
                "max":        f"No debe exceder {cfg.get('max', 128)} caracteres.",
                "noPersonal": "No debe incluir tu nombre ni tu email.",
            },
        }
