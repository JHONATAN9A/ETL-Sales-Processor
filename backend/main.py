"""ETL Sales Pipeline — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.connection import engine
from database.models import Base
from routers.etl_route import router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: crea las tablas si no existen. Shutdown: logging."""
    logger.info("Iniciando ETL Sales Pipeline — creando tablas si no existen")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tablas listas")

    yield

    logger.info("Apagando ETL Sales Pipeline")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ETL Sales Pipeline API",
    description="Recibe archivos CSV de ventas, los procesa de forma asíncrona y los persiste en PostgreSQL.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all para excepciones no manejadas."""
    logger.exception(
        "Excepción no manejada en %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "INTERNAL_SERVER_ERROR"},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(router, prefix="/api")
