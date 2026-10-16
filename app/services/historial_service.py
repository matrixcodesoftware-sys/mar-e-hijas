"""Registro de auditoría: quién hizo qué, cuándo y sobre qué registro."""
from flask import has_request_context, request
from flask_login import current_user

from ..models import historial as historial_model
from ..utils.fechas import ahora


def registrar(accion, modulo, descripcion, registro_id=None, usuario_id=None):
    """Ej.: registrar('crear', 'ventas', 'creó la venta V-000123', 123).

    La descripción se guarda precedida por el nombre del usuario:
    "Juan Pérez creó la venta V-000123".
    """
    nombre = ""
    if usuario_id is None and has_request_context() and current_user.is_authenticated:
        usuario_id = current_user.id
        nombre = current_user.nombre_completo
    ip = None
    if has_request_context():
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()[:45]
    texto = f"{nombre} {descripcion}".strip() if nombre else descripcion
    historial_model.insertar(
        ahora(), usuario_id, accion, modulo, str(registro_id) if registro_id is not None else None, texto, ip
    )
