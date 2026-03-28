# FABOT Planner — Manual para Implementação

> Este documento é escrito para que **outra IA** consiga entender, aplicar e
> debugar o sistema sem contexto adicional. Cada decisão de design está explicada.

---

## O que este sistema faz

Transforma um documento (PDF, TXT, DOCX) em uma série de roteiros de podcast
educacional com:

- Número de episódios calculado **matematicamente** (não pelo feeling do LLM)
- **100% do conteúdo coberto** — verificado antes de gerar qualquer roteiro
- **Qualidade constante** do episódio 1 ao N (contexto acumulado)
- Fallback automático entre 3 APIs (GLM-5 → Kimi → MiniMax)
- Estado salvo a cada etapa — retoma de onde parou se cair

---

## Estrutura de arquivos

```
fabot_planner/
├── models.py            Todos os tipos de dados (dataclasses)
├── api_router.py        Roteador de APIs com fallback
├── extractor.py         Leitura e estruturação do documento
├── concept_extractor.py Extração de conceitos via LLM
├── decisor.py           Cálculo matemático de episódios
├── grouper.py           Agrupamento em episódios (ordenação topológica)
├── coverage_check.py    Validação de cobertura 100%
├── content_bible.py     Geração da Content Bible via LLM
├── generator.py         Geração dos roteiros com contexto acumulado
├── validator.py         Validação dos roteiros gerados
├── pipeline.py          Orquestrador completo com estado
└── README_IA.md         Este arquivo
```

---

## Como executar

### Instalação de dependências

```bash
pip install openai pdfplumber
# Opcional mas recomendado:
pip install python-docx pypdf
```

### Execução básica

```bash
# Um arquivo PDF
python pipeline.py meu_livro.pdf

# Com título e diretório de saída personalizado
python pipeline.py estatistica.pdf --titulo "Estatística" --output ./output_est

# Forçar regeneração de tudo
python pipeline.py estatistica.pdf --force
```

### O que é gerado em `./output/`

```
output/
├── pipeline_state.json     Estado completo do pipeline
├── plano.json              Plano de todos os episódios (antes de gerar)
├── bible.json              Content Bible do documento
├── ep01_introducao.json    Roteiro do episódio 1
├── ep01_introducao.txt     Roteiro ep 1 em texto legível
├── ep02_variaveis.json
├── ep02_variaveis.txt
├── ...
├── validacao.json          Resultados de todas as validações
└── relatorio.txt           Relatório final
```

---

## Fluxo de dados entre módulos

```
arquivo.pdf
    ↓ extractor.py
DocumentoEstruturado (blocos, palavras, páginas, flags de código/fórmula)
    ↓ concept_extractor.py  [LLM]
list[Conceito] (id, nome, complexidade, dependencias, keywords)
    ↓ decisor.py  [matemática pura]
ResultadoDecisao (total_episodios, scores, segmentos_necessarios por conceito)
    ↓ grouper.py  [algoritmo de grafos]
PlanoCompleto (episodios com conceitos alocados, chunks de texto, depth_level)
    ↓ coverage_check.py  [lógica pura]
ResultadoCobertura (valido=True se 100% coberto, senão erros detalhados)
    ↓ content_bible.py  [LLM]
ContentBible (glossário, tom, exemplos do livro, o que não fazer)
    ↓ generator.py  [LLM por episódio]
list[Episodio] (roteiro JSON compatível com script_template_v7)
    ↓ validator.py  [lógica pura]
list[ResultadoValidacao] (valido, erros, avisos, conceitos cobertos)
```

---

## Por que cada módulo existe

### `models.py` — Tipos centralizados

**Problema resolvido:** código original criava dicionários ad-hoc em cada arquivo.
Um `dict` com `"conceitos"` no `decisor.py` pode ter campos diferentes do `dict`
com `"conceitos"` no `generator.py`. Isso causa KeyError silenciosos difíceis de
debugar.

