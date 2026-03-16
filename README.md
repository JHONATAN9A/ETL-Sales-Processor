# ETL Sales Processor

Sistema ETL asíncrono para procesar archivos CSV de ventas de millones de registros, construido con FastAPI, Azure Storage (Azurite local), PostgreSQL, y automatización con N8N.

---

## Arquitectura

El sistema está compuesto por 4 capas principales:

```
Cliente → FastAPI → Azure Blob Storage
                 → Azure Queue Storage → Worker → PostgreSQL
                                                      ↑
                                          N8N (resumen periódico)
```

### Componentes

| Componente | Responsabilidad |
|---|---|
| **FastAPI** | Recibe el CSV, lo sube al Blob, encola el job, devuelve `job_id` |
| **Azure Blob Storage** | Almacena los archivos CSV (Azurite en local) |
| **Azure Queue Storage** | Cola de mensajes para desacoplar la API del procesamiento |
| **Worker** | Escucha la cola, descarga el CSV por chunks, inserta en PostgreSQL |
| **PostgreSQL** | Almacena `jobs`, `sales`, y `sales_daily_summary` |
| **N8N** | Workflow periódico que calcula el resumen diario de ventas |

### Flujo completo

1. El cliente hace `POST /api/upload` con un archivo CSV
2. La API sube el archivo a Azure Blob Storage
3. La API registra el job como `PENDING` en PostgreSQL
4. La API manda un mensaje a Azure Queue con `job_id` y `blob_name`
5. La API responde inmediatamente con el `job_id`
6. El Worker detecta el mensaje en la cola
7. El Worker descarga el CSV del Blob y lo procesa chunk a chunk
8. El Worker inserta los datos en PostgreSQL en batches de 5000 filas usando `COPY`
9. El Worker actualiza el job a `COMPLETED` (o `FAILED` si hay error)
10. N8N consulta periódicamente los jobs completados y actualiza `sales_daily_summary`

---

## Sustentación

El siguiente video presenta la arquitectura del sistema, las decisiones técnicas tomadas y una demo en vivo del flujo completo.

<div>
    <a href="https://www.loom.com/share/a7a2de09fed44b3cbdd579ba8cb2cf55">
      <p>Presentación de un sistema de carga asíncrona de datos desde archivos CSV a PostgreSQL - Watch Video</p>
    </a>
    <a href="https://www.loom.com/share/a7a2de09fed44b3cbdd579ba8cb2cf55">
      <img style="max-width:100vw;" src="https://cdn.loom.com/sessions/thumbnails/a7a2de09fed44b3cbdd579ba8cb2cf55-8cdeedb47a3b7463-full-play.gif#t=0.1">
    </a>
  </div>

## Decisiones técnicas

### ¿Por qué no cargar el CSV completo en memoria?

El Worker usa `csv.DictReader` sobre el contenido descargado en chunks. Nunca materializa el archivo completo — procesa línea por línea y acumula un batch de 5000 filas. Cuando el batch se llena, lo inserta y lo limpia. El consumo de memoria es constante independientemente del tamaño del archivo.

### ¿Cómo se evita saturar PostgreSQL?

Se usa `asyncpg.copy_records_to_table` en lugar de `INSERT` fila por fila. `COPY` es el mecanismo más eficiente de inserción masiva en PostgreSQL — reduce drásticamente el número de round-trips y el overhead de parsing SQL. El `BATCH_SIZE=5000` controla la memoria usada en cada operación. El pool de conexiones (`min_size=2, max_size=10`) limita la concurrencia.

### ¿Por qué Azure Queue Storage?

Desacopla completamente la API del Worker. La API responde en milisegundos sin importar el tamaño del archivo. Si el Worker falla, el mensaje permanece en la cola y puede ser reprocesado. Permite escalar el Worker horizontalmente con múltiples réplicas sin cambiar código (Azure Queue garantiza que cada mensaje lo consume un solo Worker).

### ¿Por qué Azurite para desarrollo local?

