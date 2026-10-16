"""Clientes y cuentas corrientes."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..database import transaction
from ..models import catalogos
from ..models import cliente as cliente_model
from ..models import cuenta_corriente as cc_model
from ..services import cuenta_corriente_service, historial_service, pdf_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError, ValidacionError
from ..utils.formato import opciones
from ..utils.validadores import Validador
from ._comun import arg_fecha, arg_txt, hay_busqueda, respuesta_pdf

bp = Blueprint("clientes", __name__, url_prefix="/clientes")

TIPOS = [k for k, _ in opciones("tipo_cliente")]
CONDICIONES = [k for k, _ in opciones("condicion_iva")]


@bp.route("/")
@permiso_requerido("clientes.ver")
def index():
    pagina = None
    if hay_busqueda() or request.args.get("deuda"):
        pagina = cliente_model.buscar(texto=arg_txt("q"), tipo=arg_txt("tipo"), localidad=arg_txt("localidad"),
                                      activo=request.args.get("activo", "1"),
                                      con_deuda=bool(request.args.get("deuda")) and current_user.puede("cuentas.ver"))
    return render_template("clientes/index.html", pagina=pagina)


def _leer_form(cliente_id=None):
    v = Validador(request.form)
    doc_tipo = v.opcion("documento_tipo", ("DNI", "CUIT", "CUIL", "OTRO"), defecto="DNI")
    datos = {
        "tipo": v.opcion("tipo", TIPOS, etiqueta="Tipo de cliente"),
        "razon_social": v.texto("razon_social", True, 150, etiqueta="Nombre / razón social"),
        "documento_tipo": doc_tipo,
        "documento": v.documento("documento", doc_tipo),
        "condicion_iva": v.opcion("condicion_iva", CONDICIONES, defecto="consumidor_final"),
        "telefono": v.texto("telefono", maximo=40),
        "whatsapp": v.texto("whatsapp", maximo=40),
        "email": v.email("email"),
        "direccion": v.texto("direccion", maximo=200),
        "localidad": v.texto("localidad", maximo=100),
        "zona_id": v.entero("zona_id"),
        "referencia_ubicacion": v.texto("referencia_ubicacion", maximo=255),
        "observaciones": v.texto("observaciones", maximo=2000),
        "activo": v.booleano("activo"),
    }
    limite = v.decimal("limite_credito", minimo=0, etiqueta="Límite de crédito")
    if datos["documento"] and cliente_model.existe_documento(datos["documento"], cliente_id):
        v.error("documento", "Ya existe un cliente con ese documento.")
    v.verificar()
    return datos, limite


def _form(cliente=None, errores=None, datos=None):
    return render_template("clientes/form.html", c=datos or cliente or {"activo": 1, "tipo": "particular",
                                                                        "documento_tipo": "DNI"},
                           editando=cliente is not None, errores=errores or {},
                           zonas=catalogos.opciones("zonas_entrega"))


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("clientes.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos, limite = _leer_form()
            with transaction():
                cid = cliente_model.crear(datos)
                cc_model.crear(cid, limite or 0)
                historial_service.registrar("crear", "clientes", f"creó el cliente {datos['razon_social']}", cid)
            flash(f"Cliente {datos['razon_social']} creado.", "success")
            destino = request.args.get("volver")
            if destino in ("venta", "presupuesto", "pedido"):
                return redirect(url_for({"venta": "ventas.nueva", "presupuesto": "presupuestos.nuevo",
                                         "pedido": "pedidos.nuevo"}[destino], cliente_id=cid))
            return redirect(url_for("clientes.ver", cliente_id=cid))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(errores=e.errores, datos=request.form)
    return _form()


@bp.route("/<int:cliente_id>/editar", methods=["GET", "POST"])
@permiso_requerido("clientes.gestionar")
def editar(cliente_id):
    cliente = cliente_model.obtener(cliente_id) or abort(404)
    if request.method == "POST":
        try:
            datos, limite = _leer_form(cliente_id)
            with transaction():
                cliente_model.actualizar(cliente_id, datos)
                if limite is not None and current_user.puede("cuentas.gestionar"):
                    cuenta_corriente_service.actualizar_limite(cliente_id, limite)
                historial_service.registrar("modificar", "clientes", f"modificó el cliente {datos['razon_social']}",
                                            cliente_id)
            flash("Cliente actualizado.", "success")
            return redirect(url_for("clientes.ver", cliente_id=cliente_id))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(cliente, e.errores, {**request.form, "id": cliente_id})
    return _form(cliente)


@bp.route("/<int:cliente_id>")
@permiso_requerido("clientes.ver")
def ver(cliente_id):
    cliente = cliente_model.obtener(cliente_id) or abort(404)
    return render_template(
        "clientes/ver.html", c=cliente, stats=cliente_model.estadisticas(cliente_id),
        ventas=cliente_model.ventas(cliente_id) if current_user.puede("ventas.ver") else [],
        pedidos=cliente_model.pedidos(cliente_id) if current_user.puede("pedidos.ver") else [],
        presupuestos=cliente_model.presupuestos(cliente_id) if current_user.puede("presupuestos.ver") else [],
        pagos=cliente_model.pagos(cliente_id) if current_user.puede("cuentas.ver") else [],
        frecuentes=cliente_model.materiales_frecuentes(cliente_id))


# ------------------------------------------------------------------ cuenta corriente
@bp.route("/<int:cliente_id>/cuenta")
@permiso_requerido("cuentas.ver")
def cuenta(cliente_id):
    cliente = cliente_model.obtener(cliente_id) or abort(404)
    desde, hasta = arg_fecha("desde"), arg_fecha("hasta")
    r = cuenta_corriente_service.resumen(cliente_id, desde, hasta)
    return render_template("cuentas/cuenta.html", c=cliente, r=r, desde=desde, hasta=hasta,
                           metodos=catalogos.metodos_pago(incluir_cta_cte=False),
                           imprimir=bool(request.args.get("imprimir")))


@bp.route("/<int:cliente_id>/cuenta/pdf")
@permiso_requerido("cuentas.ver")
def cuenta_pdf(cliente_id):
    cliente = cliente_model.obtener(cliente_id) or abort(404)
    desde, hasta = arg_fecha("desde"), arg_fecha("hasta")
    r = cuenta_corriente_service.resumen(cliente_id, desde, hasta)
    return respuesta_pdf(f"cuenta_{cliente_id}", pdf_service.cuenta_pdf(cliente, r, desde, hasta))


@bp.route("/<int:cliente_id>/cuenta/movimiento", methods=["POST"])
@permiso_requerido("cuentas.gestionar")
def cuenta_movimiento(cliente_id):
    cliente_model.obtener(cliente_id) or abort(404)
    v = Validador(request.form)
    tipo = v.opcion("tipo", ("pago", "deuda", "credito"), etiqueta="Tipo")
    monto = v.decimal("monto", True, positivo=True, etiqueta="Monto")
    try:
        if tipo == "pago":
            metodo = v.entero("metodo_pago_id", True, etiqueta="Método de pago")
            referencia = v.texto("referencia", maximo=100)
            v.verificar()
            cuenta_corriente_service.registrar_pago(cliente_id, monto, metodo, current_user.id, referencia,
                                                    v.texto("observaciones", maximo=255))
            flash("Pago registrado. Ingresó en la caja.", "success")
        else:
            concepto = v.texto("concepto", True, 200, etiqueta="Concepto")
            v.verificar()
            cuenta_corriente_service.registrar_manual(cliente_id, tipo, monto, concepto, current_user.id)
            flash("Movimiento registrado.", "success")
    except (ValidacionError, NegocioError) as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("clientes.cuenta", cliente_id=cliente_id))
