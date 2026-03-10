from __future__ import annotations

import os

from fastapi import Request

from app.support.audit import Audit
from app.support.realm import Realm


def realm(request: Request | None = None) -> str | None:
    """Retorna el dominio actual (admin / customer)."""
    return Realm.current(request)


def is_realm_admin(request: Request | None = None) -> bool:
    return Realm.is_admin(request)


def is_realm_customer(request: Request | None = None) -> bool:
    return Realm.is_customer(request)


async def audit_log(
    action: str,
    context: dict | None = None,
    target_user_id: int | None = None,
) -> None:
    """Alias conveniente para Audit.log()."""
    await Audit.log(action, context, target_user_id)


def env_any(*params) -> bool:
    """Retorna True si al menos uno de los env vars tiene valor verdadero."""
    for env in params:
        if isinstance(env, str):
            val = os.getenv(env, "").lower()
            if val in ("1", "true", "yes"):
                return True
        elif isinstance(env, (list, tuple)):
            if env_any(*env):
                return True
        else:
            raise ValueError(f"ENV ERROR: parámetro inválido {env!r}")
    return False
