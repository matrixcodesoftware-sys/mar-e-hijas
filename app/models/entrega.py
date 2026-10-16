"""Entregas (viajes) y su carga."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

SELECT = """
    SELECT e.*, cl.razon_social AS cliente, cl.telefono AS cliente_telefono, cl.whatsapp AS cliente_whatsapp,
           CONCAT(ch.nombre, ' ', ch.apellido) AS chofer, ch.telefono AS chofer_telefono,
           ve.patente, ve.capacidad, uc.abreviatura AS unidad_capacidad, tv.nombre AS tipo_vehiculo,
           (SELECT GROUP_CONCAT(CONCAT(TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM de.cantidad)), ' ', ud.abreviatura, ' ', m.nombre)
                   ORDER BY de.id SEPARATOR ' · ')
              FROM detalle_entregas de JOIN materiales m ON m.id = de.material_id JOIN unidades ud ON ud.id = de.unidad_id
             WHERE de.entrega_id = e.id) AS carga
"""
FROM = """
    FROM entregas e
    JOIN clientes cl ON cl.id = e.cliente_id
    LEFT JOIN choferes ch ON ch.id = e.chofer_id
    LEFT JOIN vehiculos ve ON ve.id = e.vehiculo_id
    LEFT JOIN unidades uc ON uc.id = ve.unidad_capacidad_id
    LEFT JOIN tipos_vehiculo tv ON tv.id = ve.tipo_vehiculo_id
"""


def buscar(estado=None, chofer_id=None, vehiculo_id=None, desde=None, hasta=None, cliente_id=None, activas=False,
           pagina=None):
    where, params = ["1=1"], []
    if estado:
        where.append("e.estado = %s")
        params.append(estado)
    if activas:
        where.append("e.estado IN ('pendiente','asignada','en_camino')")
    if chofer_id:
        where.append("e.chofer_id = %s")
        params.append(chofer_id)
    if vehiculo_id:
        where.append("e.vehiculo_id = %s")
        params.append(vehiculo_id)
    if desde:
        where.append("e.fecha >= %s")
        params.append(desde)
    if hasta:
        where.append("e.fecha <= %s")
        params.append(hasta)
    if cliente_id:
        where.append("e.cliente_id = %s")
        params.append(cliente_id)
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params,
                   "ORDER BY e.fecha, e.horario IS NULL, e.horario, e.id", pagina=pagina)


def obtener(entrega_id, bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM entregas WHERE id = %s FOR UPDATE", (entrega_id,))
    return query_one(SELECT + FROM + " WHERE e.id = %s", (entrega_id,))


def detalle(entrega_id):
    return query(
        """SELECT de.*, m.nombre AS material, u.abreviatura AS unidad, u.nombre AS unidad_nombre
           FROM detalle_entregas de JOIN materiales m ON m.id = de.material_id JOIN unidades u ON u.id = de.unidad_id
           WHERE de.entrega_id = %s ORDER BY de.id""", (entrega_id,))


def de_chofer(chofer_id, fecha_desde, fecha_hasta):
    return query(SELECT + FROM + """ WHERE e.chofer_id = %s AND e.fecha BETWEEN %s AND %s
                 AND e.estado <> 'cancelada'
                 ORDER BY e.fecha, FIELD(e.estado, 'en_camino', 'asignada', 'pendiente', 'no_entregada', 'entregada'),
                          e.horario IS NULL, e.horario, e.id""",
                 (chofer_id, fecha_desde, fecha_hasta))


def de_venta(venta_id):
    return query(SELECT + FROM + " WHERE e.venta_id = %s ORDER BY e.id", (venta_id,))


CAMPOS = ["pedido_id", "venta_id", "cliente_id", "direccion", "localidad", "referencia", "telefono_contacto",
          "chofer_id", "vehiculo_id", "fecha", "horario", "estado", "observaciones", "usuario_id"]


def insertar(datos):
    return execute(f"INSERT INTO entregas ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
                   [datos.get(c) for c in CAMPOS])


def insertar_detalle(entrega_id, material_id, unidad_id, cantidad, detalle_pedido_id=None):
    return execute(
        "INSERT INTO detalle_entregas (entrega_id, detalle_pedido_id, material_id, unidad_id, cantidad) "
        "VALUES (%s, %s, %s, %s, %s)", (entrega_id, detalle_pedido_id, material_id, unidad_id, cantidad))


def asignar(entrega_id, chofer_id, vehiculo_id, fecha, horario, estado, observaciones):
    execute("UPDATE entregas SET chofer_id=%s, vehiculo_id=%s, fecha=%s, horario=%s, estado=%s, observaciones=%s "
            "WHERE id=%s", (chofer_id, vehiculo_id, fecha, horario, estado, observaciones, entrega_id))


def set_estado(entrega_id, estado, **extra):
    campos = {"estado": estado, **extra}
    execute("UPDATE entregas SET " + ", ".join(f"{k} = %s" for k in campos) + " WHERE id = %s",
            list(campos.values()) + [entrega_id])


def cancelar_pendientes_de_venta(venta_id):
    execute("UPDATE entregas SET estado='cancelada' WHERE venta_id=%s AND estado IN ('pendiente','asignada')",
            (venta_id,))


def entregadas_de_venta(venta_id, pedido_id=None):
    """Viajes ya realizados o en curso de la venta (o de su pedido de origen)."""
    return query_one(
        """SELECT COUNT(*) AS n FROM entregas WHERE (venta_id = %s OR (pedido_id IS NOT NULL AND pedido_id = %s))
           AND estado IN ('entregada','en_camino')""", (venta_id, pedido_id or 0))["n"]


def vincular_pedido_a_venta(pedido_id, venta_id):
    execute("UPDATE entregas SET venta_id = %s WHERE pedido_id = %s", (venta_id, pedido_id))


def contar_hoy(fecha):
    return query_one(
        """SELECT COUNT(*) AS total, SUM(estado = 'entregada') AS entregadas,
                  SUM(estado IN ('pendiente','asignada','en_camino')) AS pendientes
           FROM entregas WHERE fecha = %s AND estado <> 'cancelada'""", (fecha,))
