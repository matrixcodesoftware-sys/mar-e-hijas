"""Usuarios, roles y permisos (sólo dueño por defecto)."""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..database import transaction
from ..models import usuario as usuario_model
from ..services import historial_service
from ..utils.decoradores import permiso_requerido
from ..utils.errores import ValidacionError
from ..utils.validadores import Validador
from ._comun import arg_int, arg_txt

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")


@bp.route("/")
@permiso_requerido("usuarios.gestionar")
def index():
    pagina = usuario_model.buscar(texto=arg_txt("q"), rol_id=arg_int("rol_id"), activo=request.args.get("activo"))
    return render_template("usuarios/index.html", pagina=pagina, roles=usuario_model.roles())


def _leer_form(usuario_id=None):
    v = Validador(request.form)
    datos = {
        "nombre": v.texto("nombre", True, 80),
        "apellido": v.texto("apellido", True, 80),
        "username": (v.texto("username", True, 40, etiqueta="Usuario") or "").lower(),
        "email": v.email("email"),
        "telefono": v.texto("telefono", maximo=40),
        "rol_id": v.entero("rol_id", True, etiqueta="Rol"),
        "activo": v.booleano("activo"),
    }
    password = request.form.get("password") or ""
    if datos["username"] and not USERNAME_RE.match(datos["username"]):
        v.error("username", "Usá de 3 a 40 caracteres: letras minúsculas, números, punto, guion.")
    if datos["username"] and usuario_model.existe_username(datos["username"], usuario_id):
        v.error("username", "Ese nombre de usuario ya existe.")
    if datos["email"] and usuario_model.existe_email(datos["email"], usuario_id):
        v.error("email", "Ese email ya está en uso.")
    if not usuario_id or password:
        if len(password) < 8:
            v.error("password", "La contraseña debe tener al menos 8 caracteres.")
        elif password != request.form.get("password2"):
            v.error("password2", "Las contraseñas no coinciden.")
    if usuario_id:
        actual = usuario_model.obtener(usuario_id)
        rol = usuario_model.rol(datos["rol_id"]) if datos["rol_id"] else None
        deja_de_ser_duenio = actual["rol_codigo"] == "duenio" and (not datos["activo"] or (rol and rol["codigo"] != "duenio"))
        if deja_de_ser_duenio and usuario_model.cantidad_duenios_activos(excluir_id=usuario_id) == 0:
            v.error("rol_id", "Debe quedar al menos un usuario Dueño activo.")
    v.verificar()
    return datos, password


def _form(usuario=None, errores=None, datos=None):
    return render_template("usuarios/form.html", u=datos or usuario or {"activo": 1}, editando=usuario is not None,
                           errores=errores or {}, roles=[(r["id"], r["nombre"]) for r in usuario_model.roles()])


@bp.route("/nuevo", methods=["GET", "POST"])
@permiso_requerido("usuarios.gestionar")
def nuevo():
    if request.method == "POST":
        try:
            datos, password = _leer_form()
            with transaction():
                uid = usuario_model.crear(datos, password)
                historial_service.registrar("crear", "usuarios", f"creó el usuario @{datos['username']}", uid)
            flash("Usuario creado.", "success")
            return redirect(url_for("usuarios.index"))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(errores=e.errores, datos=request.form)
    return _form()


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@permiso_requerido("usuarios.gestionar")
def editar(usuario_id):
    usuario = usuario_model.obtener(usuario_id) or abort(404)
    if request.method == "POST":
        try:
            datos, password = _leer_form(usuario_id)
            if usuario_id == current_user.id and not datos["activo"]:
                raise ValidacionError({"activo": "No podés desactivar tu propio usuario."})
            with transaction():
                usuario_model.actualizar(usuario_id, datos)
                if password:
                    usuario_model.cambiar_password(usuario_id, password)
                historial_service.registrar("modificar", "usuarios", f"modificó el usuario @{datos['username']}"
                                            + (" (cambió la contraseña)" if password else ""), usuario_id)
            flash("Usuario actualizado.", "success")
            return redirect(url_for("usuarios.index"))
        except ValidacionError as e:
            flash(e.mensaje, "danger")
            return _form(usuario, e.errores, {**request.form, "id": usuario_id})
    return _form(usuario)


@bp.route("/roles", methods=["GET", "POST"])
@permiso_requerido("usuarios.gestionar")
def roles():
    roles_ = usuario_model.roles()
    permisos = usuario_model.permisos()
    if request.method == "POST":
        rol_id = arg_int_form("rol_id")
        rol = usuario_model.rol(rol_id) or abort(404)
        if rol["codigo"] == "duenio":
            flash("El rol Dueño siempre tiene todos los permisos.", "warning")
            return redirect(url_for("usuarios.roles"))
        validos = {p["id"] for p in permisos}
        elegidos = [int(x) for x in request.form.getlist("permisos") if x.isdigit() and int(x) in validos]
        with transaction():
            usuario_model.reemplazar_permisos_rol(rol_id, elegidos)
            historial_service.registrar("modificar", "usuarios", f"actualizó los permisos del rol {rol['nombre']}", rol_id)
        flash(f"Permisos de {rol['nombre']} actualizados.", "success")
        return redirect(url_for("usuarios.roles", rol=rol_id))
    asignados = {r["id"]: usuario_model.ids_permisos_de_rol(r["id"]) for r in roles_}
    modulos = {}
    for p in permisos:
        modulos.setdefault(p["modulo"], []).append(p)
    return render_template("usuarios/roles.html", roles=roles_, modulos=modulos, asignados=asignados,
                           rol_activo=arg_int("rol") or (roles_[1]["id"] if len(roles_) > 1 else roles_[0]["id"]))


def arg_int_form(nombre):
    try:
        return int(request.form.get(nombre))
    except (TypeError, ValueError):
        return None
