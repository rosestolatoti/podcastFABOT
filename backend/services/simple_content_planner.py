"""
FABOT Podcast Studio — content_planner.py

Responsabilidade:
  Recebe o texto do usuário e usa o LLM para identificar conceitos-chave,
  decidir quantos episódios gerar e planejar o título/foco de cada um.

Filosofia:
  O texto do usuário é o MAPA (aponta quais conceitos ensinar).
  O LLM é o GUIA (expande cada conceito com profundidade).
  O texto NÃO é o conteúdo — é a PAUTA.

Fluxo:
  1. Envia texto para o LLM com prompt de planejamento
  2. LLM retorna lista de episódios com título, conceitos e foco
  3. Cada episódio é gerado individualmente com o template v7
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EpisodePlan:
    """Plano de um episódio individual."""

    episode_number: int
    title: str
    main_concept: str
    key_topics: list[str] = field(default_factory=list)
    focus_prompt: str = ""  # instrução extra para o LLM ao gerar este episódio
    estimated_minutes: int = 10


@dataclass
class ContentPlan:
    """Plano completo de todos os episódios."""

    total_episodes: int
    episodes: list[EpisodePlan] = field(default_factory=list)
    original_text: str = ""
    estimated_total_minutes: int = 0


PLANNING_SYSTEM_PROMPT = """Você é um planejador de conteúdo educacional para podcast.

Sua tarefa: analisar o texto fornecido e criar um PLANO DE EPISÓDIOS.

REGRAS DE DECISÃO — QUANTOS EPISÓDIOS:
- Identifique os CONCEITOS-CHAVE no texto (não parágrafos, CONCEITOS)
- Cada conceito que precisa de explicação profunda = 1 episódio
- Conceitos relacionados podem ser agrupados (máximo 2-3 por episódio)
- Mínimo: 1 episódio
- Máximo: 10 episódios
- Se o texto tem apenas 1 conceito simples → 1 episódio
- Se o texto tem 3-5 conceitos complexos → 3-5 episódios
- Se o texto tem 10+ conceitos → agrupar em até 10 episódios

REGRAS PARA TÍTULOS:
- Cada título deve ser curto, cativante, estilo podcast
- Use metáforas do cotidiano ou negócios
- Exemplos bons: "Derivada: O Sensor de Direção do seu Modelo"
- Exemplos ruins: "Capítulo 3: Derivadas" (muito acadêmico)

REGRAS PARA focus_prompt:
- É a instrução que será dada ao LLM ao gerar o episódio
- Deve dizer QUAIS ASPECTOS do conceito aprofundar
- Deve sugerir tipos de analogias (negócios, cotidiano, tecnologia)
- Deve indicar armadilhas/erros comuns para mencionar

RESPONDA APENAS em JSON válido, sem markdown, sem comentários:
{
  "total_episodes": <número>,
  "episodes": [
    {
      "episode_number": 1,
      "title": "<título cativante>",
      "main_concept": "<conceito principal em 1 frase>",
      "key_topics": ["tópico1", "tópico2", "tópico3"],
      "focus_prompt": "<instrução detalhada para o LLM expandir este conceito>",
      "estimated_minutes": 10
    }
  ]
}"""

PLANNING_USER_PROMPT = """Analise este texto e crie o plano de episódios:

---TEXTO---
{text}
---FIM---

