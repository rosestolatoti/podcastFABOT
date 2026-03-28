"""
generator.py — Gera roteiros de episódios com qualidade constante.

A grande inovação em relação ao código original:
  - CONTEXTO ACUMULADO: cada episódio sabe o que foi ensinado antes
  - CONTENT BIBLE: garante consistência de tom, glossário e exemplos
  - SEED DE SEMENTE: última fala do ep N planta o tema do ep N+1
  - ANTI-REPETIÇÃO: lista explícita de o que NÃO repetir

Por que a qualidade cai nos episódios do meio (e como corrigimos):
  Original:  cada chamada = prompt genérico + chunk do livro
  Corrigido: cada chamada = bible + chunk + conceitos cobertos + resumo do ep anterior
                            + conceitos que o próximo vai precisar

Compatibilidade:
  - Gera JSON no formato exato de script_template_v7.py
  - Usa os speakers NARRADOR, WILLIAM, CRISTINA
  - Respeita pause_after_ms e block_transition
  - Segue depth_level do EpisodioPlano

NÃO faz:
  - Síntese de voz (responsabilidade do projeto principal)
  - Salvamento no banco de dados
  - Validação pós-geração (responsabilidade de validator.py)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from api_router import chamar_llm
from content_bible import bible_para_texto_prompt
from models import (
    ContentBible,
    DepthLevel,
    Episodio,
    EpisodioPlano,
    PlanoCompleto,
    Segmento,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE PERSONAGENS (compatível com script_template_v7)
# ═══════════════════════════════════════════════════════════════

SPEAKERS = {
    "narrador": "NARRADOR",
    "host":     "WILLIAM",
    "cohost":   "CRISTINA",
}

DEPTH_INSTRUCOES = {
    DepthLevel.QUICK:    "Pontos fundamentais apenas. Mínimo 5 segmentos por conceito. Total mínimo: 25 segmentos.",
    DepthLevel.STANDARD: "Pontos principais com exemplos. Mínimo 8 segmentos por conceito. Total mínimo: 35 segmentos.",
    DepthLevel.DETAILED: "MODO ENSINO COMPLETO. Cobrir TUDO. Mínimo 12 segmentos por conceito. Total mínimo: 45 segmentos.",
}


# ═══════════════════════════════════════════════════════════════
# CONSTRUÇÃO DO PROMPT
# ═══════════════════════════════════════════════════════════════

def _construir_system_prompt(bible: ContentBible) -> str:
    """
    System prompt que contém a identidade fixa + a Content Bible.
    Enviado em TODAS as chamadas de geração.
    """
    bible_texto = bible_para_texto_prompt(bible)

    return f"""Você é o roteirista do FABOT Podcast, podcast educacional sobre {bible.area_conhecimento}.

IDENTIDADE FIXA:
  NARRADOR  — voz de abertura. Apenas no PRIMEIRO segmento. Tom de locutor profissional.
  WILLIAM   — masculino. Faz perguntas. Representa o ouvinte curioso. Traz exemplos de negócio.
  CRISTINA  — feminina. Explica com paciência. Diferencia conceitos. Confirma entendimento.

OUVINTE: estudante universitário de {bible.nivel_audiencia} nível. Ouve no carro ou caminhando. NÃO vê tela.

{bible_texto}

REGRAS DE ÁUDIO (CRÍTICO):
  ✗ Proibido: "como você pode ver", "no código abaixo", "na figura", "veja o exemplo"
  ✗ Proibido: ler código literalmente (for i in range...) — descreva O QUE FAZ
  ✓ Obrigatório: descrever código em palavras ("você cria uma lista de sete dias e com três linhas...")
  ✓ Números por extenso: "quinze mil" não "15000"
  ✓ Siglas explicadas na primeira menção

TAMANHO DAS FALAS:
  Máximo 40 palavras por fala. Máximo 2 frases por fala (NARRADOR pode ter 3).
  WILLIAM pergunta mais do que explica.
  CRISTINA explica em blocos curtos — nunca monólogo longo.
  Troca de falante frequente — diálogo real, não palestra.

CONFIRMAÇÕES VARIADAS (nunca use "Perfeita!" repetido):
  "Exatamente isso.", "Perfeito!", "Faz sentido.", "Isso mesmo.",
  "Boa pergunta.", "Você pegou rápido.", "Correto.", "Certo."

