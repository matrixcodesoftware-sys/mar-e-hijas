"""Conversión de unidades configurable (nada fijo en el código).

Regla: 1 [origen] = factor [destino]. Se busca un camino entre unidades usando
conversiones específicas del material (prioritarias) y generales, en ambos
sentidos (la inversa usa 1/factor), con hasta 3 saltos.
Ej.: viaje → m³ (general: 6) y m³ → t (arena: 1,6) ⇒ 1 viaje de arena = 9,6 t.
"""
from collections import deque
from decimal import Decimal

from ..database import query
from ..models import catalogos
from ..models import conversion as conversion_model
from ..utils.errores import NegocioError

PRECISION = Decimal("0.000001")


def _grafo(material_id):
    """Aristas {origen: {destino: factor}}; las específicas del material pisan a las generales."""
    grafo = {}
    filas = conversion_model.aplicables(material_id)
    # primero generales, luego específicas (para que sobrescriban)
    filas.sort(key=lambda f: f["material_id"] is not None)
    for f in filas:
        o, d, k = f["unidad_origen_id"], f["unidad_destino_id"], Decimal(f["factor"])
        grafo.setdefault(o, {})[d] = k
        grafo.setdefault(d, {}).setdefault(o, Decimal(1) / k)
        if f["material_id"] is not None:
            grafo[d][o] = Decimal(1) / k
    return grafo


def factor(material_id, desde_unidad_id, hacia_unidad_id, grafo=None):
    """Cuántas [hacia] equivalen a 1 [desde]. None si no hay camino."""
    desde_unidad_id, hacia_unidad_id = int(desde_unidad_id), int(hacia_unidad_id)
    if desde_unidad_id == hacia_unidad_id:
        return Decimal(1)
    grafo = grafo if grafo is not None else _grafo(material_id)
    visitados = {desde_unidad_id}
    cola = deque([(desde_unidad_id, Decimal(1), 0)])
    while cola:
        nodo, acumulado, saltos = cola.popleft()
        if saltos >= 3:
            continue
        for vecino, k in grafo.get(nodo, {}).items():
            if vecino in visitados:
                continue
            nuevo = acumulado * k
            if vecino == hacia_unidad_id:
                return nuevo.quantize(PRECISION)
            visitados.add(vecino)
            cola.append((vecino, nuevo, saltos + 1))
    return None


def factor_obligatorio(material, desde_unidad_id, hacia_unidad_id=None):
    """Como factor() pero lanza NegocioError con un mensaje accionable."""
    hacia = hacia_unidad_id or material["unidad_id"]
    k = factor(material["id"], desde_unidad_id, hacia)
    if k is None:
        nombres = {u["id"]: u["nombre"] for u in catalogos.listar("unidades")}
        raise NegocioError(
            f"No hay conversión configurada de {nombres.get(int(desde_unidad_id), '?')} a "
            f"{nombres.get(int(hacia), '?')} para {material['nombre']}. "
            "Cargala en Configuración → Conversiones."
        )
    return k


def unidades_para_material(material):
    """Unidades en las que se puede vender el material, con factor a la unidad de stock y precio sugerido."""
    grafo = _grafo(material["id"])
    resultado = []
    for u in catalogos.listar("unidades", solo_activos=True):
        k = factor(material["id"], u["id"], material["unidad_id"], grafo)
        if k is None:
            continue
        resultado.append({
            "id": u["id"],
            "nombre": u["nombre"],
            "abreviatura": u["abreviatura"],
            "factor": str(k),
            "precio": str((Decimal(material["precio_venta"]) * k).quantize(Decimal("0.01"))),
            "es_base": u["id"] == material["unidad_id"],
        })
    resultado.sort(key=lambda x: (not x["es_base"], x["nombre"]))
    return resultado


def unidades_ids_por_material(material_ids):
    """Mapa material_id -> lista de unidades (para precargar formularios)."""
    if not material_ids:
        return {}
    marcadores = ", ".join(["%s"] * len(material_ids))
    mats = query(f"SELECT * FROM materiales WHERE id IN ({marcadores})", list(material_ids))
    return {m["id"]: unidades_para_material(m) for m in mats}
