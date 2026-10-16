"""Usuarios, roles y permisos."""
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from ..database import execute, query, query_one
from ..utils.paginacion import paginar


class Usuario(UserMixin):
    """Usuario autenticado. Carga sus permisos una vez por request."""

    def __init__(self, fila, permisos):
        self.id = fila["id"]
        self.nombre = fila["nombre"]
        self.apellido = fila["apellido"]
        self.username = fila["username"]
        self.email = fila.get("email")
        self.rol_id = fila["rol_id"]
        self.rol_codigo = fila["rol_codigo"]
        self.rol_nombre = fila["rol_nombre"]
        self.activo = bool(fila["activo"])
        self.permisos = set(permisos)
        self.chofer_id = fila.get("chofer_id")

    @property
    def is_active(self):
        return self.activo

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def iniciales(self):
        return (self.nombre[:1] + self.apellido[:1]).upper()

    def puede(self, codigo):
        return codigo in self.permisos

    @property
    def es_chofer(self):
        return self.rol_codigo == "chofer"


SQL_BASE = """
    SELECT u.*, r.codigo AS rol_codigo, r.nombre AS rol_nombre, c.id AS chofer_id
    FROM usuarios u
    JOIN roles r ON r.id = u.rol_id
    LEFT JOIN choferes c ON c.usuario_id = u.id
"""


def permisos_de_rol(rol_id):
    filas = query(
        """SELECT p.codigo FROM roles_permisos rp JOIN permisos p ON p.id = rp.permiso_id
           WHERE rp.rol_id = %s""",
        (rol_id,),
    )
    return [f["codigo"] for f in filas]


def cargar(usuario_id):
    fila = query_one(SQL_BASE + " WHERE u.id = %s", (usuario_id,))
    if not fila:
        return None
    return Usuario(fila, permisos_de_rol(fila["rol_id"]))


def por_username(username):
    return query_one(SQL_BASE + " WHERE u.username = %s", (username,))


def obtener(usuario_id):
    return query_one(SQL_BASE + " WHERE u.id = %s", (usuario_id,))


def verificar_password(fila, password):
    return bool(fila) and check_password_hash(fila["password_hash"], password)


def hash_password(password):
    return generate_password_hash(password)


def registrar_acceso(usuario_id, cuando):
    execute("UPDATE usuarios SET ultimo_acceso = %s WHERE id = %s", (cuando, usuario_id))


def buscar(texto=None, rol_id=None, activo=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(u.nombre LIKE %s OR u.apellido LIKE %s OR u.username LIKE %s)")
        params += [f"%{texto}%"] * 3
    if rol_id:
        where.append("u.rol_id = %s")
        params.append(rol_id)
    if activo in ("0", "1"):
        where.append("u.activo = %s")
        params.append(int(activo))
    return paginar(
        "SELECT u.id, u.nombre, u.apellido, u.username, u.email, u.activo, u.ultimo_acceso, "
        "r.nombre AS rol_nombre, r.codigo AS rol_codigo",
        "FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE " + " AND ".join(where),
        params,
        "ORDER BY u.activo DESC, u.apellido, u.nombre",
    )


def existe_username(username, excluir_id=None):
    fila = query_one(
        "SELECT id FROM usuarios WHERE username = %s AND id <> %s", (username, excluir_id or 0)
    )
    return fila is not None


def existe_email(email, excluir_id=None):
    if not email:
        return False
    fila = query_one("SELECT id FROM usuarios WHERE email = %s AND id <> %s", (email, excluir_id or 0))
    return fila is not None


def crear(datos, password):
    return execute(
        """INSERT INTO usuarios (nombre, apellido, username, email, telefono, password_hash, rol_id, activo)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            datos["nombre"], datos["apellido"], datos["username"], datos.get("email"),
            datos.get("telefono"), hash_password(password), datos["rol_id"], datos.get("activo", 1),
        ),
    )


def actualizar(usuario_id, datos):
    execute(
        """UPDATE usuarios SET nombre=%s, apellido=%s, username=%s, email=%s, telefono=%s,
           rol_id=%s, activo=%s WHERE id=%s""",
        (
            datos["nombre"], datos["apellido"], datos["username"], datos.get("email"),
            datos.get("telefono"), datos["rol_id"], datos["activo"], usuario_id,
        ),
    )


def actualizar_perfil(usuario_id, datos):
    execute(
        "UPDATE usuarios SET nombre=%s, apellido=%s, email=%s, telefono=%s WHERE id=%s",
        (datos["nombre"], datos["apellido"], datos.get("email"), datos.get("telefono"), usuario_id),
    )


def cambiar_password(usuario_id, password):
    execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (hash_password(password), usuario_id))


def cantidad_duenios_activos(excluir_id=None):
    fila = query_one(
        """SELECT COUNT(*) AS n FROM usuarios u JOIN roles r ON r.id=u.rol_id
           WHERE r.codigo='duenio' AND u.activo=1 AND u.id <> %s""",
        (excluir_id or 0,),
    )
    return fila["n"]


def listar_activos():
    return query(
        "SELECT id, nombre, apellido, username FROM usuarios WHERE activo=1 ORDER BY nombre, apellido"
    )


# ------------------------------------------------------------------ roles
def roles():
    return query("SELECT * FROM roles ORDER BY id")


def rol(rol_id):
    return query_one("SELECT * FROM roles WHERE id=%s", (rol_id,))


def permisos():
    return query("SELECT * FROM permisos ORDER BY modulo, codigo")


def ids_permisos_de_rol(rol_id):
    return {f["permiso_id"] for f in query("SELECT permiso_id FROM roles_permisos WHERE rol_id=%s", (rol_id,))}


def reemplazar_permisos_rol(rol_id, permiso_ids):
    execute("DELETE FROM roles_permisos WHERE rol_id=%s", (rol_id,))
    for pid in permiso_ids:
        execute("INSERT INTO roles_permisos (rol_id, permiso_id) VALUES (%s, %s)", (rol_id, pid))
