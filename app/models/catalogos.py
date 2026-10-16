"""Tablas de parámetros simples: categorías de materiales, unidades, zonas de entrega,
tipos de vehículo, categorías de gastos y métodos de pago.

Los nombres de tabla y columnas están fijados aquí (nunca vienen del usuario),
y los valores siempre van parametrizados.
"""
from ..database import execute, query, query_one

CATALOGOS = {
    "categorias_materiales": {
        "titulo": "Categorías / tipos de material",
        "singular": "categoría",
        "columnas": ["nombre", "descripcion", "activo"],
        "orden": "nombre",
    },
    "unidades": {
        "titulo": "Unidades de venta",
        "singular": "unidad",
        "columnas": ["codigo", "nombre", "abreviatura", "magnitud", "activo"],
        "orden": "id",
    },
    "zonas_entrega": {
        "titulo": "Zonas de entrega",
        "singular": "zona",
        "columnas": ["nombre", "descripcion", "distancia_km", "costo_fijo", "costo_por_km", "costo_por_unidad", "activo"],
        "orden": "nombre",
    },
    "tipos_vehiculo": {
        "titulo": "Tipos de vehículo",
        "singular": "tipo de vehículo",
        "columnas": ["nombre", "recargo_transporte", "activo"],
        "orden": "nombre",
    },
    "categorias_gastos": {
        "titulo": "Categorías de gastos",
        "singular": "categoría",
        "columnas": ["nombre", "activo"],
        "orden": "nombre",
    },
    "metodos_pago": {
        "titulo": "Métodos de pago",
        "singular": "método de pago",
        "columnas": ["codigo", "nombre", "grupo", "activo"],
        "orden": "id",
    },
}


def _cfg(tabla):
    if tabla not in CATALOGOS:
        raise ValueError("Catálogo inexistente")
    return CATALOGOS[tabla]


def listar(tabla, solo_activos=False):
    cfg = _cfg(tabla)
    where = " WHERE activo = 1" if solo_activos else ""
    return query(f"SELECT * FROM {tabla}{where} ORDER BY {cfg['orden']}")


def obtener(tabla, id_):
    _cfg(tabla)
    return query_one(f"SELECT * FROM {tabla} WHERE id = %s", (id_,))


def existe_valor(tabla, columna, valor, excluir_id=None):
    cfg = _cfg(tabla)
    if columna not in cfg["columnas"]:
        raise ValueError("Columna inválida")
    return query_one(
        f"SELECT id FROM {tabla} WHERE {columna} = %s AND id <> %s", (valor, excluir_id or 0)
    ) is not None


def crear(tabla, datos):
    cfg = _cfg(tabla)
    cols = [c for c in cfg["columnas"] if c in datos]
    marcadores = ", ".join(["%s"] * len(cols))
    return execute(
        f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({marcadores})", [datos[c] for c in cols]
    )


def actualizar(tabla, id_, datos):
    cfg = _cfg(tabla)
    cols = [c for c in cfg["columnas"] if c in datos]
    asignaciones = ", ".join(f"{c} = %s" for c in cols)
    execute(f"UPDATE {tabla} SET {asignaciones} WHERE id = %s", [datos[c] for c in cols] + [id_])


def opciones(tabla, texto="nombre", solo_activos=True):
    return [(f["id"], f[texto]) for f in listar(tabla, solo_activos)]


# ---- atajos usados por formularios
def unidades_opciones():
    return [(u["id"], f"{u['nombre']} ({u['abreviatura']})") for u in listar("unidades", True)]


def metodos_pago(incluir_cta_cte=True):
    filas = listar("metodos_pago", True)
    if not incluir_cta_cte:
        filas = [f for f in filas if f["grupo"] != "cuenta_corriente"]
    return filas


def metodo_pago(id_):
    return obtener("metodos_pago", id_)


def metodo_por_codigo(codigo):
    return query_one("SELECT * FROM metodos_pago WHERE codigo = %s", (codigo,))


def zonas():
    return listar("zonas_entrega", True)
