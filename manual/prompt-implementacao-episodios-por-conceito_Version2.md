# FABOT Podcast — Implementar Geração por Conceitos

## Contexto

O FABOT Podcast Studio é um sistema que gera podcasts educacionais a partir de texto.
Atualmente, ele divide o texto por headers Markdown (`##`) ou por tamanho de tokens.
Isso resulta em episódios rasos que resumem o texto em vez de expandir cada conceito.

## Objetivo

Implementar um novo fluxo de geração onde:
1. O LLM extrai os conceitos-chave do texto
2. Planeja episódios (1 conceito principal por episódio)
3. Gera cada roteiro com PROFUNDIDADE — histórias, exemplos reais, erros comuns, cuidados

## Arquivos envolvidos

### 1. NOVO: `backend/services/content_planner.py`

Este é o arquivo novo que faz a extração de conceitos e planejamento de episódios.

```python
"""
FABOT Podcast Studio — content_planner.py

Extrai conceitos-chave do texto e planeja episódios com profundidade.
Cada conceito vira 1 episódio completo onde o LLM EXPANDE o assunto
com histórias, exemplos reais, erros comuns e cuidados.
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EpisodePlan:
    numero: int
    titulo: str
    conceito_principal: str
    subtopicos: list[str]
    contexto_original: str  # trecho do texto original sobre esse conceito
    resumo_episodio_anterior: str = ""


PLANNING_PROMPT = """Você é um planejador de podcast educacional.

Dado o texto abaixo, extraia os CONCEITOS-CHAVE e planeje episódios de podcast.

REGRAS:
1. Cada conceito principal deve virar 1 episódio separado
2. Conceitos relacionados podem ser agrupados (máximo 2 por episódio)
3. Mínimo de 2 episódios, máximo de 8 episódios
4. Para cada episódio, defina:
   - titulo: título atraente para o episódio
   - conceito_principal: o conceito central
   - subtopicos: lista de 4-6 subtópicos que devem ser cobertos
   - trecho_relevante: qual parte do texto original trata desse conceito

IMPORTANTE: Os subtópicos devem incluir:
- O que é (definição clara)
- Por que importa (contexto de negócio)
- Como funciona na prática (exemplo real de empresa)
- Erros comuns e armadilhas
- Dicas e cuidados
- Conexão com o próximo episódio (se houver)

Responda APENAS em JSON válido, sem markdown:
{
  "total_episodios": N,
  "episodios": [
    {
      "numero": 1,
      "titulo": "Título do Episódio",
      "conceito_principal": "nome do conceito",
      "subtopicos": ["subtópico 1", "subtópico 2", ...],
      "trecho_relevante": "parte do texto que fala desse conceito"
    }
  ]
}

TEXTO:
---
{texto}
---"""


async def planejar_episodios(provider, texto: str) -> list[EpisodePlan]:
    """
    Usa o LLM para extrair conceitos e planejar episódios.
    Retorna lista de EpisodePlan prontos para geração de roteiro.
    """
    logger.info("[ContentPlanner] Extraindo conceitos e planejando episódios...")

    prompt = PLANNING_PROMPT.format(texto=texto[:15000])  # limita input

    try:
        # Chama o LLM com prompt de planejamento
        response = await provider.call_llm(
            system_prompt="Você é um planejador de conteúdo educacional. Responda APENAS em JSON.",
            user_prompt=prompt,
            temperature=0.3,  # baixa temperatura para planejamento consistente
        )

        # Parse do JSON
        plan_data = _parse_planning_response(response)

        if not plan_data or not plan_data.get("episodios"):
            logger.warning("[ContentPlanner] Planejamento falhou, usando fallback")
            return _fallback_planning(texto)

        episodios = []
        for ep in plan_data["episodios"]:
            episodios.append(EpisodePlan(
                numero=ep.get("numero", len(episodios) + 1),
                titulo=ep.get("titulo", f"Episódio {len(episodios) + 1}"),
                conceito_principal=ep.get("conceito_principal", ""),
                subtopicos=ep.get("subtopicos", []),
                contexto_original=ep.get("trecho_relevante", ""),
            ))

        logger.info(
            f"[ContentPlanner] Planejados {len(episodios)} episódios: "
            f"{[e.titulo for e in episodios]}"
        )
        return episodios

    except Exception as e:
        logger.error(f"[ContentPlanner] Erro no planejamento: {e}")
        return _fallback_planning(texto)


def _parse_planning_response(response: str) -> dict | None:
    """Extrai JSON da resposta do LLM."""
    if not response:
        return None

    # Remove markdown code blocks
    clean = re.sub(r'```json\s*', '', response)
    clean = re.sub(r'```\s*', '', clean)
    clean = clean.strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Tenta encontrar JSON dentro do texto
        match = re.search(r'\{[\s\S]*\}', clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def _fallback_planning(texto: str) -> list[EpisodePlan]:
    """
    Fallback quando o LLM não consegue planejar.
    Divide o texto em seções e cria planos básicos.
    """
    from backend.services.text_splitter import dividir_texto

    secoes = dividir_texto(texto)

    if not secoes:
        return [EpisodePlan(
            numero=1,
            titulo="Episódio Único",
            conceito_principal="Conteúdo completo",
            subtopicos=["Introdução", "Conceitos principais", "Exemplos", "Conclusão"],
            contexto_original=texto[:5000],
        )]

    return [
        EpisodePlan(
            numero=i + 1,
            titulo=s.titulo,
            conceito_principal=s.titulo,
            subtopicos=["Introdução", "O que é", "Exemplos práticos", "Cuidados"],
            contexto_original=s.conteudo,
        )
        for i, s in enumerate(secoes)
    ]
```

### 2. MODIFICAR: `backend/workers/podcast_worker.py`

Na função `generate_script_only`, substituir a lógica de divisão por conceitos.

**MUDANÇA PRINCIPAL**: Em vez de `dividir_texto()` → usar `planejar_episodios()` primeiro.

```python
async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera roteiro com planejamento por conceitos."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        # PASSO 1 - Lendo texto
        job.status = "READING"
        job.progress = 2
        job.current_step = "📄 Lendo texto de entrada..."
        db.commit()

        from backend.services.llm import get_provider
        from backend.services.content_planner import planejar_episodios

        text = job.input_text or ""
        llm_mode = job.llm_mode

        # PASSO 2 - Conectando LLM
        job.progress = 5
        job.current_step = f"🤖 Conectando ao provedor LLM ({llm_mode})..."
        db.commit()

        provider = get_provider(str(llm_mode))

        # PASSO 3 - Planejando episódios (NOVO!)
        job.status = "PLANNING"
        job.progress = 8
        job.current_step = "🧠 Analisando conceitos-chave do texto..."
        db.commit()

        episodios_plan = await planejar_episodios(provider, text)
        total_episodes = len(episodios_plan)

        # PASSO 4 - Plano pronto
        job.progress = 12
        job.current_step = (
            f"📋 Plano definido: {total_episodes} episódio(s) — "
            f"{', '.join(ep.titulo for ep in episodios_plan[:3])}"
            f"{'...' if total_episodes > 3 else ''}"
        )
        db.commit()

        logger.info(
            f"[ScriptOnly] Plano: {total_episodes} episódios para job {job_id}"
        )

        # PASSO 5+ Gerando cada episódio
        job.status = "LLM_PROCESSING"
        all_scripts = []
        previous_summary = ""
        total_segments = 0

        for i, ep_plan in enumerate(episodios_plan):
            episode_num = i + 1

            # Progresso granular por episódio
            base_progress = 15
            episode_progress = int((episode_num / total_episodes) * 20)
            job.progress = base_progress + episode_progress
            job.current_step = (
                f"🧠 Gerando Ep.{episode_num}/{total_episodes}: "
                f"{ep_plan.titulo}..."
            )
            db.commit()

            # Config com planejamento de conceitos
            config = {
                "target_duration": job.target_duration or 10,
                "depth_level": job.depth_level or "deep",
                "podcast_type": job.podcast_type,
                "voice_host": job.voice_host,
                "voice_cohost": job.voice_cohost,
                "section_title": ep_plan.titulo,
                "episode_number": episode_num,
                "total_episodes": total_episodes,
                "previous_summary": previous_summary,
                # NOVOS campos para profundidade
                "conceito_principal": ep_plan.conceito_principal,
                "subtopicos": ep_plan.subtopicos,
                "contexto_original": ep_plan.contexto_original,
            }

            # Gerar roteiro para este episódio
            script = await provider.generate_script(ep_plan.contexto_original, config)

            # Atualizar progresso com resultado
            ep_segments = (
                len(script.get("segments", [])) if isinstance(script, dict) else 0
            )
            total_segments += ep_segments
            job.progress = base_progress + episode_progress + 2
            job.current_step = (
                f"✅ Ep.{episode_num}/{total_episodes} gerado "
                f"({ep_segments} falas): {ep_plan.titulo}"
            )
            db.commit()

            # Extrair resumo para contexto do próximo episódio
            if isinstance(script, dict):
                segments = script.get("segments", [])
                last_texts = [
                    s.get("text", "") for s in segments[-3:] if s.get("text")
                ]
                previous_summary = " ".join(last_texts)[:500]

                script["episode_number"] = episode_num
                script["total_episodes"] = total_episodes
                script["section_title"] = ep_plan.titulo
                script["conceito_principal"] = ep_plan.conceito_principal

            all_scripts.append(script)
            logger.info(
                f"Episódio {episode_num}/{total_episodes} gerado: {ep_plan.titulo} "
                f"({ep_segments} falas)"
            )

        # PASSO - Parseando e validando
        job.progress = 36
        job.current_step = (
            f"📝 Combinando {total_episodes} roteiro(s) "
            f"({total_segments} falas total)..."
        )
        db.commit()

        # Salvar scripts
        if len(all_scripts) == 1:
            job.script_json = json.dumps(all_scripts[0], ensure_ascii=False)
        else:
            job.script_json = json.dumps(all_scripts, ensure_ascii=False)

        # PASSO - Salvando
        job.progress = 39
        job.current_step = "💾 Salvando roteiro no banco de dados..."
        db.commit()

        # PASSO - Concluído
        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = (
            f"✅ Roteiro pronto ({total_episodes} episódios, "
            f"{total_segments} falas)"
        )
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "total_episodes": total_episodes,
            "total_segments": total_segments,
            "episodes": [
                {
                    "episode": ep.numero,
                    "title": ep.titulo,
                    "conceito": ep.conceito_principal,
                }
                for ep in episodios_plan
            ],
        }

    except Exception as e:
        logger.error(f"Job {job_id} falhou ao gerar roteiro: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_step = f"❌ Erro: {str(e)[:100]}"
                db.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status failed: {db_err}")
        return {"success": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()
```

### 3. MODIFICAR: `backend/services/llm.py`

Adicionar o método `call_llm` nos providers para o content_planner usar.
Também modificar `generate_script` para usar os novos campos de config
(conceito_principal, subtopicos).

**NO PROVIDER (ex: GeminiProvider ou GenericProvider):**

Adicionar este método se não existir:

```python
async def call_llm(
    self, system_prompt: str, user_prompt: str, temperature: float = 0.7
) -> str:
    """
    Chamada genérica ao LLM. Retorna texto puro.
    Usado pelo content_planner para planejamento.
    """
    # Usar a mesma infraestrutura do generate_script mas retornar texto puro
    # A implementação depende do provider (Gemini, Groq, etc.)
    raise NotImplementedError("Implementar call_llm no provider")
```

**NO TEMPLATE DO PROMPT (script_template_v7.py):**

Adicionar suporte aos novos campos no USER_PROMPT_TEMPLATE:

```python
# Adicionar ao final do USER_PROMPT_TEMPLATE, antes do texto:
{% if conceito_principal %}

CONCEITO PRINCIPAL DESTE EPISÓDIO: {{ conceito_principal }}

SUBTÓPICOS OBRIGATÓRIOS (deve cobrir TODOS):
{% for sub in subtopicos %}
  - {{ sub }}
{% endfor %}

INSTRUÇÃO DE PROFUNDIDADE:
Você NÃO está resumindo o texto. Você está ENSINANDO o conceito.
Para cada subtópico, você DEVE:
1. Explicar O QUE É com analogia de negócio
2. Dar EXEMPLO REAL de empresa (Amazon, Netflix, Uber, iFood, Nubank, etc.)
3. Contar o ERRO MAIS COMUM que profissionais cometem
4. Dar DICA PRÁTICA que o ouvinte pode aplicar imediatamente
5. Fazer TRANSIÇÃO NATURAL para o próximo subtópico

NÃO use exemplos de receita de bolo, gaveta ou lista de compras.
Use SEMPRE contexto empresarial e profissional.
{% endif %}
```

### 4. MODIFICAR: `frontend/src/components/RightPanel.jsx` (ProgressTab)

Adicionar o status "PLANNING" à lista de steps:

```javascript
const steps = [
  { status: 'READING', label: 'Lendo texto de entrada' },
  { status: 'PLANNING', label: 'Analisando conceitos e planejando episódios' },
  { status: 'LLM_PROCESSING', label: 'Gerando roteiros com IA' },
  { status: 'SCRIPT_DONE', label: 'Roteiro pronto para revisão' },
  { status: 'TTS_PROCESSING', label: 'Sintetizando áudio com Edge TTS' },
  { status: 'POST_PRODUCTION', label: 'Finalizando e mixando áudio' },
];
```

Também no `InputPanel.jsx`, adicionar 'PLANNING' à lista de status ativos:

```javascript
const activeStatuses = ['READING', 'PLANNING', 'LLM_PROCESSING', 'TTS_PROCESSING', 'PENDING'];
```

E no `ProgressOverlay.jsx`, adicionar 'PLANNING' onde necessário:

```javascript
visible={showProgress || (currentJob && ['READING', 'PLANNING', 'LLM_PROCESSING', 'TTS_PROCESSING'].includes(currentJob.status))}
```

### 5. NÃO MODIFICAR

- `text_splitter.py` — continua existindo como fallback
- `fabot_tts.py` — não muda nada na síntese de voz
- `models.py` — não precisa de novos campos no banco
- CSS — não muda nada visual

## Fluxo Final

```
Texto do usuário (qualquer tamanho, com ou sem ##)
       ↓
content_planner.py → LLM extrai conceitos → plano de episódios
       ↓
podcast_worker.py → Para cada episódio do plano:
  → LLM gera roteiro EXPANDIDO com profundidade
  → Mínimo 50 falas por episódio
  → Histórias, exemplos reais, erros comuns
       ↓
Resultado: N episódios profundos e didáticos
```

## Resumo das mudanças

| Arquivo | Ação | Risco |
|---|---|---|
| `backend/services/content_planner.py` | CRIAR (novo) | Nenhum — arquivo novo |
| `backend/workers/podcast_worker.py` | MODIFICAR `generate_script_only()` | Baixo — substitui lógica de divisão |
| `backend/services/llm.py` | ADICIONAR método `call_llm` | Baixo — método novo |
| `backend/prompts/script_template_v7.py` | ADICIONAR campos no template | Nenhum — campos opcionais com `{% if %}` |
| `frontend/src/components/RightPanel.jsx` | ADICIONAR status 'PLANNING' | Nenhum — só adiciona 1 step |
| `frontend/src/components/InputPanel.jsx` | ADICIONAR 'PLANNING' em activeStatuses | Nenhum |
| `frontend/src/App.jsx` | ADICIONAR 'PLANNING' no ProgressOverlay | Nenhum |

## Teste esperado

Com o texto sobre visualização de dados em ML:
- **Antes**: 1 episódio raso com ~50 falas resumindo tudo
- **Depois**: 4 episódios profundos:
  1. "Histograma: Enxergando a Forma dos Dados" (~50 falas)
  2. "Box Plot: Resumindo e Comparando Distribuições" (~50 falas)
  3. "Scatter Plot: Relações Entre Variáveis" (~50 falas)
  4. "Heatmap: O Raio-X do Dataset" (~50 falas)

Cada episódio com histórias, exemplos de empresas reais, erros comuns e cuidados.