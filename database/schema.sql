-- =============================================================================
--  MAR E HIJAS — Sistema de Gestión de Áridos
--  Esquema de base de datos MySQL 8.0+ / MariaDB 10.6+
--  Motor InnoDB, charset utf8mb4, diseño normalizado (3FN salvo saldos cacheados
--  documentados: materiales.stock_actual, cuentas_corrientes.saldo,
--  proveedores.saldo_cuenta — se actualizan SIEMPRE dentro de la misma
--  transacción que el movimiento que los origina, con bloqueo FOR UPDATE).
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS comprobantes;
DROP TABLE IF EXISTS puntos_venta;
DROP TABLE IF EXISTS tipos_comprobante;
DROP TABLE IF EXISTS historial_operaciones;
DROP TABLE IF EXISTS movimientos_caja;
DROP TABLE IF EXISTS gastos;
DROP TABLE IF EXISTS categorias_gastos;
DROP TABLE IF EXISTS pagos_proveedores;
DROP TABLE IF EXISTS movimientos_cuenta_proveedor;
DROP TABLE IF EXISTS movimientos_cuenta_corriente;
DROP TABLE IF EXISTS cuentas_corrientes;
DROP TABLE IF EXISTS pagos;
DROP TABLE IF EXISTS detalle_entregas;
DROP TABLE IF EXISTS entregas;
DROP TABLE IF EXISTS detalle_pedidos;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS detalle_presupuestos;
DROP TABLE IF EXISTS presupuestos;
DROP TABLE IF EXISTS movimientos_stock;
DROP TABLE IF EXISTS detalle_ventas;
DROP TABLE IF EXISTS ventas;
DROP TABLE IF EXISTS cajas;
DROP TABLE IF EXISTS metodos_pago;
DROP TABLE IF EXISTS vehiculos;
DROP TABLE IF EXISTS tipos_vehiculo;
DROP TABLE IF EXISTS choferes;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS zonas_entrega;
DROP TABLE IF EXISTS conversiones_unidades;
DROP TABLE IF EXISTS materiales;
DROP TABLE IF EXISTS unidades;
DROP TABLE IF EXISTS categorias_materiales;
DROP TABLE IF EXISTS proveedores;
DROP TABLE IF EXISTS configuracion;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS roles_permisos;
DROP TABLE IF EXISTS permisos;
DROP TABLE IF EXISTS roles;

SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------------------------
-- SEGURIDAD: roles, permisos, usuarios
-- -----------------------------------------------------------------------------
CREATE TABLE roles (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo        VARCHAR(30)  NOT NULL,
    nombre        VARCHAR(60)  NOT NULL,
    descripcion   VARCHAR(255) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_roles_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE permisos (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo        VARCHAR(60)  NOT NULL,
    modulo        VARCHAR(40)  NOT NULL,
    descripcion   VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_permisos_codigo (codigo),
    KEY ix_permisos_modulo (modulo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE roles_permisos (
    rol_id        INT UNSIGNED NOT NULL,
    permiso_id    INT UNSIGNED NOT NULL,
    PRIMARY KEY (rol_id, permiso_id),
    CONSTRAINT fk_rp_rol     FOREIGN KEY (rol_id)     REFERENCES roles(id)    ON DELETE CASCADE,
    CONSTRAINT fk_rp_permiso FOREIGN KEY (permiso_id) REFERENCES permisos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE usuarios (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre          VARCHAR(80)  NOT NULL,
    apellido        VARCHAR(80)  NOT NULL,
    username        VARCHAR(40)  NOT NULL,
    email           VARCHAR(120) NULL,
    telefono        VARCHAR(40)  NULL,
    password_hash   VARCHAR(255) NOT NULL,
    rol_id          INT UNSIGNED NOT NULL,
    activo          TINYINT(1)   NOT NULL DEFAULT 1,
    ultimo_acceso   DATETIME     NULL,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuarios_username (username),
    UNIQUE KEY uq_usuarios_email (email),
    KEY ix_usuarios_rol (rol_id),
    CONSTRAINT fk_usuarios_rol FOREIGN KEY (rol_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Parámetros generales (datos de la empresa, datos fiscales, alertas…)
CREATE TABLE configuracion (
    clave         VARCHAR(60)  NOT NULL,
    valor         TEXT         NULL,
    descripcion   VARCHAR(255) NULL,
    PRIMARY KEY (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PROVEEDORES
-- -----------------------------------------------------------------------------
CREATE TABLE proveedores (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    razon_social    VARCHAR(150) NOT NULL,
    cuit            VARCHAR(13)  NULL,
    telefono        VARCHAR(40)  NULL,
    email           VARCHAR(120) NULL,
    direccion       VARCHAR(200) NULL,
    localidad       VARCHAR(100) NULL,
    contacto        VARCHAR(120) NULL,
    observaciones   TEXT         NULL,
    saldo_cuenta    DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- lo que le debemos (cache)
    activo          TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_proveedores_cuit (cuit),
    KEY ix_proveedores_razon (razon_social)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- MATERIALES, UNIDADES Y CONVERSIONES
-- -----------------------------------------------------------------------------
CREATE TABLE categorias_materiales (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(60)  NOT NULL,
    descripcion   VARCHAR(255) NULL,
    activo        TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_catmat_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE unidades (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo        VARCHAR(20)  NOT NULL,
    nombre        VARCHAR(60)  NOT NULL,
    abreviatura   VARCHAR(12)  NOT NULL,
    magnitud      ENUM('masa','volumen','conteo','viaje','otra') NOT NULL,
    activo        TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_unidades_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE materiales (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo          VARCHAR(20)  NOT NULL,
    nombre          VARCHAR(120) NOT NULL,
    categoria_id    INT UNSIGNED NOT NULL,
    descripcion     TEXT         NULL,
    unidad_id       INT UNSIGNED NOT NULL,             -- unidad de venta y de stock
    precio_compra   DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- por unidad_id
    precio_venta    DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- por unidad_id
    stock_actual    DECIMAL(14,3) NOT NULL DEFAULT 0.000, -- cache de movimientos_stock
    stock_minimo    DECIMAL(14,3) NOT NULL DEFAULT 0.000,
    proveedor_id    INT UNSIGNED NULL,
    activo          TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en  DATETIME     NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_materiales_codigo (codigo),
    KEY ix_materiales_nombre (nombre),
    KEY ix_materiales_categoria (categoria_id),
    KEY ix_materiales_proveedor (proveedor_id),
    CONSTRAINT fk_mat_categoria FOREIGN KEY (categoria_id) REFERENCES categorias_materiales(id),
    CONSTRAINT fk_mat_unidad    FOREIGN KEY (unidad_id)    REFERENCES unidades(id),
    CONSTRAINT fk_mat_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id) ON DELETE SET NULL,
    CONSTRAINT ck_mat_precios   CHECK (precio_compra >= 0 AND precio_venta >= 0),
    CONSTRAINT ck_mat_stockmin  CHECK (stock_minimo >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1 [unidad_origen] = factor [unidad_destino].
-- material_id NULL => conversión general (ej.: 1 m³ = 2 medio m³).
-- material_id con valor => específica de ese material (ej.: arena: 1 t = 0,625 m³).
CREATE TABLE conversiones_unidades (
    id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
    material_id        INT UNSIGNED NULL,
    unidad_origen_id   INT UNSIGNED NOT NULL,
    unidad_destino_id  INT UNSIGNED NOT NULL,
    factor             DECIMAL(14,6) NOT NULL,
    observaciones      VARCHAR(255) NULL,
    material_key       INT UNSIGNED AS (IFNULL(material_id, 0)) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uq_conv (material_key, unidad_origen_id, unidad_destino_id),
    KEY ix_conv_material (material_id),
    CONSTRAINT fk_conv_material FOREIGN KEY (material_id)       REFERENCES materiales(id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_origen   FOREIGN KEY (unidad_origen_id)  REFERENCES unidades(id),
    CONSTRAINT fk_conv_destino  FOREIGN KEY (unidad_destino_id) REFERENCES unidades(id),
    CONSTRAINT ck_conv_factor   CHECK (factor > 0),
    CONSTRAINT ck_conv_distintas CHECK (unidad_origen_id <> unidad_destino_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- TRANSPORTE: zonas, tipos de vehículo, vehículos, choferes
-- -----------------------------------------------------------------------------
CREATE TABLE zonas_entrega (
    id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre            VARCHAR(80)  NOT NULL,
    descripcion       VARCHAR(255) NULL,
    distancia_km      DECIMAL(8,2) NOT NULL DEFAULT 0.00,  -- distancia de referencia
    costo_fijo        DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    costo_por_km      DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    costo_por_unidad  DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- por unidad de carga (m³/t)
    activo            TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_zonas_nombre (nombre),
    CONSTRAINT ck_zonas_costos CHECK (costo_fijo >= 0 AND costo_por_km >= 0 AND costo_por_unidad >= 0 AND distancia_km >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tipos_vehiculo (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre              VARCHAR(60)  NOT NULL,
    recargo_transporte  DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    activo              TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tipveh_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE choferes (
    id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre                VARCHAR(80)  NOT NULL,
    apellido              VARCHAR(80)  NOT NULL,
    dni                   VARCHAR(15)  NOT NULL,
    telefono              VARCHAR(40)  NULL,
    licencia_numero       VARCHAR(40)  NULL,
    licencia_categoria    VARCHAR(20)  NULL,
    licencia_vencimiento  DATE         NULL,
    usuario_id            INT UNSIGNED NULL,   -- usuario con rol chofer para la vista móvil
    estado                ENUM('activo','inactivo','licencia') NOT NULL DEFAULT 'activo',
    observaciones         TEXT NULL,
    creado_en             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_choferes_dni (dni),
    UNIQUE KEY uq_choferes_usuario (usuario_id),
    CONSTRAINT fk_choferes_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE vehiculos (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    patente             VARCHAR(10)  NOT NULL,
    tipo_vehiculo_id    INT UNSIGNED NOT NULL,
    marca               VARCHAR(60)  NULL,
    modelo              VARCHAR(60)  NULL,
    anio                SMALLINT UNSIGNED NULL,
    capacidad           DECIMAL(10,3) NOT NULL,
    unidad_capacidad_id INT UNSIGNED NOT NULL,
    estado              ENUM('disponible','en_uso','mantenimiento','inactivo') NOT NULL DEFAULT 'disponible',
    chofer_id           INT UNSIGNED NULL,
    observaciones       TEXT NULL,
    creado_en           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_vehiculos_patente (patente),
    KEY ix_vehiculos_chofer (chofer_id),
    CONSTRAINT fk_veh_tipo    FOREIGN KEY (tipo_vehiculo_id)    REFERENCES tipos_vehiculo(id),
    CONSTRAINT fk_veh_unidad  FOREIGN KEY (unidad_capacidad_id) REFERENCES unidades(id),
    CONSTRAINT fk_veh_chofer  FOREIGN KEY (chofer_id)           REFERENCES choferes(id) ON DELETE SET NULL,
    CONSTRAINT ck_veh_capacidad CHECK (capacidad > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- CLIENTES Y CUENTAS CORRIENTES
-- -----------------------------------------------------------------------------
CREATE TABLE clientes (
    id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    tipo                  ENUM('particular','constructor','empresa','corralon','otro') NOT NULL DEFAULT 'particular',
    razon_social          VARCHAR(150) NOT NULL,
    documento_tipo        ENUM('DNI','CUIT','CUIL','OTRO') NOT NULL DEFAULT 'DNI',
    documento             VARCHAR(13)  NULL,
    condicion_iva         ENUM('consumidor_final','responsable_inscripto','monotributo','exento','no_categorizado') NOT NULL DEFAULT 'consumidor_final',
    telefono              VARCHAR(40)  NULL,
    whatsapp              VARCHAR(40)  NULL,
    email                 VARCHAR(120) NULL,
    direccion             VARCHAR(200) NULL,
    localidad             VARCHAR(100) NULL,
    zona_id               INT UNSIGNED NULL,
    referencia_ubicacion  VARCHAR(255) NULL,
    observaciones         TEXT NULL,
    activo                TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en             DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_clientes_documento (documento),
    KEY ix_clientes_razon (razon_social),
    KEY ix_clientes_localidad (localidad),
    CONSTRAINT fk_clientes_zona FOREIGN KEY (zona_id) REFERENCES zonas_entrega(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Una cuenta por cliente. saldo > 0 => el cliente nos debe.
CREATE TABLE cuentas_corrientes (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cliente_id      INT UNSIGNED NOT NULL,
    limite_credito  DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- 0 = sin límite
    saldo           DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    actualizado_en  DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cc_cliente (cliente_id),
    KEY ix_cc_saldo (saldo),
    CONSTRAINT fk_cc_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- CAJA Y MÉTODOS DE PAGO
-- -----------------------------------------------------------------------------
CREATE TABLE metodos_pago (
    id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
    codigo    VARCHAR(30)  NOT NULL,
    nombre    VARCHAR(60)  NOT NULL,
    grupo     ENUM('efectivo','transferencia','tarjeta','billetera','cuenta_corriente','otro') NOT NULL,
    activo    TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_mp_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE cajas (
    id                     INT UNSIGNED NOT NULL AUTO_INCREMENT,
    usuario_apertura_id    INT UNSIGNED NOT NULL,
    fecha_apertura         DATETIME     NOT NULL,
    monto_inicial          DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    estado                 ENUM('abierta','cerrada') NOT NULL DEFAULT 'abierta',
    usuario_cierre_id      INT UNSIGNED NULL,
    fecha_cierre           DATETIME     NULL,
    total_efectivo_ing     DECIMAL(14,2) NULL,
    total_efectivo_egr     DECIMAL(14,2) NULL,
    total_transferencias   DECIMAL(14,2) NULL,
    total_tarjetas         DECIMAL(14,2) NULL,
    total_otros            DECIMAL(14,2) NULL,
    saldo_esperado         DECIMAL(14,2) NULL,
    saldo_declarado        DECIMAL(14,2) NULL,
    diferencia             DECIMAL(14,2) NULL,
    observaciones          TEXT NULL,
    -- Garantiza una sola caja abierta a la vez.
    abierta_flag           TINYINT AS (IF(estado = 'abierta', 1, NULL)) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cajas_una_abierta (abierta_flag),
    KEY ix_cajas_fecha (fecha_apertura),
    CONSTRAINT fk_cajas_uape FOREIGN KEY (usuario_apertura_id) REFERENCES usuarios(id),
    CONSTRAINT fk_cajas_ucie FOREIGN KEY (usuario_cierre_id)   REFERENCES usuarios(id),
    CONSTRAINT ck_cajas_inicial CHECK (monto_inicial >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PRESUPUESTOS
-- -----------------------------------------------------------------------------
CREATE TABLE presupuestos (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha               DATETIME     NOT NULL,
    fecha_vencimiento   DATE         NOT NULL,
    cliente_id          INT UNSIGNED NOT NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    tipo_entrega        ENUM('retiro','envio') NOT NULL DEFAULT 'retiro',
    zona_id             INT UNSIGNED NULL,
    direccion_entrega   VARCHAR(200) NULL,
    subtotal            DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    descuento_general   DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    costo_envio         DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    total               DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    estado              ENUM('pendiente','enviado','aceptado','rechazado','vencido') NOT NULL DEFAULT 'pendiente',
    venta_id            INT UNSIGNED NULL,
    pedido_id           INT UNSIGNED NULL,
    observaciones       TEXT NULL,
    creado_en           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_presu_fecha (fecha),
    KEY ix_presu_cliente (cliente_id),
    KEY ix_presu_estado (estado),
    CONSTRAINT fk_presu_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id),
    CONSTRAINT fk_presu_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT fk_presu_zona    FOREIGN KEY (zona_id)    REFERENCES zonas_entrega(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE detalle_presupuestos (
    id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    presupuesto_id   INT UNSIGNED NOT NULL,
    material_id      INT UNSIGNED NOT NULL,
    unidad_id        INT UNSIGNED NOT NULL,
    cantidad         DECIMAL(14,3) NOT NULL,
    precio_unitario  DECIMAL(14,2) NOT NULL,
    descuento_pct    DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    subtotal         DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_dp_presu (presupuesto_id),
    CONSTRAINT fk_dpres_presu    FOREIGN KEY (presupuesto_id) REFERENCES presupuestos(id) ON DELETE CASCADE,
    CONSTRAINT fk_dpres_material FOREIGN KEY (material_id)    REFERENCES materiales(id),
    CONSTRAINT fk_dpres_unidad   FOREIGN KEY (unidad_id)      REFERENCES unidades(id),
    CONSTRAINT ck_dpres_cant     CHECK (cantidad > 0),
    CONSTRAINT ck_dpres_desc     CHECK (descuento_pct >= 0 AND descuento_pct <= 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- VENTAS
-- -----------------------------------------------------------------------------
CREATE TABLE ventas (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha               DATETIME     NOT NULL,
    cliente_id          INT UNSIGNED NOT NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    presupuesto_id      INT UNSIGNED NULL,
    pedido_id           INT UNSIGNED NULL,
    tipo_entrega        ENUM('retiro','envio') NOT NULL DEFAULT 'retiro',
    zona_id             INT UNSIGNED NULL,
    direccion_entrega   VARCHAR(200) NULL,
    subtotal            DECIMAL(14,2) NOT NULL,
    descuento_general   DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    costo_envio         DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    total               DECIMAL(14,2) NOT NULL,
    costo_mercaderia    DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- para ganancia estimada
    monto_pagado        DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    saldo_cta_cte       DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- parte enviada a cuenta corriente
    estado_pago         ENUM('pagada','parcial','cuenta_corriente') NOT NULL,
    estado              ENUM('confirmada','anulada') NOT NULL DEFAULT 'confirmada',
    motivo_anulacion    VARCHAR(255) NULL,
    anulada_por         INT UNSIGNED NULL,
    anulada_en          DATETIME NULL,
    observaciones       TEXT NULL,
    PRIMARY KEY (id),
    KEY ix_ventas_fecha (fecha),
    KEY ix_ventas_cliente (cliente_id),
    KEY ix_ventas_usuario (usuario_id),
    KEY ix_ventas_estado (estado, fecha),
    CONSTRAINT fk_ventas_cliente FOREIGN KEY (cliente_id)     REFERENCES clientes(id),
    CONSTRAINT fk_ventas_usuario FOREIGN KEY (usuario_id)     REFERENCES usuarios(id),
    CONSTRAINT fk_ventas_presu   FOREIGN KEY (presupuesto_id) REFERENCES presupuestos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ventas_zona    FOREIGN KEY (zona_id)        REFERENCES zonas_entrega(id) ON DELETE SET NULL,
    CONSTRAINT fk_ventas_anulo   FOREIGN KEY (anulada_por)    REFERENCES usuarios(id),
    CONSTRAINT ck_ventas_montos  CHECK (total >= 0 AND monto_pagado >= 0 AND saldo_cta_cte >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE detalle_ventas (
    id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
    venta_id           INT UNSIGNED NOT NULL,
    material_id        INT UNSIGNED NOT NULL,
    unidad_id          INT UNSIGNED NOT NULL,           -- unidad elegida en la venta
    cantidad           DECIMAL(14,3) NOT NULL,          -- en unidad_id
    factor_conversion  DECIMAL(14,6) NOT NULL DEFAULT 1, -- unidad_id -> unidad de stock
    cantidad_stock     DECIMAL(14,3) NOT NULL,          -- descontada del stock
    precio_unitario    DECIMAL(14,2) NOT NULL,          -- por unidad_id
    descuento_pct      DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    subtotal           DECIMAL(14,2) NOT NULL,
    costo_unitario     DECIMAL(14,2) NOT NULL DEFAULT 0.00, -- costo por unidad de stock (foto)
    PRIMARY KEY (id),
    KEY ix_dv_venta (venta_id),
    KEY ix_dv_material (material_id),
    CONSTRAINT fk_dv_venta    FOREIGN KEY (venta_id)    REFERENCES ventas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dv_material FOREIGN KEY (material_id) REFERENCES materiales(id),
    CONSTRAINT fk_dv_unidad   FOREIGN KEY (unidad_id)   REFERENCES unidades(id),
    CONSTRAINT ck_dv_cant     CHECK (cantidad > 0),
    CONSTRAINT ck_dv_desc     CHECK (descuento_pct >= 0 AND descuento_pct <= 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- STOCK
-- -----------------------------------------------------------------------------
CREATE TABLE movimientos_stock (
    id                    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha                 DATETIME     NOT NULL,
    material_id           INT UNSIGNED NOT NULL,
    tipo                  ENUM('entrada','salida','ajuste','anulacion') NOT NULL,
    cantidad              DECIMAL(14,3) NOT NULL,  -- con signo, en unidad de stock
    unidad_id             INT UNSIGNED NOT NULL,   -- unidad en que se registró
    cantidad_unidad       DECIMAL(14,3) NOT NULL,  -- cantidad en esa unidad (sin signo)
    factor_conversion     DECIMAL(14,6) NOT NULL DEFAULT 1,
    stock_anterior        DECIMAL(14,3) NOT NULL,
    stock_resultante      DECIMAL(14,3) NOT NULL,
    proveedor_id          INT UNSIGNED NULL,
    cliente_id            INT UNSIGNED NULL,
    venta_id              INT UNSIGNED NULL,
    vehiculo_id           INT UNSIGNED NULL,
    vehiculo_descripcion  VARCHAR(120) NULL,   -- camión externo del proveedor
    remito_numero         VARCHAR(40)  NULL,
    costo_unitario        DECIMAL(14,2) NULL,  -- por unidad de stock
    costo_total           DECIMAL(14,2) NULL,
    usuario_id            INT UNSIGNED NOT NULL,
    observaciones         VARCHAR(255) NULL,
    PRIMARY KEY (id),
    KEY ix_ms_material_fecha (material_id, fecha),
    KEY ix_ms_tipo_fecha (tipo, fecha),
    KEY ix_ms_venta (venta_id),
    KEY ix_ms_proveedor (proveedor_id),
    CONSTRAINT fk_ms_material  FOREIGN KEY (material_id)  REFERENCES materiales(id),
    CONSTRAINT fk_ms_unidad    FOREIGN KEY (unidad_id)    REFERENCES unidades(id),
    CONSTRAINT fk_ms_proveedor FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
    CONSTRAINT fk_ms_cliente   FOREIGN KEY (cliente_id)   REFERENCES clientes(id),
    CONSTRAINT fk_ms_venta     FOREIGN KEY (venta_id)     REFERENCES ventas(id),
    CONSTRAINT fk_ms_vehiculo  FOREIGN KEY (vehiculo_id)  REFERENCES vehiculos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ms_usuario   FOREIGN KEY (usuario_id)   REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PAGOS DE CLIENTES Y MOVIMIENTOS DE CUENTA CORRIENTE
-- -----------------------------------------------------------------------------
CREATE TABLE pagos (
    id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha            DATETIME     NOT NULL,
    cliente_id       INT UNSIGNED NOT NULL,
    venta_id         INT UNSIGNED NULL,     -- NULL = pago a cuenta corriente
    metodo_pago_id   INT UNSIGNED NOT NULL,
    monto            DECIMAL(14,2) NOT NULL,
    caja_id          INT UNSIGNED NOT NULL,
    referencia       VARCHAR(100) NULL,     -- nro. de transferencia, cupón, etc.
    estado           ENUM('registrado','anulado') NOT NULL DEFAULT 'registrado',
    usuario_id       INT UNSIGNED NOT NULL,
    observaciones    VARCHAR(255) NULL,
    PRIMARY KEY (id),
    KEY ix_pagos_fecha (fecha),
    KEY ix_pagos_cliente (cliente_id),
    KEY ix_pagos_venta (venta_id),
    CONSTRAINT fk_pagos_cliente FOREIGN KEY (cliente_id)     REFERENCES clientes(id),
    CONSTRAINT fk_pagos_venta   FOREIGN KEY (venta_id)       REFERENCES ventas(id),
    CONSTRAINT fk_pagos_metodo  FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id),
    CONSTRAINT fk_pagos_caja    FOREIGN KEY (caja_id)        REFERENCES cajas(id),
    CONSTRAINT fk_pagos_usuario FOREIGN KEY (usuario_id)     REFERENCES usuarios(id),
    CONSTRAINT ck_pagos_monto   CHECK (monto > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE movimientos_cuenta_corriente (
    id                 INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cuenta_id          INT UNSIGNED NOT NULL,
    fecha              DATETIME     NOT NULL,
    tipo               ENUM('venta','pago','deuda','credito','anulacion','ajuste') NOT NULL,
    concepto           VARCHAR(200) NOT NULL,
    debe               DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- aumenta la deuda del cliente
    haber              DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- disminuye la deuda
    saldo_resultante   DECIMAL(14,2) NOT NULL,
    venta_id           INT UNSIGNED NULL,
    pago_id            INT UNSIGNED NULL,
    usuario_id         INT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    KEY ix_mcc_cuenta_fecha (cuenta_id, fecha),
    CONSTRAINT fk_mcc_cuenta  FOREIGN KEY (cuenta_id)  REFERENCES cuentas_corrientes(id) ON DELETE CASCADE,
    CONSTRAINT fk_mcc_venta   FOREIGN KEY (venta_id)   REFERENCES ventas(id),
    CONSTRAINT fk_mcc_pago    FOREIGN KEY (pago_id)    REFERENCES pagos(id),
    CONSTRAINT fk_mcc_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    CONSTRAINT ck_mcc_importes CHECK (debe >= 0 AND haber >= 0 AND (debe > 0 OR haber > 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PROVEEDORES: cuenta y pagos
-- -----------------------------------------------------------------------------
CREATE TABLE pagos_proveedores (
    id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha            DATETIME     NOT NULL,
    proveedor_id     INT UNSIGNED NOT NULL,
    metodo_pago_id   INT UNSIGNED NOT NULL,
    monto            DECIMAL(14,2) NOT NULL,
    caja_id          INT UNSIGNED NULL,
    referencia       VARCHAR(100) NULL,
    usuario_id       INT UNSIGNED NOT NULL,
    observaciones    VARCHAR(255) NULL,
    PRIMARY KEY (id),
    KEY ix_pp_proveedor (proveedor_id, fecha),
    CONSTRAINT fk_pp_proveedor FOREIGN KEY (proveedor_id)   REFERENCES proveedores(id),
    CONSTRAINT fk_pp_metodo    FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id),
    CONSTRAINT fk_pp_caja      FOREIGN KEY (caja_id)        REFERENCES cajas(id),
    CONSTRAINT fk_pp_usuario   FOREIGN KEY (usuario_id)     REFERENCES usuarios(id),
    CONSTRAINT ck_pp_monto     CHECK (monto > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE movimientos_cuenta_proveedor (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    proveedor_id        INT UNSIGNED NOT NULL,
    fecha               DATETIME     NOT NULL,
    tipo                ENUM('compra','pago','ajuste') NOT NULL,
    concepto            VARCHAR(200) NOT NULL,
    cargo               DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- aumenta lo que debemos
    abono               DECIMAL(14,2) NOT NULL DEFAULT 0.00,  -- disminuye lo que debemos
    saldo_resultante    DECIMAL(14,2) NOT NULL,
    movimiento_stock_id INT UNSIGNED NULL,
    pago_proveedor_id   INT UNSIGNED NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    KEY ix_mcp_prov_fecha (proveedor_id, fecha),
    CONSTRAINT fk_mcp_proveedor FOREIGN KEY (proveedor_id)        REFERENCES proveedores(id),
    CONSTRAINT fk_mcp_mstock    FOREIGN KEY (movimiento_stock_id) REFERENCES movimientos_stock(id),
    CONSTRAINT fk_mcp_pago      FOREIGN KEY (pago_proveedor_id)   REFERENCES pagos_proveedores(id),
    CONSTRAINT fk_mcp_usuario   FOREIGN KEY (usuario_id)          REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- PEDIDOS Y ENTREGAS
-- -----------------------------------------------------------------------------
CREATE TABLE pedidos (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha               DATETIME     NOT NULL,
    cliente_id          INT UNSIGNED NOT NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    presupuesto_id      INT UNSIGNED NULL,
    venta_id            INT UNSIGNED NULL,
    tipo_entrega        ENUM('retiro','envio') NOT NULL DEFAULT 'envio',
    direccion_entrega   VARCHAR(200) NULL,
    localidad           VARCHAR(100) NULL,
    referencia          VARCHAR(255) NULL,
    zona_id             INT UNSIGNED NULL,
    fecha_solicitada    DATE         NOT NULL,
    horario             VARCHAR(40)  NULL,
    vehiculo_id         INT UNSIGNED NULL,
    chofer_id           INT UNSIGNED NULL,
    subtotal            DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    descuento_general   DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    costo_envio         DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    total               DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    estado              ENUM('pendiente','confirmado','preparando','listo','en_camino','entregado','cancelado') NOT NULL DEFAULT 'pendiente',
    observaciones       TEXT NULL,
    creado_en           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_pedidos_fecha_sol (fecha_solicitada),
    KEY ix_pedidos_estado (estado),
    KEY ix_pedidos_cliente (cliente_id),
    CONSTRAINT fk_ped_cliente  FOREIGN KEY (cliente_id)     REFERENCES clientes(id),
    CONSTRAINT fk_ped_usuario  FOREIGN KEY (usuario_id)     REFERENCES usuarios(id),
    CONSTRAINT fk_ped_presu    FOREIGN KEY (presupuesto_id) REFERENCES presupuestos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ped_venta    FOREIGN KEY (venta_id)       REFERENCES ventas(id) ON DELETE SET NULL,
    CONSTRAINT fk_ped_zona     FOREIGN KEY (zona_id)        REFERENCES zonas_entrega(id) ON DELETE SET NULL,
    CONSTRAINT fk_ped_vehiculo FOREIGN KEY (vehiculo_id)    REFERENCES vehiculos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ped_chofer   FOREIGN KEY (chofer_id)      REFERENCES choferes(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE ventas
    ADD CONSTRAINT fk_ventas_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE SET NULL;
ALTER TABLE presupuestos
    ADD CONSTRAINT fk_presu_venta  FOREIGN KEY (venta_id)  REFERENCES ventas(id)  ON DELETE SET NULL,
    ADD CONSTRAINT fk_presu_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos(id) ON DELETE SET NULL;

CREATE TABLE detalle_pedidos (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    pedido_id           INT UNSIGNED NOT NULL,
    material_id         INT UNSIGNED NOT NULL,
    unidad_id           INT UNSIGNED NOT NULL,
    cantidad            DECIMAL(14,3) NOT NULL,
    precio_unitario     DECIMAL(14,2) NOT NULL,
    descuento_pct       DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    subtotal            DECIMAL(14,2) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_dped_pedido (pedido_id),
    CONSTRAINT fk_dped_pedido   FOREIGN KEY (pedido_id)   REFERENCES pedidos(id) ON DELETE CASCADE,
    CONSTRAINT fk_dped_material FOREIGN KEY (material_id) REFERENCES materiales(id),
    CONSTRAINT fk_dped_unidad   FOREIGN KEY (unidad_id)   REFERENCES unidades(id),
    CONSTRAINT ck_dped_cant     CHECK (cantidad > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Una entrega = un viaje de un camión. Un pedido grande puede requerir varias.
CREATE TABLE entregas (
    id                   INT UNSIGNED NOT NULL AUTO_INCREMENT,
    pedido_id            INT UNSIGNED NULL,
    venta_id             INT UNSIGNED NULL,
    cliente_id           INT UNSIGNED NOT NULL,
    direccion            VARCHAR(200) NOT NULL,
    localidad            VARCHAR(100) NULL,
    referencia           VARCHAR(255) NULL,
    telefono_contacto    VARCHAR(40)  NULL,
    chofer_id            INT UNSIGNED NULL,
    vehiculo_id          INT UNSIGNED NULL,
    fecha                DATE         NOT NULL,
    horario              VARCHAR(40)  NULL,
    estado               ENUM('pendiente','asignada','en_camino','entregada','no_entregada','cancelada') NOT NULL DEFAULT 'pendiente',
    observaciones        TEXT NULL,
    motivo_no_entrega    VARCHAR(255) NULL,
    recibido_por         VARCHAR(120) NULL,
    fecha_salida         DATETIME NULL,
    fecha_entrega_real   DATETIME NULL,
    usuario_id           INT UNSIGNED NOT NULL,
    creado_en            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_ent_fecha_estado (fecha, estado),
    KEY ix_ent_chofer (chofer_id, fecha),
    KEY ix_ent_vehiculo (vehiculo_id),
    KEY ix_ent_pedido (pedido_id),
    CONSTRAINT fk_ent_pedido   FOREIGN KEY (pedido_id)   REFERENCES pedidos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ent_venta    FOREIGN KEY (venta_id)    REFERENCES ventas(id)  ON DELETE SET NULL,
    CONSTRAINT fk_ent_cliente  FOREIGN KEY (cliente_id)  REFERENCES clientes(id),
    CONSTRAINT fk_ent_chofer   FOREIGN KEY (chofer_id)   REFERENCES choferes(id) ON DELETE SET NULL,
    CONSTRAINT fk_ent_vehiculo FOREIGN KEY (vehiculo_id) REFERENCES vehiculos(id) ON DELETE SET NULL,
    CONSTRAINT fk_ent_usuario  FOREIGN KEY (usuario_id)  REFERENCES usuarios(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE detalle_entregas (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    entrega_id          INT UNSIGNED NOT NULL,
    detalle_pedido_id   INT UNSIGNED NULL,
    material_id         INT UNSIGNED NOT NULL,
    unidad_id           INT UNSIGNED NOT NULL,
    cantidad            DECIMAL(14,3) NOT NULL,
    PRIMARY KEY (id),
    KEY ix_dent_entrega (entrega_id),
    CONSTRAINT fk_dent_entrega  FOREIGN KEY (entrega_id)        REFERENCES entregas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dent_dpedido  FOREIGN KEY (detalle_pedido_id) REFERENCES detalle_pedidos(id) ON DELETE SET NULL,
    CONSTRAINT fk_dent_material FOREIGN KEY (material_id)       REFERENCES materiales(id),
    CONSTRAINT fk_dent_unidad   FOREIGN KEY (unidad_id)         REFERENCES unidades(id),
    CONSTRAINT ck_dent_cant     CHECK (cantidad > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- GASTOS
-- -----------------------------------------------------------------------------
CREATE TABLE categorias_gastos (
    id       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre   VARCHAR(60) NOT NULL,
    activo   TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_catgas_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE gastos (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha               DATETIME     NOT NULL,
    categoria_id        INT UNSIGNED NOT NULL,
    descripcion         VARCHAR(200) NOT NULL,
    monto               DECIMAL(14,2) NOT NULL,
    metodo_pago_id      INT UNSIGNED NOT NULL,
    proveedor_id        INT UNSIGNED NULL,
    vehiculo_id         INT UNSIGNED NULL,
    caja_id             INT UNSIGNED NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    estado              ENUM('registrado','anulado') NOT NULL DEFAULT 'registrado',
    observaciones       TEXT NULL,
    PRIMARY KEY (id),
    KEY ix_gastos_fecha (fecha),
    KEY ix_gastos_categoria (categoria_id),
    CONSTRAINT fk_gas_categoria FOREIGN KEY (categoria_id)   REFERENCES categorias_gastos(id),
    CONSTRAINT fk_gas_metodo    FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id),
    CONSTRAINT fk_gas_proveedor FOREIGN KEY (proveedor_id)   REFERENCES proveedores(id) ON DELETE SET NULL,
    CONSTRAINT fk_gas_vehiculo  FOREIGN KEY (vehiculo_id)    REFERENCES vehiculos(id) ON DELETE SET NULL,
    CONSTRAINT fk_gas_caja      FOREIGN KEY (caja_id)        REFERENCES cajas(id),
    CONSTRAINT fk_gas_usuario   FOREIGN KEY (usuario_id)     REFERENCES usuarios(id),
    CONSTRAINT ck_gas_monto     CHECK (monto > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- MOVIMIENTOS DE CAJA
-- -----------------------------------------------------------------------------
CREATE TABLE movimientos_caja (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    caja_id             INT UNSIGNED NOT NULL,
    fecha               DATETIME     NOT NULL,
    tipo                ENUM('venta','pago_cliente','gasto','retiro','ingreso','ajuste','pago_proveedor','anulacion') NOT NULL,
    sentido             ENUM('ingreso','egreso') NOT NULL,
    metodo_pago_id      INT UNSIGNED NOT NULL,
    monto               DECIMAL(14,2) NOT NULL,
    concepto            VARCHAR(200) NOT NULL,
    venta_id            INT UNSIGNED NULL,
    pago_id             INT UNSIGNED NULL,
    gasto_id            INT UNSIGNED NULL,
    pago_proveedor_id   INT UNSIGNED NULL,
    usuario_id          INT UNSIGNED NOT NULL,
    PRIMARY KEY (id),
    KEY ix_mc_caja (caja_id, fecha),
    KEY ix_mc_tipo (tipo),
    CONSTRAINT fk_mc_caja      FOREIGN KEY (caja_id)           REFERENCES cajas(id),
    CONSTRAINT fk_mc_metodo    FOREIGN KEY (metodo_pago_id)    REFERENCES metodos_pago(id),
    CONSTRAINT fk_mc_venta     FOREIGN KEY (venta_id)          REFERENCES ventas(id),
    CONSTRAINT fk_mc_pago      FOREIGN KEY (pago_id)           REFERENCES pagos(id),
    CONSTRAINT fk_mc_gasto     FOREIGN KEY (gasto_id)          REFERENCES gastos(id),
    CONSTRAINT fk_mc_pprov     FOREIGN KEY (pago_proveedor_id) REFERENCES pagos_proveedores(id),
    CONSTRAINT fk_mc_usuario   FOREIGN KEY (usuario_id)        REFERENCES usuarios(id),
    CONSTRAINT ck_mc_monto     CHECK (monto > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- HISTORIAL / AUDITORÍA
-- -----------------------------------------------------------------------------
CREATE TABLE historial_operaciones (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    fecha         DATETIME     NOT NULL,
    usuario_id    INT UNSIGNED NULL,
    accion        VARCHAR(40)  NOT NULL,     -- crear, modificar, anular, login…
    modulo        VARCHAR(40)  NOT NULL,
    registro_id   VARCHAR(40)  NULL,
    descripcion   VARCHAR(500) NOT NULL,
    ip            VARCHAR(45)  NULL,
    PRIMARY KEY (id),
    KEY ix_hist_fecha (fecha),
    KEY ix_hist_usuario (usuario_id, fecha),
    KEY ix_hist_modulo (modulo, fecha),
    CONSTRAINT fk_hist_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- FACTURACIÓN ELECTRÓNICA (preparada para ARCA/AFIP — sin integración ficticia)
-- -----------------------------------------------------------------------------
CREATE TABLE tipos_comprobante (
    codigo        SMALLINT UNSIGNED NOT NULL,   -- código oficial ARCA (1=Fact. A, 6=Fact. B, 11=Fact. C…)
    descripcion   VARCHAR(60) NOT NULL,
    letra         CHAR(1)     NOT NULL,
    clase         ENUM('factura','nota_debito','nota_credito','recibo') NOT NULL,
    activo        TINYINT(1)  NOT NULL DEFAULT 1,
    PRIMARY KEY (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE puntos_venta (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    numero        SMALLINT UNSIGNED NOT NULL,
    descripcion   VARCHAR(100) NULL,
    modalidad     ENUM('electronico','manual') NOT NULL DEFAULT 'electronico',
    activo        TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_pv_numero (numero)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE comprobantes (
    id                       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    venta_id                 INT UNSIGNED NOT NULL,
    tipo_comprobante         SMALLINT UNSIGNED NOT NULL,
    punto_venta_id           INT UNSIGNED NOT NULL,
    numero                   INT UNSIGNED NULL,          -- lo asigna ARCA al autorizar
    fecha_emision            DATE NOT NULL,
    cuit_emisor              VARCHAR(11) NOT NULL,
    receptor_doc_tipo        SMALLINT UNSIGNED NOT NULL, -- 80=CUIT, 96=DNI, 99=Consumidor final
    receptor_doc_nro         VARCHAR(13) NOT NULL,
    receptor_condicion_iva   VARCHAR(30) NOT NULL,
    importe_neto             DECIMAL(14,2) NOT NULL,
    importe_iva              DECIMAL(14,2) NOT NULL DEFAULT 0.00,
    importe_total            DECIMAL(14,2) NOT NULL,
    cae                      VARCHAR(20) NULL,
    cae_vencimiento          DATE NULL,
    estado                   ENUM('borrador','pendiente','autorizado','rechazado','error') NOT NULL DEFAULT 'borrador',
    observaciones_arca       TEXT NULL,
    creado_en                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_comp_numero (tipo_comprobante, punto_venta_id, numero),
    KEY ix_comp_venta (venta_id),
    CONSTRAINT fk_comp_venta FOREIGN KEY (venta_id)         REFERENCES ventas(id),
    CONSTRAINT fk_comp_tipo  FOREIGN KEY (tipo_comprobante) REFERENCES tipos_comprobante(codigo),
    CONSTRAINT fk_comp_pv    FOREIGN KEY (punto_venta_id)   REFERENCES puntos_venta(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
