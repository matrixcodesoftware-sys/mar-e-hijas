"""Consultas del historial de operaciones."""
from ..database import execute
from ..utils.fechas import fin_dia_exclusivo, inicio_dia
from ..utils.paginacion import paginar


def insertar(fecha, usuario_id, accion, modulo, registro_id, descripcion, ip):
    execute(
        """INSERT INTO historial_operaciones (fecha, usuario_id, accion, modulo, registro_id, descripcion, ip)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (fecha, usuario_id, accion, modulo, registro_id, descripcion[:500], ip),
    )


def buscar(usuario_id=None, modulo=None, accion=None, desde=None, hasta=None, texto=None):
    where, params = ["1=1"], []
    if usuario_id:
        where.append("h.usuario_id = %s")
        params.append(usuario_id)
    if modulo:
        where.append("h.modulo = %s")
        params.append(modulo)
    if accion:
        where.append("h.accion = %s")
        params.append(accion)
    if desde:
        where.append("h.fecha >= %s")
        params.append(inicio_dia(desde))
    if hasta:
        where.append("h.fecha < %s")
        params.append(fin_dia_exclusivo(hasta))
    if texto:
        where.append("h.descripcion LIKE %s")
        params.append(f"%{texto}%")
    return paginar(
        "SELECT h.*, CONCAT(u.nombre, ' ', u.apellido) AS usuario",
        "FROM historial_operaciones h LEFT JOIN usuarios u ON u.id = h.usuario_id WHERE " + " AND ".join(where),
        params,
        "ORDER BY h.fecha DESC, h.id DESC",
    )


MODULOS = [
    "auth", "ventas", "pedidos", "presupuestos", "entregas", "materiales", "stock", "clientes",
    "cuentas", "proveedores", "vehiculos", "choferes", "caja", "gastos", "usuarios", "configuracion",
    "facturacion",
]
