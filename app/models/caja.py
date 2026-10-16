"""Cajas y movimientos de caja."""
from ..database import execute, query, query_one
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar

SELECT_CAJA = """
    SELECT c.*, CONCAT(ua.nombre, ' ', ua.apellido) AS usuario_apertura,
           CONCAT(uc.nombre, ' ', uc.apellido) AS usuario_cierre
    FROM cajas c
    JOIN usuarios ua ON ua.id = c.usuario_apertura_id
    LEFT JOIN usuarios uc ON uc.id = c.usuario_cierre_id
"""


def abierta(bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM cajas WHERE estado = 'abierta' FOR UPDATE")
    return query_one(SELECT_CAJA + " WHERE c.estado = 'abierta'")


def obtener(caja_id):
    return query_one(SELECT_CAJA + " WHERE c.id = %s", (caja_id,))


def crear(usuario_id, fecha, monto_inicial, observaciones=None):
    return execute(
        "INSERT INTO cajas (usuario_apertura_id, fecha_apertura, monto_inicial, estado, observaciones) "
        "VALUES (%s, %s, %s, 'abierta', %s)", (usuario_id, fecha, monto_inicial, observaciones))


def cerrar(caja_id, datos):
    execute(
        """UPDATE cajas SET estado='cerrada', usuario_cierre_id=%s, fecha_cierre=%s, total_efectivo_ing=%s,
           total_efectivo_egr=%s, total_transferencias=%s, total_tarjetas=%s, total_otros=%s,
           saldo_esperado=%s, saldo_declarado=%s, diferencia=%s,
           observaciones=CONCAT_WS(' | ', observaciones, %s) WHERE id=%s""",
        (datos["usuario_id"], datos["fecha"], datos["total_efectivo_ing"], datos["total_efectivo_egr"],
         datos["total_transferencias"], datos["total_tarjetas"], datos["total_otros"], datos["saldo_esperado"],
         datos["saldo_declarado"], datos["diferencia"], datos.get("observaciones"), caja_id))


def insertar_movimiento(datos):
    return execute(
        """INSERT INTO movimientos_caja (caja_id, fecha, tipo, sentido, metodo_pago_id, monto, concepto, venta_id,
           pago_id, gasto_id, pago_proveedor_id, usuario_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (datos["caja_id"], datos["fecha"], datos["tipo"], datos["sentido"], datos["metodo_pago_id"], datos["monto"],
         datos["concepto"][:200], datos.get("venta_id"), datos.get("pago_id"), datos.get("gasto_id"),
         datos.get("pago_proveedor_id"), datos["usuario_id"]))


def movimientos(caja_id):
    return query(
        """SELECT mc.*, mp.nombre AS metodo, mp.grupo, CONCAT(u.nombre, ' ', u.apellido) AS usuario
           FROM movimientos_caja mc JOIN metodos_pago mp ON mp.id = mc.metodo_pago_id
           JOIN usuarios u ON u.id = mc.usuario_id
           WHERE mc.caja_id = %s ORDER BY mc.fecha DESC, mc.id DESC""", (caja_id,))


def totales(caja_id):
    """Totales por grupo de método y sentido."""
    return query(
        """SELECT mp.grupo, mc.sentido, mc.tipo, SUM(mc.monto) AS total
           FROM movimientos_caja mc JOIN metodos_pago mp ON mp.id = mc.metodo_pago_id
           WHERE mc.caja_id = %s GROUP BY mp.grupo, mc.sentido, mc.tipo""", (caja_id,))


def historial(desde=None, hasta=None, pagina=None):
    where, params = ["c.estado = 'cerrada'"], []
    if desde:
        where.append("c.fecha_apertura >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("c.fecha_apertura < %s")
        params.append(fin_dia_exclusivo(hasta))
    return paginar(
        "SELECT c.*, CONCAT(ua.nombre, ' ', ua.apellido) AS usuario_apertura, "
        "CONCAT(uc.nombre, ' ', uc.apellido) AS usuario_cierre",
        "FROM cajas c JOIN usuarios ua ON ua.id = c.usuario_apertura_id "
        "LEFT JOIN usuarios uc ON uc.id = c.usuario_cierre_id WHERE " + " AND ".join(where),
        params, "ORDER BY c.fecha_apertura DESC", pagina=pagina)
