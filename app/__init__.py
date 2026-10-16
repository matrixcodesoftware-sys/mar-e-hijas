"""MAR E HIJAS — Sistema de Gestión de Áridos. Fábrica de la aplicación Flask."""
import logging

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from . import database
from .config import obtener_config
from .extensions import csrf, login_manager
from .utils.errores import NegocioError
from .utils.formato import registrar_filtros

# Menú lateral: (endpoint, etiqueta, icono, permisos requeridos (alguno))
MENU = [
    ("dashboard.index", "Dashboard", "grid", ("dashboard.ver",)),
    ("entregas.mis_entregas", "Mis entregas", "truck", ("entregas.propias",)),
    None,
    ("ventas.index", "Ventas", "cart", ("ventas.ver",)),
    ("pedidos.index", "Pedidos", "clipboard", ("pedidos.ver",)),
    ("presupuestos.index", "Presupuestos", "file", ("presupuestos.ver",)),
    ("entregas.index", "Entregas", "route", ("entregas.ver",)),
    None,
    ("materiales.index", "Materiales", "layers", ("materiales.ver",)),
    ("stock.index", "Stock", "box", ("stock.ver",)),
    ("clientes.index", "Clientes", "users", ("clientes.ver",)),
    ("proveedores.index", "Proveedores", "factory", ("proveedores.ver",)),
    None,
    ("vehiculos.index", "Camiones", "truck", ("vehiculos.ver",)),
    ("choferes.index", "Choferes", "id", ("choferes.ver",)),
    None,
    ("caja.index", "Caja", "cash", ("caja.ver", "caja.operar")),
    ("gastos.index", "Gastos", "receipt", ("gastos.ver",)),
    ("reportes.index", "Reportes", "chart", ("reportes.ver",)),
    None,
    ("usuarios.index", "Usuarios", "shield", ("usuarios.gestionar",)),
    ("configuracion.index", "Configuración", "settings",
     ("parametros.gestionar", "configuracion.gestionar", "facturacion.gestionar")),
    ("historial.index", "Historial", "history", ("historial.ver",)),
]


def create_app(config_obj=None):
    app = Flask(__name__)
    app.config.from_object(config_obj or obtener_config())

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta SECRET_KEY en el archivo .env (ver .env.example).")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    registrar_filtros(app)

    @login_manager.user_loader
    def cargar_usuario(user_id):
        from .models import usuario as usuario_model

        try:
            return usuario_model.cargar(int(user_id))
        except (TypeError, ValueError):
            return None

    @login_manager.unauthorized_handler
    def no_autorizado():
        if request.path.startswith("/api/"):
            return jsonify(error="Sesión expirada. Volvé a iniciar sesión."), 401
        flash("Iniciá sesión para continuar.", "warning")
        return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))

    _registrar_blueprints(app)
    _registrar_errores(app)
    _registrar_contexto(app)
    _registrar_seguridad(app)
    return app


def _registrar_blueprints(app):
    from .routes import (api, auth, caja, choferes, clientes, configuracion, dashboard, entregas, gastos,
                         historial, materiales, pedidos, presupuestos, proveedores, reportes, stock,
                         usuarios, vehiculos, ventas)

    for modulo in (auth, dashboard, ventas, pedidos, presupuestos, entregas, materiales, stock, clientes,
                   proveedores, vehiculos, choferes, caja, gastos, reportes, usuarios, configuracion,
                   historial, api):
        app.register_blueprint(modulo.bp)


def _registrar_contexto(app):
    @app.context_processor
    def contexto_global():
        menu = []
        if current_user.is_authenticated:
            separador_pendiente = False
            for item in MENU:
                if item is None:
                    separador_pendiente = bool(menu)
                    continue
                endpoint, etiqueta, icono, permisos = item
                if endpoint == "entregas.mis_entregas" and current_user.puede("entregas.ver") \
                        and not current_user.chofer_id:
                    continue
                if any(current_user.puede(p) for p in permisos):
                    if separador_pendiente:
                        menu.append(None)
                        separador_pendiente = False
                    menu.append({"endpoint": endpoint, "etiqueta": etiqueta, "icono": icono,
                                 "activo": request.blueprint == endpoint.split(".")[0]
                                 and not (endpoint == "entregas.mis_entregas" and request.endpoint != endpoint)
                                 and not (endpoint == "entregas.index" and request.endpoint == "entregas.mis_entregas")})
        from .utils.fechas import hoy

        return {
            "hoy_fecha": hoy(),
            "APP_NOMBRE": app.config["APP_NOMBRE"],
            "APP_SUBTITULO": app.config["APP_SUBTITULO"],
            "menu_lateral": menu,
        }


def _registrar_errores(app):
    def _responder(codigo, titulo, mensaje):
        if request.path.startswith("/api/"):
            return jsonify(error=mensaje), codigo
        return render_template("errors/error.html", codigo=codigo, titulo=titulo, mensaje=mensaje), codigo

    @app.errorhandler(400)
    def e400(e):
        return _responder(400, "Solicitud inválida", getattr(e, "description", "La solicitud no es válida."))

    @app.errorhandler(CSRFError)
    def e_csrf(_e):
        return _responder(400, "Formulario vencido",
                          "El formulario expiró o no es válido. Recargá la página e intentá de nuevo.")

    @app.errorhandler(403)
    def e403(_e):
        return _responder(403, "Acceso denegado", "Tu usuario no tiene permiso para acceder a esta sección.")

    @app.errorhandler(404)
    def e404(_e):
        return _responder(404, "No encontrado", "La página o el registro que buscás no existe.")

    @app.errorhandler(405)
    def e405(_e):
        return _responder(405, "Método no permitido", "La operación no está permitida.")

    @app.errorhandler(NegocioError)
    def e_negocio(e):
        # Red de seguridad: normalmente las vistas capturan NegocioError y re-muestran el formulario.
        if request.path.startswith("/api/"):
            return jsonify(error=e.mensaje), 422
        flash(e.mensaje, "danger")
        return redirect(request.referrer or url_for("dashboard.index"))

    @app.errorhandler(500)
    def e500(e):
        app.logger.exception("Error interno: %s", e)
        return _responder(500, "Error interno", "Ocurrió un error inesperado. El problema quedó registrado.")

    @app.errorhandler(Exception)
    def e_generico(e):
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e
        app.logger.exception("Excepción no controlada")
        return _responder(500, "Error interno", "Ocurrió un error inesperado. El problema quedó registrado.")


def _registrar_seguridad(app):
    @app.after_request
    def cabeceras(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; form-action 'self'",
        )
        if request.path.startswith("/api/") or (current_user.is_authenticated and resp.mimetype == "text/html"):
            resp.headers["Cache-Control"] = "no-store"
        return resp
