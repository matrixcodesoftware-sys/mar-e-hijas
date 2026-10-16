"""Fechas en la zona horaria del negocio (no la del servidor MySQL)."""
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import current_app


def _tz():
    return ZoneInfo(current_app.config.get("APP_TIMEZONE", "America/Argentina/Buenos_Aires"))


_AHORA_FIJO = ContextVar("ahora_fijo", default=None)


def fijar_ahora(momento):
    """Fija la hora 'actual' (sólo lo usa manage.py para generar historial de prueba)."""
    _AHORA_FIJO.set(momento)


def ahora() -> datetime:
    """datetime 'naive' en hora local del negocio, listo para guardar en DATETIME."""
    fijo = _AHORA_FIJO.get()
    if fijo is not None:
        return fijo
    return datetime.now(_tz()).replace(tzinfo=None, microsecond=0)


def hoy() -> date:
    return ahora().date()


def parse_fecha(texto):
    if not texto:
        return None
    if isinstance(texto, date):
        return texto
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(texto).strip(), fmt).date()
        except ValueError:
            continue
    return None


def inicio_dia(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def fin_dia_exclusivo(d: date) -> datetime:
    return inicio_dia(d) + timedelta(days=1)


def rango_periodo(periodo: str, desde=None, hasta=None):
    """Devuelve (desde_date, hasta_date) inclusivos para 'hoy', 'semana', 'mes', 'anio' o 'rango'."""
    h = hoy()
    if periodo == "hoy":
        return h, h
    if periodo == "ayer":
        a = h - timedelta(days=1)
        return a, a
    if periodo == "semana":
        return h - timedelta(days=h.weekday()), h
    if periodo == "mes":
        return h.replace(day=1), h
    if periodo == "mes_anterior":
        fin = h.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin
    if periodo == "anio":
        return h.replace(month=1, day=1), h
    d = parse_fecha(desde) or h.replace(day=1)
    hs = parse_fecha(hasta) or h
    if d > hs:
        d, hs = hs, d
    return d, hs
