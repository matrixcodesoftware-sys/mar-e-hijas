"""Pruebas de integración de punta a punta contra una base MySQL de prueba.

Requiere un MySQL accesible con las credenciales del .env. Usa una base aparte
(<DB_NAME>_test) que se recrea en cada corrida.

    pytest -q
"""
import os
import re
from decimal import Decimal

import pytest

os.environ.setdefault("SECRET_KEY", "clave-de-pruebas")

from app import create_app  # noqa: E402
from app.config import DevelopmentConfig  # noqa: E402


class ConfigPruebas(DevelopmentConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    DB_NAME = os.environ.get("DB_NAME", "mar_e_hijas") + "_test"
    SECRET_KEY = "clave-de-pruebas"


@pytest.fixture(scope="session")
def app():
    import manage

    app = create_app(ConfigPruebas)
    manage.crear_esquema(app, borrar=True)
    with app.app_context(), app.test_request_context():
        from app.seed import cargar_base, cargar_demo

        cargar_base()
        cargar_demo(dias_historial=10)
    return app


def login(app, usuario, password):
    c = app.test_client()
    r = c.post("/login", data={"username": usuario, "password": password})
    assert r.status_code == 302, f"login {usuario} falló"
    return c


@pytest.fixture(scope="session")
def dueno(app):
    return login(app, "dueno", "Dueno2026!")


def q(app, sql, params=()):
    with app.app_context():
        from app.database import query

        return query(sql, params)


def q1(app, sql, params=()):
    filas = q(app, sql, params)
    return filas[0] if filas else None


# ---------------------------------------------------------------------------
def test_login_incorrecto(app):
    c = app.test_client()
    r = c.post("/login", data={"username": "dueno", "password": "mal"})
    assert r.status_code == 401


def test_csrf_activo():
    """Con la configuración normal, un POST sin token CSRF se rechaza."""
    class ConfCSRF(ConfigPruebas):
        WTF_CSRF_ENABLED = True

    app = create_app(ConfCSRF)
    r = app.test_client().post("/login", data={"username": "dueno", "password": "Dueno2026!"})
    assert r.status_code == 400


def test_paginas_con_busqueda(app, dueno):
    urls = ["/ventas/?rapido=mes", "/pedidos/?rapido=activos", "/presupuestos/?rapido=todos", "/entregas/?rapido=hoy",
            "/materiales/?rapido=todos", "/clientes/?buscar=1", "/clientes/?deuda=1&buscar=1", "/proveedores/?buscar=1",
            "/stock/movimientos?buscar=1", "/stock/?bajo=1", "/gastos/?rapido=mes", "/historial/?buscar=1",
            "/caja/historial", "/reportes/ventas", "/reportes/materiales?orden=menos", "/reportes/clientes",
            "/reportes/entregas?periodo=semana", "/configuracion/empresa", "/configuracion/zonas_entrega",
            "/configuracion/conversiones", "/configuracion/facturacion", "/configuracion/metodos_pago",
            "/usuarios/roles"]
    for u in urls:
        r = dueno.get(u)
        assert r.status_code == 200, u


def test_detalles(app, dueno):
    for tabla, url in [("ventas", "/ventas/{}"), ("clientes", "/clientes/{}"), ("clientes", "/clientes/{}/cuenta"),
                       ("materiales", "/materiales/{}"), ("proveedores", "/proveedores/{}"), ("vehiculos", "/camiones/{}"),
                       ("choferes", "/choferes/{}"), ("entregas", "/entregas/{}"), ("pedidos", "/pedidos/{}"),
                       ("presupuestos", "/presupuestos/{}"), ("cajas", "/caja/{}")]:
        fila = q1(app, f"SELECT MAX(id) AS id FROM {tabla}")
        r = dueno.get(url.format(fila["id"]))
        assert r.status_code == 200, url


def test_pdfs_y_exportaciones(app, dueno):
    v = q1(app, "SELECT MAX(id) AS id FROM ventas")["id"]
    p = q1(app, "SELECT MAX(id) AS id FROM presupuestos")["id"]
    c = q1(app, "SELECT MAX(cliente_id) AS id FROM cuentas_corrientes")["id"]
    for u in [f"/ventas/{v}/pdf", f"/presupuestos/{p}/pdf", f"/clientes/{c}/cuenta/pdf",
              "/reportes/ventas?formato=pdf", "/reportes/materiales?formato=pdf", "/reportes/entregas?formato=pdf",
              "/reportes/clientes?formato=pdf&lista=deudores"]:
        r = dueno.get(u)
        assert r.status_code == 200 and r.data[:4] == b"%PDF", u
    r = dueno.get("/reportes/ventas?formato=csv")
    assert r.status_code == 200 and "Facturación" in r.data.decode("utf-8-sig")


def test_api(app, dueno):
    assert dueno.get("/api/clientes/buscar?q=Juan").get_json()["resultados"]
    mats = dueno.get("/api/materiales/buscar?q=arena").get_json()["resultados"]
    arena = next(m for m in mats if m["texto"] == "Arena gruesa")
    unidades = {u["nombre"]: u for u in arena["unidades"]}
    # Conversiones configurables: medio m³ = 0,5 m³; viaje = 6 m³; tonelada (arena) = 0,625 m³
    assert Decimal(unidades["Medio metro cúbico"]["factor"]) == Decimal("0.5")
    assert Decimal(unidades["Viaje"]["factor"]) == Decimal("6")
    assert Decimal(unidades["Tonelada"]["factor"]) == Decimal("0.625")
    zona = q1(app, "SELECT id FROM zonas_entrega WHERE nombre LIKE 'Zona 3%'")["id"]
    cot = dueno.get(f"/api/transporte/cotizar?zona_id={zona}&cantidad=6").get_json()
    assert Decimal(cot["total"]) == Decimal("18000") + Decimal("900") * 25
    assert "notificaciones" in dueno.get("/api/estado").get_json()


def _stock(app, codigo):
    return Decimal(q1(app, "SELECT stock_actual FROM materiales WHERE codigo=%s", (codigo,))["stock_actual"])


def test_flujo_completo(app, dueno):
    """CLIENTE → PRESUPUESTO → PEDIDO → VENTA → STOCK → ENTREGA → PAGO → CAJA → REPORTE"""
    # Cliente nuevo
    r = dueno.post("/clientes/nuevo", data={"razon_social": "Cliente Test Flujo", "tipo": "constructor",
                                            "documento_tipo": "DNI", "documento": "40111222",
                                            "condicion_iva": "consumidor_final", "direccion": "Calle 1",
                                            "localidad": "Rosario", "limite_credito": "5000000", "activo": "1"})
    assert r.status_code == 302
    cid = q1(app, "SELECT id FROM clientes WHERE documento='40111222'")["id"]
    arena = q1(app, "SELECT * FROM materiales WHERE codigo='ARE-GR'")
    u = {x["codigo"]: x["id"] for x in q(app, "SELECT id, codigo FROM unidades")}
    zona = q1(app, "SELECT id FROM zonas_entrega WHERE nombre LIKE 'Zona 1%'")["id"]

    # Presupuesto: 2 viajes de arena (=12 m³)
    r = dueno.post("/presupuestos/nuevo", data={"cliente_id": cid, "tipo_entrega": "envio", "zona_id": zona,
                                                "direccion_entrega": "Calle 1", "costo_envio": "15000",
                                                "item_material_id": arena["id"], "item_unidad_id": u["viaje"],
                                                "item_cantidad": "2", "item_precio": "", "item_descuento": "0"})
    assert r.status_code == 302
    pres = q1(app, "SELECT * FROM presupuestos WHERE cliente_id=%s", (cid,))
    assert pres["total"] == Decimal(arena["precio_venta"]) * 12 + 15000

    # Presupuesto → pedido
    r = dueno.post(f"/presupuestos/{pres['id']}/a-pedido")
    assert r.status_code == 302
    ped = q1(app, "SELECT * FROM pedidos WHERE presupuesto_id=%s", (pres["id"],))
    assert ped and q1(app, "SELECT estado FROM presupuestos WHERE id=%s", (pres["id"],))["estado"] == "aceptado"
    dp = q1(app, "SELECT * FROM detalle_pedidos WHERE pedido_id=%s", (ped["id"],))

    # Viaje de 2 viajes (=12 m³) en camión de 6 m³ → debe rechazarse por capacidad
    v6 = q1(app, "SELECT * FROM vehiculos WHERE patente='AB123CD'")
    dueno.post(f"/pedidos/{ped['id']}/viaje", data={f"cant_{dp['id']}": "2", "vehiculo_id": v6["id"],
                                                    "chofer_id": v6["chofer_id"]})
    assert not q(app, "SELECT id FROM entregas WHERE pedido_id=%s", (ped["id"],))
    # Dos viajes de 1 (=6 m³) sí entran
    for _ in range(2):
        dueno.post(f"/pedidos/{ped['id']}/viaje", data={f"cant_{dp['id']}": "1", "vehiculo_id": v6["id"],
                                                        "chofer_id": v6["chofer_id"]})
    entregas = q(app, "SELECT * FROM entregas WHERE pedido_id=%s", (ped["id"],))
    assert len(entregas) == 2 and all(e["estado"] == "asignada" for e in entregas)
    # No se puede programar más de lo pedido
    dueno.post(f"/pedidos/{ped['id']}/viaje", data={f"cant_{dp['id']}": "1"})
    assert len(q(app, "SELECT id FROM entregas WHERE pedido_id=%s", (ped["id"],))) == 2

    # Pedido → venta: parte en efectivo, resto a cuenta corriente
    stock_antes = _stock(app, "ARE-GR")
    caja = q1(app, "SELECT * FROM cajas WHERE estado='abierta'")
    efectivo = q1(app, "SELECT id FROM metodos_pago WHERE codigo='efectivo'")["id"]
    total = Decimal(ped["total"])
    r = dueno.post("/ventas/nueva", data={"cliente_id": cid, "pedido_id": ped["id"], "tipo_entrega": "envio",
                                          "zona_id": zona, "direccion_entrega": "Calle 1", "costo_envio": "15000",
                                          "item_material_id": arena["id"], "item_unidad_id": u["viaje"],
                                          "item_cantidad": "2", "item_precio": str(Decimal(arena["precio_venta"]) * 6),
                                          "item_descuento": "0", "metodo_pago_id": efectivo, "monto_pagado": "100000"})
    assert r.status_code == 302, r.data[:500]
    venta = q1(app, "SELECT * FROM ventas WHERE pedido_id=%s", (ped["id"],))
    assert venta["total"] == total and venta["monto_pagado"] == 100000
    assert venta["saldo_cta_cte"] == total - 100000 and venta["estado_pago"] == "parcial"
    assert _stock(app, "ARE-GR") == stock_antes - 12  # 2 viajes × 6 m³
    assert q1(app, "SELECT venta_id FROM pedidos WHERE id=%s", (ped["id"],))["venta_id"] == venta["id"]
    mc = q1(app, "SELECT * FROM movimientos_caja WHERE venta_id=%s", (venta["id"],))
    assert mc["caja_id"] == caja["id"] and mc["monto"] == 100000
    saldo_cc = q1(app, "SELECT saldo FROM cuentas_corrientes WHERE cliente_id=%s", (cid,))["saldo"]
    assert saldo_cc == total - 100000

    # Chofer: sólo ve sus entregas y marca ENTREGA REALIZADA
    chofer = login(app, "chofer1", "Chofer2026!")
    assert chofer.get("/entregas/mis-entregas").status_code == 200
    assert chofer.get("/ventas/").status_code == 403
    assert chofer.get("/dashboard/").status_code == 403
    for e in entregas:
        chofer.post(f"/entregas/{e['id']}/estado", data={"estado": "en_camino"})
        assert q1(app, "SELECT estado FROM pedidos WHERE id=%s", (ped["id"],))["estado"] == "en_camino"
        chofer.post(f"/entregas/{e['id']}/estado", data={"estado": "entregada", "recibido_por": "Capataz"})
    assert all(x["estado"] == "entregada" for x in q(app, "SELECT estado FROM entregas WHERE pedido_id=%s", (ped["id"],)))
    assert q1(app, "SELECT estado FROM pedidos WHERE id=%s", (ped["id"],))["estado"] == "entregado"

    # La venta con entregas realizadas no se puede anular
    dueno.post(f"/ventas/{venta['id']}/anular", data={"motivo": "prueba de anulación"})
    assert q1(app, "SELECT estado FROM ventas WHERE id=%s", (venta["id"],))["estado"] == "confirmada"

    # Pago de cuenta corriente → caja
    transf = q1(app, "SELECT id FROM metodos_pago WHERE codigo='transferencia'")["id"]
    dueno.post(f"/clientes/{cid}/cuenta/movimiento", data={"tipo": "pago", "monto": str(saldo_cc),
                                                           "metodo_pago_id": transf, "referencia": "OP-1"})
    assert q1(app, "SELECT saldo FROM cuentas_corrientes WHERE cliente_id=%s", (cid,))["saldo"] == 0

    # Reporte de ventas del día incluye la venta
    r = dueno.get("/reportes/ventas?periodo=hoy&formato=csv")
    assert r.status_code == 200

    # Historial registró las operaciones
    textos = " ".join(h["descripcion"] for h in q(app, "SELECT descripcion FROM historial_operaciones ORDER BY id DESC LIMIT 40"))
    assert "creó la venta" in textos and "registró un pago" in textos


def test_venta_y_anulacion(app, dueno):
    cliente = q1(app, "SELECT id FROM clientes WHERE razon_social LIKE 'Juan%%'")["id"]
    piedra = q1(app, "SELECT * FROM materiales WHERE codigo='PP-620'")
    m3 = q1(app, "SELECT id FROM unidades WHERE codigo='m3'")["id"]
    mp = q1(app, "SELECT id FROM metodos_pago WHERE codigo='mercado_pago'")["id"]
    antes = _stock(app, "PP-620")
    r = dueno.post("/ventas/nueva", data={"cliente_id": cliente, "tipo_entrega": "retiro", "item_material_id": piedra["id"],
                                          "item_unidad_id": m3, "item_cantidad": "2", "item_precio": "",
                                          "item_descuento": "10", "metodo_pago_id": mp})
    assert r.status_code == 302
    vid = int(re.search(r"/ventas/(\d+)", r.headers["Location"]).group(1))
    v = q1(app, "SELECT * FROM ventas WHERE id=%s", (vid,))
    # 2 m³ de piedra = 3 t; precio por m³ = 1,5 × precio por t; 10 % de descuento
    esperado = (Decimal(2) * Decimal(piedra["precio_venta"]) * Decimal("1.5") * Decimal("0.9")).quantize(Decimal("0.01"))
    assert v["total"] == esperado and v["estado_pago"] == "pagada"
    assert _stock(app, "PP-620") == antes - 3
    r = dueno.post(f"/ventas/{vid}/anular", data={"motivo": "Cliente se arrepintió"})
    assert q1(app, "SELECT estado FROM ventas WHERE id=%s", (vid,))["estado"] == "anulada"
    assert _stock(app, "PP-620") == antes
    assert q1(app, "SELECT COUNT(*) AS n FROM movimientos_caja WHERE venta_id=%s AND tipo='anulacion'", (vid,))["n"] == 1


def test_stock_insuficiente_y_limite(app, dueno):
    cliente = q1(app, "SELECT id FROM clientes WHERE razon_social LIKE 'Ana%%'")["id"]
    cem = q1(app, "SELECT * FROM materiales WHERE codigo='CEM-50'")
    efectivo = q1(app, "SELECT id FROM metodos_pago WHERE codigo='efectivo'")["id"]
    antes = q1(app, "SELECT COUNT(*) AS n FROM ventas")["n"]
    r = dueno.post("/ventas/nueva", data={"cliente_id": cliente, "tipo_entrega": "retiro", "item_material_id": cem["id"],
                                          "item_unidad_id": cem["unidad_id"], "item_cantidad": "99999",
                                          "metodo_pago_id": efectivo})
    assert r.status_code == 200 and "Stock insuficiente" in r.data.decode()
    assert q1(app, "SELECT COUNT(*) AS n FROM ventas")["n"] == antes  # rollback completo


def test_caja_cierre(app, dueno):
    caja = q1(app, "SELECT * FROM cajas WHERE estado='abierta'")
    efectivo = q1(app, "SELECT id FROM metodos_pago WHERE codigo='efectivo'")["id"]
    dueno.post("/caja/movimiento", data={"tipo": "ingreso", "metodo_pago_id": efectivo, "monto": "1000",
                                         "concepto": "Cambio"})
    r = dueno.post("/caja/cerrar", data={"saldo_declarado": "0"})
    assert r.status_code == 302
    cerrada = q1(app, "SELECT * FROM cajas WHERE id=%s", (caja["id"],))
    assert cerrada["estado"] == "cerrada" and cerrada["diferencia"] == -cerrada["saldo_esperado"]
    # Sin caja abierta no se puede cobrar
    cliente = q1(app, "SELECT id FROM clientes WHERE razon_social LIKE 'Ana%%'")["id"]
    arena = q1(app, "SELECT * FROM materiales WHERE codigo='ARE-GR'")
    r = dueno.post("/ventas/nueva", data={"cliente_id": cliente, "tipo_entrega": "retiro", "item_material_id": arena["id"],
                                          "item_unidad_id": arena["unidad_id"], "item_cantidad": "1",
                                          "metodo_pago_id": efectivo})
    assert "No hay una caja abierta" in r.data.decode()
    dueno.post("/caja/abrir", data={"monto_inicial": "10000"})
    assert q1(app, "SELECT COUNT(*) AS n FROM cajas WHERE estado='abierta'")["n"] == 1


def test_permisos_por_rol(app):
    vendedor = login(app, "vendedor", "Vende2026!")
    assert vendedor.get("/ventas/nueva").status_code == 200
    assert vendedor.get("/presupuestos/nuevo").status_code == 200
    assert vendedor.get("/clientes/nuevo").status_code == 200
    assert vendedor.get("/materiales/?rapido=todos").status_code == 200
    assert vendedor.get("/pedidos/?rapido=activos").status_code == 200
    for prohibida in ["/usuarios/", "/configuracion/empresa", "/caja/", "/gastos/", "/reportes/ventas",
                      "/materiales/nuevo", "/pedidos/nuevo", "/historial/"]:
        assert vendedor.get(prohibida).status_code == 403, prohibida
    admin = login(app, "admin", "Admin2026!")
    assert admin.get("/reportes/ventas").status_code == 200
    assert admin.get("/configuracion/zonas_entrega").status_code == 200
    assert admin.get("/usuarios/").status_code == 403
    assert admin.get("/configuracion/empresa").status_code == 403
