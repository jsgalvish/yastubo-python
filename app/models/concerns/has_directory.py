from __future__ import annotations

import os


class HasDirectory:
    """
    Mixin para modelos que almacenan archivos en disco.

    Equivale al trait HasDirectory de PHP.
    """

    def storage_path(self, field: str | None = None) -> str:
        """
        Retorna la ruta de almacenamiento del modelo.

        Args:
            field: nombre del campo (opcional). Si se proporciona, se agrega
                   el valor del campo a la ruta base.

        Returns:
            Ruta absoluta al directorio (o archivo) del modelo.
        """
        from app.config import settings

        base = os.path.join(
            settings.app_storage_dir,
            self.__tablename__,  # type: ignore[attr-defined]
            str(self.id),        # type: ignore[attr-defined]
        )
        if field:
            value = getattr(self, field, None)
            return os.path.join(base, value) if value else base
        return base
