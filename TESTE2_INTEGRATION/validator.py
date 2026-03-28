"""
validator.py — Valida roteiros gerados com critérios objetivos.

Critérios de validação (em ordem de severidade):

ERROS (bloqueiam o uso do episódio):
  1. Menos de MIN_SEGMENTOS segmentos no total
  2. NARRADOR aparece em segmento que não seja o primeiro
  3. Alguma fala com mais de MAX_PALAVRAS_POR_FALA palavras
  4. Algum conceito do plano não foi coberto (verificado por keywords)
  5. block_transition=True nunca ocorre (episódio sem estrutura de blocos)

AVISOS (não bloqueiam, mas alertam):
  1. Conceito coberto apenas superficialmente (< 3 segmentos)
  2. Código lido literalmente (detectado por padrões)
  3. Frase proibida detectada ("como você pode ver", "veja a figura")
  4. A mesma confirmação usada mais de 3 vezes ("Perfeita!")
  5. Episódio muito curto para o depth_level planejado

O pipeline usa validator.py para:
  - Decidir se regenera o episódio (erros críticos)
  - Registrar avisos no log para análise posterior
  - Calcular métricas de qualidade do lote
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from models import (
    Conceito,
    DepthLevel,
    Episodio,
    EpisodioPlano,
    ResultadoValidacao,
    Segmento,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════

MIN_SEGMENTOS = 20
MAX_PALAVRAS_POR_FALA = 45  # 40 é o limite do script_template_v7, +5 de margem

MIN_SEGMENTOS_POR_DEPTH = {
    DepthLevel.QUICK:    25,
    DepthLevel.STANDARD: 35,
    DepthLevel.DETAILED: 45,
}

# Frases proibidas para áudio (ouvinte não vê tela)
FRASES_VISUAIS = [
    "como você pode ver",
    "veja a figura",
    "no código abaixo",
    "na tabela",
    "conforme mostrado",
    "observe o diagrama",
    "na imagem",
    "no slide",
    "no quadro",
    "no exemplo acima",
    "no exemplo abaixo",
]

# Padrões de código lido literalmente (não deve aparecer em áudio)
PADROES_CODIGO_LITERAL = [
    re.compile(r"\bfor\s+\w+\s+in\s+range\s*\(", re.IGNORECASE),
    re.compile(r"\bdef\s+\w+\s*\("),
    re.compile(r"\bprint\s*\("),
    re.compile(r"\bimport\s+\w+"),
    re.compile(r"\bwhile\s+\w+\s*[:<]"),
    re.compile(r"[a-z_]+\s*=\s*\[\]"),
    re.compile(r"\bwriteln\s*\(", re.IGNORECASE),
    re.compile(r"\breadln\s*\(", re.IGNORECASE),
    re.compile(r"para\s+\w+\s+de\s+\d+\s+incr\s+\d+\s+até", re.IGNORECASE),
]

# Confirmações repetitivas
CONFIRMACOES_CLICHE = [
    "perfeita!", "perfeito!", "exatamente!", "isso mesmo!",
    "ótimo!", "show!", "muito bem!",
]


# ═══════════════════════════════════════════════════════════════
# VERIFICAÇÕES INDIVIDUAIS
# ═══════════════════════════════════════════════════════════════

def _verificar_minimo_segmentos(
    episodio: Episodio,
    plano: EpisodioPlano,
) -> list[str]:
    total = len(episodio.segments)
    minimo = max(MIN_SEGMENTOS, MIN_SEGMENTOS_POR_DEPTH.get(plano.depth_level, MIN_SEGMENTOS))
    if total < minimo:
        return [
            f"Apenas {total} segmentos. Mínimo para {plano.depth_level.value}: {minimo}."
        ]
    return []


def _verificar_narrador_posicao(episodio: Episodio) -> list[str]:
    """NARRADOR deve aparecer apenas no primeiro segmento."""
    erros = []
    for idx, seg in enumerate(episodio.segments):
        if seg.speaker == "NARRADOR" and idx != 0:
            erros.append(
                f"NARRADOR aparece no segmento {idx + 1} (só pode ser no segmento 1)."
            )
    return erros


def _verificar_tamanho_falas(episodio: Episodio) -> list[str]:
    """Nenhuma fala pode ter mais de MAX_PALAVRAS_POR_FALA palavras."""
    erros = []
    maior = 0
    maior_idx = -1

    for idx, seg in enumerate(episodio.segments):
        palavras = len(seg.text.split())
        if palavras > maior:
            maior = palavras
            maior_idx = idx
        if palavras > MAX_PALAVRAS_POR_FALA:
            erros.append(
                f"Fala {idx + 1} ({seg.speaker}) tem {palavras} palavras "
                f"(máximo: {MAX_PALAVRAS_POR_FALA})."
            )
    return erros


def _verificar_block_transition(episodio: Episodio) -> list[str]:
    """Pelo menos 1 block_transition=True deve existir (estrutura de blocos)."""
    tem_transition = any(seg.block_transition for seg in episodio.segments)
    if not tem_transition:
        return ["Nenhum block_transition=true. Episódio sem estrutura de blocos."]
    return []


def _verificar_cobertura_conceitos(
    episodio: Episodio,
    conceitos: list[Conceito],
    plano: EpisodioPlano,
) -> tuple[list[str], list[str], list[str]]:
    """
    Verifica se os conceitos do plano foram cobertos no roteiro.

    Estratégia: verifica se as keywords do conceito aparecem no texto dos segmentos.
    É heurístico — o generator pode usar sinônimos.

    Retorna: (erros, avisos, cobertos, faltando)
    """
    erros = []
    avisos = []
    cobertos = []
    faltando = []

    texto_total = " ".join(s.text.lower() for s in episodio.segments)

    id_para_conceito = {c.id: c for c in conceitos}

    for conceito_id in plano.conceitos:
        conceito = id_para_conceito.get(conceito_id)
        if not conceito:
            continue

        # Conta quantas keywords do conceito aparecem no texto
        keywords_encontradas = sum(
            1 for kw in conceito.keywords
            if kw.lower() in texto_total
        )

        # Conta segmentos que mencionam o nome do conceito
        nome_lower = conceito.nome.lower()
        segs_com_conceito = sum(
            1 for s in episodio.segments
            if nome_lower in s.text.lower()
            or any(kw.lower() in s.text.lower() for kw in conceito.keywords[:3])
        )

        if keywords_encontradas == 0 and nome_lower not in texto_total:
            faltando.append(conceito.nome)
        elif segs_com_conceito < 3:
            avisos.append(
                f"Conceito '{conceito.nome}' mencionado apenas em "
                f"{segs_com_conceito} segmento(s). Pode estar superficial."
            )
            cobertos.append(conceito.nome)
        else:
            cobertos.append(conceito.nome)

    if faltando:
        erros.append(
            f"Conceito(s) não coberto(s): {', '.join(faltando)}. "
            f"Verifique se o roteiro realmente ensina esses temas."
        )

    return erros, avisos, cobertos, faltando


def _verificar_audio_rules(episodio: Episodio) -> list[str]:
    """Verifica regras de áudio: sem referências visuais, sem código literal."""
    avisos = []
    texto_total = " ".join(s.text.lower() for s in episodio.segments)
    texto_completo = " ".join(s.text for s in episodio.segments)

    # Frases visuais
    for frase in FRASES_VISUAIS:
        if frase in texto_total:
            avisos.append(f"Referência visual detectada: '{frase}'")

    # Código lido literalmente
    for padrao in PADROES_CODIGO_LITERAL:
        if padrao.search(texto_completo):
            avisos.append(f"Possível código lido literalmente: {padrao.pattern}")
            break

    return avisos


def _verificar_confirmacoes_repetidas(episodio: Episodio) -> list[str]:
    """Verifica se a mesma confirmação é usada mais de 3 vezes."""
    avisos = []
    textos_lower = [s.text.lower() for s in episodio.segments]

    for cliche in CONFIRMACOES_CLICHE:
        contagem = sum(1 for t in textos_lower if cliche in t)
        if contagem > 3:
            avisos.append(
                f"Confirmação repetida: '{cliche}' usada {contagem} vezes. "
                f"Usar variações."
            )

    return avisos


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def validar_episodio(
    episodio: Episodio,
    plano: EpisodioPlano,
    conceitos: list[Conceito],
) -> ResultadoValidacao:
    """
    Valida um episódio gerado contra os critérios objetivos.

    Args:
        episodio: Episodio gerado por generator.py
        plano: EpisodioPlano original (para verificar conceitos esperados)
        conceitos: Lista completa de Conceito (para acessar keywords)

    Returns:
        ResultadoValidacao com valido=True apenas se sem erros críticos.
    """
    logger.info(
        f"[Validator] Validando ep {episodio.numero}: "
        f"'{episodio.title}' ({len(episodio.segments)} segmentos)"
    )

    erros: list[str] = []
    avisos: list[str] = []
    cobertos: list[str] = []
    faltando: list[str] = []

    # ── Verificações de erro ──────────────────────────────────

    erros += _verificar_minimo_segmentos(episodio, plano)
    erros += _verificar_narrador_posicao(episodio)
    erros += _verificar_tamanho_falas(episodio)
    erros += _verificar_block_transition(episodio)

    erros_conc, avisos_conc, cobertos, faltando = _verificar_cobertura_conceitos(
        episodio, conceitos, plano
    )
    erros += erros_conc
    avisos += avisos_conc

    # ── Verificações de aviso ─────────────────────────────────

    avisos += _verificar_audio_rules(episodio)
    avisos += _verificar_confirmacoes_repetidas(episodio)

    # ── Métricas ──────────────────────────────────────────────

    todas_palavras = [len(s.text.split()) for s in episodio.segments]
    maior_fala = max(todas_palavras) if todas_palavras else 0

    # Detecta código literal para o campo específico
    texto_completo = " ".join(s.text for s in episodio.segments)
    tem_codigo_literal = any(p.search(texto_completo) for p in PADROES_CODIGO_LITERAL)

    valido = len(erros) == 0

    if valido:
        logger.info(
            f"[Validator] ✅ Ep {episodio.numero} válido | "
            f"{len(episodio.segments)} segmentos | "
            f"{len(avisos)} aviso(s)"
        )
    else:
        logger.error(
            f"[Validator] ❌ Ep {episodio.numero} INVÁLIDO:\n"
            + "\n".join(f"  • {e}" for e in erros)
        )

    if avisos:
        logger.warning(
            f"[Validator] ⚠️ Ep {episodio.numero} avisos:\n"
            + "\n".join(f"  • {a}" for a in avisos)
        )

    return ResultadoValidacao(
        valido=valido,
        episodio_numero=episodio.numero,
        total_segmentos=len(episodio.segments),
        erros=erros,
        avisos=avisos,
        conceitos_cobertos=cobertos,
        conceitos_faltando=faltando,
        falante_mais_longo_palavras=maior_fala,
        tem_codigo_literal=tem_codigo_literal,
    )
