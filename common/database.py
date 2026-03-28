"""
Configuración de base de datos async con SQLAlchemy 2.0.

Cambios aplicados por auditoría de skills:
  - HIGH-5: try/except/finally en get_db() para rollback en error.
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from common.config import settings

engine = create_async_engine(settings.db_url, echo=settings.app_debug, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para FastAPI: inyecta una sesión async de base de datos.

    Patrón try/yield/except/finally para garantizar rollback en caso de error
    y cierre limpio de la sesión.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
