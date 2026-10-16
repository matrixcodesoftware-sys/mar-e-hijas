"""Logística: entregas (viajes) y vista móvil del chofer."""
from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import entrega as entrega_model
from ..models import flota
from ..services import entrega_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError
from ..utils.fechas import hoy, parse_fecha
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda

bp = Blueprint("entregas", __name__, url_prefix="/entregas")


@bp.route("/")
@permiso_requerido("entregas.ver")
def index():
    pagina = None
    rapido = request.args.get("rapido")
    if hay_busqueda():
        h = hoy()
        filtros = {"estado": arg_txt("estado"), "chofer_id": arg_int("chofer_id"), "vehiculo_id": arg_int("vehiculo_id"),
                   "desde": arg_fecha("desde"), "hasta": arg_fecha("hasta")}
        if rapido == "hoy":
            filtros.update(desde=h, hasta=h)
        elif rapido == "manana":
            filtros.update(desde=h + timedelta(days=1), hasta=h + timedelta(days=1))
        elif rapido == "pendientes":
            filtros["activas"] = True
        elif rapido == "sin_asignar":
            filtros["estado"] = "pendiente"
        pagina = entrega_model.buscar(**filtros)
    return render_template("entregas/index.html", pagina=pagina, choferes=flota.opciones_choferes(),
                           vehiculos=flota.opciones_vehiculos(todos=True))


@bp.route("/<int:entrega_id>")
@permiso_requerido("entregas.ver", "entregas.propias")
def ver(entrega_id):
    e = entrega_model.obtener(entrega_id) or abort(404)
    if not current_user.puede("entregas.ver") and e["chofer_id"] != current_user.chofer_id:
        abort(403)
    return render_template("entregas/ver.html", e=e, detalle=entrega_model.detalle(entrega_id),
                           transiciones=sorted(entrega_service.TRANSICIONES.get(e["estado"], set())),
                           vehiculos=flota.opciones_vehiculos(), choferes=flota.opciones_choferes())


@bp.route("/<int:entrega_id>/asignar", methods=["POST"])
@permiso_requerido("entregas.gestionar")
def asignar(entrega_id):
    def _int(n):
        try:
            return int(request.form.get(n)) if request.form.get(n) else None
        except ValueError:
            return None
    fecha = parse_fecha(request.form.get("fecha"))
    if not fecha:
        flash("Indicá la fecha de la entrega.", "danger")
        return redirect(url_for("entregas.ver", entrega_id=entrega_id))
    try:
        entrega_service.asignar(entrega_id, _int("chofer_id"), _int("vehiculo_id"), fecha,
                                (request.form.get("horario") or "")[:40] or None,
                                (request.form.get("observaciones") or "")[:1000] or None, current_user.id)
        flash("Entrega actualizada.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("entregas.ver", entrega_id=entrega_id))


@bp.route("/<int:entrega_id>/estado", methods=["POST"])
@permiso_requerido("entregas.gestionar", "entregas.propias")
def estado(entrega_id):
    nuevo = request.form.get("estado")
    try:
        entrega_service.cambiar_estado(entrega_id, nuevo, current_user, recibido_por=request.form.get("recibido_por"),
                                       motivo=request.form.get("motivo"))
        flash("¡Entrega realizada!" if nuevo == "entregada" else "Estado actualizado.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    destino = request.form.get("volver")
    if destino == "mis":
        return redirect(url_for("entregas.mis_entregas", fecha=request.form.get("fecha_vista") or None))
    return redirect(url_for("entregas.ver", entrega_id=entrega_id))


@bp.route("/mis-entregas")
@permiso_requerido("entregas.propias")
def mis_entregas():
    if not current_user.chofer_id:
        return render_template("entregas/mis_entregas.html", entregas=[], sin_chofer=True, fecha=hoy(), dias=[])
    fecha = arg_fecha("fecha") or hoy()
    entregas = entrega_model.de_chofer(current_user.chofer_id, fecha, fecha)
    detalles = {e["id"]: entrega_model.detalle(e["id"]) for e in entregas}
    h = hoy()
    dias = [h + timedelta(days=i) for i in range(-1, 4)]
    return render_template("entregas/mis_entregas.html", entregas=entregas, detalles=detalles, fecha=fecha, dias=dias,
                           sin_chofer=False)
