"""
concept_extractor.py — Extrai conceitos atômicos do documento via LLM.

Responsabilidades:
  - Enviar o texto do documento para o LLM em chunks gerenciáveis
  - Obter lista estruturada de conceitos com: nome, complexidade, dependências, keywords
  - Deduplicar conceitos similares
  - Retornar ResultadoExtracaoConceitos

Por que o LLM faz isso (e não regex):
  - Identificar o que É um conceito pedagógico requer compreensão semântica
  - Dependências entre conceitos só aparecem implicitamente no texto
  - Complexidade relativa entre conceitos exige contexto do domínio

NÃO faz:
  - Decidir quantos episódios (responsabilidade de decisor.py)
  - Agrupar conceitos (responsabilidade de grouper.py)
  - Gerar roteiro
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Optional

from api_router import chamar_llm
from models import (
    Bloco,
    Complexidade,
    Conceito,
    DocumentoEstruturado,
    ResultadoExtracaoConceitos,
)

logger = logging.getLogger(__name__)

# Tamanho máximo de texto enviado ao LLM por chunk (em palavras)
MAX_PALAVRAS_POR_CHUNK = 2500

# Mínimo de palavras para um bloco ser analisado individualmente
MIN_PALAVRAS_BLOCO = 80


# ═══════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT_EXTRATOR = """Você é um especialista em design instrucional.
Sua tarefa é analisar trechos de livros didáticos e identificar os conceitos pedagógicos atômicos.

Um CONCEITO ATÔMICO é:
- A menor unidade de conhecimento que pode ser ensinada de forma independente
- Tem um nome claro e uma definição precisa
- Pode depender de outros conceitos (mas não é igual a eles)
- Aparece como tema central de pelo menos um parágrafo do texto

RETORNE APENAS JSON VÁLIDO. Sem texto antes ou depois. Sem markdown."""

_PROMPT_EXTRATOR_TEMPLATE = """Analise o trecho abaixo do livro "{titulo}" e extraia os conceitos pedagógicos atômicos.

TRECHO:
{texto}

RETORNE um JSON com a seguinte estrutura exata:
{{
  "conceitos": [
    {{
      "id": "slug_sem_acento_snake_case",
      "nome": "Nome legível do conceito",
      "descricao": "1-2 frases do que é este conceito",
      "complexidade": "baixa|media|alta|critica",
      "dependencias": ["id_de_outro_conceito", "..."],
      "keywords": ["palavra1", "palavra2", "palavra3"],
      "tem_codigo": true|false,
      "tem_formula": true|false,
      "subconcepts_count": 0,
      "paragrafos_estimados": 2
    }}
  ]
}}

REGRAS:
1. "id" deve ser único, snake_case, sem acentos (ex: "variavel_inteira", "media_aritmetica")
2. "complexidade":
   - "baixa": conceito simples, sem pré-requisitos (ex: "dado estatístico")
   - "media": requer 1-2 conceitos anteriores (ex: "frequência relativa")
   - "alta": cadeia longa de deps, tem código ou fórmula (ex: "busca binária")
   - "critica": conceito central sem o qual nada faz sentido (ex: "variável em programação")
3. "dependencias": liste apenas IDs de conceitos QUE VOCÊ JÁ EXTRAIU nesta resposta
   Não invente dependências externas — elas serão resolvidas em passagem posterior
4. "tem_codigo": true se o conceito é explicado com exemplos de código/algoritmo
5. "paragrafos_estimados": quantos parágrafos do texto cobrem este conceito (estimativa)
6. Extraia TODOS os conceitos do trecho, não apenas os principais
7. NÃO inclua: nomes de autores, referências bibliográficas, números de página
"""

_PROMPT_DEDUP = """Você recebeu listas de conceitos extraídas de diferentes partes de um livro.
Alguns conceitos podem estar duplicados com nomes ligeiramente diferentes.

LISTA DE CONCEITOS:
{lista_conceitos}

