"""Logística: entregas (viajes), capacidad de camiones y estados.

Una entrega es UN viaje de UN camión. La carga (convertida a la unidad de
capacidad del camión) no puede superar su capacidad.
"""
from decimal import Decimal

from ..database import transaction
from ..models import entrega as entrega_model
from ..models import flota
from ..models import material as material_model
from ..models import pedido as pedido_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import cantidad as fmt_cant
from ..utils.formato import etiqueta
from ..utils.numeros import cantidad as q3
from . import conversion_service, historial_service

TRANSICIONES = {
    "pendiente": {"asignada", "cancelada"},
    "asignada": {"en_camino", "pendiente", "cancelada"},
    "en_camino": {"entregada", "no_entregada"},
    "no_entregada": {"asignada", "pendiente", "cancelada"},
    "entregada": set(),
    "cancelada": set(),
}
ESTADOS_CHOFER = {"en_camino", "entregada", "no_entregada"}


def validar_capacidad(vehiculo_id, lineas):
    """lineas: [{material_id, unidad_id, cantidad}]. Lanza NegocioError si se excede la capacidad."""
    if not vehiculo_id:
        return None
    vehiculo = flota.vehiculo(vehiculo_id)
    if not vehiculo:
        raise NegocioError("El vehículo no existe.")
    if vehiculo["estado"] in ("mantenimiento", "inactivo"):
        raise NegocioError(f"El vehículo {vehiculo['patente']} está en {etiqueta(vehiculo['estado'], 'estado_vehiculo').lower()}.")
    carga = Decimal(0)
    for ln in lineas:
        material = material_model.obtener(ln["material_id"])
        k = conversion_service.factor(material["id"], ln["unidad_id"], vehiculo["unidad_capacidad_id"])
        if k is None:
            raise NegocioError(
                f"No se puede controlar la capacidad del camión {vehiculo['patente']}: falta la conversión de la "
                f"unidad de {material['nombre']} a {vehiculo['unidad_nombre']}. Cargala en Configuración → Conversiones.")
        carga += Decimal(ln["cantidad"]) * k
    carga = q3(carga)
    if carga > Decimal(vehiculo["capacidad"]):
        raise NegocioError(
            f"La carga ({fmt_cant(carga)} {vehiculo['unidad_abrev']}) supera la capacidad del camión "
            f"{vehiculo['patente']} ({fmt_cant(vehiculo['capacidad'])} {vehiculo['unidad_abrev']}). "
            "Dividí la entrega en más de un viaje.")
    return carga


def _validar_chofer(chofer_id):
    if not chofer_id:
        return
    ch = flota.chofer(chofer_id)
    if not ch or ch["estado"] != "activo":
        raise NegocioError("El chofer no existe o no está activo.")


def crear(datos, lineas, usuario_id):
    """datos: cliente_id, direccion, localidad, referencia, telefono_contacto, chofer_id, vehiculo_id, fecha,
    horario, observaciones, pedido_id?, venta_id?.  lineas: [{material_id, unidad_id, cantidad, detalle_pedido_id?}]"""
    lineas = [ln for ln in lineas if Decimal(ln["cantidad"] or 0) > 0]
    if not lineas:
        raise NegocioError("La entrega debe llevar al menos un material.")
    if not datos.get("direccion"):
        raise NegocioError("La dirección de entrega es obligatoria.")
    with transaction():
        _validar_chofer(datos.get("chofer_id"))
        validar_capacidad(datos.get("vehiculo_id"), lineas)
        if datos.get("pedido_id"):
            _validar_pendiente_pedido(datos["pedido_id"], lineas)
        estado = "asignada" if datos.get("chofer_id") and datos.get("vehiculo_id") else "pendiente"
        entrega_id = entrega_model.insertar({**datos, "estado": estado, "usuario_id": usuario_id})
        for ln in lineas:
            entrega_model.insertar_detalle(entrega_id, ln["material_id"], ln["unidad_id"], q3(ln["cantidad"]),
                                           ln.get("detalle_pedido_id"))
        if datos.get("pedido_id"):
            pedido = pedido_model.obtener(datos["pedido_id"], bloquear=True)
            if pedido["estado"] in ("pendiente", "confirmado"):
                pedido_model.set_estado(pedido["id"], "preparando")
        historial_service.registrar("crear", "entregas", f"programó la entrega E-{entrega_id:06d}"
                                    + (f" del pedido P-{datos['pedido_id']:06d}" if datos.get("pedido_id") else ""),
                                    entrega_id)
        return entrega_id


