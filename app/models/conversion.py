"""Conversiones entre unidades (generales o por material)."""
from ..database import execute, query, query_one

SELECT = """
    SELECT cv.*, uo.nombre AS origen_nombre, uo.abreviatura AS origen_abrev,
           ud.nombre AS destino_nombre, ud.abreviatura AS destino_abrev,
           m.nombre AS material_nombre
    FROM conversiones_unidades cv
    JOIN unidades uo ON uo.id = cv.unidad_origen_id
    JOIN unidades ud ON ud.id = cv.unidad_destino_id
    LEFT JOIN materiales m ON m.id = cv.material_id
"""


def listar(material_id=None, solo_generales=False):
    if solo_generales:
        return query(SELECT + " WHERE cv.material_id IS NULL ORDER BY uo.nombre, ud.nombre")
    if material_id:
        return query(SELECT + " WHERE cv.material_id = %s ORDER BY uo.nombre", (material_id,))
    return query(SELECT + " ORDER BY m.nombre IS NOT NULL, m.nombre, uo.nombre, ud.nombre")


def aplicables(material_id):
    """Conversiones específicas del material + generales."""
    return query(
        "SELECT material_id, unidad_origen_id, unidad_destino_id, factor FROM conversiones_unidades "
        "WHERE material_id = %s OR material_id IS NULL",
        (material_id,),
    )


def obtener(conv_id):
    return query_one(SELECT + " WHERE cv.id = %s", (conv_id,))


def existe(material_id, origen_id, destino_id, excluir_id=None):
    return query_one(
        """SELECT id FROM conversiones_unidades
           WHERE material_key = %s AND unidad_origen_id = %s AND unidad_destino_id = %s AND id <> %s""",
        (material_id or 0, origen_id, destino_id, excluir_id or 0),
    ) is not None


def crear(datos):
    return execute(
        """INSERT INTO conversiones_unidades (material_id, unidad_origen_id, unidad_destino_id, factor, observaciones)
           VALUES (%s, %s, %s, %s, %s)""",
        (datos.get("material_id"), datos["unidad_origen_id"], datos["unidad_destino_id"], datos["factor"],
         datos.get("observaciones")),
    )


def actualizar(conv_id, datos):
    execute(
        """UPDATE conversiones_unidades SET material_id=%s, unidad_origen_id=%s, unidad_destino_id=%s,
           factor=%s, observaciones=%s WHERE id=%s""",
        (datos.get("material_id"), datos["unidad_origen_id"], datos["unidad_destino_id"], datos["factor"],
         datos.get("observaciones"), conv_id),
    )


def eliminar(conv_id):
    execute("DELETE FROM conversiones_unidades WHERE id = %s", (conv_id,))
