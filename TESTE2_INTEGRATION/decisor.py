"""
decisor.py — Calcula score de complexidade e quantidade de episódios.

ZERO chamadas a LLM. Pura matemática determinística.

Por que não deixar o LLM decidir o número de episódios:
  - O LLM dá números baseados em padrão estatístico de treinamento
  - Não sabe o tamanho real do documento
  - Não sabe quantos conceitos foram extraídos
  - Não sabe a capacidade real de áudio por episódio
  - O resultado seria inconsistente entre chamadas

A fórmula usa:
  - Complexidade de cada conceito (calculada a partir dos atributos)
  - Número de dependências (conceitos mais dependentes precisam de mais contexto)
  - Capacidade de áudio: ~40 segmentos × ~25 palavras = 1000 palavras por episódio
  - Mínimo de segmentos por conceito dependendo da complexidade
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from models import Complexidade, Conceito

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONSTANTES DE CALIBRAÇÃO
# ═══════════════════════════════════════════════════════════════

# Segmentos mínimos por nível de complexidade
SEGMENTOS_MIN_POR_COMPLEXIDADE: dict[Complexidade, int] = {
    Complexidade.BAIXA:   8,   # Definição + 1 exemplo + fixação
    Complexidade.MEDIA:  12,   # Contexto + definição + 2 exemplos + cuidado + fixação
    Complexidade.ALTA:   18,   # Tudo acima + código descrito + analogia + 2 fixações
    Complexidade.CRITICA: 22,  # Tudo acima + transição longa para o próximo
}

# Bonus de segmentos por característica do conceito
BONUS_CODIGO = 4       # Explicar código sem o ouvinte ver precisa de mais tempo
BONUS_FORMULA = 3      # Fórmulas matemáticas precisam ser descritas verbalmente
BONUS_SUBCONCEPT = 2   # Cada subconceito adiciona complexidade
BONUS_DEPENDENCIA = 1  # Cada dependência adiciona contexto necessário

# Capacidade de um episódio
SEGMENTOS_POR_EPISODIO = 40   # Mínimo do script_template_v7 é 40
PALAVRAS_POR_SEGMENTO = 22    # Média real de palavras por fala (máx é 40)
PALAVRAS_POR_EPISODIO = SEGMENTOS_POR_EPISODIO * PALAVRAS_POR_SEGMENTO  # = 880

# Limites globais
MAX_CONCEITOS_POR_EPISODIO = 3   # Foco: não sobrecarregar o ouvinte
MIN_EPISODIOS = 1
MAX_EPISODIOS = 30


# ═══════════════════════════════════════════════════════════════
# RESULTADO
# ═══════════════════════════════════════════════════════════════

@dataclass
class ResultadoDecisao:
    """Resultado completo do cálculo de episódios."""
    total_episodios: int
    total_segmentos_necessarios: int
    media_segmentos_por_episodio: float
    media_conceitos_por_episodio: float
    conceitos_rankeados: list[Conceito]          # Ordenados por score_complexidade desc
    detalhes_por_conceito: list[dict]            # Para debug e rastreabilidade


# ═══════════════════════════════════════════════════════════════
# CÁLCULO
# ═══════════════════════════════════════════════════════════════

def _calcular_score_conceito(conceito: Conceito) -> float:
    """
    Calcula o score de complexidade de um conceito.

    O score representa o "peso" do conceito em termos de tempo de áudio necessário.
    É proporcional ao número de segmentos que precisaremos gerar.

    Fórmula:
        score = segmentos_base
              + bonus_codigo
              + bonus_formula
              + bonus_subconcepts
              + bonus_dependencias
              + bonus_paragrafos_extras
    """
    # Base: mínimo de segmentos para este nível de complexidade
    score = float(SEGMENTOS_MIN_POR_COMPLEXIDADE[conceito.complexidade])

    # Bônus por características especiais
    if conceito.tem_codigo:
        score += BONUS_CODIGO
    if conceito.tem_formula:
        score += BONUS_FORMULA
    score += conceito.subconcepts_count * BONUS_SUBCONCEPT
    score += len(conceito.dependencias) * BONUS_DEPENDENCIA

    # Bônus por quantidade de parágrafos no texto original
    # (mais parágrafos = mais conteúdo a cobrir)
    paragrafos_extra = max(0, conceito.paragrafos_estimados - 2)
    score += paragrafos_extra * 0.8

    return round(score, 1)


def calcular_episodios(conceitos: list[Conceito]) -> ResultadoDecisao:
    """
    Calcula o número de episódios necessários para cobrir todos os conceitos.

    Algoritmo:
    1. Calcula score de complexidade de cada conceito
    2. Calcula segmentos necessários de cada conceito
    3. Soma total de segmentos
    4. Divide pelo número de segmentos por episódio
    5. Aplica limites e ajusta para múltiplo de MAX_CONCEITOS_POR_EPISODIO

    O número final é o mínimo de episódios necessários para cobrir
    todos os conceitos com a profundidade adequada.

    Args:
        conceitos: Lista de Conceito produzida por concept_extractor.py

    Returns:
        ResultadoDecisao com total_episodios e metadados de cálculo.
    """
    if not conceitos:
        logger.warning("[Decisor] Lista de conceitos vazia.")
        return ResultadoDecisao(
            total_episodios=1,
            total_segmentos_necessarios=0,
            media_segmentos_por_episodio=0.0,
            media_conceitos_por_episodio=0.0,
            conceitos_rankeados=[],
            detalhes_por_conceito=[],
        )

    detalhes: list[dict] = []
    total_segmentos = 0

    for conceito in conceitos:
        score = _calcular_score_conceito(conceito)
        segmentos = int(math.ceil(score))

        # Atualiza o conceito com os valores calculados
        conceito.score_complexidade = score
        conceito.segmentos_necessarios = segmentos

        total_segmentos += segmentos

        detalhes.append({
            "id": conceito.id,
            "nome": conceito.nome,
            "complexidade": conceito.complexidade.value,
            "score": score,
            "segmentos": segmentos,
            "tem_codigo": conceito.tem_codigo,
            "tem_formula": conceito.tem_formula,
            "dependencias": len(conceito.dependencias),
        })

    # Cálculo base de episódios
    episodios_base = total_segmentos / SEGMENTOS_POR_EPISODIO

    # Ajuste pelo limite de MAX_CONCEITOS_POR_EPISODIO:
    # Se tivermos 10 conceitos e a fórmula diz 2 episódios,
    # precisamos de pelo menos ceil(10/3) = 4 episódios para não sobrecarregar.
    episodios_min_por_foco = math.ceil(len(conceitos) / MAX_CONCEITOS_POR_EPISODIO)

    # Pega o maior dos dois
    episodios_calculado = max(episodios_base, episodios_min_por_foco)

    # Arredonda para cima e aplica limites globais
    total_episodios = int(math.ceil(episodios_calculado))
    total_episodios = max(MIN_EPISODIOS, min(MAX_EPISODIOS, total_episodios))

    # Métricas para rastreabilidade
    media_segs = total_segmentos / total_episodios if total_episodios else 0
    media_concs = len(conceitos) / total_episodios if total_episodios else 0

    # Ordena conceitos por score desc (mais complexos primeiro, para grouper)
    conceitos_rankeados = sorted(conceitos, key=lambda c: c.score_complexidade, reverse=True)

    logger.info(
        f"[Decisor] ✅ Cálculo concluído:\n"
        f"  Conceitos: {len(conceitos)}\n"
        f"  Segmentos necessários: {total_segmentos}\n"
        f"  Episódios por segmentos: {episodios_base:.1f}\n"
        f"  Episódios por foco (max {MAX_CONCEITOS_POR_EPISODIO}/ep): {episodios_min_por_foco}\n"
        f"  Total FINAL: {total_episodios} episódios"
    )

    return ResultadoDecisao(
        total_episodios=total_episodios,
        total_segmentos_necessarios=total_segmentos,
        media_segmentos_por_episodio=round(media_segs, 1),
        media_conceitos_por_episodio=round(media_concs, 1),
        conceitos_rankeados=conceitos_rankeados,
        detalhes_por_conceito=sorted(detalhes, key=lambda d: d["score"], reverse=True),
    )
