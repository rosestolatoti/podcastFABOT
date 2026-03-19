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
        text = clean_extracted_text(text)

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
        combined_text = clean_extracted_text(combined_text)

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


def clean_extracted_text(text: str) -> str:
    """
    Limpa e formata o texto extraído.
    """
    if not text:
        return ""

    # Remover linhas em branco excessivas
    lines = text.split("\n")
    cleaned_lines = []
    prev_empty = False

    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned_lines.append(stripped)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append("")
            prev_empty = True

    # Remover espaços duplos
    text = "\n".join(cleaned_lines)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

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
