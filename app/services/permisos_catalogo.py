"""Catálogo de permisos del sistema y permisos por defecto de cada rol.

Se usa al inicializar la base (manage.py seed). Después, el dueño puede
modificar los permisos de cada rol desde Usuarios → Roles y permisos.
"""

PERMISOS = [
    # codigo, modulo, descripcion
    ("dashboard.ver", "dashboard", "Ver el tablero principal"),
    ("dashboard.finanzas", "dashboard", "Ver ganancias, caja y facturación en el tablero"),
    ("ventas.ver", "ventas", "Consultar ventas"),
    ("ventas.crear", "ventas", "Registrar ventas"),
    ("ventas.anular", "ventas", "Anular ventas"),
    ("presupuestos.ver", "presupuestos", "Consultar presupuestos"),
    ("presupuestos.gestionar", "presupuestos", "Crear y modificar presupuestos"),
    ("pedidos.ver", "pedidos", "Consultar pedidos"),
    ("pedidos.gestionar", "pedidos", "Crear, modificar y cambiar estado de pedidos"),
    ("entregas.ver", "entregas", "Consultar todas las entregas"),
    ("entregas.gestionar", "entregas", "Programar y asignar entregas"),
    ("entregas.propias", "entregas", "Ver y actualizar las entregas asignadas (chofer)"),
    ("materiales.ver", "materiales", "Consultar materiales y precios"),
    ("materiales.gestionar", "materiales", "Alta, baja y modificación de materiales y precios"),
    ("stock.ver", "stock", "Consultar stock y movimientos"),
    ("stock.gestionar", "stock", "Registrar entradas y ajustes de stock"),
    ("clientes.ver", "clientes", "Consultar clientes"),
    ("clientes.gestionar", "clientes", "Alta y modificación de clientes"),
    ("cuentas.ver", "cuentas", "Consultar cuentas corrientes"),
    ("cuentas.gestionar", "cuentas", "Registrar pagos, deudas y créditos en cuenta corriente"),
    ("proveedores.ver", "proveedores", "Consultar proveedores"),
    ("proveedores.gestionar", "proveedores", "Gestionar proveedores y pagos a proveedores"),
    ("vehiculos.ver", "vehiculos", "Consultar camiones y vehículos"),
    ("vehiculos.gestionar", "vehiculos", "Gestionar camiones y vehículos"),
    ("choferes.ver", "choferes", "Consultar choferes"),
    ("choferes.gestionar", "choferes", "Gestionar choferes"),
    ("caja.ver", "caja", "Consultar caja e historial de cierres"),
    ("caja.operar", "caja", "Abrir, cerrar y registrar movimientos de caja"),
    ("gastos.ver", "gastos", "Consultar gastos"),
    ("gastos.gestionar", "gastos", "Registrar y anular gastos"),
    ("reportes.ver", "reportes", "Ver y exportar reportes"),
    ("historial.ver", "historial", "Ver historial de operaciones"),
    ("parametros.gestionar", "configuracion", "Unidades, conversiones, zonas, categorías y métodos de pago"),
    ("configuracion.gestionar", "configuracion", "Datos de la empresa, fiscales y reglas del sistema"),
    ("facturacion.gestionar", "configuracion", "Facturación electrónica y puntos de venta"),
    ("usuarios.gestionar", "usuarios", "Usuarios, roles y permisos"),
]

ROLES = [
    ("duenio", "Dueño", "Acceso completo al sistema"),
    ("admin", "Administrador", "Gestión, ventas, stock, clientes, proveedores y reportes"),
    ("vendedor", "Vendedor", "Ventas, presupuestos, clientes y consultas"),
    ("chofer", "Repartidor / Chofer", "Entregas asignadas desde el celular"),
]

_TODOS = [p[0] for p in PERMISOS]

PERMISOS_POR_ROL = {
    "duenio": _TODOS,
    "admin": [p for p in _TODOS if p not in ("usuarios.gestionar", "configuracion.gestionar", "facturacion.gestionar")],
    "vendedor": [
        "dashboard.ver", "ventas.ver", "ventas.crear", "presupuestos.ver", "presupuestos.gestionar",
        "pedidos.ver", "clientes.ver", "clientes.gestionar", "cuentas.ver", "materiales.ver", "stock.ver",
    ],
    "chofer": ["entregas.propias"],
}
