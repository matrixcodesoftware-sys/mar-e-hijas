"""Gastos."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import caja as caja_model
from ..models import catalogos, flota
from ..models import gasto as gasto_model
from ..models import proveedor as proveedor_model
from ..services import gasto_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError, ValidacionError
from ..utils.fechas import hoy, rango_periodo
from ..utils.validadores import Validador
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda

bp = Blueprint("gastos", __name__, url_prefix="/gastos")


@bp.route("/")
@permiso_requerido("gastos.ver")
def index():
    pagina, total = None, None
    if hay_busqueda():
        desde, hasta = arg_fecha("desde"), arg_fecha("hasta")
        if request.args.get("rapido") in ("hoy", "semana", "mes"):
            desde, hasta = rango_periodo(request.args["rapido"])
        filtros = {"categoria_id": arg_int("categoria_id"), "desde": desde, "hasta": hasta, "texto": arg_txt("q"),
                   "vehiculo_id": arg_int("vehiculo_id"), "estado": arg_txt("estado")}
        pagina = gasto_model.buscar(**filtros)
        total = gasto_model.total(**filtros)
    desde_mes, hasta_mes = rango_periodo("mes")
    return render_template("gastos/index.html", pagina=pagina, total=total, categorias=catalogos.opciones("categorias_gastos"),
                           vehiculos=flota.opciones_vehiculos(todos=True),
                           por_categoria=gasto_model.por_categoria(desde_mes, hasta_mes))


def _form(errores=None, datos=None):
    return render_template("gastos/form.html", g=datos or {"fecha": hoy().isoformat()}, errores=errores or {},
                           categorias=catalogos.opciones("categorias_gastos"),
                           metodos=catalogos.metodos_pago(incluir_cta_cte=False),
                           proveedores=proveedor_model.opciones(), vehiculos=flota.opciones_vehiculos(todos=True),
                           caja=caja_model.abierta())


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("gastos.gestionar")
def nuevo():
    if request.method == "POST":
        v = Validador(request.form)
        datos = {
            "categoria_id": v.entero("categoria_id", True, etiqueta="Categoría"),
            "descripcion": v.texto("descripcion", True, 200, etiqueta="Descripción"),
            "monto": v.decimal("monto", True, positivo=True, etiqueta="Monto"),
            "metodo_pago_id": v.entero("metodo_pago_id", True, etiqueta="Método de pago"),
            "fecha": v.fecha("fecha", True, etiqueta="Fecha"),
            "proveedor_id": v.entero("proveedor_id"),
            "vehiculo_id": v.entero("vehiculo_id"),
            "observaciones": v.texto("observaciones", maximo=2000),
        }
        if datos["fecha"] and datos["fecha"] > hoy():
            v.error("fecha", "La fecha no puede ser futura.")
        try:
            v.verificar()
            gasto_service.registrar(datos, current_user.id)
            flash("Gasto registrado (egreso de caja).", "success")
            return redirect(url_for("gastos.index", rapido="mes"))
        except (ValidacionError, NegocioError) as e:
            flash(e.mensaje, "danger")
            return _form(getattr(e, "errores", {}), request.form)
    return _form()


@bp.route("/<int:gasto_id>/anular", methods=["POST"])
@permiso_requerido("gastos.gestionar")
def anular(gasto_id):
    try:
        gasto_service.anular(gasto_id, current_user.id)
        flash("Gasto anulado. Se registró el reingreso en la caja.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(request.referrer or url_for("gastos.index"))
