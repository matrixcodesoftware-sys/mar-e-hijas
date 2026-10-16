"""Stock: situación actual, entradas, ajustes e historial de movimientos."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..models import catalogos, flota
from ..models import material as material_model
from ..models import stock as stock_model
from ..services import stock_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError, ValidacionError
from ..utils.fechas import hoy, inicio_dia, rango_periodo
from ..utils.validadores import Validador
from ._comun import arg_fecha, arg_int, arg_txt, hay_busqueda

bp = Blueprint("stock", __name__, url_prefix="/stock")


@bp.route("/")
@permiso_requerido("stock.ver")
def index():
    desde, hasta = rango_periodo(request.args.get("periodo", "mes"), request.args.get("desde"), request.args.get("hasta"))
    filas = stock_model.totales_por_material(desde, hasta)
    if request.args.get("bajo"):
        filas = [f for f in filas if f["stock_actual"] <= f["stock_minimo"]]
    return render_template("stock/index.html", filas=filas, desde=desde, hasta=hasta)


@bp.route("/movimientos")
@permiso_requerido("stock.ver")
def movimientos():
    pagina = None
    if hay_busqueda():
        pagina = stock_model.buscar(material_id=arg_int("material_id"), tipo=arg_txt("tipo"), desde=arg_fecha("desde"),
                                    hasta=arg_fecha("hasta"), proveedor_id=arg_int("proveedor_id"),
                                    remito=arg_txt("remito"))
    return render_template("stock/movimientos.html", pagina=pagina, materiales=material_model.opciones())


def _form_entrada(errores=None, datos=None):
    return render_template(
        "stock/entrada.html", errores=errores or {}, d=datos or {"fecha": hoy().isoformat(),
                                                                  "material_id": request.args.get("material_id")},
        materiales=material_model.opciones(), unidades=catalogos.unidades_opciones(),
        vehiculos=flota.opciones_vehiculos(), metodos=catalogos.metodos_pago(incluir_cta_cte=False))


@bp.route("/entrada", methods=["GET", "POST"])
@permiso_requerido("stock.gestionar")
def entrada():
    if request.method == "POST":
        v = Validador(request.form)
        datos = {
            "material_id": v.entero("material_id", True, etiqueta="Material"),
            "cantidad": v.decimal("cantidad", True, positivo=True, etiqueta="Cantidad"),
            "unidad_id": v.entero("unidad_id", True, etiqueta="Unidad"),
            "proveedor_id": v.entero("proveedor_id"),
            "fecha": v.fecha("fecha", True, etiqueta="Fecha"),
            "vehiculo_id": v.entero("vehiculo_id"),
            "vehiculo_descripcion": v.texto("vehiculo_descripcion", maximo=120),
            "remito_numero": v.texto("remito_numero", maximo=40, etiqueta="Número de remito"),
            "costo_total": v.decimal("costo_total", minimo=0, etiqueta="Costo total"),
            "observaciones": v.texto("observaciones", maximo=255),
            "condicion": v.opcion("condicion", ("cuenta", "contado"), defecto="cuenta"),
            "metodo_pago_id": v.entero("metodo_pago_id"),
            "actualizar_precio": v.booleano("actualizar_precio"),
        }
        if datos["fecha"] and datos["fecha"] > hoy():
            v.error("fecha", "La fecha no puede ser futura.")
        if datos["condicion"] == "contado" and datos["costo_total"] and not datos["metodo_pago_id"]:
            v.error("metodo_pago_id", "Indicá con qué se pagó.")
        try:
            v.verificar()
            if datos["fecha"] and datos["fecha"] != hoy():
                datos["fecha"] = inicio_dia(datos["fecha"]).replace(hour=12)
            else:
                datos["fecha"] = None
            stock_service.registrar_entrada(datos, current_user.id)
            flash("Entrada registrada y stock actualizado.", "success")
            if request.form.get("otra"):
                return redirect(url_for("stock.entrada"))
            return redirect(url_for("stock.movimientos", tipo="entrada", buscar=1))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form_entrada(e.errores, request.form)
        except NegocioError as e:
            flash(e.mensaje, "danger")
            return _form_entrada({}, request.form)
    return _form_entrada()


@bp.route("/ajuste", methods=["GET", "POST"])
@permiso_requerido("stock.gestionar")
def ajuste():
    if request.method == "POST":
        v = Validador(request.form)
        material_id = v.entero("material_id", True, etiqueta="Material")
        modo = v.opcion("modo", ("conteo", "sumar", "restar"), etiqueta="Tipo de ajuste")
        valor = v.decimal("valor", True, minimo=0, etiqueta="Cantidad")
        unidad_id = v.entero("unidad_id", True, etiqueta="Unidad")
        motivo = v.texto("motivo", True, 255, etiqueta="Motivo")
        try:
            v.verificar()
            stock_service.registrar_ajuste(material_id, modo, valor, unidad_id, motivo, current_user.id)
            flash("Ajuste registrado.", "success")
            return redirect(url_for("stock.movimientos", tipo="ajuste", buscar=1))
        except (ValidacionError, NegocioError) as e:
            flash(e.mensaje, "danger")
            return render_template("stock/ajuste.html", d=request.form, errores=getattr(e, "errores", {}),
                                   materiales=material_model.opciones(), unidades=catalogos.unidades_opciones())
    return render_template("stock/ajuste.html", d={"material_id": request.args.get("material_id"), "modo": "conteo"},
                           errores={}, materiales=material_model.opciones(), unidades=catalogos.unidades_opciones())
