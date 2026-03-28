# FABOT PODCAST STUDIO - MEMÓRIA DO PROJETO

## 📅 Data: 26/03/2026
## 🎯 Versão: 2.2.0 (Em desenvolvimento)
## 👤 Responsável: Fabio Rosestolato

---

## 🎙️ IDENTIDADE DO PROJETO

### Nome Fixo
**FABOT PODCAST** - Nunca muda!

### 3 Vozes Edge (FIXAS - nunca mudam)
| Personagem | Voz Edge TTS | Uso |
|------------|--------------|-----|
| NARRADOR | `pt-BR-ThalitaMultilingualNeural` | Abertura e fechamento |
| WILLIAM | `pt-BR-AntonioNeural` | Faz perguntas, representa ouvinte |
| CRISTINA | `pt-BR-FranciscaNeural` | Explica conceitos |

### Personalizações (variáveis)
- **Ouvinte:** Nome de quem ouve (ex: Fábio)
- **Pessoas próximas:** Nome e relação (ex: Fabricio, filho, 5 anos)
- **Empresas:** Para exemplos (Nubank, Itaú, Magazine Luiza, etc)
- **Personagens fictícios:** Para cenários

---

## 📚 ARQUITETURA DO SCRIPT (RAIZ)

### arquivo: `backend/prompts/script_template_v7.py`

Este é o **CORAÇÃO** do sistema. Define TUDO sobre como o roteiro é gerado.

```python
SPEAKER_VOICE_MAP = {
    "NARRADOR": "pt-BR-ThalitaMultilingualNeural",
    "WILLIAM": "pt-BR-AntonioNeural",
    "CRISTINA": "pt-BR-FranciscaNeural",
}
```

### Estrutura do Prompt

1. **IDENTIDADE FIXA** - Apresentadores e ouvinte
2. **PERSONAGENS/EMPRESAS** - Para exemplos personalizados
3. **DENSIDADE OBRIGATÓRIA** - Mínimo 10 segmentos por conceito
4. **ESTRUTURA DO EPISÓDIO** - Narrador → Blocos → Fechamento
5. **REGRAS DE ÁUDIO** - O ouvinte está no carro, não vê tela

---

## 🎯 REGRAS FUNDAMENTAIS

### Para QUALQUER Assunto

1. **Mínimo de segmentos:** 40 por episódio (ideal: 50-70)
2. **Cada conceito:** Mínimo 10 segmentos
3. **Fórmulas matemáticas:** Explicar 3x com exemplos
4. **Código:** Descrever o que FAZ, nunca ler literalmente
5. **Expressões humanas:** Risadas, "uau", "nossa", expressões naturais

### Para estatística/ML

1. **Desvio padrão:** Explicar com examples do cotidiano
2. **Variância:** Mostrar cálculo passo a passo
3. **Amplitude:** Range simples de entender
4. **Frequência:** Distribuição de dados
5. **Covariância/Correlação:** Para ML

### Para Menções Pessoais

- **Fábio:** Ouvinte principal
- **Fabricio:** Filho, 5 anos - mencionar organicamente
  - Exemplo: "O Fabricio, com 5 anos, já tá aprendendo números..."
  - NÃO toda hora - máximo 1-2 por episódio
  - Tom elogioso e afetivo

### Call-to-Action (FABOT)

Todo episódio DEVE ter:
1. Menção "FABOT Podcast" pelo menos 1x
2. "Não esqueça de assinar o podcast" no final
3. "Se gostou, compartilhe com alguém"

---

## 🔄 PIPELINE DE 7 ETAPAS (TESTE2)

```
1. Extração Estrutural (blocos do documento)
        ↓
2. Conceitos via LLM (pedagógicos)
        ↓
3. Fórmula Matemática (quantos episódios)
        ↓
4. Agrupamento Topológico (ordem correta)
        ↓
5. Validação 100% Cobertura
        ↓
6. Content Bible (glossário + tom)
        ↓
7. Geração N episódios (c/ contexto)
```

---

## 📊 DADOS DO USUÁRIO

| Campo | Valor |
|-------|-------|
| Ouvinte | Fábio |
| Pessoa próxima | Fabricio (filho, 5 anos) |
| Empresas preferidas | Nubank, Itaú, Magazine Luiza |

---

## 🎯 CRITÉRIOS DE QUALIDADE

