"""
extractor.py — Extração estrutural de documentos (PDF, TXT, DOCX).

Responsabilidades:
  - Ler o arquivo e extrair texto limpo
  - Identificar capítulos, seções e subseções
  - Contar palavras, parágrafos, detectar código e fórmulas
  - Retornar DocumentoEstruturado com blocos organizados

NÃO faz:
  - Interpretação semântica (responsabilidade de concept_extractor.py)
  - Chamadas a LLM
  - Decisões sobre episódios

Dependências opcionais (instala o que estiver disponível):
  - pdfplumber  (melhor para PDFs com texto)
  - pypdf        (fallback para PDFs simples)
  - python-docx  (para .docx)

Sem nenhuma dessas: lê como texto puro.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from pathlib import Path

from models import Bloco, DocumentoEstruturado

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# PADRÕES DE DETECÇÃO
# ═══════════════════════════════════════════════════════════════

# Padrões que indicam início de capítulo
_PADROES_CAPITULO = [
    re.compile(r"^cap[íi]tulo\s+\d+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^chapter\s+\d+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\d+\.\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]{4,}", re.MULTILINE),
    re.compile(r"^UNIDADE\s+\d+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^MÓDULO\s+\d+", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^PARTE\s+\d+", re.IGNORECASE | re.MULTILINE),
]

# Padrões que indicam início de seção
_PADROES_SECAO = [
    re.compile(r"^\d+\.\d+\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", re.MULTILINE),
    re.compile(r"^[a-z]\)\s+[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", re.MULTILINE),
    re.compile(r"^Objetivos de aprendizagem", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Introdução\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Conceitos? básicos?", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Aplicaç", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Exemplos?\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Exerc[íi]cios?\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^Referências?\b", re.IGNORECASE | re.MULTILINE),
]

# Palavras-chave que indicam bloco de código
_PALAVRAS_CODIGO = {
    "def ", "class ", "import ", "from ", "return ", "if __name__",
    "for ", "while ", "print(", "input(", "==>", ">>>", "void ",
    "int ", "float ", "String ", "public ", "private ",
    "procedure", "begin", "end;", "writeln", "readln",
    "printf(", "scanf(", "cout <<", "#include",
    "para ", " faça", " incr ", " até ", "escrever(", "ler(",  # pseudocódigo
    "Constante:", "Variável:", "Variáveis:", "algoritmo",
}

# Símbolos que indicam fórmula matemática
_SIMBOLOS_FORMULA = {
    "∑", "∫", "√", "∂", "∞", "≤", "≥", "≠", "≈", "π", "μ", "σ", "α", "β",
    "Σ", "Π", "Δ", "∈", "∉", "⊂", "⊃", "∪", "∩",
}
_REGEX_FORMULA = re.compile(r"[=+\-*/^]{2,}|[a-zA-Z]\^[0-9]|\b[a-z]\d\b|_{[^}]+}")

# Frases que indicam exemplos didáticos
_PALAVRAS_EXEMPLO = re.compile(
    r"\b(por exemplo|exemplo:|ex\.|exemplo\s+\d+|figura\s+\d+|quadro\s+\d+|vejamos)\b",
    re.IGNORECASE,
)

# Texto que deve ser removido (metadados de PDF, cabeçalhos)
_LIXO_PDF = re.compile(
    r"(Edelweiss_\d+\.indd|delweiss_\d+\.indd|\d{2}/\d{2}/\d{1,2}|"
    r"Encerra aqui o trecho|Biblioteca Virtual|Unidade de Aprendizagem|"
    r"Conteúdo:|SOLUÇÕES\s+EDUCACIONAIS|www\.\S+\.(br|com|org))",
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES DE LIMPEZA
# ═══════════════════════════════════════════════════════════════

def _limpar_texto(texto: str) -> str:
    """
    Remove artefatos de extração de PDF: hifenização quebrada,
    espaços duplos, linhas de metadados, caracteres de controle.
    """
    # Normaliza unicode (NFC)
    texto = unicodedata.normalize("NFC", texto)

    # Remove linhas de metadados do PDF
    linhas = texto.split("\n")
    linhas_limpas = []
    for linha in linhas:
        linha_stripped = linha.strip()
        if not linha_stripped:
            linhas_limpas.append("")
            continue
        # Filtra metadados
        if _LIXO_PDF.search(linha_stripped):
            continue
        # Filtra linhas que são só números de página
        if re.match(r"^\d{1,3}$", linha_stripped):
            continue
        # Filtra linhas muito curtas que são provavelmente cabeçalhos de página
        if len(linha_stripped) < 4 and not linha_stripped.endswith("."):
            continue
        linhas_limpas.append(linha)

    texto = "\n".join(linhas_limpas)

    # Junta palavras hifenizadas no final de linha: "algo-\nritmo" → "algoritmo"
    texto = re.sub(r"-\n([a-záàâãéêíóôõúça-z])", r"\1", texto)

    # Múltiplos espaços → um espaço
    texto = re.sub(r"[ \t]+", " ", texto)

    # Mais de 2 quebras de linha → 2
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    return texto.strip()


def _contar_palavras(texto: str) -> int:
    return len(texto.split())


def _detectar_codigo(texto: str) -> bool:
    texto_lower = texto.lower()
    return any(kw.lower() in texto_lower for kw in _PALAVRAS_CODIGO)


def _detectar_formula(texto: str) -> bool:
    if any(s in texto for s in _SIMBOLOS_FORMULA):
        return True
    if _REGEX_FORMULA.search(texto):
        return True
    return False


def _detectar_exemplos(texto: str) -> bool:
    return bool(_PALAVRAS_EXEMPLO.search(texto))


# ═══════════════════════════════════════════════════════════════
# LEITURA DE ARQUIVOS
# ═══════════════════════════════════════════════════════════════

def _ler_pdf(caminho: Path) -> tuple[str, int]:
    """Retorna (texto_limpo, total_paginas). Tenta pdfplumber → pypdf."""
    try:
        import pdfplumber
        texto_paginas = []
        with pdfplumber.open(caminho) as pdf:
            total = len(pdf.pages)
            for pagina in pdf.pages:
                t = pagina.extract_text() or ""
                texto_paginas.append(t)
        return "\n\n".join(texto_paginas), total
    except ImportError:
        pass

    try:
        from pypdf import PdfReader
        reader = PdfReader(caminho)
        total = len(reader.pages)
        partes = []
        for pagina in reader.pages:
            partes.append(pagina.extract_text() or "")
        return "\n\n".join(partes), total
    except ImportError:
        pass

    # Último fallback: lê como bytes e decodifica o que der
    logger.warning(
        "pdfplumber e pypdf não instalados. Lendo PDF como texto raw. "
        "Instale: pip install pdfplumber"
    )
    conteudo = caminho.read_bytes()
    texto = conteudo.decode("utf-8", errors="replace")
    # Extrai texto entre streams de PDF de forma rudimentar
    matches = re.findall(r"BT\s*(.*?)\s*ET", texto, re.DOTALL)
    texto_extraido = " ".join(matches) if matches else texto
    return texto_extraido, 1


def _ler_docx(caminho: Path) -> tuple[str, int]:
    """Retorna (texto_limpo, total_paginas_estimado)."""
    try:
        from docx import Document
        doc = Document(caminho)
        paragrafos = [p.text for p in doc.paragraphs]
        texto = "\n".join(paragrafos)
        paginas_estimadas = max(1, len(texto.split()) // 300)
        return texto, paginas_estimadas
    except ImportError:
        raise ImportError(
            "python-docx não instalado. Execute: pip install python-docx"
        )


def _ler_txt(caminho: Path) -> tuple[str, int]:
    """Lê arquivo de texto simples."""
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            texto = caminho.read_text(encoding=enc)
            palavras = len(texto.split())
            paginas_estimadas = max(1, palavras // 300)
            return texto, paginas_estimadas
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não foi possível decodificar o arquivo: {caminho}")


# ═══════════════════════════════════════════════════════════════
# SEGMENTAÇÃO EM BLOCOS
# ═══════════════════════════════════════════════════════════════

def _segmentar_blocos(texto_limpo: str, titulo_documento: str) -> list[Bloco]:
    """
    Divide o texto limpo em blocos estruturais (capítulos, seções, subseções).

    Estratégia:
    1. Detecta linhas que são títulos de seção pelos padrões regex
    2. Acumula texto entre títulos
    3. Cria um Bloco para cada segmento
    """
    linhas = texto_limpo.split("\n")
    blocos: list[Bloco] = []
    bloco_atual_titulo = titulo_documento
    bloco_atual_nivel = 1
    bloco_atual_linhas: list[str] = []
    bloco_contador = 0

    def _finalizar_bloco():
        nonlocal bloco_contador
        if not bloco_atual_linhas:
            return
        texto_bloco = "\n".join(bloco_atual_linhas).strip()
        if not texto_bloco or len(texto_bloco.split()) < 10:
            return  # Ignora blocos muito pequenos (provavelmente só título)

        bloco_contador += 1
        bloco = Bloco(
            id=f"bloco_{bloco_contador:03d}",
            nivel=bloco_atual_nivel,
            titulo=bloco_atual_titulo,
            texto=texto_bloco,
            palavras=_contar_palavras(texto_bloco),
            paragrafos=texto_bloco.count("\n\n") + 1,
            tem_codigo=_detectar_codigo(texto_bloco),
            tem_formula=_detectar_formula(texto_bloco),
            tem_exemplos=_detectar_exemplos(texto_bloco),
        )
        blocos.append(bloco)

    for linha in linhas:
        linha_stripped = linha.strip()

        # Verifica se é um título de capítulo (nível 1)
        eh_capitulo = any(p.match(linha_stripped) for p in _PADROES_CAPITULO)

        # Verifica se é um título de seção (nível 2)
        eh_secao = (
            not eh_capitulo
            and any(p.match(linha_stripped) for p in _PADROES_SECAO)
            and len(linha_stripped) > 5
            and len(linha_stripped) < 100  # Evita linhas longas como sendo títulos
        )

        if eh_capitulo or eh_secao:
            _finalizar_bloco()
            bloco_atual_titulo = linha_stripped
            bloco_atual_nivel = 1 if eh_capitulo else 2
            bloco_atual_linhas = []
        else:
            bloco_atual_linhas.append(linha)

    # Finaliza último bloco
    _finalizar_bloco()

    # Se não encontrou nenhum bloco estruturado, trata o texto inteiro como 1 bloco
    if not blocos:
        logger.warning(
            "Nenhuma estrutura de capítulo/seção detectada. "
            "Tratando documento como bloco único."
        )
        palavras = _contar_palavras(texto_limpo)
        blocos.append(Bloco(
            id="bloco_001",
            nivel=1,
            titulo=titulo_documento,
            texto=texto_limpo,
            palavras=palavras,
            paragrafos=texto_limpo.count("\n\n") + 1,
            tem_codigo=_detectar_codigo(texto_limpo),
            tem_formula=_detectar_formula(texto_limpo),
            tem_exemplos=_detectar_exemplos(texto_limpo),
        ))

    return blocos


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def extrair_documento(
    caminho_arquivo: str,
    titulo_override: str = "",
) -> DocumentoEstruturado:
    """
    Lê um arquivo (PDF, DOCX, TXT) e retorna DocumentoEstruturado.

    Args:
        caminho_arquivo: Caminho absoluto ou relativo do arquivo.
        titulo_override: Se fornecido, usa este título em vez de tentar extrair do arquivo.

    Returns:
        DocumentoEstruturado com blocos, contagens e texto completo.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se a extensão não for suportada.
    """
    caminho = Path(caminho_arquivo).resolve()
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    extensao = caminho.suffix.lower()
    logger.info(f"[Extractor] Lendo {extensao.upper()}: {caminho.name}")

    # Leitura por tipo
    if extensao == ".pdf":
        texto_raw, total_paginas = _ler_pdf(caminho)
    elif extensao in (".docx", ".doc"):
        texto_raw, total_paginas = _ler_docx(caminho)
    elif extensao in (".txt", ".md"):
        texto_raw, total_paginas = _ler_txt(caminho)
    else:
        raise ValueError(
            f"Extensão '{extensao}' não suportada. Use: .pdf, .docx, .txt, .md"
        )

    # Limpeza
    texto_limpo = _limpar_texto(texto_raw)

    # Título do documento
    titulo = titulo_override or caminho.stem.replace("_", " ").title()

    # Segmentação em blocos
    blocos = _segmentar_blocos(texto_limpo, titulo)

    # Estatísticas
    total_palavras = sum(b.palavras for b in blocos)

    doc = DocumentoEstruturado(
        titulo_documento=titulo,
        fonte=str(caminho),
        total_palavras=total_palavras,
        total_paginas=total_paginas,
        blocos=blocos,
        texto_completo=texto_limpo,
        metadados={
            "extensao": extensao,
            "total_blocos": len(blocos),
            "blocos_com_codigo": sum(1 for b in blocos if b.tem_codigo),
            "blocos_com_formula": sum(1 for b in blocos if b.tem_formula),
            "blocos_com_exemplos": sum(1 for b in blocos if b.tem_exemplos),
        },
    )

    logger.info(
        f"[Extractor] ✅ {titulo}: "
        f"{total_palavras} palavras | "
        f"{len(blocos)} blocos | "
        f"{total_paginas} páginas"
    )

    return doc
