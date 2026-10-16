"""Parámetros generales clave/valor (datos de la empresa, fiscales, reglas)."""
from flask import g

from ..database import execute, query

# Claves conocidas con su valor por defecto y descripción.
DEFINICIONES = {
    "empresa_nombre": ("MAR E HIJAS", "Nombre comercial"),
    "empresa_razon_social": ("", "Razón social"),
    "empresa_cuit": ("", "CUIT de la empresa"),
    "empresa_condicion_iva": ("responsable_inscripto", "Condición frente al IVA"),
    "empresa_direccion": ("", "Dirección del galpón"),
    "empresa_localidad": ("", "Localidad"),
    "empresa_telefono": ("", "Teléfono"),
    "empresa_whatsapp": ("", "WhatsApp"),
    "empresa_email": ("", "Email"),
    "empresa_inicio_actividades": ("", "Inicio de actividades"),
    "presupuesto_validez_dias": ("7", "Días de validez de un presupuesto"),
    "presupuesto_leyenda": ("Precios sujetos a modificación sin previo aviso. Flete según zona.",
                            "Leyenda al pie del presupuesto"),
    "permitir_stock_negativo": ("0", "Permitir vender sin stock suficiente"),
    "alerta_licencia_dias": ("30", "Avisar vencimiento de licencias con X días de anticipación"),
}


def todas():
    if "config_cache" not in g:
        valores = {k: v[0] for k, v in DEFINICIONES.items()}
        for fila in query("SELECT clave, valor FROM configuracion"):
            valores[fila["clave"]] = fila["valor"] if fila["valor"] is not None else ""
        g.config_cache = valores
    return g.config_cache


def get(clave, defecto=None):
    valor = todas().get(clave)
    return defecto if valor in (None, "") and defecto is not None else valor


def get_bool(clave):
    return str(get(clave, "0")) in ("1", "true", "si")


def get_int(clave, defecto=0):
    try:
        return int(get(clave, defecto))
    except (TypeError, ValueError):
        return defecto


def guardar(valores: dict):
    for clave, valor in valores.items():
        if clave not in DEFINICIONES:
            continue
        execute(
            """INSERT INTO configuracion (clave, valor, descripcion) VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE valor = VALUES(valor)""",
            (clave, valor, DEFINICIONES[clave][1]),
        )
    g.pop("config_cache", None)
