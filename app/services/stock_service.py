"""Stock de áridos a granel.

Toda variación de stock pasa por _mover(), que:
  1. bloquea la fila del material (SELECT … FOR UPDATE),
  2. valida que el stock no quede negativo (salvo configuración),
  3. inserta el movimiento con stock anterior/resultante,
  4. actualiza materiales.stock_actual.
Debe llamarse dentro de una transacción (lo garantiza el propio servicio).
"""
from decimal import Decimal

from ..database import transaction
from ..models import configuracion
from ..models import material as material_model
from ..models import proveedor as proveedor_model
from ..models import stock as stock_model
from ..utils.errores import NegocioError
from ..utils.fechas import ahora
from ..utils.formato import cantidad as fmt_cant
from ..utils.numeros import cantidad as q3
from ..utils.numeros import dinero
from . import conversion_service, historial_service


def _mover(material_id, tipo, cantidad_stock, unidad_id, cantidad_unidad, factor, usuario_id, fecha=None,
           permitir_negativo=None, **extra):
    material = material_model.obtener(material_id, bloquear=True)
    if not material:
        raise NegocioError("El material no existe.")
    anterior = Decimal(material["stock_actual"])
    resultante = q3(anterior + cantidad_stock)
    if permitir_negativo is None:
        permitir_negativo = configuracion.get_bool("permitir_stock_negativo")
    if resultante < 0 and not permitir_negativo:
        raise NegocioError(
            f"Stock insuficiente de {material['nombre']}: hay {fmt_cant(anterior)} y se necesitan "
            f"{fmt_cant(abs(cantidad_stock))} (en su unidad de stock)."
        )
    mov_id = stock_model.insertar({
        "fecha": fecha or ahora(),
        "material_id": material_id,
        "tipo": tipo,
        "cantidad": q3(cantidad_stock),
        "unidad_id": unidad_id,
        "cantidad_unidad": q3(abs(cantidad_unidad)),
        "factor_conversion": factor,
        "stock_anterior": anterior,
        "stock_resultante": resultante,
        "usuario_id": usuario_id,
        **extra,
    })
    material_model.set_stock(material_id, resultante)
    return mov_id, material, resultante


def registrar_entrada(datos, usuario_id):
    """Entrada de material al galpón (compra a proveedor).

    datos: material_id, cantidad, unidad_id, proveedor_id, fecha, vehiculo_id | vehiculo_descripcion,
           remito_numero, costo_total, observaciones, condicion ('contado' | 'cuenta'),
           metodo_pago_id (si contado), actualizar_precio (bool)
    """
    from . import caja_service  # import diferido para evitar ciclos

    with transaction():
        material = material_model.obtener(datos["material_id"])
        if not material or not material["activo"]:
            raise NegocioError("El material no existe o está inactivo.")
        factor = conversion_service.factor_obligatorio(material, datos["unidad_id"])
        cantidad_stock = q3(Decimal(datos["cantidad"]) * factor)
        if cantidad_stock <= 0:
            raise NegocioError("La cantidad debe ser mayor a cero.")
        costo_total = dinero(datos.get("costo_total") or 0)
        costo_unitario = dinero(costo_total / cantidad_stock) if costo_total else None
        fecha = datos.get("fecha") or ahora()

        mov_id, material, resultante = _mover(
            material["id"], "entrada", cantidad_stock, datos["unidad_id"], datos["cantidad"], factor, usuario_id,
            fecha=fecha, permitir_negativo=True,
            proveedor_id=datos.get("proveedor_id"), vehiculo_id=datos.get("vehiculo_id"),
            vehiculo_descripcion=datos.get("vehiculo_descripcion"), remito_numero=datos.get("remito_numero"),
            costo_unitario=costo_unitario, costo_total=costo_total or None, observaciones=datos.get("observaciones"),
        )

        if costo_unitario and datos.get("actualizar_precio"):
            material_model.set_precio_compra(material["id"], costo_unitario)

        # Impacto económico con el proveedor
        if costo_total and datos.get("proveedor_id"):
            proveedor = proveedor_model.obtener(datos["proveedor_id"], bloquear=True)
            if not proveedor:
                raise NegocioError("Proveedor inexistente.")
            concepto = f"Entrada {fmt_cant(datos['cantidad'])} de {material['nombre']}"
            if datos.get("remito_numero"):
                concepto += f" · remito {datos['remito_numero']}"
            saldo = dinero(Decimal(proveedor["saldo_cuenta"]) + costo_total)
            proveedor_model.insertar_movimiento({
                "proveedor_id": proveedor["id"], "fecha": fecha, "tipo": "compra", "concepto": concepto,
                "cargo": costo_total, "saldo_resultante": saldo, "movimiento_stock_id": mov_id,
                "usuario_id": usuario_id,
            })
            proveedor_model.set_saldo(proveedor["id"], saldo)
            if datos.get("condicion") == "contado":
                from . import proveedor_service

                proveedor_service.registrar_pago({
                    "proveedor_id": proveedor["id"], "monto": costo_total,
                    "metodo_pago_id": datos["metodo_pago_id"], "referencia": datos.get("remito_numero"),
                    "observaciones": "Pago contado de entrada de material",
                }, usuario_id)
        elif costo_total and datos.get("condicion") == "contado":
            caja_service.registrar_movimiento(
                "gasto", "egreso", datos["metodo_pago_id"], costo_total,
                f"Compra de {material['nombre']} (sin proveedor)", usuario_id)

        historial_service.registrar(
            "crear", "stock",
            f"registró entrada de {fmt_cant(datos['cantidad'])} de {material['nombre']}"
            + (f" (remito {datos['remito_numero']})" if datos.get("remito_numero") else ""),
            mov_id)
        return mov_id


