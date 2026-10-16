"""Datos iniciales.

cargar_base():  catálogos imprescindibles (roles, permisos, unidades, métodos de pago,
                categorías, tipos de comprobante ARCA, configuración).
cargar_demo():  DATOS DE PRUEBA claramente identificados (usuarios, materiales con
                precios ficticios, clientes, proveedores, flota) y un historial de
                operaciones de las últimas semanas generado con los servicios reales,
                para que el dashboard y los reportes tengan información.
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from flask_login import login_user

from .database import execute, query, query_one, transaction
from .models import catalogos, configuracion
from .models import usuario as usuario_model
from .services import (caja_service, cuenta_corriente_service, entrega_service, gasto_service, pedido_service,
                       presupuesto_service, proveedor_service, stock_service, venta_service)
from .services.permisos_catalogo import PERMISOS, PERMISOS_POR_ROL, ROLES
from .utils.errores import NegocioError
from .utils.fechas import fijar_ahora, hoy

PRUEBA = "(DATO DE PRUEBA)"


# =============================================================================
# BASE
# =============================================================================
def cargar_base():
    with transaction():
        for codigo, nombre, desc in ROLES:
            execute("INSERT IGNORE INTO roles (codigo, nombre, descripcion) VALUES (%s, %s, %s)", (codigo, nombre, desc))
        for codigo, modulo, desc in PERMISOS:
            execute("INSERT IGNORE INTO permisos (codigo, modulo, descripcion) VALUES (%s, %s, %s)", (codigo, modulo, desc))
        roles = {r["codigo"]: r["id"] for r in query("SELECT id, codigo FROM roles")}
        permisos = {p["codigo"]: p["id"] for p in query("SELECT id, codigo FROM permisos")}
        for rol, lista in PERMISOS_POR_ROL.items():
            for p in lista:
                execute("INSERT IGNORE INTO roles_permisos (rol_id, permiso_id) VALUES (%s, %s)", (roles[rol], permisos[p]))

        unidades = [
            ("tonelada", "Tonelada", "t", "masa"),
            ("m3", "Metro cúbico", "m³", "volumen"),
            ("medio_m3", "Medio metro cúbico", "½ m³", "volumen"),
            ("bolson", "Bolsón", "bolsón", "volumen"),
            ("bolsa", "Bolsa", "bolsa", "conteo"),
            ("unidad", "Unidad", "u", "conteo"),
            ("viaje", "Viaje", "viaje", "viaje"),
            ("kg", "Kilogramo", "kg", "masa"),
        ]
        for u in unidades:
            execute("INSERT IGNORE INTO unidades (codigo, nombre, abreviatura, magnitud) VALUES (%s, %s, %s, %s)", u)
        u = {r["codigo"]: r["id"] for r in query("SELECT id, codigo FROM unidades")}
        generales = [
            (u["m3"], u["medio_m3"], "2", "Medio metro = 0,5 m³"),
            (u["viaje"], u["m3"], "6", "Viaje estándar de camión volcador: ajustar a la realidad del galpón"),
            (u["bolson"], u["m3"], "1", "Bolsón de 1 m³"),
            (u["tonelada"], u["kg"], "1000", None),
        ]
        for o, d, f, obs in generales:
            execute("""INSERT IGNORE INTO conversiones_unidades (material_id, unidad_origen_id, unidad_destino_id, factor,
                       observaciones) VALUES (NULL, %s, %s, %s, %s)""", (o, d, f, obs))

        for m in [("efectivo", "Efectivo", "efectivo"), ("transferencia", "Transferencia", "transferencia"),
                  ("debito", "Tarjeta de débito", "tarjeta"), ("credito", "Tarjeta de crédito", "tarjeta"),
                  ("mercado_pago", "Mercado Pago", "billetera"), ("cuenta_corriente", "Cuenta corriente", "cuenta_corriente"),
                  ("otro", "Otro", "otro")]:
            execute("INSERT IGNORE INTO metodos_pago (codigo, nombre, grupo) VALUES (%s, %s, %s)", m)

        for c in ["Arena", "Ripio", "Piedra", "Piedra partida", "Granito", "Canto rodado", "Tosca", "Tierra", "Otros"]:
            execute("INSERT IGNORE INTO categorias_materiales (nombre) VALUES (%s)", (c,))
        for c in ["Combustible", "Mantenimiento", "Proveedores", "Servicios", "Reparaciones", "Sueldos", "Otros"]:
            execute("INSERT IGNORE INTO categorias_gastos (nombre) VALUES (%s)", (c,))
        for t in [("Camión volcador", 0), ("Camión con acoplado", 0), ("Camioneta", 0), ("Otro", 0)]:
            execute("INSERT IGNORE INTO tipos_vehiculo (nombre, recargo_transporte) VALUES (%s, %s)", t)

        for t in [(1, "Factura A", "A", "factura"), (2, "Nota de débito A", "A", "nota_debito"),
                  (3, "Nota de crédito A", "A", "nota_credito"), (6, "Factura B", "B", "factura"),
                  (7, "Nota de débito B", "B", "nota_debito"), (8, "Nota de crédito B", "B", "nota_credito"),
                  (11, "Factura C", "C", "factura"), (12, "Nota de débito C", "C", "nota_debito"),
                  (13, "Nota de crédito C", "C", "nota_credito")]:
            execute("INSERT IGNORE INTO tipos_comprobante (codigo, descripcion, letra, clase) VALUES (%s, %s, %s, %s)", t)

        if not query_one("SELECT clave FROM configuracion LIMIT 1"):
            configuracion.guardar({k: v[0] for k, v in configuracion.DEFINICIONES.items()})


def crear_usuario(nombre, apellido, username, password, rol_codigo, email=None):
    rol = query_one("SELECT id FROM roles WHERE codigo = %s", (rol_codigo,))
    if not rol:
        raise ValueError(f"Rol inexistente: {rol_codigo}")
    existente = query_one("SELECT id FROM usuarios WHERE username = %s", (username,))
    if existente:
        return existente["id"]
    return usuario_model.crear({"nombre": nombre, "apellido": apellido, "username": username, "email": email,
                                "rol_id": rol["id"], "activo": 1}, password)


# =============================================================================
# DEMO
# =============================================================================
USUARIOS_DEMO = [
    ("Marta", "Rodríguez", "dueno", "Dueno2026!", "duenio"),
    ("Julián", "Ferreyra", "admin", "Admin2026!", "admin"),
    ("Sofía", "Medina", "vendedor", "Vende2026!", "vendedor"),
    ("Carlos", "Gómez", "chofer1", "Chofer2026!", "chofer"),
    ("Raúl", "Benítez", "chofer2", "Chofer2026!", "chofer"),
]

# código, nombre, categoría, unidad, compra, venta, stock mínimo, conversiones propias [(origen, destino, factor)]
MATERIALES_DEMO = [
    ("ARE-GR", "Arena gruesa", "Arena", "m3", 18000, 28000, 30, [("tonelada", "m3", "0.625")]),
    ("ARE-FI", "Arena fina", "Arena", "m3", 17000, 26500, 25, [("tonelada", "m3", "0.667")]),
    ("RIP-01", "Ripio", "Ripio", "m3", 16000, 25000, 25, [("tonelada", "m3", "0.588")]),
    ("PP-620", "Piedra partida 6/20", "Piedra partida", "tonelada", 30000, 45000, 20, [("m3", "tonelada", "1.5")]),
    ("PP-1030", "Piedra partida 10/30", "Piedra partida", "tonelada", 28000, 43000, 20, [("m3", "tonelada", "1.5")]),
    ("CAN-01", "Canto rodado", "Canto rodado", "tonelada", 22000, 34000, 15, [("m3", "tonelada", "1.6")]),
    ("GRA-01", "Granito triturado", "Granito", "tonelada", 38000, 56000, 10, [("m3", "tonelada", "1.55")]),
    ("TOS-01", "Tosca", "Tosca", "m3", 9000, 15000, 30, [("tonelada", "m3", "0.555")]),
    ("TIE-NE", "Tierra negra", "Tierra", "m3", 11000, 19000, 20, [("tonelada", "m3", "0.8")]),
    ("CEM-50", "Cemento portland 50 kg", "Otros", "bolsa", 7500, 9800, 40, [("bolsa", "m3", "0.035"), ("bolsa", "kg", "50")]),
]

PROVEEDORES_DEMO = [
    ("Cantera Los Álamos S.A. " + PRUEBA, "30712345676", "Ing. Pablo Ríos", "0341 555-1001", "Piedra, granito y canto rodado"),
    ("Arenera del Río S.R.L. " + PRUEBA, "30698765432", "Luciana Paz", "0341 555-1002", "Arena gruesa y fina"),
    ("Áridos y Transportes Sur " + PRUEBA, "20304050607", "Diego Suárez", "0341 555-1003", "Ripio, tosca y tierra"),
]


def _cuit(base10):
    """Completa el dígito verificador de un CUIT de 10 dígitos."""
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(base10, pesos))
    r = 11 - (suma % 11)
    dv = 0 if r == 11 else (9 if r == 10 else r)
    return base10 + str(dv)


CLIENTES_DEMO = [
    # tipo, razón social, doc tipo, doc, cond iva, tel, dirección, localidad, zona, límite
    ("particular", "Consumidor final", "OTRO", None, "consumidor_final", None, None, None, None, 0),
    ("particular", "Juan Pérez " + PRUEBA, "DNI", "28456123", "consumidor_final", "341 611-2233", "Belgrano 1450", "Centro", "Zona 1 - Centro", 300000),
    ("particular", "Ana Gutiérrez " + PRUEBA, "DNI", "33987456", "consumidor_final", "341 622-4455", "Los Aromos 230", "Barrio Parque", "Zona 2 - Barrios", 0),
    ("constructor", "Hernán Luna — Construcciones " + PRUEBA, "CUIT", _cuit("2025678901"), "monotributo", "341 633-7788", "San Martín 3200", "Centro", "Zona 1 - Centro", 1500000),
    ("constructor", "Obras Norte SRL " + PRUEBA, "CUIT", _cuit("3071234987"), "responsable_inscripto", "341 644-9900", "Ruta 34 km 5", "Zona Norte", "Zona 3 - Rural", 3000000),
    ("empresa", "Constructora Del Valle S.A. " + PRUEBA, "CUIT", _cuit("3070011223"), "responsable_inscripto", "341 655-1122", "Av. Pellegrini 900", "Centro", "Zona 1 - Centro", 5000000),
    ("corralon", "Corralón El Tornillo " + PRUEBA, "CUIT", _cuit("3069988776"), "responsable_inscripto", "341 666-3344", "Mitre 780", "Barrio Sur", "Zona 2 - Barrios", 2000000),
    ("particular", "María Fernández " + PRUEBA, "DNI", "30111222", "consumidor_final", "341 677-5566", "Camino a la Costa s/n", "Zona Rural", "Zona 3 - Rural", 0),
    ("otro", "Municipalidad (Obras Públicas) " + PRUEBA, "CUIT", _cuit("3099911122"), "exento", "341 688-7788", "Palacio Municipal", "Centro", "Zona 4 - Parque industrial", 0),
]


def cargar_demo(dias_historial=45, semilla=2026):
    """Carga datos de prueba y un historial simulado. Idempotente para los maestros."""
    rnd = random.Random(semilla)
    ids = {}
    with transaction():
        for nombre, apellido, user, pwd, rol in USUARIOS_DEMO:
            ids[user] = crear_usuario(nombre, apellido, user, pwd, rol, f"{user}@marehijas.test")
        configuracion.guardar({
            "empresa_nombre": "MAR E HIJAS", "empresa_razon_social": "Mar e Hijas S.R.L. " + PRUEBA,
            "empresa_cuit": _cuit("3071555888"), "empresa_condicion_iva": "responsable_inscripto",
            "empresa_direccion": "Ruta Provincial 18 km 7,5 " + PRUEBA, "empresa_localidad": "Rosario, Santa Fe",
            "empresa_telefono": "0341 555-0000", "empresa_whatsapp": "341 555-0000", "empresa_email": "ventas@marehijas.test",
        })
        zonas = [("Zona 1 - Centro", "Radio urbano hasta 5 km " + PRUEBA, 4, 15000, 0, 0),
                 ("Zona 2 - Barrios", "Barrios periféricos 5 a 12 km " + PRUEBA, 9, 22000, 0, 0),
                 ("Zona 3 - Rural", "Zona rural: fijo + por km " + PRUEBA, 25, 18000, 900, 0),
                 ("Zona 4 - Parque industrial", "Fijo + por m³ transportado " + PRUEBA, 12, 12000, 0, 1500)]
        for z in zonas:
            execute("""INSERT IGNORE INTO zonas_entrega (nombre, descripcion, distancia_km, costo_fijo, costo_por_km,
                       costo_por_unidad) VALUES (%s,%s,%s,%s,%s,%s)""", z)
        execute("UPDATE tipos_vehiculo SET recargo_transporte = 15000 WHERE nombre = 'Camión con acoplado'")
        execute("INSERT IGNORE INTO puntos_venta (numero, descripcion, modalidad) VALUES (1, %s, 'electronico')",
                ("Punto de venta de prueba",))

        for rs, cuit, contacto, tel, obs in PROVEEDORES_DEMO:
            if not query_one("SELECT id FROM proveedores WHERE cuit = %s", (cuit,)):
                execute("""INSERT INTO proveedores (razon_social, cuit, contacto, telefono, localidad, observaciones)
                           VALUES (%s,%s,%s,%s,'Rosario',%s)""", (rs, cuit, contacto, tel, obs))
        prov = [p["id"] for p in query("SELECT id FROM proveedores ORDER BY id")]

        cat = {c["nombre"]: c["id"] for c in query("SELECT id, nombre FROM categorias_materiales")}
        uni = {u["codigo"]: u["id"] for u in query("SELECT id, codigo FROM unidades")}
        prov_por_cat = {"Arena": prov[1], "Piedra partida": prov[0], "Granito": prov[0], "Canto rodado": prov[0]}
        for cod, nombre, categoria, unidad, compra, venta, minimo, convs in MATERIALES_DEMO:
            if query_one("SELECT id FROM materiales WHERE codigo = %s", (cod,)):
                continue
            mid = execute("""INSERT INTO materiales (codigo, nombre, categoria_id, descripcion, unidad_id, precio_compra,
                             precio_venta, stock_minimo, proveedor_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                          (cod, nombre, cat[categoria], f"{PRUEBA} Precios ficticios para probar el sistema.",
                           uni[unidad], compra, venta, minimo, prov_por_cat.get(categoria, prov[2])))
            for o, d, f in convs:
                execute("""INSERT INTO conversiones_unidades (material_id, unidad_origen_id, unidad_destino_id, factor)
                           VALUES (%s,%s,%s,%s)""", (mid, uni[o], uni[d], f))

        zid = {z["nombre"]: z["id"] for z in query("SELECT id, nombre FROM zonas_entrega")}
        for tipo, rs, dt, doc, iva, tel, dir_, loc, zona, limite in CLIENTES_DEMO:
            if query_one("SELECT id FROM clientes WHERE razon_social = %s", (rs,)):
                continue
            cid = execute("""INSERT INTO clientes (tipo, razon_social, documento_tipo, documento, condicion_iva, telefono,
                             whatsapp, direccion, localidad, zona_id, referencia_ubicacion)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                          (tipo, rs, dt, doc, iva, tel, tel, dir_, loc, zid.get(zona),
                           "Portón verde, tocar bocina" if dir_ else None))
            execute("INSERT INTO cuentas_corrientes (cliente_id, limite_credito) VALUES (%s, %s)", (cid, limite))

        tv = {t["nombre"]: t["id"] for t in query("SELECT id, nombre FROM tipos_vehiculo")}
        choferes = [("Carlos", "Gómez", "25111222", "341 600-1111", "E1", 400, ids["chofer1"]),
                    ("Raúl", "Benítez", "27333444", "341 600-2222", "E1", 20, ids["chofer2"]),
                    ("Miguel", "Sosa", "31555666", "341 600-3333", "B1", 200, None)]
        for nom, ape, dni, tel, cat_l, dias_vto, uid in choferes:
            if not query_one("SELECT id FROM choferes WHERE dni = %s", (dni,)):
                execute("""INSERT INTO choferes (nombre, apellido, dni, telefono, licencia_numero, licencia_categoria,
                           licencia_vencimiento, usuario_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (nom, ape, dni, tel, f"LIC-{dni}", cat_l, hoy() + timedelta(days=dias_vto), uid))
        ch = {c["dni"]: c["id"] for c in query("SELECT id, dni FROM choferes")}
        vehiculos = [("AB123CD", "Camión volcador", "Mercedes-Benz", "Atego 1726", 2016, "6", "m3", ch["25111222"]),
                     ("AC456EF", "Camión con acoplado", "Iveco", "Tector 170E28", 2019, "14", "m3", ch["27333444"]),
                     ("AA789GH", "Camioneta", "Toyota", "Hilux", 2020, "1", "tonelada", ch["31555666"])]
        for pat, tipo, marca, modelo, anio, cap, un, cho in vehiculos:
            if not query_one("SELECT id FROM vehiculos WHERE patente = %s", (pat,)):
                execute("""INSERT INTO vehiculos (patente, tipo_vehiculo_id, marca, modelo, anio, capacidad,
                           unidad_capacidad_id, chofer_id, observaciones) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (pat, tv[tipo], marca, modelo, anio, cap, uni[un], cho, PRUEBA))

    if query_one("SELECT id FROM ventas LIMIT 1"):
        return  # el historial ya existe
    _historial(rnd, ids, dias_historial)


# -----------------------------------------------------------------------------
def _usuario(uid):
    login_user(usuario_model.cargar(uid))
    return uid


def _historial(rnd, ids, dias):
    mats = {m["codigo"]: m for m in query("SELECT * FROM materiales")}
    uni = {u["codigo"]: u["id"] for u in query("SELECT id, codigo FROM unidades")}
    clientes = query("SELECT c.*, cc.limite_credito FROM clientes c JOIN cuentas_corrientes cc ON cc.cliente_id = c.id")
    prov = [p["id"] for p in query("SELECT id FROM proveedores ORDER BY id")]
    mp = {m["codigo"]: m["id"] for m in query("SELECT id, codigo FROM metodos_pago")}
    gcat = {g["nombre"]: g["id"] for g in query("SELECT id, nombre FROM categorias_gastos")}
    veh = {v["patente"]: v for v in query("SELECT * FROM vehiculos")}
    cho = {c["dni"]: c["id"] for c in query("SELECT id, dni FROM choferes")}
    zonas = {z["id"]: z for z in catalogos.listar("zonas_entrega")}
    hoy_ = hoy()
    inicio = hoy_ - timedelta(days=dias)

    def en(d, h, m=0):
        fijar_ahora(datetime.combine(d, time(h, m)))

    # Opciones de venta: (código material, unidad, rango cantidad)
    opciones = [("ARE-GR", "m3", (1, 6)), ("ARE-GR", "medio_m3", (1, 3)), ("ARE-FI", "m3", (1, 4)),
                ("RIP-01", "m3", (1, 6)), ("PP-620", "tonelada", (1, 6)), ("PP-1030", "tonelada", (1, 5)),
                ("CAN-01", "tonelada", (1, 4)), ("GRA-01", "tonelada", (1, 3)), ("TOS-01", "m3", (2, 6)),
                ("TIE-NE", "m3", (1, 5)), ("CEM-50", "bolsa", (5, 40)), ("ARE-GR", "viaje", (1, 1))]
    pesos = [18, 8, 9, 12, 9, 6, 4, 3, 6, 6, 10, 3]
    metodos = [("efectivo", 40), ("transferencia", 25), ("debito", 8), ("credito", 5), ("mercado_pago", 10),
               ("cuenta_corriente", 12)]

    # Stock inicial (entradas a proveedores, a cuenta)
    _usuario(ids["admin"])
    en(inicio - timedelta(days=1), 8)
    caja_service.abrir(50000, ids["admin"], "Caja inicial " + PRUEBA)
    cargas = {"ARE-GR": 260, "ARE-FI": 150, "RIP-01": 200, "PP-620": 180, "PP-1030": 150, "CAN-01": 120,
              "GRA-01": 80, "TOS-01": 200, "TIE-NE": 150, "CEM-50": 400}
    for i, (cod, cant) in enumerate(cargas.items()):
        m = mats[cod]
        en(inicio - timedelta(days=1), 9, i * 3)
        stock_service.registrar_entrada({
            "material_id": m["id"], "cantidad": Decimal(cant), "unidad_id": m["unidad_id"],
            "proveedor_id": m["proveedor_id"], "remito_numero": f"R-0001-{1000 + i}",
            "vehiculo_descripcion": "Camión del proveedor", "costo_total": Decimal(cant) * Decimal(m["precio_compra"]),
            "condicion": "cuenta", "observaciones": "Stock inicial " + PRUEBA,
        }, ids["admin"])
    en(inicio - timedelta(days=1), 18)
    caja_service.cerrar(caja_service.resumen(caja_service.caja_abierta())["saldo_esperado"], ids["admin"])

    dia = inicio
    while dia <= hoy_:
        es_hoy = dia == hoy_
        if dia.weekday() == 6:  # domingo cerrado
            dia += timedelta(days=1)
            continue
        vendedor = ids["vendedor"] if rnd.random() < 0.65 else ids["admin"]
        _usuario(ids["admin"])
        en(dia, 7, 45)
        caja_service.abrir(Decimal(rnd.choice([20000, 30000, 40000])), ids["admin"])

        # Reposición semanal
        if dia.weekday() == 1:
            for j, cod in enumerate(rnd.sample(list(cargas), 4)):
                m = mats[cod]
                cant = Decimal(rnd.choice([30, 40, 60])) if m["unidad_id"] != uni["bolsa"] else Decimal(200)
                en(dia, 8, 10 + j)
                stock_service.registrar_entrada({
                    "material_id": m["id"], "cantidad": cant, "unidad_id": m["unidad_id"],
                    "proveedor_id": m["proveedor_id"], "remito_numero": f"R-{dia.strftime('%m%d')}-{j}",
                    "vehiculo_descripcion": "Batea del proveedor", "costo_total": cant * Decimal(m["precio_compra"]),
                    "condicion": "cuenta", "actualizar_precio": False,
                }, ids["admin"])

        _usuario(vendedor)
        n_ventas = rnd.randint(2, 6) if not es_hoy else 3
        for k in range(n_ventas):
            en(dia, rnd.randint(8, 16), rnd.randint(0, 59))
            cliente = rnd.choice(clientes[1:]) if rnd.random() < 0.8 else clientes[0]
            items = []
            for _ in range(1 if rnd.random() < 0.7 else 2):
                cod, un, (a, b) = rnd.choices(opciones, pesos)[0]
                if any(i["material_id"] == mats[cod]["id"] for i in items):
                    continue
                cant = rnd.randint(a, b)
                items.append({"material_id": mats[cod]["id"], "unidad_id": uni[un], "cantidad": str(cant),
                              "precio_unitario": None, "descuento_pct": "5" if cliente["tipo"] == "corralon" else "0"})
            envio = cliente["zona_id"] and rnd.random() < 0.6
            metodo = rnd.choices([m for m, _ in metodos], [w for _, w in metodos])[0]
            if metodo == "cuenta_corriente" and cliente["documento"] is None:
                metodo = "efectivo"
            costo_envio = 0
            if envio:
                z = zonas[cliente["zona_id"]]
                costo_envio = Decimal(z["costo_fijo"]) + Decimal(z["costo_por_km"]) * Decimal(z["distancia_km"])
            datos = {"cliente_id": cliente["id"], "tipo_entrega": "envio" if envio else "retiro",
                     "zona_id": cliente["zona_id"] if envio else None,
                     "direccion_entrega": f"{cliente['direccion']}, {cliente['localidad']}" if envio else None,
                     "costo_envio": costo_envio, "metodo_pago_id": mp[metodo], "crear_entrega": 1,
                     "fecha_entrega": dia, "horario_entrega": rnd.choice(["8 a 12 h", "13 a 17 h", None])}
            if metodo not in ("cuenta_corriente",) and rnd.random() < 0.12:
                datos["monto_pagado"] = None  # pago total
            try:
                venta_id = venta_service.registrar(datos, items, vendedor)
            except NegocioError:
                continue
            if envio:
                _usuario(ids["admin"])
                e = query_one("SELECT id FROM entregas WHERE venta_id = %s", (venta_id,))
                patente = "AC456EF" if rnd.random() < 0.3 else "AB123CD"
                v = veh[patente]
                try:
                    entrega_service.asignar(e["id"], v["chofer_id"], v["id"], dia, datos["horario_entrega"], None,
                                            ids["admin"])
                except NegocioError:
                    v = veh["AC456EF"]
                    try:
                        entrega_service.asignar(e["id"], v["chofer_id"], v["id"], dia, None, None, ids["admin"])
                    except NegocioError:
                        _usuario(vendedor)
                        continue
                if not es_hoy or k == 0:
                    chofer_uid = ids["chofer1"] if v["chofer_id"] == cho["25111222"] else ids["chofer2"]
                    _usuario(chofer_uid)
                    en(dia, 17, 0)
                    usuario = usuario_model.cargar(chofer_uid)
                    try:
                        entrega_service.cambiar_estado(e["id"], "en_camino", usuario)
                        if not es_hoy:
                            en(dia, 17, 40)
                            entrega_service.cambiar_estado(e["id"], "entregada", usuario,
                                                           recibido_por=rnd.choice(["El cliente", "Encargado de obra", "Vecino"]))
                    except NegocioError:
                        pass
                _usuario(vendedor)

        # Cobros de cuenta corriente
        if rnd.random() < 0.35:
            _usuario(ids["admin"])
            deudor = query_one("""SELECT cliente_id, saldo FROM cuentas_corrientes WHERE saldo > 0
                                  ORDER BY RAND(%s) LIMIT 1""", (rnd.randint(1, 99999),))
            if deudor:
                en(dia, 16, 30)
                monto = (Decimal(deudor["saldo"]) * Decimal(rnd.choice(["0.5", "1"]))).quantize(Decimal("1"))
                if monto > 0:
                    cuenta_corriente_service.registrar_pago(deudor["cliente_id"], monto,
                                                            mp[rnd.choice(["efectivo", "transferencia"])], ids["admin"],
                                                            observaciones=PRUEBA)
        # Gastos
        _usuario(ids["admin"])
        if dia.weekday() in (0, 3):
            en(dia, 12, 15)
            gasto_service.registrar({"categoria_id": gcat["Combustible"], "descripcion": "Gasoil camiones " + PRUEBA,
                                     "monto": Decimal(rnd.choice([85000, 110000, 95000])), "metodo_pago_id": mp["debito"],
                                     "vehiculo_id": veh["AB123CD"]["id"], "fecha": dia}, ids["admin"])
        if dia.day == 5 and not es_hoy:
            en(dia, 11)
            gasto_service.registrar({"categoria_id": gcat["Sueldos"], "descripcion": "Sueldos quincena " + PRUEBA,
                                     "monto": Decimal(950000), "metodo_pago_id": mp["transferencia"], "fecha": dia},
                                    ids["admin"])
        if dia.day in (10, 25) and not es_hoy:
            en(dia, 10)
            gasto_service.registrar({"categoria_id": gcat["Servicios"], "descripcion": "Luz y teléfono " + PRUEBA,
                                     "monto": Decimal(68000), "metodo_pago_id": mp["transferencia"], "fecha": dia},
                                    ids["admin"])
        if dia.weekday() == 4 and not es_hoy and rnd.random() < 0.5:
            en(dia, 15)
            proveedor_service.registrar_pago({"proveedor_id": rnd.choice(prov), "monto": Decimal(rnd.choice([400000, 600000])),
                                              "metodo_pago_id": mp["transferencia"], "referencia": "TRF " + PRUEBA},
                                             ids["admin"])

        if not es_hoy:
            en(dia, 18, 30)
            esperado = caja_service.resumen(caja_service.caja_abierta())["saldo_esperado"]
            diferencia = Decimal(rnd.choice([0, 0, 0, 0, -500, 200]))
            caja_service.cerrar(esperado + diferencia, ids["admin"], "Cierre diario " + PRUEBA)
        dia += timedelta(days=1)

    # Presupuestos y pedidos abiertos
    _usuario(ids["vendedor"])
    en(hoy_, 10, 5)
    c = [x for x in clientes if x["tipo"] == "constructor"][0]
    presupuesto_service.guardar({"cliente_id": c["id"], "tipo_entrega": "envio", "zona_id": c["zona_id"],
                                 "direccion_entrega": c["direccion"], "costo_envio": 15000,
                                 "observaciones": "Obra calle San Martín " + PRUEBA},
                                [{"material_id": mats["ARE-GR"]["id"], "unidad_id": uni["m3"], "cantidad": "12"},
                                 {"material_id": mats["PP-620"]["id"], "unidad_id": uni["tonelada"], "cantidad": "8"},
                                 {"material_id": mats["CEM-50"]["id"], "unidad_id": uni["bolsa"], "cantidad": "60"}],
                                ids["vendedor"])
    en(hoy_ - timedelta(days=3), 11)
    presupuesto_service.guardar({"cliente_id": clientes[2]["id"], "tipo_entrega": "retiro"},
                                [{"material_id": mats["TIE-NE"]["id"], "unidad_id": uni["m3"], "cantidad": "3"}],
                                ids["vendedor"])
    _usuario(ids["admin"])
    en(hoy_, 10, 30)
    obras = [x for x in clientes if x["tipo"] == "empresa"][0]
    pid = pedido_service.guardar({"cliente_id": obras["id"], "tipo_entrega": "envio", "zona_id": obras["zona_id"],
                                  "direccion_entrega": obras["direccion"], "localidad": obras["localidad"],
                                  "fecha_solicitada": hoy_ + timedelta(days=1), "horario": "7 a 11 h",
                                  "costo_envio": 30000, "observaciones": "Descargar en obrador " + PRUEBA},
                                 [{"material_id": mats["ARE-GR"]["id"], "unidad_id": uni["m3"], "cantidad": "18"},
                                  {"material_id": mats["RIP-01"]["id"], "unidad_id": uni["m3"], "cantidad": "6"}],
                                 ids["admin"])
    pedido_service.cambiar_estado(pid, "confirmado", ids["admin"])
    pedido_service.guardar({"cliente_id": clientes[1]["id"], "tipo_entrega": "retiro",
                            "fecha_solicitada": hoy_, "horario": "Por la tarde"},
                           [{"material_id": mats["CEM-50"]["id"], "unidad_id": uni["bolsa"], "cantidad": "10"}],
                           ids["admin"])
    fijar_ahora(None)
