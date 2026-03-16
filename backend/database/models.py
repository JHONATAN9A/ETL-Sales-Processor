"""SQLAlchemy ORM models for the ETL Sales Pipeline database."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Date, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.x declarative base."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class JobModel(Base):
    """Representa un job de procesamiento de archivo CSV.

    Cada fila trackea el ciclo de vida de un archivo subido:
    desde que llega a la API hasta que el Worker termina de insertarlo.

    Attributes:
        id:          UUID generado por la API al recibir el archivo.
        blob_name:   Ruta del archivo dentro del Blob Container.
        status:      Estado del job: PENDING, PROCESSING, COMPLETED, FAILED.
        error:       Mensaje de error si el job falló.
        created_at:  Timestamp de creación del job.
        updated_at:  Timestamp de la última actualización de estado.
    """

    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    blob_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SaleModel(Base):
    """Representa un registro individual de venta procesado desde el CSV.

    Attributes:
        id:          Auto-incremented primary key.
        date:        Fecha de la venta.
        product_id:  Identificador del producto.
        quantity:    Cantidad vendida.
        price:       Precio unitario.
        total:       Total calculado (quantity * price).
    """

    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)


class SalesDailySummaryModel(Base):
    """Representa el resumen de ventas agregado por día.

    Lo calcula y persiste el workflow de N8N periódicamente.

    Attributes:
        date:            Fecha del resumen (primary key).
        total_sales:     Suma de todos los totales del día.
        total_quantity:  Suma de todas las cantidades del día.
        updated_at:      Última vez que N8N actualizó este registro.
    """

    __tablename__ = "sales_daily_summary"

    date = Column(Date, primary_key=True)
    total_sales = Column(Numeric(12, 2), nullable=False)
    total_quantity = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)