"""Caja: apertura, movimientos, cierre e historial."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import caja as caja_model
from ..models import catalogos
from ..services import caja_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError, ValidacionError
from ..utils.validadores import Validador
from ._comun import arg_fecha

bp = Blueprint("caja", __name__, url_prefix="/caja")


@bp.route("/")
@permiso_requerido("caja.ver", "caja.operar")
def index():
    caja = caja_model.abierta()
    resumen = caja_service.resumen(caja) if caja else None
    movimientos = caja_model.movimientos(caja["id"]) if caja else []
    return render_template("caja/index.html", caja=caja, r=resumen, movimientos=movimientos,
                           metodos=catalogos.metodos_pago(incluir_cta_cte=False))


@bp.route("/abrir", methods=["POST"])
@permiso_requerido("caja.operar")
def abrir():
    v = Validador(request.form)
    monto = v.decimal("monto_inicial", True, minimo=0, etiqueta="Monto inicial")
    obs = v.texto("observaciones", maximo=255)
    try:
        v.verificar()
        caja_service.abrir(monto, current_user.id, obs)
        flash("Caja abierta.", "success")
    except (ValidacionError, NegocioError) as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("caja.index"))


@bp.route("/movimiento", methods=["POST"])
@permiso_requerido("caja.operar")
def movimiento():
    v = Validador(request.form)
    tipo = v.opcion("tipo", ("ingreso", "retiro", "ajuste"), etiqueta="Tipo")
    sentido = request.form.get("sentido")
    metodo = v.entero("metodo_pago_id", True, etiqueta="Método")
    monto = v.decimal("monto", True, positivo=True, etiqueta="Monto")
    concepto = v.texto("concepto", True, 200, etiqueta="Concepto")
    try:
        v.verificar()
        caja_service.movimiento_manual(tipo, sentido, metodo, monto, concepto, current_user.id)
        flash("Movimiento registrado.", "success")
    except (ValidacionError, NegocioError) as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("caja.index"))


@bp.route("/cerrar", methods=["POST"])
@permiso_requerido("caja.operar")
def cerrar():
    v = Validador(request.form)
    declarado = v.decimal("saldo_declarado", True, minimo=0, etiqueta="Efectivo contado")
    obs = v.texto("observaciones", maximo=255)
    try:
        v.verificar()
        caja_id = caja_service.cerrar(declarado, current_user.id, obs)
        flash("Caja cerrada.", "success")
        return redirect(url_for("caja.ver", caja_id=caja_id))
    except (ValidacionError, NegocioError) as e:
        flash(e.mensaje, "danger")
        return redirect(url_for("caja.index"))


@bp.route("/historial")
@permiso_requerido("caja.ver")
def historial():
    pagina = caja_model.historial(arg_fecha("desde"), arg_fecha("hasta"))
    return render_template("caja/historial.html", pagina=pagina)


@bp.route("/<int:caja_id>")
@permiso_requerido("caja.ver")
def ver(caja_id):
    caja = caja_model.obtener(caja_id) or abort(404)
    return render_template("caja/ver.html", caja=caja, r=caja_service.resumen(caja),
                           movimientos=caja_model.movimientos(caja_id))
