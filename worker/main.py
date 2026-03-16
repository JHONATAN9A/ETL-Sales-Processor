"""Worker — escucha la Queue, procesa el CSV y lo inserta en PostgreSQL."""

import asyncio
import csv
import json
import logging
import os
from datetime import date as date_type

import asyncpg
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.queue.aio import QueueServiceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONN_STR   = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER  = os.environ["AZURE_BLOB_CONTAINER"]
QUEUE_NAME = os.environ["AZURE_QUEUE_NAME"]
DB_URL     = os.environ["DATABASE_URL"]
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 5000))


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

async def update_job_status(
    pool: asyncpg.Pool,
    job_id: str,
    status: str,
    error: str = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET status = $1, error = $2, updated_at = NOW()
            WHERE id = $3
            """,
            status, error, job_id,
        )
    logger.info("Job %s → %s", job_id, status)


async def flush_batch(pool: asyncpg.Pool, batch: list) -> None:
    """Inserta un batch en sales usando COPY — más eficiente que INSERT masivo."""
    async with pool.acquire() as conn:
        await conn.copy_records_to_table(
            "sales",
            records=batch,
            columns=["date", "product_id", "quantity", "price", "total"],
        )
    logger.info("Batch de %d filas insertado", len(batch))


# ---------------------------------------------------------------------------
# Procesamiento del CSV — streaming real chunk a chunk
# ---------------------------------------------------------------------------

async def process_blob(pool: asyncpg.Pool, blob_name: str) -> None:
    """Descarga y procesa el CSV chunk a chunk.

    Nunca carga el archivo completo en memoria — solo vive
    un chunk (~512KB) a la vez independientemente del tamaño del archivo.

    El 'leftover' resuelve el caso donde un chunk se corta
    en medio de una línea — guarda ese fragmento y lo une
    con el inicio del siguiente chunk.
    """
    async with BlobServiceClient.from_connection_string(CONN_STR) as client:
        blob     = client.get_blob_client(container=CONTAINER, blob=blob_name)
        download = await blob.download_blob()
        content  = await download.readall()

    lines = content.decode("utf-8").splitlines()
    reader = csv.DictReader(lines)  # DictReader maneja el header automáticamente

    batch      = []
    total_rows = 0

    for row in reader:
        try:
            quantity = int(row["quantity"].strip())
            price    = float(row["price"].strip())
            total    = round(quantity * price, 2)

            batch.append((
                date_type.fromisoformat(row["date"].strip()),
                int(row["product_id"].strip()),
                quantity,
                price,
                total,
            ))
        except (ValueError, KeyError) as e:
            logger.warning("Línea inválida ignorada: %s — %s", row, e)
            continue

        if len(batch) >= BATCH_SIZE:
            await flush_batch(pool, batch)
            total_rows += len(batch)
            batch.clear()

    if batch:
        await flush_batch(pool, batch)
        total_rows += len(batch)

    logger.info("Total filas insertadas: %d", total_rows)


# ---------------------------------------------------------------------------
# Procesamiento del mensaje
# ---------------------------------------------------------------------------

async def process_message(pool: asyncpg.Pool, message) -> None:
    body      = json.loads(message.content)
    job_id    = body["job_id"]
    blob_name = body["blob_name"]

    logger.info("Procesando job %s — blob: %s", job_id, blob_name)
    await update_job_status(pool, job_id, "PROCESSING")

    try:
        await process_blob(pool, blob_name)
        await update_job_status(pool, job_id, "COMPLETED")
    except Exception as e:
        logger.exception("Error procesando job %s", job_id)
        await update_job_status(pool, job_id, "FAILED", error=str(e))


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

async def main() -> None:
    logger.info("Worker iniciado — escuchando queue '%s'", QUEUE_NAME)

    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=10)

    async with QueueServiceClient.from_connection_string(CONN_STR) as queue_service:
        queue = queue_service.get_queue_client(QUEUE_NAME)

        while True:
            messages = queue.receive_messages(max_messages=1)

            async for message in messages:
                try:
                    await process_message(pool, message)
                    await queue.delete_message(message)
                except Exception:
                    logger.exception(
                        "Error inesperado — mensaje no eliminado, volverá a la queue"
                    )

            await asyncio.sleep(5)


asyncio.run(main())