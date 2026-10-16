"""Soporte común de formularios de documentos (venta, presupuesto, pedido)."""
from flask import request

from ..models import catalogos
from ..models import cliente as cliente_model
from ..models import material as material_model
from ..services import conversion_service
from ..utils.validadores import Validador


def cliente_json(cliente_id):
    if not cliente_id:
        return None
    c = cliente_model.obtener(cliente_id)
    if not c:
        return None
    detalle = " · ".join(x for x in [c["documento"], c["localidad"], c["whatsapp"] or c["telefono"]] if x)
    return {"id": c["id"], "texto": c["razon_social"], "detalle": detalle, "direccion": c["direccion"],
            "localidad": c["localidad"], "zona_id": c["zona_id"], "referencia": c["referencia_ubicacion"],
            "saldo": str(c["saldo"] or 0), "limite": str(c["limite_credito"] or 0),
            "telefono": c["whatsapp"] or c["telefono"]}


def items_desde_post(items):
    """Reconstruye los ítems enviados para re-mostrar el formulario tras un error."""
    salida = []
    for it in items:
        try:
            m = material_model.obtener(int(it["material_id"]))
        except (TypeError, ValueError):
            m = None
        if not m:
            continue
        salida.append({
            "material_id": m["id"], "material": m["nombre"], "unidad_id": it.get("unidad_id"),
            "cantidad": it.get("cantidad") or "", "precio": it.get("precio_unitario") or "",
            "descuento": it.get("descuento_pct") or "0", "stock": str(m["stock_actual"]),
            "unidad_stock": m["unidad_abrev"], "unidades": conversion_service.unidades_para_material(m),
        })
    return salida


def leer_cabecera(form):
    """Campos comunes de cabecera (cliente, entrega, descuentos)."""
    v = Validador(form)
    tipo_entrega = v.opcion("tipo_entrega", ("retiro", "envio"), defecto="retiro")
    datos = {
        "cliente_id": v.entero("cliente_id"),
        "tipo_entrega": tipo_entrega,
        "zona_id": v.entero("zona_id"),
        "direccion_entrega": v.texto("direccion_entrega", maximo=200),
        "descuento_general": v.decimal("descuento_general", minimo=0) or 0,
        "costo_envio": v.decimal("costo_envio", minimo=0) or 0,
        "observaciones": v.texto("observaciones", maximo=2000),
    }
    return v, datos


def contexto_formulario():
    return {
        "zonas": catalogos.zonas(),
        "tipos_vehiculo": catalogos.listar("tipos_vehiculo", True),
    }


def origen_args():
    return {k: request.args.get(k) for k in ("presupuesto", "pedido") if request.args.get(k)}
