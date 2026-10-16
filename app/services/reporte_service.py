"""Consultas de reportes y del dashboard (sólo lectura)."""
from datetime import date, timedelta
from decimal import Decimal

from ..database import query, query_one
from ..utils.fechas import fin_dia_exclusivo, hoy, inicio_dia

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _filtro_ventas(desde, hasta, cliente_id=None, usuario_id=None, material_id=None, alias="v"):
    where = [f"{alias}.estado = 'confirmada'", f"{alias}.fecha >= %s", f"{alias}.fecha < %s"]
    params = [inicio_dia(desde), fin_dia_exclusivo(hasta)]
    if cliente_id:
        where.append(f"{alias}.cliente_id = %s")
        params.append(cliente_id)
    if usuario_id:
        where.append(f"{alias}.usuario_id = %s")
        params.append(usuario_id)
    if material_id:
        where.append(f"EXISTS (SELECT 1 FROM detalle_ventas dx WHERE dx.venta_id = {alias}.id AND dx.material_id = %s)")
        params.append(material_id)
    return " AND ".join(where), params


# ------------------------------------------------------------------ ventas
def ventas_resumen(desde, hasta, **f):
    where, params = _filtro_ventas(desde, hasta, **f)
    r = query_one(
        f"""SELECT COUNT(*) AS cantidad, COALESCE(SUM(v.total), 0) AS facturacion,
                   COALESCE(SUM(v.costo_mercaderia), 0) AS costo, COALESCE(SUM(v.costo_envio), 0) AS fletes,
                   COALESCE(SUM(v.saldo_cta_cte), 0) AS a_cuenta, COALESCE(AVG(v.total), 0) AS ticket
            FROM ventas v WHERE {where}""", params)
    r["ganancia"] = Decimal(r["facturacion"]) - Decimal(r["costo"])
    if f.get("material_id"):
        m = query_one(
            f"""SELECT COALESCE(SUM(d.subtotal), 0) AS facturacion_material, COALESCE(SUM(d.cantidad_stock), 0) AS cantidad_material,
                       COALESCE(SUM(d.cantidad_stock * d.costo_unitario), 0) AS costo_material
                FROM detalle_ventas d JOIN ventas v ON v.id = d.venta_id WHERE {where} AND d.material_id = %s""",
            params + [f["material_id"]])
        r.update(m)
        r["ganancia_material"] = Decimal(m["facturacion_material"]) - Decimal(m["costo_material"])
    return r


def ventas_por_dia(desde, hasta, **f):
    where, params = _filtro_ventas(desde, hasta, **f)
    filas = {f_["dia"]: f_ for f_ in query(
        f"""SELECT DATE(v.fecha) AS dia, COUNT(*) AS cantidad, SUM(v.total) AS total, SUM(v.costo_mercaderia) AS costo
            FROM ventas v WHERE {where} GROUP BY DATE(v.fecha) ORDER BY dia""", params)}
    serie, d = [], desde
    while d <= hasta:
        fila = filas.get(d)
        serie.append({"etiqueta": d.strftime("%d/%m"), "fecha": d, "cantidad": fila["cantidad"] if fila else 0,
                      "total": fila["total"] if fila else 0,
                      "ganancia": (Decimal(fila["total"]) - Decimal(fila["costo"])) if fila else 0})
        d += timedelta(days=1)
    return serie


def ventas_por_mes(meses=12, **f):
    fin = hoy()
    inicio = date(fin.year, fin.month, 1)
    for _ in range(meses - 1):
        inicio = date(inicio.year - (inicio.month == 1), 12 if inicio.month == 1 else inicio.month - 1, 1)
    where, params = _filtro_ventas(inicio, fin, **f)
    filas = {(r["anio"], r["mes"]): r for r in query(
        f"""SELECT YEAR(v.fecha) AS anio, MONTH(v.fecha) AS mes, COUNT(*) AS cantidad, SUM(v.total) AS total,
                   SUM(v.costo_mercaderia) AS costo
            FROM ventas v WHERE {where} GROUP BY YEAR(v.fecha), MONTH(v.fecha)""", params)}
    serie, d = [], inicio
    for _ in range(meses):
        r = filas.get((d.year, d.month))
        serie.append({"etiqueta": f"{MESES[d.month - 1]} {str(d.year)[2:]}", "cantidad": r["cantidad"] if r else 0,
                      "total": r["total"] if r else 0,
                      "ganancia": (Decimal(r["total"]) - Decimal(r["costo"])) if r else 0})
        d = date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
    return serie


def ventas_por_vendedor(desde, hasta, **f):
    where, params = _filtro_ventas(desde, hasta, **f)
    return query(
        f"""SELECT CONCAT(u.nombre, ' ', u.apellido) AS vendedor, COUNT(*) AS cantidad, SUM(v.total) AS total,
                   SUM(v.total - v.costo_mercaderia) AS ganancia
            FROM ventas v JOIN usuarios u ON u.id = v.usuario_id WHERE {where}
            GROUP BY u.id, u.nombre, u.apellido ORDER BY total DESC""", params)


