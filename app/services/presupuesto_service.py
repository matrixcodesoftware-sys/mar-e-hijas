"""Presupuestos: alta, edición, estados y conversión a pedido.

La conversión a VENTA se hace abriendo el formulario de venta precargado con
los datos del presupuesto (el vendedor sólo elige la forma de pago); al
confirmar, venta_service vincula ambos documentos.
"""
from datetime import timedelta

from ..database import transaction
from ..models import cliente as cliente_model
from ..models import configuracion
from ..models import pedido as pedido_model
from ..models import presupuesto as presupuesto_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora, hoy
from ..utils.formato import etiqueta, moneda
from . import documento_service, historial_service

EDITABLES = ("pendiente", "enviado", "vencido")


def _datos_documento(datos, calc):
    envio = datos.get("tipo_entrega") == "envio"
    return {
        "cliente_id": datos["cliente_id"], "tipo_entrega": datos.get("tipo_entrega") or "retiro",
        "zona_id": datos.get("zona_id") if envio else None,
        "direccion_entrega": datos.get("direccion_entrega") if envio else None,
        "subtotal": calc["subtotal"], "descuento_general": calc["descuento_general"],
        "costo_envio": calc["costo_envio"], "total": calc["total"], "observaciones": datos.get("observaciones"),
    }


def _validar_cliente(cliente_id):
    cliente = cliente_model.obtener(cliente_id) if cliente_id else None
    if not cliente or not cliente["activo"]:
        raise NegocioError("Seleccioná un cliente activo.")
    return cliente


def guardar(datos, items, usuario_id, presupuesto_id=None):
    with transaction():
        cliente = _validar_cliente(datos.get("cliente_id"))
        envio = datos.get("costo_envio") if datos.get("tipo_entrega") == "envio" else 0
        calc = documento_service.calcular(items, datos.get("descuento_general"), envio)
        vencimiento = datos.get("fecha_vencimiento") or (hoy() + timedelta(days=configuracion.get_int("presupuesto_validez_dias", 7)))
        doc = {**_datos_documento(datos, calc), "fecha_vencimiento": vencimiento}
        if presupuesto_id:
            actual = presupuesto_model.obtener(presupuesto_id, bloquear=True)
            if not actual:
                raise NegocioError("El presupuesto no existe.")
            if actual["estado"] not in EDITABLES or actual["venta_id"] or actual["pedido_id"]:
                raise NegocioError("Sólo se pueden editar presupuestos pendientes, enviados o vencidos sin convertir.")
            presupuesto_model.actualizar(presupuesto_id, doc)
            presupuesto_model.borrar_detalle(presupuesto_id)
            if actual["estado"] == "vencido" and vencimiento >= hoy():
                presupuesto_model.set_estado(presupuesto_id, "pendiente")
            accion, texto = "modificar", "modificó"
        else:
            presupuesto_id = presupuesto_model.insertar({**doc, "fecha": ahora(), "usuario_id": usuario_id,
                                                         "estado": "pendiente"})
            accion, texto = "crear", "creó"
        for ln in calc["lineas"]:
            presupuesto_model.insertar_detalle(presupuesto_id, ln)
        historial_service.registrar(accion, "presupuestos", f"{texto} el presupuesto PR-{presupuesto_id:06d} para "
                                    f"{cliente['razon_social']} por {moneda(calc['total'])}", presupuesto_id)
        return presupuesto_id


def cambiar_estado(presupuesto_id, estado, usuario_id):
    if estado not in ("pendiente", "enviado", "aceptado", "rechazado"):
        raise NegocioError("Estado inválido.")
    with transaction():
        p = presupuesto_model.obtener(presupuesto_id, bloquear=True)
        if not p:
            raise NegocioError("El presupuesto no existe.")
        if p["venta_id"] or p["pedido_id"]:
            raise NegocioError("El presupuesto ya fue convertido; no se puede cambiar su estado.")
        if estado in ("pendiente", "enviado") and p["fecha_vencimiento"] < hoy():
            raise NegocioError("El presupuesto está vencido. Editalo y extendé la fecha de vencimiento.")
        presupuesto_model.set_estado(presupuesto_id, estado)
        historial_service.registrar("estado", "presupuestos", f"marcó el presupuesto PR-{presupuesto_id:06d} como "
                                    f"{etiqueta(estado, 'estado_presupuesto').lower()}", presupuesto_id)


def convertir_en_pedido(presupuesto_id, usuario_id):
    """Crea un pedido con los mismos ítems/flete. Devuelve el id del pedido."""
    with transaction():
        p = presupuesto_model.obtener(presupuesto_id, bloquear=True)
        if not p:
            raise NegocioError("El presupuesto no existe.")
        if p["pedido_id"] or p["venta_id"]:
            raise NegocioError("El presupuesto ya fue convertido.")
        if p["estado"] in ("rechazado",):
            raise NegocioError("El presupuesto está rechazado.")
        cliente = cliente_model.obtener(p["cliente_id"])
        detalle = presupuesto_model.detalle(presupuesto_id)
        pedido_id = pedido_model.insertar({
            "fecha": ahora(), "cliente_id": p["cliente_id"], "usuario_id": usuario_id, "presupuesto_id": p["id"],
            "tipo_entrega": p["tipo_entrega"], "direccion_entrega": p["direccion_entrega"] or cliente["direccion"],
            "localidad": cliente["localidad"], "referencia": cliente["referencia_ubicacion"],
            "zona_id": p["zona_id"] or cliente["zona_id"], "fecha_solicitada": hoy() + timedelta(days=1),
            "subtotal": p["subtotal"], "descuento_general": p["descuento_general"], "costo_envio": p["costo_envio"],
            "total": p["total"], "estado": "pendiente", "observaciones": p["observaciones"],
        })
        for d in detalle:
            pedido_model.insertar_detalle(pedido_id, d)
        presupuesto_model.marcar_convertido(presupuesto_id, pedido_id=pedido_id)
        historial_service.registrar("convertir", "presupuestos",
                                    f"convirtió el presupuesto PR-{presupuesto_id:06d} en el pedido P-{pedido_id:06d}",
                                    presupuesto_id)
        return pedido_id
