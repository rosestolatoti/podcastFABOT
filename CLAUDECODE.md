# CLAUDECODE.md — FABOT Podcast Studio

## 📅 Atualização: 26/03/2026
## 🎯 Versão: 2.2.0

---

## 🎙️ IDENTIDADE DO PROJETO

### Nome Fixo: **FABOT PODCAST**
- O nome do podcast NUNCA muda
- TODO episódio deve mencionar "FABOT Podcast"
- Call-to-action: "Não esqueça de assinar o FABOT Podcast"

### 3 Vozes Edge (FIXAS - nunca mudam)
| Personagem | Voz Edge TTS | Uso |
|------------|--------------|-----|
| NARRADOR | `pt-BR-ThalitaMultilingualNeural` | Abertura e fechamento |
| WILLIAM | `pt-BR-AntonioNeural` | Faz perguntas, representa ouvinte |
| CRISTINA | `pt-BR-FranciscaNeural` | Explica conceitos |

### Personalizações Variáveis
- **Ouvinte:** Nome de quem ouve (ex: Fabio)
- **Pessoas próximas:** Nome e relação (ex: Fabricio, filho, 5 anos)
- **Empresas:** Para exemplos (Nubank, Itau, Magazine Luiza)
- **Personagens fictícios:** Para cenários

---

## 📁 ESTRUTURA DO PROJETO

```
fabot-studio/
├── backend/
│   ├── prompts/
│   │   ├── script_template_v7.py  ← RAIZ DO PODCAST
│   │   └── prompt_variator.py
│   ├── services/
│   │   ├── content_planner/       ← 11 MÓDULOS A INTEGRAR
│   │   └── llm.py
│   ├── routers/
│   │   └── jobs.py               ← EXPANDIR
│   └── models.py                 ← EXPANDIR
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ScriptPanel.jsx    ← DASHBOARD EPISÓDIOS
│       │   └── InputPanel.jsx    ← BOTÃO "GERAR SÉRIE"
│       └── store/
│           └── jobStore.js
└── data/output/
```

---

## 🔄 PIPELINE DE 7 ETAPAS (TESTE2 INTEGRATION)

O LLM decide MATEMATICAMENTE quantos episódios criar via **decisor.py**:

```
1. EXTRACTOR → Extrai estrutura do documento
        ↓
2. CONCEPT_EXTRACTOR → Extrai conceitos pedagógicos (LLM)
        ↓
3. DECISOR → Fórmula matemática decide qtd episódios
        ↓
4. GROUPER → Agrupamento topológico (ordem correta)
        ↓
5. COVERAGE_CHECK → Validação 100% cobertura
        ↓
6. CONTENT_BIBLE → Glossário + tom + exemplos (LLM)
        ↓
7. GENERATOR → Gera N episódios (LLM)
   └─ Contexto acumulado
   └─ Anti-repetição
   └─ Menção FABOT
```

---

## 📊 11 ARQUIVOS A INTEGRAR (TESTE2_INTEGRATION/)

| Arquivo | Função | LLM? |
|---------|--------|-------|
| `models.py` | Tipos (dataclasses) | Não |
| `api_router.py` | Fallback GLM-5→Kimi→MiniMax | Não |
| `extractor.py` | Leitura PDF/TXT/DOCX | Não |
| `concept_extractor.py` | Extrai conceitos pedagógicos | SIM |
| `decisor.py` | **Decide qtd episódios MATEMATICAMENTE** | Não |
| `grouper.py` | Ordenação topológica | Não |
| `coverage_check.py` | Valida 100% cobertura | Não |
| `content_bible.py` | Gera glossário + tom | SIM |
| `generator.py` | Gera roteiros c/ contexto | SIM |
| `validator.py` | Valida roteiros | Não |
| `pipeline.py` | Orquestrador com estado | Não |

---

## 🧮 FÓRMULA MATEMÁTICA (decisor.py)

O **DECISOR decide quantos episódios criar**:

```python
score_conceito = segmentos_base[complexidade]
              + (4 se tem_codigo)
              + (3 se tem_formula)
              + (subconcepts × 2)
              + (dependencies × 1)

segmentos_min = { baixa: 8, media: 12, alta: 18, critica: 22 }

total_episodios = max(
    total_segmentos / 40,        # por capacidade
    len(conceitos) / 3          # por foco (max 3 conceitos/ep)
)
```

