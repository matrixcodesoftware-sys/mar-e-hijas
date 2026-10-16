"""Generación de PDFs con ReportLab (100 % Python, sin dependencias del sistema).

- presupuesto_pdf: presupuesto imprimible para el cliente.
- venta_pdf: comprobante interno / remito (NO válido como factura).
- cuenta_pdf: resumen de cuenta corriente.
- tabla_pdf: exportación genérica de reportes.
"""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import configuracion
from ..utils.fechas import ahora
from ..utils.formato import cantidad, etiqueta, fecha, fecha_hora, moneda

GRAFITO = colors.HexColor("#1f262b")
OCRE = colors.HexColor("#d49a3a")
GRIS = colors.HexColor("#56626a")
FONDO = colors.HexColor("#f3f1ec")
BORDE = colors.HexColor("#e0dbd1")

_base = getSampleStyleSheet()
E = {
    "normal": ParagraphStyle("n", parent=_base["Normal"], fontName="Helvetica", fontSize=9, leading=12),
    "chico": ParagraphStyle("c", parent=_base["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=GRIS),
    "titulo": ParagraphStyle("t", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=19,
                             textColor=GRAFITO),
    "marca": ParagraphStyle("m", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=20,
                            textColor=GRAFITO),
    "sub": ParagraphStyle("s", parent=_base["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=OCRE),
    "derecha": ParagraphStyle("d", parent=_base["Normal"], fontName="Helvetica", fontSize=9, leading=12,
                              alignment=TA_RIGHT),
    "negrita": ParagraphStyle("b", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=12),
    "cabecera": ParagraphStyle("h", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11,
                               textColor=colors.white),
}


def _p(texto, estilo="normal"):
    from xml.sax.saxutils import escape

    return Paragraph(escape(str(texto if texto is not None else "")).replace("\n", "<br/>"), E[estilo])


def _encabezado(titulo, numero=None, fecha_doc=None, subtitulo=None):
    cfg = configuracion.todas()
    empresa = [
        _p(cfg.get("empresa_nombre") or "MAR E HIJAS", "marca"),
        _p("Venta y distribución de áridos", "sub"),
        _p(" · ".join(x for x in [cfg.get("empresa_direccion"), cfg.get("empresa_localidad")] if x), "chico"),
        _p(" · ".join(x for x in [f"Tel. {cfg['empresa_telefono']}" if cfg.get("empresa_telefono") else "",
                                  f"WhatsApp {cfg['empresa_whatsapp']}" if cfg.get("empresa_whatsapp") else "",
                                  cfg.get("empresa_email")] if x), "chico"),
    ]
    if cfg.get("empresa_cuit"):
        empresa.append(_p(f"CUIT {cfg['empresa_cuit']} · {etiqueta(cfg.get('empresa_condicion_iva'), 'condicion_iva')}",
                          "chico"))
    doc = [_p(titulo, "titulo")]
    if numero:
        doc.append(_p(f"N.º {numero}", "negrita"))
    if fecha_doc:
        doc.append(_p(f"Fecha: {fecha(fecha_doc)}"))
    if subtitulo:
        doc.append(_p(subtitulo, "chico"))
    t = Table([[empresa, doc]], colWidths=[110 * mm, 70 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 2, OCRE),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [t, Spacer(1, 6 * mm)]


def _caja_cliente(cliente):
    filas = [
        [_p("Cliente", "chico"), _p(cliente.get("razon_social") or cliente.get("cliente"), "negrita")],
    ]
    doc = cliente.get("documento") or cliente.get("cliente_documento")
    if doc:
        filas.append([_p("DNI / CUIT", "chico"), _p(doc)])
    dir_ = cliente.get("direccion") or cliente.get("cliente_direccion")
    if dir_:
        filas.append([_p("Dirección", "chico"), _p(", ".join(x for x in [dir_, cliente.get("localidad") or cliente.get("cliente_localidad")] if x))])
    tel = cliente.get("telefono") or cliente.get("cliente_telefono")
    if tel:
        filas.append([_p("Teléfono", "chico"), _p(tel)])
    t = Table(filas, colWidths=[30 * mm, 150 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), FONDO), ("BOX", (0, 0), (-1, -1), 0.5, BORDE),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return [t, Spacer(1, 5 * mm)]


def _tabla(cabecera, filas, anchos, alinear_derecha=(), pie=None):
    datos = [[_p(c, "cabecera") for c in cabecera]]
    for f in filas:
        datos.append([_p(v, "derecha") if i in alinear_derecha else _p(v) for i, v in enumerate(f)])
    if pie:
        datos.append([_p(v, "negrita") if i not in alinear_derecha else Paragraph(f"<b>{v}</b>", E["derecha"])
                      for i, v in enumerate(pie)])
    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), GRAFITO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(len(cabecera)):
        if i in alinear_derecha:
            estilo.append(("ALIGN", (i, 0), (i, -1), "RIGHT"))
    if pie:
        estilo.append(("BACKGROUND", (0, -1), (-1, -1), FONDO))
    t.setStyle(TableStyle(estilo))
    return t


def _totales(pares):
    filas = []
    for i, (k, v) in enumerate(pares):
        ultimo = i == len(pares) - 1
        filas.append([_p(k, "negrita" if ultimo else "normal"),
                      Paragraph(f"<b>{v}</b>" if ultimo else v, E["derecha"])])
    t = Table(filas, colWidths=[40 * mm, 35 * mm], hAlign="RIGHT")
    t.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 1.2, GRAFITO), ("FONTSIZE", (0, -1), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def _pie(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRIS)
    canvas.drawString(15 * mm, 10 * mm, f"MAR E HIJAS · Sistema de Gestión de Áridos · generado {fecha_hora(ahora())}")
    canvas.drawRightString(doc.pagesize[0] - 15 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _construir(historia, apaisado=False, titulo="Documento"):
    buffer = io.BytesIO()
    tam = landscape(A4) if apaisado else A4
    doc = SimpleDocTemplate(buffer, pagesize=tam, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=16 * mm, title=titulo, author="MAR E HIJAS")
    doc.build(historia, onFirstPage=_pie, onLaterPages=_pie)
    return buffer.getvalue()


def _lineas_items(detalle):
    filas = []
    for d in detalle:
        filas.append([
            d["material"], f"{cantidad(d['cantidad'])} {d['unidad']}", moneda(d["precio_unitario"]),
            f"{cantidad(d['descuento_pct'])} %" if Decimal(d["descuento_pct"] or 0) else "—", moneda(d["subtotal"]),
        ])
    return filas


def presupuesto_pdf(p, detalle):
    historia = _encabezado("PRESUPUESTO", f"PR-{p['id']:06d}", p["fecha"],
                           f"Válido hasta el {fecha(p['fecha_vencimiento'])}")
    historia += _caja_cliente(p)
    historia.append(_tabla(["Material", "Cantidad", "Precio unit.", "Desc.", "Subtotal"], _lineas_items(detalle),
                           [70 * mm, 30 * mm, 30 * mm, 18 * mm, 32 * mm], alinear_derecha=(1, 2, 3, 4)))
    historia.append(Spacer(1, 4 * mm))
    pares = [("Subtotal", moneda(p["subtotal"]))]
    if p["descuento_general"]:
        pares.append(("Descuento", "- " + moneda(p["descuento_general"])))
    if p["tipo_entrega"] == "envio":
        pares.append((f"Flete{(' · ' + p['zona']) if p.get('zona') else ''}", moneda(p["costo_envio"])))
    pares.append(("TOTAL", moneda(p["total"])))
    historia.append(_totales(pares))
    historia.append(Spacer(1, 6 * mm))
    entrega = "Retiro en galpón" if p["tipo_entrega"] == "retiro" else f"Envío a: {p.get('direccion_entrega') or '—'}"
    historia.append(_p(f"Entrega: {entrega}"))
    if p.get("observaciones"):
        historia.append(_p(f"Observaciones: {p['observaciones']}"))
    historia.append(Spacer(1, 4 * mm))
    historia.append(_p(configuracion.get("presupuesto_leyenda") or "", "chico"))
    historia.append(_p(f"Atendido por: {p.get('usuario') or ''}", "chico"))
    return _construir(historia, titulo=f"Presupuesto PR-{p['id']:06d}")


def venta_pdf(v, detalle, pagos):
    historia = _encabezado("COMPROBANTE DE VENTA", f"V-{v['id']:06d}", v["fecha"],
                           "Documento interno — no válido como factura")
    historia += _caja_cliente(v)
    historia.append(_tabla(["Material", "Cantidad", "Precio unit.", "Desc.", "Subtotal"], _lineas_items(detalle),
                           [70 * mm, 30 * mm, 30 * mm, 18 * mm, 32 * mm], alinear_derecha=(1, 2, 3, 4)))
    historia.append(Spacer(1, 4 * mm))
    pares = [("Subtotal", moneda(v["subtotal"]))]
    if v["descuento_general"]:
        pares.append(("Descuento", "- " + moneda(v["descuento_general"])))
    if v["tipo_entrega"] == "envio":
        pares.append(("Flete", moneda(v["costo_envio"])))
    pares.append(("TOTAL", moneda(v["total"])))
    historia.append(_totales(pares))
    historia.append(Spacer(1, 5 * mm))
    for pg in pagos:
        historia.append(_p(f"Pago {pg['metodo']}: {moneda(pg['monto'])}"
                           + (f" (ref. {pg['referencia']})" if pg.get("referencia") else "")
                           + (" — ANULADO" if pg["estado"] == "anulado" else "")))
    if Decimal(v["saldo_cta_cte"]):
        historia.append(_p(f"Saldo a cuenta corriente: {moneda(v['saldo_cta_cte'])}", "negrita"))
    if v["tipo_entrega"] == "envio":
        historia.append(_p(f"Entrega en: {v.get('direccion_entrega') or ''}"))
    if v["estado"] == "anulada":
        historia.append(Spacer(1, 3 * mm))
        historia.append(_p(f"VENTA ANULADA — {v.get('motivo_anulacion') or ''}", "negrita"))
    historia.append(Spacer(1, 14 * mm))
    firma = Table([["", ""], [_p("Firma y aclaración de quien recibe", "chico"), _p("Vendedor: " + (v.get("vendedor") or ""), "chico")]],
                  colWidths=[90 * mm, 90 * mm])
    firma.setStyle(TableStyle([("LINEABOVE", (0, 1), (0, 1), 0.5, GRIS)]))
    historia.append(firma)
    return _construir(historia, titulo=f"Venta V-{v['id']:06d}")


def cuenta_pdf(cliente, r, desde=None, hasta=None):
    rango = ""
    if desde or hasta:
        rango = f"Período: {fecha(desde) or 'inicio'} a {fecha(hasta) or 'hoy'}"
    historia = _encabezado("RESUMEN DE CUENTA", None, ahora(), rango)
    historia += _caja_cliente(cliente)
    filas = []
    if desde:
        filas.append(["", "Saldo anterior", "", "", moneda(r["saldo_inicial"])])
    for m in r["movimientos"]:
        filas.append([fecha(m["fecha"]), m["concepto"], moneda(m["debe"]) if m["debe"] else "",
                      moneda(m["haber"]) if m["haber"] else "", moneda(m["saldo_resultante"])])
    pie = ["", "Totales del período", moneda(r.get("total_debe", 0)), moneda(r.get("total_haber", 0)),
           moneda(r.get("saldo_final", 0))]
    historia.append(_tabla(["Fecha", "Concepto", "Debe", "Haber", "Saldo"], filas,
                           [22 * mm, 76 * mm, 27 * mm, 27 * mm, 28 * mm], alinear_derecha=(2, 3, 4), pie=pie))
    historia.append(Spacer(1, 6 * mm))
    saldo = Decimal(r["cuenta"]["saldo"]) if r.get("cuenta") else Decimal(0)
    texto = "SALDO PENDIENTE" if saldo > 0 else ("SALDO A FAVOR DEL CLIENTE" if saldo < 0 else "CUENTA SALDADA")
    historia.append(_totales([(texto, moneda(abs(saldo)))]))
    return _construir(historia, titulo="Resumen de cuenta")


def tabla_pdf(titulo, subtitulo, cabecera, filas, alinear_derecha=(), resumen=None):
    apaisado = len(cabecera) > 6
    ancho_total = (297 if apaisado else 210) - 30
    anchos = [ancho_total / len(cabecera) * mm] * len(cabecera)
    historia = _encabezado(titulo.upper(), None, ahora(), subtitulo)
    if resumen:
        historia.append(_p(" · ".join(f"{k}: {v}" for k, v in resumen), "negrita"))
        historia.append(Spacer(1, 4 * mm))
    historia.append(_tabla(cabecera, filas, anchos, alinear_derecha=alinear_derecha))
    return _construir(historia, apaisado=apaisado, titulo=titulo)
