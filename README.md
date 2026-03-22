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

O FABOT usa 3 vozes FIXAS para criar diálogos naturais:

| Personagem | Voz Edge TTS | Cor na Interface | Descrição |
|-----------|--------------|-------------------|------------|
| **NARRADORA** | ThalitaMultilingualNeural | 🔴 Vermelho | APRESENTA o tema, faz introduções e transições |
| **WILLIAM** | AntonioNeural | 🔵 Azul | FAZ PERGUNTAS, representa o ouvinte curioso |
| **VILMA** | FranciscaNeural | 🩷 Rosa | EXPLICA os conceitos, é a "professora" |

### Personagens vs Apresentadores

**Personagens FIXOS (voz não muda):**
- NARRADORA (Thalita) - só na introdução
- WILLIAM (Antonio) - voz masculina
- VILMA (Francisca) - voz feminina

**Apresentadores (nomes que podem mudar):**
- Host = WILLIAM (pode mudar nome, voz NÃO muda)
- Co-host = VILMA (pode mudar nome, voz NÃO muda)

### Estrutura do Roteiro

Cada episódio segue uma estrutura didática:

1. **NARRADORA** → Introduz o tema (ex: "Olá Vanda!")
2. **WILLIAM** → Faz pergunta sobre o conceito
3. **VILMA** → Explica com exemplos e analogias
4. (Repete esse padrão durante todo o episódio)
5. **NARRADORA** → Faz despedida (ex: "Até o próximo episódio, Vanda!")

### Personalização Automática

Quando configurado no ConfigPanel (⚙️):
- NARRADOR saúda pelo nome do ouvinte
- WILLIAM/VILMA mencionam pessoas próximas nos exemplos
- Encerramento personalizado com nome do ouvinte

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

### 20/03/2026 - Sistema de Personalização Completo 🎉

**NOVO RECURSO: ConfigPanel - Personalização Total do Podcast**

O FABOT agora permite personalizar completamente cada podcast através do botão ⚙️ no cabeçalho.

#### O que pode ser personalizado:

1. **Quem vai ouvir (Aluno/Ouvinte)**
   - Nome da pessoa que vai ouvir o podcast
   - Este nome é usado para saudações personalizadas no roteiro

2. **Pessoas Próximas (Afetivo)**
   - Lista de pessoas próximas (mãe, pai, esposa, filho, etc.)
   - Usadas em exemplos durante o podcast
   - Exemplo: "Célia, sua mãe, sabe como é importante controlar o estoque"

3. **Apresentadores (Host e Co-host)**
   - Nomes podem ser alterados
   - Vozes são FIXAS (não mudam):
     - NARRADORA = Thalita (voz feminina)
     - WILLIAM = Antonio (voz masculina)
     - VILMA = Francisca (voz feminina)
   
4. **Personagens de Exemplo**
   - Lista de personagens fictícios para usar nos exemplos
   - Formato: Nome - Cargo - Empresa
   - Exemplo: Luciano Hang - CEO - Havan

5. **Empresas**
   - Lista de empresas reais para usar nos exemplos
   - Exemplo: Havan, Magazine Luiza, Nubank, Itaú

6. **Opções**
   - Saudar pelo nome no início
   - Mencionar pessoas próximas
   - Despedida personalizada

#### Como funciona:

1. Clique em ⚙️ (Config) no cabeçalho
2. Configure os nomes e opções
3. Clique em "Salvar Configuração"
4. Os 3 cards na coluna central mostram os apresentadores configurados
5. Ao gerar um podcast, o roteiro será personalizado automaticamente

#### Fluxo de personalização:

```
ConfigPanel → Salvar → Redis/Banco
                           ↓
                   load_config_variables()
                           ↓
                   Template v6 + Jinja2
                           ↓
                   Roteiro Personalizado
```

#### Arquivos principais:

- `frontend/src/components/ConfigPanel.jsx` - Interface de configuração
- `backend/routers/config.py` - API de configuração
- `backend/prompts/script_template_v6.py` - Template com variáveis Jinja2
- `backend/services/llm.py` - Injeção de variáveis no prompt

---

### 20/03/2026 - Template v6 com Jinja2

**Substituição do Template v5 pelo v6**

O novo template usa Jinja2 para injetar variáveis de configuração diretamente no prompt.

#### Variáveis disponíveis:

```python
{
    "usuario_nome": "Vanda",           # Quem vai ouvir
    "pessoas_proximas": [              # Pessoas para exemplos
        {"nome": "Célia", "relacao": "mãe"}
    ],
    "host_nome": "William",            # Nome do apresentador
    "cohost_nome": "Vilma",            # Nome da apresentadora
    "personagens": [                   # Personagens de exemplo
        {"nome": "Luciano Hang", "cargo": "CEO", "empresa": "Havan"}
    ],
    "empresas": ["Havan", "Magazine Luiza"],  # Empresas de exemplo
    "saudar_nome": True,               # Saudar pelo nome
    "mencionar_pessoas": True,         # Mencionar pessoas próximas
    "despedida_personalizada": True    # Despedida com nome
}
```

