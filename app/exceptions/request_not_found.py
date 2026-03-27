"""
Excepción para recursos no encontrados.

Equivale a App\Exceptions\RequestNotFoundException de PHP.
"""

from app.exceptions.base_exception import BaseAppException


class RequestNotFoundException(BaseAppException):
    pass
