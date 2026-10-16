"""Clientes."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

SELECT = """
    SELECT cl.*, z.nombre AS zona, cc.saldo, cc.limite_credito, cc.id AS cuenta_id
"""
FROM = """
    FROM clientes cl
    LEFT JOIN zonas_entrega z ON z.id = cl.zona_id
    LEFT JOIN cuentas_corrientes cc ON cc.cliente_id = cl.id
"""

CAMPOS = ["tipo", "razon_social", "documento_tipo", "documento", "condicion_iva", "telefono", "whatsapp",
          "email", "direccion", "localidad", "zona_id", "referencia_ubicacion", "observaciones", "activo"]


def buscar(texto=None, tipo=None, localidad=None, activo=None, con_deuda=False, pagina=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(cl.razon_social LIKE %s OR cl.documento LIKE %s OR cl.telefono LIKE %s OR cl.whatsapp LIKE %s)")
        params += [f"%{texto}%"] * 4
    if tipo:
        where.append("cl.tipo = %s")
        params.append(tipo)
    if localidad:
        where.append("cl.localidad LIKE %s")
        params.append(f"%{localidad}%")
    if activo in ("0", "1"):
        where.append("cl.activo = %s")
        params.append(int(activo))
    if con_deuda:
        where.append("cc.saldo > 0")
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params,
                   "ORDER BY " + ("cc.saldo DESC" if con_deuda else "cl.razon_social"), pagina=pagina)


def obtener(cliente_id):
    return query_one(SELECT + FROM + " WHERE cl.id = %s", (cliente_id,))


def autocompletar(texto, limite=12):
    like = f"%{texto}%"
    return query(
        SELECT + FROM + """ WHERE cl.activo = 1 AND (cl.razon_social LIKE %s OR cl.documento LIKE %s
        OR cl.telefono LIKE %s) ORDER BY cl.razon_social LIMIT %s""",
        (like, like, like, limite),
    )


def existe_documento(documento, excluir_id=None):
    if not documento:
        return False
    return query_one("SELECT id FROM clientes WHERE documento = %s AND id <> %s", (documento, excluir_id or 0)) is not None


def crear(datos):
    return execute(
        f"INSERT INTO clientes ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
        [datos.get(c) for c in CAMPOS],
    )


def actualizar(cliente_id, datos):
    execute("UPDATE clientes SET " + ", ".join(f"{c} = %s" for c in CAMPOS) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS] + [cliente_id])


def con_deuda(limite=10):
    return query(
        SELECT + FROM + " WHERE cc.saldo > 0 ORDER BY cc.saldo DESC LIMIT %s", (limite,)
    )


def estadisticas(cliente_id):
    return query_one(
        """SELECT COUNT(*) AS ventas, COALESCE(SUM(total), 0) AS facturado, MAX(fecha) AS ultima_compra
           FROM ventas WHERE cliente_id = %s AND estado = 'confirmada'""",
        (cliente_id,),
    )


def ventas(cliente_id, limite=15):
    return query(
        """SELECT id, fecha, total, estado, estado_pago, tipo_entrega FROM ventas
           WHERE cliente_id = %s ORDER BY fecha DESC LIMIT %s""",
        (cliente_id, limite),
    )


def pedidos(cliente_id, limite=15):
    return query(
        """SELECT id, fecha, fecha_solicitada, total, estado FROM pedidos
           WHERE cliente_id = %s ORDER BY fecha DESC LIMIT %s""",
        (cliente_id, limite),
    )


def presupuestos(cliente_id, limite=15):
    return query(
        """SELECT id, fecha, fecha_vencimiento, total, estado FROM presupuestos
           WHERE cliente_id = %s ORDER BY fecha DESC LIMIT %s""",
        (cliente_id, limite),
    )


def pagos(cliente_id, limite=15):
    return query(
        """SELECT p.*, mp.nombre AS metodo FROM pagos p JOIN metodos_pago mp ON mp.id = p.metodo_pago_id
           WHERE p.cliente_id = %s ORDER BY p.fecha DESC LIMIT %s""",
        (cliente_id, limite),
    )


def materiales_frecuentes(cliente_id, limite=5):
    return query(
        """SELECT m.nombre, u.abreviatura, SUM(dv.cantidad_stock) AS cantidad, SUM(dv.subtotal) AS importe
           FROM detalle_ventas dv JOIN ventas v ON v.id = dv.venta_id
           JOIN materiales m ON m.id = dv.material_id JOIN unidades u ON u.id = m.unidad_id
           WHERE v.cliente_id = %s AND v.estado = 'confirmada'
           GROUP BY m.id, m.nombre, u.abreviatura ORDER BY importe DESC LIMIT %s""",
        (cliente_id, limite),
    )
