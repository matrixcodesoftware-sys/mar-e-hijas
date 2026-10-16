"""Autenticación, perfil y cierre de sesión."""
import time
from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..models import usuario as usuario_model
from ..services import historial_service
from ..utils.errores import ValidacionError
from ..utils.fechas import ahora
from ..utils.validadores import Validador

bp = Blueprint("auth", __name__)

# Bloqueo simple por intentos fallidos (por proceso). En despliegues con varios
# procesos conviene moverlo a Redis; para un galpón con un servidor alcanza.
_INTENTOS = {}
MAX_INTENTOS = 5
BLOQUEO_SEG = 300


def _clave_intento(username):
    return f"{request.remote_addr}|{(username or '').lower()}"


def _bloqueado(clave):
    intentos, desde = _INTENTOS.get(clave, (0, 0))
    if intentos >= MAX_INTENTOS and time.time() - desde < BLOQUEO_SEG:
        return True
    if time.time() - desde >= BLOQUEO_SEG:
        _INTENTOS.pop(clave, None)
    return False


def _destino_seguro(destino):
    if not destino:
        return None
    partes = urlparse(destino)
    if partes.netloc or partes.scheme or not destino.startswith("/"):
        return None
    return destino


def pagina_inicio():
    if current_user.puede("dashboard.ver"):
        return url_for("dashboard.index")
    if current_user.puede("entregas.propias"):
        return url_for("entregas.mis_entregas")
    return url_for("auth.perfil")


@bp.route("/")
def raiz():
    if current_user.is_authenticated:
        return redirect(pagina_inicio())
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(pagina_inicio())
    if request.method == "POST":
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        clave = _clave_intento(username)
        if _bloqueado(clave):
            flash("Demasiados intentos fallidos. Esperá 5 minutos e intentá de nuevo.", "danger")
            return render_template("auth/login.html", username=username), 429
        fila = usuario_model.por_username(username)
        if not fila or not usuario_model.verificar_password(fila, password):
            intentos, desde = _INTENTOS.get(clave, (0, time.time()))
            _INTENTOS[clave] = (intentos + 1, desde if intentos else time.time())
            flash("Usuario o contraseña incorrectos.", "danger")
            return render_template("auth/login.html", username=username), 401
        if not fila["activo"]:
            flash("Tu usuario está desactivado. Consultá con el administrador.", "danger")
            return render_template("auth/login.html", username=username), 403
        _INTENTOS.pop(clave, None)
        session.clear()
        usuario = usuario_model.cargar(fila["id"])
        login_user(usuario, remember=bool(request.form.get("recordar")))
        session.permanent = True
        usuario_model.registrar_acceso(usuario.id, ahora())
        historial_service.registrar("login", "auth", "inició sesión", usuario.id)
        destino = _destino_seguro(request.args.get("next"))
        return redirect(destino or pagina_inicio())
    return render_template("auth/login.html", username="")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    historial_service.registrar("logout", "auth", "cerró sesión", current_user.id)
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    fila = usuario_model.obtener(current_user.id)
    errores = {}
    if request.method == "POST":
        accion = request.form.get("accion")
        v = Validador(request.form)
        try:
            if accion == "datos":
                datos = {
                    "nombre": v.texto("nombre", True, 80),
                    "apellido": v.texto("apellido", True, 80),
                    "email": v.email("email"),
                    "telefono": v.texto("telefono", maximo=40),
                }
                if datos["email"] and usuario_model.existe_email(datos["email"], current_user.id):
                    v.error("email", "Ese email ya está en uso.")
                v.verificar()
                usuario_model.actualizar_perfil(current_user.id, datos)
                historial_service.registrar("modificar", "usuarios", "actualizó su perfil", current_user.id)
                flash("Datos actualizados.", "success")
            elif accion == "password":
                actual = request.form.get("password_actual") or ""
                nueva = request.form.get("password_nueva") or ""
                repetir = request.form.get("password_repetir") or ""
                if not usuario_model.verificar_password(fila, actual):
                    v.error("password_actual", "La contraseña actual no es correcta.")
                if len(nueva) < 8:
                    v.error("password_nueva", "La nueva contraseña debe tener al menos 8 caracteres.")
                if nueva != repetir:
                    v.error("password_repetir", "Las contraseñas no coinciden.")
                v.verificar()
                usuario_model.cambiar_password(current_user.id, nueva)
                historial_service.registrar("modificar", "usuarios", "cambió su contraseña", current_user.id)
                flash("Contraseña actualizada.", "success")
            return redirect(url_for("auth.perfil"))
        except ValidacionError as e:
            errores = e.errores
            flash(e.mensaje, "danger")
            if accion == "datos":
                fila = {**fila, **{k: request.form.get(k) for k in ("nombre", "apellido", "email", "telefono")}}
    return render_template("auth/perfil.html", u=fila, errores=errores)
