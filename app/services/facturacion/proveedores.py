"""Registro de proveedores de facturación."""
from flask import current_app

from .base import FacturacionNoDisponible, ProveedorFacturacion


class SinProveedor(ProveedorFacturacion):
    """Proveedor por defecto: NO emite nada. Evita comprobantes falsos."""

    nombre = "ninguno"

    def disponible(self):
        return False

    def ultimo_numero(self, punto_venta, tipo_comprobante):
        raise FacturacionNoDisponible("La facturación electrónica no está configurada.")

    def autorizar(self, datos):
        raise FacturacionNoDisponible(
            "La facturación electrónica con ARCA todavía no está integrada. El comprobante quedó guardado como "
            "borrador con todos sus datos; se podrá autorizar cuando se configure el proveedor oficial.")


# Agregar aquí la integración real, p. ej.: {"arca": ArcaWSFEProveedor}
PROVEEDORES = {
    "ninguno": SinProveedor,
}


def obtener_proveedor() -> ProveedorFacturacion:
    clave = (current_app.config.get("FACTURACION_PROVEEDOR") or "ninguno").lower()
    clase = PROVEEDORES.get(clave, SinProveedor)
    return clase()