**O LLM NÃO decide - a MATEMÁTICA decide!**

---

## 📝 REGRAS DE QUALIDADE

### Para QUALQUER Assunto
1. Mínimo de segmentos: 40 por episódio (ideal: 50-70)
2. Cada conceito: Mínimo 10 segmentos
3. Fórmulas matemáticas: Explicar 3x com exemplos
4. Código: Descrever o que FAZ, nunca ler literalmente
5. Expressões humanas: Risadas, "uau", "nossa", expressões naturais

### Call-to-Action (OBRIGATÓRIO)
Todo episódio DEVE ter:
1. Menção "FABOT Podcast" pelo menos 1x
2. "Não esqueça de assinar o podcast" no final
3. "Se gostou, compartilhe com alguém"

### Menções Pessoais (Fabio + Fabricio)
- **Fabio:** Ouvinte principal
- **Fabricio:** Filho, 5 anos
  - Máximo 1-2 menções por episódio
  - Tom elogioso e afetivo
  - Exemplo: "O Fabricio, com 5 anos, já tá aprendendo números..."

---

## 🎯 IMPLEMENTAÇÃO NECESSÁRIA

### Backend
- [ ] Criar `backend/services/content_planner/`
  - Copiar 11 arquivos de `TESTE2_INTEGRATION/`
  - Adaptar imports para usar `backend.services.llm.get_provider()`
- [ ] Estender `backend/models.py`
  ```python
  episodes_count = Column(Integer, default=1)
  episodes_json = Column(Text, nullable=True)
  pipeline_mode = Column(String(20), default="single")
  pipeline_status = Column(String(50), nullable=True)
  ```
- [ ] Criar endpoints:
  - `POST /jobs/{id}/generate-multi` → Pipeline inteligente
  - `GET /jobs/{id}/episodes` → Lista roteiros
  - `POST /jobs/{id}/start-tts-all` → TTS todos eps

### Frontend
- [ ] InputPanel: Botão "Gerar Série de Podcasts"
- [ ] ScriptPanel: Dashboard episódios
  ```
  ┌──────────────────────────────────────────────┐
  │ 📊 SÉRIE: X Episódios    [▶ Gerar Áudio]   │
  ├──────────┬──────────┬──────────────────────────┤
  │ 📖 Ep 01│ 📖 Ep 02│ 📖 Ep 03 │ ...        │
  │ ✅ Pronto│ ✅ Pronto│ ⏳ Processando...│         │
  └──────────┴──────────┴──────────────────────────┘
  ```
- [ ] Barra progresso 7 etapas
- [ ] Roteiros concatenados com divisores

---

## 📊 DADOS DO USUÁRIO

| Campo | Valor |
|-------|-------|
| Ouvinte | Fabio |
| Pessoa próxima | Fabricio (filho, 5 anos) |
| Empresas | Nubank, Itau, Magazine Luiza |

---

## 🔧 OTIMIZAÇÕES DE BANCO

```sql
CREATE INDEX idx_jobs_pipeline_mode ON jobs(pipeline_mode);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
```

---

## 🚀 PRÓXIMOS PASSOS

1. **Integrar 11 arquivos** ao `backend/services/content_planner/`
2. **Adaptar api_router** para usar `backend.services.llm.get_provider()`
3. **Estender models.py** com campos multi-episódio
4. **Criar endpoints** generate-multi, episodes, start-tts-all
5. **Atualizar frontend** com dashboard e botão
6. **Testar pipeline** completo
7. **Gerar relatório** final

---

## 📈 MÉTRICAS DE SUCESSO

| Métrica | Meta |
|---------|------|
| Segmentos por episódio | 50-70 |
| Conceitos por episódio | 1-3 |
| Cobertura | 100% |
| Menção FABOT | 1+ por episódio |
| CTA assinatura | No final |
| Referência Fabricio | 1-2 (orgânico) |

---

## ⚠️ REGRAS FUNDAMENTAIS

1. **Podcast pode ter 20+ minutos** - qualidade > velocidade
2. **Qualidade > quantidade** - não limitar segmentos
3. **Humanização é crítica** - não deixar robótico
4. **FABOT é a marca** - SEMPRE mencionar
5. **Decisor decide** - NÃO o feeling do LLM

---

**Última atualização:** 26/03/2026
**Status:** Em implementação