def metodos_pago(desde, hasta, **f):
    where, params = _filtro_ventas(desde, hasta, **f)
    filas = query(
        f"""SELECT mp.nombre, SUM(p.monto) AS total FROM pagos p JOIN ventas v ON v.id = p.venta_id
            JOIN metodos_pago mp ON mp.id = p.metodo_pago_id
            WHERE p.estado = 'registrado' AND {where} GROUP BY mp.nombre ORDER BY total DESC""", params)
    cc = query_one(f"SELECT COALESCE(SUM(v.saldo_cta_cte), 0) AS t FROM ventas v WHERE {where}", params)["t"]
    if cc:
        filas.append({"nombre": "Cuenta corriente", "total": cc})
    return filas


# ------------------------------------------------------------------ materiales
def ranking_materiales(desde, hasta, orden="cantidad", limite=None, **f):
    where, params = _filtro_ventas(desde, hasta, **{k: v for k, v in f.items() if k != "material_id"})
    orden_sql = {"cantidad": "cantidad DESC", "facturacion": "facturacion DESC",
                 "menos": "cantidad ASC", "ganancia": "ganancia DESC"}.get(orden, "cantidad DESC")
    sql = f"""SELECT m.id, m.codigo, m.nombre, u.abreviatura AS unidad,
                     COALESCE(SUM(d.cantidad_stock), 0) AS cantidad, COALESCE(SUM(d.subtotal), 0) AS facturacion,
                     COALESCE(SUM(d.subtotal - d.cantidad_stock * d.costo_unitario), 0) AS ganancia,
                     COUNT(DISTINCT d.venta_id) AS ventas
              FROM materiales m JOIN unidades u ON u.id = m.unidad_id
              LEFT JOIN (detalle_ventas d JOIN ventas v ON v.id = d.venta_id AND {where}) ON d.material_id = m.id
              WHERE m.activo = 1
              GROUP BY m.id, m.codigo, m.nombre, u.abreviatura ORDER BY {orden_sql}, m.nombre"""
    if limite:
        sql += " LIMIT %s"
        params = params + [limite]
    return query(sql, params)


def material_mas_vendido(desde, hasta):
    filas = [r for r in ranking_materiales(desde, hasta, "facturacion", 1) if r["facturacion"]]
    return filas[0] if filas else None


# ------------------------------------------------------------------ clientes
def ranking_clientes(desde, hasta, orden="consumo", limite=20):
    where, params = _filtro_ventas(desde, hasta)
    orden_sql = "total DESC" if orden == "consumo" else "compras DESC, total DESC"
    return query(
        f"""SELECT cl.id, cl.razon_social, cl.tipo, COUNT(*) AS compras, SUM(v.total) AS total, MAX(v.fecha) AS ultima,
                   COALESCE(cc.saldo, 0) AS saldo
            FROM ventas v JOIN clientes cl ON cl.id = v.cliente_id LEFT JOIN cuentas_corrientes cc ON cc.cliente_id = cl.id
            WHERE {where} GROUP BY cl.id, cl.razon_social, cl.tipo, cc.saldo ORDER BY {orden_sql} LIMIT %s""",
        params + [limite])


def clientes_con_deuda(limite=50):
    return query(
        """SELECT cl.id, cl.razon_social, cl.tipo, cl.telefono, cl.whatsapp, cc.saldo, cc.limite_credito,
                  (SELECT MAX(m.fecha) FROM movimientos_cuenta_corriente m WHERE m.cuenta_id = cc.id AND m.tipo = 'pago')
                      AS ultimo_pago
           FROM cuentas_corrientes cc JOIN clientes cl ON cl.id = cc.cliente_id
           WHERE cc.saldo > 0 ORDER BY cc.saldo DESC LIMIT %s""", (limite,))


# ------------------------------------------------------------------ entregas
def entregas_resumen(desde, hasta):
    return query_one(
        """SELECT COUNT(*) AS total, SUM(estado = 'entregada') AS entregadas,
                  SUM(estado IN ('pendiente','asignada','en_camino')) AS pendientes,
                  SUM(estado = 'cancelada') AS canceladas, SUM(estado = 'no_entregada') AS no_entregadas
           FROM entregas WHERE fecha BETWEEN %s AND %s""", (desde, hasta))


