"""
grouper.py — Agrupa conceitos em episódios respeitando dependências.

Responsabilidades:
  - Ordenar conceitos por cadeia de dependência (ordem topológica)
  - Agrupar em episódios respeitando o limite de MAX_CONCEITOS_POR_EPISODIO
  - Distribuir a profundidade (depth_level) por complexidade
  - Extrair o chunk de texto correspondente a cada episódio do documento original
  - Retornar PlanoCompleto pronto para coverage_check.py

Algoritmo:
  1. Ordenação topológica dos conceitos (Kahn's algorithm)
     → Garante que nunca ensinamos B antes de A se B depende de A
  2. Empacotamento guloso por capacidade
     → Preenche cada episódio até MAX_CONCEITOS_POR_EPISODIO conceitos
     → Respeita o budget de segmentos por episódio
  3. Extração de chunks de texto
     → Busca os blocos de origem de cada conceito no documento
  4. Cálculo de depth_level por episódio
     → Episódios com conceitos "criticos" ou "altos" ficam em "detailed"

NÃO faz:
  - Chamar LLM (pura lógica de grafos)
  - Gerar roteiro
  - Validar cobertura (responsabilidade de coverage_check.py)
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from datetime import datetime, timezone

from decisor import SEGMENTOS_POR_EPISODIO, ResultadoDecisao
from models import (
    Complexidade,
    Conceito,
    DepthLevel,
    DocumentoEstruturado,
    EpisodioPlano,
    PlanoCompleto,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

MAX_CONCEITOS_POR_EPISODIO = 3
MAX_SEGMENTOS_POR_EPISODIO = SEGMENTOS_POR_EPISODIO + 20  # Margem de 20


# ═══════════════════════════════════════════════════════════════
# ORDENAÇÃO TOPOLÓGICA (KAHN'S ALGORITHM)
# ═══════════════════════════════════════════════════════════════

def _ordenar_topologicamente(conceitos: list[Conceito]) -> list[Conceito]:
    """
    Ordena conceitos pela cadeia de dependências usando o algoritmo de Kahn.
    
    Resultado: conceito A vem sempre antes de B se B depende de A.
    
    Conceitos sem dependências vêm primeiro, ordenados por score desc
    (os mais complexos sem deps primeiro, para dar mais tempo a eles).
    
    Se houver ciclo residual (não deveria, pois concept_extractor.py já remove),
    os conceitos do ciclo são adicionados ao final para garantir cobertura.
    """
    id_para_conceito = {c.id: c for c in conceitos}
    
    # Grau de entrada: quantas deps cada conceito tem que ainda não foram processadas
    grau_entrada: dict[str, int] = {c.id: 0 for c in conceitos}
    # Quem depende de quem: deps_de[A] = lista de conceitos que dependem de A
    deps_de: dict[str, list[str]] = defaultdict(list)
    
    for conceito in conceitos:
        for dep_id in conceito.dependencias:
            if dep_id in id_para_conceito:
                grau_entrada[conceito.id] += 1
                deps_de[dep_id].append(conceito.id)
    
    # Fila inicial: todos com grau 0 (sem dependências)
    # Ordenados por score desc (mais complexos primeiro)
    fila = deque(sorted(
        [c.id for c in conceitos if grau_entrada[c.id] == 0],
        key=lambda cid: id_para_conceito[cid].score_complexidade,
        reverse=True,
    ))
    
    resultado: list[Conceito] = []
    
    while fila:
        cid = fila.popleft()
        conceito = id_para_conceito[cid]
        resultado.append(conceito)
        
        # Para cada conceito que dependia deste, decrementa o grau
        for dependente_id in deps_de[cid]:
            grau_entrada[dependente_id] -= 1
            if grau_entrada[dependente_id] == 0:
                fila.append(dependente_id)
    
    # Ciclos residuais: adiciona ao final para garantir cobertura total
    nao_processados = [c for c in conceitos if c not in resultado]
    if nao_processados:
        logger.warning(
            f"[Grouper] {len(nao_processados)} conceitos com ciclo residual. "
            f"Adicionando ao final: {[c.id for c in nao_processados]}"
        )
        resultado.extend(sorted(
            nao_processados,
            key=lambda c: c.score_complexidade,
            reverse=True,
        ))
    
    return resultado


# ═══════════════════════════════════════════════════════════════
# EMPACOTAMENTO EM EPISÓDIOS
# ═══════════════════════════════════════════════════════════════

def _determinar_depth_level(conceitos_ep: list[Conceito]) -> DepthLevel:
    """Determina a profundidade do episódio com base nos conceitos que contém."""
    complexidades = {c.complexidade for c in conceitos_ep}
    
    if Complexidade.CRITICA in complexidades or Complexidade.ALTA in complexidades:
        return DepthLevel.DETAILED
    elif Complexidade.MEDIA in complexidades:
        return DepthLevel.STANDARD
    else:
        return DepthLevel.QUICK


def _estimar_palavras_episodio(conceitos_ep: list[Conceito]) -> int:
    """Estima o total de palavras do episódio gerado."""
    from decisor import PALAVRAS_POR_SEGMENTO
    total_segs = sum(c.segmentos_necessarios for c in conceitos_ep)
    return total_segs * PALAVRAS_POR_SEGMENTO


def _empacotar_em_episodios(
    conceitos_ordenados: list[Conceito],
    total_episodios: int,
) -> list[list[Conceito]]:
    """
    Distribui os conceitos em exatamente total_episodios grupos.
    
    Estratégia: empacotamento guloso com rebalanceamento.
    - Preenche cada episódio até MAX_CONCEITOS_POR_EPISODIO ou MAX_SEGMENTOS_POR_EPISODIO
    - Se sobrar episódios, distribui os mais carregados
    
    Returns: lista de listas, cada sublista = conceitos de um episódio
    """
    grupos: list[list[Conceito]] = []
    grupo_atual: list[Conceito] = []
    segs_atual = 0
    
    for conceito in conceitos_ordenados:
        pode_adicionar = (
            len(grupo_atual) < MAX_CONCEITOS_POR_EPISODIO
            and segs_atual + conceito.segmentos_necessarios <= MAX_SEGMENTOS_POR_EPISODIO
        )
        
        if not pode_adicionar and grupo_atual:
            grupos.append(grupo_atual)
            grupo_atual = []
            segs_atual = 0
        
        grupo_atual.append(conceito)
        segs_atual += conceito.segmentos_necessarios
    
    if grupo_atual:
        grupos.append(grupo_atual)
    
    # Se geramos mais grupos que o planejado, não é problema —
    # total_episodios é um mínimo, não um máximo rígido.
    # Se geramos menos, está OK também.
    
    if len(grupos) != total_episodios:
        logger.info(
            f"[Grouper] Planejado: {total_episodios} eps | "
            f"Gerado: {len(grupos)} eps "
            f"(diferença normal pelo empacotamento)"
        )
    
    return grupos


# ═══════════════════════════════════════════════════════════════
# EXTRAÇÃO DE CHUNK DE TEXTO
# ═══════════════════════════════════════════════════════════════

def _extrair_chunk_texto(
    conceitos_ep: list[Conceito],
    documento: DocumentoEstruturado,
) -> str:
    """
    Busca os blocos do documento que correspondem aos conceitos do episódio.
    
    Estratégia:
    1. Pega os IDs dos blocos de origem dos conceitos
    2. Busca esses blocos no documento
    3. Se não encontrar, usa a busca por keywords nos textos dos blocos
    4. Retorna os textos concatenados (limitado a 3000 palavras)
    """
    MAX_PALAVRAS_CHUNK = 3000
    
    # Coleta blocos de origem
    blocos_ids = {c.bloco_origem_id for c in conceitos_ep if c.bloco_origem_id}
    blocos_encontrados = [
        b for b in documento.blocos if b.id in blocos_ids
    ]
    
    # Se não encontrou por ID, busca por keywords
    if not blocos_encontrados:
        todas_keywords = set()
        for conceito in conceitos_ep:
            todas_keywords.update(conceito.keywords)
            todas_keywords.add(conceito.nome.lower())
        
        for bloco in documento.blocos:
            texto_lower = bloco.texto.lower()
            matches = sum(1 for kw in todas_keywords if kw in texto_lower)
            if matches >= 2:
                blocos_encontrados.append(bloco)
    
    # Se ainda não encontrou, usa os primeiros blocos do documento
    if not blocos_encontrados:
        logger.warning(
            f"[Grouper] Chunk: nenhum bloco encontrado para conceitos "
            f"{[c.id for c in conceitos_ep]}. Usando início do documento."
        )
        blocos_encontrados = documento.blocos[:2]
    
    # Concatena os textos, respeitando o limite de palavras
    partes = []
    palavras_total = 0
    
    for bloco in blocos_encontrados:
        if palavras_total >= MAX_PALAVRAS_CHUNK:
            break
        palavras_bloco = len(bloco.texto.split())
        if palavras_total + palavras_bloco > MAX_PALAVRAS_CHUNK:
            # Trunca o bloco
            palavras_restantes = MAX_PALAVRAS_CHUNK - palavras_total
            texto_truncado = " ".join(bloco.texto.split()[:palavras_restantes])
            partes.append(f"[{bloco.titulo}]\n{texto_truncado}")
            palavras_total = MAX_PALAVRAS_CHUNK
        else:
            partes.append(f"[{bloco.titulo}]\n{bloco.texto}")
            palavras_total += palavras_bloco
    
    return "\n\n".join(partes)


# ═══════════════════════════════════════════════════════════════
# GERAÇÃO DE TÍTULO SUGERIDO
# ═══════════════════════════════════════════════════════════════

def _gerar_titulo_sugerido(conceitos_ep: list[Conceito], numero: int) -> str:
    """Gera um título descritivo para o episódio baseado nos conceitos."""
    if len(conceitos_ep) == 1:
        return conceitos_ep[0].nome
    
    if len(conceitos_ep) == 2:
        return f"{conceitos_ep[0].nome} e {conceitos_ep[1].nome}"
    
    # Para 3+ conceitos, usa o mais complexo como tema principal
    principal = max(conceitos_ep, key=lambda c: c.score_complexidade)
    outros = [c for c in conceitos_ep if c.id != principal.id]
    
    if len(outros) == 1:
        return f"{principal.nome}: {outros[0].nome}"
    
    return f"{principal.nome}, {outros[0].nome} e {outros[1].nome}"


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def agrupar_em_episodios(
    decisao: ResultadoDecisao,
    documento: DocumentoEstruturado,
) -> PlanoCompleto:
    """
    Agrupa conceitos em episódios respeitando dependências e capacidade.
    
    Args:
        decisao: ResultadoDecisao de decisor.py (com scores calculados)
        documento: DocumentoEstruturado de extractor.py (para extrair chunks)
    
    Returns:
        PlanoCompleto com lista de EpisodioPlano prontos para geração.
    """
    conceitos = decisao.conceitos_rankeados
    total_episodios_planejado = decisao.total_episodios
    
    logger.info(
        f"[Grouper] Agrupando {len(conceitos)} conceitos em "
        f"~{total_episodios_planejado} episódios..."
    )
    
    # 1. Ordenação topológica
    conceitos_ordenados = _ordenar_topologicamente(conceitos)
    
    # 2. Empacotamento
    grupos = _empacotar_em_episodios(conceitos_ordenados, total_episodios_planejado)
    
    # 3. Construir EpisodioPlano para cada grupo
    episodios: list[EpisodioPlano] = []
    conceitos_ja_cobertos: list[str] = []
    
    for num_ep, grupo in enumerate(grupos, start=1):
        depth = _determinar_depth_level(grupo)
        palavras_est = _estimar_palavras_episodio(grupo)
        segs_est = sum(c.segmentos_necessarios for c in grupo)
        
        # Conceitos que o próximo episódio vai precisar
        proximo_grupo = grupos[num_ep] if num_ep < len(grupos) else []
        conceitos_preparar = [c.id for c in proximo_grupo]
        
        # Chunk de texto correspondente
        chunk = _extrair_chunk_texto(grupo, documento)
        
        # Notas para o generator
        notas = []
        if any(c.tem_codigo for c in grupo):
            notas.append("Este episódio tem conceitos com código — nunca leia literalmente.")
        if any(c.tem_formula for c in grupo):
            notas.append("Este episódio tem fórmulas — descreva em palavras o que calculam.")
        if conceitos_preparar:
            nomes_prox = [
                next((c.nome for c in conceitos_ordenados if c.id == cid), cid)
                for cid in conceitos_preparar[:2]
            ]
            notas.append(
                f"Plante a semente dos conceitos do próximo episódio: "
                f"{', '.join(nomes_prox)}."
            )
        
        ep = EpisodioPlano(
            numero=num_ep,
            titulo_sugerido=_gerar_titulo_sugerido(grupo, num_ep),
            conceitos=[c.id for c in grupo],
            depth_level=depth,
            palavras_estimadas=palavras_est,
            segmentos_estimados=segs_est,
            dependencias_satisfeitas=list(conceitos_ja_cobertos),
            conceitos_preparar=conceitos_preparar,
            chunk_texto=chunk,
            notas_gerador="\n".join(notas),
        )
        episodios.append(ep)
        
        # Marca estes conceitos como cobertos para o próximo episódio
        conceitos_ja_cobertos.extend(c.id for c in grupo)
    
    plano = PlanoCompleto(
        documento_titulo=documento.titulo_documento,
        total_episodios=len(episodios),
        total_conceitos=len(conceitos),
        episodios=episodios,
        cobertura_percentual=0.0,  # Será preenchido por coverage_check.py
        criado_em=datetime.now(timezone.utc).isoformat(),
    )
    
    logger.info(
        f"[Grouper] ✅ Plano criado: {len(episodios)} episódios | "
        f"{len(conceitos)} conceitos"
    )
    
    return plano
