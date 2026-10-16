"""Comandos de administración de MAR E HIJAS.

    python manage.py init-db            Crea la base (si no existe), las tablas y los datos base.
    python manage.py seed-demo          Carga DATOS DE PRUEBA e historial simulado de ~45 días.
    python manage.py crear-usuario      Crea un usuario (interactivo).
    python manage.py reset-demo         ¡Borra todo! Recrea tablas + datos base + demo.
"""
import getpass
import os
import sys

import pymysql

from app import create_app
from app.config import BASE_DIR

SCHEMA = os.path.join(BASE_DIR, "database", "schema.sql")


def _sentencias(sql):
    """Divide el script en sentencias, ignorando comentarios de línea."""
    limpio = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    return [s.strip() for s in limpio.split(";") if s.strip()]


def crear_esquema(app, borrar=False):
    cfg = app.config
    con = pymysql.connect(host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
                          charset="utf8mb4", autocommit=True)
    with con.cursor() as cur:
        nombre = cfg["DB_NAME"].replace("`", "")
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{nombre}`")
        cur.execute("SHOW TABLES LIKE 'usuarios'")
        existe = cur.fetchone() is not None
        if existe and not borrar:
            print("Las tablas ya existen: no se modifican. (Usá reset-demo para recrear todo.)")
            con.close()
            return
        with open(SCHEMA, encoding="utf-8") as f:
            for sentencia in _sentencias(f.read()):
                cur.execute(sentencia)
    con.close()
    print(f"Esquema creado en la base '{cfg['DB_NAME']}'.")


def cmd_init_db(app):
    crear_esquema(app)
    with app.app_context():
        from app.seed import cargar_base

        cargar_base()
        print("Datos base cargados (roles, permisos, unidades, métodos de pago, categorías, comprobantes ARCA).")
        from app.database import query_one

        if not query_one("SELECT id FROM usuarios LIMIT 1"):
            print("\nNo hay usuarios. Creá el usuario Dueño con:  python manage.py crear-usuario")


def cmd_seed_demo(app):
    with app.app_context(), app.test_request_context():
        from app.seed import cargar_base, cargar_demo

        cargar_base()
        print("Cargando datos de prueba e historial (puede tardar unos segundos)…")
        cargar_demo()
    print("Datos de prueba cargados. Usuarios de prueba:")
    from app.seed import USUARIOS_DEMO

    for nombre, apellido, user, pwd, rol in USUARIOS_DEMO:
        print(f"   {user:<10} / {pwd:<12} ({rol})")


def cmd_reset_demo(app):
    resp = input(f"Se BORRARÁN todos los datos de '{app.config['DB_NAME']}'. Escribí BORRAR para confirmar: ")
    if resp.strip() != "BORRAR":
        print("Cancelado.")
        return
    crear_esquema(app, borrar=True)
    cmd_seed_demo(app)


def cmd_crear_usuario(app):
    with app.app_context():
        from app.database import query
        from app.seed import cargar_base, crear_usuario

        cargar_base()
        roles = query("SELECT codigo, nombre FROM roles ORDER BY id")
        nombre = input("Nombre: ").strip()
        apellido = input("Apellido: ").strip()
        username = input("Usuario (para ingresar): ").strip().lower()
        print("Roles: " + ", ".join(f"{r['codigo']} ({r['nombre']})" for r in roles))
        rol = input("Rol [duenio]: ").strip() or "duenio"
        while True:
            pwd = getpass.getpass("Contraseña (mín. 8): ")
            if len(pwd) >= 8 and pwd == getpass.getpass("Repetir: "):
                break
            print("La contraseña es corta o no coincide.")
        uid = crear_usuario(nombre, apellido, username, pwd, rol)
        print(f"Usuario creado (id {uid}).")


COMANDOS = {"init-db": cmd_init_db, "seed-demo": cmd_seed_demo, "crear-usuario": cmd_crear_usuario,
            "reset-demo": cmd_reset_demo}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print(__doc__)
        sys.exit(1)
    COMANDOS[sys.argv[1]](create_app())
