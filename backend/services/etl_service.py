"""Business logic for upload and job status."""

import json
import logging
import uuid

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.queue.aio import QueueServiceClient
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.models import JobModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blob
# ---------------------------------------------------------------------------

async def upload_to_blob(file: UploadFile, blob_name: str) -> None:
    """Sube el archivo CSV a Azure Blob Storage como stream.

    No carga el archivo completo en memoria — usa el stream
    del UploadFile directamente.

    Args:
        file:      Archivo recibido por FastAPI.
        blob_name: Ruta destino dentro del contenedor.
    """
    async with BlobServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        blob = client.get_blob_client(
            container=settings.azure_blob_container,
            blob=blob_name,
        )
        await blob.upload_blob(file, overwrite=True)
        logger.info("Archivo subido al blob: %s", blob_name)


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

async def send_queue_message(job_id: str, blob_name: str) -> None:
    """Envía un mensaje a la Queue indicando que hay un archivo para procesar.

    Args:
        job_id:    Identificador único del job.
        blob_name: Ruta del archivo en el Blob.
    """
    async with QueueServiceClient.from_connection_string(
        settings.azure_storage_connection_string
    ) as client:
        queue = client.get_queue_client(settings.azure_queue_name)
        message = json.dumps({"job_id": job_id, "blob_name": blob_name})
        await queue.send_message(message)
        logger.info("Mensaje encolado para job: %s", job_id)


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

async def create_job(db: AsyncSession, job_id: str, blob_name: str) -> JobModel:
    """Registra un nuevo job como PENDING en la base de datos.

    Args:
        db:        Sesión de base de datos.
        job_id:    Identificador único del job.
        blob_name: Ruta del archivo en el Blob.

    Returns:
        El JobModel recién creado.
    """
    job = JobModel(id=job_id, blob_name=blob_name, status="PENDING")
    db.add(job)
    await db.commit()
    await db.refresh(job)
    logger.info("Job creado: %s", job_id)
    return job


async def get_job(db: AsyncSession, job_id: str) -> JobModel | None:
    """Busca un job por su ID.

    Args:
        db:     Sesión de base de datos.
        job_id: Identificador del job a buscar.

    Returns:
        El JobModel si existe, None si no.
    """
    result = await db.execute(select(JobModel).where(JobModel.id == job_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Upload orchestration
# ---------------------------------------------------------------------------

async def handle_upload(db: AsyncSession, file: UploadFile) -> str:
    """Orquesta el flujo completo de upload.

    1. Genera un job_id único.
    2. Sube el archivo al Blob Storage.
    3. Registra el job como PENDING en la DB.
    4. Encola el mensaje para el Worker.

    Args:
        db:   Sesión de base de datos.
        file: Archivo CSV recibido.

    Returns:
        El job_id generado.
    """
    job_id = str(uuid.uuid4())
    blob_name = f"uploads/{job_id}/{file.filename}"

    await upload_to_blob(file, blob_name)
    await create_job(db, job_id, blob_name)
    await send_queue_message(job_id, blob_name)

    return job_id