# FABOT Podcast Studio - Correções e Melhorias

## Resumo

Este documento descreve todas as correções implementadas para resolver problemas de estabilidade e confiabilidade do sistema.

---

## Correção 1: SQLite WAL Mode (database.py)

### Problema
Sem WAL mode, quando o backend e o worker tentam escrever no banco ao mesmo tempo, um bloqueia o outro durante escritas simultâneas.

### Solução
Adicionado evento que ativa WAL na primeira conexão com o banco:

```python
from sqlalchemy import create_engine, event

engine = create_engine(
    f"sqlite:///{settings.DATABASE_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()
```

### Verificação
```bash
python -c "
import sqlite3
conn = sqlite3.connect('backend/db/fabot.db')
print('WAL mode:', conn.execute('PRAGMA journal_mode').fetchone()[0])
conn.close()
"
# Resultado esperado: WAL mode: wal
```

---

## Correção 2: Timeout no Edge TTS (fabot_tts.py)

### Problema
Se um segmento de áudio travar na chamada da Microsoft, o job inteiro fica preso para sempre.

### Solução
Adicionado timeout de 30 segundos por segmento usando `asyncio.timeout`:

```python
import asyncio
import logging

logger = logging.getLogger(__name__)

async def synthesize_segment(
    text: str,
    speaker: str,
    keywords: list[str],
    output_path: Path,
    timeout: float = 30.0,
) -> Path:
    """Gera o MP3 de um segmento com Edge TTS com timeout."""
    config = build_ssml(text, speaker, keywords)
    communicate = edge_tts.Communicate(
        config["text"], config["voice"], rate=config["rate"], pitch=config["pitch"]
    )

    audio_data = b""
    try:
        async with asyncio.timeout(timeout):
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
    except asyncio.TimeoutError:
        logger.error(f"Timeout ({timeout}s) ao sintetizar: {text[:50]}...")
        raise TimeoutError(f"Edge TTS timeout após {timeout}s no segmento: {text[:50]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_data)
    return output_path
```

### Verificação
```bash
python -c "from backend.services.fabot_tts import *; print('Edge TTS OK')"
```

---

## Correção 3: Cleanup de arquivos temporários (fabot_tts.py)

### Problema
Cada podcast gera N arquivos `seg_*.mp3` que nunca são apagados. Com o tempo o disco enche e o sistema para de gravar áudio silenciosamente.

### Solução
Adicionada função de cleanup que deleta arquivos temporários após concatenação bem-sucedida:

```python
def cleanup_segments(output_dir: Path) -> int:
    """Remove arquivos temporários de segmento após concatenação."""
    import glob
    import os

    pattern = os.path.join(output_dir, "seg_*.mp3")
    files = glob.glob(pattern)

    removed = 0
    for f in files:
        try:
            os.remove(f)
            removed += 1
        except Exception as e:
            logger.warning(f"Não foi possível remover {f}: {e}")

    return removed
```

Chamada após exportar o áudio final:

```python
# ── Exporta MP3 final ──
# ... (código de export)

# ── Cleanup arquivos temporários ──
if final_path.exists() and final_path.stat().st_size > 0:
    removed = cleanup_segments(output_dir)
    if removed > 0:
        print(f"🗑️  Cleanup: {removed} arquivos temp removidos")

return final_path
```

---

## Correção 4: Redis Keepalive (podcast_worker.py)

### Problema
A conexão Redis cai silenciosamente depois de inatividade. O worker para de processar jobs mas continua "rodando" pelo systemd.

### Solução
Adicionados parâmetros de timeout e retry na configuração do RedisSettings:

```python
class WorkerSettings:
    functions = ["process_podcast_job", "start_tts_job"]
    redis_settings = None
    max_jobs = 5
    timeout = 3600

    @classmethod
    def get_redis_settings(cls):
        from arq.connections import RedisSettings

        return RedisSettings(
            host="localhost",
            port=6379,
            conn_timeout=10,      # timeout para conectar
            conn_retries=5,        # tentativas antes de desistir
            conn_retry_delay=1,   # espera entre tentativas
        )
```

### Verificação
```bash
python -c "
from backend.workers.podcast_worker import WorkerSettings
rs = WorkerSettings.get_redis_settings()
print(f'conn_timeout: {rs.conn_timeout}, conn_retries: {rs.conn_retries}')
"
# Resultado esperado: conn_timeout: 10, conn_retries: 5
```

---

