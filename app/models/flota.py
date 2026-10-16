"""Vehículos (camiones) y choferes."""
from ..database import execute, query, query_one
from ..utils.paginacion import paginar

# ------------------------------------------------------------------ vehículos
SELECT_VEH = """
    SELECT v.*, tv.nombre AS tipo, tv.recargo_transporte, u.nombre AS unidad_nombre, u.abreviatura AS unidad_abrev,
           CONCAT(c.nombre, ' ', c.apellido) AS chofer
"""
FROM_VEH = """
    FROM vehiculos v
    JOIN tipos_vehiculo tv ON tv.id = v.tipo_vehiculo_id
    JOIN unidades u ON u.id = v.unidad_capacidad_id
    LEFT JOIN choferes c ON c.id = v.chofer_id
"""
CAMPOS_VEH = ["patente", "tipo_vehiculo_id", "marca", "modelo", "anio", "capacidad", "unidad_capacidad_id",
              "estado", "chofer_id", "observaciones"]


def buscar_vehiculos(texto=None, tipo_id=None, estado=None, pagina=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(v.patente LIKE %s OR v.marca LIKE %s OR v.modelo LIKE %s)")
        params += [f"%{texto}%"] * 3
    if tipo_id:
        where.append("v.tipo_vehiculo_id = %s")
        params.append(tipo_id)
    if estado:
        where.append("v.estado = %s")
        params.append(estado)
    return paginar(SELECT_VEH, FROM_VEH + " WHERE " + " AND ".join(where), params, "ORDER BY v.patente", pagina=pagina)


def vehiculo(vehiculo_id):
    return query_one(SELECT_VEH + FROM_VEH + " WHERE v.id = %s", (vehiculo_id,))


def vehiculos_operativos():
    return query(SELECT_VEH + FROM_VEH + " WHERE v.estado IN ('disponible','en_uso') ORDER BY v.patente")


def opciones_vehiculos(todos=False):
    filas = query(SELECT_VEH + FROM_VEH + ("" if todos else " WHERE v.estado <> 'inactivo'") + " ORDER BY v.patente")
    return [(v["id"], f"{v['patente']} · {v['tipo']} ({v['capacidad']:.3g} {v['unidad_abrev']})") for v in filas]


def existe_patente(patente, excluir_id=None):
    return query_one("SELECT id FROM vehiculos WHERE patente = %s AND id <> %s", (patente, excluir_id or 0)) is not None


def crear_vehiculo(datos):
    return execute(
        f"INSERT INTO vehiculos ({', '.join(CAMPOS_VEH)}) VALUES ({', '.join(['%s'] * len(CAMPOS_VEH))})",
        [datos.get(c) for c in CAMPOS_VEH])


def actualizar_vehiculo(vehiculo_id, datos):
    execute("UPDATE vehiculos SET " + ", ".join(f"{c} = %s" for c in CAMPOS_VEH) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS_VEH] + [vehiculo_id])


def set_estado_vehiculo(vehiculo_id, estado):
    execute("UPDATE vehiculos SET estado = %s WHERE id = %s", (estado, vehiculo_id))


# ------------------------------------------------------------------ choferes
SELECT_CHO = """
    SELECT c.*, u.username, (SELECT GROUP_CONCAT(v.patente SEPARATOR ', ') FROM vehiculos v WHERE v.chofer_id = c.id) AS vehiculos
"""
FROM_CHO = " FROM choferes c LEFT JOIN usuarios u ON u.id = c.usuario_id "
CAMPOS_CHO = ["nombre", "apellido", "dni", "telefono", "licencia_numero", "licencia_categoria",
              "licencia_vencimiento", "usuario_id", "estado", "observaciones"]


def buscar_choferes(texto=None, estado=None, pagina=None):
    where, params = ["1=1"], []
    if texto:
        where.append("(c.nombre LIKE %s OR c.apellido LIKE %s OR c.dni LIKE %s)")
        params += [f"%{texto}%"] * 3
    if estado:
        where.append("c.estado = %s")
        params.append(estado)
    return paginar(SELECT_CHO, FROM_CHO + " WHERE " + " AND ".join(where), params, "ORDER BY c.apellido, c.nombre",
                   pagina=pagina)


def chofer(chofer_id):
    return query_one(SELECT_CHO + FROM_CHO + " WHERE c.id = %s", (chofer_id,))


def opciones_choferes():
    return [(c["id"], f"{c['nombre']} {c['apellido']}") for c in query(
        "SELECT id, nombre, apellido FROM choferes WHERE estado = 'activo' ORDER BY nombre, apellido")]


def existe_dni(dni, excluir_id=None):
    return query_one("SELECT id FROM choferes WHERE dni = %s AND id <> %s", (dni, excluir_id or 0)) is not None


def usuario_ya_asignado(usuario_id, excluir_id=None):
    if not usuario_id:
        return False
    return query_one("SELECT id FROM choferes WHERE usuario_id = %s AND id <> %s",
                     (usuario_id, excluir_id or 0)) is not None


def usuarios_chofer_opciones():
    filas = query(
        """SELECT u.id, u.nombre, u.apellido, u.username FROM usuarios u JOIN roles r ON r.id = u.rol_id
           WHERE r.codigo = 'chofer' AND u.activo = 1 ORDER BY u.nombre""")
    return [(u["id"], f"{u['nombre']} {u['apellido']} (@{u['username']})") for u in filas]


def crear_chofer(datos):
    return execute(
        f"INSERT INTO choferes ({', '.join(CAMPOS_CHO)}) VALUES ({', '.join(['%s'] * len(CAMPOS_CHO))})",
        [datos.get(c) for c in CAMPOS_CHO])


def actualizar_chofer(chofer_id, datos):
    execute("UPDATE choferes SET " + ", ".join(f"{c} = %s" for c in CAMPOS_CHO) + " WHERE id = %s",
            [datos.get(c) for c in CAMPOS_CHO] + [chofer_id])


def licencias_por_vencer(hasta):
    return query(
        """SELECT id, nombre, apellido, licencia_vencimiento FROM choferes
           WHERE estado = 'activo' AND licencia_vencimiento IS NOT NULL AND licencia_vencimiento <= %s
           ORDER BY licencia_vencimiento""", (hasta,))


def estadisticas_chofer(chofer_id):
    return query_one(
        """SELECT COUNT(*) AS total,
                  SUM(estado = 'entregada') AS entregadas,
                  SUM(estado IN ('pendiente','asignada','en_camino')) AS pendientes,
                  SUM(estado = 'no_entregada') AS no_entregadas
           FROM entregas WHERE chofer_id = %s""", (chofer_id,))
