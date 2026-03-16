#!/bin/bash

set -e

echo "================================"
echo "Corriendo tests del backend..."
echo "================================"
cd backend
pip install -r requirements.txt --quiet
pip install pytest pytest-asyncio anyio httpx --quiet
PYTHONPATH=. pytest tests/ -v
cd ..

echo "================================"
echo "Corriendo tests del worker..."
echo "================================"
cd worker
pip install -r requirements.txt --quiet
pip install pytest pytest-asyncio anyio --quiet
PYTHONPATH=. pytest tests/ -v
cd ..

echo "================================"
echo "Todos los tests pasaron ✅"
echo "================================"