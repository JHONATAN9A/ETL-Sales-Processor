"""Pydantic schemas for request and response validation."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Job schemas
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    """Respuesta inmediata al subir un archivo CSV."""

    job_id: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


class JobStatusResponse(BaseModel):
    """Estado detallado de un job de procesamiento."""

    job_id: str
    blob_name: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}