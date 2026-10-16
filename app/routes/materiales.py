"""ABM de materiales / áridos."""
from decimal import Decimal

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..database import transaction
from ..models import catalogos
from ..models import conversion as conversion_model
from ..models import material as material_model
from ..models import proveedor as proveedor_model
from ..models import stock as stock_model
from ..services import conversion_service, historial_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import ValidacionError
from ..utils.formato import moneda
from ..utils.validadores import Validador
from ._comun import arg_int, arg_txt, hay_busqueda

bp = Blueprint("materiales", __name__, url_prefix="/materiales")


@bp.route("/")
@permiso_requerido("materiales.ver")
def index():
    pagina = None
    if hay_busqueda():
        pagina = material_model.buscar(
            texto=arg_txt("q"), categoria_id=arg_int("categoria_id"), proveedor_id=arg_int("proveedor_id"),
            activo=request.args.get("activo", "1") if request.args.get("rapido") != "todos" else None,
            bajo_stock=request.args.get("rapido") == "bajo")
    return render_template("materiales/index.html", pagina=pagina, categorias=catalogos.opciones("categorias_materiales"),
                           proveedores=proveedor_model.opciones())


def _leer_form(material_id=None):
    v = Validador(request.form)
    datos = {
        "codigo": (v.texto("codigo", True, 20, etiqueta="Código") or "").upper(),
        "nombre": v.texto("nombre", True, 120, etiqueta="Nombre"),
        "categoria_id": v.entero("categoria_id", True, etiqueta="Tipo"),
        "descripcion": v.texto("descripcion", maximo=2000),
        "unidad_id": v.entero("unidad_id", True, etiqueta="Unidad de venta"),
        "precio_compra": v.decimal("precio_compra", True, minimo=0, etiqueta="Precio de compra"),
        "precio_venta": v.decimal("precio_venta", True, minimo=0, etiqueta="Precio de venta"),
        "stock_minimo": v.decimal("stock_minimo", minimo=0, etiqueta="Stock mínimo") or Decimal(0),
        "proveedor_id": v.entero("proveedor_id"),
        "activo": v.booleano("activo"),
    }
    if datos["codigo"] and material_model.existe_codigo(datos["codigo"], material_id):
        v.error("codigo", "Ya existe un material con ese código.")
    if material_id and datos["unidad_id"]:
        actual = material_model.obtener(material_id)
        if actual and actual["unidad_id"] != datos["unidad_id"] and material_model.tiene_movimientos(material_id):
            v.error("unidad_id", "No se puede cambiar la unidad de stock de un material con movimientos. "
                                 "Creá conversiones para venderlo en otras unidades.")
    if (datos["precio_venta"] is not None and datos["precio_compra"] is not None
            and datos["precio_venta"] < datos["precio_compra"]):
        flash("Atención: el precio de venta es menor al de compra.", "warning")
    v.verificar()
    return datos


def _form(material=None, errores=None, datos=None):
    return render_template(
        "materiales/form.html", m=datos or material or {"activo": 1, "codigo": material_model.siguiente_codigo()},
        editando=material is not None, errores=errores or {},
        categorias=catalogos.opciones("categorias_materiales"), unidades=catalogos.unidades_opciones(),
        proveedores=proveedor_model.opciones())


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("materiales.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos = _leer_form()
            with transaction():
                mid = material_model.crear(datos)
                historial_service.registrar("crear", "materiales", f"creó el material {datos['nombre']} "
                                            f"({moneda(datos['precio_venta'])})", mid)
            flash(f"Material {datos['nombre']} creado.", "success")
            return redirect(url_for("materiales.ver", material_id=mid))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(errores=e.errores, datos=request.form)
    return _form()


@bp.route("/<int:material_id>/editar", methods=["GET", "POST"])
@permiso_requerido("materiales.gestionar")
def editar(material_id):
    material = material_model.obtener(material_id) or abort(404)
    if request.method == "POST":
        try:
            datos = _leer_form(material_id)
            with transaction():
                material_model.actualizar(material_id, datos)
                cambios = []
                if Decimal(material["precio_venta"]) != datos["precio_venta"]:
                    cambios.append(f"precio de venta {moneda(material['precio_venta'])} → {moneda(datos['precio_venta'])}")
                if Decimal(material["precio_compra"]) != datos["precio_compra"]:
                    cambios.append(f"precio de compra {moneda(material['precio_compra'])} → {moneda(datos['precio_compra'])}")
                if material["activo"] != datos["activo"]:
                    cambios.append("activado" if datos["activo"] else "desactivado")
                historial_service.registrar(
                    "modificar", "materiales",
                    f"modificó el material {datos['nombre']}" + (f": {', '.join(cambios)}" if cambios else ""), material_id)
            flash("Material actualizado.", "success")
            return redirect(url_for("materiales.ver", material_id=material_id))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(material, e.errores, {**request.form, "id": material_id})
    return _form(material)


@bp.route("/<int:material_id>")
@permiso_requerido("materiales.ver")
def ver(material_id):
    material = material_model.obtener(material_id) or abort(404)
    movimientos = stock_model.buscar(material_id=material_id, pagina=1).items if current_user.puede("stock.ver") else []
    return render_template(
        "materiales/ver.html", m=material, unidades=conversion_service.unidades_para_material(material),
        conversiones=conversion_model.listar(material_id=material_id), movimientos=movimientos[:10],
        unidades_opciones=catalogos.unidades_opciones())


@bp.route("/<int:material_id>/conversiones", methods=["POST"])
@permiso_requerido("materiales.gestionar", "parametros.gestionar")
def agregar_conversion(material_id):
    material = material_model.obtener(material_id) or abort(404)
    v = Validador(request.form)
    datos = {
        "material_id": material_id,
        "unidad_origen_id": v.entero("unidad_origen_id", True, etiqueta="Unidad origen"),
        "unidad_destino_id": v.entero("unidad_destino_id", True, etiqueta="Unidad destino"),
        "factor": v.decimal("factor", True, positivo=True, etiqueta="Factor"),
        "observaciones": v.texto("observaciones", maximo=255),
    }
    if datos["unidad_origen_id"] and datos["unidad_origen_id"] == datos["unidad_destino_id"]:
        v.error("unidad_destino_id", "Las unidades deben ser distintas.")
    if not v.errores and conversion_model.existe(material_id, datos["unidad_origen_id"], datos["unidad_destino_id"]):
        v.error("factor", "Esa conversión ya existe para este material.")
    try:
        v.verificar()
        cid = conversion_model.crear(datos)
        historial_service.registrar("crear", "materiales", f"agregó una conversión de unidades a {material['nombre']}", cid)
        flash("Conversión agregada.", "success")
    except ValidacionError as e:
        flash(e.mensaje, "danger")
    return redirect(url_for("materiales.ver", material_id=material_id) + "#conversiones")


@bp.route("/<int:material_id>/conversiones/<int:conv_id>/eliminar", methods=["POST"])
@permiso_requerido("materiales.gestionar", "parametros.gestionar")
def eliminar_conversion(material_id, conv_id):
    conv = conversion_model.obtener(conv_id)
    if not conv or conv["material_id"] != material_id:
        abort(404)
    conversion_model.eliminar(conv_id)
    historial_service.registrar("eliminar", "materiales", f"eliminó una conversión de {conv['material_nombre']}", conv_id)
    flash("Conversión eliminada.", "success")
    return redirect(url_for("materiales.ver", material_id=material_id) + "#conversiones")
