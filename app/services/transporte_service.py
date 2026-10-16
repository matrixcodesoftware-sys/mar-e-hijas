"""Cotización de flete configurable.

costo = costo_fijo(zona)
      + costo_por_km(zona) × distancia (la informada o la de referencia de la zona)
      + costo_por_unidad(zona) × cantidad de carga
      + recargo del tipo de vehículo
Todos los valores salen de Configuración → Zonas de entrega y Tipos de vehículo.
"""
from decimal import Decimal

from ..models import catalogos
from ..utils.errores import NegocioError
from ..utils.numeros import D, dinero


def cotizar(zona_id, cantidad=None, distancia_km=None, tipo_vehiculo_id=None):
    zona = catalogos.obtener("zonas_entrega", zona_id) if zona_id else None
    if not zona or not zona["activo"]:
        raise NegocioError("Seleccioná una zona de entrega válida.")
    distancia = D(distancia_km) if distancia_km not in (None, "") else Decimal(zona["distancia_km"])
    carga = D(cantidad)
    detalle = []
    total = Decimal(zona["costo_fijo"])
    if zona["costo_fijo"]:
        detalle.append({"concepto": f"Fijo {zona['nombre']}", "importe": str(dinero(zona["costo_fijo"]))})
    if zona["costo_por_km"] and distancia:
        imp = Decimal(zona["costo_por_km"]) * distancia
        total += imp
        detalle.append({"concepto": f"{distancia} km × {zona['costo_por_km']}", "importe": str(dinero(imp))})
    if zona["costo_por_unidad"] and carga:
        imp = Decimal(zona["costo_por_unidad"]) * carga
        total += imp
        detalle.append({"concepto": f"{carga} u. de carga × {zona['costo_por_unidad']}", "importe": str(dinero(imp))})
    if tipo_vehiculo_id:
        tipo = catalogos.obtener("tipos_vehiculo", tipo_vehiculo_id)
        if tipo and tipo["recargo_transporte"]:
            total += Decimal(tipo["recargo_transporte"])
            detalle.append({"concepto": f"Recargo {tipo['nombre']}", "importe": str(dinero(tipo["recargo_transporte"]))})
    return {"zona": zona["nombre"], "distancia_km": str(distancia), "total": str(dinero(total)), "detalle": detalle}
