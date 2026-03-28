"""
models.py — Tipos de dados compartilhados entre todos os módulos do FABOT Planner.

Usa dataclasses puras (sem dependência extra além do Python 3.10+).
Todos os módulos importam daqui. Nunca criam suas próprias estruturas.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════

class Complexidade(str, Enum):
    """Nível de complexidade pedagógica de um conceito."""
    BAIXA   = "baixa"    # Definição simples, sem pré-requisitos
    MEDIA   = "media"    # Requer 1-2 conceitos anteriores
    ALTA    = "alta"     # Requer cadeia longa, tem código ou fórmula
    CRITICA = "critica"  # Conceito central do livro, sem ele o resto não faz sentido


class StatusPipeline(str, Enum):
    """Estado atual do pipeline de geração."""
    PENDENTE          = "pendente"
    EXTRACAO_OK       = "extracao_ok"
    CONCEITOS_OK      = "conceitos_ok"
    PLANO_OK          = "plano_ok"
    COBERTURA_OK      = "cobertura_ok"
    BIBLE_OK          = "bible_ok"
    GERANDO           = "gerando"
    CONCLUIDO         = "concluido"
    ERRO              = "erro"


class DepthLevel(str, Enum):
    """Profundidade de geração do roteiro (compatível com script_template_v7)."""
    QUICK    = "quick"    # Pontos fundamentais — mín 5 segs/conceito
    STANDARD = "standard" # Pontos principais — mín 8 segs/conceito
    DETAILED = "detailed" # Modo ensino completo — mín 10 segs/conceito


# ═══════════════════════════════════════════════════════════════
# EXTRAÇÃO ESTRUTURAL
# ═══════════════════════════════════════════════════════════════

@dataclass
class Bloco:
    """
    Unidade estrutural extraída do documento original.
    Um bloco pode ser um capítulo, seção ou subseção.
    """
    id: str                          # Ex: "cap3_sec2_sub1"
    nivel: int                       # 1=capítulo, 2=seção, 3=subseção
    titulo: str
    texto: str                       # Conteúdo bruto limpo
    palavras: int                    # Contagem real
    paragrafos: int
    tem_codigo: bool = False         # Detectado por indentação ou palavras-chave
    tem_formula: bool = False        # Detectado por símbolos matemáticos
    tem_exemplos: bool = False       # "por exemplo", "exemplo:", "ex:"
    pagina_inicio: Optional[int] = None
    pagina_fim: Optional[int] = None


@dataclass
class DocumentoEstruturado:
    """
    Resultado completo da extração estrutural de um documento.
    Produzido por extractor.py.
    """
    titulo_documento: str
    fonte: str                       # Caminho do arquivo original
    total_palavras: int
    total_paginas: int
    blocos: list[Bloco] = field(default_factory=list)
    texto_completo: str = ""         # Texto limpo concatenado (para LLM)
    metadados: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# CONCEITOS
# ═══════════════════════════════════════════════════════════════

@dataclass
class Conceito:
    """
    Unidade de conhecimento extraída pelo LLM a partir do documento.
    Cada conceito terá pelo menos 1 episódio que o cobre.
    """
    id: str                                  # Slug único: "variavel_inteira"
    nome: str                                # Nome humano: "Variável inteira"
    descricao: str                           # 1-2 frases do que é
    complexidade: Complexidade
    dependencias: list[str] = field(default_factory=list)  # IDs de outros conceitos
    keywords: list[str] = field(default_factory=list)
    bloco_origem_id: str = ""               # De qual bloco do documento veio
    tem_codigo: bool = False
    tem_formula: bool = False
    subconcepts_count: int = 0              # Quantos subconceitos tem
    paragrafos_estimados: int = 0           # Estimativa de parágrafo no texto

    # Calculados por decisor.py — não preencher manualmente
    score_complexidade: float = 0.0
    segmentos_necessarios: int = 0
    episodio_alocado: Optional[int] = None  # Preenchido pelo grouper.py


@dataclass
class ResultadoExtracaoConceitos:
    """
    Resultado completo de concept_extractor.py.
    Contém a lista de conceitos e metadados da extração.
    """
    conceitos: list[Conceito]
    total_conceitos: int
    api_usada: str
    tokens_usados: int = 0
    aviso: str = ""                          # Warnings do LLM


# ═══════════════════════════════════════════════════════════════
# PLANO DE EPISÓDIOS
# ═══════════════════════════════════════════════════════════════

@dataclass
class EpisodioPlano:
    """
    Plano de um episódio antes da geração do roteiro.
    Produzido por grouper.py e validado por coverage_check.py.
    """
    numero: int
    titulo_sugerido: str
    conceitos: list[str]             # IDs dos conceitos que este episódio cobre
    depth_level: DepthLevel
    palavras_estimadas: int
    segmentos_estimados: int
    dependencias_satisfeitas: list[str] = field(default_factory=list)  # Conceitos cobertos em eps anteriores
    conceitos_preparar: list[str] = field(default_factory=list)       # Conceitos que o próximo ep vai usar
    chunk_texto: str = ""            # Trecho do documento referente a este episódio
    notas_gerador: str = ""          # Instrução extra para o generator.py


@dataclass
class PlanoCompleto:
    """
    Plano validado de todos os episódios de um documento.
    Só é produzido depois que coverage_check.py confirma 100%.
    """
    documento_titulo: str
    total_episodios: int
    total_conceitos: int
    episodios: list[EpisodioPlano]
    cobertura_percentual: float      # Deve ser 100.0
    criado_em: str                   # ISO timestamp


# ═══════════════════════════════════════════════════════════════
# CONTENT BIBLE
# ═══════════════════════════════════════════════════════════════

@dataclass
class ContentBible:
    """
    Documento de referência gerado uma vez por livro.
    Acompanha TODA chamada ao generator.py para garantir consistência.
    """
    documento_titulo: str
    glossario: dict[str, str]        # termo → definição curta
    estilo_tom: str                  # Descrição do tom do livro
    exemplos_do_livro: list[str]     # Exemplos reais que devem aparecer nos roteiros
    conceitos_centrais: list[str]    # Os 5-7 conceitos mais importantes
    o_que_nao_fazer: list[str]       # Erros comuns de interpretação deste livro
    nivel_audiencia: str             # "iniciante", "intermediário", "avançado"
    area_conhecimento: str           # "programação", "estatística", "comunicação"


# ═══════════════════════════════════════════════════════════════
# GERAÇÃO E VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════

@dataclass
class Segmento:
    """Um segmento de fala do roteiro (compatível com script_template_v7)."""
    speaker: str                     # "NARRADOR", "WILLIAM", "CRISTINA"
    text: str
    emotion: str = "neutral"
    pause_after_ms: int = 600
    block_transition: bool = False


@dataclass
class Episodio:
    """Roteiro gerado de um episódio."""
    numero: int
    title: str
    episode_summary: str
    keywords: list[str]
    segments: list[Segmento]
    api_usada: str = ""
    tokens_usados: int = 0
    tentativas: int = 1


@dataclass
class ResultadoValidacao:
    """Resultado da validação de um episódio gerado."""
    valido: bool
    episodio_numero: int
    total_segmentos: int
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    conceitos_cobertos: list[str] = field(default_factory=list)
    conceitos_faltando: list[str] = field(default_factory=list)
    falante_mais_longo_palavras: int = 0
    tem_codigo_literal: bool = False


# ═══════════════════════════════════════════════════════════════
# ESTADO DO PIPELINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class EstadoPipeline:
    """
    Estado completo do pipeline, salvo em JSON após cada etapa.
    Permite retomar de onde parou sem repetir trabalho.
    """
    job_id: str
    documento_fonte: str
    status: StatusPipeline
    criado_em: str
    atualizado_em: str

    # Preenchidos progressivamente
    documento: Optional[DocumentoEstruturado] = None
    conceitos: Optional[list[Conceito]] = None
    plano: Optional[PlanoCompleto] = None
    bible: Optional[ContentBible] = None
    episodios_gerados: list[Episodio] = field(default_factory=list)
    validacoes: list[ResultadoValidacao] = field(default_factory=list)

    # Controle de erros
    erros: list[str] = field(default_factory=list)
    ultimo_erro: str = ""
