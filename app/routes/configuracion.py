"""Configuración: empresa, parámetros (catálogos), conversiones y facturación."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..database import execute, query, query_one, transaction
from ..models import catalogos, configuracion
from ..models import conversion as conversion_model
from ..services import historial_service
from ..services.facturacion import servicio as facturacion
from ..utils.decoradores import permiso_requerido
from ..utils.errores import ValidacionError
from ..utils.formato import opciones
from ..utils.validadores import Validador

bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")

# Campos editables por catálogo: (campo, etiqueta, tipo, requerido | opciones)
CAMPOS = {
    "categorias_materiales": [("nombre", "Nombre", "texto", True), ("descripcion", "Descripción", "texto", False),
                              ("activo", "Activo", "bool", None)],
    "unidades": [("codigo", "Código", "texto", True), ("nombre", "Nombre", "texto", True),
                 ("abreviatura", "Abreviatura", "texto", True),
                 ("magnitud", "Magnitud", "opcion", ["masa", "volumen", "conteo", "viaje", "otra"]),
                 ("activo", "Activa", "bool", None)],
    "zonas_entrega": [("nombre", "Nombre", "texto", True), ("descripcion", "Descripción / barrios", "texto", False),
                      ("distancia_km", "Distancia de referencia (km)", "decimal", False),
                      ("costo_fijo", "Costo fijo $", "decimal", False), ("costo_por_km", "Costo por km $", "decimal", False),
                      ("costo_por_unidad", "Costo por unidad de carga $", "decimal", False),
                      ("activo", "Activa", "bool", None)],
    "tipos_vehiculo": [("nombre", "Nombre", "texto", True), ("recargo_transporte", "Recargo de flete $", "decimal", False),
                       ("activo", "Activo", "bool", None)],
    "categorias_gastos": [("nombre", "Nombre", "texto", True), ("activo", "Activa", "bool", None)],
    "metodos_pago": [("codigo", "Código", "texto", True), ("nombre", "Nombre", "texto", True),
                     ("grupo", "Grupo", "opcion", ["efectivo", "transferencia", "tarjeta", "billetera", "cuenta_corriente", "otro"]),
                     ("activo", "Activo", "bool", None)],
}
UNICOS = {"categorias_materiales": "nombre", "unidades": "codigo", "zonas_entrega": "nombre",
          "tipos_vehiculo": "nombre", "categorias_gastos": "nombre", "metodos_pago": "codigo"}


def _secciones():
    s = []
    if current_user.puede("configuracion.gestionar"):
        s.append(("empresa", "Empresa y reglas"))
    if current_user.puede("parametros.gestionar"):
        s += [("zonas_entrega", "Zonas de entrega"), ("unidades", "Unidades"), ("conversiones", "Conversiones"),
              ("categorias_materiales", "Tipos de material"), ("tipos_vehiculo", "Tipos de vehículo"),
              ("categorias_gastos", "Categorías de gastos"), ("metodos_pago", "Métodos de pago")]
    if current_user.puede("facturacion.gestionar"):
        s.append(("facturacion", "Facturación ARCA"))
    return s


@bp.route("/")
@permiso_requerido("parametros.gestionar", "configuracion.gestionar", "facturacion.gestionar")
def index():
    secciones = _secciones()
    return redirect(url_for("configuracion.seccion", nombre=secciones[0][0]))


@bp.route("/<nombre>", methods=["GET", "POST"])
@permiso_requerido("parametros.gestionar", "configuracion.gestionar", "facturacion.gestionar")
def seccion(nombre):
    secciones = dict(_secciones())
    if nombre not in secciones:
        abort(403 if nombre in CAMPOS or nombre in ("empresa", "conversiones", "facturacion") else 404)
    if nombre == "empresa":
        return _empresa(secciones)
    if nombre == "conversiones":
        return _conversiones(secciones)
    if nombre == "facturacion":
        return _facturacion(secciones)
    return _catalogo(nombre, secciones)


# ------------------------------------------------------------------ empresa
def _empresa(secciones):
    if request.method == "POST":
        v = Validador(request.form)
        valores = {}
        for clave in configuracion.DEFINICIONES:
            if clave == "empresa_cuit":
                valores[clave] = v.cuit(clave) or ""
            elif clave == "permitir_stock_negativo":
                valores[clave] = str(v.booleano(clave))
            elif clave in ("presupuesto_validez_dias", "alerta_licencia_dias"):
                valores[clave] = str(v.entero(clave, True, minimo=1, maximo=365) or "")
            elif clave == "empresa_email":
                valores[clave] = v.email(clave) or ""
            else:
                valores[clave] = v.texto(clave, maximo=500) or ""
        try:
            v.verificar()
            configuracion.guardar(valores)
            historial_service.registrar("modificar", "configuracion", "actualizó los datos de la empresa y reglas")
            flash("Configuración guardada.", "success")
            return redirect(url_for("configuracion.seccion", nombre="empresa"))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return render_template("configuracion/empresa.html", secciones=secciones, actual="empresa",
                                   cfg=request.form, errores=e.errores)
    return render_template("configuracion/empresa.html", secciones=secciones, actual="empresa",
                           cfg=configuracion.todas(), errores={})


# ------------------------------------------------------------------ catálogos
def _catalogo(tabla, secciones):
    campos = CAMPOS[tabla]
    editar_id = request.args.get("editar", type=int)
    registro = catalogos.obtener(tabla, editar_id) if editar_id else None
    errores = {}
    if request.method == "POST":
        v = Validador(request.form)
        registro_id = request.form.get("id", type=int)
        datos = {}
        for campo, etq, tipo, extra in campos:
            if tipo == "texto":
                datos[campo] = v.texto(campo, bool(extra), 255 if campo == "descripcion" else 80, etiqueta=etq)
            elif tipo == "decimal":
                datos[campo] = v.decimal(campo, minimo=0, etiqueta=etq) or 0
            elif tipo == "opcion":
                datos[campo] = v.opcion(campo, extra, etiqueta=etq)
            elif tipo == "bool":
                datos[campo] = v.booleano(campo)
        unico = UNICOS[tabla]
        if datos.get(unico) and catalogos.existe_valor(tabla, unico, datos[unico], registro_id):
            v.error(unico, "Ya existe un registro con ese valor.")
        try:
            v.verificar()
            with transaction():
                if registro_id:
                    catalogos.actualizar(tabla, registro_id, datos)
                    accion = "modificó"
                else:
                    registro_id = catalogos.crear(tabla, datos)
                    accion = "creó"
                historial_service.registrar("modificar", "configuracion",
                                            f"{accion} {catalogos.CATALOGOS[tabla]['singular']} «{datos.get('nombre') or datos.get('codigo')}»",
                                            registro_id)
            flash("Guardado.", "success")
            return redirect(url_for("configuracion.seccion", nombre=tabla))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            errores = e.errores
            registro = {**request.form, "id": registro_id}
    return render_template("configuracion/catalogo.html", secciones=secciones, actual=tabla, tabla=tabla,
                           info=catalogos.CATALOGOS[tabla], campos=campos, filas=catalogos.listar(tabla),
                           registro=registro, errores=errores)


# ------------------------------------------------------------------ conversiones generales
def _conversiones(secciones):
    editar_id = request.args.get("editar", type=int)
    registro = conversion_model.obtener(editar_id) if editar_id else None
    if request.method == "POST":
        if request.form.get("eliminar"):
            cid = request.form.get("eliminar", type=int)
            conv = conversion_model.obtener(cid)
            if conv:
                conversion_model.eliminar(cid)
                historial_service.registrar("eliminar", "configuracion", "eliminó una conversión de unidades", cid)
                flash("Conversión eliminada.", "success")
            return redirect(url_for("configuracion.seccion", nombre="conversiones"))
        v = Validador(request.form)
        cid = request.form.get("id", type=int)
        datos = {
            "material_id": None,
            "unidad_origen_id": v.entero("unidad_origen_id", True, etiqueta="Unidad origen"),
            "unidad_destino_id": v.entero("unidad_destino_id", True, etiqueta="Unidad destino"),
            "factor": v.decimal("factor", True, positivo=True, etiqueta="Factor"),
            "observaciones": v.texto("observaciones", maximo=255),
        }
        if datos["unidad_origen_id"] and datos["unidad_origen_id"] == datos["unidad_destino_id"]:
            v.error("unidad_destino_id", "Las unidades deben ser distintas.")
        if not v.errores and conversion_model.existe(None, datos["unidad_origen_id"], datos["unidad_destino_id"], cid):
            v.error("factor", "Esa conversión general ya existe.")
        try:
            v.verificar()
            with transaction():
                if cid:
                    conversion_model.actualizar(cid, datos)
                else:
                    cid = conversion_model.crear(datos)
                historial_service.registrar("modificar", "configuracion", "guardó una conversión general de unidades", cid)
            flash("Conversión guardada.", "success")
            return redirect(url_for("configuracion.seccion", nombre="conversiones"))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
    return render_template("configuracion/conversiones.html", secciones=secciones, actual="conversiones",
                           generales=conversion_model.listar(solo_generales=True),
                           especificas=[c for c in conversion_model.listar() if c["material_id"]],
                           unidades=catalogos.unidades_opciones(), registro=registro)


# ------------------------------------------------------------------ facturación
def _facturacion(secciones):
    if request.method == "POST":
        v = Validador(request.form)
        pv_id = request.form.get("id", type=int)
        datos = {"numero": v.entero("numero", True, minimo=1, maximo=99998, etiqueta="Número"),
                 "descripcion": v.texto("descripcion", maximo=100),
                 "modalidad": v.opcion("modalidad", ("electronico", "manual"), defecto="electronico"),
                 "activo": v.booleano("activo")}
        dup = query_one("SELECT id FROM puntos_venta WHERE numero = %s AND id <> %s", (datos["numero"], pv_id or 0))
        if dup:
            v.error("numero", "Ese punto de venta ya existe.")
        try:
            v.verificar()
            if pv_id:
                execute("UPDATE puntos_venta SET numero=%s, descripcion=%s, modalidad=%s, activo=%s WHERE id=%s",
                        (datos["numero"], datos["descripcion"], datos["modalidad"], datos["activo"], pv_id))
            else:
                execute("INSERT INTO puntos_venta (numero, descripcion, modalidad, activo) VALUES (%s,%s,%s,%s)",
                        (datos["numero"], datos["descripcion"], datos["modalidad"], datos["activo"]))
            historial_service.registrar("modificar", "facturacion", f"guardó el punto de venta {datos['numero']}")
            flash("Punto de venta guardado.", "success")
        except ValidacionError as e:
            flash(e.mensaje, "danger")
        return redirect(url_for("configuracion.seccion", nombre="facturacion"))
    return render_template(
        "configuracion/facturacion.html", secciones=secciones, actual="facturacion",
        estado=facturacion.estado_integracion(), puntos=facturacion.puntos_venta(),
        tipos=query("SELECT * FROM tipos_comprobante ORDER BY codigo"), cfg=configuracion.todas(),
        ultimos=query("""SELECT c.*, t.descripcion AS tipo_desc FROM comprobantes c
                         JOIN tipos_comprobante t ON t.codigo = c.tipo_comprobante ORDER BY c.id DESC LIMIT 10"""))
