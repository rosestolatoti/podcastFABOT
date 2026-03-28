"""
content_bible.py — Gera o documento de referência que acompanha TODOS os episódios.

A ContentBible é gerada UMA VEZ por livro/documento e serve de âncora para
o generator.py em TODAS as chamadas subsequentes.

Sem a ContentBible:
  - Ep 1 usa o exemplo "Magazine Luiza vendendo produtos"
  - Ep 7 usa "Magazine Luiza vendendo produtos" de novo
  - Tom muda entre episódios
  - Termos técnicos são explicados de formas diferentes

Com a ContentBible:
  - Glossário fixo: "variável" sempre é explicada da mesma forma
  - Tom fixo: nível de formalidade consistente do ep 1 ao N
  - Exemplos do próprio livro: o generator sabe quais exemplos o autor usa
  - O que não fazer: evita erros de interpretação comuns do conteúdo

NÃO faz:
  - Gerar roteiro
  - Decidir episódios
  - Chamar TTS
"""

from __future__ import annotations

import json
import logging

from api_router import chamar_llm
from models import ContentBible, DocumentoEstruturado

logger = logging.getLogger(__name__)

# Limite de texto enviado ao LLM para geração da bible
# Mais do que isso não melhora a qualidade e aumenta custo
MAX_PALAVRAS_BIBLE = 4000


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_BIBLE = """Você é um especialista em design instrucional e produção de podcasts educacionais.
Sua tarefa é criar um documento de referência (Content Bible) para um podcast educacional
baseado em um livro didático.

A Content Bible garante consistência em todos os episódios do podcast.
Seja preciso, concreto e específico para o conteúdo deste livro.

RETORNE APENAS JSON VÁLIDO. Sem texto antes ou depois."""

_PROMPT_BIBLE_TEMPLATE = """Analise o livro "{titulo}" e crie a Content Bible para o podcast educacional.

TRECHO DO LIVRO (para referência):
{texto}

RETORNE um JSON com esta estrutura exata:
{{
  "glossario": {{
    "termo_tecnico_1": "definição curta e clara em 1 frase",
    "termo_tecnico_2": "definição curta e clara em 1 frase"
  }},
  "estilo_tom": "Descrição do tom adequado para este conteúdo (3-4 frases). Ex: linguagem técnica mas acessível, analogias do mundo dos negócios, sem jargão excessivo.",
  "exemplos_do_livro": [
    "Exemplo real que o próprio livro usa e deve aparecer no podcast",
    "Outro exemplo real do livro"
  ],
  "conceitos_centrais": [
    "Conceito mais importante do livro",
    "Segundo conceito mais importante"
  ],
  "o_que_nao_fazer": [
    "Erro de interpretação comum sobre este conteúdo",
    "Outro erro comum"
  ],
  "nivel_audiencia": "iniciante|intermediario|avancado",
  "area_conhecimento": "area principal do conteúdo (ex: programacao, estatistica, comunicacao)"
}}

REGRAS:
1. "glossario": inclua 5-15 termos técnicos do conteúdo com definições em português informal
2. "exemplos_do_livro": extraia exemplos REAIS que o livro usa (figuras, situações, analogias)
3. "conceitos_centrais": os 5-7 conceitos sem os quais nada mais faz sentido
4. "o_que_nao_fazer": erros comuns de quem está aprendendo este assunto pela primeira vez
5. "nivel_audiencia": avalie pelo vocabulário e pré-requisitos assumidos no texto
6. Seja específico ao conteúdo — não dê respostas genéricas

RETORNE APENAS JSON VÁLIDO."""


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def gerar_content_bible(documento: DocumentoEstruturado) -> ContentBible:
    """
    Gera a Content Bible para o documento.

    Envia os primeiros MAX_PALAVRAS_BIBLE palavras do documento ao LLM.
    A introdução e os primeiros capítulos geralmente contêm a essência do livro.

    Args:
        documento: DocumentoEstruturado de extractor.py

    Returns:
        ContentBible pronta para ser usada pelo generator.py

    Raises:
        RuntimeError: Se todas as APIs falharem (propagado de api_router.py)
    """
    logger.info(f"[ContentBible] Gerando bible para: {documento.titulo_documento}")

    # Seleciona os primeiros N palavras do texto completo
    palavras = documento.texto_completo.split()
    texto_referencia = " ".join(palavras[:MAX_PALAVRAS_BIBLE])

    prompt = _PROMPT_BIBLE_TEMPLATE.format(
        titulo=documento.titulo_documento,
        texto=texto_referencia,
    )

    resposta = chamar_llm(
        system_prompt=SYSTEM_PROMPT_BIBLE,
        user_prompt=prompt,
        esperar_json=True,
        temperature_override=0.3,  # Baixa: queremos consistência, não criatividade
    )

    try:
        data = json.loads(resposta.texto)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"ContentBible: JSON inválido recebido de {resposta.api_nome}: {e}"
        )

    # Parseia o JSON com fallbacks para campos obrigatórios
    bible = ContentBible(
        documento_titulo=documento.titulo_documento,
        glossario=data.get("glossario", {}),
        estilo_tom=data.get("estilo_tom", "Tom didático e acessível."),
        exemplos_do_livro=data.get("exemplos_do_livro", []),
        conceitos_centrais=data.get("conceitos_centrais", []),
        o_que_nao_fazer=data.get("o_que_nao_fazer", []),
        nivel_audiencia=data.get("nivel_audiencia", "iniciante"),
        area_conhecimento=data.get("area_conhecimento", "geral"),
    )

    logger.info(
        f"[ContentBible] ✅ Bible gerada via {resposta.api_nome}:\n"
        f"  Glossário: {len(bible.glossario)} termos\n"
        f"  Conceitos centrais: {len(bible.conceitos_centrais)}\n"
        f"  Exemplos do livro: {len(bible.exemplos_do_livro)}\n"
        f"  O que não fazer: {len(bible.o_que_nao_fazer)}"
    )

    return bible


