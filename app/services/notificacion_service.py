"""Notificaciones calculadas en el momento según permisos del usuario."""
from datetime import timedelta

from flask import url_for

from ..database import query_one
from ..models import caja as caja_model
from ..models import configuracion
from ..models import flota
from ..utils.fechas import hoy
from ..utils.formato import fecha


def para(usuario):
    h = hoy()
    notifs = []
    if usuario.puede("stock.ver"):
        n = query_one("SELECT COUNT(*) AS n FROM materiales WHERE activo = 1 AND stock_actual <= stock_minimo")["n"]
        if n:
            notifs.append({"titulo": "Stock bajo", "texto": f"{n} material(es) en o bajo el stock mínimo",
                           "url": url_for("stock.index", bajo=1), "icono": "alert", "color": "rojo"})
    if usuario.puede("entregas.ver"):
        r = query_one("""SELECT COUNT(*) AS n FROM entregas WHERE fecha = %s
                         AND estado IN ('pendiente','asignada','en_camino')""", (h,))
        if r["n"]:
            notifs.append({"titulo": "Entregas de hoy", "texto": f"{r['n']} entrega(s) pendientes para hoy",
                           "url": url_for("entregas.index", rapido="hoy"), "icono": "truck", "color": "azul"})
        sin = query_one("SELECT COUNT(*) AS n FROM entregas WHERE estado = 'pendiente' AND fecha <= %s",
                        (h + timedelta(days=1),))["n"]
        if sin:
            notifs.append({"titulo": "Entregas sin asignar", "texto": f"{sin} viaje(s) sin chofer/camión para hoy o mañana",
                           "url": url_for("entregas.index", estado="pendiente", buscar=1), "icono": "route",
                           "color": "ambar"})
    if usuario.puede("pedidos.ver"):
        n = query_one("""SELECT COUNT(*) AS n FROM pedidos WHERE fecha_solicitada < %s
                         AND estado NOT IN ('entregado','cancelado')""", (h,))["n"]
        if n:
            notifs.append({"titulo": "Pedidos atrasados", "texto": f"{n} pedido(s) con fecha solicitada vencida",
                           "url": url_for("pedidos.index", rapido="atrasados"), "icono": "clipboard", "color": "rojo"})
    if usuario.puede("presupuestos.ver"):
        n = query_one("""SELECT COUNT(*) AS n FROM presupuestos WHERE estado IN ('pendiente','enviado')
                         AND fecha_vencimiento BETWEEN %s AND %s""", (h, h + timedelta(days=2)))["n"]
        if n:
            notifs.append({"titulo": "Presupuestos por vencer", "texto": f"{n} presupuesto(s) vencen en 48 h",
                           "url": url_for("presupuestos.index", estado="pendiente", buscar=1), "icono": "file",
                           "color": "ambar"})
    if usuario.puede("choferes.ver"):
        dias = configuracion.get_int("alerta_licencia_dias", 30)
        for ch in flota.licencias_por_vencer(h + timedelta(days=dias))[:3]:
            vencida = ch["licencia_vencimiento"] < h
            notifs.append({"titulo": "Licencia vencida" if vencida else "Licencia por vencer",
                           "texto": f"{ch['nombre']} {ch['apellido']}: {fecha(ch['licencia_vencimiento'])}",
                           "url": url_for("choferes.ver", chofer_id=ch["id"]), "icono": "id",
                           "color": "rojo" if vencida else "ambar"})
    if usuario.puede("caja.operar") and not caja_model.abierta():
        notifs.append({"titulo": "Caja cerrada", "texto": "Abrí la caja para registrar cobros",
                       "url": url_for("caja.index"), "icono": "cash", "color": "ambar"})
    if usuario.puede("entregas.propias") and usuario.chofer_id:
        n = query_one("""SELECT COUNT(*) AS n FROM entregas WHERE chofer_id = %s AND fecha = %s
                         AND estado IN ('asignada','en_camino')""", (usuario.chofer_id, h))["n"]
        if n:
            notifs.append({"titulo": "Tus entregas de hoy", "texto": f"Tenés {n} entrega(s) asignada(s)",
                           "url": url_for("entregas.mis_entregas"), "icono": "truck", "color": "azul"})
    return notifs
