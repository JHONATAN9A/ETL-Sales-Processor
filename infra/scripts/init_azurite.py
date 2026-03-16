"""Inicializa los recursos de Azurite: Blob Container y Storage Queue."""

import asyncio
import logging
import os

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.queue.aio import QueueServiceClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

CONN_STR = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
BLOB_CONTAINER = os.environ["AZURE_BLOB_CONTAINER"]
QUEUE_NAME = os.environ["AZURE_QUEUE_NAME"]


async def init_blob() -> None:
    async with BlobServiceClient.from_connection_string(CONN_STR) as client:
        try:
            await client.create_container(BLOB_CONTAINER)
            logger.info("Contenedor '%s' creado", BLOB_CONTAINER)
        except Exception:
            logger.info("Contenedor '%s' ya existe", BLOB_CONTAINER)


async def init_queue() -> None:
    async with QueueServiceClient.from_connection_string(CONN_STR) as client:
        try:
            await client.create_queue(QUEUE_NAME)
            logger.info("Queue '%s' creada", QUEUE_NAME)
        except Exception:
            logger.info("Queue '%s' ya existe", QUEUE_NAME)


async def main() -> None:
    logger.info("Inicializando recursos de Azurite...")
    await init_blob()
    await init_queue()
    logger.info("Listo")


asyncio.run(main())