Azurite es el emulador oficial de Microsoft para Azure Storage. Usa exactamente el mismo SDK (`azure-storage-blob`, `azure-storage-queue`) que Azure real. Para pasar a producción solo se cambia la `AZURE_STORAGE_CONNECTION_STRING` — el código no toca una sola línea.

### Estrategia de inserción masiva

```
CSV → DictReader (línea por línea) → batch (5000 filas) → COPY → PostgreSQL
```

`COPY` es entre 5 y 10 veces más rápido que `INSERT` masivo. Para 1 millón de filas el Worker completa el procesamiento en aproximadamente 20 segundos.

### Diseño de capas

```
backend/
├── config/      → Settings y conexión a la DB
├── database/    → Modelos SQLAlchemy
├── schemas/     → Schemas Pydantic (request/response)
├── services/    → Lógica de negocio (blob, queue, jobs)
└── routers/     → Endpoints FastAPI

worker/
└── main.py      → Loop de escucha, procesamiento y inserción
```

---

## Estructura del proyecto

```
ETL-Sales-Processor/
├── backend/
│   ├── config/
│   │   ├── settings.py
│   │   └── connection.py
│   ├── database/
│   │   └── models.py
│   ├── schemas/
│   │   └── etl_schema.py
│   ├── services/
│   │   └── etl_service.py
│   ├── routers/
│   │   └── etl_route.py
│   ├── tests/
│   │   ├── test_routes.py
│   │   └── test_services.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── worker/
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_worker.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── infra/
│   └── scripts/
│       ├── init_azurite.py
│       ├── requirements.txt
│       └── Dockerfile
├── files/
│   ├── generate_csv.py
│   └── test_large.csv
├── workflow/
│   └── n8n.json
├── docker-compose.yml
├── run_tests.sh
└── README.md
```

---

## Base de datos

### Tabla `jobs`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | UUID | Identificador único del job |
| `blob_name` | TEXT | Ruta del archivo en Blob Storage |
| `status` | TEXT | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `error` | TEXT | Mensaje de error si falló |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Última actualización |

### Tabla `sales`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | BIGSERIAL | Primary key autoincremental |
| `date` | DATE | Fecha de la venta |
| `product_id` | INTEGER | Identificador del producto |
| `quantity` | INTEGER | Cantidad vendida |
| `price` | NUMERIC(10,2) | Precio unitario |
| `total` | NUMERIC(10,2) | `quantity * price` |

### Tabla `sales_daily_summary`

| Columna | Tipo | Descripción |
|---|---|---|
| `date` | DATE | Fecha (primary key) |
| `total_sales` | NUMERIC(12,2) | Suma de ventas del día |
| `total_quantity` | INTEGER | Suma de cantidades del día |
| `updated_at` | TIMESTAMPTZ | Última actualización por N8N |

---

## API

### `POST /api/upload`

Recibe un archivo CSV y lo procesa de forma asíncrona.

**Request:**
```bash
curl -X POST http://localhost:8001/api/upload \
  -F "file=@ventas.csv"
```

**Response `202`:**
```json
{
  "job_id": "e54e290f-0c58-41b1-81b9-c63ae15c0b39",
  "status": "PENDING"
}
```

**Errores:**
- `400` — El archivo no es un CSV
- `500` — Error al subir o encolar

### `GET /api/job/{job_id}`

Consulta el estado de procesamiento de un job.

**Request:**
```bash
curl http://localhost:8001/api/job/e54e290f-0c58-41b1-81b9-c63ae15c0b39
```

**Response `200`:**
```json
{
  "job_id": "e54e290f-0c58-41b1-81b9-c63ae15c0b39",
  "blob_name": "uploads/e54e290f/ventas.csv",
  "status": "COMPLETED",
  "error": null,
  "created_at": "2026-03-16T01:48:35+00:00",
  "updated_at": "2026-03-16T01:49:10+00:00"
}
```

**Errores:**
- `404` — Job no encontrado

---

## Cómo ejecutar el sistema