#### Exemplo de prompt personalizado:

```
NARRADOR: "Olá Vanda! Um abraço especial para Célia também!"
WILLIAM: "Vanda, você sabia que a precificação correta..."
VILMA: "Sim, e para isso a Havan precisa entender..."
```

---

### 20/03/2026 - Bug do Cache Corrigido 🔴 CRÍTICO

**PROBLEMA CRÍTICO: Cache Redis não incluía variáveis de configuração**

O cache do LLM usava apenas o hash do texto de entrada para gerar a chave.
Quando o usuário mudava a configuração (ex: Cristina → Vilma) e gerava
um podcast com o MESMO texto, o Redis retornava o roteiro antigo cacheado.

**Causa raiz:**
```python
# ANTES (ERRADO):
text_hash = compute_text_hash(text)
config_hash = compute_config_hash(config)  # config NÃO tinha as variáveis do banco!
cached = cache_manager.get(text_hash, config_hash)
```

**Solução:**
```python
# DEPOIS (CORRETO):
config_vars = load_config_variables()  # Carrega do banco ANTES
text_hash = compute_text_hash(text)
config_hash = compute_config_hash({**config, **config_vars})  # Inclui variáveis!
cached = cache_manager.get(text_hash, config_hash)
```

**Arquivo corrigido:** `backend/services/llm.py`

---

### 20/03/2026 - Bug do Pydantic Serialization

**PROBLEMA: Objetos Pydantic não são JSON serializáveis**

Ao salvar configuração com personagens/pessoas_proximas, o backend retornava
Internal Server Error porque `json.dumps()` não funciona com objetos Pydantic.

**Causa:**
```python
# ERRO:
config.personagens = json.dumps(data.personagens)  # data.personagens é lista de Pydantic models!
```

**Solução:**
```python
# CORRETO:
config.personagens = json.dumps([p.model_dump() for p in data.personagens])
```

**Arquivos corrigidos:**
- `backend/routers/config.py` - Linhas 89, 103

---

### 20/03/2026 - Voz Vilma Adicionada

**PROBLEMA: Nome Cristina hardcoded no fabot_tts.py**

O mapeamento de vozes não tinha Vilma, então o TTS usava William como fallback.

**Solução:** Adicionado mapeamento para Vilma:
```python
VOICES = {
    "NARRADOR": {"voice": "pt-BR-ThalitaMultilingualNeural"},
    "William": {"voice": "pt-BR-AntonioNeural"},
    "Vilma": {"voice": "pt-BR-FranciscaNeural"},  # Adicionado!
}
```

**Arquivo corrigido:** `backend/services/fabot_tts.py`

---

### 20/03/2026 - Worker ARQ Entry Point

**PROBLEMA: docker-compose.yml apontava para módulo sem entry point**

O comando `python -m backend.workers.podcast_worker` não funcionava porque
o arquivo não tinha `__main__.py`.

**Solução:** Criado `backend/workers/__main__.py` com entry point correto.

---

### 20/03/2026 - Bug do jobId no Catch

**PROBLEMA: Variável jobId declarada com let dentro do try**

Se ocorresse erro antes da atribuição, o catch tentava `updateActiveJob(undefined)`.

**Solução:**
```javascript
// ANTES (ERRADO):
try {
    let jobId;  // ← pode falhar antes da atribuição
    ...
} catch (error) {
    if (jobId) updateActiveJob(jobId, ...);  // ← undefined aqui!
}

// DEPOIS (CORRETO):
let jobId = null;  // ← inicializado
try {
    ...
} catch (error) {
    if (jobId) updateActiveJob(jobId, ...);  // ← funciona
} finally {
    if (!jobId) console.warn("Job não foi criado");
}
```

**Arquivo corrigido:** `frontend/src/App.jsx`

---

### 20/03/2026 - LocalStorage com Job Inexistente

**PROBLEMA: currentJobId persistido mas job deletado do banco**

Ao reabrir a página, o frontend tentava buscar um job que não existia mais.

**Solução:** Tratamento de 404 no useEffect que carrega currentJob.

**Arquivo corrigido:** `frontend/src/App.jsx`

---

### 20/03/2026 - Frontend: 3 Cards de Apresentadores

**NOVO RECURSO: Visualização instantânea da configuração**

Quando não há roteiro carregado, a coluna central mostra 3 cards com
os nomes dos apresentadores configurados.

**Benefício:** Permite verificar se a configuração está correta sem
precisar gerar um podcast apenas para confirmar.

