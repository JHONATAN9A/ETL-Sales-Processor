"""Tests para los endpoints de la API."""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_upload_csv_exitoso(client):
    """POST /upload con CSV válido debe retornar job_id y status PENDING."""
    with patch("routers.etl_route.handle_upload", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "test-job-123"

        response = await client.post(
            "/api/upload",
            files={"file": ("ventas.csv", b"date,product_id,quantity,price\n2026-01-01,1001,2,10.5", "text/csv")},
        )

    assert response.status_code == 202
    assert response.json()["job_id"] == "test-job-123"
    assert response.json()["status"] == "PENDING"


@pytest.mark.anyio
async def test_upload_archivo_no_csv(client):
    """POST /upload con archivo no CSV debe retornar 400."""
    response = await client.post(
        "/api/upload",
        files={"file": ("datos.txt", b"contenido", "text/plain")},
    )

    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


@pytest.mark.anyio
async def test_upload_falla_servicio(client):
    """POST /upload cuando el servicio falla debe retornar 500."""
    with patch("routers.etl_route.handle_upload", new_callable=AsyncMock) as mock_upload:
        mock_upload.side_effect = Exception("Error de conexión")

        response = await client.post(
            "/api/upload",
            files={"file": ("ventas.csv", b"date,product_id,quantity,price", "text/csv")},
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/job/{job_id}
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_get_job_existente(client):
    """GET /job/{job_id} con job existente debe retornar el status."""
    from datetime import datetime, timezone
    from database.models import JobModel

    job_mock = JobModel(
        id="test-job-123",
        blob_name="uploads/test-job-123/ventas.csv",
        status="COMPLETED",
        error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with patch("routers.etl_route.get_job", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = job_mock

        response = await client.get("/api/job/test-job-123")

    assert response.status_code == 200
    assert response.json()["job_id"] == "test-job-123"
    assert response.json()["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_get_job_no_existe(client):
    """GET /job/{job_id} con job inexistente debe retornar 404."""
    with patch("routers.etl_route.get_job", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None

        response = await client.get("/api/job/no-existe")

    assert response.status_code == 404