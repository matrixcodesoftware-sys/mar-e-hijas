"""Historial de operaciones (auditoría)."""
from flask import Blueprint, render_template

from ..models import historial as historial_model
from ..models import usuario as usuario_model
from ..utils.decoradores import permiso_requerido
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda

bp = Blueprint("historial", __name__, url_prefix="/historial")


@bp.route("/")
@permiso_requerido("historial.ver")
def index():
    pagina = None
    if hay_busqueda():
        pagina = historial_model.buscar(usuario_id=arg_int("usuario_id"), modulo=arg_txt("modulo"),
                                        accion=arg_txt("accion"), desde=arg_fecha("desde"), hasta=arg_fecha("hasta"),
                                        texto=arg_txt("q"))
    return render_template("historial/index.html", pagina=pagina, usuarios=usuario_model.listar_activos(),
                           modulos=historial_model.MODULOS)