def entregas_por_chofer(desde, hasta):
    return query(
        """SELECT COALESCE(CONCAT(ch.nombre, ' ', ch.apellido), 'Sin asignar') AS nombre, COUNT(*) AS total,
                  SUM(e.estado = 'entregada') AS entregadas, SUM(e.estado IN ('pendiente','asignada','en_camino')) AS pendientes,
                  SUM(e.estado = 'no_entregada') AS no_entregadas, SUM(e.estado = 'cancelada') AS canceladas
           FROM entregas e LEFT JOIN choferes ch ON ch.id = e.chofer_id
           WHERE e.fecha BETWEEN %s AND %s GROUP BY ch.id, ch.nombre, ch.apellido ORDER BY entregadas DESC""",
        (desde, hasta))


def entregas_por_vehiculo(desde, hasta):
    return query(
        """SELECT COALESCE(v.patente, 'Sin asignar') AS nombre, tv.nombre AS tipo, COUNT(*) AS total,
                  SUM(e.estado = 'entregada') AS entregadas, SUM(e.estado IN ('pendiente','asignada','en_camino')) AS pendientes,
                  SUM(e.estado = 'no_entregada') AS no_entregadas, SUM(e.estado = 'cancelada') AS canceladas
           FROM entregas e LEFT JOIN vehiculos v ON v.id = e.vehiculo_id LEFT JOIN tipos_vehiculo tv ON tv.id = v.tipo_vehiculo_id
           WHERE e.fecha BETWEEN %s AND %s GROUP BY v.id, v.patente, tv.nombre ORDER BY entregadas DESC""",
        (desde, hasta))


def entregas_por_fecha(desde, hasta):
    filas = {r["fecha"]: r for r in query(
        """SELECT fecha, COUNT(*) AS total, SUM(estado = 'entregada') AS entregadas,
                  SUM(estado = 'cancelada') AS canceladas, SUM(estado IN ('pendiente','asignada','en_camino')) AS pendientes
           FROM entregas WHERE fecha BETWEEN %s AND %s GROUP BY fecha""", (desde, hasta))}
    serie, d = [], desde
    while d <= hasta:
        r = filas.get(d) or {}
        serie.append({"etiqueta": d.strftime("%d/%m"), "total": r.get("total", 0), "entregadas": r.get("entregadas") or 0,
                      "pendientes": r.get("pendientes") or 0, "canceladas": r.get("canceladas") or 0})
        d += timedelta(days=1)
    return serie


# ------------------------------------------------------------------ dashboard
def dashboard(finanzas=True):
    h = hoy()
    inicio_mes = h.replace(day=1)
    dia = ventas_resumen(h, h)
    mes = ventas_resumen(inicio_mes, h)
    gastos_mes = query_one(
        "SELECT COALESCE(SUM(monto), 0) AS t FROM gastos WHERE estado='registrado' AND fecha >= %s AND fecha < %s",
        (inicio_dia(inicio_mes), fin_dia_exclusivo(h)))["t"]
    pedidos_pend = query_one("SELECT COUNT(*) AS n FROM pedidos WHERE estado IN ('pendiente','confirmado','preparando','listo')")["n"]
    entregas_hoy = query_one(
        """SELECT COUNT(*) AS total, SUM(estado = 'entregada') AS entregadas FROM entregas
           WHERE fecha = %s AND estado <> 'cancelada'""", (h,))
    deuda = query_one("SELECT COUNT(*) AS n, COALESCE(SUM(saldo), 0) AS t FROM cuentas_corrientes WHERE saldo > 0")
    stock = query_one(
        """SELECT COUNT(*) AS materiales, SUM(stock_actual <= stock_minimo) AS bajo,
                  COALESCE(SUM(stock_actual * precio_compra), 0) AS valor
           FROM materiales WHERE activo = 1""")
    return {
        "ventas_dia": dia, "ventas_mes": mes, "gastos_mes": gastos_mes,
        "ganancia_mes": Decimal(mes["ganancia"]) - Decimal(gastos_mes),
        "pedidos_pendientes": pedidos_pend, "entregas_hoy": entregas_hoy, "deuda": deuda, "stock": stock,
        "mas_vendido": material_mas_vendido(inicio_mes, h),
    }


def stock_disponible():
    return query(
        """SELECT m.id, m.nombre, m.stock_actual, m.stock_minimo, u.abreviatura
           FROM materiales m JOIN unidades u ON u.id = m.unidad_id WHERE m.activo = 1 ORDER BY m.nombre""")


def ultimas_ventas(limite=8):
    return query(
        """SELECT v.id, v.fecha, v.total, v.estado, v.estado_pago, cl.razon_social AS cliente
           FROM ventas v JOIN clientes cl ON cl.id = v.cliente_id ORDER BY v.fecha DESC, v.id DESC LIMIT %s""",
        (limite,))


def entregas_del_dia(fecha):
    from ..models import entrega as entrega_model

    return query(
        entrega_model.SELECT + entrega_model.FROM + " WHERE e.fecha = %s AND e.estado <> 'cancelada' "
        "ORDER BY FIELD(e.estado,'en_camino','asignada','pendiente','no_entregada','entregada'), e.horario", (fecha,))
