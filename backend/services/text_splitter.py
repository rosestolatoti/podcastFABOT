"""
FABOT Podcast Studio — text_splitter.py

Problema resolvido:
  Quando o texto é longo, o LLM entra em modo de compressão e gera
  conteúdo raso. A solução é dividir o texto em seções menores antes
  de mandar para o LLM. Cada seção vira um episódio completo e detalhado.

Lógica de divisão:
  1. Detecta headers ## como divisores naturais de seção
  2. Se uma seção for maior que MAX_TOKENS, subdivide pelos ### 
  3. Se ainda for grande, corta por parágrafos mantendo contexto
  4. Cada seção resultante tem entre MIN_TOKENS e MAX_TOKENS

Resultado:
  Texto com 9 capítulos → 9 episódios
  Cada episódio: 10-15 minutos de podcast completo e detalhado
  Total: até 2 horas de conteúdo de qualidade
"""

import re
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────
# LIMITES CALIBRADOS PARA llama-3.3-70b-versatile NO GROQ
# ─────────────────────────────────────────────────────────────────
# Contexto total do modelo: 128k tokens
# Input máximo seguro:  3000 tokens (~12.000 chars)
#   → Deixa ~8000 tokens livres para o output (roteiro completo)
#   → ~150 segmentos de podcast possíveis = 20-25 min por episódio
#
# Input mínimo útil:  400 tokens (~1600 chars)
#   → Seções muito pequenas geram episódios rasos
#   → Abaixo disso, agrupar com a seção seguinte

MAX_TOKENS   = 3000   # máximo por chamada ao LLM
MIN_TOKENS   = 400    # mínimo para um episódio ter profundidade
CHARS_PER_TOKEN = 4   # estimativa conservadora (português)


@dataclass
class Secao:
    titulo: str           # título da seção
    conteudo: str         # texto completo
    nivel: int            # 1=capitulo, 2=secao, 3=subsecao
    tokens_estimado: int  # estimativa de tokens
    indice: int           # posição no documento original


def estimar_tokens(texto: str) -> int:
    return len(texto) // CHARS_PER_TOKEN


def dividir_texto(texto: str) -> list[Secao]:
    """
    Divide o texto em seções adequadas para o LLM.
    Retorna lista de Secao, cada uma pronta para virar um episódio.
    """
    secoes_brutas = _extrair_secoes(texto)
    secoes_finais = _ajustar_tamanhos(secoes_brutas)
    return secoes_finais


def _extrair_secoes(texto: str) -> list[Secao]:
    """
    Extrai seções baseadas em headers Markdown.
    # Capítulo (nível 1)
    ## Seção (nível 2)  ← divisor principal
    ### Subseção (nível 3)
    """
    secoes = []

    # Divide por headers ## ou # (qualquer nível)
    partes = re.split(r'\n(?=#{1,3} )', texto)

    for i, parte in enumerate(partes):
        if not parte.strip():
            continue

        # Detecta nível do header
        if parte.startswith('### '):
            nivel = 3
            titulo = parte.split('\n')[0].replace('### ', '').strip()
        elif parte.startswith('## '):
            nivel = 2
            titulo = parte.split('\n')[0].replace('## ', '').strip()
        elif parte.startswith('# '):
            nivel = 1
            titulo = parte.split('\n')[0].replace('# ', '').strip()
        else:
            # Texto sem header (introdução do capítulo)
            nivel = 2
            titulo = "Introdução"

        tokens = estimar_tokens(parte)
        secoes.append(Secao(
            titulo=titulo,
            conteudo=parte.strip(),
            nivel=nivel,
            tokens_estimado=tokens,
            indice=i
        ))

    return secoes


