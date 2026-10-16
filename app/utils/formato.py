"""Filtros Jinja y formateo en estilo argentino."""
from datetime import date, datetime
from decimal import Decimal

from .numeros import D

ETIQUETAS = {
    "estado_pedido": {
        "pendiente": ("Pendiente", "gris"),
        "confirmado": ("Confirmado", "azul"),
        "preparando": ("Preparando", "ambar"),
        "listo": ("Listo para entregar", "violeta"),
        "en_camino": ("En camino", "celeste"),
        "entregado": ("Entregado", "verde"),
        "cancelado": ("Cancelado", "rojo"),
    },
    "estado_entrega": {
        "pendiente": ("Pendiente", "gris"),
        "asignada": ("Asignada", "azul"),
        "en_camino": ("En camino", "celeste"),
        "entregada": ("Entregada", "verde"),
        "no_entregada": ("No entregada", "ambar"),
        "cancelada": ("Cancelada", "rojo"),
    },
    "estado_presupuesto": {
        "pendiente": ("Pendiente", "gris"),
        "enviado": ("Enviado", "azul"),
        "aceptado": ("Aceptado", "verde"),
        "rechazado": ("Rechazado", "rojo"),
        "vencido": ("Vencido", "ambar"),
    },
    "estado_venta": {
        "confirmada": ("Confirmada", "verde"),
        "anulada": ("Anulada", "rojo"),
    },
    "estado_pago": {
        "pagada": ("Pagada", "verde"),
        "parcial": ("Pago parcial", "ambar"),
        "cuenta_corriente": ("Cuenta corriente", "azul"),
    },
    "estado_vehiculo": {
        "disponible": ("Disponible", "verde"),
        "en_uso": ("En uso", "celeste"),
        "mantenimiento": ("Mantenimiento", "ambar"),
        "inactivo": ("Inactivo", "gris"),
    },
    "estado_chofer": {
        "activo": ("Activo", "verde"),
        "inactivo": ("Inactivo", "gris"),
        "licencia": ("De licencia", "ambar"),
    },
    "tipo_cliente": {
        "particular": ("Particular", "gris"),
        "constructor": ("Constructor", "ambar"),
        "empresa": ("Empresa", "azul"),
        "corralon": ("Corralón", "violeta"),
        "otro": ("Otro", "gris"),
    },
    "tipo_mov_stock": {
        "entrada": ("Entrada", "verde"),
        "salida": ("Salida", "azul"),
        "ajuste": ("Ajuste", "ambar"),
        "anulacion": ("Anulación", "rojo"),
    },
    "tipo_entrega": {
        "retiro": ("Retiro en galpón", "gris"),
        "envio": ("Envío a domicilio", "celeste"),
    },
    "condicion_iva": {
        "consumidor_final": ("Consumidor final", "gris"),
        "responsable_inscripto": ("Responsable inscripto", "azul"),
        "monotributo": ("Monotributo", "violeta"),
        "exento": ("Exento", "gris"),
        "no_categorizado": ("No categorizado", "gris"),
    },
    "tipo_mov_caja": {
        "venta": ("Venta", "verde"),
        "pago_cliente": ("Pago de cliente", "verde"),
        "gasto": ("Gasto", "rojo"),
        "retiro": ("Retiro", "rojo"),
        "ingreso": ("Ingreso", "verde"),
        "ajuste": ("Ajuste", "ambar"),
        "pago_proveedor": ("Pago a proveedor", "rojo"),
        "anulacion": ("Anulación", "rojo"),
    },
}


def etiqueta(valor, grupo):
    """Texto legible de un código de estado."""
    return ETIQUETAS.get(grupo, {}).get(valor, (str(valor or "").replace("_", " ").capitalize(), "gris"))[0]


def color(valor, grupo):
    return ETIQUETAS.get(grupo, {}).get(valor, ("", "gris"))[1]


def opciones(grupo):
    return [(k, v[0]) for k, v in ETIQUETAS.get(grupo, {}).items()]


def _miles(entero: str) -> str:
    negativo = entero.startswith("-")
    entero = entero.lstrip("-")
    grupos = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    return ("-" if negativo else "") + ".".join(grupos)


def numero(valor, decimales=2, recortar=False):
    if valor is None or valor == "":
        return ""
    v = D(valor)
    texto = f"{v:.{decimales}f}"
    entero, _, dec = texto.partition(".")
    if recortar and dec:
        dec = dec.rstrip("0")
    return _miles(entero) + ("," + dec if dec else "")


def moneda(valor):
    if valor is None or valor == "":
        valor = Decimal("0")
    v = D(valor)
    signo = "-" if v < 0 else ""
    return f"{signo}$ {numero(abs(v), 2)}"


def cantidad(valor):
    return numero(valor, 3, recortar=True)


def fecha(valor):
    if not valor:
        return ""
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def fecha_hora(valor):
    if not valor:
        return ""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    return fecha(valor)


def hora(valor):
    return valor.strftime("%H:%M") if isinstance(valor, datetime) else ""


def nro(valor, prefijo):
    """Número de documento legible: V-000123."""
    return f"{prefijo}-{int(valor):06d}" if valor else ""


def fecha_iso(valor):
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%Y-%m-%d")
    return valor or ""


def registrar_filtros(app):
    app.jinja_env.filters.update(
        moneda=moneda,
        numero=numero,
        cantidad=cantidad,
        fecha=fecha,
        fecha_hora=fecha_hora,
        hora=hora,
        etiqueta=etiqueta,
        color=color,
        nro=nro,
        fecha_iso=fecha_iso,
    )
    app.jinja_env.globals.update(opciones=opciones)
