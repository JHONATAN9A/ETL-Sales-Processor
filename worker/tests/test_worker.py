"""Tests para el Worker ETL."""

import json
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch, call, PropertyMock
from contextlib import asynccontextmanager


# ---------------------------------------------------------------------------
# Helpers para mockear async context managers
# ---------------------------------------------------------------------------

def make_pool_mock(mock_conn):
    """Crea un mock de asyncpg.Pool que soporta async with pool.acquire()."""
    mock_pool = MagicMock()

    @asynccontextmanager
    async def fake_acquire():
        yield mock_conn

    mock_pool.acquire = fake_acquire
    return mock_pool


def make_blob_service_mock(mock_download):
    """Crea un mock de BlobServiceClient que soporta async with."""
    mock_blob_client = AsyncMock()
    mock_blob_client.download_blob = AsyncMock(return_value=mock_download)

    mock_service = MagicMock()
    mock_service.get_blob_client = MagicMock(return_value=mock_blob_client)

    @asynccontextmanager
    async def fake_service_ctx(*args, **kwargs):
        yield mock_service

    return fake_service_ctx


# ---------------------------------------------------------------------------
# update_job_status
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_update_job_status_completed():
    """update_job_status debe ejecutar el UPDATE con los parámetros correctos."""
    from main import update_job_status

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    await update_job_status(mock_pool, "job-123", "COMPLETED")

    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    assert "COMPLETED" in args
    assert "job-123" in args


@pytest.mark.anyio
async def test_update_job_status_failed_con_error():
    """update_job_status debe pasar el mensaje de error al UPDATE."""
    from main import update_job_status

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    await update_job_status(mock_pool, "job-123", "FAILED", error="algo falló")

    args = mock_conn.execute.call_args[0]
    assert "FAILED" in args
    assert "algo falló" in args


# ---------------------------------------------------------------------------
# flush_batch
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_flush_batch_llama_copy_records():
    """flush_batch debe llamar copy_records_to_table con el batch correcto."""
    from main import flush_batch

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    batch = [
        (date(2026, 1, 1), 1001, 2, 10.5, 21.0),
        (date(2026, 1, 1), 1002, 1, 5.2, 5.2),
    ]

    await flush_batch(mock_pool, batch)

    mock_conn.copy_records_to_table.assert_called_once_with(
        "sales",
        records=batch,
        columns=["date", "product_id", "quantity", "price", "total"],
    )


# ---------------------------------------------------------------------------
# process_blob
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_process_blob_inserta_filas_correctamente():
    """process_blob debe parsear el CSV e insertar las filas en PostgreSQL."""
    from main import process_blob

    csv_content = b"date,product_id,quantity,price\n2026-01-01,1001,2,10.50\n2026-01-02,1002,1,5.20\n"

    mock_download = AsyncMock()
    mock_download.readall = AsyncMock(return_value=csv_content)

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    with patch("main.BlobServiceClient.from_connection_string", make_blob_service_mock(mock_download)):
        await process_blob(mock_pool, "uploads/test.csv")

    mock_conn.copy_records_to_table.assert_called()
    call_args = mock_conn.copy_records_to_table.call_args[1]["records"]
    assert len(call_args) == 2
    assert call_args[0][0] == date(2026, 1, 1)
    assert call_args[0][2] == 2
    assert call_args[0][4] == 21.0


@pytest.mark.anyio
async def test_process_blob_ignora_filas_invalidas():
    """process_blob debe ignorar filas con datos inválidos sin fallar."""
    from main import process_blob

    csv_content = b"date,product_id,quantity,price\n2026-01-01,1001,2,10.50\nFILA_INVALIDA\n2026-01-02,1002,1,5.20\n"

    mock_download = AsyncMock()
    mock_download.readall = AsyncMock(return_value=csv_content)

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    with patch("main.BlobServiceClient.from_connection_string", make_blob_service_mock(mock_download)):
        await process_blob(mock_pool, "uploads/test.csv")

    call_args = mock_conn.copy_records_to_table.call_args[1]["records"]
    assert len(call_args) == 2


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_process_message_exitoso():
    """process_message debe marcar el job como COMPLETED si todo sale bien."""
    from main import process_message

    message         = MagicMock()
    message.content = json.dumps({"job_id": "job-123", "blob_name": "uploads/test.csv"})

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    with patch("main.update_job_status", new_callable=AsyncMock) as mock_status, \
         patch("main.process_blob", new_callable=AsyncMock) as mock_blob:

        await process_message(mock_pool, message)

    assert mock_status.call_args_list[0] == call(mock_pool, "job-123", "PROCESSING")
    assert mock_status.call_args_list[1] == call(mock_pool, "job-123", "COMPLETED")
    mock_blob.assert_called_once_with(mock_pool, "uploads/test.csv")


@pytest.mark.anyio
async def test_process_message_marca_failed_si_falla():
    """process_message debe marcar el job como FAILED si process_blob lanza excepción."""
    from main import process_message

    message         = MagicMock()
    message.content = json.dumps({"job_id": "job-123", "blob_name": "uploads/test.csv"})

    mock_conn = AsyncMock()
    mock_pool = make_pool_mock(mock_conn)

    with patch("main.update_job_status", new_callable=AsyncMock) as mock_status, \
         patch("main.process_blob", new_callable=AsyncMock) as mock_blob:

        mock_blob.side_effect = Exception("Error de conexión")
        await process_message(mock_pool, message)

    last_call = mock_status.call_args_list[-1]
    assert last_call[0][2] == "FAILED"