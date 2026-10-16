"""Cuenta corriente de clientes.

saldo > 0 ⇒ el cliente nos debe.
DEBE  (aumenta deuda): venta fiada, deuda manual, ajuste.
HABER (disminuye deuda): pago, crédito / nota a favor, anulación de venta.
Cada movimiento guarda el saldo resultante; el saldo de la cuenta se actualiza
en la misma transacción con la fila bloqueada.
"""
from decimal import Decimal

from ..database import execute, transaction
from ..models import catalogos
from ..models import cliente as cliente_model
from ..models import cuenta_corriente as cc_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import moneda
from ..utils.numeros import dinero
from . import caja_service, historial_service


def asegurar_cuenta(cliente_id):
    cuenta = cc_model.por_cliente(cliente_id, bloquear=True)
    if not cuenta:
        cc_model.crear(cliente_id)
        cuenta = cc_model.por_cliente(cliente_id, bloquear=True)
    return cuenta


def _movimiento(cliente_id, tipo, concepto, debe, haber, usuario_id, venta_id=None, pago_id=None,
                fecha=None, validar_limite=False):
    cuenta = asegurar_cuenta(cliente_id)
    debe, haber = dinero(debe), dinero(haber)
    nuevo_saldo = dinero(Decimal(cuenta["saldo"]) + debe - haber)
    limite = Decimal(cuenta["limite_credito"])
    if validar_limite and debe > 0 and limite > 0 and nuevo_saldo > limite:
        raise NegocioError(
            f"La operación supera el límite de crédito del cliente ({moneda(limite)}). "
            f"Saldo actual {moneda(cuenta['saldo'])}, quedaría en {moneda(nuevo_saldo)}.")
    fecha = fecha or ahora()
    mov_id = cc_model.insertar_movimiento({
        "cuenta_id": cuenta["id"], "fecha": fecha, "tipo": tipo, "concepto": concepto, "debe": debe,
        "haber": haber, "saldo_resultante": nuevo_saldo, "venta_id": venta_id, "pago_id": pago_id,
        "usuario_id": usuario_id,
    })
    cc_model.set_saldo(cuenta["id"], nuevo_saldo, fecha)
    return mov_id, nuevo_saldo


def cargar_venta(cliente_id, venta_id, monto, usuario_id, fecha):
    """Parte no cobrada de una venta → DEBE."""
    return _movimiento(cliente_id, "venta", f"Venta V-{venta_id:06d}", monto, 0, usuario_id,
                       venta_id=venta_id, fecha=fecha, validar_limite=True)


def revertir_venta(cliente_id, venta_id, monto, usuario_id):
    return _movimiento(cliente_id, "anulacion", f"Anulación venta V-{venta_id:06d}", 0, monto, usuario_id,
                       venta_id=venta_id)


def insertar_pago(cliente_id, venta_id, metodo_pago_id, monto, caja_id, referencia, usuario_id, fecha,
                  observaciones=None):
    return execute(
        """INSERT INTO pagos (fecha, cliente_id, venta_id, metodo_pago_id, monto, caja_id, referencia, usuario_id,
           observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (fecha, cliente_id, venta_id, metodo_pago_id, dinero(monto), caja_id, referencia, usuario_id, observaciones))


def registrar_pago(cliente_id, monto, metodo_pago_id, usuario_id, referencia=None, observaciones=None):
    """Pago a cuenta corriente: HABER + ingreso en caja."""
    monto = dinero(monto)
    if monto <= 0:
        raise NegocioError("El monto del pago debe ser mayor a cero.")
    with transaction():
        cliente = cliente_model.obtener(cliente_id)
        if not cliente:
            raise NegocioError("Cliente inexistente.")
        metodo = catalogos.metodo_pago(metodo_pago_id)
        if not metodo or metodo["grupo"] == "cuenta_corriente":
            raise NegocioError("Elegí un método de pago válido (efectivo, transferencia, etc.).")
        caja = caja_service.requerir_caja_abierta()
        fecha = ahora()
        pago_id = insertar_pago(cliente_id, None, metodo_pago_id, monto, caja["id"], referencia, usuario_id, fecha,
                                observaciones)
        concepto = f"Pago {metodo['nombre']}" + (f" · ref. {referencia}" if referencia else "")
        _, saldo = _movimiento(cliente_id, "pago", concepto, 0, monto, usuario_id, pago_id=pago_id, fecha=fecha)
        caja_service.registrar_movimiento(
            "pago_cliente", "ingreso", metodo_pago_id, monto, f"Pago cta. cte. {cliente['razon_social']}",
            usuario_id, pago_id=pago_id, fecha=fecha)
        historial_service.registrar(
            "crear", "cuentas", f"registró un pago de {moneda(monto)} de {cliente['razon_social']} "
            f"({metodo['nombre']}). Saldo: {moneda(saldo)}", pago_id)
        return pago_id


def registrar_manual(cliente_id, tipo, monto, concepto, usuario_id):
    """Deuda (DEBE) o crédito (HABER) manual, sin movimiento de caja."""
    monto = dinero(monto)
    if monto <= 0:
        raise NegocioError("El monto debe ser mayor a cero.")
    if not concepto:
        raise NegocioError("El concepto es obligatorio.")
    if tipo not in ("deuda", "credito"):
        raise NegocioError("Tipo de movimiento inválido.")
    with transaction():
        cliente = cliente_model.obtener(cliente_id)
        if not cliente:
            raise NegocioError("Cliente inexistente.")
        debe, haber = (monto, 0) if tipo == "deuda" else (0, monto)
        mov_id, saldo = _movimiento(cliente_id, tipo, concepto, debe, haber, usuario_id)
        historial_service.registrar(
            "crear", "cuentas", f"registró {'una deuda' if tipo == 'deuda' else 'un crédito'} de {moneda(monto)} "
            f"a {cliente['razon_social']}: {concepto}. Saldo: {moneda(saldo)}", mov_id)
        return mov_id


def actualizar_limite(cliente_id, limite, usuario_id=None):
    with transaction():
        asegurar_cuenta(cliente_id)
        cc_model.set_limite(cliente_id, dinero(limite))


def resumen(cliente_id, desde=None, hasta=None):
    cuenta = cc_model.por_cliente(cliente_id)
    if not cuenta:
        return {"cuenta": None, "movimientos": [], "saldo_inicial": Decimal(0)}
    saldo_inicial = Decimal(cc_model.saldo_al(cuenta["id"], desde)) if desde else Decimal(0)
    movs = cc_model.movimientos(cuenta["id"], desde, hasta)
    total_debe = sum((Decimal(m["debe"]) for m in movs), Decimal(0))
    total_haber = sum((Decimal(m["haber"]) for m in movs), Decimal(0))
    return {"cuenta": cuenta, "movimientos": movs, "saldo_inicial": saldo_inicial,
            "total_debe": total_debe, "total_haber": total_haber,
            "saldo_final": movs[-1]["saldo_resultante"] if movs else saldo_inicial}
