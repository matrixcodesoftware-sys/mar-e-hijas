"""Cuentas corrientes de clientes y sus movimientos."""
from ..database import execute, query, query_one
from ..utils.fechas import fin_dia_exclusivo, inicio_dia


def por_cliente(cliente_id, bloquear=False):
    return query_one("SELECT * FROM cuentas_corrientes WHERE cliente_id = %s" + (" FOR UPDATE" if bloquear else ""),
                     (cliente_id,))


def crear(cliente_id, limite_credito=0):
    return execute("INSERT INTO cuentas_corrientes (cliente_id, limite_credito, saldo) VALUES (%s, %s, 0)",
                   (cliente_id, limite_credito))


def set_limite(cliente_id, limite):
    execute("UPDATE cuentas_corrientes SET limite_credito = %s WHERE cliente_id = %s", (limite, cliente_id))


def set_saldo(cuenta_id, saldo, fecha):
    execute("UPDATE cuentas_corrientes SET saldo = %s, actualizado_en = %s WHERE id = %s", (saldo, fecha, cuenta_id))


def insertar_movimiento(datos):
    return execute(
        """INSERT INTO movimientos_cuenta_corriente (cuenta_id, fecha, tipo, concepto, debe, haber, saldo_resultante,
           venta_id, pago_id, usuario_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (datos["cuenta_id"], datos["fecha"], datos["tipo"], datos["concepto"][:200], datos.get("debe", 0),
         datos.get("haber", 0), datos["saldo_resultante"], datos.get("venta_id"), datos.get("pago_id"),
         datos["usuario_id"]))


def movimientos(cuenta_id, desde=None, hasta=None):
    where, params = ["m.cuenta_id = %s"], [cuenta_id]
    if desde:
        where.append("m.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("m.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    return query(
        "SELECT m.*, CONCAT(u.nombre, ' ', u.apellido) AS usuario FROM movimientos_cuenta_corriente m "
        "JOIN usuarios u ON u.id = m.usuario_id WHERE " + " AND ".join(where) + " ORDER BY m.fecha, m.id", params)


def saldo_al(cuenta_id, fecha_inicio):
    """Saldo inmediatamente anterior a una fecha (para el saldo inicial de un resumen)."""
    fila = query_one(
        """SELECT saldo_resultante FROM movimientos_cuenta_corriente WHERE cuenta_id = %s AND fecha < %s
           ORDER BY fecha DESC, id DESC LIMIT 1""", (cuenta_id, inicio_dia(fecha_inicio)))
    return fila["saldo_resultante"] if fila else 0


def total_deuda():
    return query_one("SELECT COUNT(*) AS clientes, COALESCE(SUM(saldo), 0) AS total FROM cuentas_corrientes WHERE saldo > 0")
