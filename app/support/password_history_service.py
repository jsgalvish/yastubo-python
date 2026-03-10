from __future__ import annotations


class PasswordHistoryService:
    def reused(self, user: object, plain: str) -> bool:
        """
        Verifica si la contraseña fue usada recientemente.

        TODO: completar en Step 2 (Models) cuando PasswordHistory esté disponible.
        """
        return False  # TODO: implementar con PasswordHistory model

    def remember(self, user: object, old_hash: str | None) -> None:
        """
        Guarda el hash anterior en el historial.

        TODO: completar en Step 2 (Models) cuando PasswordHistory esté disponible.
        """
        pass  # TODO: implementar con PasswordHistory model
