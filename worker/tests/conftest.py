"""Configura las variables de entorno necesarias para los tests del Worker."""

import os
import pytest

# Inyecta las variables ANTES de que main.py las lea al importarse
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=test;BlobEndpoint=http://localhost:10000/devstoreaccount1;QueueEndpoint=http://localhost:10001/devstoreaccount1;")
os.environ.setdefault("AZURE_BLOB_CONTAINER", "csv-uploads")
os.environ.setdefault("AZURE_QUEUE_NAME", "csv-jobs")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/salesdb")
os.environ.setdefault("BATCH_SIZE", "5000")