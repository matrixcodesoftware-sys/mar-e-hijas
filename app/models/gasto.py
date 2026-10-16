"""Gastos."""
from ..database import execute, query, query_one
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar

SELECT = """
    SELECT g.*, cg.nombre AS categoria, mp.nombre AS metodo, p.razon_social AS proveedor, v.patente,
           CONCAT(u.nombre, ' ', u.apellido) AS usuario
"""
FROM = """
    FROM gastos g
    JOIN categorias_gastos cg ON cg.id = g.categoria_id
    JOIN metodos_pago mp ON mp.id = g.metodo_pago_id
    JOIN usuarios u ON u.id = g.usuario_id
    LEFT JOIN proveedores p ON p.id = g.proveedor_id
    LEFT JOIN vehiculos v ON v.id = g.vehiculo_id
"""


def _where(categoria_id=None, desde=None, hasta=None, texto=None, vehiculo_id=None, estado=None):
    where, params = ["1=1"], []
    if categoria_id:
        where.append("g.categoria_id = %s")
        params.append(categoria_id)
    if desde:
        where.append("g.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("g.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    if texto:
        where.append("(g.descripcion LIKE %s OR g.observaciones LIKE %s)")
        params += [f"%{texto}%"] * 2
    if vehiculo_id:
        where.append("g.vehiculo_id = %s")
        params.append(vehiculo_id)
    if estado:
        where.append("g.estado = %s")
        params.append(estado)
    return " WHERE " + " AND ".join(where), params


def buscar(pagina=None, **filtros):
    where, params = _where(**filtros)
    return paginar(SELECT, FROM + where, params, "ORDER BY g.fecha DESC, g.id DESC", pagina=pagina)


def total(**filtros):
    where, params = _where(**filtros)
    return query_one("SELECT COALESCE(SUM(g.monto), 0) AS total " + FROM + where + " AND g.estado = 'registrado'",
                     params)["total"]


def obtener(gasto_id, bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM gastos WHERE id = %s FOR UPDATE", (gasto_id,))
    return query_one(SELECT + FROM + " WHERE g.id = %s", (gasto_id,))


def insertar(datos):
    campos = ["fecha", "categoria_id", "descripcion", "monto", "metodo_pago_id", "proveedor_id", "vehiculo_id",
              "caja_id", "usuario_id", "observaciones"]
    return execute(f"INSERT INTO gastos ({', '.join(campos)}) VALUES ({', '.join(['%s'] * len(campos))})",
                   [datos.get(c) for c in campos])


def anular(gasto_id):
    execute("UPDATE gastos SET estado = 'anulado' WHERE id = %s", (gasto_id,))


def por_categoria(desde, hasta):
    return query(
        """SELECT cg.nombre, SUM(g.monto) AS total FROM gastos g JOIN categorias_gastos cg ON cg.id = g.categoria_id
           WHERE g.estado = 'registrado' AND g.fecha >= %s AND g.fecha < %s GROUP BY cg.nombre ORDER BY total DESC""",
        (inicio_dia(desde), fin_dia_exclusivo(hasta)))
