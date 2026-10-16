"""Movimientos de stock."""
from ..database import execute, query
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar

CAMPOS = ["fecha", "material_id", "tipo", "cantidad", "unidad_id", "cantidad_unidad", "factor_conversion",
          "stock_anterior", "stock_resultante", "proveedor_id", "cliente_id", "venta_id", "vehiculo_id",
          "vehiculo_descripcion", "remito_numero", "costo_unitario", "costo_total", "usuario_id", "observaciones"]


def insertar(datos):
    return execute(
        f"INSERT INTO movimientos_stock ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
        [datos.get(c) for c in CAMPOS])


SELECT = """
    SELECT ms.*, m.nombre AS material, m.codigo AS material_codigo, ub.abreviatura AS unidad_stock,
           u.abreviatura AS unidad_mov, p.razon_social AS proveedor, cl.razon_social AS cliente,
           CONCAT(us.nombre, ' ', us.apellido) AS usuario, ve.patente
"""
FROM = """
    FROM movimientos_stock ms
    JOIN materiales m ON m.id = ms.material_id
    JOIN unidades ub ON ub.id = m.unidad_id
    JOIN unidades u ON u.id = ms.unidad_id
    JOIN usuarios us ON us.id = ms.usuario_id
    LEFT JOIN proveedores p ON p.id = ms.proveedor_id
    LEFT JOIN clientes cl ON cl.id = ms.cliente_id
    LEFT JOIN vehiculos ve ON ve.id = ms.vehiculo_id
"""


def buscar(material_id=None, tipo=None, desde=None, hasta=None, proveedor_id=None, remito=None, pagina=None):
    where, params = ["1=1"], []
    if material_id:
        where.append("ms.material_id = %s")
        params.append(material_id)
    if tipo:
        where.append("ms.tipo = %s")
        params.append(tipo)
    if desde:
        where.append("ms.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("ms.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    if proveedor_id:
        where.append("ms.proveedor_id = %s")
        params.append(proveedor_id)
    if remito:
        where.append("ms.remito_numero LIKE %s")
        params.append(f"%{remito}%")
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params, "ORDER BY ms.fecha DESC, ms.id DESC",
                   pagina=pagina)


def de_venta(venta_id):
    return query(SELECT + FROM + " WHERE ms.venta_id = %s ORDER BY ms.id", (venta_id,))


def totales_por_material(desde, hasta):
    """Entradas, salidas y ajustes del período por material (en unidad de stock)."""
    return query(
        """SELECT m.id, m.codigo, m.nombre, u.abreviatura, m.stock_actual, m.stock_minimo,
                  COALESCE(SUM(CASE WHEN ms.tipo = 'entrada' THEN ms.cantidad END), 0) AS entradas,
                  COALESCE(-SUM(CASE WHEN ms.tipo = 'salida' THEN ms.cantidad END), 0) AS salidas,
                  COALESCE(SUM(CASE WHEN ms.tipo IN ('ajuste','anulacion') THEN ms.cantidad END), 0) AS ajustes
           FROM materiales m
           JOIN unidades u ON u.id = m.unidad_id
           LEFT JOIN movimientos_stock ms ON ms.material_id = m.id AND ms.fecha >= %s AND ms.fecha < %s
           WHERE m.activo = 1
           GROUP BY m.id, m.codigo, m.nombre, u.abreviatura, m.stock_actual, m.stock_minimo
           ORDER BY m.nombre""",
        (inicio_dia(desde), fin_dia_exclusivo(hasta)))
