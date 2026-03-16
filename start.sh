#!/bin/bash
set -e

echo "========================================="
echo "FABOT Podcast Studio - Iniciando..."
echo "========================================="

if ! command -v docker &> /dev/null; then
    echo "ERRO: Docker não está instalado."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERRO: Docker Compose não está instalado."
    exit 1
fi

echo "Criando diretórios..."
mkdir -p data/uploads data/output data/db logs

if [ ! -f .env ]; then
    echo "Criando .env a partir do .env.example..."
    cp .env.example .env
fi

echo "Iniciando serviços Docker..."
docker compose up -d

echo "Aguardando health checks..."
MAX_WAIT=60
ELAPSED=0

check_service() {
    local service=$1
    local url=$2
    while [ $ELAPSED -lt $MAX_WAIT ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo "✓ $service está UP"
            return 0
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done
    echo "✗ $service está DOWN (timeout)"
    return 1
}

check_service "Backend" "http://localhost:8000/health" || true
check_service "Frontend" "http://localhost:3000" || true

echo ""
echo "========================================="
echo "Serviços iniciados!"
echo "========================================="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "Kokoro:   http://localhost:8880"
echo ""

docker compose ps
