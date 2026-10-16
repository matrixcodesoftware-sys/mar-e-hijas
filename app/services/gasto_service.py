"""Gastos operativos (combustible, mantenimiento, sueldos…)."""
from ..database import transaction
from ..models import catalogos
from ..models import gasto as gasto_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora, inicio_dia
from ..utils.formato import moneda
from ..utils.numeros import dinero
from . import caja_service, historial_service


def registrar(datos, usuario_id):
    """Si el método de pago mueve dinero (todos salvo cuenta corriente) se registra el egreso en la caja abierta."""
    monto = dinero(datos["monto"])
    if monto <= 0:
        raise NegocioError("El monto debe ser mayor a cero.")
    with transaction():
        metodo = catalogos.metodo_pago(datos["metodo_pago_id"])
        if not metodo or not metodo["activo"]:
            raise NegocioError("Método de pago inválido.")
        if metodo["grupo"] == "cuenta_corriente":
            raise NegocioError("Los gastos no se pueden registrar en cuenta corriente de clientes. "
                               "Si quedó a pagar a un proveedor, registralo desde Proveedores.")
        fecha = ahora()
        if datos.get("fecha") and datos["fecha"] != fecha.date():
            fecha = inicio_dia(datos["fecha"]).replace(hour=12)
        caja = caja_service.requerir_caja_abierta()
        gasto_id = gasto_model.insertar({**datos, "monto": monto, "fecha": fecha, "caja_id": caja["id"],
                                         "usuario_id": usuario_id})
        caja_service.registrar_movimiento("gasto", "egreso", metodo["id"], monto, f"Gasto: {datos['descripcion']}",
                                          usuario_id, gasto_id=gasto_id)
        historial_service.registrar("crear", "gastos", f"registró un gasto de {moneda(monto)}: {datos['descripcion']}",
                                    gasto_id)
        return gasto_id


def anular(gasto_id, usuario_id):
    with transaction():
        g = gasto_model.obtener(gasto_id, bloquear=True)
        if not g:
            raise NegocioError("Gasto inexistente.")
        if g["estado"] == "anulado":
            raise NegocioError("El gasto ya está anulado.")
        caja_service.registrar_movimiento("anulacion", "ingreso", g["metodo_pago_id"], g["monto"],
                                          f"Anulación gasto #{gasto_id}: {g['descripcion']}", usuario_id,
                                          gasto_id=gasto_id)
        gasto_model.anular(gasto_id)
        historial_service.registrar("anular", "gastos", f"anuló el gasto #{gasto_id} ({moneda(g['monto'])})", gasto_id)
