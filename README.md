# FABOT - Podcast Studio

Sistema profissional para geração de podcasts educacionais usando Inteligência Artificial.

---

## 📋 Índice

1. [O que é o FABOT](#o-que-é-o-fabot)
2. [Tecnologias](#tecnologias)
3. [Personagens e Vozes](#personagens-e-vozes)
4. [Como Funciona](#como-funciona)
5. [Interface](#interface)
6. [Funcionalidades](#funcionalidades)
7. [Estrutura do Projeto](#estrutura-do-projeto)
8. [Descrição dos Arquivos](#descrição-dos-arquivos)
9. [API Endpoints](#api-endpoints)
10. [Banco de Dados](#banco-de-dados)
11. [Configuração](#configuração)
12. [Como Executar](#como-executar)
13. [LLMs Suportados](#llms-suportados)
14. [Erros Comuns](#erros-comuns)
15. [Histórico de Atualizações](#histórico-de-atualizações)

---

## 🎙️ O que é o FABOT

O FABOT é um sistema que transforma textos e documentos em podcasts educacionais de alta qualidade. Ele usa IA para:

- Ler e processar textos ou PDFs
- Gerar roteiros estruturados com diálogos naturais
- Converter o roteiro em áudio profissional usando síntese de voz
- Organizar os podcasts em categorias e playlists

---

## 🛠️ Tecnologias

| Componente | Tecnologia | Descrição |
|-----------|------------|------------|
| **Frontend** | React + Vite | Interface web moderna e responsiva |
| **Backend** | FastAPI | API REST em Python |
| **Banco de Dados** | SQLite | Armazenamento local de podcasts e roteiros |
| **Fila de Jobs** | Redis + ARQ | Processamento assíncrono de tarefas |
| **TTS (Voz)** | Edge TTS | Síntese de voz da Microsoft (gratuito) |
| **LLM** | Groq, Gemini, GLM, Ollama | Geração de roteiros |

---

## 🎤 Personagens e Vozes

O FABOT usa 3 vozes diferentes para criar diálogos naturais:

| Personagem | Voz Edge TTS | Cor na Interface | Descrição |
|-----------|--------------|-------------------|------------|
| **NARRADORA** | ThalitaMultilingualNeural | 🔴 Vermelho | APRESENTA o tema, faz introduções e transições |
| **WILLIAM** | AntonioNeural | 🔵 Azul | FAZ PERGUNTAS, representa o ouvinte curioso |
| **CRISTINA** | FranciscaNeural | 🩷 Rosa | EXPLICA os conceitos, é a "professora" |

### Estrutura do Roteiro

Cada episódio segue uma estrutura didática:

1. **NARRADORA** → Introduz o tema
2. **WILLIAM** → Faz pergunta sobre o conceito
3. **CRISTINA** → Explica com exemplos e analogias
4. (Repete esse padrão durante todo o episódio)
5. **NARRADORA** → Faz transição para próximo episódio

---

## ⚙️ Como Funciona

### Fluxo Principal

```
1. Usuário cola texto ou faz upload de PDF
         ↓
2. Sistema processa o texto (divide em partes se necessário)
         ↓
3. LLM gera o roteiro em JSON (com diálogos NARRADORA/WILLIAM/CRISTINA)
         ↓
4. Usuário pode EDITAR o roteiro na interface
         ↓
5. Edge TTS converte cada fala em áudio
         ↓
6. Sistema concatena os áudios com pausas adequadas
         ↓
7. Podcast pronto!MP3 salvo no banco
```

### Dois Modos de Geração

1. **Gerar Roteiro** → Apenas cria o texto do roteiro (sem áudio)
2. **Gerar Podcast Completo** → Cria roteiro + áudio

---

## 🎨 Interface

A interface tem 3 colunas:

### Coluna 1 - Entrada
- Campo para digitar título do podcast
- Área para colar texto
- Upload de arquivos (PDF, DOCX, TXT)
- Botões para gerar roteiro ou podcast completo

### Coluna 2 - Roteiro
- Lista de falas em ordem cronológica
- Cada fala em uma caixa separada
- Cores por personagem (Vermelho/Azul/Rosa)
- Editor de texto para editar cada fala
- Botão "Salvar" para persistir alterações
- Botão "Gerar Áudio" para criar o podcast

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

- [x] Upload de texto ou PDF
- [x] Geração automática de roteiro
- [x] Editor visual de roteiro
- [x] Síntese de voz profissional
- [x] Múltiplas vozes (NARRADORA, WILLIAM, CRISTINA)
- [x] Histórico de podcasts
- [x] Busca no histórico
- [x] Favoritos
- [x] Categorias
- [x] Playlists
- [x] Modo escuro
- [x] Exportação de roteiro (Markdown)
- [x] Download de MP3

---

## 📁 Estrutura do Projeto

```
fabot-studio/
├── backend/
│   ├── config.py           # Configurações globais
│   ├── database.py        # Conexão SQLite
│   ├── models.py          # Modelos do banco (Job, File)
│   │
│   ├── routers/
│   │   ├── jobs.py        # Endpoints de jobs (CRUD)
│   │   ├── upload.py      # Upload de arquivos/texto
│   │   └── health.py     # Health check
│   │
│   ├── services/
│   │   ├── fabot_tts.py  # Geração de áudio (Edge TTS)
│   │   ├── llm.py        # Integração com LLMs
│   │   ├── text_splitter.py # Divisão de texto grande
│   │   └── ...
│   │
│   ├── workers/
│   │   └── podcast_worker.py # Processamento em background
│   │
│   └── prompts/
│       └── script_template_v5.py # Prompt do LLM
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── InputPanel.jsx    # Coluna 1: Entrada
│   │   │   ├── ScriptPanel.jsx   # Coluna 2: Roteiro
│   │   │   └── PlayerPanel.jsx    # Coluna 3: Player
│   │   ├── store/
│   │   │   └── jobStore.js       # Estado global
│   │   └── App.jsx
│   └── package.json
│
├── data/
│   ├── output/            # Áudios gerados
│   └── uploads/          # Arquivos enviados
│
├── docker-compose.yml    # Orquestração de containers
└── README.md
```

---

## 📝 Descrição dos Arquivos

### Backend - Raiz

| Arquivo | Descrição |
|---------|------------|
| `config.py` | Configurações globais: chaves de API, caminhos, variáveis de ambiente |
| `database.py` | Conexão e inicialização do banco SQLite |
| `models.py` | Modelos ORM: Job (podcast), File (arquivos enviados) |
| `main.py` | Aplicação FastAPI principal, rotas, middleware |

### Backend - Routers

| Arquivo | Descrição |
|---------|------------|
| `routers/jobs.py` | Endpoints: criar job, listar, detalhes, gerar script, gerar áudio, deletar |
| `routers/upload.py` | Upload de arquivos e texto para criar jobs |
| `routers/health.py` | Health check da API |

### Backend - Services

| Arquivo | Descrição |
|---------|------------|
| `services/fabot_tts.py` | Engine de TTS: usa Edge TTS para gerar áudio de cada fala, concatena com pausas |
| `services/llm.py` | Integração com LLMs (Groq, Gemini, Ollama, GLM). Define como chamar cada API e parsear resposta |
| `services/text_splitter.py` | Divide textos grandes em seções menores para não exceder limite do LLM |
| `services/ingestor.py` | Extrai texto de PDFs e outros arquivos |

### Backend - Workers

| Arquivo | Descrição |
|---------|------------|
| `workers/podcast_worker.py` | Processamento em background: processa jobs em fila (gera roteiro → gera áudio) |

### Backend - Prompts

| Arquivo | Descrição |
|---------|------------|
| `prompts/script_template_v5.py` | Template do prompt que instrui o LLM a gerar roteiros no formato correto |

### Frontend - Components

| Arquivo | Descrição |
|---------|------------|
| `components/InputPanel.jsx` | Coluna 1: input de texto, upload de arquivo, campo de título |
| `components/ScriptPanel.jsx` | Coluna 2: exibe roteiros em caixas editáveis por personagem |
| `components/PlayerPanel.jsx` | Coluna 3: player de áudio, histórico, busca, filtros |
| `components/Header.jsx` | Cabeçalho com seleção de LLM, tema escuro, botão de histórico |

### Frontend - Store

| Arquivo | Descrição |
|---------|------------|
| `store/jobStore.js` | Estado global (Zustand): job atual, histórico, funções de API |

---

## 🔌 API Endpoints

### Jobs

| Método | Endpoint | Descrição |
|--------|----------|------------|
| POST | `/jobs/` | Criar novo job |
| GET | `/jobs/` | Listar todos os jobs |
| GET | `/jobs/{id}` | Ver detalhes de um job |
| POST | `/jobs/{id}/generate-script` | Gerar roteiro |
| POST | `/jobs/{id}/start` | Gerar roteiro + áudio |
| POST | `/jobs/{id}/start-tts` | Gerar áudio do roteiro |
| PUT | `/jobs/{id}/script` | Salvar roteiro editado |
| PATCH | `/jobs/{id}` | Atualizar título, categoria, favorito |
| DELETE | `/jobs/{id}` | Deletar job |
| GET | `/jobs/history` | Histórico com filtros (busca, categoria, favoritos) |

### Upload

| Método | Endpoint | Descrição |
|--------|----------|------------|
| POST | `/upload/` | Upload de arquivo |
| POST | `/upload/paste` | Enviar texto direto |

### Áudio

| Método | Endpoint | Descrição |
|--------|----------|------------|
| GET | `/audio/{filepath}` | Servir arquivo de áudio |

---

## 💾 Banco de Dados

### Tabela Jobs

```sql
jobs (
  id              VARCHAR(36) PRIMARY KEY,
  title           VARCHAR(255),
  status          VARCHAR(20),      -- PENDING, READING, LLM_PROCESSING, SCRIPT_DONE, DONE, FAILED
  progress        INTEGER,
  current_step   VARCHAR(255),
  script_json    TEXT,              -- Roteiro completo em JSON
  audio_path     VARCHAR(500),      -- Caminho do arquivo MP3
  duration_seconds INTEGER,
  category       VARCHAR(100),     -- Categoria (Python, ML, etc)
  tags           VARCHAR(500),     -- Tags separadas por vírgula
  is_favorite    BOOLEAN,
  playlist       VARCHAR(100),
  llm_mode        VARCHAR(20),      -- groq, glm, gemini, ollama
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
  file_type       VARCHAR(20),      -- pdf, txt, docx
  file_path       VARCHAR(500),
  extracted_text  TEXT,
  char_count      INTEGER,
  status          VARCHAR(20)
)
```

---

## ⚙️ Configuração

Variáveis de ambiente (`.env`):

```env
# Banco
DATABASE_PATH=backend/db/fabot.db

# Diretórios
OUTPUT_DIR=data/output
UPLOAD_DIR=data/uploads

# Redis
REDIS_URL=redis://localhost:6379

# LLMs
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
GLM_API_KEY=your_glm_key
OLLAMA_URL=http://localhost:11434

# Configurações
DEBUG=true
LOG_LEVEL=INFO
```

---

## 🚀 Como Executar

### Desenvolvimento

1. **Instalar dependências:**
```bash
cd fabot-studio
pip install -r requirements.txt
cd frontend && npm install
```

2. **Iniciar Redis:**
```bash
redis-server
```

3. **Iniciar Backend:**
```bash
cd fabot-studio
uvicorn backend.main:app --reload --port 8000
```

4. **Iniciar Frontend:**
```bash
cd fabot-studio/frontend
npm run dev
```

5. **Acessar:**
```
http://localhost:3000
```

### Docker

```bash
docker-compose up -d
```

---

## 🤖 LLMs Suportados

| Nome | Valor no Select | API Key Necessária |
|------|-----------------|-------------------|
| GLM-4-Flash | `glm` | Sim (gratuito) |
| Groq (Llama) | `groq` | Sim (gratuito) |
| Gemini Flash | `gemini` | Sim |
| Ollama Local | `ollama` | Não |

---

## ❌ Erros Comuns

### Áudio não toca
- Verificar se o backend está rodando
- Verificar caminho do arquivo no banco

### Roteiro não aparece
- Verificar se há script_json no banco
- Verificar console do navegador (F12)

### LLM não funciona
- Verificar API key no arquivo .env
- Verificar se há créditos na API

---

## 📜 Histórico de Atualizações

### 16/03/2026
- Interface completamente reformulada
- ScriptPanel com caixas editáveis por fala
- Cores por personagem (NARRADORA=Vermelho, WILLIAM=Azul, CRISTINA=Rosa)
- Adicionado GLM-4-Flash como LLM principal
- Sistema de favoritos
- Busca no histórico
- Categorias e playlists
- Modo escuro
- Exportação de roteiro
- Importação de podcasts prontos (ML e Python)
- Correção do sistema de áudio

---

## 📄 Licença

MIT License

---

**PRODUZIDO POR: FABIO ROSESTOLATO**

FABOT Podcast Studio - Transformando texto em conhecimento 🎙️
