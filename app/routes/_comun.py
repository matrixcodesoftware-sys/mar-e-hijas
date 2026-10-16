"""Utilidades compartidas por los controladores."""
import csv
import io

from flask import Response, request

from ..utils.fechas import parse_fecha


def hay_busqueda():
    """Los listados sólo consultan cuando el usuario pidió resultados."""
    return any(request.args.get(k) for k in ("buscar", "rapido", "pagina"))


def arg_int(nombre):
    try:
        valor = request.args.get(nombre)
        return int(valor) if valor not in (None, "") else None
    except ValueError:
        return None


def arg_fecha(nombre):
    return parse_fecha(request.args.get(nombre))


def arg_txt(nombre, maximo=100):
    valor = (request.args.get(nombre) or "").strip()
    return valor[:maximo] or None


def respuesta_csv(nombre_archivo, cabecera, filas):
    """CSV con BOM y ';' para que Excel en español lo abra bien."""
    buffer = io.StringIO()
    buffer.write("﻿")
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    escritor.writerow(cabecera)
    for f in filas:
        escritor.writerow(["" if v is None else v for v in f])
    return Response(buffer.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}.csv"'})


def respuesta_pdf(nombre_archivo, contenido, descargar=False):
    disposicion = "attachment" if descargar else "inline"
    return Response(contenido, mimetype="application/pdf",
                    headers={"Content-Disposition": f'{disposicion}; filename="{nombre_archivo}.pdf"'})


def num_csv(valor, decimales=2):
    """Número con coma decimal para Excel en español."""
    if valor is None:
        return ""
    return f"{float(valor):.{decimales}f}".replace(".", ",")
