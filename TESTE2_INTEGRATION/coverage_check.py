"""
coverage_check.py — Valida cobertura 100% do conteúdo antes de gerar roteiros.

Regras que DEVEM passar (pipeline para se a qualquer falhar):
  1. Todo conceito está em exatamente 1 episódio (sem lacuna, sem duplicata)
  2. Nenhum episódio está vazio
  3. A cadeia de dependências é respeitada (B não aparece antes de A se B depende de A)
  4. Nenhum episódio tem mais de MAX_CONCEITOS_POR_EPISODIO conceitos
  5. O chunk_texto de cada episódio não está vazio
  6. O total de segmentos estimados é suficiente (pelo menos 20 por episódio)

Se alguma regra falhar, retorna o problema detalhado para que o pipeline possa
ajustar o plano (não para com erro genérico — explica o que está errado).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from models import Conceito, EpisodioPlano, PlanoCompleto

logger = logging.getLogger(__name__)

MAX_CONCEITOS_POR_EPISODIO = 3
MIN_SEGMENTOS_POR_EPISODIO = 20
MIN_PALAVRAS_CHUNK = 50


# ═══════════════════════════════════════════════════════════════
# RESULTADO
# ═══════════════════════════════════════════════════════════════

@dataclass
class ResultadoCobertura:
    valido: bool
    cobertura_percentual: float
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# VERIFICAÇÕES INDIVIDUAIS
# ═══════════════════════════════════════════════════════════════

def _verificar_sem_lacuna(
    conceitos: list[Conceito],
    episodios: list[EpisodioPlano],
) -> list[str]:
    """Verifica que todo conceito está em pelo menos 1 episódio."""
    ids_conceitos = {c.id for c in conceitos}
    ids_alocados = set()
    for ep in episodios:
        ids_alocados.update(ep.conceitos)

    faltando = ids_conceitos - ids_alocados
    if faltando:
        nomes = sorted(faltando)
        return [
            f"LACUNA: {len(faltando)} conceito(s) sem episódio alocado: "
            f"{', '.join(nomes)}"
        ]
    return []


def _verificar_sem_duplicata(episodios: list[EpisodioPlano]) -> list[str]:
    """Verifica que nenhum conceito aparece em mais de 1 episódio."""
    contagem: dict[str, list[int]] = {}
    for ep in episodios:
        for cid in ep.conceitos:
            contagem.setdefault(cid, []).append(ep.numero)

    duplicatas = {cid: eps for cid, eps in contagem.items() if len(eps) > 1}
    if duplicatas:
        detalhes = [f"{cid} (eps {eps})" for cid, eps in duplicatas.items()]
        return [
            f"DUPLICATA: {len(duplicatas)} conceito(s) aparecem em múltiplos episódios: "
            f"{', '.join(detalhes)}"
        ]
    return []


def _verificar_episodios_vazios(episodios: list[EpisodioPlano]) -> list[str]:
    """Verifica que nenhum episódio está vazio."""
    vazios = [ep.numero for ep in episodios if not ep.conceitos]
    if vazios:
        return [f"EPISÓDIO VAZIO: eps {vazios} não têm conceitos."]
    return []


def _verificar_ordem_dependencias(
    conceitos: list[Conceito],
    episodios: list[EpisodioPlano],
) -> list[str]:
    """
    Verifica que B nunca aparece antes de A se B depende de A.
    
    Constrói mapa: conceito_id → número do episódio onde aparece.
    Para cada conceito, verifica se todos os seus deps aparecem em episódios anteriores.
    """
    id_para_ep: dict[str, int] = {}
    for ep in episodios:
        for cid in ep.conceitos:
            id_para_ep[cid] = ep.numero

    erros = []
    id_para_conceito = {c.id: c for c in conceitos}

    for conceito in conceitos:
        ep_conceito = id_para_ep.get(conceito.id)
        if ep_conceito is None:
            continue  # Já detectado em sem_lacuna

        for dep_id in conceito.dependencias:
            ep_dep = id_para_ep.get(dep_id)
            if ep_dep is None:
                erros.append(
                    f"DEPENDÊNCIA AUSENTE: '{conceito.id}' depende de "
                    f"'{dep_id}' que não está alocado em nenhum episódio."
                )
            elif ep_dep >= ep_conceito:
                dep_nome = id_para_conceito.get(dep_id, type("", (), {"nome": dep_id})()).nome
                erros.append(
                    f"ORDEM INCORRETA: '{conceito.nome}' (ep {ep_conceito}) "
                    f"depende de '{dep_nome}' (ep {ep_dep}), "
                    f"mas dep deve vir ANTES."
                )

    return erros


def _verificar_limite_conceitos(episodios: list[EpisodioPlano]) -> list[str]:
    """Verifica que nenhum episódio tem mais de MAX_CONCEITOS_POR_EPISODIO."""
    sobrecarga = [
        ep.numero
        for ep in episodios
        if len(ep.conceitos) > MAX_CONCEITOS_POR_EPISODIO
    ]
    if sobrecarga:
        return [
            f"SOBRECARGA: eps {sobrecarga} têm mais de "
            f"{MAX_CONCEITOS_POR_EPISODIO} conceitos. "
            f"Ouvinte não consegue absorver."
        ]
    return []


def _verificar_chunks(episodios: list[EpisodioPlano]) -> list[str]:
    """Verifica que todo episódio tem chunk de texto para referência do gerador."""
    sem_chunk = [
        ep.numero
        for ep in episodios
        if not ep.chunk_texto or len(ep.chunk_texto.split()) < MIN_PALAVRAS_CHUNK
    ]
    if sem_chunk:
        return [
            f"SEM CHUNK: eps {sem_chunk} não têm texto de referência "
            f"(mínimo {MIN_PALAVRAS_CHUNK} palavras). "
            f"O gerador não saberá o que ensinar."
        ]
    return []


def _verificar_segmentos_minimos(episodios: list[EpisodioPlano]) -> list[str]:
    """Verifica que a estimativa de segmentos é suficiente."""
    poucos_segs = [
        (ep.numero, ep.segmentos_estimados)
        for ep in episodios
        if ep.segmentos_estimados < MIN_SEGMENTOS_POR_EPISODIO
    ]
    if poucos_segs:
        detalhes = [f"ep {n}: {s} segs" for n, s in poucos_segs]
        return [
            f"SEGMENTOS INSUFICIENTES: {', '.join(detalhes)}. "
            f"Mínimo é {MIN_SEGMENTOS_POR_EPISODIO} segmentos por episódio. "
            f"Isso vai gerar episódio raso."
        ]
    return []


# ═══════════════════════════════════════════════════════════════
# CÁLCULO DE COBERTURA
# ═══════════════════════════════════════════════════════════════

def _calcular_cobertura(
    conceitos: list[Conceito],
    episodios: list[EpisodioPlano],
) -> float:
    """
    Calcula percentual de cobertura ponderado pelo score de complexidade.
    
    Um conceito "critico" com score 22 vale mais que um "baixo" com score 8.
    Isso reflete a importância real do conteúdo.
    """
    if not conceitos:
        return 0.0

    ids_alocados = set()
    for ep in episodios:
        ids_alocados.update(ep.conceitos)

    score_total = sum(c.score_complexidade for c in conceitos)
    if score_total == 0:
        return 100.0 if all(c.id in ids_alocados for c in conceitos) else 0.0

    score_coberto = sum(
        c.score_complexidade
        for c in conceitos
        if c.id in ids_alocados
    )

    return round((score_coberto / score_total) * 100, 2)


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def verificar_cobertura(
    conceitos: list[Conceito],
    plano: PlanoCompleto,
) -> ResultadoCobertura:
    """
    Executa todas as verificações de cobertura no plano.
    
    Se retornar valido=False, o pipeline NÃO deve prosseguir para geração.
    Os erros indicam exatamente o que está errado para diagnóstico.
    
    Args:
        conceitos: Lista de Conceito de concept_extractor.py
        plano: PlanoCompleto de grouper.py (ainda não validado)
    
    Returns:
        ResultadoCobertura com valido=True apenas se TODAS as regras passarem.
    """
    logger.info(
        f"[Coverage] Verificando cobertura: "
        f"{len(conceitos)} conceitos | {len(plano.episodios)} episódios"
    )

    erros: list[str] = []
    avisos: list[str] = []

    # Executa todas as verificações
    erros += _verificar_sem_lacuna(conceitos, plano.episodios)
    erros += _verificar_sem_duplicata(plano.episodios)
    erros += _verificar_episodios_vazios(plano.episodios)
    erros += _verificar_ordem_dependencias(conceitos, plano.episodios)
    erros += _verificar_limite_conceitos(plano.episodios)
    erros += _verificar_chunks(plano.episodios)
    avisos += _verificar_segmentos_minimos(plano.episodios)

    # Calcula cobertura ponderada
    cobertura = _calcular_cobertura(conceitos, plano.episodios)

    # Atualiza o plano com a cobertura calculada
    plano.cobertura_percentual = cobertura

    # Cobertura abaixo de 100% é erro crítico
    if cobertura < 100.0:
        erros.append(
            f"COBERTURA INCOMPLETA: {cobertura:.1f}% do conteúdo está coberto. "
            f"Precisa ser 100%."
        )

    valido = len(erros) == 0

    if valido:
        logger.info(
            f"[Coverage] ✅ Cobertura OK: {cobertura:.1f}% | "
            f"{len(avisos)} avisos"
        )
    else:
        logger.error(
            f"[Coverage] ❌ {len(erros)} erro(s) encontrado(s):\n"
            + "\n".join(f"  • {e}" for e in erros)
        )

    if avisos:
        logger.warning(
            f"[Coverage] ⚠️ {len(avisos)} aviso(s):\n"
            + "\n".join(f"  • {a}" for a in avisos)
        )

    return ResultadoCobertura(
        valido=valido,
        cobertura_percentual=cobertura,
        erros=erros,
        avisos=avisos,
    )