**Solução:** todos os módulos importam de `models.py`. Se o tipo mudar, muda em
um lugar só e os erros aparecem em compile time.

### `api_router.py` — Fallback automático

**Problema resolvido:** código original usava só GLM-5. Se a API caía, o processo
parava. Tinha 3 chaves mas só uma era usada.

**Solução:**
```
GLM-5 falha → espera 10s → Kimi
Kimi falha  → espera 10s → MiniMax
MiniMax falha → RuntimeError com log detalhado de todas as falhas
```

**Como usar:**
```python
from api_router import chamar_llm

resposta = chamar_llm(
    system_prompt="Você é...",
    user_prompt="Faça isso...",
    esperar_json=True,   # Valida que a resposta é JSON antes de retornar
)
print(resposta.texto)    # JSON limpo (sem fences)
print(resposta.api_nome) # Qual API foi usada
```

### `extractor.py` — Estrutura real do documento

**Problema resolvido:** código original enviava `conteudo[:15000]` para o LLM.
Isso é o início do livro. Se o livro tem 400 páginas, 90% do conteúdo nunca
era analisado.

**Solução:** lê o documento inteiro e retorna `DocumentoEstruturado` com:
- Lista de `Bloco` (capítulo/seção/subseção) com texto, palavras, flags
- `texto_completo` para envio ao LLM em chunks
- Detecção de código e fórmulas (influencia o score de complexidade)

**Para documentos sem estrutura clara** (sem títulos de capítulo detectáveis):
O extractor trata o documento inteiro como um bloco único. A qualidade é menor
mas o sistema continua funcionando.

### `concept_extractor.py` — O que o LLM faz bem

**Por que o LLM e não regex:** identificar o que É um conceito pedagógico
(vs. exemplo, exercício, nota de rodapé) exige compreensão semântica.
Identificar que "bubble sort" DEPENDE de "vetor" exige leitura do contexto.

**Estratégia de chunking:**
O livro é dividido em chunks de ~2500 palavras. Cada chunk é analisado
separadamente. No final, os conceitos são deduplicados.

**Por que temperatura baixa (0.3):**
Extração de conceitos é tarefa analítica, não criativa. Temperatura baixa
= resposta mais consistente entre execuções.

### `decisor.py` — Matemática pura, zero LLM

**A fórmula:**

```
score_conceito = segmentos_min[complexidade]
               + (4 se tem_codigo)
               + (3 se tem_formula)
               + (subconcepts_count × 2)
               + (len(dependencias) × 1)
               + (max(0, paragrafos - 2) × 0.8)

segmentos_min = { baixa: 8, media: 12, alta: 18, critica: 22 }

total_segmentos = sum(score para cada conceito)
episodios_por_capacidade = ceil(total_segmentos / 40)
episodios_por_foco = ceil(len(conceitos) / 3)  # max 3 conceitos/ep
total_episodios = max(episodios_por_capacidade, episodios_por_foco)
```

**Por que não deixar o LLM decidir:**
Em testes, o LLM deu 4 episódios para um livro de algoritmos com 12 conceitos
de alta complexidade. A fórmula teria dado 8-10. A fórmula reflete a carga
real de conteúdo.

**Calibração:** os valores de `segmentos_min` foram derivados do
`script_template_v7.py` que exige mínimo de 40 segmentos por episódio com
mínimo de 10 por conceito. Com 3 conceitos por episódio = 30 segmentos mínimos.

### `grouper.py` — Ordenação topológica

**O problema:** se B depende de A, B nunca pode aparecer antes de A.
Com 15 conceitos e dependências cruzadas, isso é um problema de ordenação
de grafo dirigido.

**Kahn's Algorithm:**
1. Calcula o "grau de entrada" de cada nó (quantas deps tem)
2. Nós com grau 0 vão para a fila (podem aparecer primeiro)
3. Processa fila: adiciona ao resultado, decrementa grau dos dependentes
4. Nós que chegam a grau 0 entram na fila

