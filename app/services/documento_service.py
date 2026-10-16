"""Cálculo de ítems para ventas, presupuestos y pedidos.

El navegador calcula totales para mostrar, pero el servidor SIEMPRE recalcula
todo acá con Decimal y con los datos vigentes de la base.
"""
from decimal import Decimal

from ..models import material as material_model
from ..utils.errores import NegocioError
from ..utils.numeros import D, cantidad, dinero
from . import conversion_service


def leer_items(form):
    """Lee las listas item_*[] enviadas por el editor de ítems."""
    materiales = form.getlist("item_material_id")
    unidades = form.getlist("item_unidad_id")
    cantidades = form.getlist("item_cantidad")
    precios = form.getlist("item_precio")
    descuentos = form.getlist("item_descuento")
    items = []
    for i, mat in enumerate(materiales):
        if not mat:
            continue
        items.append({
            "material_id": mat,
            "unidad_id": unidades[i] if i < len(unidades) else None,
            "cantidad": cantidades[i] if i < len(cantidades) else None,
            "precio_unitario": precios[i] if i < len(precios) else None,
            "descuento_pct": descuentos[i] if i < len(descuentos) else None,
        })
    return items


def calcular(items, descuento_general=0, costo_envio=0, exigir_items=True):
    """Valida y calcula. Devuelve dict con lineas (enriquecidas) y totales."""
    if exigir_items and not items:
        raise NegocioError("Agregá al menos un material.")
    lineas = []
    subtotal = Decimal(0)
    costo_mercaderia = Decimal(0)
    for n, it in enumerate(items, start=1):
        try:
            material_id = int(it["material_id"])
            unidad_id = int(it["unidad_id"])
        except (TypeError, ValueError):
            raise NegocioError(f"Ítem {n}: seleccioná material y unidad.")
        material = material_model.obtener(material_id)
        if not material or not material["activo"]:
            raise NegocioError(f"Ítem {n}: el material no existe o está inactivo.")
        cant = cantidad(it.get("cantidad"))
        if cant <= 0:
            raise NegocioError(f"Ítem {n} ({material['nombre']}): la cantidad debe ser mayor a cero.")
        factor = conversion_service.factor_obligatorio(material, unidad_id)
        precio = it.get("precio_unitario")
        precio = dinero(precio) if precio not in (None, "") else dinero(Decimal(material["precio_venta"]) * factor)
        if precio < 0:
            raise NegocioError(f"Ítem {n}: el precio no puede ser negativo.")
        desc = D(it.get("descuento_pct"))
        if desc < 0 or desc > 100:
            raise NegocioError(f"Ítem {n}: el descuento debe estar entre 0 y 100 %.")
        sub = dinero(cant * precio * (Decimal(100) - desc) / Decimal(100))
        cant_stock = cantidad(cant * factor)
        costo_unit = dinero(material["precio_compra"])
        costo_mercaderia += dinero(cant_stock * costo_unit)
        subtotal += sub
        lineas.append({
            "material_id": material_id, "material": material, "unidad_id": unidad_id, "cantidad": cant,
            "factor_conversion": factor, "cantidad_stock": cant_stock, "precio_unitario": precio,
            "descuento_pct": dinero(desc), "subtotal": sub, "costo_unitario": costo_unit,
        })
    subtotal = dinero(subtotal)
    desc_general = dinero(descuento_general)
    envio = dinero(costo_envio)
    if desc_general < 0 or envio < 0:
        raise NegocioError("Descuento y flete no pueden ser negativos.")
    if desc_general > subtotal:
        raise NegocioError("El descuento general no puede superar el subtotal.")
    total = dinero(subtotal - desc_general + envio)
    return {"lineas": lineas, "subtotal": subtotal, "descuento_general": desc_general, "costo_envio": envio,
            "total": total, "costo_mercaderia": dinero(costo_mercaderia)}


def items_para_formulario(detalle):
    """Convierte filas de detalle (presupuesto/pedido/venta) al formato que consume el editor JS."""
    ids = {d["material_id"] for d in detalle}
    unidades = conversion_service.unidades_ids_por_material(ids)
    salida = []
    for d in detalle:
        salida.append({
            "material_id": d["material_id"], "material": d.get("material") or d.get("material_nombre"),
            "unidad_id": d["unidad_id"], "cantidad": str(d["cantidad"]), "precio": str(d["precio_unitario"]),
            "descuento": str(d.get("descuento_pct") or 0), "stock": str(d.get("stock_actual") or ""),
            "unidad_stock": d.get("unidad_stock") or "", "unidades": unidades.get(d["material_id"], []),
        })
    return salida
