# FABOT - Podcast Studio

Sistema profissional para geração de podcasts educacionais usando Inteligência Artificial.

**Versão:** 2.0.0 | **Última atualização:** 23/03/2026

---

## Índice

1. [O que é o FABOT](#o-que-é-o-fabot)
2. [Tecnologias](#tecnologias)
3. [Personagens e Vozes](#personagens-e-vozes)
4. [Motor de Variedade Criativa V7](#motor-de-variedade-criativa-v7)
5. [Como Funciona](#como-funciona)
6. [Interface](#interface)
7. [Funcionalidades](#funcionalidades)
8. [Estrutura do Projeto](#estrutura-do-projeto)
9. [Descrição dos Arquivos](#descrição-dos-arquivos)
10. [API Endpoints](#api-endpoints)
11. [Banco de Dados](#banco-de-dados)
12. [Configuração](#configuração)
13. [Como Executar](#como-executar)
14. [LLMs Suportados](#llms-suportados)
15. [Erros Comuns](#erros-comuns)
16. [Sistema de Inicialização](#sistema-de-inicialização)
17. [Correções Implementadas](#correções-implementadas)
18. [Histórico de Atualizações](#histórico-de-atualizações)

---

## 🎙️ O que é o FABOT

O FABOT é um sistema que transforma textos e documentos em podcasts educacionais de alta qualidade. Ele usa IA para:

- Ler e processar textos, PDFs ou extrair texto de imagens (OCR)
- Gerar roteiros estruturados com diálogos naturais entre apresentadores
- Converter o roteiro em áudio profissional usando síntese de voz (Edge TTS)
- Organizar os podcasts em categorias, favoritos e playlists
- **Gerar roteiros radicalmente diferentes** para o mesmo texto (Motor de Variedade V7)

---

## 🛠️ Tecnologias

| Componente | Tecnologia | Descrição |
|------------|------------|-----------|
| **Frontend** | React + Vite | Interface web moderna e responsiva |
| **Backend** | FastAPI | API REST em Python |
| **Banco de Dados** | SQLite (WAL Mode) | Armazenamento local de podcasts e roteiros |
| **Fila de Jobs** | Redis + ARQ | Processamento assíncrono de tarefas |
| **TTS (Voz)** | Edge TTS | Síntese de voz da Microsoft (gratuito) |
| **LLM** | Gemini, GLM | Geração de roteiros inteligentes |
| **OCR** | pdfminer + pytesseract | Extração de texto de PDFs e imagens |

---

## 🎤 Personagens e Vozes

O FABOT usa 3 vozes FIXAS para criar diálogos naturais:

| Personagem | Voz Edge TTS | Cor na Interface | Descrição |
|------------|--------------|------------------|-----------|
| **NARRADORA** | pt-BR-ThalitaMultilingualNeural | 🔴 Vermelho | APRESENTA o tema, faz introduções e despedidas |
| **WILLIAM** | pt-BR-AntonioNeural | 🔵 Azul | FAZ PERGUNTAS, representa o ouvinte curioso |
| **CRISTINA** | pt-BR-FranciscaNeural | 🩷 Rosa | EXPLICA os conceitos, é a "professora" |

### Personagens vs Apresentadores

**Personagens FIXOS (voz não muda):**
- NARRADORA (Thalita) - só na introdução e despedida
- WILLIAM (Antonio) - voz masculina, sempre presente
- CRISTINA (Francisca) - voz feminina, sempre presente

**Apresentadores (nomes que podem mudar):**
- Host = WILLIAM (pode mudar nome, voz NÃO muda)
- Co-host = CRISTINA (pode mudar nome, voz NÃO muda)

### Estrutura do Roteiro

Cada episódio segue uma estrutura didática:

1. **NARRADORA** → Introduz o tema (ex: "Olá Fábio!")
2. **WILLIAM** → Faz pergunta sobre o conceito
3. **CRISTINA** → Explica com exemplos e analogias de negócios
4. (Repete esse padrão durante todo o episódio - 40+ segmentos)
5. **NARRADORA** → Faz despedida (ex: "Até o próximo episódio!")

### Personalização Automática

Quando configurado no ConfigPanel (⚙️):
- NARRADORA saúda pelo nome do ouvinte
- WILLIAM/CRISTINA mencionam pessoas próximas nos exemplos
- Encerramento personalizado com nome do ouvinte
- Personagens fictícios de empresas reais nos exemplos

---

## 🚀 Motor de Variedade Criativa V7

**Problema original:** Gerar 3 roteiros com o mesmo texto resultava em roteiros idênticos.

**Solução implementada (V7):**

### As 6 causas raiz identificadas:

1. **Abertura fixa** - Template literal no prompt
2. **Sequência rígida** - Passos numerados hardcoded com clichês
3. **Personagens sem shuffle** - Sempre na mesma ordem
4. **Temperatura baixa** - 0.7 era conservadora demais
5. **Cache Redis** - Hash idêntico bloqueava variedade
6. **Zero randomização** - Prompt determinístico

### O que foi implementado:

#### 1. `prompt_variator.py` - Motor de Variedade

```python
ABERTURAS = [
    "E aí, {usuario_nome}, preparado para um assunto que vai mudar sua perspectiva?",
    "Imagina {usuario_nome} no comando de uma empresa...",  # analogia CFO
    "Noventa por cento dos iniciantes cometem esse erro...",  # erro comum
    "Em {ano_atual}, {empresa} enfrentou um problema que...",  # história real
    "Se alguém te pedisse para {situacao}, você saberia por onde começar?",
    "{usuario_nome}, você já parou para pensar em como...",
]

ESTRATEGIAS = [
    "pergunta",  # Começa com pergunta direta
    "analogia_cfo",  # Comparação com gestão financeira
    "erro_comum",  # Mostra erro que todos cometem
    "historia_real",  # Conta história de empresa real
    "situacao_pratica",  # Coloca em situação real
    "provocacao",  # Provoca curiosidade
    "metrica_impactante",  # Usa dado impressionante
    "contexto_atual",  # Relaciona com momento atual
]
```

#### 2. `script_template_v7.py` - Template Jinja2

Template completo com variáveis dinâmicas:
- `{{ abertura.instrucao }}` - Instrução de abertura
- `{{ abertura.estilo }}` - Estilo narrativo
- `{{ abertura.contexto }}` - Contexto sugerido
- `{{ reacao.william }}` - Reação do William
- `{{ reacao.cristina }}` - Reação da Cristina

#### 3. Parâmetros de Geração Otimizados

```python
# GeminiProvider
generation_config=genai.types.GenerationConfig(
    temperature=0.88,  # ↑ de 0.7 para 0.88
    top_p=0.92,        # ↑ de 0.9 para 0.92
    max_output_tokens=8192,
)

# GLMProvider  
generation_config={
    "temperature": 0.88,
    "top_p": 0.92,
    "frequency_penalty": 0.4,
    "presence_penalty": 0.3,
}
```

#### 4. Cache Desabilitado

```python
# Cache REMOVIDO da geração de roteiro
# O hash inclui timestamp para garantir uniqueness
cache_key = f"script:{text_hash}:{timestamp}"
```

### Resultado

Teste prático: 5 gerações do texto "Python Lista" resultaram em 5 roteiros **100% diferentes**:

| # | Título | Estilo de Abertura |
|---|--------|-------------------|
| 1 | "Listas em Python: O CRM do seu Negócio" | Provocação |
| 2 | "Desvendando Listas e Operadores" | Desafio |
| 3 | "Listas em Python: Organizando como um CFO" | Analogia CFO |
| 4 | "O Erro de Milhões no Estoque Digital" | Erro comum |
| 5 | "Organize Seu Negócio Como um Gigante do Varejo" | História real |

---

## ⚙️ Como Funciona

### Fluxo Principal

```
1. Usuário cola texto, faz upload de PDF ou usa OCR
         ↓
2. Sistema processa o texto (divide em partes se necessário)
         ↓
3. LLM gera o roteiro em JSON (com diálogos NARRADORA/WILLIAM/CRISTINA)
         ↓
4. Motor de Variedade V7 garante roteiros diferentes a cada geração
         ↓
5. Usuário pode EDITAR o roteiro na interface
         ↓
6. Edge TTS converte cada fala em áudio (paralelo)
         ↓
7. Sistema concatena os áudios com pausas adequadas
         ↓
8. Podcast pronto! MP3 salvo no banco
```

### Dois Modos de Geração

1. **Gerar Roteiro** → Apenas cria o texto do roteiro (sem áudio)
2. **Gerar Podcast Completo** → Cria roteiro + áudio

### Entrada de Dados

O sistema aceita 3 tipos de entrada:

1. **Texto** - Cola texto diretamente na interface
2. **Arquivo** - Upload de PDF, DOCX ou TXT
3. **OCR** - Extrai texto de imagens ou PDFs escaneados

---

## 🎨 Interface

A interface tem 3 colunas:

### Coluna 1 - Entrada

- Campo para digitar título do podcast
- **3 abas de entrada:**
  - **Arquivos** - Upload de PDF, DOCX, TXT
  - **Texto** - Cola texto diretamente
  - **OCR** - Extrai texto de imagens/PDFs escaneados
- Botões para gerar roteiro ou podcast completo
- Seletor de LLM no cabeçalho

### Coluna 2 - Roteiro

- Lista de falas em ordem cronológica
- Cada fala em uma caixa separada
- Cores por personagem (Vermelho/Azul/Rosa)
- Editor de texto para editar cada fala
- Botão "Salvar" para persistir alterações
- Botão "Gerar Áudio" para criar o podcast
- 3 cards de apresentadores quando não há roteiro

### Coluna 3 - Player

- Player de áudio para ouvir o podcast
- Botão para baixar MP3
- Histórico de podcasts gerados
- Busca por título
- Filtro de favoritos
- Categorias e playlists
- Alternância de tema claro/escuro

---

## ✨ Funcionalidades

- [x] Upload de texto, PDF, DOCX, TXT
- [x] **OCR para extrair texto de imagens e PDFs escaneados**
- [x] Geração automática de roteiro
- [x] **Motor de Variedade V7 - roteiros sempre diferentes**
- [x] Editor visual de roteiro
- [x] Síntese de voz profissional (Edge TTS)
- [x] Múltiplas vozes (NARRADORA, WILLIAM, CRISTINA)
- [x] Histórico de podcasts
- [x] Busca no histórico
- [x] Favoritos
- [x] Categorias
- [x] Playlists
- [x] Modo escuro
- [x] Exportação de roteiro (Markdown)
- [x] Download de MP3
- [x] ConfigPanel para personalização completa
- [x] Health check em tempo real (Redis, Worker, LLM, SQLite)

---

## 📁 Estrutura do Projeto

```
fabot-studio/
├── backend/
│   ├── __init__.py
│   ├── config.py              # Configurações globais
│   ├── database.py            # Conexão SQLite (WAL mode)
│   ├── models.py              # Modelos do banco (Job, File)
│   ├── main.py                # FastAPI app
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── jobs.py            # CRUD de jobs
│   │   ├── upload.py          # Upload de arquivos/texto
│   │   ├── health.py          # Health check
│   │   ├── config.py          # ConfigPanel API
│   │   └── ocr.py             # OCR endpoint
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py             # Provedores LLM (Gemini, GLM)
│   │   ├── fabot_tts.py       # Edge TTS com parallelismo
│   │   ├── text_splitter.py   # Divisão de texto grande
│   │   ├── ocr_extractor.py   # Extração OCR
│   │   └── cache_manager.py   # Cache Redis
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── __main__.py        # Entry point ARQ
│   │   └── podcast_worker.py  # Processamento background
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── script_template_v5.py  # Legado
│   │   ├── script_template_v6.py  # Template atual (Jinja2)
│   │   ├── script_template_v7.py  # Motor de Variedade
│   │   └── prompt_variator.py  # Variações de prompt
│   │
│   └── db/
│       └── fabot.db           # Banco SQLite
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx        # Cabeçalho + seletor LLM
│   │   │   ├── InputPanel.jsx     # Coluna 1: Entrada
│   │   │   ├── OcrPanel.jsx       # OCR de imagens/PDFs
│   │   │   ├── ScriptPanel.jsx    # Coluna 2: Roteiro
│   │   │   ├── PlayerPanel.jsx    # Coluna 3: Player
│   │   │   ├── ConfigPanel.jsx    # Configurações
│   │   │   └── ...
│   │   ├── hooks/
│   │   │   ├── useHealthCheck.js  # Health check
│   │   │   └── ...
│   │   ├── store/
│   │   │   └── jobStore.js        # Estado global (Zustand)
│   │   ├── api.js                 # URLs centralizadas
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   ├── output/                # Áudios gerados
│   └── uploads/              # Arquivos enviados
│
├── logs/
│   ├── backend.log
│   └── frontend.log
│
├── .env                      # Variáveis de ambiente
├── requirements.txt
├── docker-compose.yml
├── start_reliable.sh         # Script de inicialização
└── README.md
```

---

## 📝 Descrição dos Arquivos

### Backend - Raiz

| Arquivo | Descrição |
|---------|-----------|
| `config.py` | Configurações globais: chaves de API, CORS, caminhos |
| `database.py` | Conexão SQLite com WAL mode para escritas simultâneas |
| `models.py` | Modelos ORM: Job (podcast), File (arquivos) |
| `main.py` | Aplicação FastAPI principal, rotas, middleware CORS |

### Backend - Routers

| Arquivo | Descrição |
|---------|-----------|
| `routers/jobs.py` | CRUD de jobs, geração de roteiro/áudio, cancelamento |
| `routers/upload.py` | Upload de arquivos e texto para criar jobs |
| `routers/health.py` | Health check: Redis, Worker, LLM, SQLite |
| `routers/config.py` | API do ConfigPanel (personalização) |
| `routers/ocr.py` | Endpoint para extrair texto de imagens/PDFs |

### Backend - Services

| Arquivo | Descrição |
|---------|-----------|
| `services/llm.py` | GeminiProvider e GLMProvider com variedade V7 |
| `services/fabot_tts.py` | Edge TTS paralelo com timeout e cleanup |
| `services/text_splitter.py` | Divide textos grandes em seções menores |
| `services/ocr_extractor.py` | Extrai texto de PDFs e imagens |
| `services/cache_manager.py` | Cache Redis para LLM |

### Backend - Workers

| Arquivo | Descrição |
|---------|-----------|
| `workers/podcast_worker.py` | Processa jobs em fila (roteiro → áudio) |
| `workers/__main__.py` | Entry point para ARQ |

### Backend - Prompts

| Arquivo | Descrição |
|---------|-----------|
| `prompts/script_template_v5.py` | Template legado |
| `prompts/script_template_v6.py` | Template atual com Jinja2 |
| `prompts/script_template_v7.py` | Template do Motor de Variedade |
| `prompts/prompt_variator.py` | 6 aberturas, 8 estratégias, 10 reações |

### Frontend - Components

| Arquivo | Descrição |
|---------|-----------|
| `components/Header.jsx` | Cabeçalho com seletor LLM, tema, histórico |
| `components/InputPanel.jsx` | Abas Arquivos, Texto, OCR |
| `components/OcrPanel.jsx` | Upload e extração OCR |
| `components/ScriptPanel.jsx` | Editor de roteiro com 3 cards |
| `components/PlayerPanel.jsx` | Player, histórico, busca, favoritos |
| `components/ConfigPanel.jsx` | Modal de configuração |

### Frontend - Hooks

| Arquivo | Descrição |
|---------|-----------|
| `hooks/useHealthCheck.js` | Poll do health check a cada 3s |

---

## 🔌 API Endpoints

### Jobs

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/jobs/` | Criar novo job |
| GET | `/jobs/` | Listar todos os jobs |
| GET | `/jobs/{id}` | Ver detalhes de um job |
| POST | `/jobs/{id}/generate-script` | Gerar roteiro |
| POST | `/jobs/{id}/start` | Gerar roteiro + áudio |
| POST | `/jobs/{id}/start-tts` | Gerar áudio do roteiro |
| PUT | `/jobs/{id}/script` | Salvar roteiro editado |
| PATCH | `/jobs/{id}` | Atualizar título, categoria, favorito |
| DELETE | `/jobs/{id}` | Deletar job |
| GET | `/jobs/history` | Histórico com filtros |
| POST | `/jobs/{id}/cancel` | Cancelar job |

### Upload

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/upload/` | Upload de arquivo |
| POST | `/upload/paste` | Enviar texto direto |

### OCR

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/ocr/extract` | Extrair texto de imagem/PDF |
| POST | `/ocr/extract-batch` | Extrair de múltiplos arquivos |

### Config

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/config/` | Buscar configuração |
| POST | `/config/` | Salvar configuração |

### Áudio

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/audio/{filepath}` | Servir arquivo de áudio |

### Health

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health/` | Status de todos os serviços |

---

## 💾 Banco de Dados

### Tabela Jobs

```sql
jobs (
  id              VARCHAR(36) PRIMARY KEY,
  title           VARCHAR(255),
  status          VARCHAR(20),        -- PENDING, READING, LLM_PROCESSING, SCRIPT_DONE, TTS_QUEUED, TTS_PROCESSING, DONE, FAILED, CANCELLED
  progress        INTEGER,
  current_step    VARCHAR(255),
  script_json     TEXT,               -- Roteiro completo em JSON
  script_edited   BOOLEAN,
  audio_path      VARCHAR(500),       -- Caminho do arquivo MP3
  duration_seconds INTEGER,
  category        VARCHAR(100),
  tags            VARCHAR(500),
  is_favorite     BOOLEAN,
  playlist        VARCHAR(100),
  llm_mode        VARCHAR(50),       -- gemini-2.5-flash, glm-4.7-flash
  voice_host      VARCHAR(50),        -- pf_dora, etc
  error_message   TEXT,
  created_at      DATETIME,
  updated_at      DATETIME
)
```

### Tabela Files

```sql
files (
  id              VARCHAR(36) PRIMARY KEY,
  job_id          VARCHAR(36) FOREIGN KEY,
  original_name   VARCHAR(255),
  file_type       VARCHAR(20),        -- pdf, txt, docx, image
  file_path       VARCHAR(500),
  extracted_text  TEXT,
  char_count      INTEGER,
  status          VARCHAR(20)
)
```

---

## ⚙️ Configuração

### Variáveis de ambiente (.env)

```env
# Banco
DATABASE_PATH=backend/db/fabot.db

# Diretórios
OUTPUT_DIR=data/output
UPLOAD_DIR=data/uploads

# Redis
REDIS_URL=redis://localhost:6379

# LLMs
GEMINI_API_KEY=your_gemini_key_here
GLM_API_KEY=your_glm_key_here

# Ollama (não usado atualmente)
OLLAMA_URL=http://localhost:11434

# Configurações
DEBUG=true
LOG_LEVEL=INFO
LOG_FILE=logs/fabot.log
```

### ConfigPanel - Personalização

O ConfigPanel (⚙️) permite configurar:

1. **Ouvinte** - Nome de quem vai ouvir
2. **Pessoas Próximas** - Para usar em exemplos afetivos
3. **Apresentadores** - Nomes (vozes são fixas)
4. **Personagens** - Personagens fictícios para exemplos
5. **Empresas** - Empresas reais para usar nos exemplos
6. **Opções** - Saudar por nome, mencionar pessoas, despedida personalizada

### CORS

O backend aceita requisições de:
- `http://localhost:3000`
- `http://127.0.0.1:3000`
- `http://localhost:5173`
- `http://127.0.0.1:5173`

---

## 🚀 Como Executar

### Script de Atalho (Recomendado)

```bash
# Clique no ícone FABOT-PODCAST.desktop na área de trabalho
# Ou execute manualmente:
bash ~/Área\ de\ trabalho/FABOT-PODCAST.sh
```

O script verifica e inicia automaticamente:
1. Redis
2. Backend (porta 8000)
3. Frontend (porta 3000)
4. Abre o Chrome em http://localhost:3000

### Manual - Passo a Passo

1. **Instalar dependências:**
```bash
cd fabot-studio
pip install -r requirements.txt
cd frontend && npm install
```

2. **Iniciar Redis:**
```bash
redis-server --daemonize yes
```

3. **Iniciar Backend:**
```bash
cd fabot-studio
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Iniciar Worker (outro terminal):**
```bash
cd fabot-studio
python backend/run_worker.py
# Ou via systemd:
sudo systemctl start fabot-worker
```

5. **Iniciar Frontend:**
```bash
cd fabot-studio/frontend
npm run dev
```

6. **Acessar:**
```
http://localhost:3000
```

---

## 🤖 LLMs Suportados

| Nome | Valor no Select | API Key | Custo |
|------|-----------------|---------|-------|
| **Gemini 2.5 Flash** | `gemini-2.5-flash` | Sim (Google AI Studio) | **GRÁTIS** ⭐ |
| Gemini 2.5 Flash-Lite | `gemini-2.5-flash-lite` | Sim | **GRÁTIS** |
| Gemini 2.5 Pro | `gemini-2.5-pro` | Sim | Pago |
| GLM-4.7-Flash | `glm-4.7-flash` | Sim | **GRÁTIS** |
| GLM-4-Flash | `glm-4-flash` | Sim | **GRÁTIS** |

**Recomendado:** Gemini 2.5 Flash - melhor custo-benefício.

### Limites do Gemini 2.5 Flash

| Limite | Valor |
|--------|-------|
| Requests/minuto | 15 |
| Requests/dia | 1.500 |
| Tokens contexto | 1M |
| **Custo** | **GRÁTIS** |

---

## ❌ Erros Comuns

### Áudio não toca
- Verificar se o backend está rodando
- Verificar health check (Redis, Worker, LLM)
- Verificar console do navegador (F12)

### Roteiro não aparece
- Verificar se há script_json no banco
- Verificar status do job (deve ser SCRIPT_DONE ou DONE)
- Verificar logs do backend

### OCR não funciona
- Verificar CORS_ORIGINS no config.py
- Backend precisa estar na porta configurada (3000)

### LLM não funciona
- Verificar API key no arquivo .env
- Verificar se há créditos na API do Google AI Studio

### Worker não processa jobs
```bash
sudo systemctl status fabot-worker
sudo systemctl restart fabot-worker
```

---

## 🔧 Sistema de Inicialização

### Script FABOT-PODCAST.sh

```bash
#!/bin/bash
DIR="/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio"

# Verificar Redis
redis-cli ping || redis-server --daemonize yes

# Verificar Backend (porta 8000)
curl -sf http://localhost:8000/health/ || \
  nohup .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 &

# Verificar Frontend (porta 3000)
curl -sf http://localhost:3000 || \
  nohup npm run dev -- --host 0.0.0.0 --port 3000 &

# Abrir Chrome
google-chrome --new-window http://localhost:3000
```

### Worker via systemd

O worker é gerenciado pelo systemd para auto-restart:

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

---

## ✅ Correções Implementadas

Todas as correções foram documentadas em [CORRECOES.md](./CORRECOES.md).

### Resumo das Correções

| # | Correção | Arquivo | Prioridade |
|---|----------|---------|------------|
| 1 | SQLite WAL Mode | database.py | 🔴 Crítica |
| 2 | Edge TTS Timeout (30s) | fabot_tts.py | 🔴 Crítica |
| 3 | Cleanup arquivos temp | fabot_tts.py | 🔴 Crítica |
| 4 | Redis Keepalive | podcast_worker.py | 🟡 Alta |
| 5 | Retry JSON LLM | llm.py | 🟡 Alta |
| 6 | asyncio.run() | jobs.py | 🔴 Crítica |
| 7 | TTS Paralelo (5x) | fabot_tts.py | 🔴 Crítica |
| 8 | API Keys no .env | config.py, llm.py | 🔴 Crítica |
| 9 | URLs centralizadas | frontend/src/api.js | 🟡 Alta |
| 10 | CORS restritivo | config.py | 🟡 Alta |
| 11 | Cancel funcional | jobs.py | 🟡 Alta |
| 12 | Health check Worker | health.py | 🟡 Alta |
| 13 | Timeout polling frontend | App.jsx | 🟡 Alta |
| 14 | Motor de Variedade V7 | prompt_variator.py, llm.py | 🔴 Crítica |

---

## 📜 Histórico de Atualizações

### 23/03/2026 - Motor de Variedade Criativa V7 🚀

**Problema:** Gerar 3 roteiros com o mesmo texto resultava em roteiros idênticos.

**Solução implementada:**

1. **prompt_variator.py** - 6 aberturas, 8 estratégias, 10 reações
2. **script_template_v7.py** - Template Jinja2 com variáveis dinâmicas
3. **Parâmetros otimizados:** temperature 0.88, topP 0.92
4. **Cache desabilitado** na geração de roteiro
5. **Remoção de provedores não usados:** GroqProvider, OllamaProvider

**Resultado:** 5 gerações do mesmo texto = 5 roteiros 100% diferentes.

### 23/03/2026 - OCR Implementado

**Endpoint:** `POST /ocr/extract`

Extrai texto de:
- PDFs (via pdfminer)
- Imagens (via pytesseract/OCR)

### 23/03/2026 - CORS Atualizado

CORS_ORIGINS agora inclui portas 3000 e 5173.

### 20/03/2026 - Sistema de Personalização Completo

ConfigPanel permite personalizar:
- Nome do ouvinte
- Pessoas próximas
- Apresentadores
- Personagens de exemplo
- Empresas

---

## 📊 Limites dos LLMs

### Gemini 2.5 Flash (GRÁTIS) ⭐ PADRÃO

| Limite | Valor |
|--------|-------|
| Requests/minuto | 15 |
| Requests/dia | 1.500 |
| Tokens contexto | 1M |
| **Custo** | **GRÁTIS** |

### GLM-4.7-Flash (GRÁTIS)

| Limite | Valor |
|--------|-------|
| Custo | **GRÁTIS** |

---

## 🐛 Debugging - Checklist de Problemas

Se o sistema não funcionar, verifique nesta ordem:

1. **Health check OK?**
   ```bash
   curl http://localhost:8000/health/
   ```
   Deve mostrar: Redis UP, Worker UP, Ollama UP

2. **Backend rodando?**
   ```bash
   curl http://localhost:8000/config/
   ```

3. **Frontend rodando?**
   ```bash
   curl http://localhost:3000 > /dev/null && echo "OK"
   ```

4. **Redis rodando?**
   ```bash
   redis-cli ping
   ```

5. **Worker ARQ rodando?**
   ```bash
   sudo systemctl status fabot-worker
   ```

6. **Job travou?**
   ```bash
   curl http://localhost:8000/jobs/{id}
   ```

7. **WAL mode ativo?**
   ```bash
   sqlite3 backend/db/fabot.db "PRAGMA journal_mode;"
   # Resultado esperado: wal
   ```

---

## 🔮 Próximas Melhorias Planejadas

- [ ] Notificação quando podcast estiver pronto
- [ ] Auto-retry quando falhar
- [ ] Salvar podcasts por nome do tema
- [ ] Integração WhatsApp via OpenClaw
- [ ] RAG (busca semântica) para contextualizar roteiros
- [ ] Migração para PostgreSQL (quando escalar)
- [ ] Deploy na nuvem (Vercel + Supabase)

---

## 📄 Licença

MIT License

---

**PRODUZIDO POR: FABIO ROSESTOLATO**

FABOT Podcast Studio - Transformando texto em conhecimento 🎙️
