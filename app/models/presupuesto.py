"""Presupuestos y su detalle."""
from ..database import execute, query, query_one
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar

SELECT = """
    SELECT p.*, cl.razon_social AS cliente, cl.documento AS cliente_documento, cl.telefono AS cliente_telefono,
           cl.whatsapp AS cliente_whatsapp, cl.email AS cliente_email, cl.direccion AS cliente_direccion,
           cl.localidad AS cliente_localidad, cl.condicion_iva AS cliente_condicion_iva,
           z.nombre AS zona, CONCAT(u.nombre, ' ', u.apellido) AS usuario
"""
FROM = """
    FROM presupuestos p
    JOIN clientes cl ON cl.id = p.cliente_id
    JOIN usuarios u ON u.id = p.usuario_id
    LEFT JOIN zonas_entrega z ON z.id = p.zona_id
"""


def vencer_automaticamente(hoy):
    execute("UPDATE presupuestos SET estado = 'vencido' WHERE estado IN ('pendiente','enviado') "
            "AND fecha_vencimiento < %s", (hoy,))


def buscar(estado=None, cliente_id=None, desde=None, hasta=None, numero=None, pagina=None):
    where, params = ["1=1"], []
    if numero:
        where.append("p.id = %s")
        params.append(numero)
    if estado:
        where.append("p.estado = %s")
        params.append(estado)
    if cliente_id:
        where.append("p.cliente_id = %s")
        params.append(cliente_id)
    if desde:
        where.append("p.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("p.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    return paginar(SELECT, FROM + " WHERE " + " AND ".join(where), params, "ORDER BY p.fecha DESC, p.id DESC",
                   pagina=pagina)


def obtener(presupuesto_id, bloquear=False):
    if bloquear:
        return query_one("SELECT * FROM presupuestos WHERE id = %s FOR UPDATE", (presupuesto_id,))
    return query_one(SELECT + FROM + " WHERE p.id = %s", (presupuesto_id,))


def detalle(presupuesto_id):
    return query(
        """SELECT d.*, m.nombre AS material, m.codigo, u.abreviatura AS unidad, u.nombre AS unidad_nombre,
                  ub.abreviatura AS unidad_stock, m.stock_actual
           FROM detalle_presupuestos d JOIN materiales m ON m.id = d.material_id
           JOIN unidades u ON u.id = d.unidad_id JOIN unidades ub ON ub.id = m.unidad_id
           WHERE d.presupuesto_id = %s ORDER BY d.id""", (presupuesto_id,))


CAMPOS = ["fecha", "fecha_vencimiento", "cliente_id", "usuario_id", "tipo_entrega", "zona_id", "direccion_entrega",
          "subtotal", "descuento_general", "costo_envio", "total", "estado", "observaciones"]
CAMPOS_EDIT = ["fecha_vencimiento", "cliente_id", "tipo_entrega", "zona_id", "direccion_entrega", "subtotal",
               "descuento_general", "costo_envio", "total", "observaciones"]


def insertar(datos):
    return execute(f"INSERT INTO presupuestos ({', '.join(CAMPOS)}) VALUES ({', '.join(['%s'] * len(CAMPOS))})",
                   [datos.get(c) for c in CAMPOS])


def actualizar(presupuesto_id, datos):
    execute("UPDATE presupuestos SET " + ", ".join(f"{c} = %s" for c in CAMPOS_EDIT) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS_EDIT] + [presupuesto_id])


def borrar_detalle(presupuesto_id):
    execute("DELETE FROM detalle_presupuestos WHERE presupuesto_id = %s", (presupuesto_id,))


def insertar_detalle(presupuesto_id, ln):
    return execute(
        """INSERT INTO detalle_presupuestos (presupuesto_id, material_id, unidad_id, cantidad, precio_unitario,
           descuento_pct, subtotal) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (presupuesto_id, ln["material_id"], ln["unidad_id"], ln["cantidad"], ln["precio_unitario"],
         ln["descuento_pct"], ln["subtotal"]))


def set_estado(presupuesto_id, estado):
    execute("UPDATE presupuestos SET estado = %s WHERE id = %s", (estado, presupuesto_id))


def marcar_convertido(presupuesto_id, venta_id=None, pedido_id=None):
    if venta_id:
        execute("UPDATE presupuestos SET estado='aceptado', venta_id=%s WHERE id=%s", (venta_id, presupuesto_id))
    if pedido_id:
        execute("UPDATE presupuestos SET estado='aceptado', pedido_id=%s WHERE id=%s", (pedido_id, presupuesto_id))


def desvincular_venta(presupuesto_id):
    execute("UPDATE presupuestos SET venta_id = NULL WHERE id = %s", (presupuesto_id,))
