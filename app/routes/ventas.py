"""Ventas."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import caja as caja_model
from ..models import catalogos
from ..models import entrega as entrega_model
from ..models import material as material_model
from ..models import pedido as pedido_model
from ..models import presupuesto as presupuesto_model
from ..models import stock as stock_model
from ..models import usuario as usuario_model
from ..models import venta as venta_model
from ..models import cliente as cliente_model
from ..services import documento_service, pdf_service, venta_service
from ..services.facturacion import servicio as facturacion
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError
from ..utils.fechas import hoy, rango_periodo
from ..utils.validadores import Validador
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda, respuesta_pdf
from ._documentos import cliente_json, contexto_formulario, items_desde_post, leer_cabecera

bp = Blueprint("ventas", __name__, url_prefix="/ventas")


@bp.route("/")
@permiso_requerido("ventas.ver")
def index():
    pagina = None
    rapido = request.args.get("rapido")
    if hay_busqueda():
        desde, hasta = arg_fecha("desde"), arg_fecha("hasta")
        if rapido in ("hoy", "semana", "mes"):
            desde, hasta = rango_periodo(rapido)
        numero = arg_txt("numero")
        numero = int("".join(ch for ch in numero if ch.isdigit()) or 0) if numero else None
        pagina = venta_model.buscar(desde=desde, hasta=hasta, cliente_id=arg_int("cliente_id"),
                                    usuario_id=arg_int("usuario_id"), material_id=arg_int("material_id"),
                                    estado=arg_txt("estado"), estado_pago=arg_txt("estado_pago"), numero=numero)
    cliente_sel = cliente_model.obtener(arg_int("cliente_id")) if arg_int("cliente_id") else None
    return render_template("ventas/index.html", pagina=pagina, materiales=material_model.opciones(),
                           vendedores=usuario_model.listar_activos(), cliente_sel=cliente_sel)


def _render_form(datos, items, errores=None):
    return render_template(
        "ventas/form.html", d=datos, items=items, errores=errores or {}, cliente=cliente_json(datos.get("cliente_id")),
        metodos=catalogos.metodos_pago(), caja=caja_model.abierta(), **contexto_formulario())


@bp.route("/nueva", methods=["GET", "POST"])
@permiso_requerido("ventas.crear")
def nueva():
    if request.method == "POST":
        v, datos = leer_cabecera(request.form)
        datos.update({
            "metodo_pago_id": v.entero("metodo_pago_id"),
            "monto_pagado": request.form.get("monto_pagado"),
            "referencia_pago": v.texto("referencia_pago", maximo=100),
            "presupuesto_id": v.entero("presupuesto_id"),
            "pedido_id": v.entero("pedido_id"),
            "crear_entrega": v.booleano("crear_entrega"),
            "fecha_entrega": v.fecha("fecha_entrega"),
            "horario_entrega": v.texto("horario_entrega", maximo=40),
        })
        items = documento_service.leer_items(request.form)
        try:
            v.verificar()
            venta_id = venta_service.registrar(datos, items, current_user.id)
            flash(f"Venta V-{venta_id:06d} registrada.", "success")
            return redirect(url_for("ventas.ver", venta_id=venta_id, nueva=1))
        except NegocioError as e:
            flash(e.mensaje, "danger")
            return _render_form({**datos, "monto_pagado": request.form.get("monto_pagado")}, items_desde_post(items),
                                getattr(e, "errores", {}))

    datos = {"tipo_entrega": "retiro", "cliente_id": arg_int("cliente_id"), "crear_entrega": 1,
             "fecha_entrega": hoy()}
    items = []
    # Conversión desde presupuesto o pedido: se reutilizan todos los datos.
    if request.args.get("presupuesto"):
        p = presupuesto_model.obtener(arg_int("presupuesto")) or abort(404)
        if p["venta_id"]:
            flash(f"El presupuesto ya se convirtió en la venta V-{p['venta_id']:06d}.", "warning")
            return redirect(url_for("ventas.ver", venta_id=p["venta_id"]))
        datos.update({"cliente_id": p["cliente_id"], "presupuesto_id": p["id"], "tipo_entrega": p["tipo_entrega"],
                      "zona_id": p["zona_id"], "direccion_entrega": p["direccion_entrega"],
                      "descuento_general": p["descuento_general"], "costo_envio": p["costo_envio"],
                      "observaciones": p["observaciones"]})
        items = documento_service.items_para_formulario(presupuesto_model.detalle(p["id"]))
        flash(f"Datos cargados del presupuesto PR-{p['id']:06d}. Revisá y elegí la forma de pago.", "info")
    elif request.args.get("pedido"):
        p = pedido_model.obtener(arg_int("pedido")) or abort(404)
        if p["venta_id"]:
            flash(f"El pedido ya tiene la venta V-{p['venta_id']:06d}.", "warning")
            return redirect(url_for("ventas.ver", venta_id=p["venta_id"]))
        datos.update({"cliente_id": p["cliente_id"], "pedido_id": p["id"], "tipo_entrega": p["tipo_entrega"],
                      "zona_id": p["zona_id"], "direccion_entrega": p["direccion_entrega"],
                      "descuento_general": p["descuento_general"], "costo_envio": p["costo_envio"],
                      "observaciones": p["observaciones"], "crear_entrega": 0})
        items = documento_service.items_para_formulario(pedido_model.detalle(p["id"]))
        flash(f"Datos cargados del pedido P-{p['id']:06d}. Las entregas se gestionan desde el pedido.", "info")
    return _render_form(datos, items)


@bp.route("/<int:venta_id>")
@permiso_requerido("ventas.ver")
def ver(venta_id):
    venta = venta_model.obtener(venta_id) or abort(404)
    return render_template(
        "ventas/ver.html", v=venta, detalle=venta_model.detalle(venta_id), pagos=venta_model.pagos(venta_id),
        entregas=entrega_model.de_venta(venta_id), movimientos=stock_model.de_venta(venta_id),
        comprobantes=facturacion.comprobantes_de_venta(venta_id),
        puntos_venta=facturacion.puntos_venta() if current_user.puede("facturacion.gestionar") else [],
        nueva=bool(request.args.get("nueva")))


@bp.route("/<int:venta_id>/pdf")
@permiso_requerido("ventas.ver")
def pdf(venta_id):
    venta = venta_model.obtener(venta_id) or abort(404)
    return respuesta_pdf(f"venta_V-{venta_id:06d}", pdf_service.venta_pdf(venta, venta_model.detalle(venta_id),
                                                                          venta_model.pagos(venta_id)))


@bp.route("/<int:venta_id>/anular", methods=["POST"])
@permiso_requerido("ventas.anular")
def anular(venta_id):
    try:
        venta_service.anular(venta_id, request.form.get("motivo") or "", current_user.id)
        flash("Venta anulada. Se repuso el stock y se revirtieron caja y cuenta corriente.", "success")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("ventas.ver", venta_id=venta_id))


@bp.route("/<int:venta_id>/facturar", methods=["POST"])
@permiso_requerido("facturacion.gestionar")
def facturar(venta_id):
    venta = venta_model.obtener(venta_id) or abort(404)
    v = Validador(request.form)
    pv = v.entero("punto_venta_id", True, etiqueta="Punto de venta")
    try:
        v.verificar()
        cliente = cliente_model.obtener(venta["cliente_id"])
        _, mensaje = facturacion.emitir(venta, cliente, venta_model.detalle(venta_id), pv)
        flash(mensaje, "warning")
    except NegocioError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("ventas.ver", venta_id=venta_id))
