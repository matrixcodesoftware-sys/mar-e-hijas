"""Pedidos: alta, edición, estados y programación de viajes."""
from decimal import Decimal

from ..database import execute, transaction
from ..models import cliente as cliente_model
from ..models import pedido as pedido_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import etiqueta, moneda
from . import documento_service, entrega_service, historial_service

ORDEN = ["pendiente", "confirmado", "preparando", "listo", "en_camino", "entregado"]
# Transiciones manuales permitidas (en_camino / entregado también se derivan de las entregas)
TRANSICIONES = {
    "pendiente": {"confirmado", "cancelado"},
    "confirmado": {"preparando", "listo", "pendiente", "cancelado"},
    "preparando": {"listo", "confirmado", "cancelado"},
    "listo": {"en_camino", "entregado", "preparando", "cancelado"},
    "en_camino": {"entregado", "listo"},
    "entregado": set(),
    "cancelado": set(),
}


def guardar(datos, items, usuario_id, pedido_id=None):
    with transaction():
        cliente = cliente_model.obtener(datos.get("cliente_id")) if datos.get("cliente_id") else None
        if not cliente or not cliente["activo"]:
            raise NegocioError("Seleccioná un cliente activo.")
        if not datos.get("fecha_solicitada"):
            raise NegocioError("Indicá la fecha solicitada de entrega.")
        envio = datos.get("tipo_entrega") == "envio"
        if envio and not datos.get("direccion_entrega"):
            raise NegocioError("Indicá la dirección de entrega.")
        calc = documento_service.calcular(items, datos.get("descuento_general"),
                                          datos.get("costo_envio") if envio else 0)
        doc = {
            "cliente_id": cliente["id"], "tipo_entrega": datos.get("tipo_entrega") or "envio",
            "direccion_entrega": datos.get("direccion_entrega"), "localidad": datos.get("localidad"),
            "referencia": datos.get("referencia"), "zona_id": datos.get("zona_id") if envio else None,
            "fecha_solicitada": datos["fecha_solicitada"], "horario": datos.get("horario"),
            "vehiculo_id": datos.get("vehiculo_id"), "chofer_id": datos.get("chofer_id"),
            "subtotal": calc["subtotal"], "descuento_general": calc["descuento_general"],
            "costo_envio": calc["costo_envio"], "total": calc["total"], "observaciones": datos.get("observaciones"),
        }
        if pedido_id:
            actual = pedido_model.obtener(pedido_id, bloquear=True)
            if not actual:
                raise NegocioError("El pedido no existe.")
            if actual["venta_id"]:
                raise NegocioError("El pedido ya tiene venta generada; no se pueden modificar sus ítems.")
            if actual["estado"] not in ("pendiente", "confirmado", "preparando"):
                raise NegocioError("Sólo se pueden editar pedidos pendientes, confirmados o en preparación.")
            if pedido_model.entregas(pedido_id):
                if any(e["estado"] != "cancelada" for e in pedido_model.entregas(pedido_id)):
                    raise NegocioError("El pedido tiene viajes programados. Cancelalos antes de modificar los ítems.")
            pedido_model.actualizar(pedido_id, doc)
            pedido_model.borrar_detalle(pedido_id)
            accion, texto = "modificar", "modificó"
        else:
            pedido_id = pedido_model.insertar({**doc, "fecha": ahora(), "usuario_id": usuario_id,
                                               "presupuesto_id": datos.get("presupuesto_id"), "estado": "pendiente"})
            accion, texto = "crear", "creó"
        for ln in calc["lineas"]:
            pedido_model.insertar_detalle(pedido_id, ln)
        historial_service.registrar(accion, "pedidos", f"{texto} el pedido P-{pedido_id:06d} de "
                                    f"{cliente['razon_social']} por {moneda(calc['total'])}", pedido_id)
        return pedido_id


def cambiar_estado(pedido_id, nuevo, usuario_id):
    with transaction():
        p = pedido_model.obtener(pedido_id, bloquear=True)
        if not p:
            raise NegocioError("El pedido no existe.")
        if nuevo not in TRANSICIONES.get(p["estado"], set()):
            raise NegocioError(f"No se puede pasar de '{etiqueta(p['estado'], 'estado_pedido')}' a "
                               f"'{etiqueta(nuevo, 'estado_pedido')}'.")
        entregas = pedido_model.entregas(pedido_id)
        if nuevo == "cancelado":
            if any(e["estado"] in ("entregada", "en_camino") for e in entregas):
                raise NegocioError("El pedido tiene viajes entregados o en camino; no se puede cancelar.")
            if p["venta_id"]:
                raise NegocioError(f"El pedido tiene la venta V-{p['venta_id']:06d}. Anulá la venta primero.")
            execute("UPDATE entregas SET estado='cancelada' WHERE pedido_id=%s AND estado IN "
                    "('pendiente','asignada','no_entregada')", (pedido_id,))
        if nuevo == "entregado" and p["tipo_entrega"] == "envio" and entregas:
            detalle = pedido_model.detalle(pedido_id)
            if not all(Decimal(d["entregado"]) >= Decimal(d["cantidad"]) for d in detalle):
                raise NegocioError("Todavía hay material sin entregar en los viajes del pedido.")
        pedido_model.set_estado(pedido_id, nuevo)
        historial_service.registrar("estado", "pedidos", f"cambió el pedido P-{pedido_id:06d} a "
                                    f"{etiqueta(nuevo, 'estado_pedido').lower()}", pedido_id)


def programar_viaje(pedido_id, datos, cantidades, usuario_id):
    """cantidades: {detalle_pedido_id: cantidad}."""
    p = pedido_model.obtener(pedido_id)
    if not p:
        raise NegocioError("El pedido no existe.")
    if p["estado"] in ("cancelado", "entregado"):
        raise NegocioError("El pedido está cerrado.")
    if p["tipo_entrega"] != "envio":
        raise NegocioError("El pedido es para retiro en galpón; no requiere viajes.")
    detalle = {d["id"]: d for d in pedido_model.detalle(pedido_id)}
    lineas = []
    for dp_id, cant in cantidades.items():
        d = detalle.get(int(dp_id))
        if d and Decimal(cant or 0) > 0:
            lineas.append({"detalle_pedido_id": d["id"], "material_id": d["material_id"], "unidad_id": d["unidad_id"],
                           "cantidad": Decimal(cant)})
    return entrega_service.crear({
        "pedido_id": pedido_id, "venta_id": p["venta_id"], "cliente_id": p["cliente_id"],
        "direccion": p["direccion_entrega"], "localidad": p["localidad"], "referencia": p["referencia"],
        "telefono_contacto": p["cliente_whatsapp"] or p["cliente_telefono"],
        "chofer_id": datos.get("chofer_id"), "vehiculo_id": datos.get("vehiculo_id"),
        "fecha": datos.get("fecha") or p["fecha_solicitada"], "horario": datos.get("horario") or p["horario"],
        "observaciones": datos.get("observaciones") or p["observaciones"],
    }, lineas, usuario_id)
