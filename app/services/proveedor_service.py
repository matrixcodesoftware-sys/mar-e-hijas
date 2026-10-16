"""Cuenta y pagos a proveedores."""
from decimal import Decimal

from ..database import transaction
from ..models import catalogos
from ..models import proveedor as proveedor_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import moneda
from ..utils.numeros import dinero
from . import caja_service, historial_service


def registrar_pago(datos, usuario_id):
    """Pago a proveedor: egreso de caja + abono en su cuenta."""
    monto = dinero(datos["monto"])
    if monto <= 0:
        raise NegocioError("El monto debe ser mayor a cero.")
    with transaction():
        proveedor = proveedor_model.obtener(datos["proveedor_id"], bloquear=True)
        if not proveedor:
            raise NegocioError("Proveedor inexistente.")
        metodo = catalogos.metodo_pago(datos["metodo_pago_id"])
        if not metodo or metodo["grupo"] == "cuenta_corriente":
            raise NegocioError("Elegí un método de pago válido.")
        caja = caja_service.requerir_caja_abierta()
        fecha = ahora()
        pago_id = proveedor_model.insertar_pago({
            "fecha": fecha, "proveedor_id": proveedor["id"], "metodo_pago_id": metodo["id"], "monto": monto,
            "caja_id": caja["id"], "referencia": datos.get("referencia"), "usuario_id": usuario_id,
            "observaciones": datos.get("observaciones"),
        })
        saldo = dinero(Decimal(proveedor["saldo_cuenta"]) - monto)
        proveedor_model.insertar_movimiento({
            "proveedor_id": proveedor["id"], "fecha": fecha, "tipo": "pago",
            "concepto": f"Pago {metodo['nombre']}" + (f" · {datos['referencia']}" if datos.get("referencia") else ""),
            "abono": monto, "saldo_resultante": saldo, "pago_proveedor_id": pago_id, "usuario_id": usuario_id,
        })
        proveedor_model.set_saldo(proveedor["id"], saldo)
        caja_service.registrar_movimiento(
            "pago_proveedor", "egreso", metodo["id"], monto, f"Pago a {proveedor['razon_social']}", usuario_id,
            pago_proveedor_id=pago_id, fecha=fecha)
        historial_service.registrar(
            "crear", "proveedores", f"registró un pago de {moneda(monto)} a {proveedor['razon_social']}", pago_id)
        return pago_id
