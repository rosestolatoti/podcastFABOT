# FABOT Studio — Relatório de Auditoria e Correções
**Data:** 20/03/2026  
**Versão:** 2.0.0  
**Status geral:** ✅ Sistema operacional

---

## 1. Status do Sistema (verificado ao vivo)

| Serviço | Status | Detalhe |
|---------|--------|---------|
| Backend FastAPI | ✅ UP | `{"version":"2.0.0"}` |
| Redis | ✅ UP | Conectado em localhost:6379 |
| SQLite WAL | ✅ ATIVO | `journal_mode=wal, synchronous=NORMAL` |
| Ollama | ✅ UP | Status 200 |
| Worker ARQ | ✅ UP | Processo ativo |
| Disco | ✅ OK | 23.8 GB livres |
| CORS localhost:3000 | ✅ OK | Header `access-control-allow-origin: http://localhost:3000` |
| CORS origem externa | ✅ BLOQUEADO | `hacker.com` não recebe allow-origin |
| Path traversal `/audio/../../etc/passwd` | ✅ BLOQUEADO | HTTP 403 Forbidden |
| API Keys hardcoded | ✅ LIMPO | Nenhuma key no código |

---

## 2. Correções Originais (10) — Validação

| # | Correção | Status | Verificação |
|---|----------|--------|-------------|
| 1 | SQLite WAL mode | ✅ OK | `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` confirmados ao vivo |
| 2 | Edge TTS Timeout 30s | ✅ OK | `asyncio.timeout(30.0)` em `fabot_tts.py` |
| 3 | Cleanup arquivos temp | ✅ OK | `cleanup_segments()` executa após `final.mp3` existir |
| 4 | Redis keepalive | ✅ OK | `conn_timeout=10, conn_retries=5, conn_retry_delay=1` |
| 5 | Retry JSON LLM | ✅ OK | `parse_llm_json()` limpa markdown + regex fallback |
| 6 | `asyncio.run()` | ✅ OK | Substituiu `new_event_loop()` em `jobs.py` |
| 7 | TTS Paralelo 5x | ✅ OK | `Semaphore(5)` + `asyncio.gather(*tasks, return_exceptions=True)` |
| 8 | API Keys no `.env` | ✅ OK | `os.getenv()` em todos os providers — sem hardcode |
| 9 | URLs centralizadas | ⚠️ PARCIAL | `api.js` existe mas frontend usa diretamente `http://localhost:8000` — **não é problema para uso local** |
| 10 | CORS restritivo | ✅ OK | Apenas `localhost:3000` e `127.0.0.1:3000` permitidos |

---

## 3. Bugs Corrigidos nesta Auditoria

### BUG 1 — Rota `/history` duplicada (`jobs.py`) ✅ CORRIGIDO
**Severidade:** FATAL — a segunda rota nunca executava  
**Problema:** Duas funções `@router.get("/history")` no mesmo arquivo. FastAPI usa sempre a primeira, ignorando a segunda com filtros (`q`, `category`, `playlist`, `favorites`).  
**Correção:** Unificado em uma única rota que aceita todos os parâmetros opcionais.  
**Verificado:** `GET /jobs/history?q=teste&favorites=false` retorna resultados filtrados corretamente.

```python
# ANTES: duas rotas separadas — a segunda era inatingível
@router.get("/history")  # linha 142 — única que executava
async def get_job_history(limit, db): ...

@router.get("/history")  # linha 418 — NUNCA executada
async def get_job_history_search(q, category, playlist, favorites, db): ...

# DEPOIS: uma única rota com todos os parâmetros
@router.get("/history")
async def get_job_history(limit, q, category, playlist, favorites, db): ...
```

---

### BUG 2 — `db.close()` faltando em `run_generate_script_only` (`jobs.py`) ✅ CORRIGIDO
**Severidade:** ALTA — vazamento de conexões de banco de dados  
**Problema:** O `finally: db.close()` estava dentro do bloco `except`, não no `try` externo. Em caso de sucesso, a conexão nunca era fechada — acumulando conexões ociosas com o SQLite.  
**Correção:** `finally: db.close()` movido para o nível correto do `try` externo, idêntico ao padrão usado em `run_podcast_job_background`.

```python
# ANTES — db.close() só fechava em caso de ERRO
except Exception as e:
    ...
    finally:        # ← pertencia ao except, não ao try
        db.close()  # ← nunca chamado em caso de sucesso!

# DEPOIS — db.close() sempre executa
    ...
finally:        # ← nível correto: pertence ao try externo
    db.close()  # ← garante fechamento sempre
```

---

### BUG 3 — `bare except:` silenciando erros (`llm.py` + `config.py`) ✅ CORRIGIDO
**Severidade:** ALTA — mascara erros reais incluindo `KeyboardInterrupt` e `SystemExit`  
**Problema:** 6 ocorrências de `except:` sem tipo em `llm.py` e 3 em `config.py`. Um `bare except` captura **tudo**, incluindo sinais de sistema (`Ctrl+C`), tornando o processo impossível de interromper e silenciando erros inesperados.  
**Correção:** Todos substituídos por `except Exception:`.  
**Verificado:** `grep -rn "except:" backend/` retorna zero resultados.

```python
# ANTES
except:
    pessoas = []

# DEPOIS
except Exception:
    pessoas = []
```

---

