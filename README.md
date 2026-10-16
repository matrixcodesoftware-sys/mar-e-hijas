# MAR E HIJAS — Sistema de Gestión de Áridos

Aplicación web para administrar un galpón de venta y distribución de áridos:
ventas por m³, tonelada, medio metro, viaje o bolsa; pedidos y entregas con
camiones; stock a granel; clientes con cuenta corriente; proveedores; caja;
gastos; reportes e historial de operaciones.

**Tecnologías:** Python 3.10+ · Flask 3 · MySQL 8 / MariaDB 10.6+ · HTML5 · CSS3 · JavaScript · Chart.js (incluido, funciona sin internet) · ReportLab (PDF).

El diseño completo (arquitectura, modelo entidad‑relación y flujos de venta, pedido/entrega, stock y cuenta corriente) está en **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

---

## 1. Instalación en Windows

### 1.1 MySQL
Instalá **MySQL 8** (MySQL Installer) o **XAMPP** (trae MariaDB). Anotá el usuario y la contraseña de `root`,
o creá un usuario propio:

```sql
CREATE USER 'marehijas'@'localhost' IDENTIFIED BY 'una-clave-segura';
GRANT ALL PRIVILEGES ON mar_e_hijas.* TO 'marehijas'@'localhost';
```

### 1.2 Proyecto (PowerShell, dentro de la carpeta del proyecto)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Editá `.env`: completá `DB_USER`, `DB_PASSWORD` y generá una `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

> Si `Activate.ps1` da error de política de ejecución: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
> Si no tenés `python` en el PATH, usá `py`.

### 1.3 Base de datos

```powershell
python manage.py init-db        # crea la base, las 38 tablas y los datos base
python manage.py seed-demo      # (opcional) DATOS DE PRUEBA + ~45 días de historial
python manage.py crear-usuario  # (uso real) crea el usuario Dueño
```

También podés cargar `database/schema.sql` a mano desde MySQL Workbench / phpMyAdmin y después correr `init-db`
(no toca tablas existentes).

### 1.4 Ejecutar

```powershell
python run.py
```

Abrí **http://localhost:5000**.

Mac / Linux: igual, con `source venv/bin/activate` y `cp .env.example .env`.

## 2. Usuarios de prueba (sólo con `seed-demo`)

| Usuario    | Contraseña    | Rol                  |
|------------|---------------|----------------------|
| `dueno`    | `Dueno2026!`  | Dueño (todo)         |
| `admin`    | `Admin2026!`  | Administrador        |
| `vendedor` | `Vende2026!`  | Vendedor             |
| `chofer1`  | `Chofer2026!` | Chofer (Carlos Gómez, camión AB123CD) |
| `chofer2`  | `Chofer2026!` | Chofer (Raúl Benítez, camión AC456EF) |

Todos los precios, clientes, proveedores y CUIT de la demo son **ficticios** y están marcados como
`(DATO DE PRUEBA)`. Para empezar a usar el sistema en serio, recreá la base sin `seed-demo`.

**Probá el chofer desde el celular:** con la PC y el celular en la misma red, ejecutá
`set HOST=0.0.0.0` y luego `python run.py`, y entrá desde el celular a `http://IP-DE-LA-PC:5000`.

## 3. Qué hace cada módulo

