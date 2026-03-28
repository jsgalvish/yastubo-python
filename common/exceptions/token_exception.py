"""
Excepción para errores de token.

Equivale a App/Exceptions/TokenException de PHP.
"""

from common.exceptions.base_exception import BaseAppException


class TokenException(BaseAppException):
    pass