**Empacotamento:** após a ordenação, empacota até 3 conceitos por episódio
respeitando o budget de 60 segmentos por episódio.

**Chunks de texto:** para cada grupo de conceitos, busca os blocos de origem
no documento e extrai até 3000 palavras de referência. O generator usa isso
como material de ensino — nunca tenta ensinar de memória.

### `coverage_check.py` — A garantia de 100%

**A verificação mais importante do sistema.** Sem ela, o pipeline pode gerar
10 episódios perfeitos que cobrem apenas 70% do livro.

**O que verifica:**
1. Todo conceito em exatamente 1 episódio (sem lacuna, sem duplicata)
2. Ordem de dependências respeitada
3. Nenhum episódio vazio
4. Nenhum episódio com >3 conceitos
5. Todos os chunks têm conteúdo suficiente
6. Estimativa de segmentos suficiente por episódio

**O pipeline para se qualquer verificação falhar** e reporta exatamente
o que está errado (não um erro genérico).

### `content_bible.py` — Consistência entre episódios

**O problema:** sem a bible, cada chamada ao generator é independente.
O episódio 7 pode definir "variável" de forma diferente do episódio 1.
Pode usar "Magazine Luiza" como exemplo no ep 1 e ep 7 e ep 12.

**A bible contém:**
- `glossario`: definições fixas de todos os termos técnicos
- `estilo_tom`: como falar sobre este assunto
- `exemplos_do_livro`: exemplos reais que o próprio livro usa
- `conceitos_centrais`: o núcleo que tudo orbita
- `o_que_nao_fazer`: erros comuns de interpretação

**bible_para_texto_prompt():** converte a bible em texto formatado que vai
no `system_prompt` de TODAS as chamadas ao generator. Não no user_prompt —
no system_prompt, que tem prioridade mais alta.

### `generator.py` — Contexto acumulado (a grande mudança)

**Problema original:** qualidade cai nos episódios do meio porque cada
chamada começa do zero.

**O que vai em cada chamada:**
```python
system_prompt = identidade_fixa + bible_completa

user_prompt = (
    "Ep 5 de 10"
    + "Conceitos a ensinar: [lista]"
    + "Depth: detailed"
    + "JÁ ENSINADO (não repetir): [últimos 8 conceitos cobertos]"
    + "RESUMO DO EP 4: [ep_summary + keywords do ep anterior]"
    + "PRÓXIMO EP vai precisar: [conceitos do ep 6]"
    + "NOTAS ESPECIAIS: [tem código, plantar semente]"
    + "MATERIAL: [chunk do documento]"
)
```

**Por que funciona:**
- A bible garante tom e glossário consistentes
- "JÁ ENSINADO" elimina repetição
- "RESUMO DO EP ANTERIOR" permite continuidade natural ("no episódio passado...")
- "PRÓXIMO EP vai precisar" força o generator a plantar a semente
- O chunk garante que o generator ensina o que ESTÁ NO LIVRO, não o que inventa

### `validator.py` — Critérios objetivos de qualidade

**Sem validação objetiva:** o pipeline aceita qualquer JSON retornado pelo LLM,
mesmo que tenha 8 segmentos e não mencione nenhum dos conceitos.

**O que valida:**
- Quantidade mínima de segmentos por depth_level
- NARRADOR apenas no segmento 1
- Falas com menos de 45 palavras
- pelo menos 1 `block_transition=true`
- Conceitos do plano foram cobertos (por keywords)
- Sem referências visuais ("como você pode ver")
- Sem código lido literalmente

**Se inválido:** o pipeline regenera até MAX_REGENERACOES vezes, depois aceita
com ressalva no relatório. Não para o processo inteiro por um episódio ruim.

### `pipeline.py` — Estado persistido

**A feature mais importante para uso prático:** se o processo cair no
episódio 7 de 12, na próxima execução retoma do ep 8.