### BUG 4 — Path Traversal em `/audio/{filepath:path}` (`main.py`) ✅ CORRIGIDO
**Severidade:** ALTA — exposição de arquivos do sistema  
**Problema:** A rota `/audio/../../etc/passwd` construía o path sem validar se o resultado estava dentro do diretório `data/output/`. Um atacante (ou erro de cliente) poderia acessar qualquer arquivo do servidor.  
**Correção:** `.resolve()` no path final + verificação `startswith(output_dir)` antes de servir.  
**Verificado:** `GET /audio/../../etc/passwd` → `HTTP 403 Forbidden`.

```python
# ANTES — sem validação
audio_path = base_dir / "data" / "output" / filepath
if not audio_path.exists():
    return {"error": "não encontrado"}

# DEPOIS — com proteção
output_dir = (base_dir / "data" / "output").resolve()
audio_path = (output_dir / filepath).resolve()
if not str(audio_path).startswith(str(output_dir)):
    raise HTTPException(status_code=403, detail="Acesso negado")
```

---

### BUG 5 — `MAX_UPLOAD_MB` sem proteção contra valor inválido (`config.py`) ✅ CORRIGIDO
**Severidade:** MÉDIA — crash na inicialização do servidor  
**Problema:** `int(os.getenv("MAX_UPLOAD_MB", "50"))` sem try/except. Se o `.env` contiver `MAX_UPLOAD_MB=abc` ou estiver corrompido, o servidor não inicia com `ValueError` sem mensagem clara.  
**Correção:** Envolto em `try/except ValueError` com fallback para 50.

```python
# ANTES
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))  # crash se valor inválido

# DEPOIS
try:
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
except ValueError:
    MAX_UPLOAD_MB = 50  # fallback seguro
```

---

## 4. O que NÃO foi alterado (e por quê)

| Item | Decisão | Motivo |
|------|---------|--------|
| URLs hardcoded no frontend (`http://localhost:8000`) | **Mantido** | Sistema roda apenas local — não é problema agora |
| `StaticPool` no SQLAlchemy | **Mantido** | SQLite tem lock interno de qualquer forma; a solução real é migrar para PostgreSQL quando escalar |
| `print()` em `fabot_tts.py` | **Mantido** | Não quebra nada em ambiente local |
| `RotatingFileHandler` para logs | **Mantido** | Não urgente para uso local |
| Logging sem rotação (`fabot.log`) | **Mantido** | Não urgente para uso local |
| CORS_ORIGINS via `.env` | **Mantido** | Hardcoded em `config.py` é ok para uso local |

---

## 5. Arquitetura — Visão Geral

```
fabot-studio/
├── backend/
│   ├── main.py              — FastAPI app + CORS + rotas de áudio
│   ├── config.py            — Settings centralizadas via .env
│   ├── database.py          — SQLAlchemy + SQLite WAL
│   ├── models.py            — Job, File, UserConfig
│   ├── routers/
│   │   ├── jobs.py          — CRUD jobs + background tasks
│   │   ├── upload.py        — Upload PDF/texto
│   │   ├── health.py        — Health check Redis/Disk/Ollama/Worker
│   │   ├── ocr.py           — OCR de imagens
│   │   └── config.py        — Configurações do usuário
│   ├── services/
│   │   ├── llm.py           — Groq / Gemini / GLM / Ollama providers
│   │   ├── fabot_tts.py     — Edge TTS paralelo com Semaphore(5)
│   │   ├── ingestor.py      — Extração de texto de PDF/TXT
│   │   └── text_splitter.py — Divisão de texto em seções
│   └── workers/
│       └── podcast_worker.py — ARQ workers (generate_script, start_tts)
└── frontend/
    └── src/
        ├── api.js           — Instância axios centralizada (existe mas não totalmente usada)
        ├── App.jsx          — Orquestrador principal
        ├── store/jobStore.js — Estado global (Zustand)
        ├── hooks/
        │   ├── useHealthCheck.js
        │   └── useJobStream.js
        └── components/
            ├── InputPanel, ScriptPanel, PlayerPanel
            ├── HistoryPanel, ConfigPanel
            └── ActiveJobsBar (jobs em andamento)
```

---

## 6. Fluxo de Geração de Podcast

```
Upload (PDF/texto)
       ↓
POST /upload/paste  →  cria Job (status: PENDING)
       ↓
POST /jobs/{id}/generate-script  →  BackgroundTask
       ↓
run_generate_script_only()
  └→ asyncio.run(generate_script_only())
       └→ LLM Provider (Groq/GLM/Gemini)
             └→ parse_llm_json() + validate_script_response()
       ↓
Job status: SCRIPT_DONE
       ↓
POST /jobs/{id}/start-tts  →  ARQ Queue → Redis
       ↓
start_tts_job() [worker]
  └→ build_episode() [fabot_tts.py]
       └→ synthesize_segment() × N  [paralelo, Semaphore(5)]
             └→ Edge TTS [timeout 30s cada]
       └→ concat + export final.mp3
       └→ cleanup_segments()
       ↓
Job status: DONE  →  áudio disponível em /audio/{job_id}/final.mp3
```

---

## 7. Resumo Final

| Categoria | Quantidade | Status |
|-----------|-----------|--------|
| Correções originais validadas | 9/10 | ✅ |
| Correção parcial (URLs frontend) | 1/10 | ⚠️ não urgente |
| Bugs fatais/críticos corrigidos | 5 | ✅ |
| `bare except:` eliminados | 6 (llm.py) + 3 (config.py) = **9 total** | ✅ |
| Vulnerabilidade path traversal | 1 | ✅ corrigida |
| Serviços UP ao vivo | 5/5 | ✅ |

**O sistema está estável e funcional para uso local.**  
Os únicos itens pendentes (URLs hardcoded, RotatingFileHandler, StaticPool) são melhorias para quando houver planos de deploy em produção.