## Correção 5: Retry para JSON inválido (llm.py)

### Problema
O Gemini às vezes retorna JSON malformado. O sistema falhava em vez de tentar novamente.

### Solução
Criada função `parse_llm_json()` que faz parsing inteligente com regex para extrair JSON de respostas malformadas:

```python
def parse_llm_json(response_text: str) -> dict:
    """
    Parse JSON da resposta do LLM com limpeza automática.
    LLMs às vezes retornam JSON com markdown ou texto antes/depois.
    """
    if not response_text:
        raise ValueError("Resposta do LLM está vazia")

    text = response_text.strip()

    # Remover blocos markdown ```json ... ```
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    # Tentar parse direto
    try:
        data = json.loads(text)
        if "segments" in data and len(data.get("segments", [])) > 0:
            return data
    except json.JSONDecodeError:
        pass

    # Tentar extrair JSON do meio do texto
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if "segments" in data and len(data.get("segments", [])) > 0:
                logger.info("JSON extraído com regex — resposta tinha texto extra")
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível extrair JSON válido da resposta do LLM")
```

Agora todos os providers (Groq, Gemini, Ollama, GLM) usam esta função e fazem retry automático:

```python
# Exemplo no GroqProvider:
try:
    script_data = parse_llm_json(content)
except ValueError as e:
    logger.error(f"JSON inválido: {e}")
    continue  # faz retry no loop
```

### Verificação
```bash
python -c "from backend.services.llm import *; print('LLM OK')"
```

---

## Sistema de Inicialização Confiável

### Script start_reliable.sh

Criado script que verifica todos os serviços antes de iniciar:

```bash
#!/bin/bash
# /home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio/start_reliable.sh

# Verifica Redis, Backend, Worker (systemd), Frontend
# Só continua se cada serviço estiver pronto
```

### Worker via systemd

O worker agora é gerenciado pelo systemd, que reinicia automaticamente em 3 segundos se morrer:

```ini
# /etc/systemd/system/fabot-worker.service
[Unit]
Description=FABOT ARQ Worker
After=redis.service

[Service]
Type=simple
User=fabiorjvr
WorkingDirectory=/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio
ExecStart=/home/fabiorjvr/fabot-start-worker.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Wrapper script para evitar problemas com caminhos com espaços:

```bash
#!/bin/bash
# /home/fabiorjvr/fabot-start-worker.sh
export PYTHONPATH="/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio"
export REDIS_URL=redis://localhost:6379
cd "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio"
exec .venv/bin/python backend/run_worker.py
```

---

## Timeout no Frontend (App.jsx)

### Problema
O frontend ficava esperando eternamente se o job travasse.

### Solução
Adicionado timeout de 10 minutos em todos os polliings:

```javascript
const MAX_POLL_TIME = 10 * 60 * 1000; // 10 minutos

const pollScript = async () => {
  try {
    if (Date.now() - pollStartTime > MAX_POLL_TIME) {
      updateActiveJob(jobId, { 
        status: 'FAILED', 
        current_step: 'Tempo limite excedido (10 min). Verifique o Worker e tente novamente.' 
      });
      return;
    }
    // ... resto do polling
  }
};
```

---

## Cancel Funcional (jobs.py)

### Problema
O botão cancelar só marcava no banco, mas o job continuava no Redis.

### Solução
Agora cancela tanto no banco quanto no Redis:

```python
@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    # ... validações ...
    
    job.status = "CANCELLED"
    job.error_message = "Cancelado pelo usuário"
    db.commit()

    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        job_key = f"arq:job:{job_id}"
        r.delete(job_key)
        logger.info(f"Job {job_id} removido do Redis")
    except Exception as e:
        logger.warning(f"Não foi possível cancelar job no Redis: {e}")

    return {"status": "cancelled", "job_id": job_id}
```

---

## Health Check do Worker (health.py)

### Problema
Não havia como saber se o worker estava rodando via interface.

### Solução
Adicionado verificação do worker no health check:

```python
try:
    import subprocess
    result = subprocess.run(
        ["pgrep", "-f", "run_worker.py"],
        capture_output=True,
        text=True
    )
    worker_alive = result.returncode == 0

    if worker_alive:
        results.append(HealthStatus(service="worker", status="UP", details=None))
    else:
        results.append(HealthStatus(
            service="worker",
            status="DOWN",
            details="Worker não está rodando"
        ))
except Exception as e:
    results.append(HealthStatus(service="worker", status="DOWN", details=str(e)))