# ═══════════════════════════════════════════════════════════════
# SERIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

def bible_para_texto_prompt(bible: ContentBible) -> str:
    """
    Converte a ContentBible em texto formatado para incluir no prompt do generator.
    
    O generator.py usa esta função para inserir a bible no system prompt.
    Formato otimizado para que o LLM absorva as instruções rapidamente.
    """
    linhas = [
        f"━━━ CONTENT BIBLE — {bible.documento_titulo} ━━━",
        "",
        f"ÁREA: {bible.area_conhecimento} | NÍVEL: {bible.nivel_audiencia}",
        "",
        "TOM E ESTILO:",
        bible.estilo_tom,
        "",
    ]

    if bible.glossario:
        linhas.append("GLOSSÁRIO (use SEMPRE estas definições):")
        for termo, definicao in list(bible.glossario.items())[:12]:  # Max 12 termos
            linhas.append(f"  {termo}: {definicao}")
        linhas.append("")

    if bible.conceitos_centrais:
        linhas.append("CONCEITOS CENTRAIS (não simplificar demais):")
        for c in bible.conceitos_centrais[:7]:
            linhas.append(f"  • {c}")
        linhas.append("")

    if bible.exemplos_do_livro:
        linhas.append("EXEMPLOS DO LIVRO (use-os nos episódios):")
        for e in bible.exemplos_do_livro[:5]:
            linhas.append(f"  • {e}")
        linhas.append("")

    if bible.o_que_nao_fazer:
        linhas.append("O QUE NÃO FAZER (erros comuns):")
        for e in bible.o_que_nao_fazer[:5]:
            linhas.append(f"  ✗ {e}")
        linhas.append("")

    linhas.append("━━━ FIM DA CONTENT BIBLE ━━━")

    return "\n".join(linhas)
