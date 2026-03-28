"""
Excepción para transacciones no encontradas.

Equivale a App/Exceptions/TransactionNotFoundException de PHP.
"""

from common.exceptions.base_exception import BaseAppException


class TransactionNotFoundException(BaseAppException):
    pass
