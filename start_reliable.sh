#!/bin/bash
set -e

PROJECT_DIR="/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio"
mkdir -p "$PROJECT_DIR/logs"

echo "========================================="
echo "FABOT Podcast Studio - Iniciando..."
echo "========================================="

echo ""
echo "▶ Verificando Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis está rodando"
else
    echo "⚠️  Redis não está rodando, iniciando..."
    redis-server --daemonize yes
    sleep 2
    if redis-cli ping > /dev/null 2>&1; then
        echo "✅ Redis iniciado"
    else
        echo "❌ ERRO: Não foi possível iniciar o Redis"
        exit 1
    fi
fi

echo ""
echo "▶ Verificando Backend (porta 8000)..."
if curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "✅ Backend já está rodando"
else
    echo "📦 Iniciando Backend..."
    cd "$PROJECT_DIR"
    nohup .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
        >> logs/backend.log 2>&1 &
    sleep 4
    if curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
        echo "✅ Backend iniciado"
    else
        echo "❌ ERRO: Backend falhou ao iniciar. Verifique logs/backend.log"
        exit 1
    fi
fi

echo ""
echo "▶ Verificando Worker..."
if sudo systemctl is-active --quiet fabot-worker 2>/dev/null; then
    echo "✅ Worker está rodando via systemd"
else
    echo "📦 Iniciando Worker..."
    sudo systemctl start fabot-worker
    sleep 3
    if sudo systemctl is-active --quiet fabot-worker 2>/dev/null; then
        echo "✅ Worker iniciado via systemd"
    else
        echo "❌ ERRO: Worker falhou ao iniciar"
        exit 1
    fi
fi

echo ""
echo "▶ Verificando Frontend (porta 3000)..."
if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend já está rodando"
else
    echo "📦 Iniciando Frontend..."
    cd "$PROJECT_DIR/frontend"
    nohup npm run dev >> ../logs/frontend.log 2>&1 &
    sleep 5
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        echo "✅ Frontend iniciado"
    else
        echo "❌ ERRO: Frontend falhou ao iniciar. Verifique logs/frontend.log"
        exit 1
    fi
fi

echo ""
echo "========================================="
echo "🎙️  FABOT Podcast Studio - Online!"
echo "========================================="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo ""
echo "Status dos serviços:"
echo "  Redis:   $(redis-cli ping 2>/dev/null | grep -q PONG && echo '✅' || echo '❌')"
echo "  Backend: $(curl -sf http://localhost:8000/health/ > /dev/null && echo '✅' || echo '❌')"
echo "  Worker:  $(sudo systemctl is-active --quiet fabot-worker 2>/dev/null && echo '✅' || echo '❌')"
echo "  Front:   $(curl -sf http://localhost:3000 > /dev/null && echo '✅' || echo '❌')"
echo ""
