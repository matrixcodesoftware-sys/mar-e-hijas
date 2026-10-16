"""Facturación electrónica (ARCA, ex AFIP) — arquitectura preparada, SIN integración ficticia.

Estructura:
    base.py         Contratos: datos del comprobante, resultado de autorización e interfaz del proveedor.
    proveedores.py  Registro de proveedores. Hoy sólo existe SinProveedor, que rechaza explícitamente.
    servicio.py     Arma el comprobante a partir de una venta, lo persiste y delega la autorización.

Para integrar ARCA (WSAA + WSFEv1):
    1. Crear `arca.py` con una clase que implemente ProveedorFacturacion
       (obtener TA en WSAA con el certificado, FECompUltimoAutorizado, FECAESolicitar).
    2. Registrarla en proveedores.PROVEEDORES con la clave "arca".
    3. En .env: FACTURACION_PROVEEDOR=arca, ARCA_CERT_PATH, ARCA_KEY_PATH, ARCA_PRODUCCION.
Nada más del sistema necesita cambiar.
"""