TAREFA:
1. Identifique grupos de conceitos que representam a mesma ideia
2. Para cada grupo, mantenha APENAS o conceito mais completo (maior descricao + mais keywords)
3. Atualize as dependências para usar apenas IDs que existem na lista final
4. Corrija dependências circulares (A depende de B e B depende de A → remova a menos importante)

RETORNE um JSON com a estrutura:
{{
  "conceitos": [ lista_final_deduplicated ]
}}

RETORNE APENAS JSON VÁLIDO."""


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def _slug(texto: str) -> str:
    """Converte texto para snake_case sem acentos."""
    # Normaliza para ASCII
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Minúsculas
    texto = texto.lower()
    # Substitui espaços e hífen por underscore
    texto = re.sub(r"[\s\-]+", "_", texto)
    # Remove caracteres não alfanuméricos (exceto underscore)
    texto = re.sub(r"[^a-z0-9_]", "", texto)
    # Remove underscores múltiplos
    texto = re.sub(r"_+", "_", texto).strip("_")
    return texto


def _agrupar_blocos_em_chunks(
    blocos: list[Bloco],
    max_palavras: int = MAX_PALAVRAS_POR_CHUNK,
) -> list[tuple[str, list[Bloco]]]:
    """
    Agrupa blocos em chunks que não excedam max_palavras.
    Retorna lista de (texto_chunk, blocos_incluidos).
    """
    chunks: list[tuple[str, list[Bloco]]] = []
    chunk_atual: list[Bloco] = []
    palavras_atual = 0

    for bloco in blocos:
        if bloco.palavras < MIN_PALAVRAS_BLOCO:
            continue  # Ignora blocos muito pequenos

        # Se adicionar este bloco excede o limite, fecha o chunk atual
        if palavras_atual + bloco.palavras > max_palavras and chunk_atual:
            texto = "\n\n".join(f"### {b.titulo}\n{b.texto}" for b in chunk_atual)
            chunks.append((texto, chunk_atual))
            chunk_atual = []
            palavras_atual = 0

        chunk_atual.append(bloco)
        palavras_atual += bloco.palavras

    # Fecha o último chunk
    if chunk_atual:
        texto = "\n\n".join(f"### {b.titulo}\n{b.texto}" for b in chunk_atual)
        chunks.append((texto, chunk_atual))

    return chunks


def _parsear_conceitos_json(json_str: str, blocos_origem: list[Bloco]) -> list[Conceito]:
    """Converte o JSON retornado pelo LLM em lista de Conceito."""
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"[ConceptExtractor] Erro ao parsear JSON: {e}")
        return []

    conceitos_raw = data.get("conceitos", [])
    if not isinstance(conceitos_raw, list):
        logger.warning("[ConceptExtractor] 'conceitos' não é uma lista")
        return []

    complexidade_map = {
        "baixa": Complexidade.BAIXA,
        "media": Complexidade.MEDIA,
        "alta": Complexidade.ALTA,
        "critica": Complexidade.CRITICA,
    }

    bloco_id_ref = blocos_origem[0].id if blocos_origem else ""
    conceitos: list[Conceito] = []

    for raw in conceitos_raw:
        if not isinstance(raw, dict):
            continue

        nome = raw.get("nome", "").strip()
        if not nome:
            continue

        # Garante que o ID é válido
        id_raw = raw.get("id", "")
        if not id_raw or not re.match(r"^[a-z][a-z0-9_]*$", id_raw):
            id_raw = _slug(nome)

        complexidade_str = raw.get("complexidade", "media").lower().strip()
        complexidade = complexidade_map.get(complexidade_str, Complexidade.MEDIA)

        conceito = Conceito(
            id=id_raw,
            nome=nome,
            descricao=raw.get("descricao", "").strip(),
            complexidade=complexidade,
            dependencias=[
                d for d in raw.get("dependencias", [])
                if isinstance(d, str) and d
            ],
            keywords=[
                k.lower().strip()
                for k in raw.get("keywords", [])
                if isinstance(k, str) and k
            ],
            bloco_origem_id=bloco_id_ref,
            tem_codigo=bool(raw.get("tem_codigo", False)),
            tem_formula=bool(raw.get("tem_formula", False)),
            subconcepts_count=int(raw.get("subconcepts_count", 0)),
            paragrafos_estimados=int(raw.get("paragrafos_estimados", 1)),
        )
        conceitos.append(conceito)

    return conceitos


def _deduplicar_conceitos(
    todos_conceitos: list[Conceito],
    titulo_documento: str,
) -> list[Conceito]:
    """
    Remove conceitos duplicados via LLM quando há mais de 15 conceitos.
    Para menos de 15, faz deduplicação simples por ID.
    """
    # Dedup simples por ID (mantém o primeiro encontrado)
    seen_ids: dict[str, Conceito] = {}
    for c in todos_conceitos:
        if c.id not in seen_ids:
            seen_ids[c.id] = c
        else:
            # Mantém o que tem descrição mais completa
            existente = seen_ids[c.id]
            if len(c.descricao) > len(existente.descricao):
                seen_ids[c.id] = c

    sem_dup_basico = list(seen_ids.values())

    # Se poucos conceitos, não precisa de LLM para dedup
    if len(sem_dup_basico) <= 15:
        return sem_dup_basico

    # Dedup semântico via LLM
    logger.info(
        f"[ConceptExtractor] Deduplicando {len(sem_dup_basico)} conceitos via LLM..."
    )

    lista_simples = [
        {"id": c.id, "nome": c.nome, "descricao": c.descricao,
         "complexidade": c.complexidade.value,
         "dependencias": c.dependencias, "keywords": c.keywords,
         "tem_codigo": c.tem_codigo, "tem_formula": c.tem_formula,
         "subconcepts_count": c.subconcepts_count,
         "paragrafos_estimados": c.paragrafos_estimados}
        for c in sem_dup_basico
    ]

    prompt = _PROMPT_DEDUP.format(
        lista_conceitos=json.dumps(lista_simples, ensure_ascii=False, indent=2)
    )

    try:
        resposta = chamar_llm(
            system_prompt=SYSTEM_PROMPT_EXTRATOR,
            user_prompt=prompt,
            esperar_json=True,
            temperature_override=0.2,  # Baixa temperatura para tarefa analítica
        )
        conceitos_dedup = _parsear_conceitos_json(resposta.texto, [])
        if conceitos_dedup:
            logger.info(
                f"[ConceptExtractor] Após dedup: "
                f"{len(sem_dup_basico)} → {len(conceitos_dedup)} conceitos"
            )
            return conceitos_dedup
    except Exception as e:
        logger.warning(f"[ConceptExtractor] Dedup LLM falhou: {e}. Usando dedup simples.")

    return sem_dup_basico


def _validar_dependencias(conceitos: list[Conceito]) -> list[Conceito]:
    """
    Garante que todas as dependências referenciam IDs existentes.
    Remove referências a IDs inexistentes.
    Remove dependências circulares simples.
    """
    ids_validos = {c.id for c in conceitos}

    for conceito in conceitos:
        # Remove deps para IDs que não existem
        deps_validas = [d for d in conceito.dependencias if d in ids_validos and d != conceito.id]
        conceito.dependencias = deps_validas

    # Detecta e remove ciclos (A→B→A)
    for conceito in conceitos:
        deps_sem_ciclo = []
        for dep_id in conceito.dependencias:
            dep = next((c for c in conceitos if c.id == dep_id), None)
            if dep and conceito.id in dep.dependencias:
                # Ciclo detectado: remove a dependência do conceito de menor complexidade
                logger.warning(
                    f"[ConceptExtractor] Ciclo detectado: "
                    f"{conceito.id} ↔ {dep_id}. Removendo do menos complexo."
                )
                ordem = [Complexidade.BAIXA, Complexidade.MEDIA, Complexidade.ALTA, Complexidade.CRITICA]
                if ordem.index(conceito.complexidade) <= ordem.index(dep.complexidade):
                    continue  # Não adiciona esta dep (remove do mais simples)
            deps_sem_ciclo.append(dep_id)
        conceito.dependencias = deps_sem_ciclo

    return conceitos


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def extrair_conceitos(
    documento: DocumentoEstruturado,
) -> ResultadoExtracaoConceitos:
    """
    Extrai todos os conceitos pedagógicos do documento via LLM.

    Estratégia:
    1. Divide os blocos em chunks de MAX_PALAVRAS_POR_CHUNK palavras
    2. Chama o LLM para cada chunk
    3. Coleta todos os conceitos
    4. Deduplicação (simples + semântica se necessário)
    5. Valida dependências

    Args:
        documento: DocumentoEstruturado produzido por extractor.py

    Returns:
        ResultadoExtracaoConceitos com lista completa e metadados.
    """
    logger.info(
        f"[ConceptExtractor] Iniciando extração para: {documento.titulo_documento}"
    )

    blocos_validos = [b for b in documento.blocos if b.palavras >= MIN_PALAVRAS_BLOCO]
    if not blocos_validos:
        logger.warning("[ConceptExtractor] Nenhum bloco com palavras suficientes encontrado.")
        return ResultadoExtracaoConceitos(
            conceitos=[],
            total_conceitos=0,
            api_usada="none",
            aviso="Documento sem blocos de conteúdo suficiente para extração.",
        )

    chunks = _agrupar_blocos_em_chunks(blocos_validos)
    logger.info(f"[ConceptExtractor] {len(blocos_validos)} blocos → {len(chunks)} chunks para LLM")

    todos_conceitos: list[Conceito] = []
    api_usada = "GLM-5"
    tokens_total = 0

    for idx, (texto_chunk, blocos_chunk) in enumerate(chunks):
        logger.info(f"[ConceptExtractor] Processando chunk {idx + 1}/{len(chunks)}...")

        prompt = _PROMPT_EXTRATOR_TEMPLATE.format(
            titulo=documento.titulo_documento,
            texto=texto_chunk,
        )

        try:
            resposta = chamar_llm(
                system_prompt=SYSTEM_PROMPT_EXTRATOR,
                user_prompt=prompt,
                esperar_json=True,
                temperature_override=0.3,  # Baixa para extração precisa
            )

            conceitos_chunk = _parsear_conceitos_json(resposta.texto, blocos_chunk)
            todos_conceitos.extend(conceitos_chunk)
            api_usada = resposta.api_nome
            tokens_total += resposta.tokens_estimados

            logger.info(
                f"[ConceptExtractor] Chunk {idx + 1}: "
                f"{len(conceitos_chunk)} conceitos extraídos via {resposta.api_nome}"
            )

        except Exception as e:
            logger.error(f"[ConceptExtractor] Erro no chunk {idx + 1}: {e}")
            # Continua com os outros chunks

    if not todos_conceitos:
        return ResultadoExtracaoConceitos(
            conceitos=[],
            total_conceitos=0,
            api_usada=api_usada,
            tokens_usados=tokens_total,
            aviso="Nenhum conceito extraído. Verifique o conteúdo do documento.",
        )

    # Deduplicação
    conceitos_dedup = _deduplicar_conceitos(todos_conceitos, documento.titulo_documento)

    # Validação de dependências
    conceitos_validos = _validar_dependencias(conceitos_dedup)

    logger.info(
        f"[ConceptExtractor] ✅ Extração concluída: "
        f"{len(todos_conceitos)} brutos → {len(conceitos_validos)} únicos válidos"
    )

    return ResultadoExtracaoConceitos(
        conceitos=conceitos_validos,
        total_conceitos=len(conceitos_validos),
        api_usada=api_usada,
        tokens_usados=tokens_total,
    )