| Módulo | Resumen |
|---|---|
| Dashboard | Ventas del día/mes, ganancia estimada, caja, pedidos, entregas de hoy, deudores, stock, más vendido, 4 gráficos y accesos rápidos. |
| Ventas | Varios materiales por venta, cada uno en su unidad (m³, t, ½ m³, viaje, bolsa…), descuento por línea y general, flete por zona, cobro total/parcial con el resto a cuenta corriente, comprobante PDF, anulación con reversión completa. |
| Presupuestos | Imprimible en PDF, envío por WhatsApp, estados, vencimiento automático, **Convertir presupuesto en venta** (reutiliza todos los datos) o en pedido. |
| Pedidos | 7 estados, fecha y horario, camión/chofer sugerido, programación de **viajes** con control de capacidad, “Generar venta”. |
| Entregas | Logística diaria, asignación de chofer y camión, hoja de ruta imprimible, vista móvil del chofer con **ENTREGA REALIZADA**. |
| Materiales | ABM, precios, unidad de venta, conversiones propias del material, precio sugerido por unidad. |
| Stock | Situación actual, entradas (proveedor, remito, camión, costo, contado o a cuenta), ajustes por conteo físico, historial de movimientos. |
| Clientes | ABM, ficha con historial de compras, pedidos, presupuestos, pagos y **cuenta corriente** (Debe/Haber/Saldo, pagos, deudas, créditos, límite, resumen imprimible y PDF). |
| Proveedores | ABM, cuenta del proveedor, compras, pagos, materiales suministrados. |
| Camiones / Choferes | ABM, capacidad y unidad de capacidad, chofer asignado, vencimiento de licencias con alertas. |
| Caja | Apertura, ingresos/retiros/ajustes, cierre con arqueo (efectivo esperado vs. declarado), historial de cierres. |
| Gastos | Por categoría, vehículo y proveedor; egreso automático de caja; anulación. |
| Reportes | Ventas, materiales, clientes y entregas con filtros y gráficos; exportación **CSV** y **PDF**. |
| Usuarios | ABM de usuarios y edición de permisos por rol. |
| Configuración | Empresa y reglas, zonas de entrega, unidades, conversiones, tipos de material y vehículo, categorías de gastos, métodos de pago, facturación ARCA. |
| Historial | Quién hizo qué, cuándo y sobre qué registro (“Sofía Medina creó la venta V-000123…”). |

## 4. Estructura

```
mar_e_hijas/
├── app/
│   ├── __init__.py          fábrica de la app, menú, errores, cabeceras de seguridad
│   ├── config.py            configuración desde .env
│   ├── extensions.py        Flask-Login, CSRF
│   ├── database.py          conexión PyMySQL, transacciones
│   ├── seed.py              datos base y datos de prueba
│   ├── models/              acceso a datos (SQL parametrizado)
│   ├── services/            reglas de negocio y transacciones
│   │   └── facturacion/     preparado para ARCA (sin integración ficticia)
│   ├── routes/              controladores (blueprints)
│   ├── utils/               decoradores, validación, fechas, formato, paginación
│   ├── templates/           vistas Jinja2 por módulo
│   └── static/              css, js (Chart.js incluido), img
├── database/schema.sql      esquema MySQL completo
├── docs/ARQUITECTURA.md     análisis y diseño
├── tests/                   pruebas de integración (pytest)
├── manage.py                comandos: init-db, seed-demo, crear-usuario, reset-demo
├── run.py                   servidor (desarrollo / producción con waitress)
├── requirements.txt
└── .env.example
```

## 5. Seguridad

Contraseñas con hash (werkzeug), sesiones Flask‑Login con cookies `HttpOnly`/`SameSite`, bloqueo tras 5
intentos fallidos, CSRF en todos los formularios y llamadas `fetch`, permisos por decorador
`@permiso_requerido`, consultas parametrizadas, autoescape contra XSS, Content‑Security‑Policy,
validación en servidor de todos los formularios, errores centralizados y secretos en `.env`.

## 6. Pruebas

```powershell
pip install pytest
pytest -q
```

Crean y usan una base aparte (`mar_e_hijas_test`) y recorren el flujo completo
cliente → presupuesto → pedido → viajes → venta → stock → entrega del chofer → pago → caja → reportes,
además de permisos por rol, CSRF, PDFs y exportaciones.

## 7. Producción

1. `FLASK_ENV=production`, `SECRET_KEY` larga y aleatoria, usuario MySQL con permisos sólo sobre la base.
2. Servir con HTTPS detrás de un proxy (Nginx/IIS/Caddy) y poner `SESSION_COOKIE_SECURE=1`.
3. Ejecutar `python run.py --prod` (waitress, Windows/Linux) o `gunicorn -w 3 -b 127.0.0.1:8000 "run:app"` (Linux).
4. Programar backups diarios: `mysqldump mar_e_hijas > backup.sql`.

## 8. Facturación electrónica (ARCA)

El sistema ya guarda tipo de comprobante, punto de venta, número, CUIT, condición IVA, CAE y vencimiento,
y prepara cada factura como **borrador** desde la venta (Factura A/B/C según condiciones de IVA).
Para emitir: implementar `ProveedorFacturacion` para WSAA + WSFEv1 en `app/services/facturacion/`,
registrarlo en `proveedores.py` y configurar `FACTURACION_PROVEEDOR=arca` y el certificado en `.env`.
Ver `docs/ARQUITECTURA.md` §12.
