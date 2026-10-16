"""Servicio de facturación: arma comprobantes desde ventas y delega en el proveedor configurado."""
import re
from decimal import ROUND_HALF_UP, Decimal

from ...database import execute, query, query_one, transaction
from ...models import configuracion
from ...utils.errores import NegocioError
from ...utils.fechas import hoy
from .. import historial_service
from .base import (CONDICION_IVA_RECEPTOR, DOC_CONSUMIDOR_FINAL, DOC_CUIT, DOC_DNI, DatosComprobante,
                   FacturacionNoDisponible, ItemComprobante)
from .proveedores import obtener_proveedor

IVA_GENERAL = Decimal("21")
CENT = Decimal("0.01")


def letra_comprobante(condicion_emisor, condicion_receptor):
    """Determina la letra según las condiciones frente al IVA."""
    if condicion_emisor in ("monotributo", "exento"):
        return "C"
    if condicion_emisor == "responsable_inscripto":
        return "A" if condicion_receptor in ("responsable_inscripto", "monotributo") else "B"
    raise NegocioError("Configurá la condición frente al IVA de la empresa.")


def tipo_factura(letra):
    return {"A": 1, "B": 6, "C": 11}[letra]


def puntos_venta():
    return query("SELECT * FROM puntos_venta ORDER BY numero")


def tipos_comprobante():
    return query("SELECT * FROM tipos_comprobante WHERE activo = 1 ORDER BY codigo")


def comprobantes_de_venta(venta_id):
    return query(
        """SELECT c.*, t.descripcion AS tipo_desc, t.letra, pv.numero AS pv_numero FROM comprobantes c
           JOIN tipos_comprobante t ON t.codigo = c.tipo_comprobante JOIN puntos_venta pv ON pv.id = c.punto_venta_id
           WHERE c.venta_id = %s ORDER BY c.id""", (venta_id,))


def preparar_desde_venta(venta, cliente, detalle, punto_venta_id):
    cfg = configuracion.todas()
    cuit_emisor = re.sub(r"\D", "", cfg.get("empresa_cuit") or "")
    if len(cuit_emisor) != 11:
        raise NegocioError("Cargá el CUIT de la empresa en Configuración → Empresa antes de facturar.")
    pv = query_one("SELECT * FROM puntos_venta WHERE id = %s AND activo = 1", (punto_venta_id,))
    if not pv:
        raise NegocioError("Seleccioná un punto de venta activo.")
    letra = letra_comprobante(cfg.get("empresa_condicion_iva"), cliente["condicion_iva"])
    total = Decimal(venta["total"])
    if letra == "C":
        neto, iva = total, Decimal(0)
    else:
        neto = (total / (1 + IVA_GENERAL / 100)).quantize(CENT, ROUND_HALF_UP)
        iva = total - neto
    doc = re.sub(r"\D", "", cliente.get("documento") or "")
    if cliente["documento_tipo"] in ("CUIT", "CUIL") and len(doc) == 11:
        doc_tipo = DOC_CUIT
    elif cliente["documento_tipo"] == "DNI" and doc:
        doc_tipo = DOC_DNI
    else:
        doc_tipo, doc = DOC_CONSUMIDOR_FINAL, "0"
    if letra == "A" and doc_tipo != DOC_CUIT:
        raise NegocioError("Para Factura A el cliente debe tener CUIT válido.")
    items = [ItemComprobante(d["material"], Decimal(d["cantidad"]), d["unidad"], Decimal(d["precio_unitario"]),
                             Decimal(d["subtotal"])) for d in detalle]
    return DatosComprobante(
        tipo_comprobante=tipo_factura(letra), punto_venta=pv["numero"], fecha_emision=hoy(), cuit_emisor=cuit_emisor,
        receptor_doc_tipo=doc_tipo, receptor_doc_nro=doc, receptor_condicion_iva=cliente["condicion_iva"],
        importe_neto=neto, importe_iva=iva, importe_total=total, items=items), pv


def emitir(venta, cliente, detalle, punto_venta_id):
    """Guarda el comprobante (borrador) y solicita autorización al proveedor. Devuelve (id, mensaje)."""
    if venta["estado"] != "confirmada":
        raise NegocioError("Sólo se pueden facturar ventas confirmadas.")
    existente = query_one("SELECT id FROM comprobantes WHERE venta_id = %s AND estado IN ('autorizado','pendiente')",
                          (venta["id"],))
    if existente:
        raise NegocioError("La venta ya tiene un comprobante autorizado o pendiente.")
    datos, pv = preparar_desde_venta(venta, cliente, detalle, punto_venta_id)
    with transaction():
        comp_id = execute(
            """INSERT INTO comprobantes (venta_id, tipo_comprobante, punto_venta_id, fecha_emision, cuit_emisor,
               receptor_doc_tipo, receptor_doc_nro, receptor_condicion_iva, importe_neto, importe_iva, importe_total,
               estado) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'borrador')""",
            (venta["id"], datos.tipo_comprobante, pv["id"], datos.fecha_emision, datos.cuit_emisor,
             datos.receptor_doc_tipo, datos.receptor_doc_nro, datos.receptor_condicion_iva, datos.importe_neto,
             datos.importe_iva, datos.importe_total))
        historial_service.registrar("crear", "facturacion", f"preparó el comprobante #{comp_id} de la venta "
                                    f"V-{venta['id']:06d}", comp_id)
    proveedor = obtener_proveedor()
    try:
        resultado = proveedor.autorizar(datos)
    except FacturacionNoDisponible as e:
        return comp_id, str(e)
    estado = "autorizado" if resultado.aprobado else "rechazado"
    execute("""UPDATE comprobantes SET numero=%s, cae=%s, cae_vencimiento=%s, estado=%s, observaciones_arca=%s
               WHERE id=%s""", (resultado.numero, resultado.cae, resultado.cae_vencimiento, estado,
                                resultado.observaciones, comp_id))
    return comp_id, ("Comprobante autorizado. CAE " + resultado.cae) if resultado.aprobado else resultado.observaciones


def estado_integracion():
    p = obtener_proveedor()
    return {"proveedor": p.nombre, "disponible": p.disponible()}
