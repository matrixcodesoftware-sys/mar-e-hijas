"""Pedidos y su detalle."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

SELECT = """
    SELECT p.*, cl.razon_social AS cliente, cl.telefono AS cliente_telefono, cl.whatsapp AS cliente_whatsapp,
           z.nombre AS zona, ve.patente, CONCAT(ch.nombre, ' ', ch.apellido) AS chofer,
           CONCAT(u.nombre, ' ', u.apellido) AS usuario
"""
FROM = """
    FROM pedidos p
    JOIN clientes cl ON cl.id = p.cliente_id
    JOIN usuarios u ON u.id = p.usuario_id
    LEFT JOIN zonas_entrega z ON z.id = p.zona_id
    LEFT JOIN vehiculos ve ON ve.id = p.vehiculo_id
    LEFT JOIN choferes ch ON ch.id = p.chofer_id
"""


def buscar(estado=None, cliente_id=None, desde=None, hasta=None, numero=None, chofer_id=None, activos=False,
           pagina=None):
    where, params = ["1=1"], []
    if numero:
        where.append("p.id = %s")
        params.append(numero)
    if estado:
        where.append("p.estado = %s")
        params.append(estado)
    if activos:
        where.append("p.estado NOT IN ('entregado','cancelado')")
    if cliente_id:
        where.append("p.cliente_id = %s")
        params.append(cliente_id)
    if desde:
        where.append("p.fecha_solicitada >= %s")
        params.append(desde)
    if hasta:
        where.append("p.fecha_solicitada <= %s")
        params.append(hasta)
    if chofer_id:
        where.append("p.chofer_id = %s")
        params.append(chofer_id)
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params,
                   "ORDER BY p.fecha_solicitada, p.id", pagina=pagina)


def obtener(pedido_id, bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM pedidos WHERE id = %s FOR UPDATE", (pedido_id,))
    return query_one(SELECT + FROM + " WHERE p.id = %s", (pedido_id,))


def detalle(pedido_id):
    """Ítems con lo ya programado/entregado en viajes no cancelados."""
    return query(
        """SELECT d.*, m.nombre AS material, m.codigo, u.abreviatura AS unidad, u.nombre AS unidad_nombre,
                  ub.abreviatura AS unidad_stock, m.stock_actual,
                  COALESCE((SELECT SUM(de.cantidad) FROM detalle_entregas de JOIN entregas e ON e.id = de.entrega_id
                            WHERE de.detalle_pedido_id = d.id AND e.estado NOT IN ('cancelada','no_entregada')), 0)
                      AS programado,
                  COALESCE((SELECT SUM(de.cantidad) FROM detalle_entregas de JOIN entregas e ON e.id = de.entrega_id
                            WHERE de.detalle_pedido_id = d.id AND e.estado = 'entregada'), 0) AS entregado
           FROM detalle_pedidos d JOIN materiales m ON m.id = d.material_id
           JOIN unidades u ON u.id = d.unidad_id JOIN unidades ub ON ub.id = m.unidad_id
           WHERE d.pedido_id = %s ORDER BY d.id""", (pedido_id,))


CAMPOS = ["fecha", "cliente_id", "usuario_id", "presupuesto_id", "tipo_entrega", "direccion_entrega", "localidad",
          "referencia", "zona_id", "fecha_solicitada", "horario", "vehiculo_id", "chofer_id", "subtotal",
          "descuento_general", "costo_envio", "total", "estado", "observaciones"]
CAMPOS_EDIT = [c for c in CAMPOS if c not in ("fecha", "usuario_id", "presupuesto_id", "estado")]


def insertar(datos):
    return execute(f"INSERT INTO pedidos ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
                   [datos.get(c) for c in CAMPOS])


def actualizar(pedido_id, datos):
    execute("UPDATE pedidos SET " + ", ".join(f"{c} = %s" for c in CAMPOS_EDIT) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS_EDIT] + [pedido_id])


def borrar_detalle(pedido_id):
    execute("DELETE FROM detalle_pedidos WHERE pedido_id = %s", (pedido_id,))


def insertar_detalle(pedido_id, linea):
    return execute(
        """INSERT INTO detalle_pedidos (pedido_id, material_id, unidad_id, cantidad, precio_unitario, descuento_pct,
           subtotal) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (pedido_id, linea["material_id"], linea["unidad_id"], linea["cantidad"], linea["precio_unitario"],
         linea["descuento_pct"], linea["subtotal"]))


def set_estado(pedido_id, estado):
    execute("UPDATE pedidos SET estado = %s WHERE id = %s", (estado, pedido_id))


def set_venta(pedido_id, venta_id):
    execute("UPDATE pedidos SET venta_id = %s WHERE id = %s", (venta_id, pedido_id))


def entregas(pedido_id):
    return query(
        """SELECT e.*, CONCAT(ch.nombre, ' ', ch.apellido) AS chofer, ve.patente
           FROM entregas e LEFT JOIN choferes ch ON ch.id = e.chofer_id LEFT JOIN vehiculos ve ON ve.id = e.vehiculo_id
           WHERE e.pedido_id = %s ORDER BY e.fecha, e.id""", (pedido_id,))


def contar_por_estado():
    return {f["estado"]: f["n"] for f in query("SELECT estado, COUNT(*) AS n FROM pedidos GROUP BY estado")}
