"""Decoradores de autorización."""
from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user


def _es_api():
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def permiso_requerido(*codigos, todos=False):
    """Exige que el usuario tenga alguno (o todos) de los permisos indicados.

    @permiso_requerido("ventas.crear")
    @permiso_requerido("stock.ver", "stock.gestionar")
    """

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                if _es_api():
                    return jsonify(error="Sesión expirada. Volvé a iniciar sesión."), 401
                from ..extensions import login_manager as lm

                return lm.unauthorized()
            chequeo = all if todos else any
            if not chequeo(current_user.puede(c) for c in codigos):
                if _es_api():
                    return jsonify(error="No tenés permiso para esta operación."), 403
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador


def rol_requerido(*roles):
    """Restricción por rol (usar sólo cuando la regla es realmente de rol, p. ej. 'duenio')."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not current_user.is_authenticated:
                from ..extensions import login_manager as lm

                return lm.unauthorized()
            if current_user.rol_codigo not in roles:
                abort(403)
            return vista(*args, **kwargs)

        return envoltura

    return decorador