**Estado salvo em `pipeline_state.json` após cada etapa:**
- Após extração
- Após extração de conceitos
- Após plano
- Após cada episódio gerado

**Pausa de 20s entre episódios:** respeita o rate limit das APIs.
Com 10 episódios, o processo total leva ~5-7 minutos de espera mais
o tempo de geração (~2-4 min/ep) = total ~30-50 minutos.

---

## Casos de uso e comportamento esperado

### Livro pequeno (1 capítulo, ~10 páginas)

```
Conceitos extraídos: 5-8
Episódios calculados: 2-3
Tempo estimado: 15-20 min
```

### Livro médio (6 capítulos, ~80 páginas)

```
Conceitos extraídos: 15-25
Episódios calculados: 6-10
Tempo estimado: 45-90 min
```

### Livro grande (15+ capítulos, 300+ páginas)

```
Conceitos extraídos: 30-50
Episódios calculados: 12-20
Tempo estimado: 2-4 horas
Recomendação: dividir por capítulo e processar separado
```

---

## Troubleshooting

### "Nenhum bloco estruturado detectado"

O documento não tem títulos de capítulo reconhecíveis.
O extractor trata tudo como 1 bloco — funciona, mas a qualidade de chunking
para cada episódio será menor. Para melhorar: adicione padrões ao `_PADROES_CAPITULO`
em `extractor.py` que correspondam ao formato do seu documento.

### "Cobertura inválida: conceito X sem episódio"

O grouper não alocou o conceito X. Causas possíveis:
1. O conceito tem dependências circulares não detectadas
2. O empacotamento guloso criou um grupo onde X não coube

Solução: verificar `plano.json` e ajustar manualmente ou aumentar
`MAX_CONCEITOS_POR_EPISODIO` em `grouper.py`.

### "Todas as APIs falharam"

Verificar:
1. As chaves de API estão válidas (testar diretamente com curl)
2. A conexão com `integrate.api.nvidia.com` está disponível
3. Não está em rate limit (aguardar 1-2 min e tentar de novo)

### Episódio gerado com poucos segmentos

O LLM às vezes gera respostas curtas mesmo com instruções de mínimo.
O validator detecta e o pipeline regenera automaticamente (até 3 vezes).
Se persistir: aumentar `max_tokens_override` em `api_router.py`.

### JSON inválido do LLM

O `api_router.py` detecta JSON inválido e trata como falha, tentando
a próxima API. Se todas retornam JSON inválido, verificar se o prompt
está muito longo (>8000 tokens) e reduzir o chunk de texto.

---

## Como integrar ao projeto principal (fabot-studio)

O sistema foi desenvolvido como módulo independente de teste.
Para integrar ao fabot-studio:

1. Copiar todos os arquivos para `backend/planner/`
2. Ajustar `api_router.py` para usar as chaves do `config.py` do projeto
3. Adaptar `pipeline.py` para ser chamado como task ARQ em vez de CLI
4. O output (list de `Episodio` com JSON de segmentos) é diretamente
   compatível com o formato que o `podcast_worker.py` espera para gerar áudio

---

## Compatibilidade com script_template_v7.py

O `generator.py` gera JSON no formato exato do `script_template_v7.py`:

```json
{
  "title": "...",
  "episode_summary": "...",
  "keywords": ["..."],
  "segments": [
    {
      "speaker": "NARRADOR",
      "text": "...",
      "emotion": "neutral",
      "pause_after_ms": 1800,
      "block_transition": false
    }
  ]
}
```

Speakers: `"NARRADOR"`, `"WILLIAM"`, `"CRISTINA"` — exatamente como
`SPEAKER_VOICE_MAP` em `script_template_v7.py`.

---

*FABOT Planner — Desenvolvido para o projeto FABOT Podcast Studio*
*Compatível com script_template_v7.py e a arquitetura FastAPI+ARQ do projeto principal*