**Implementação:**
```jsx
// ScriptPanel.jsx - Quando !hasScript
<div className="presenter-preview">
  <div className="presenter-card narrador">
    <div className="presenter-icon">🎤</div>
    <div className="presenter-name">NARRADORA</div>
    <div className="presenter-role">Voz de abertura</div>
  </div>
  <div className="presenter-card host">
    <div className="presenter-icon">🎙️</div>
    <div className="presenter-name">{config?.apresentador?.nome || "WILLIAM"}</div>
    <div className="presenter-role">Apresentador</div>
  </div>
  <div className="presenter-card cohost">
    <div className="presenter-icon">🎙️</div>
    <div className="presenter-name">{config?.apresentadora?.nome || "CRISTINA"}</div>
    <div className="presenter-role">Apresentadora</div>
  </div>
</div>
```

---

### 18/03/2026 - Correção Crítica do Edge TTS 🔴

**PROBLEMA CRÍTICO DESCOBERTO:**
O Edge TTS **NÃO SUPORTA SSML customizado**. O código estava gerando XML completo que era lido como texto pelo TTS.

**Sintomas:**
- Áudio falava: "Speak version equals 1.0, XML and SQLs, HTTP..."
- Tags SSML sendo lidas como texto
- Áudio completamente inutilizável

**Causa:**
```python
# ANTES (ERRADO):
ssml = """<speak version="1.0" xmlns="..." xml:lang="pt-BR">
  <voice name="...">
    <prosody rate="...">
      Texto aqui
    </prosody>
  </voice>
</speak>"""
communicate = edge_tts.Communicate(ssml, voice)
```

**Solução:**
```python
# DEPOIS (CORRETO):
communicate = edge_tts.Communicate(
    texto_limpo,  # Sem tags SSML
    voice,
    rate="-5%",   # Parâmetros diretamente
    pitch="+0Hz"
)
```

**Arquivo corrigido:** `backend/services/fabot_tts.py`

---

### 18/03/2026 - Limpeza de Pastas

**Problema:**
Existiam pastas duplicadas fora do projeto:
- `/ELEVENLABS2/backend/` (vazia, não usada)
- `/ELEVENLABS2/data/` (parcial, não usada)
- `/ELEVENLABS2/fabot-studio/` (projeto real)

**Solução:**
- Apagadas pastas não utilizadas
- Projeto centralizado em `fabot-studio/`

---

### 18/03/2026 - Melhorias no Worker ARQ

**Problemas corrigidos:**
1. Status mismatch: worker aceitava só `SCRIPT_DONE`, mas endpoint mudava para `TTS_QUEUED`
2. worker não recarregava código após updates

**Solução:**
```python
# Worker agora aceita ambos statuses:
if job.status not in ("SCRIPT_DONE", "TTS_QUEUED"):
    raise ValueError(f"Status inválido para TTS: {job.status}")
```

---

### 17/03/2026 - Interface Reformulada

- ScriptPanel com caixas editáveis por fala
- Cores por personagem (NARRADORA=Vermelho, WILLIAM=Azul, CRISTINA=Vilma=Rosa)
- Sistema de favoritos
- Busca no histórico
- Modo escuro

---

## 📊 Limites dos LLMs

### Gemini 2.5 Flash (GRÁTIS) ⭐ PADRÃO
| Limite | Valor |
|--------|-------|
| Requests/minuto | 15 |
| Requests/dia | 1.500 |
| Tokens contexto | 1M |
| Custo | **GRÁTIS** |

**Recomendação:** Use para ~10-15 podcasts/dia sem problemas.

### Groq (Llama 3.3 70B)
| Limite | Valor |
|--------|-------|
| Requests/minuto | 30 |
| Custo | **GRÁTIS** (tier free) |

### GLM-4-Flash
| Limite | Valor |
|--------|-------|
| Custo | **GRÁTIS** |

---

## 🐛 Debugging - Checklist de Problemas

Se o sistema não funcionar, verifique nesta ordem:

1. **Backend rodando?**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Redis rodando?**
   ```bash
   redis-cli ping
   ```

3. **Worker ARQ rodando?**
   ```bash
   ps aux | grep arq
   ```

4. **Worker recarregado após mudanças?**
   ```bash
   pkill -f "arq backend.workers"
   # Reiniciar worker
   ```

5. **Status do job correto?**
   ```bash
   curl http://localhost:8000/jobs/{id}
   ```

---

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

## 🔮 Próximas Melhorias Planejadas

- [ ] Monitoramento de erros mais claro no frontend
- [ ] Auto-retry quando falhar
- [ ] Notificação quando podcast estiver pronto
- [ ] Salvar podcasts por nome do tema (em vez de UUID)
- [ ] Configurações de apresentador no frontend (nome, empresa, área)
- [ ] OCR para extrair texto de imagens
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
