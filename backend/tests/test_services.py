"""Tests para los servicios del ETL."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# handle_upload
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_handle_upload_llama_servicios_en_orden():
    """handle_upload debe llamar blob, db y queue en ese orden."""
    from services.etl_service import handle_upload

    mock_db   = AsyncMock()
    mock_file = MagicMock()
    mock_file.filename = "ventas.csv"

    with patch("services.etl_service.upload_to_blob", new_callable=AsyncMock) as mock_blob, \
         patch("services.etl_service.create_job", new_callable=AsyncMock) as mock_create, \
         patch("services.etl_service.send_queue_message", new_callable=AsyncMock) as mock_queue:

        job_id = await handle_upload(mock_db, mock_file)

    assert job_id is not None
    mock_blob.assert_called_once()
    mock_create.assert_called_once()
    mock_queue.assert_called_once()


@pytest.mark.anyio
async def test_handle_upload_genera_job_id_unico():
    """handle_upload debe generar job_ids únicos en cada llamada."""
    from services.etl_service import handle_upload

    mock_db   = AsyncMock()
    mock_file = MagicMock()
    mock_file.filename = "ventas.csv"

    with patch("services.etl_service.upload_to_blob", new_callable=AsyncMock), \
         patch("services.etl_service.create_job", new_callable=AsyncMock), \
         patch("services.etl_service.send_queue_message", new_callable=AsyncMock):

        job_id_1 = await handle_upload(mock_db, mock_file)
        job_id_2 = await handle_upload(mock_db, mock_file)

    assert job_id_1 != job_id_2


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_job_retorna_job_existente():
    """get_job debe retornar el job cuando existe."""
    from services.etl_service import get_job
    from database.models import JobModel

    job_mock = JobModel(id="abc-123", blob_name="uploads/abc.csv", status="PENDING")

    mock_db     = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = job_mock
    mock_db.execute.return_value = mock_result

    result = await get_job(mock_db, "abc-123")

    assert result.id == "abc-123"
    assert result.status == "PENDING"


@pytest.mark.anyio
async def test_get_job_retorna_none_si_no_existe():
    """get_job debe retornar None cuando el job no existe."""
    from services.etl_service import get_job

    mock_db     = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await get_job(mock_db, "no-existe")

    assert result is None