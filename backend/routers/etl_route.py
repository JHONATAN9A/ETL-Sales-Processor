"""API route definitions for the ETL Sales Pipeline."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from schemas.etl_schema import JobResponse, JobStatusResponse
from services.etl_service import get_job, handle_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/upload",
    response_model=JobResponse,
    status_code=202,
    summary="Subir archivo CSV",
    description="Recibe un CSV, lo guarda en Blob Storage, encola el job y responde con el job_id.",
)
async def upload_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Endpoint para subir un archivo CSV.

    Responde inmediatamente con un job_id sin esperar
    a que el archivo sea procesado.

    Args:
        file: Archivo CSV enviado como multipart/form-data.
        db:   Sesión de base de datos inyectada por FastAPI.

    Returns:
        JobResponse con el job_id y status PENDING.

    Raises:
        HTTPException 400: Si el archivo no es un CSV.
        HTTPException 500: Si falla el upload o el encolamiento.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un CSV.")

    try:
        job_id = await handle_upload(db, file)
    except Exception:
        logger.exception("Error procesando el upload del archivo %s", file.filename)
        raise HTTPException(status_code=500, detail="Error al procesar el archivo.")

    return JobResponse(job_id=job_id, status="PENDING")


@router.get(
    "/job/{job_id}",
    response_model=JobStatusResponse,
    summary="Consultar estado de un job",
    description="Devuelve el estado actual del procesamiento de un archivo CSV.",
)
async def get_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """Endpoint para consultar el estado de un job.

    Args:
        job_id: Identificador del job a consultar.
        db:     Sesión de base de datos inyectada por FastAPI.

    Returns:
        JobStatusResponse con el estado actual del job.

    Raises:
        HTTPException 404: Si el job_id no existe.
    """
    job = await get_job(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado.")

    return JobStatusResponse(
        job_id=job.id,
        blob_name=job.blob_name,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