def _validar_pendiente_pedido(pedido_id, lineas, excluir_entrega_id=None):
    detalle = {d["id"]: d for d in pedido_model.detalle(pedido_id)}
    for ln in lineas:
        d = detalle.get(int(ln.get("detalle_pedido_id") or 0))
        if not d:
            raise NegocioError("La carga no corresponde a los ítems del pedido.")
        pendiente = Decimal(d["cantidad"]) - Decimal(d["programado"])
        if Decimal(ln["cantidad"]) > pendiente + Decimal("0.0005"):
            raise NegocioError(
                f"{d['material']}: se quieren programar {fmt_cant(ln['cantidad'])} {d['unidad']} pero quedan "
                f"{fmt_cant(pendiente)} {d['unidad']} sin programar.")


def asignar(entrega_id, chofer_id, vehiculo_id, fecha, horario, observaciones, usuario_id):
    with transaction():
        e = entrega_model.obtener(entrega_id, bloquear=True)
        if not e:
            raise NegocioError("Entrega inexistente.")
        if e["estado"] not in ("pendiente", "asignada", "no_entregada"):
            raise NegocioError("Sólo se pueden reprogramar entregas pendientes, asignadas o no entregadas.")
        _validar_chofer(chofer_id)
        validar_capacidad(vehiculo_id, entrega_model.detalle(entrega_id))
        estado = "asignada" if chofer_id and vehiculo_id else "pendiente"
        entrega_model.asignar(entrega_id, chofer_id, vehiculo_id, fecha, horario, estado, observaciones)
        historial_service.registrar("modificar", "entregas", f"asignó/reprogramó la entrega E-{entrega_id:06d}",
                                    entrega_id)


def cambiar_estado(entrega_id, nuevo, usuario, recibido_por=None, motivo=None):
    """usuario: current_user (para validar que el chofer sólo toque sus entregas)."""
    with transaction():
        e = entrega_model.obtener(entrega_id, bloquear=True)
        if not e:
            raise NegocioError("Entrega inexistente.")
        es_chofer_propio = usuario.puede("entregas.propias") and usuario.chofer_id and e["chofer_id"] == usuario.chofer_id
        if not usuario.puede("entregas.gestionar"):
            if not es_chofer_propio:
                raise NegocioError("Esta entrega no está asignada a vos.")
            if nuevo not in ESTADOS_CHOFER:
                raise NegocioError("No podés aplicar ese estado.")
        if nuevo not in TRANSICIONES.get(e["estado"], set()):
            raise NegocioError(
                f"No se puede pasar de '{etiqueta(e['estado'], 'estado_entrega')}' a '{etiqueta(nuevo, 'estado_entrega')}'.")
        if nuevo == "asignada" and not (e["chofer_id"] and e["vehiculo_id"]):
            raise NegocioError("Asigná chofer y camión antes de marcarla como asignada.")
        extra = {}
        if nuevo == "en_camino":
            extra["fecha_salida"] = ahora()
            if e["vehiculo_id"]:
                flota.set_estado_vehiculo(e["vehiculo_id"], "en_uso")
        if nuevo == "entregada":
            extra["fecha_entrega_real"] = ahora()
            extra["recibido_por"] = (recibido_por or "")[:120] or None
        if nuevo == "no_entregada":
            if not motivo:
                raise NegocioError("Indicá el motivo por el que no se entregó.")
            extra["motivo_no_entrega"] = motivo[:255]
            extra["fecha_entrega_real"] = ahora()
        entrega_model.set_estado(entrega_id, nuevo, **extra)
        if nuevo in ("entregada", "no_entregada") and e["vehiculo_id"]:
            flota.set_estado_vehiculo(e["vehiculo_id"], "disponible")
        if e["pedido_id"]:
            sincronizar_pedido(e["pedido_id"])
        historial_service.registrar(
            "estado", "entregas",
            f"marcó la entrega E-{entrega_id:06d} como {etiqueta(nuevo, 'estado_entrega').lower()}"
            + (f" (recibió: {recibido_por})" if recibido_por else "") + (f" (motivo: {motivo})" if motivo else ""),
            entrega_id)


def sincronizar_pedido(pedido_id):
    """Deriva el estado del pedido a partir de sus viajes."""
    pedido = pedido_model.obtener(pedido_id, bloquear=True)
    if not pedido or pedido["estado"] in ("cancelado",):
        return
    entregas = pedido_model.entregas(pedido_id)
    detalle = pedido_model.detalle(pedido_id)
    completo = detalle and all(Decimal(d["entregado"]) + Decimal("0.0005") >= Decimal(d["cantidad"]) for d in detalle)
    if completo:
        nuevo = "entregado"
    elif any(e["estado"] == "en_camino" for e in entregas):
        nuevo = "en_camino"
    elif pedido["estado"] in ("en_camino", "entregado"):
        nuevo = "listo"
    else:
        return
    if nuevo != pedido["estado"]:
        pedido_model.set_estado(pedido_id, nuevo)
