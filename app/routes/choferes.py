"""Choferes."""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..database import transaction
from ..models import configuracion, flota
from ..models import entrega as entrega_model
from ..services import historial_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import ValidacionError
from ..utils.fechas import hoy
from ..utils.validadores import Validador
from ._comun import arg_txt

bp = Blueprint("choferes", __name__, url_prefix="/choferes")


@bp.route("/")
@permiso_requerido("choferes.ver")
def index():
    pagina = flota.buscar_choferes(texto=arg_txt("q"), estado=arg_txt("estado"))
    return render_template("choferes/index.html", pagina=pagina, hoy=hoy(),
                           limite_alerta=hoy() + timedelta(days=configuracion.get_int("alerta_licencia_dias", 30)))


def _leer_form(chofer_id=None):
    v = Validador(request.form)
    datos = {
        "nombre": v.texto("nombre", True, 80),
        "apellido": v.texto("apellido", True, 80),
        "dni": v.documento("dni", "DNI", requerido=True),
        "telefono": v.texto("telefono", maximo=40),
        "licencia_numero": v.texto("licencia_numero", maximo=40, etiqueta="Número de licencia"),
        "licencia_categoria": v.texto("licencia_categoria", maximo=20, etiqueta="Categoría"),
        "licencia_vencimiento": v.fecha("licencia_vencimiento", etiqueta="Vencimiento de licencia"),
        "usuario_id": v.entero("usuario_id"),
        "estado": v.opcion("estado", ("activo", "inactivo", "licencia"), defecto="activo"),
        "observaciones": v.texto("observaciones", maximo=2000),
    }
    if datos["dni"] and flota.existe_dni(datos["dni"], chofer_id):
        v.error("dni", "Ya existe un chofer con ese DNI.")
    if flota.usuario_ya_asignado(datos["usuario_id"], chofer_id):
        v.error("usuario_id", "Ese usuario ya está vinculado a otro chofer.")
    v.verificar()
    return datos


def _form(chofer=None, errores=None, datos=None):
    return render_template("choferes/form.html", c=datos or chofer or {"estado": "activo"}, editando=chofer is not None,
                           errores=errores or {}, usuarios=flota.usuarios_chofer_opciones())


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("choferes.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos = _leer_form()
            with transaction():
                cid = flota.crear_chofer(datos)
                historial_service.registrar("crear", "choferes", f"dio de alta al chofer {datos['nombre']} {datos['apellido']}", cid)
            flash("Chofer creado.", "success")
            return redirect(url_for("choferes.ver", chofer_id=cid))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(errores=e.errores, datos=request.form)
    return _form()


@bp.route("/<int:chofer_id>/editar", methods=["GET", "POST"])
@permiso_requerido("choferes.gestionar")
def editar(chofer_id):
    chofer = flota.chofer(chofer_id) or abort(404)
    if request.method == "POST":
        try:
            datos = _leer_form(chofer_id)
            with transaction():
                flota.actualizar_chofer(chofer_id, datos)
                historial_service.registrar("modificar", "choferes", f"modificó al chofer {datos['nombre']} {datos['apellido']}",
                                            chofer_id)
            flash("Chofer actualizado.", "success")
            return redirect(url_for("choferes.ver", chofer_id=chofer_id))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(chofer, e.errores, {**request.form, "id": chofer_id})
    return _form(chofer)


@bp.route("/<int:chofer_id>")
@permiso_requerido("choferes.ver")
def ver(chofer_id):
    chofer = flota.chofer(chofer_id) or abort(404)
    h = hoy()
    proximas = entrega_model.de_chofer(chofer_id, h, h + timedelta(days=7))
    return render_template("choferes/ver.html", c=chofer, stats=flota.estadisticas_chofer(chofer_id), proximas=proximas,
                           hoy=h, limite_alerta=h + timedelta(days=configuracion.get_int("alerta_licencia_dias", 30)))
