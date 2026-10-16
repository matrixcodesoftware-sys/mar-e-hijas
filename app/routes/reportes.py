"""Reportes con gráficos y exportación CSV / PDF."""
from decimal import Decimal

from flask import Blueprint, abort, redirect, render_template, request, url_for

from ..models import cliente as cliente_model
from ..models import material as material_model
from ..models import usuario as usuario_model
from ..services import pdf_service, reporte_service
from ..utils.decoradores import permiso_requerido
from ..utils.fechas import rango_periodo
from ..utils.formato import cantidad, etiqueta, fecha, moneda
from ._comun import arg_int, num_csv, respuesta_csv, respuesta_pdf

bp = Blueprint("reportes", __name__, url_prefix="/reportes")

TIPOS = {"ventas": "Ventas", "materiales": "Materiales", "clientes": "Clientes", "entregas": "Entregas"}


def _f(v):
    return float(v or 0)


@bp.route("/")
@permiso_requerido("reportes.ver")
def index():
    return redirect(url_for("reportes.ver", tipo="ventas"))


@bp.route("/<tipo>")
@permiso_requerido("reportes.ver")
def ver(tipo):
    if tipo not in TIPOS:
        abort(404)
    periodo = request.args.get("periodo", "mes")
    desde, hasta = rango_periodo(periodo, request.args.get("desde"), request.args.get("hasta"))
    filtros = {"cliente_id": arg_int("cliente_id"), "usuario_id": arg_int("usuario_id"),
               "material_id": arg_int("material_id")}
    subtitulo = f"Período {fecha(desde)} al {fecha(hasta)}"
    formato = request.args.get("formato")
    ctx = {"tipo": tipo, "tipos": TIPOS, "desde": desde, "hasta": hasta, "periodo": periodo, "grafico": None,
           "mensual_json": None, "orden": None}

    if tipo == "ventas":
        resumen = reporte_service.ventas_resumen(desde, hasta, **filtros)
        por_dia = reporte_service.ventas_por_dia(desde, hasta, **filtros)
        vendedores = reporte_service.ventas_por_vendedor(desde, hasta, **filtros)
        metodos = reporte_service.metodos_pago(desde, hasta, **filtros)
        if formato:
            cab = ["Fecha", "Cantidad de ventas", "Facturación", "Ganancia estimada"]
            filas = [[fecha(d["fecha"]), d["cantidad"], d["total"], d["ganancia"]] for d in por_dia]
            res = [("Ventas", resumen["cantidad"]), ("Facturación", moneda(resumen["facturacion"])),
                   ("Ganancia", moneda(resumen["ganancia"]))]
            if filtros["material_id"]:
                res.append(("Cantidad vendida del material", cantidad(resumen.get("cantidad_material"))))
            return _exportar(formato, "reporte_ventas", "Reporte de ventas", subtitulo, cab, filas, (1, 2, 3), res,
                             monedas=(2, 3))
        ctx.update(resumen=resumen, por_vendedor=vendedores, metodos=metodos,
                   grafico={"etiquetas": [d["etiqueta"] for d in por_dia], "total": [_f(d["total"]) for d in por_dia],
                            "ganancia": [_f(d["ganancia"]) for d in por_dia],
                            "cantidad": [d["cantidad"] for d in por_dia],
                            "metodos": {"etiquetas": [m["nombre"] for m in metodos], "total": [_f(m["total"]) for m in metodos]}},
                   mensual=reporte_service.ventas_por_mes(12, **filtros))
        ctx["mensual_json"] = {"etiquetas": [m["etiqueta"] for m in ctx["mensual"]],
                               "total": [_f(m["total"]) for m in ctx["mensual"]]}

    elif tipo == "materiales":
        orden = request.args.get("orden", "cantidad")
        ranking = reporte_service.ranking_materiales(desde, hasta, orden, **{k: v for k, v in filtros.items() if k != "material_id"})
        bajo = material_model.bajo_stock(50)
        if formato:
            cab = ["Código", "Material", "Unidad", "Cantidad vendida", "Facturación", "Ganancia", "Ventas"]
            filas = [[m["codigo"], m["nombre"], m["unidad"], m["cantidad"], m["facturacion"], m["ganancia"], m["ventas"]]
                     for m in ranking]
            return _exportar(formato, "reporte_materiales", "Reporte de materiales", subtitulo, cab, filas,
                             (3, 4, 5, 6), monedas=(4, 5), cantidades=(3,))
        top = [m for m in ranking if m["cantidad"]][:10] if orden != "menos" else ranking[:10]
        ctx.update(ranking=ranking, bajo=bajo, orden=orden,
                   grafico={"etiquetas": [m["nombre"] for m in top], "facturacion": [_f(m["facturacion"]) for m in top],
                            "cantidad": [_f(m["cantidad"]) for m in top]})

    elif tipo == "clientes":
        orden = request.args.get("orden", "consumo")
        ranking = reporte_service.ranking_clientes(desde, hasta, orden, 50)
        deudores = reporte_service.clientes_con_deuda(100)
        if formato:
            if request.args.get("lista") == "deudores":
                cab = ["Cliente", "Tipo", "Teléfono", "Saldo", "Límite", "Último pago"]
                filas = [[c["razon_social"], etiqueta(c["tipo"], "tipo_cliente"), c["whatsapp"] or c["telefono"] or "",
                          c["saldo"], c["limite_credito"], fecha(c["ultimo_pago"])] for c in deudores]
                total = sum((Decimal(c["saldo"]) for c in deudores), Decimal(0))
                return _exportar(formato, "clientes_con_deuda", "Clientes con deuda", f"Al {fecha(hasta)}", cab, filas,
                                 (3, 4), [("Total adeudado", moneda(total))], monedas=(3, 4))
            cab = ["Cliente", "Tipo", "Compras", "Total comprado", "Última compra", "Saldo cta. cte."]
            filas = [[c["razon_social"], etiqueta(c["tipo"], "tipo_cliente"), c["compras"], c["total"],
                      fecha(c["ultima"]), c["saldo"]] for c in ranking]
            return _exportar(formato, "reporte_clientes", "Clientes por consumo" if orden == "consumo" else "Clientes frecuentes",
                             subtitulo, cab, filas, (2, 3, 5), monedas=(3, 5))
        top = ranking[:10]
        ctx.update(ranking=ranking, deudores=deudores, orden=orden,
                   grafico={"etiquetas": [c["razon_social"] for c in top], "total": [_f(c["total"]) for c in top]})

    elif tipo == "entregas":
        resumen = reporte_service.entregas_resumen(desde, hasta)
        por_chofer = reporte_service.entregas_por_chofer(desde, hasta)
        por_vehiculo = reporte_service.entregas_por_vehiculo(desde, hasta)
        por_fecha = reporte_service.entregas_por_fecha(desde, hasta)
        if formato:
            agrupar = request.args.get("agrupar", "chofer")
            datos = por_vehiculo if agrupar == "vehiculo" else por_chofer
            cab = ["Vehículo" if agrupar == "vehiculo" else "Chofer", "Total", "Entregadas", "Pendientes",
                   "No entregadas", "Canceladas"]
            filas = [[d["nombre"], d["total"], d["entregadas"], d["pendientes"], d["no_entregadas"], d["canceladas"]]
                     for d in datos]
            res = [("Total", resumen["total"]), ("Entregadas", resumen["entregadas"] or 0),
                   ("Pendientes", resumen["pendientes"] or 0), ("Canceladas", resumen["canceladas"] or 0)]
            return _exportar(formato, f"entregas_por_{agrupar}", "Reporte de entregas", subtitulo, cab, filas,
                             (1, 2, 3, 4, 5), res)
        ctx.update(resumen=resumen, por_chofer=por_chofer, por_vehiculo=por_vehiculo,
                   grafico={"etiquetas": [d["etiqueta"] for d in por_fecha],
                            "entregadas": [int(d["entregadas"]) for d in por_fecha],
                            "pendientes": [int(d["pendientes"]) for d in por_fecha],
                            "canceladas": [int(d["canceladas"]) for d in por_fecha]})

    ctx.update(materiales=material_model.opciones(), vendedores=usuario_model.listar_activos(),
               cliente_sel=cliente_model.obtener(filtros["cliente_id"]) if filtros["cliente_id"] else None)
    return render_template("reportes/index.html", **ctx)


def _exportar(formato, nombre, titulo, subtitulo, cabecera, filas, derecha=(), resumen=None, monedas=(), cantidades=()):
    if formato == "csv":
        filas_csv = []
        for f in filas:
            fila = []
            for i, v in enumerate(f):
                if i in monedas:
                    fila.append(num_csv(v, 2))
                elif i in cantidades:
                    fila.append(num_csv(v, 3))
                else:
                    fila.append(v)
            filas_csv.append(fila)
        return respuesta_csv(nombre, cabecera, filas_csv)
    if formato == "pdf":
        filas_pdf = []
        for f in filas:
            fila = []
            for i, v in enumerate(f):
                if i in monedas:
                    fila.append(moneda(v))
                elif i in cantidades:
                    fila.append(cantidad(v))
                else:
                    fila.append("" if v is None else str(v))
            filas_pdf.append(fila)
        return respuesta_pdf(nombre, pdf_service.tabla_pdf(titulo, subtitulo, cabecera, filas_pdf, derecha, resumen))
    abort(400)
