"""Caja diaria.

- Hay a lo sumo una caja abierta (garantizado también por índice único en la BD).
- Todo cobro/pago, de cualquier método, se registra como movimiento de la caja
  abierta; así el cierre discrimina efectivo, transferencias, tarjetas y otros.
- Saldo esperado (efectivo físico) = inicial + ingresos en efectivo − egresos en efectivo.
"""
from decimal import Decimal

from ..database import transaction
from ..models import caja as caja_model
from ..models import catalogos
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import moneda
from ..utils.numeros import dinero
from . import historial_service

TIPOS_MANUALES = {"ingreso": "ingreso", "retiro": "egreso", "ajuste": None}


def caja_abierta():
    return caja_model.abierta()


def requerir_caja_abierta():
    caja = caja_model.abierta(bloquear=True)
    if not caja:
        raise NegocioError("No hay una caja abierta. Abrí la caja para registrar cobros o pagos.")
    return caja


def abrir(monto_inicial, usuario_id, observaciones=None):
    monto = dinero(monto_inicial)
    if monto < 0:
        raise NegocioError("El monto inicial no puede ser negativo.")
    with transaction():
        if caja_model.abierta(bloquear=True):
            raise NegocioError("Ya hay una caja abierta.")
        caja_id = caja_model.crear(usuario_id, ahora(), monto, observaciones)
        historial_service.registrar("crear", "caja", f"abrió la caja #{caja_id} con {moneda(monto)}", caja_id)
        return caja_id


def registrar_movimiento(tipo, sentido, metodo_pago_id, monto, concepto, usuario_id, **refs):
    """Registra un movimiento en la caja abierta. Llamar dentro de una transacción."""
    monto = dinero(monto)
    if monto <= 0:
        raise NegocioError("El monto del movimiento debe ser mayor a cero.")
    metodo = catalogos.metodo_pago(metodo_pago_id)
    if not metodo or not metodo["activo"]:
        raise NegocioError("Método de pago inválido.")
    if metodo["grupo"] == "cuenta_corriente":
        raise NegocioError("La cuenta corriente no es un medio de cobro de caja.")
    caja = requerir_caja_abierta()
    if sentido == "egreso" and metodo["grupo"] == "efectivo":
        disponible = resumen(caja)["saldo_esperado"]
        if monto > disponible:
            raise NegocioError(f"No hay suficiente efectivo en caja: disponible {moneda(disponible)}, "
                               f"se quieren retirar {moneda(monto)}.")
    return caja_model.insertar_movimiento({
        "caja_id": caja["id"], "fecha": refs.pop("fecha", None) or ahora(), "tipo": tipo, "sentido": sentido,
        "metodo_pago_id": metodo_pago_id, "monto": monto, "concepto": concepto, "usuario_id": usuario_id, **refs,
    })


def movimiento_manual(tipo, sentido, metodo_pago_id, monto, concepto, usuario_id):
    if tipo not in TIPOS_MANUALES:
        raise NegocioError("Tipo de movimiento inválido.")
    sentido = TIPOS_MANUALES[tipo] or sentido
    if sentido not in ("ingreso", "egreso"):
        raise NegocioError("Indicá si el ajuste es ingreso o egreso.")
    if not concepto:
        raise NegocioError("El concepto es obligatorio.")
    with transaction():
        mov_id = registrar_movimiento(tipo, sentido, metodo_pago_id, monto, concepto, usuario_id)
        historial_service.registrar(
            "crear", "caja", f"registró un {tipo} de caja por {moneda(monto)}: {concepto}", mov_id)
        return mov_id


def resumen(caja):
    """Totales de la caja para mostrar en pantalla o cerrar."""
    t = {
        "ventas_efectivo": Decimal(0), "cobros_efectivo": Decimal(0), "efectivo_ing": Decimal(0),
        "efectivo_egr": Decimal(0), "transferencias": Decimal(0), "tarjetas": Decimal(0), "otros": Decimal(0),
        "ingresos": Decimal(0), "egresos": Decimal(0),
    }
    for fila in caja_model.totales(caja["id"]):
        monto = Decimal(fila["total"])
        signo = 1 if fila["sentido"] == "ingreso" else -1
        if fila["sentido"] == "ingreso":
            t["ingresos"] += monto
        else:
            t["egresos"] += monto
        if fila["grupo"] == "efectivo":
            if fila["sentido"] == "ingreso":
                t["efectivo_ing"] += monto
                if fila["tipo"] == "venta":
                    t["ventas_efectivo"] += monto
                elif fila["tipo"] == "pago_cliente":
                    t["cobros_efectivo"] += monto
            else:
                t["efectivo_egr"] += monto
        elif fila["grupo"] == "transferencia":
            t["transferencias"] += signo * monto
        elif fila["grupo"] == "tarjeta":
            t["tarjetas"] += signo * monto
        else:
            t["otros"] += signo * monto
    t["saldo_inicial"] = Decimal(caja["monto_inicial"])
    t["saldo_esperado"] = dinero(t["saldo_inicial"] + t["efectivo_ing"] - t["efectivo_egr"])
    return t


def cerrar(saldo_declarado, usuario_id, observaciones=None):
    declarado = dinero(saldo_declarado)
    if declarado < 0:
        raise NegocioError("El saldo declarado no puede ser negativo.")
    with transaction():
        caja = caja_model.abierta(bloquear=True)
        if not caja:
            raise NegocioError("No hay una caja abierta.")
        r = resumen(caja)
        diferencia = dinero(declarado - r["saldo_esperado"])
        caja_model.cerrar(caja["id"], {
            "usuario_id": usuario_id, "fecha": ahora(), "total_efectivo_ing": r["efectivo_ing"],
            "total_efectivo_egr": r["efectivo_egr"], "total_transferencias": r["transferencias"],
            "total_tarjetas": r["tarjetas"], "total_otros": r["otros"], "saldo_esperado": r["saldo_esperado"],
            "saldo_declarado": declarado, "diferencia": diferencia, "observaciones": observaciones,
        })
        historial_service.registrar(
            "cerrar", "caja",
            f"cerró la caja #{caja['id']}: esperado {moneda(r['saldo_esperado'])}, declarado {moneda(declarado)}, "
            f"diferencia {moneda(diferencia)}", caja["id"])
        return caja["id"]