def registrar_ajuste(material_id, modo, valor, unidad_id, motivo, usuario_id):
    """Ajuste por conteo físico o corrección.

    modo = 'conteo'  → valor es el stock real medido (en unidad_id)
    modo = 'sumar' / 'restar' → valor es la diferencia
    """
    if not motivo:
        raise NegocioError("El motivo del ajuste es obligatorio.")
    with transaction():
        material = material_model.obtener(material_id)
        if not material:
            raise NegocioError("El material no existe.")
        factor = conversion_service.factor_obligatorio(material, unidad_id)
        valor_stock = q3(Decimal(valor) * factor)
        bloqueado = material_model.obtener(material_id, bloquear=True)
        actual = Decimal(bloqueado["stock_actual"])
        if modo == "conteo":
            diferencia = valor_stock - actual
        elif modo == "sumar":
            diferencia = valor_stock
        elif modo == "restar":
            diferencia = -valor_stock
        else:
            raise NegocioError("Tipo de ajuste inválido.")
        if diferencia == 0:
            raise NegocioError("El ajuste no modifica el stock.")
        mov_id, _, resultante = _mover(material_id, "ajuste", diferencia, unidad_id, valor, factor, usuario_id,
                                       permitir_negativo=False, observaciones=motivo[:255])
        historial_service.registrar(
            "ajustar", "stock",
            f"ajustó el stock de {material['nombre']} ({'+' if diferencia > 0 else ''}{fmt_cant(diferencia)} "
            f"{material['unidad_abrev']}, queda {fmt_cant(resultante)}). Motivo: {motivo}", mov_id)
        return mov_id


def salida_por_venta(linea, venta_id, cliente_id, usuario_id, fecha):
    """linea: dict con material_id, unidad_id, cantidad, factor_conversion, cantidad_stock."""
    mov_id, material, _ = _mover(
        linea["material_id"], "salida", -Decimal(linea["cantidad_stock"]), linea["unidad_id"], linea["cantidad"],
        linea["factor_conversion"], usuario_id, fecha=fecha, venta_id=venta_id, cliente_id=cliente_id,
        observaciones=f"Venta V-{venta_id:06d}")
    return mov_id


def reingreso_por_anulacion(linea, venta_id, cliente_id, usuario_id):
    _mover(linea["material_id"], "anulacion", Decimal(linea["cantidad_stock"]), linea["unidad_id"], linea["cantidad"],
           linea["factor_conversion"], usuario_id, permitir_negativo=True, venta_id=venta_id, cliente_id=cliente_id,
           observaciones=f"Anulación de venta V-{venta_id:06d}")