### Requisitos previos

- Docker y Docker Compose
- Python 3.11+ (para correr los tests localmente)

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/ETL-Sales-Processor.git
cd ETL-Sales-Processor
```

### 2. Levantar todos los servicios

```bash
docker compose up -d
```

Esto levanta en orden:
1. `azurite` — emulador de Azure Storage
2. `init-azurite` — crea el bucket y la queue
3. `postgres` — base de datos
4. `api` — FastAPI en `http://localhost:8001`
5. `worker` — procesador de jobs
6. `n8n` — automatización en `http://localhost:5678`

### 3. Verificar que todo está corriendo

```bash
docker compose ps
docker compose logs api
docker compose logs worker
```

### 4. Generar un CSV de prueba

```bash
cd files
python generate_csv.py   # genera test_large.csv con 1,000,000 filas
```

### 5. Subir un archivo

```bash
curl -X POST http://localhost:8001/api/upload \
  -F "file=@files/test_large.csv"
```

### 6. Consultar el estado

```bash
curl http://localhost:8001/api/job/{job_id}
```

### 7. Verificar los datos en PostgreSQL

```bash
docker compose exec postgres psql -U user -d salesdb -c "SELECT * FROM jobs;"
docker compose exec postgres psql -U user -d salesdb -c "SELECT COUNT(*) FROM sales;"
docker compose exec postgres psql -U user -d salesdb -c "SELECT * FROM sales_daily_summary ORDER BY date;"
```

### 8. Configurar N8N

1. Abrir `http://localhost:5678`
2. Ir a **Settings → Import workflow**
3. Importar el archivo `workflow/n8n.json`
4. Activar el workflow con el toggle **Active**

---

## Pruebas unitarias

### Correr todos los tests

```bash
./run_tests.sh
```

### Tests incluidos

**Backend (9 tests):**
- `test_upload_csv_exitoso` — POST /upload responde con job_id y PENDING
- `test_upload_archivo_no_csv` — rechaza archivos que no son CSV
- `test_upload_falla_servicio` — maneja errores internos con 500
- `test_get_job_existente` — devuelve el status del job
- `test_get_job_no_existe` — devuelve 404 si el job no existe
- `test_handle_upload_llama_servicios_en_orden` — blob → db → queue
- `test_handle_upload_genera_job_id_unico` — cada upload genera un UUID distinto
- `test_get_job_retorna_job_existente` — retorna el modelo correcto
- `test_get_job_retorna_none_si_no_existe` — retorna None correctamente

**Worker (7 tests):**
- `test_update_job_status_completed` — ejecuta el UPDATE con los parámetros correctos
- `test_update_job_status_failed_con_error` — pasa el mensaje de error al UPDATE
- `test_flush_batch_llama_copy_records` — usa COPY con las columnas correctas
- `test_process_blob_inserta_filas_correctamente` — parsea y calcula el total
- `test_process_blob_ignora_filas_invalidas` — no falla con datos corruptos
- `test_process_message_exitoso` — ciclo PROCESSING → COMPLETED
- `test_process_message_marca_failed_si_falla` — ciclo PROCESSING → FAILED

---

## Workflow N8N

El workflow `ETL - Resumen diario de ventas` corre cada 15 minutos y:

1. Consulta los jobs con `status = COMPLETED` en PostgreSQL
2. Si hay jobs completados, calcula el total de ventas agrupado por día
3. Hace upsert en `sales_daily_summary` con `ON CONFLICT DO UPDATE`

El nodo `IF` garantiza que el cálculo solo corre cuando hay datos nuevos.

---

## Variables de entorno

### Backend (`.env`)

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/salesdb
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
AZURE_BLOB_CONTAINER=csv-uploads
AZURE_QUEUE_NAME=csv-jobs
```

### Worker (`.env`)

```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/salesdb
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;..."
AZURE_BLOB_CONTAINER=csv-uploads
AZURE_QUEUE_NAME=csv-jobs
BATCH_SIZE=5000
```

---

