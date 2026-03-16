#!/bin/bash
# FABOT Podcast Studio - Setup Script

set -e

echo "=========================================="
echo "FABOT Podcast Studio - Setup"
echo "=========================================="

# Cria diretórios necessários
echo "[1/6] Criando diretórios..."
mkdir -p backend/db
mkdir -p data/output
mkdir -p data/uploads
mkdir -p logs

# Instala dependências
echo "[2/6] Instalando dependências Python..."
pip install -r requirements.txt

# Copia .env se não existir
echo "[3/6] Verificando arquivo .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   Arquivo .env criado a partir do exemplo"
    echo "   ATENÇÃO: Configure suas API keys em .env"
else
    echo "   Arquivo .env já existe"
fi

# Verifica Redis
echo "[4/6] Verificando Redis..."
if command -v redis-server &> /dev/null; then
    redis-server --daemonize yes 2>/dev/null || true
    echo "   Redis iniciado"
else
    echo "   Redis não encontrado (requerido para cache)"
fi

# Verifica Docker
echo "[5/6] Verificando Docker..."
if command -v docker &> /dev/null; then
    echo "   Docker disponível"
    echo "   Para iniciar Kokoro: docker run -d -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:v0.2.2"
else
    echo "   Docker não encontrado"
fi

# Inicia backend
echo "[6/6] Iniciando Backend..."
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
echo ""
echo "=========================================="
echo "Backend iniciado em http://localhost:8000"
echo "Documentação API: http://localhost:8000/docs"
echo "=========================================="
