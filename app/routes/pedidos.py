"""Pedidos."""
from datetime import timedelta
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import cliente as cliente_model
from ..models import flota
from ..models import pedido as pedido_model
from ..services import documento_service, pedido_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError
from ..utils.fechas import hoy
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda
from ._documentos import cliente_json, contexto_formulario, items_desde_post, leer_cabecera

bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


@bp.route("/")
@permiso_requerido("pedidos.ver")
def index():
    pagina = None
    rapido = request.args.get("rapido")
    if hay_busqueda():
        h = hoy()
        filtros = {"estado": arg_txt("estado"), "cliente_id": arg_int("cliente_id"), "desde": arg_fecha("desde"),
                   "hasta": arg_fecha("hasta"), "chofer_id": arg_int("chofer_id")}
        numero = arg_txt("numero")
        if numero:
            filtros["numero"] = int("".join(ch for ch in numero if ch.isdigit()) or 0)
        if rapido == "activos":
            filtros["activos"] = True
        elif rapido == "hoy":
            filtros.update(desde=h, hasta=h, activos=True)
        elif rapido == "manana":
            filtros.update(desde=h + timedelta(days=1), hasta=h + timedelta(days=1), activos=True)
        elif rapido == "atrasados":
            filtros.update(hasta=h - timedelta(days=1), activos=True)
        pagina = pedido_model.buscar(**filtros)
    cliente_sel = cliente_model.obtener(arg_int("cliente_id")) if arg_int("cliente_id") else None
    return render_template("pedidos/index.html", pagina=pagina, conteo=pedido_model.contar_por_estado(),
                           choferes=flota.opciones_choferes(), cliente_sel=cliente_sel)


def _render_form(datos, items, pedido=None):
    return render_template("pedidos/form.html", d=datos, items=items, errores={}, p=pedido,
                           cliente=cliente_json(datos.get("cliente_id")), vehiculos=flota.opciones_vehiculos(),
                           choferes=flota.opciones_choferes(), **contexto_formulario())


def _guardar(pedido_id=None):
    v, datos = leer_cabecera(request.form)
    datos.update({
        "fecha_solicitada": v.fecha("fecha_solicitada", True, etiqueta="Fecha solicitada"),
        "horario": v.texto("horario", maximo=40),
        "localidad": v.texto("localidad", maximo=100),
        "referencia": v.texto("referencia", maximo=255),
        "vehiculo_id": v.entero("vehiculo_id"),
        "chofer_id": v.entero("chofer_id"),
        "presupuesto_id": v.entero("presupuesto_id"),
    })
    items = documento_service.leer_items(request.form)
    try:
        v.verificar()
        pid = pedido_service.guardar(datos, items, current_user.id, pedido_id)
        flash(f"Pedido P-{pid:06d} guardado.", "success")
        return redirect(url_for("pedidos.ver", pedido_id=pid))
    except NegocioError as e:
        flash(e.mensaje, "danger")
        return _render_form(datos, items_desde_post(items), pedido_model.obtener(pedido_id) if pedido_id else None)


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("pedidos.gestionar")
def nuevo():
    if request.method == "POST":
        return _guardar()
    return _render_form({"tipo_entrega": "envio", "cliente_id": arg_int("cliente_id"),
                         "fecha_solicitada": hoy() + timedelta(days=1)}, [])


@bp.route("/<int:pedido_id>/editar", methods=["GET", "POST"])
@permiso_requerido("pedidos.gestionar")
def editar(pedido_id):
    p = pedido_model.obtener(pedido_id) or abort(404)
    if request.method == "POST":
        return _guardar(pedido_id)
    datos = {k: p[k] for k in ("cliente_id", "tipo_entrega", "zona_id", "direccion_entrega", "descuento_general",
                               "costo_envio", "observaciones", "fecha_solicitada", "horario", "localidad",
                               "referencia", "vehiculo_id", "chofer_id", "presupuesto_id")}
    return _render_form(datos, documento_service.items_para_formulario(pedido_model.detalle(pedido_id)), p)


@bp.route("/<int:pedido_id>")
@permiso_requerido("pedidos.ver")
def ver(pedido_id):
    p = pedido_model.obtener(pedido_id) or abort(404)
    detalle = pedido_model.detalle(pedido_id)
    for d in detalle:
        d["pendiente"] = max(Decimal(d["cantidad"]) - Decimal(d["programado"]), Decimal(0))
    return render_template("pedidos/ver.html", p=p, detalle=detalle, entregas=pedido_model.entregas(pedido_id),
                           transiciones=sorted(pedido_service.TRANSICIONES.get(p["estado"], set()),
                                               key=lambda e: (pedido_service.ORDEN + ["cancelado"]).index(e)),
                           vehiculos=flota.opciones_vehiculos(), choferes=flota.opciones_choferes(),
                           hay_pendiente=any(d["pendiente"] > 0 for d in detalle))


@bp.route("/<int:pedido_id>/estado", methods=["POST"])
@permiso_requerido("pedidos.gestionar")
def estado(pedido_id):
    try:
        pedido_service.cambiar_estado(pedido_id, request.form.get("estado"), current_user.id)
        flash("Estado del pedido actualizado.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("pedidos.ver", pedido_id=pedido_id))


@bp.route("/<int:pedido_id>/viaje", methods=["POST"])
@permiso_requerido("entregas.gestionar")
def viaje(pedido_id):
    cantidades = {}
    for clave, valor in request.form.items():
        if clave.startswith("cant_") and valor.strip():
            try:
                cantidades[int(clave[5:])] = Decimal(valor.replace(",", "."))
            except Exception:
                flash("Cantidad inválida.", "danger")
                return redirect(url_for("pedidos.ver", pedido_id=pedido_id))
    datos = {
        "chofer_id": arg_int_form("chofer_id"), "vehiculo_id": arg_int_form("vehiculo_id"),
        "fecha": request.form.get("fecha") or None, "horario": (request.form.get("horario") or "")[:40] or None,
        "observaciones": (request.form.get("observaciones") or "")[:1000] or None,
    }
    try:
        entrega_id = pedido_service.programar_viaje(pedido_id, datos, cantidades, current_user.id)
        flash(f"Viaje E-{entrega_id:06d} programado.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("pedidos.ver", pedido_id=pedido_id) + "#viajes")


def arg_int_form(nombre):
    try:
        v = request.form.get(nombre)
        return int(v) if v else None
    except ValueError:
        return None
