"""Presupuestos."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import cliente as cliente_model
from ..models import presupuesto as presupuesto_model
from ..services import documento_service, pdf_service, presupuesto_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError
from ..utils.fechas import hoy
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda, respuesta_pdf
from ._documentos import cliente_json, contexto_formulario, items_desde_post, leer_cabecera

bp = Blueprint("presupuestos", __name__, url_prefix="/presupuestos")


@bp.route("/")
@permiso_requerido("presupuestos.ver")
def index():
    presupuesto_model.vencer_automaticamente(hoy())
    pagina = None
    if hay_busqueda():
        numero = arg_txt("numero")
        numero = int("".join(ch for ch in numero if ch.isdigit()) or 0) if numero else None
        estado = arg_txt("estado") or ({"pendientes": "pendiente"}.get(request.args.get("rapido")))
        pagina = presupuesto_model.buscar(estado=estado, cliente_id=arg_int("cliente_id"), desde=arg_fecha("desde"),
                                          hasta=arg_fecha("hasta"), numero=numero)
    cliente_sel = cliente_model.obtener(arg_int("cliente_id")) if arg_int("cliente_id") else None
    return render_template("presupuestos/index.html", pagina=pagina, cliente_sel=cliente_sel)


def _render_form(datos, items, presupuesto=None):
    return render_template("presupuestos/form.html", d=datos, items=items, errores={}, p=presupuesto,
                           cliente=cliente_json(datos.get("cliente_id")), **contexto_formulario())


def _guardar(presupuesto_id=None):
    v, datos = leer_cabecera(request.form)
    datos["fecha_vencimiento"] = v.fecha("fecha_vencimiento", etiqueta="Vencimiento")
    items = documento_service.leer_items(request.form)
    try:
        v.verificar()
        pid = presupuesto_service.guardar(datos, items, current_user.id, presupuesto_id)
        flash(f"Presupuesto PR-{pid:06d} guardado.", "success")
        return redirect(url_for("presupuestos.ver", presupuesto_id=pid))
    except NegocioError as e:
        flash(e.mensaje, "danger")
        return _render_form(datos, items_desde_post(items),
                            presupuesto_model.obtener(presupuesto_id) if presupuesto_id else None)


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("presupuestos.gestionar")
def nuevo():
    if request.method == "POST":
        return _guardar()
    return _render_form({"tipo_entrega": "retiro", "cliente_id": arg_int("cliente_id")}, [])


@bp.route("/<int:presupuesto_id>/editar", methods=["GET", "POST"])
@permiso_requerido("presupuestos.gestionar")
def editar(presupuesto_id):
    p = presupuesto_model.obtener(presupuesto_id) or abort(404)
    if request.method == "POST":
        return _guardar(presupuesto_id)
    datos = {k: p[k] for k in ("cliente_id", "tipo_entrega", "zona_id", "direccion_entrega", "descuento_general",
                               "costo_envio", "observaciones", "fecha_vencimiento")}
    return _render_form(datos, documento_service.items_para_formulario(presupuesto_model.detalle(presupuesto_id)), p)


@bp.route("/<int:presupuesto_id>")
@permiso_requerido("presupuestos.ver")
def ver(presupuesto_id):
    presupuesto_model.vencer_automaticamente(hoy())
    p = presupuesto_model.obtener(presupuesto_id) or abort(404)
    return render_template("presupuestos/ver.html", p=p, detalle=presupuesto_model.detalle(presupuesto_id))


@bp.route("/<int:presupuesto_id>/pdf")
@permiso_requerido("presupuestos.ver")
def pdf(presupuesto_id):
    p = presupuesto_model.obtener(presupuesto_id) or abort(404)
    return respuesta_pdf(f"presupuesto_PR-{presupuesto_id:06d}",
                         pdf_service.presupuesto_pdf(p, presupuesto_model.detalle(presupuesto_id)),
                         descargar=bool(request.args.get("descargar")))


@bp.route("/<int:presupuesto_id>/estado", methods=["POST"])
@permiso_requerido("presupuestos.gestionar")
def estado(presupuesto_id):
    try:
        presupuesto_service.cambiar_estado(presupuesto_id, request.form.get("estado"), current_user.id)
        flash("Estado actualizado.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("presupuestos.ver", presupuesto_id=presupuesto_id))


@bp.route("/<int:presupuesto_id>/a-pedido", methods=["POST"])
@permiso_requerido("pedidos.gestionar")
def a_pedido(presupuesto_id):
    try:
        pedido_id = presupuesto_service.convertir_en_pedido(presupuesto_id, current_user.id)
        flash(f"Se creó el pedido P-{pedido_id:06d}. Revisá fecha, horario y dirección de entrega.", "success")
        return redirect(url_for("pedidos.editar", pedido_id=pedido_id))
    except NegocioError as e:
        flash(e.mensaje, "danger")
        return redirect(url_for("presupuestos.ver", presupuesto_id=presupuesto_id))
