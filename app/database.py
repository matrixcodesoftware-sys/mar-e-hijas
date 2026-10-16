"""Capa de acceso a MySQL.

- Una conexión PyMySQL por request (guardada en flask.g), cerrada al terminar.
- autocommit=True por defecto: cada sentencia suelta se confirma sola.
- transaction(): bloque atómico (BEGIN … COMMIT / ROLLBACK). Es anidable: sólo
  el bloque más externo confirma o revierte.
- TODAS las consultas usan parámetros (%s): nunca se concatena input del usuario.
"""
from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


def _conectar():
    cfg = current_app.config
    return pymysql.connect(
        host=cfg["DB_HOST"],
        port=cfg["DB_PORT"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        database=cfg["DB_NAME"],
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=10,
    )


def get_db():
    if "db" not in g:
        g.db = _conectar()
        g.db_nivel_tx = 0
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:  # pragma: no cover - cierre best effort
            pass


def query(sql, params=None):
    """Devuelve una lista de dicts."""
    with get_db().cursor() as cur:
        cur.execute(sql, params if params else None)
        return list(cur.fetchall())


def query_one(sql, params=None):
    """Devuelve un dict o None."""
    with get_db().cursor() as cur:
        cur.execute(sql, params if params else None)
        return cur.fetchone()


def scalar(sql, params=None, defecto=None):
    """Devuelve el primer valor de la primera fila."""
    fila = query_one(sql, params)
    if not fila:
        return defecto
    valor = next(iter(fila.values()))
    return defecto if valor is None else valor


def execute(sql, params=None):
    """Ejecuta INSERT/UPDATE/DELETE. Devuelve lastrowid (INSERT) o filas afectadas."""
    with get_db().cursor() as cur:
        filas = cur.execute(sql, params if params else None)
        return cur.lastrowid if cur.lastrowid else filas


def execute_many(sql, lista_params):
    with get_db().cursor() as cur:
        return cur.executemany(sql, lista_params)


@contextmanager
def transaction():
    """Bloque transaccional anidable."""
    db = get_db()
    externo = g.db_nivel_tx == 0
    if externo:
        db.begin()
    g.db_nivel_tx += 1
    try:
        yield db
        g.db_nivel_tx -= 1
        if externo:
            db.commit()
    except Exception:
        g.db_nivel_tx -= 1
        if externo:
            db.rollback()
        raise


def init_app(app):
    app.teardown_appcontext(close_db)
