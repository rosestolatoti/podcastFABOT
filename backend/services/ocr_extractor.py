"""
FABOT Podcast Studio — OCR Extractor
Extrai texto de imagens (JPG, PNG) e PDFs usando pytesseract e pdfplumber
"""

import re
from pathlib import Path
from PIL import Image
import pytesseract
import pdfplumber
import logging

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf"}


def extract_text_from_image(image_path: Path, language: str = "por+eng") -> dict:
    """
    Extrai texto de uma imagem usando pytesseract.

    Args:
        image_path: Caminho para a imagem
        language: Idiomas para OCR (default: português + inglês)

    Returns:
        dict com 'text' e 'confidence'
    """
    try:
        img = Image.open(image_path)

        # Converter para RGB se necessário
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Extrair texto com confiança
        data = pytesseract.image_to_data(
            img, lang=language, output_type=pytesseract.Output.DICT
        )

        # Extrair apenas o texto
        text = pytesseract.image_to_string(img, lang=language)

        # Calcular confiança média
        confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Limpar texto
        text = clean_extracted_text(text, is_pdf=False)

        return {
            "text": text,
            "confidence": round(avg_confidence, 1),
            "language_detected": detect_language_preview(text),
            "char_count": len(text),
            "word_count": len(text.split()),
        }

    except Exception as e:
        logger.error(f"Erro ao extrair texto da imagem {image_path}: {e}")
        return {
            "text": "",
            "error": str(e),
            "confidence": 0,
            "char_count": 0,
            "word_count": 0,
        }


def extract_text_from_pdf(pdf_path: Path) -> dict:
    """
    Extrai texto de todas as páginas de um PDF usando pdfplumber.

    Args:
        pdf_path: Caminho para o arquivo PDF

    Returns:
        dict com 'text' e metadata
    """
    try:
        full_text = []
        page_count = 0

        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    full_text.append(f"--- Página {i + 1} ---\n{text}")

        combined_text = "\n\n".join(full_text)
        combined_text = clean_extracted_text(combined_text, is_pdf=True)

        return {
            "text": combined_text,
            "page_count": page_count,
            "char_count": len(combined_text),
            "word_count": len(combined_text.split()),
        }

    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF {pdf_path}: {e}")
        return {
            "text": "",
            "error": str(e),
            "page_count": 0,
            "char_count": 0,
            "word_count": 0,
        }


def clean_extracted_text(text: str, is_pdf: bool = False) -> str:
    """
    Limpa e formata o texto extraído.

    Args:
        text: Texto extraído
        is_pdf: Se True, aplica limpeza específica para PDFs
    """
    if not text:
        return ""

    # Remover marcadores de página do PDF
    text = re.sub(r"--- Página \d+ ---", "", text)

    # Padrões OCR comuns (letras duplicadas/espaçadas como "E E d d e l l w e i s s")
    text = re.sub(
        r"\b([A-Za-z])\s+\1{1,}\s*", r"\1\1", text
    )  # Letras duplicadas com espaço
    text = re.sub(
        r"\b([A-Za-z])\1{2,}", r"\1\1", text
    )  # Mais de 2 letras iguais seguidas

    # Remover linhas de rodapé/número de página sozinhas
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        # Pular linhas que são apenas números de página ou códigos ISBN
        if re.match(r"^ISBN\s*\d", stripped, re.IGNORECASE):
            continue
        if re.match(r"^Ed\.?\s*$", stripped, re.IGNORECASE):
            continue
        if re.match(r"^(www\.|http)", stripped, re.IGNORECASE):
            continue
        if re.match(r"^crb\s*\d+", stripped, re.IGNORECASE):
            continue
        if re.match(r"^cdd\s*\d", stripped, re.IGNORECASE):
            continue

        # Pular linhas muito curtas que parecem ser artefatos OCR
        if (
            len(stripped) <= 3
            and stripped.isupper()
            and not any(c.isdigit() for c in stripped)
        ):
            continue

        cleaned_lines.append(stripped)

    # Remover espaços duplos
    text = "\n".join(cleaned_lines)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remover espaços antes de pontuação
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)

    return text.strip()


def detect_language_preview(text: str) -> str:
    """
    Detecta idioma predominante no texto (heurística simples).
    """
    if not text:
        return "desconhecido"

    # Contar palavras comuns
    text_lower = text.lower()

    pt_count = sum(
        1
        for word in [
            "de",
            "a",
            "o",
            "que",
            "e",
            "do",
            "da",
            "em",
            "para",
            "com",
            "não",
            "uma",
            "um",
        ]
        if word in text_lower
    )
    en_count = sum(
        1
        for word in [
            "the",
            "and",
            "is",
            "of",
            "to",
            "in",
            "it",
            "you",
            "that",
            "for",
            "on",
            "with",
        ]
        if word in text_lower
    )

    if pt_count > en_count:
        return "português"
    elif en_count > pt_count:
        return "inglês"
    else:
        return "português (provável)"


def get_file_type(filename: str) -> str:
    """
    Retorna o tipo de arquivo baseado na extensão.
    """
    ext = Path(filename).suffix.lower()

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in SUPPORTED_DOCUMENT_EXTENSIONS:
        return "pdf"
    else:
        return "unknown"
