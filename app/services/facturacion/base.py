"""Contratos de la facturación electrónica, independientes del proveedor."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Optional

# Códigos de documento del receptor según ARCA
DOC_CUIT = 80
DOC_CUIL = 86
DOC_DNI = 96
DOC_CONSUMIDOR_FINAL = 99

# Condición IVA del receptor (RG 5616) — códigos oficiales
CONDICION_IVA_RECEPTOR = {
    "responsable_inscripto": 1,
    "exento": 4,
    "consumidor_final": 5,
    "monotributo": 6,
    "no_categorizado": 7,
}


@dataclass
class ItemComprobante:
    descripcion: str
    cantidad: Decimal
    unidad: str
    precio_unitario: Decimal
    importe: Decimal
    alicuota_iva: Decimal = Decimal("21")


@dataclass
class DatosComprobante:
    tipo_comprobante: int          # 1 Factura A, 6 Factura B, 11 Factura C, 3/8/13 NC…
    punto_venta: int
    fecha_emision: date
    cuit_emisor: str
    receptor_doc_tipo: int
    receptor_doc_nro: str
    receptor_condicion_iva: str
    importe_neto: Decimal
    importe_iva: Decimal
    importe_total: Decimal
    concepto: int = 1              # 1 = productos
    moneda: str = "PES"
    cotizacion: Decimal = Decimal("1")
    items: List[ItemComprobante] = field(default_factory=list)
    numero: Optional[int] = None


@dataclass
class ResultadoAutorizacion:
    aprobado: bool
    numero: Optional[int] = None
    cae: Optional[str] = None
    cae_vencimiento: Optional[date] = None
    observaciones: str = ""


class FacturacionNoDisponible(Exception):
    """El proveedor configurado no puede autorizar comprobantes."""


class ProveedorFacturacion(ABC):
    """Interfaz que debe implementar cualquier integración (ARCA WSFEv1, un PAC, etc.)."""

    nombre = "abstracto"

    @abstractmethod
    def disponible(self) -> bool:
        ...

    @abstractmethod
    def ultimo_numero(self, punto_venta: int, tipo_comprobante: int) -> int:
        ...

    @abstractmethod
    def autorizar(self, datos: DatosComprobante) -> ResultadoAutorizacion:
        ...