```

---

## Verificação Final

Execute este script para verificar todas as correções:

```bash
# 1. Reiniciar backend
pkill -f uvicorn
sleep 2
cd "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio"
nohup .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 >> logs/backend.log 2>&1 &
sleep 4

# 2. Confirmar worker rodando
sudo systemctl restart fabot-worker
sleep 3
sudo systemctl status fabot-worker | grep "Active:"

# 3. Confirmar WAL ativo
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('backend/db/fabot.db')
print('WAL:', conn.execute('PRAGMA journal_mode').fetchone()[0])
conn.close()
"

# 4. Health check completo
curl -s http://localhost:8000/health/ | python3 -m json.tool

# 5. Verificar imports sem erro
.venv/bin/python -c "
from backend.services.fabot_tts import *
from backend.services.llm import *
from backend.workers.podcast_worker import *
print('Todos imports OK')
"
```

### Resultados esperados:
- Worker: `Active: active (running)`
- WAL: `wal`
- Health: Redis UP, Worker UP, Ollama UP
- Imports: `Todos imports OK`

---

## Remoção do Kokoro

O Kokoro (TTS local via Docker) foi removido do projeto porque:

1. Nunca foi instalado ou usado
2. O Edge TTS já é usado para síntese de voz
3. Só causava confusão no health check (mostrava vermelho)

### Arquivos modificados:
- `backend/routers/health.py` - bloco do Kokoro removido
- `frontend/src/components/Header.jsx` - badge "Edge TTS" removido
- `frontend/src/hooks/useHealthCheck.js` - referência ao kokoro removida

---

## Arquivos Modificados

| Arquivo | Correção |
|---------|----------|
| `backend/database.py` | WAL mode |
| `backend/services/fabot_tts.py` | Timeout + Cleanup |
| `backend/workers/podcast_worker.py` | Redis keepalive |
| `backend/services/llm.py` | Retry JSON |
| `backend/routers/jobs.py` | Cancel funcional |
| `backend/routers/health.py` | Worker health + Kokoro removido |
| `frontend/src/App.jsx` | Timeout no polling |
| `frontend/src/components/Header.jsx` | Worker badge + Kokoro removido |
| `frontend/src/hooks/useHealthCheck.js` | Worker status + Kokoro removido |
| `fabot-studio/start_reliable.sh` | Script de inicialização |

---

## Problemas Resolvidos

| Problema | Impacto | Status |
|----------|---------|--------|
| SQLite sem WAL | Crítico - travava em escritas simultâneas | ✅ Resolvido |
| Edge TTS sem timeout | Crítico - "Gerando..." eterno | ✅ Resolvido |
| Arquivos temp não deletados | Crítico - disco cheio | ✅ Resolvido |
| Redis sem keepalive | Alto - worker parava silenciosamente | ✅ Resolvido |
| JSON inválido sem retry | Alto - falha冤枉 | ✅ Resolvido |
| Worker via nohup | Médio - worker morria | ✅ Resolvido (systemd) |
| Health check incompleto | Médio - sem visibilidade | ✅ Resolvido |
| Polling sem timeout | Médio - espera eterna | ✅ Resolvido |

---

## Correção 6: asyncio.new_event_loop() Removido (jobs.py)

### Problema
Criar novos event loops dentro de BackgroundTasks conflita com o event loop do FastAPI, causando travamentos quando 2 jobs rodam simultaneamente.

### Solução
Substituir `asyncio.new_event_loop()` + `set_event_loop()` + `run_until_complete()` por `asyncio.run()`:

```python
# ANTES (errado):
def run_podcast_job_background(job_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(process_podcast_job({}, job_id))
    finally:
        loop.close()

# DEPOIS (correto):
def run_podcast_job_background(job_id: str):
    try:
        result = asyncio.run(process_podcast_job({}, job_id))
    except Exception as e:
        logger.error(f"Erro ao executar job {job_id}: {e}")
        raise
```

### Verificação
```bash
grep -r "new_event_loop" backend/
# Resultado esperado: nenhum resultado (removido)
```

---

## Correção 7: TTS Paralelo (fabot_tts.py)

### Problema
Edge TTS processava segmentos sequencialmente. 80 segmentos × 2s = 160 segundos (quase 3 minutos).

### Solução
Usar `asyncio.gather()` com `Semaphore(5)` para processar até 5 segmentos simultaneamente:

```python
# Máximo de 5 requisições simultâneas ao Edge TTS
semaphore = asyncio.Semaphore(5)

async def synth_with_semaphore(i: int, seg: dict) -> dict | None:
    speaker = seg.get("speaker", "William")
    text = seg.get("text", "").strip()
    if not text:
        return None
    
    seg_path = output_dir / f"seg_{i:03d}_{speaker.lower()}.mp3"
    
    async with semaphore:
        await synthesize_segment(text, speaker, keywords, seg_path)
    
    return {
        "path": seg_path,
        "speaker": speaker,
        ...
    }

# Dispara TODOS os segmentos em paralelo
tasks = [synth_with_semaphore(i, seg) for i, seg in enumerate(segments)]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### Resultado
- Antes: 80 segmentos × 2s = 160 segundos
- Depois: ~32 segundos (5x mais rápido)

### Verificação
```bash
python -c "from backend.services.fabot_tts import *; print('TTS OK')"
```

---

## Correção 8: API Keys Removidas do Código (config.py, llm.py)

### Problema
API keys estavam hardcoded no código:
- `config.py`: `GLM_API_KEY = "6b754c80b0a848909600eadaa4ee5818"`
- `llm.py`: fallback com API key

### Solução
Todas as chaves agora vêm exclusivamente do arquivo `.env`:

```python
# config.py
GLM_API_KEY = os.getenv("GLM_API_KEY", "")

# llm.py
self.api_key = settings.GLM_API_KEY
if not self.api_key:
    raise ValueError("GLM_API_KEY não configurada no arquivo .env")
```

### Verificação
```bash
grep -r "6b754c80" backend/*.py
# Resultado esperado: nenhum resultado
```

---

## Correção 9: URLs Centralizadas no Frontend (frontend/src/api.js)

### Problema
12+ URLs `http://localhost:8000` espalhadas no frontend, impossível fazer deploy em produção.

### Solução
Criar arquivo `frontend/src/api.js` com URLs centralizadas:

```javascript
// frontend/src/api.js
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const urls = {
  jobs: {
    get: (id) => `${API_BASE}/jobs/${id}`,
    history: `${API_BASE}/jobs/history`,
    start: (id) => `${API_BASE}/jobs/${id}/start`,
    // ...
  }
};
```

Para produção, basta definir `VITE_API_URL=https://api.fabot.com.br` no `.env`.

### Arquivos criados
- `frontend/src/api.js` - URLs centralizadas
- `.env.example` - Template de variáveis de ambiente

---

## Correção 10: CORS Restritivo (main.py)

### Problema
CORS completamente aberto: `allow_origins=["*"]` permite qualquer site chamar o backend.

### Solução
Usar configuração do settings:

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["http://localhost:3000", ...]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# config.py
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
```

Para produção, adicionar o domínio:
```python
CORS_ORIGINS = ["http://localhost:3000", "https://fabot.com.br"]
```

---

## Resumo das Correções (Todas)

| # | Correção | Arquivo | Prioridade |
|---|----------|---------|------------|
| 1 | SQLite WAL Mode | database.py | 🔴 Crítica |
| 2 | Edge TTS Timeout | fabot_tts.py | 🔴 Crítica |
| 3 | Cleanup arquivos temp | fabot_tts.py | 🔴 Crítica |
| 4 | Redis Keepalive | podcast_worker.py | 🟡 Alta |
| 5 | Retry JSON LLM | llm.py | 🟡 Alta |
| 6 | asyncio.run() | jobs.py | 🔴 Crítica |
| 7 | TTS Paralelo | fabot_tts.py | 🔴 Crítica |
| 8 | API Keys removidas | config.py, llm.py | 🔴 Crítica |
| 9 | URLs centralizadas | frontend/src/api.js | 🟡 Alta |
| 10 | CORS restritivo | main.py | 🟡 Alta |

---

## Verificação Final

```bash
# 1. Verificar imports
cd fabot-studio
.venv/bin/python -c "
from backend.services.fabot_tts import *
from backend.services.llm import *
from backend.workers.podcast_worker import *
print('✅ Todos imports OK')
"

# 2. Verificar WAL
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('backend/db/fabot.db')
print('✅ WAL:', conn.execute('PRAGMA journal_mode').fetchone()[0])
conn.close()
"

# 3. Verificar API keys removidas
grep -r "6b754c80" backend/*.py || echo "✅ API keys não estão no código"

# 4. Health check
curl -s http://localhost:8000/health/ | python3 -m json.tool
```
