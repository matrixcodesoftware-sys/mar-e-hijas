"""Proveedores, su cuenta y sus pagos."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

CAMPOS = ["razon_social", "cuit", "telefono", "email", "direccion", "localidad", "contacto", "observaciones", "activo"]


def buscar(texto=None, activo=None, con_deuda=False, pagina=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(p.razon_social LIKE %s OR p.cuit LIKE %s OR p.contacto LIKE %s)")
        params += [f"%{texto}%"] * 3
    if activo in ("0", "1"):
        where.append("p.activo = %s")
        params.append(int(activo))
    if con_deuda:
        where.append("p.saldo_cuenta > 0")
    return paginar("SELECT p.*", "FROM proveedores p WHERE " + " AND ".join(where), params,
                   "ORDER BY p.razon_social", pagina=pagina)


def obtener(proveedor_id, bloquear=False):
    return query_one("SELECT * FROM proveedores WHERE id = %s" + (" FOR UPDATE" if bloquear else ""), (proveedor_id,))


def autocompletar(texto, limite=12):
    like = f"%{texto}%"
    return query(
        "SELECT * FROM proveedores WHERE activo = 1 AND (razon_social LIKE %s OR cuit LIKE %s) "
        "ORDER BY razon_social LIMIT %s", (like, like, limite))


def opciones():
    return [(p["id"], p["razon_social"]) for p in query(
        "SELECT id, razon_social FROM proveedores WHERE activo = 1 ORDER BY razon_social")]


def existe_cuit(cuit, excluir_id=None):
    if not cuit:
        return False
    return query_one("SELECT id FROM proveedores WHERE cuit = %s AND id <> %s", (cuit, excluir_id or 0)) is not None


def crear(datos):
    return execute(
        f"INSERT INTO proveedores ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
        [datos.get(c) for c in CAMPOS])


def actualizar(proveedor_id, datos):
    execute("UPDATE proveedores SET " + ", ".join(f"{c} = %s" for c in CAMPOS) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS] + [proveedor_id])


def set_saldo(proveedor_id, saldo):
    execute("UPDATE proveedores SET saldo_cuenta = %s WHERE id = %s", (saldo, proveedor_id))


def insertar_movimiento(datos):
    return execute(
        """INSERT INTO movimientos_cuenta_proveedor (proveedor_id, fecha, tipo, concepto, cargo, abono,
           saldo_resultante, movimiento_stock_id, pago_proveedor_id, usuario_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (datos["proveedor_id"], datos["fecha"], datos["tipo"], datos["concepto"], datos.get("cargo", 0),
         datos.get("abono", 0), datos["saldo_resultante"], datos.get("movimiento_stock_id"),
         datos.get("pago_proveedor_id"), datos["usuario_id"]))


def insertar_pago(datos):
    return execute(
        """INSERT INTO pagos_proveedores (fecha, proveedor_id, metodo_pago_id, monto, caja_id, referencia,
           usuario_id, observaciones) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (datos["fecha"], datos["proveedor_id"], datos["metodo_pago_id"], datos["monto"], datos.get("caja_id"),
         datos.get("referencia"), datos["usuario_id"], datos.get("observaciones")))


def movimientos(proveedor_id, limite=50):
    return query(
        """SELECT m.*, CONCAT(u.nombre,' ',u.apellido) AS usuario FROM movimientos_cuenta_proveedor m
           JOIN usuarios u ON u.id = m.usuario_id
           WHERE m.proveedor_id = %s ORDER BY m.fecha DESC, m.id DESC LIMIT %s""", (proveedor_id, limite))


def compras(proveedor_id, limite=20):
    return query(
        """SELECT ms.*, m.nombre AS material, u.abreviatura AS unidad FROM movimientos_stock ms
           JOIN materiales m ON m.id = ms.material_id JOIN unidades u ON u.id = ms.unidad_id
           WHERE ms.proveedor_id = %s AND ms.tipo = 'entrada' ORDER BY ms.fecha DESC LIMIT %s""",
        (proveedor_id, limite))


def pagos(proveedor_id, limite=20):
    return query(
        """SELECT pp.*, mp.nombre AS metodo FROM pagos_proveedores pp JOIN metodos_pago mp ON mp.id = pp.metodo_pago_id
           WHERE pp.proveedor_id = %s ORDER BY pp.fecha DESC LIMIT %s""", (proveedor_id, limite))


def materiales_suministrados(proveedor_id):
    return query(
        """SELECT m.id, m.nombre, u.abreviatura, COUNT(ms.id) AS entradas, SUM(ms.cantidad) AS cantidad,
                  SUM(ms.costo_total) AS costo, MAX(ms.fecha) AS ultima
           FROM movimientos_stock ms JOIN materiales m ON m.id = ms.material_id JOIN unidades u ON u.id = m.unidad_id
           WHERE ms.proveedor_id = %s AND ms.tipo = 'entrada'
           GROUP BY m.id, m.nombre, u.abreviatura ORDER BY costo DESC""", (proveedor_id,))
