"""Camiones y vehículos."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..database import query, transaction
from ..models import catalogos, flota
from ..models import gasto as gasto_model
from ..services import historial_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import ValidacionError
from ..utils.fechas import hoy
from ..utils.formato import opciones
from ..utils.validadores import Validador
from ._comun import arg_int, arg_txt, hay_busqueda

bp = Blueprint("vehiculos", __name__, url_prefix="/camiones")
ESTADOS = [k for k, _ in opciones("estado_vehiculo")]


@bp.route("/")
@permiso_requerido("vehiculos.ver")
def index():
    # La flota de un galpón es chica: se muestra completa sin necesidad de buscar.
    pagina = flota.buscar_vehiculos(texto=arg_txt("q"), tipo_id=arg_int("tipo_id"), estado=arg_txt("estado"))
    return render_template("camiones/index.html", pagina=pagina, tipos=catalogos.opciones("tipos_vehiculo"))


def _leer_form(vehiculo_id=None):
    v = Validador(request.form)
    datos = {
        "patente": v.patente("patente"),
        "tipo_vehiculo_id": v.entero("tipo_vehiculo_id", True, etiqueta="Tipo"),
        "marca": v.texto("marca", maximo=60),
        "modelo": v.texto("modelo", maximo=60),
        "anio": v.entero("anio", minimo=1950, maximo=hoy().year + 1, etiqueta="Año"),
        "capacidad": v.decimal("capacidad", True, positivo=True, etiqueta="Capacidad"),
        "unidad_capacidad_id": v.entero("unidad_capacidad_id", True, etiqueta="Unidad de capacidad"),
        "estado": v.opcion("estado", ESTADOS, defecto="disponible"),
        "chofer_id": v.entero("chofer_id"),
        "observaciones": v.texto("observaciones", maximo=2000),
    }
    if datos["patente"] and flota.existe_patente(datos["patente"], vehiculo_id):
        v.error("patente", "Ya existe un vehículo con esa patente.")
    v.verificar()
    return datos


def _form(vehiculo=None, errores=None, datos=None):
    return render_template("camiones/form.html", v=datos or vehiculo or {"estado": "disponible"},
                           editando=vehiculo is not None, errores=errores or {},
                           tipos=catalogos.opciones("tipos_vehiculo"), unidades=catalogos.unidades_opciones(),
                           choferes=flota.opciones_choferes())


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("vehiculos.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos = _leer_form()
            with transaction():
                vid = flota.crear_vehiculo(datos)
                historial_service.registrar("crear", "vehiculos", f"dio de alta el vehículo {datos['patente']}", vid)
            flash("Vehículo creado.", "success")
            return redirect(url_for("vehiculos.ver", vehiculo_id=vid))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(errores=e.errores, datos=request.form)
    return _form()


@bp.route("/<int:vehiculo_id>/editar", methods=["GET", "POST"])
@permiso_requerido("vehiculos.gestionar")
def editar(vehiculo_id):
    vehiculo = flota.vehiculo(vehiculo_id) or abort(404)
    if request.method == "POST":
        try:
            datos = _leer_form(vehiculo_id)
            with transaction():
                flota.actualizar_vehiculo(vehiculo_id, datos)
                historial_service.registrar("modificar", "vehiculos", f"modificó el vehículo {datos['patente']}",
                                            vehiculo_id)
            flash("Vehículo actualizado.", "success")
            return redirect(url_for("vehiculos.ver", vehiculo_id=vehiculo_id))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(vehiculo, e.errores, {**request.form, "id": vehiculo_id})
    return _form(vehiculo)


@bp.route("/<int:vehiculo_id>")
@permiso_requerido("vehiculos.ver")
def ver(vehiculo_id):
    vehiculo = flota.vehiculo(vehiculo_id) or abort(404)
    entregas = query(
        """SELECT e.id, e.fecha, e.estado, cl.razon_social AS cliente, CONCAT(ch.nombre,' ',ch.apellido) AS chofer
           FROM entregas e JOIN clientes cl ON cl.id = e.cliente_id LEFT JOIN choferes ch ON ch.id = e.chofer_id
           WHERE e.vehiculo_id = %s ORDER BY e.fecha DESC, e.id DESC LIMIT 15""", (vehiculo_id,))
    gastos = gasto_model.buscar(vehiculo_id=vehiculo_id, pagina=1).items[:10]
    return render_template("camiones/ver.html", v=vehiculo, entregas=entregas, gastos=gastos)
