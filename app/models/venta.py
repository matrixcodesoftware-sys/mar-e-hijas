"""Ventas, detalle y pagos asociados."""
from ..database import execute, query, query_one
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar

SELECT = """
    SELECT v.*, cl.razon_social AS cliente, cl.documento AS cliente_documento, cl.telefono AS cliente_telefono,
           CONCAT(u.nombre, ' ', u.apellido) AS vendedor, z.nombre AS zona
"""
FROM = """
    FROM ventas v
    JOIN clientes cl ON cl.id = v.cliente_id
    JOIN usuarios u ON u.id = v.usuario_id
    LEFT JOIN zonas_entrega z ON z.id = v.zona_id
"""


def buscar(desde=None, hasta=None, cliente_id=None, usuario_id=None, material_id=None, estado=None,
           estado_pago=None, numero=None, pagina=None):
    where, params = ["1=1"], []
    if numero:
        where.append("v.id = %s")
        params.append(numero)
    if desde:
        where.append("v.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("v.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    if cliente_id:
        where.append("v.cliente_id = %s")
        params.append(cliente_id)
    if usuario_id:
        where.append("v.usuario_id = %s")
        params.append(usuario_id)
    if material_id:
        where.append("EXISTS (SELECT 1 FROM detalle_ventas d WHERE d.venta_id = v.id AND d.material_id = %s)")
        params.append(material_id)
    if estado:
        where.append("v.estado = %s")
        params.append(estado)
    if estado_pago:
        where.append("v.estado_pago = %s")
        params.append(estado_pago)
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params, "ORDER BY v.fecha DESC, v.id DESC",
                   pagina=pagina)


def obtener(venta_id, bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM ventas WHERE id = %s FOR UPDATE", (venta_id,))
    return query_one(SELECT + FROM + " WHERE v.id = %s", (venta_id,))


def detalle(venta_id):
    return query(
        """SELECT d.*, m.nombre AS material, m.codigo, u.nombre AS unidad_nombre, u.abreviatura AS unidad,
                  ub.abreviatura AS unidad_stock, m.stock_actual
           FROM detalle_ventas d JOIN materiales m ON m.id = d.material_id
           JOIN unidades u ON u.id = d.unidad_id JOIN unidades ub ON ub.id = m.unidad_id
           WHERE d.venta_id = %s ORDER BY d.id""", (venta_id,))


def pagos(venta_id):
    return query(
        """SELECT p.*, mp.nombre AS metodo, CONCAT(u.nombre, ' ', u.apellido) AS usuario
           FROM pagos p JOIN metodos_pago mp ON mp.id = p.metodo_pago_id JOIN usuarios u ON u.id = p.usuario_id
           WHERE p.venta_id = %s ORDER BY p.fecha""", (venta_id,))


def insertar(datos):
    campos = ["fecha", "cliente_id", "usuario_id", "presupuesto_id", "pedido_id", "tipo_entrega", "zona_id",
              "direccion_entrega", "subtotal", "descuento_general", "costo_envio", "total", "costo_mercaderia",
              "monto_pagado", "saldo_cta_cte", "estado_pago", "observaciones"]
    return execute(
        f"INSERT INTO ventas ({', '.join(campos)}) VALUES ({', '.join(['%s'] * len(campos))})",
        [datos.get(c) for c in campos])


def insertar_detalle(venta_id, linea):
    return execute(
        """INSERT INTO detalle_ventas (venta_id, material_id, unidad_id, cantidad, factor_conversion, cantidad_stock,
           precio_unitario, descuento_pct, subtotal, costo_unitario) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (venta_id, linea["material_id"], linea["unidad_id"], linea["cantidad"], linea["factor_conversion"],
         linea["cantidad_stock"], linea["precio_unitario"], linea["descuento_pct"], linea["subtotal"],
         linea["costo_unitario"]))


def marcar_anulada(venta_id, usuario_id, fecha, motivo):
    execute("UPDATE ventas SET estado='anulada', anulada_por=%s, anulada_en=%s, motivo_anulacion=%s WHERE id=%s",
            (usuario_id, fecha, motivo, venta_id))


def anular_pagos(venta_id):
    execute("UPDATE pagos SET estado='anulado' WHERE venta_id=%s", (venta_id,))
