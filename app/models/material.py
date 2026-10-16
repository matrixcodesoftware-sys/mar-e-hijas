"""Materiales / áridos."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

SELECT = """
    SELECT m.*, c.nombre AS categoria, u.nombre AS unidad_nombre, u.abreviatura AS unidad_abrev,
           p.razon_social AS proveedor
"""
FROM = """
    FROM materiales m
    JOIN categorias_materiales c ON c.id = m.categoria_id
    JOIN unidades u ON u.id = m.unidad_id
    LEFT JOIN proveedores p ON p.id = m.proveedor_id
"""


def buscar(texto=None, categoria_id=None, proveedor_id=None, activo=None, bajo_stock=False, pagina=None, por_pagina=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(m.nombre LIKE %s OR m.codigo LIKE %s OR m.descripcion LIKE %s)")
        params += [f"%{texto}%"] * 3
    if categoria_id:
        where.append("m.categoria_id = %s")
        params.append(categoria_id)
    if proveedor_id:
        where.append("m.proveedor_id = %s")
        params.append(proveedor_id)
    if activo in ("0", "1"):
        where.append("m.activo = %s")
        params.append(int(activo))
    if bajo_stock:
        where.append("m.stock_actual <= m.stock_minimo")
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params, "ORDER BY m.nombre",
                   pagina=pagina, por_pagina=por_pagina)


def obtener(material_id, bloquear=False):
    sql = SELECT + FROM + " WHERE m.id = %s"
    if bloquear:
        # FOR UPDATE sólo sobre materiales: las demás tablas del JOIN no se bloquean de forma útil
        return query_one("SELECT * FROM materiales WHERE id = %s FOR UPDATE", (material_id,))
    return query_one(sql, (material_id,))


def autocompletar(texto, limite=12):
    like = f"%{texto}%"
    return query(
        SELECT + FROM + """ WHERE m.activo = 1 AND (m.nombre LIKE %s OR m.codigo LIKE %s)
        ORDER BY (m.codigo = %s) DESC, m.nombre LIMIT %s""",
        (like, like, texto, limite),
    )


def listar_activos():
    return query(SELECT + FROM + " WHERE m.activo = 1 ORDER BY m.nombre")


def opciones():
    return [(m["id"], f"{m['nombre']} ({m['unidad_abrev']})") for m in listar_activos()]


def existe_codigo(codigo, excluir_id=None):
    return query_one("SELECT id FROM materiales WHERE codigo = %s AND id <> %s", (codigo, excluir_id or 0)) is not None


def siguiente_codigo():
    fila = query_one("SELECT MAX(id) AS n FROM materiales")
    return f"MAT-{(fila['n'] or 0) + 1:04d}"


CAMPOS = ["codigo", "nombre", "categoria_id", "descripcion", "unidad_id", "precio_compra", "precio_venta",
          "stock_minimo", "proveedor_id", "activo"]


def crear(datos):
    return execute(
        f"INSERT INTO materiales ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
        [datos.get(c) for c in CAMPOS],
    )


def actualizar(material_id, datos):
    execute(
        "UPDATE materiales SET " + ", ".join(f"{c} = %s" for c in CAMPOS) + " WHERE id = %s",
        [datos.get(c) for c in CAMPOS] + [material_id],
    )


def set_stock(material_id, stock):
    execute("UPDATE materiales SET stock_actual = %s WHERE id = %s", (stock, material_id))


def set_precio_compra(material_id, precio):
    execute("UPDATE materiales SET precio_compra = %s WHERE id = %s", (precio, material_id))


def tiene_movimientos(material_id):
    return query_one("SELECT id FROM movimientos_stock WHERE material_id = %s LIMIT 1", (material_id,)) is not None


def bajo_stock(limite=10):
    return query(
        SELECT + FROM + """ WHERE m.activo = 1 AND m.stock_actual <= m.stock_minimo
        ORDER BY (m.stock_actual / NULLIF(m.stock_minimo, 0)), m.nombre LIMIT %s""",
        (limite,),
    )


def resumen_stock():
    return query(
        SELECT + FROM + " WHERE m.activo = 1 ORDER BY c.nombre, m.nombre"
    )
