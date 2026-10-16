"""Registro y anulación de ventas.

registrar() ejecuta, en UNA transacción:
 1) validaciones y recálculo en servidor   2) venta + detalle
 3) salida de stock (con bloqueo)          4) pago + movimiento de caja
 5) saldo a cuenta corriente               6) entrega (si es envío)
 7) vínculo con presupuesto/pedido         8) historial
"""
from decimal import Decimal

from ..database import transaction
from ..models import catalogos
from ..models import cliente as cliente_model
from ..models import entrega as entrega_model
from ..models import pedido as pedido_model
from ..models import presupuesto as presupuesto_model
from ..models import venta as venta_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import moneda
from ..utils.numeros import dinero
from . import caja_service, cuenta_corriente_service, documento_service, historial_service, stock_service


def registrar(datos, items, usuario_id):
    """datos: cliente_id, tipo_entrega, zona_id, direccion_entrega, descuento_general, costo_envio,
    metodo_pago_id, monto_pagado, referencia_pago, observaciones, presupuesto_id, pedido_id,
    crear_entrega, fecha_entrega, horario_entrega."""
    with transaction():
        cliente = cliente_model.obtener(datos.get("cliente_id")) if datos.get("cliente_id") else None
        if not cliente or not cliente["activo"]:
            raise NegocioError("Seleccioná un cliente activo.")
        tipo_entrega = datos.get("tipo_entrega") or "retiro"
        if tipo_entrega not in ("retiro", "envio"):
            raise NegocioError("Tipo de entrega inválido.")
        envio = datos.get("costo_envio") if tipo_entrega == "envio" else 0
        calc = documento_service.calcular(items, datos.get("descuento_general"), envio)
        total = calc["total"]

        metodo = catalogos.metodo_pago(datos.get("metodo_pago_id")) if datos.get("metodo_pago_id") else None
        if not metodo or not metodo["activo"]:
            raise NegocioError("Seleccioná el método de pago.")
        if metodo["grupo"] == "cuenta_corriente":
            pagado = Decimal(0)
        else:
            pagado = dinero(datos["monto_pagado"]) if datos.get("monto_pagado") not in (None, "") else total
        if pagado < 0:
            raise NegocioError("El monto cobrado no puede ser negativo.")
        if pagado > total:
            raise NegocioError(f"El monto cobrado ({moneda(pagado)}) supera el total ({moneda(total)}). "
                               "Si el cliente paga de más, registrá el vuelto por fuera.")
        saldo_cc = dinero(total - pagado)
        estado_pago = "pagada" if saldo_cc == 0 else ("cuenta_corriente" if pagado == 0 else "parcial")
        if tipo_entrega == "envio" and not datos.get("direccion_entrega"):
            raise NegocioError("Indicá la dirección de entrega.")

        pedido = None
        if datos.get("pedido_id"):
            pedido = pedido_model.obtener(datos["pedido_id"], bloquear=True)
            if not pedido:
                raise NegocioError("El pedido no existe.")
            if pedido["venta_id"]:
                raise NegocioError(f"El pedido ya tiene la venta V-{pedido['venta_id']:06d}.")
            if pedido["estado"] == "cancelado":
                raise NegocioError("El pedido está cancelado.")
        presupuesto = None
        if datos.get("presupuesto_id"):
            presupuesto = presupuesto_model.obtener(datos["presupuesto_id"], bloquear=True)
            if not presupuesto:
                raise NegocioError("El presupuesto no existe.")
            if presupuesto["venta_id"]:
                raise NegocioError(f"El presupuesto ya se convirtió en la venta V-{presupuesto['venta_id']:06d}.")

        fecha = ahora()
        venta_id = venta_model.insertar({
            "fecha": fecha, "cliente_id": cliente["id"], "usuario_id": usuario_id,
            "presupuesto_id": presupuesto["id"] if presupuesto else None,
            "pedido_id": pedido["id"] if pedido else None, "tipo_entrega": tipo_entrega,
            "zona_id": datos.get("zona_id") if tipo_entrega == "envio" else None,
            "direccion_entrega": datos.get("direccion_entrega") if tipo_entrega == "envio" else None,
            "subtotal": calc["subtotal"], "descuento_general": calc["descuento_general"],
            "costo_envio": calc["costo_envio"], "total": total, "costo_mercaderia": calc["costo_mercaderia"],
            "monto_pagado": pagado, "saldo_cta_cte": saldo_cc, "estado_pago": estado_pago,
            "observaciones": datos.get("observaciones"),
        })

        for ln in calc["lineas"]:
            venta_model.insertar_detalle(venta_id, ln)
            stock_service.salida_por_venta(ln, venta_id, cliente["id"], usuario_id, fecha)

        if pagado > 0:
            caja = caja_service.requerir_caja_abierta()
            pago_id = cuenta_corriente_service.insertar_pago(
                cliente["id"], venta_id, metodo["id"], pagado, caja["id"], datos.get("referencia_pago"), usuario_id,
                fecha)
            caja_service.registrar_movimiento(
                "venta", "ingreso", metodo["id"], pagado, f"Venta V-{venta_id:06d} · {cliente['razon_social']}",
                usuario_id, venta_id=venta_id, pago_id=pago_id, fecha=fecha)

        if saldo_cc > 0:
            cuenta_corriente_service.cargar_venta(cliente["id"], venta_id, saldo_cc, usuario_id, fecha)

        if pedido:
            pedido_model.set_venta(pedido["id"], venta_id)
            entrega_model.vincular_pedido_a_venta(pedido["id"], venta_id)
            if pedido["estado"] == "pendiente":
                pedido_model.set_estado(pedido["id"], "confirmado")
        if presupuesto:
            presupuesto_model.marcar_convertido(presupuesto["id"], venta_id=venta_id)

        if tipo_entrega == "envio" and not pedido and datos.get("crear_entrega"):
            entrega_id = entrega_model.insertar({
                "venta_id": venta_id, "cliente_id": cliente["id"], "direccion": datos.get("direccion_entrega"),
                "localidad": cliente.get("localidad"), "referencia": cliente.get("referencia_ubicacion"),
                "telefono_contacto": cliente.get("whatsapp") or cliente.get("telefono"),
                "fecha": datos.get("fecha_entrega") or fecha.date(), "horario": datos.get("horario_entrega"),
                "estado": "pendiente", "observaciones": datos.get("observaciones"), "usuario_id": usuario_id,
            })
            for ln in calc["lineas"]:
                entrega_model.insertar_detalle(entrega_id, ln["material_id"], ln["unidad_id"], ln["cantidad"])

        historial_service.registrar(
            "crear", "ventas", f"creó la venta V-{venta_id:06d} a {cliente['razon_social']} por {moneda(total)}"
            + (f" ({moneda(saldo_cc)} a cuenta corriente)" if saldo_cc else ""), venta_id)
        return venta_id


