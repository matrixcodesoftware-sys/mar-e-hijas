"""Tablero principal."""
from flask import Blueprint, render_template
from flask_login import current_user

from ..models import caja as caja_model
from ..models import material as material_model
from ..services import caja_service, reporte_service
from ..utils.decoradores import permiso_requerido
from ..utils.fechas import hoy

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@bp.route("/")
@permiso_requerido("dashboard.ver")
def index():
    datos = reporte_service.dashboard()
    caja = caja_model.abierta()
    resumen_caja = caja_service.resumen(caja) if caja else None
    return render_template(
        "dashboard/index.html",
        d=datos,
        fecha_hoy=hoy(),
        caja=caja,
        resumen_caja=resumen_caja,
        finanzas=current_user.puede("dashboard.finanzas"),
        stock=reporte_service.stock_disponible(),
        bajo_stock=material_model.bajo_stock(6),
        entregas_hoy=reporte_service.entregas_del_dia(hoy()) if current_user.puede("entregas.ver") else [],
        ultimas_ventas=reporte_service.ultimas_ventas(6) if current_user.puede("ventas.ver") else [],
        deudores=reporte_service.clientes_con_deuda(5) if current_user.puede("cuentas.ver") else [],
    )
