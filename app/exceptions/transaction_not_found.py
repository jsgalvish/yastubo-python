r"""
Excepción para transacciones no encontradas.

Equivale a App\Exceptions\TransactionNotFoundException de PHP.
"""

from app.exceptions.base_exception import BaseAppException


class TransactionNotFoundException(BaseAppException):
    pass
