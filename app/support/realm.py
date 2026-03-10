from contextvars import ContextVar

from fastapi import Request

_current_realm_var: ContextVar[str | None] = ContextVar("current_realm", default=None)


class Realm:
    ADMIN    = "admin"
    CUSTOMER = "customer"

    # Clave del atributo en el Request (espeja PHP)
    ATTRIBUTE = "_current_realm"

    @classmethod
    def all(cls) -> list[str]:
        return [cls.ADMIN, cls.CUSTOMER]

    @classmethod
    def is_valid(cls, name: str | None) -> bool:
        return name in cls.all()

    @classmethod
    def set_current(cls, name: str | None) -> None:
        _current_realm_var.set(name if cls.is_valid(name) else None)

    @classmethod
    def current(cls, request: Request | None = None) -> str | None:
        cached = _current_realm_var.get()
        if cached:
            return cached

        if request is not None:
            val = getattr(request.state, cls.ATTRIBUTE, None)
            if cls.is_valid(val):
                _current_realm_var.set(val)
                return val

        return None

    @classmethod
    def is_admin(cls, request: Request | None = None) -> bool:
        return cls.current(request) == cls.ADMIN

    @classmethod
    def is_customer(cls, request: Request | None = None) -> bool:
        return cls.current(request) == cls.CUSTOMER
