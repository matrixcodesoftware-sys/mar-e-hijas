"""Proveedores: ABM, cuenta, compras y pagos."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..database import transaction
from ..models import catalogos
from ..models import proveedor as proveedor_model
from ..services import historial_service, proveedor_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError, ValidacionError
from ..utils.validadores import Validador
from ._comun import arg_txt, hay_busqueda

bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")


@bp.route("/")
@permiso_requerido("proveedores.ver")
def index():
    pagina = None
    if hay_busqueda():
        pagina = proveedor_model.buscar(texto=arg_txt("q"), activo=request.args.get("activo", "1"),
                                        con_deuda=bool(request.args.get("deuda")))
    return render_template("proveedores/index.html", pagina=pagina)


def _leer_form(proveedor_id=None):
    v = Validador(request.form)
    datos = {
        "razon_social": v.texto("razon_social", True, 150, etiqueta="Razón social"),
        "cuit": v.cuit("cuit"),
        "telefono": v.texto("telefono", maximo=40),
        "email": v.email("email"),
        "direccion": v.texto("direccion", maximo=200),
        "localidad": v.texto("localidad", maximo=100),
        "contacto": v.texto("contacto", maximo=120),
        "observaciones": v.texto("observaciones", maximo=2000),
        "activo": v.booleano("activo"),
    }
    if datos["cuit"] and proveedor_model.existe_cuit(datos["cuit"], proveedor_id):
        v.error("cuit", "Ya existe un proveedor con ese CUIT.")
    v.verificar()
    return datos


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("proveedores.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos = _leer_form()
            with transaction():
                pid = proveedor_model.crear(datos)
                historial_service.registrar("crear", "proveedores", f"creó el proveedor {datos['razon_social']}", pid)
            flash("Proveedor creado.", "success")
            return redirect(url_for("proveedores.ver", proveedor_id=pid))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return render_template("proveedores/form.html", p=request.form, errores=e.errores, editando=False)
    return render_template("proveedores/form.html", p={"activo": 1}, errores={}, editando=False)


@bp.route("/<int:proveedor_id>/editar", methods=["GET", "POST"])
@permiso_requerido("proveedores.gestionar")
def editar(proveedor_id):
    proveedor = proveedor_model.obtener(proveedor_id) or abort(404)
    if request.method == "POST":
        try:
            datos = _leer_form(proveedor_id)
            with transaction():
                proveedor_model.actualizar(proveedor_id, datos)
                historial_service.registrar("modificar", "proveedores", f"modificó el proveedor {datos['razon_social']}",
                                            proveedor_id)
            flash("Proveedor actualizado.", "success")
            return redirect(url_for("proveedores.ver", proveedor_id=proveedor_id))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return render_template("proveedores/form.html", p={**request.form, "id": proveedor_id},
                                   errores=e.errores, editando=True)
    return render_template("proveedores/form.html", p=proveedor, errores={}, editando=True)


@bp.route("/<int:proveedor_id>")
@permiso_requerido("proveedores.ver")
def ver(proveedor_id):
    proveedor = proveedor_model.obtener(proveedor_id) or abort(404)
    return render_template(
        "proveedores/ver.html", p=proveedor, movimientos=proveedor_model.movimientos(proveedor_id),
        compras=proveedor_model.compras(proveedor_id), pagos=proveedor_model.pagos(proveedor_id),
        materiales=proveedor_model.materiales_suministrados(proveedor_id),
        metodos=catalogos.metodos_pago(incluir_cta_cte=False))


@bp.route("/<int:proveedor_id>/pago", methods=["POST"])
@permiso_requerido("proveedores.gestionar")
def pagar(proveedor_id):
    proveedor_model.obtener(proveedor_id) or abort(404)
    v = Validador(request.form)
    datos = {
        "proveedor_id": proveedor_id,
        "monto": v.decimal("monto", True, positivo=True, etiqueta="Monto"),
        "metodo_pago_id": v.entero("metodo_pago_id", True, etiqueta="Método de pago"),
        "referencia": v.texto("referencia", maximo=100),
        "observaciones": v.texto("observaciones", maximo=255),
    }
    try:
        v.verificar()
        proveedor_service.registrar_pago(datos, current_user.id)
        flash("Pago al proveedor registrado (egreso de caja).", "success")
    except (ValidacionError, NegocioError) as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("proveedores.ver", proveedor_id=proveedor_id))