### Cobertura
- 100% dos conceitos devem ser cobertos
- Cada conceito = mínimo 10 segmentos
- Nenhum conceito pode ser pulado

### Humanização
- Expressões naturais: "uau", "nossa", "puxa"
- Risadas disfarçadas: "kkkk", "rsrs"
- Elogios ao ouvinte: "Você tá pegando rápido"
- Referência ao Fabricio (quando orgânico)

### Call-to-Action
```python
CTA_FABOT = """
Lembre-se: assine o FABOT Podcast para não perder nenhum episódio.
Se você aprendeu algo hoje, compartilhe com alguém que também precisa.
"""
```

---

## 📁 ESTRUTURA DE ARQUIVOS

```
fabot-studio/
├── backend/
│   ├── prompts/
│   │   ├── script_template_v7.py  ← RAIZ DO PODCAST
│   │   └── prompt_variator.py
│   ├── services/
│   │   ├── content_planner/       ← NOVO: 11 módulos
│   │   │   ├── models.py
│   │   │   ├── extractor.py
│   │   │   ├── concept_extractor.py
│   │   │   ├── decisor.py
│   │   │   ├── grouper.py
│   │   │   ├── coverage_check.py
│   │   │   ├── content_bible.py
│   │   │   ├── generator.py
│   │   │   ├── validator.py
│   │   │   └── pipeline.py
│   │   └── llm.py
│   ├── routers/
│   │   └── jobs.py               ← Expandir c/ multi-episode
│   └── models.py                 ← Expandir c/ episodes_*
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ScriptPanel.jsx    ← Dashboard episodios
│       │   └── InputPanel.jsx    ← Botão "Gerar Série"
│       └── store/
│           └── jobStore.js
│
└── data/
    └── output/                   ← Episódios em subpastas
```

---

## 🚀 FUNCIONALIDADES A IMPLEMENTAR

### Backend
- [x] script_template_v7.py (RAIZ)
- [ ] content_planner/ (11 módulos)
- [ ] Endpoints: generate-multi, episodes, start-tts-all
- [ ] Banco: episodes_count, episodes_json, pipeline_mode

### Frontend
- [ ] Botão "Gerar Série de Podcasts"
- [ ] Dashboard com N episódios
- [ ] Barra progresso 7 etapas
- [ ] Roteiros concatenados com divisores

### Pipeline
- [ ] Geração com contexto acumulado
- [ ] Anti-repetição entre episódios
- [ ] Validação de menção FABOT
- [ ] CTA automático

---

## 📈 MÉTRICAS DE SUCESSO

| Métrica | Meta |
|---------|------|
| Segmentos por episódio | 50-70 |
| Conceitos por episódio | 1-3 |
| Cobertura | 100% |
| Menção FABOT | 1+ por episódio |
| CTA assinatura | No final de cada episódio |
| Referência Fabricio | 1-2 por episódio (orgânico) |

---

## 🔧 OTIMIZAÇÕES DE BANCO

### Novos campos no Job
```python
episodes_count = Column(Integer, default=1)
episodes_json = Column(Text, nullable=True)  # Lista de roteiros
pipeline_mode = Column(String(20), default="single")
pipeline_status = Column(String(50), nullable=True)
pipeline_etapa = Column(String(100), nullable=True)
```

### Índices sugeridos
```sql
CREATE INDEX idx_jobs_pipeline_mode ON jobs(pipeline_mode);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
```

---

## 🎓 TEXTO DE TESTE (Estatística para ML)

Gerar episódios sobre:
1. **Desvio Padrão** - Medida de dispersão
2. **Variância** - Quadrado do desvio
3. **Amplitude** - Range dos dados
4. **Frequência** - Distribuição
5. **Covariância/Correlação** - Para ML

---

## 📝 NOTAS IMPORTANTES

1. **Podcast pode ter 20+ minutos** se necessário para cobertura
2. **Qualidade > velocidade** - não limitar segmentos
3. **Humanização é crítica** - não deixar robótico
4. **FABOT é a marca** - SEMPRE mencionar
5. **Fábio e Fabricio** - referências afetivas

---

## 🕐 TIMELINE

- [x] Análise do projeto
- [ ] Implementação Phase 2 (content_planner)
- [ ] Testes e ajustes
- [ ] Geração de episódios de teste
- [ ] Documentação final

---

**Última atualização:** 26/03/2026
**Próximo passo:** Implementar content_planner com 11 módulos