def anular(venta_id, motivo, usuario_id):
    if not motivo or len(motivo.strip()) < 4:
        raise NegocioError("Indicá el motivo de la anulación.")
    with transaction():
        venta = venta_model.obtener(venta_id, bloquear=True)
        if not venta:
            raise NegocioError("La venta no existe.")
        if venta["estado"] == "anulada":
            raise NegocioError("La venta ya está anulada.")
        if entrega_model.entregadas_de_venta(venta_id, venta["pedido_id"]):
            raise NegocioError("La venta tiene entregas realizadas o en camino. Registrá un ajuste de stock o una nota de crédito.")
        from ..database import query_one

        comp = query_one("SELECT id FROM comprobantes WHERE venta_id = %s AND estado = 'autorizado'", (venta_id,))
        if comp:
            raise NegocioError("La venta tiene un comprobante autorizado por ARCA. Emití una nota de crédito.")

        for ln in venta_model.detalle(venta_id):
            stock_service.reingreso_por_anulacion(ln, venta_id, venta["cliente_id"], usuario_id)

        for p in venta_model.pagos(venta_id):
            if p["estado"] == "registrado":
                caja_service.registrar_movimiento(
                    "anulacion", "egreso", p["metodo_pago_id"], p["monto"],
                    f"Devolución por anulación V-{venta_id:06d}", usuario_id, venta_id=venta_id, pago_id=p["id"])
        venta_model.anular_pagos(venta_id)

        if Decimal(venta["saldo_cta_cte"]) > 0:
            cuenta_corriente_service.revertir_venta(venta["cliente_id"], venta_id, venta["saldo_cta_cte"], usuario_id)

        if venta["pedido_id"]:
            # Los viajes del pedido siguen siendo del pedido: sólo se desvinculan de la venta anulada.
            pedido_model.set_venta(venta["pedido_id"], None)
            entrega_model.vincular_pedido_a_venta(venta["pedido_id"], None)
        else:
            entrega_model.cancelar_pendientes_de_venta(venta_id)
        if venta["presupuesto_id"]:
            presupuesto_model.desvincular_venta(venta["presupuesto_id"])

        venta_model.marcar_anulada(venta_id, usuario_id, ahora(), motivo.strip()[:255])
        historial_service.registrar("anular", "ventas", f"anuló la venta V-{venta_id:06d} ({moneda(venta['total'])}). "
                                    f"Motivo: {motivo.strip()}", venta_id)
