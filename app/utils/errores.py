"""Excepciones de dominio.

NegocioError: regla de negocio incumplida (stock insuficiente, caja cerrada,
límite de crédito…). Su mensaje se muestra tal cual al usuario y la transacción
en curso se revierte.
"""


class NegocioError(Exception):
    def __init__(self, mensaje, campo=None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.campo = campo


class ValidacionError(NegocioError):
    """Errores de formulario: `errores` es un dict campo -> mensaje."""

    def __init__(self, errores):
        self.errores = errores
        primero = next(iter(errores.values())) if errores else "Datos inválidos."
        super().__init__(primero)
