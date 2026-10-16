"""Aritmética decimal para montos y cantidades (nunca float para dinero)."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVO = Decimal("0.01")
MILESIMA = Decimal("0.001")
CERO = Decimal("0")


def D(valor, defecto=CERO) -> Decimal:
    """Convierte a Decimal aceptando '1.234,50', '1234.50', int, float o Decimal."""
    if valor is None or valor == "":
        return defecto
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int,)):
        return Decimal(valor)
    if isinstance(valor, float):
        return Decimal(str(valor))
    texto = str(valor).strip().replace("$", "").replace(" ", "")
    if "," in texto:
        # Formato argentino: 1.234,56
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return defecto


def dinero(valor) -> Decimal:
    return D(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def cantidad(valor) -> Decimal:
    return D(valor).quantize(MILESIMA, rounding=ROUND_HALF_UP)