Lembre-se:
- Cada conceito complexo merece seu próprio episódio
- O podcast é para LEIGOS — precisa de profundidade e analogias
- Não resuma o texto — identifique os CONCEITOS que precisam ser EXPANDIDOS
- Cada episódio terá ~10 minutos (50+ falas no podcast)"""


async def create_content_plan(text: str, provider) -> ContentPlan:
    """
    Usa o LLM para analisar o texto e criar um plano de episódios.

    Args:
        text: texto original do usuário
        provider: instância do provedor LLM (Gemini, GLM, etc.)

    Returns:
        ContentPlan com a lista de episódios planejados
    """
    logger.info("[ContentPlanner] Analisando texto para planejamento...")

    # Enviar para o LLM usando raw_completion
    plan_data = await provider.raw_completion(
        system_prompt=PLANNING_SYSTEM_PROMPT,
        user_prompt=PLANNING_USER_PROMPT.format(text=text[:15000]),  # limitar input
    )

    # Parsear resposta
    plan = _parse_plan_response(plan_data, text)

    logger.info(
        f"[ContentPlanner] Plano criado: {plan.total_episodes} episódios, "
        f"~{plan.estimated_total_minutes} min total"
    )

    return plan


def _parse_plan_response(response_text: str, original_text: str) -> ContentPlan:
    """Parseia a resposta JSON do LLM em ContentPlan."""

    # Limpar response
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Tentar extrair JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Tentar encontrar JSON dentro do texto
        import re

        json_match = re.search(r"\{[\s\S]*\}", cleaned)
        if json_match:
            try:
                data = json.loads(json_match.group())
            except json.JSONDecodeError:
                logger.error("[ContentPlanner] Falha ao parsear JSON do plano")
                return _fallback_plan(original_text)
        else:
            logger.error("[ContentPlanner] Nenhum JSON encontrado na resposta")
            return _fallback_plan(original_text)

    # Validar estrutura
    if "episodes" not in data or not data["episodes"]:
        logger.warning("[ContentPlanner] Resposta sem episódios, usando fallback")
        return _fallback_plan(original_text)

    episodes = []
    for ep_data in data["episodes"]:
        episodes.append(
            EpisodePlan(
                episode_number=ep_data.get("episode_number", len(episodes) + 1),
                title=ep_data.get("title", f"Episódio {len(episodes) + 1}"),
                main_concept=ep_data.get("main_concept", ""),
                key_topics=ep_data.get("key_topics", []),
                focus_prompt=ep_data.get("focus_prompt", ""),
                estimated_minutes=ep_data.get("estimated_minutes", 10),
            )
        )

    total_minutes = sum(ep.estimated_minutes for ep in episodes)

    return ContentPlan(
        total_episodes=len(episodes),
        episodes=episodes,
        original_text=original_text,
        estimated_total_minutes=total_minutes,
    )


def _fallback_plan(text: str) -> ContentPlan:
    """Plano de fallback: 1 episódio com todo o texto."""
    logger.warning("[ContentPlanner] Usando plano de fallback (1 episódio)")
    return ContentPlan(
        total_episodes=1,
        episodes=[
            EpisodePlan(
                episode_number=1,
                title="Episódio Único",
                main_concept="Conteúdo completo",
                key_topics=[],
                focus_prompt="Explore o conteúdo com profundidade máxima. "
                "Use analogias de negócios e exemplos do cotidiano. "
                "Explique cada conceito como se fosse para alguém que nunca viu o tema.",
                estimated_minutes=10,
            )
        ],
        original_text=text,
        estimated_total_minutes=10,
    )


def format_plan_report(plan: ContentPlan) -> str:
    """Gera relatório legível do plano para logs."""
    lines = [f"{'=' * 65}"]
    lines.append(f"PLANO DE CONTEÚDO — {plan.total_episodes} episódios")
    lines.append(f"{'=' * 65}")

    for ep in plan.episodes:
        topics = ", ".join(ep.key_topics[:4]) if ep.key_topics else "—"
        lines.append(
            f"  Ep.{ep.episode_number:02d} | {ep.title[:45]:45} | "
            f"~{ep.estimated_minutes} min | {topics}"
        )

    lines.append(f"{'─' * 65}")
    lines.append(
        f"  TOTAL: {plan.total_episodes} episódios | "
        f"~{plan.estimated_total_minutes} min de podcast"
    )
    lines.append(f"{'=' * 65}")
    return "\n".join(lines)