def _ajustar_tamanhos(secoes: list[Secao]) -> list[Secao]:
    """
    Garante que cada seção está dentro dos limites.
    - Seções grandes → subdivide por parágrafo
    - Seções pequenas → agrupa com a próxima
    """
    resultado = []
    buffer = []
    buffer_tokens = 0

    for secao in secoes:

        # Seção GRANDE demais → subdivide
        if secao.tokens_estimado > MAX_TOKENS:
            # Salva buffer atual primeiro
            if buffer:
                resultado.append(_juntar_buffer(buffer))
                buffer = []
                buffer_tokens = 0

            # Subdivide a seção grande por parágrafo
            subsecoes = _subdividir_por_paragrafo(secao)
            resultado.extend(subsecoes)
            continue

        # Seção PEQUENA demais → acumula no buffer
        if secao.tokens_estimado < MIN_TOKENS:
            buffer.append(secao)
            buffer_tokens += secao.tokens_estimado

            # Buffer cheio → salva
            if buffer_tokens >= MIN_TOKENS:
                resultado.append(_juntar_buffer(buffer))
                buffer = []
                buffer_tokens = 0
            continue

        # Seção no tamanho certo → salva buffer e adiciona ela
        if buffer:
            resultado.append(_juntar_buffer(buffer))
            buffer = []
            buffer_tokens = 0

        resultado.append(secao)

    # Salva qualquer buffer restante
    if buffer:
        resultado.append(_juntar_buffer(buffer))

    # Renumera os índices
    for i, s in enumerate(resultado):
        s.indice = i + 1

    return resultado


def _subdividir_por_paragrafo(secao: Secao) -> list[Secao]:
    """
    Divide seção grande em subsecções por parágrafo.
    Mantém o título da seção pai em cada parte.
    """
    paragrafos = re.split(r'\n\n+', secao.conteudo)
    partes = []
    parte_atual = []
    tokens_atual = 0

    for para in paragrafos:
        tokens_para = estimar_tokens(para)

        if tokens_atual + tokens_para > MAX_TOKENS and parte_atual:
            # Salva parte atual e começa nova
            conteudo = '\n\n'.join(parte_atual)
            partes.append(Secao(
                titulo=f"{secao.titulo} (parte {len(partes)+1})",
                conteudo=conteudo,
                nivel=secao.nivel,
                tokens_estimado=estimar_tokens(conteudo),
                indice=0
            ))
            parte_atual = [para]
            tokens_atual = tokens_para
        else:
            parte_atual.append(para)
            tokens_atual += tokens_para

    if parte_atual:
        conteudo = '\n\n'.join(parte_atual)
        partes.append(Secao(
            titulo=f"{secao.titulo} (parte {len(partes)+1})" if len(partes) > 0 else secao.titulo,
            conteudo=conteudo,
            nivel=secao.nivel,
            tokens_estimado=estimar_tokens(conteudo),
            indice=0
        ))

    return partes


def _juntar_buffer(buffer: list[Secao]) -> Secao:
    """Junta seções pequenas em uma só."""
    titulo = " + ".join(s.titulo for s in buffer)
    conteudo = '\n\n'.join(s.conteudo for s in buffer)
    return Secao(
        titulo=titulo,
        conteudo=conteudo,
        nivel=buffer[0].nivel,
        tokens_estimado=estimar_tokens(conteudo),
        indice=0
    )


def relatorio_divisao(secoes: list[Secao]) -> str:
    """Gera relatório legível da divisão para debug."""
    linhas = [f"{'='*65}"]
    linhas.append(f"DIVISÃO DO TEXTO — {len(secoes)} episódios")
    linhas.append(f"{'='*65}")

    total_tokens = 0
    total_min_estimado = 0

    for s in secoes:
        tokens = s.tokens_estimado
        total_tokens += tokens
        # Estimativa: 1 token de input → ~2.5 tokens de output de podcast
        # ~140 palavras/min × 0.7 (média tokens por palavra) = 98 tok/min
        min_podcast = round((tokens * 2.5) / 98, 1)
        total_min_estimado += min_podcast

        status = "✅" if MIN_TOKENS <= tokens <= MAX_TOKENS else (
            "⚠️  GRANDE" if tokens > MAX_TOKENS else "⚠️  PEQUENO"
        )

        linhas.append(
            f"  Ep.{s.indice:02d} | {s.titulo[:45]:45} | "
            f"~{tokens:4} tok | ~{min_podcast:4.1f} min | {status}"
        )

    linhas.append(f"{'─'*65}")
    linhas.append(
        f"  TOTAL: {total_tokens} tokens estimados | "
        f"~{total_min_estimado:.0f} minutos de podcast"
    )
    linhas.append(f"{'='*65}")
    return '\n'.join(linhas)
