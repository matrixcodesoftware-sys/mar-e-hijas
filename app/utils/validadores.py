"""Validación de formularios del lado del servidor.

Uso:
    v = Validador(request.form)
    datos = {
        "nombre": v.texto("nombre", requerido=True, maximo=120),
        "precio": v.decimal("precio", minimo=0),
    }
    v.verificar()   # lanza ValidacionError con todos los errores juntos
"""
import re

from .errores import ValidacionError
from .fechas import parse_fecha
from .numeros import D

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATENTE_RE = re.compile(r"^([A-Z]{3}\d{3}|[A-Z]{2}\d{3}[A-Z]{2})$")


def cuit_valido(cuit: str) -> bool:
    """Verifica el dígito verificador de un CUIT/CUIL (11 dígitos)."""
    digitos = re.sub(r"\D", "", cuit or "")
    if len(digitos) != 11:
        return False
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(digitos[:10], pesos))
    resto = 11 - (suma % 11)
    verificador = 0 if resto == 11 else (9 if resto == 10 else resto)
    return verificador == int(digitos[10])


class Validador:
    def __init__(self, datos):
        self.datos = datos
        self.errores = {}

    def _raw(self, campo):
        valor = self.datos.get(campo)
        return valor.strip() if isinstance(valor, str) else valor

    def error(self, campo, mensaje):
        self.errores.setdefault(campo, mensaje)

    def texto(self, campo, requerido=False, maximo=255, minimo=0, etiqueta=None):
        valor = self._raw(campo) or ""
        nombre = etiqueta or campo.replace("_", " ").capitalize()
        if requerido and not valor:
            self.error(campo, f"{nombre} es obligatorio.")
            return None
        if valor and len(valor) > maximo:
            self.error(campo, f"{nombre} admite hasta {maximo} caracteres.")
        if valor and len(valor) < minimo:
            self.error(campo, f"{nombre} debe tener al menos {minimo} caracteres.")
        return valor or None

    def entero(self, campo, requerido=False, minimo=None, maximo=None, etiqueta=None):
        valor = self._raw(campo)
        nombre = etiqueta or campo.replace("_", " ").capitalize()
        if valor in (None, ""):
            if requerido:
                self.error(campo, f"{nombre} es obligatorio.")
            return None
        try:
            n = int(valor)
        except (TypeError, ValueError):
            self.error(campo, f"{nombre} debe ser un número entero.")
            return None
        if minimo is not None and n < minimo:
            self.error(campo, f"{nombre} debe ser mayor o igual a {minimo}.")
        if maximo is not None and n > maximo:
            self.error(campo, f"{nombre} debe ser menor o igual a {maximo}.")
        return n

    def decimal(self, campo, requerido=False, minimo=None, maximo=None, etiqueta=None, positivo=False):
        valor = self._raw(campo)
        nombre = etiqueta or campo.replace("_", " ").capitalize()
        if valor in (None, ""):
            if requerido:
                self.error(campo, f"{nombre} es obligatorio.")
            return None
        n = D(valor, defecto=None)
        if n is None:
            self.error(campo, f"{nombre} debe ser un número válido.")
            return None
        if positivo and n <= 0:
            self.error(campo, f"{nombre} debe ser mayor a cero.")
        if minimo is not None and n < D(minimo):
            self.error(campo, f"{nombre} no puede ser menor a {minimo}.")
        if maximo is not None and n > D(maximo):
            self.error(campo, f"{nombre} no puede ser mayor a {maximo}.")
        return n

    def fecha(self, campo, requerido=False, etiqueta=None):
        valor = self._raw(campo)
        nombre = etiqueta or campo.replace("_", " ").capitalize()
        if not valor:
            if requerido:
                self.error(campo, f"{nombre} es obligatoria.")
            return None
        f = parse_fecha(valor)
        if not f:
            self.error(campo, f"{nombre} no es una fecha válida.")
        return f

    def opcion(self, campo, validas, requerido=True, defecto=None, etiqueta=None):
        valor = self._raw(campo) or defecto
        nombre = etiqueta or campo.replace("_", " ").capitalize()
        if valor in (None, ""):
            if requerido:
                self.error(campo, f"{nombre} es obligatorio.")
            return None
        if valor not in validas:
            self.error(campo, f"{nombre}: opción no válida.")
            return None
        return valor

    def booleano(self, campo):
        return 1 if self._raw(campo) in ("1", "on", "true", "si", True) else 0

    def email(self, campo, requerido=False):
        valor = self.texto(campo, requerido=requerido, maximo=120, etiqueta="Email")
        if valor and not EMAIL_RE.match(valor):
            self.error(campo, "Email no válido.")
        return valor.lower() if valor else None

    def documento(self, campo, tipo, requerido=False):
        valor = self._raw(campo)
        if not valor:
            if requerido:
                self.error(campo, "El documento es obligatorio.")
            return None
        digitos = re.sub(r"\D", "", valor)
        if tipo in ("CUIT", "CUIL"):
            if not cuit_valido(digitos):
                self.error(campo, f"{tipo} no válido (verificá los 11 dígitos).")
        elif tipo == "DNI":
            if not 7 <= len(digitos) <= 8:
                self.error(campo, "DNI no válido (7 u 8 dígitos).")
        else:
            digitos = valor[:13]
        return digitos or None

    def cuit(self, campo, requerido=False):
        return self.documento(campo, "CUIT", requerido)

    def patente(self, campo):
        valor = (self._raw(campo) or "").upper().replace(" ", "").replace("-", "")
        if not valor:
            self.error(campo, "La patente es obligatoria.")
            return None
        if not PATENTE_RE.match(valor):
            self.error(campo, "Patente no válida (formatos AAA123 o AA123BB).")
        return valor

    def verificar(self):
        if self.errores:
            raise ValidacionError(self.errores)
