"""
YouTube Transcript Extractor
Extrai legendas/transcrições de vídeos do YouTube.
"""

import re
import logging
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
    VideoUnplayable,
)

logger = logging.getLogger(__name__)


def get_video_id(url: str) -> str:
    """Extrai ID do vídeo da URL do YouTube."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if len(url) == 11 and re.match(r"^[a-zA-Z0-9_-]{11}$", url):
        return url

    raise ValueError(f"URL do YouTube inválida: {url}")


def get_video_title(video_id: str) -> str:
    """Obtém o título do vídeo via API do YouTube."""
    try:
        import requests

        response = requests.get(
            f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={video_id}",
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("title", "Vídeo sem título")
    except Exception:
        pass
    return "Vídeo sem título"


def list_available_transcripts(video_id: str) -> list:
    """Lista transcrições disponíveis para o vídeo."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        transcripts = []
        for transcript in transcript_list:
            transcripts.append(
                {
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "is_translatable": transcript.is_translatable,
                }
            )

        return transcripts
    except Exception as e:
        logger.warning(f"Erro ao listar transcrições: {e}")
        return []


def transcrever_video(
    video_url: str,
    idiomas_preferidos: list = None,
) -> dict:
    """
    Transcreve vídeo do YouTube.

    Args:
        video_url: URL do vídeo do YouTube
        idiomas_preferidos: Lista de códigos de idioma em ordem de preferência

    Returns:
        dict com sucesso, texto e metadados
    """
    if idiomas_preferidos is None:
        idiomas_preferidos = ["pt", "pt-BR", "en", "en-US"]

    try:
        video_id = get_video_id(video_url)
        logger.info(f"Transcrevendo vídeo: {video_id}")

        title = get_video_title(video_id)

        api = YouTubeTranscriptApi()

        transcript = api.fetch(
            video_id=video_id,
            languages=idiomas_preferidos,
        )

        snippets = list(transcript.snippets)

        texto_completo = " ".join([s.text for s in snippets])

        duracao_segundos = (
            max(s.start + s.duration for s in snippets) if snippets else 0
        )

        resultado = {
            "sucesso": True,
            "video_id": video_id,
            "titulo": title,
            "texto_completo": texto_completo,
            "num_palavras": len(texto_completo.split()),
            "num_caracteres": len(texto_completo),
            "num_segmentos": len(snippets),
            "duracao_segundos": duracao_segundos,
            "duracao_minutos": round(duracao_segundos / 60, 1),
            "idioma": transcript.language,
            "idioma_codigo": transcript.language_code,
            "e_gerado": transcript.is_generated,
            "transcricoes_disponiveis": list_available_transcripts(video_id),
        }

        logger.info(
            f"Transcrição concluída: {resultado['num_palavras']} palavras, "
            f"{resultado['duracao_minutos']} min, idioma: {resultado['idioma']}"
        )

        return resultado

    except TranscriptsDisabled:
        return {
            "sucesso": False,
            "erro": "Transcrições desabilitadas para este vídeo",
            "codigo": "TRANSCRIPTS_DISABLED",
        }

    except NoTranscriptFound:
        return {
            "sucesso": False,
            "erro": "Nenhuma transcrição encontrada neste vídeo",
            "codigo": "NO_TRANSCRIPT",
        }

    except (VideoUnavailable, VideoUnplayable):
        return {
            "sucesso": False,
            "erro": "Vídeo não disponível, foi removido ou está bloqueado",
            "codigo": "VIDEO_UNAVAILABLE",
        }

    except CouldNotRetrieveTranscript:
        return {
            "sucesso": False,
            "erro": "Não foi possível recuperar a transcrição deste vídeo",
            "codigo": "COULD_NOT_RETRIEVE",
        }

    except ValueError as e:
        return {
            "sucesso": False,
            "erro": str(e),
            "codigo": "INVALID_URL",
        }

    except Exception as e:
        logger.error(f"Erro inesperado ao transcrever: {e}")
        return {
            "sucesso": False,
            "erro": f"Erro inesperado: {str(e)}",
            "codigo": "UNKNOWN_ERROR",
        }


def traduzir_texto_gemini(texto: str, idioma_destino: str = "pt-BR") -> dict:
    """
    Traduz texto usando Gemini 2.5 Flash.

    Args:
        texto: Texto a ser traduzido
        idioma_destino: Código do idioma de destino

    Returns:
        dict com sucesso e texto traduzido
    """
    try:
        import google.generativeai as genai
        from backend.config import settings

        genai.configure(api_key=settings.GEMINI_API_KEY)

        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""Traduza o seguinte texto para {idioma_destino}.
Mantenha o estilo, tom e formatação original.
Se o texto já estiver em {idioma_destino}, retorne-o sem alterações.

Texto:
{texto[:15000]}"""

        response = model.generate_content(prompt)

        texto_traduzido = response.text

        return {
            "sucesso": True,
            "texto_original": texto,
            "texto_traduzido": texto_traduzido,
            "idioma_origem": "detected",
            "idioma_destino": idioma_destino,
            "num_palavras_original": len(texto.split()),
            "num_palavras_traduzida": len(texto_traduzido.split()),
        }

    except Exception as e:
        logger.error(f"Erro ao traduzir com Gemini: {e}")
        return {
            "sucesso": False,
            "erro": f"Erro na tradução: {str(e)}",
            "codigo": "TRANSLATION_ERROR",
        }
