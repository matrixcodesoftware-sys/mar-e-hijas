"""API interna JSON para la interfaz (autocompletado, precios, flete, gráficos, notificaciones)."""
from datetime import timedelta

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..models import caja as caja_model
from ..models import cliente as cliente_model
from ..models import material as material_model
from ..models import proveedor as proveedor_model
from ..services import conversion_service, notificacion_service, reporte_service, transporte_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import NegocioError
from ..utils.fechas import hoy
from ..utils.formato import cantidad, fecha_hora, moneda

bp = Blueprint("api", __name__, url_prefix="/api")


def _q():
    return (request.args.get("q") or "").strip()[:60]


@bp.route("/estado")
@login_required
def estado():
    datos = {"notificaciones": notificacion_service.para(current_user)}
    if current_user.puede("caja.ver") or current_user.puede("caja.operar") or current_user.puede("ventas.crear"):
        caja = caja_model.abierta()
        datos["caja"] = {"abierta": bool(caja),
                         "texto": f"Abierta por {caja['usuario_apertura']} el {fecha_hora(caja['fecha_apertura'])}"
                         if caja else "No hay caja abierta"}
    return jsonify(datos)


@bp.route("/clientes/buscar")
@permiso_requerido("clientes.ver", "ventas.crear", "presupuestos.gestionar", "pedidos.gestionar")
def clientes_buscar():
    q = _q()
    if not q:
        return jsonify(resultados=[])
    res = []
    for c in cliente_model.autocompletar(q):
        detalle = " · ".join(x for x in [c["documento"], c["localidad"], c["telefono"]] if x)
        if c["saldo"] and c["saldo"] > 0:
            detalle += f" · debe {moneda(c['saldo'])}"
        res.append({"id": c["id"], "texto": c["razon_social"], "detalle": detalle, "direccion": c["direccion"],
                    "localidad": c["localidad"], "zona_id": c["zona_id"], "referencia": c["referencia_ubicacion"],
                    "saldo": str(c["saldo"] or 0), "limite": str(c["limite_credito"] or 0),
                    "telefono": c["whatsapp"] or c["telefono"]})
    return jsonify(resultados=res)


@bp.route("/proveedores/buscar")
@permiso_requerido("proveedores.ver", "stock.gestionar", "materiales.gestionar", "gastos.gestionar")
def proveedores_buscar():
    q = _q()
    return jsonify(resultados=[{"id": p["id"], "texto": p["razon_social"], "detalle": p["cuit"] or ""}
                               for p in proveedor_model.autocompletar(q)] if q else [])


@bp.route("/materiales/buscar")
@permiso_requerido("materiales.ver", "ventas.crear", "presupuestos.gestionar", "pedidos.gestionar", "stock.gestionar")
def materiales_buscar():
    q = _q()
    if not q:
        return jsonify(resultados=[])
    res = []
    for m in material_model.autocompletar(q):
        res.append({
            "id": m["id"], "texto": m["nombre"],
            "detalle": f"{m['codigo']} · {moneda(m['precio_venta'])}/{m['unidad_abrev']} · stock {cantidad(m['stock_actual'])} {m['unidad_abrev']}",
            "stock": str(m["stock_actual"]), "unidad_stock": m["unidad_abrev"], "unidad_id": m["unidad_id"],
            "unidades": conversion_service.unidades_para_material(m),
        })
    return jsonify(resultados=res)


@bp.route("/materiales/<int:material_id>/unidades")
@permiso_requerido("materiales.ver", "ventas.crear", "presupuestos.gestionar", "pedidos.gestionar", "stock.gestionar")
def material_unidades(material_id):
    m = material_model.obtener(material_id)
    if not m:
        return jsonify(error="Material inexistente"), 404
    return jsonify(unidades=conversion_service.unidades_para_material(m), stock=str(m["stock_actual"]),
                   unidad_stock=m["unidad_abrev"])


@bp.route("/transporte/cotizar")
@permiso_requerido("ventas.crear", "presupuestos.gestionar", "pedidos.gestionar")
def transporte_cotizar():
    try:
        return jsonify(transporte_service.cotizar(request.args.get("zona_id"), request.args.get("cantidad"),
                                                  request.args.get("distancia"), request.args.get("tipo_vehiculo_id")))
    except NegocioError as e:
        return jsonify(error=e.mensaje), 422


@bp.route("/dashboard/graficos")
@permiso_requerido("dashboard.ver")
def dashboard_graficos():
    h = hoy()
    desde30 = h - timedelta(days=29)
    finanzas = current_user.puede("dashboard.finanzas")
    por_dia = reporte_service.ventas_por_dia(desde30, h)
    por_mes = reporte_service.ventas_por_mes(12)
    materiales = [m for m in reporte_service.ranking_materiales(h.replace(day=1), h, "facturacion", 6) if m["facturacion"]]
    metodos = reporte_service.metodos_pago(h.replace(day=1), h)

    def _f(v):
        return float(v or 0)

    datos = {
        "por_dia": {"etiquetas": [d["etiqueta"] for d in por_dia], "cantidad": [d["cantidad"] for d in por_dia]},
        "materiales": {"etiquetas": [m["nombre"] for m in materiales],
                       "cantidad": [_f(m["cantidad"]) for m in materiales],
                       "unidades": [m["unidad"] for m in materiales]},
    }
    if finanzas:
        datos["por_dia"]["total"] = [_f(d["total"]) for d in por_dia]
        datos["por_mes"] = {"etiquetas": [d["etiqueta"] for d in por_mes], "total": [_f(d["total"]) for d in por_mes],
                            "ganancia": [_f(d["ganancia"]) for d in por_mes]}
        datos["materiales"]["facturacion"] = [_f(m["facturacion"]) for m in materiales]
        datos["metodos"] = {"etiquetas": [m["nombre"] for m in metodos], "total": [_f(m["total"]) for m in metodos]}
    return jsonify(datos)