RETORNE APENAS JSON VÁLIDO. Sem texto antes, sem texto depois."""


def _construir_user_prompt(
    episodio_plano: EpisodioPlano,
    plano: PlanoCompleto,
    bible: ContentBible,
    resumo_ep_anterior: str,
    conceitos_map: dict,  # id → nome
) -> str:
    """
    User prompt específico para este episódio.
    Inclui contexto acumulado para manter qualidade constante.
    """
    total_eps = plano.total_episodios
    num_ep = episodio_plano.numero
    depth = episodio_plano.depth_level
    instrucao_depth = DEPTH_INSTRUCOES[depth]

    # Nomes dos conceitos deste episódio
    nomes_conceitos = [
        conceitos_map.get(cid, cid)
        for cid in episodio_plano.conceitos
    ]

    # Conceitos já cobertos (para anti-repetição)
    ja_cobertos = episodio_plano.dependencias_satisfeitas
    nomes_cobertos = [conceitos_map.get(cid, cid) for cid in ja_cobertos[-8:]]  # Últimos 8

    # Conceitos que o próximo episódio vai precisar (para plantar semente)
    nomes_proximo = [
        conceitos_map.get(cid, cid)
        for cid in episodio_plano.conceitos_preparar[:3]
    ]

    # Monta o prompt
    partes = [
        f"━━━ EPISÓDIO {num_ep} DE {total_eps} ━━━",
        f"Título sugerido: {episodio_plano.titulo_sugerido}",
        "",
        f"CONCEITOS A ENSINAR NESTE EPISÓDIO:",
    ]
    for nome in nomes_conceitos:
        partes.append(f"  • {nome}")

    partes += [
        "",
        f"PROFUNDIDADE: {depth.value}",
        instrucao_depth,
        "",
    ]

    if nomes_cobertos:
        partes += [
            "JÁ ENSINADO NOS EPISÓDIOS ANTERIORES (NÃO REPETIR, apenas referenciar brevemente se necessário):",
        ]
        for nome in nomes_cobertos:
            partes.append(f"  ✓ {nome}")
        partes.append("")

    if resumo_ep_anterior:
        partes += [
            "RESUMO DO EPISÓDIO ANTERIOR (para dar continuidade natural):",
            resumo_ep_anterior,
            "",
        ]

    if nomes_proximo:
        partes += [
            f"PRÓXIMO EPISÓDIO vai ensinar: {', '.join(nomes_proximo)}",
            "→ Plante a semente desses conceitos nas últimas falas deste episódio.",
            "",
        ]

    if episodio_plano.notas_gerador:
        partes += [
            "NOTAS ESPECIAIS PARA ESTE EPISÓDIO:",
            episodio_plano.notas_gerador,
            "",
        ]

    partes += [
        "━━━ MATERIAL DE REFERÊNCIA (não leia literalmente — transforme em diálogo) ━━━",
        episodio_plano.chunk_texto or "[Sem chunk de texto — use apenas os conceitos listados]",
        "",
        "━━━ CHECKLIST ANTES DE RETORNAR ━━━",
        f"  □ Total de segmentos maior que {DEPTH_INSTRUCOES[depth].split('Total mínimo: ')[1].split(' ')[0]}?",
        "  □ NARRADOR aparece apenas no PRIMEIRO segmento?",
        "  □ block_transition: true no ÚLTIMO segmento de CADA bloco?",
        "  □ Nenhuma fala com mais de 40 palavras?",
        "  □ Nenhum código lido literalmente?",
        "  □ Cada conceito da lista foi ensinado?",
        "",
        "RETORNE O JSON:",
        '{',
        '  "title": "Título direto e curioso para o episódio",',
        '  "episode_summary": "Uma frase: o que o ouvinte vai aprender",',
        '  "keywords": ["termo1", "termo2", "termo3", "termo4", "termo5"],',
        '  "segments": [',
        '    {"speaker": "NARRADOR", "text": "...", "emotion": "neutral", "pause_after_ms": 1800, "block_transition": false},',
        '    {"speaker": "WILLIAM", "text": "...", "emotion": "enthusiastic", "pause_after_ms": 550, "block_transition": false},',
        '    {"speaker": "CRISTINA", "text": "...", "emotion": "neutral", "pause_after_ms": 700, "block_transition": true}',
        '  ]',
        '}',
        "",
        "RETORNE APENAS O JSON. Sem texto antes ou depois.",
    ]

    return "\n".join(partes)


# ═══════════════════════════════════════════════════════════════
# PARSE DO JSON DO LLM
# ═══════════════════════════════════════════════════════════════

def _parsear_episodio(json_str: str, numero: int, api_nome: str, tokens: int) -> Episodio:
    """Converte o JSON do LLM em objeto Episodio."""
    data = json.loads(json_str)

    segments_raw = data.get("segments", [])
    segmentos: list[Segmento] = []

    for seg in segments_raw:
        if not isinstance(seg, dict):
            continue
        speaker = str(seg.get("speaker", "WILLIAM")).upper().strip()
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        segmentos.append(Segmento(
            speaker=speaker,
            text=text,
            emotion=str(seg.get("emotion", "neutral")),
            pause_after_ms=int(seg.get("pause_after_ms", 600)),
            block_transition=bool(seg.get("block_transition", False)),
        ))

    return Episodio(
        numero=numero,
        title=str(data.get("title", f"Episódio {numero}")).strip(),
        episode_summary=str(data.get("episode_summary", "")).strip(),
        keywords=data.get("keywords", []),
        segments=segmentos,
        api_usada=api_nome,
        tokens_usados=tokens,
    )


def _gerar_resumo_episodio(episodio: Episodio) -> str:
    """
    Gera um resumo de 3-4 frases do episódio para passar ao próximo.
    Usa apenas as primeiras e últimas falas para capturar início e conclusão.
    """
    if not episodio.segments:
        return ""

    # Pega primeiras 3 e últimas 3 falas (excluindo NARRADOR)
    falas = [s for s in episodio.segments if s.speaker != "NARRADOR"]
    amostra = falas[:3] + falas[-3:] if len(falas) > 6 else falas

    textos = [f"{s.speaker}: {s.text}" for s in amostra]
    intro = f"Ep {episodio.numero} — '{episodio.title}': "
    resumo = f"{intro}{episodio.episode_summary}. Conceitos cobertos: {', '.join(episodio.keywords[:5])}."
    return resumo


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def gerar_episodio(
    episodio_plano: EpisodioPlano,
    plano: PlanoCompleto,
    bible: ContentBible,
    conceitos_lista: list,  # list[Conceito]
    historico_episodios: list[Episodio],
    max_tentativas: int = 3,
) -> Episodio:
    """
    Gera o roteiro de um episódio com contexto acumulado.

    Args:
        episodio_plano: Plano do episódio (de grouper.py)
        plano: Plano completo (para saber total de eps)
        bible: Content Bible (para consistência)
        conceitos_lista: Lista completa de conceitos (para resolver nomes)
        historico_episodios: Episódios já gerados (para contexto acumulado)
        max_tentativas: Número máximo de tentativas antes de desistir

    Returns:
        Episodio com roteiro completo.

    Raises:
        RuntimeError: Se todas as tentativas falharem.
    """
    logger.info(
        f"[Generator] Gerando ep {episodio_plano.numero}/{plano.total_episodios}: "
        f"'{episodio_plano.titulo_sugerido}'"
    )

    # Mapa de ID → nome para resolver referências
    conceitos_map = {c.id: c.nome for c in conceitos_lista}

    # Resumo do episódio anterior (contexto acumulado)
    resumo_anterior = ""
    if historico_episodios:
        ultimo_ep = historico_episodios[-1]
        resumo_anterior = _gerar_resumo_episodio(ultimo_ep)

    # Constrói prompts
    system_prompt = _construir_system_prompt(bible)
    user_prompt = _construir_user_prompt(
        episodio_plano, plano, bible, resumo_anterior, conceitos_map
    )

    ultimo_erro = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            resposta = chamar_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                esperar_json=True,
                temperature_override=0.88,
            )

            episodio = _parsear_episodio(
                resposta.texto,
                episodio_plano.numero,
                resposta.api_nome,
                resposta.tokens_estimados,
            )
            episodio.tentativas = tentativa

            # Validação mínima inline (validator.py fará a completa)
            min_segs = 20
            if len(episodio.segments) < min_segs:
                logger.warning(
                    f"[Generator] Ep {episodio_plano.numero}: "
                    f"apenas {len(episodio.segments)} segmentos (mínimo: {min_segs}). "
                    f"Tentativa {tentativa}/{max_tentativas}."
                )
                if tentativa < max_tentativas:
                    # Enriquece o prompt para a próxima tentativa
                    user_prompt = (
                        f"[ATENÇÃO: Resposta anterior com apenas {len(episodio.segments)} segmentos. "
                        f"PRECISA de pelo menos {min_segs} segmentos. "
                        f"Seja mais detalhado em cada conceito.]\n\n"
                        + user_prompt
                    )
                    continue

            logger.info(
                f"[Generator] ✅ Ep {episodio_plano.numero}: "
                f"{len(episodio.segments)} segmentos | "
                f"'{episodio.title}' | "
                f"via {resposta.api_nome} | "
                f"tentativa {tentativa}"
            )
            return episodio

        except Exception as e:
            ultimo_erro = e
            logger.error(
                f"[Generator] ❌ Ep {episodio_plano.numero} tentativa {tentativa}: {e}"
            )

    raise RuntimeError(
        f"Ep {episodio_plano.numero}: falhou após {max_tentativas} tentativas. "
        f"Último erro: {ultimo_erro}"
    )
