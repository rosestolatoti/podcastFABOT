"""
Router para transcrição de vídeos do YouTube.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class YouTubeTranscribeRequest(BaseModel):
    url: str = Field(..., description="URL do vídeo do YouTube")
    idiomas: list[str] = Field(
        default=["pt", "pt-BR", "en", "en-US"],
        description="Idiomas preferidos para transcrição",
    )


class YouTubeTranslateRequest(BaseModel):
    texto: str = Field(..., description="Texto a ser traduzido")
    idioma_destino: str = Field(
        default="pt-BR", description="Código do idioma de destino"
    )


@router.post("/transcribe")
async def transcribe_youtube(req: YouTubeTranscribeRequest):
    """
    Transcreve um vídeo do YouTube.

    - **url**: URL completa do vídeo do YouTube
    - **idiomas**: Lista de códigos de idioma em ordem de preferência
    """
    from backend.services.youtube_transcriber import transcrever_video

    logger.info(f"Recebida requisição de transcrição: {req.url}")

    resultado = transcrever_video(
        video_url=req.url,
        idiomas_preferidos=req.idiomas,
    )

    if not resultado.get("sucesso", False):
        codigo = resultado.get("codigo", "UNKNOWN")
        detalhe = resultado.get("erro", "Erro desconhecido")

        status_map = {
            "TRANSCRIPTS_DISABLED": 403,
            "NO_TRANSCRIPT": 404,
            "VIDEO_UNAVAILABLE": 404,
            "FAILED_SUBTITLES": 422,
            "INVALID_URL": 400,
        }

        status_code = status_map.get(codigo, 500)
        raise HTTPException(status_code=status_code, detail=detalhe)

    return resultado


@router.post("/translate")
async def translate_text(req: YouTubeTranslateRequest):
    """
    Traduz texto usando Gemini 2.5 Flash.

    - **texto**: Texto a ser traduzido
    - **idioma_destino**: Código do idioma de destino (padrão: pt-BR)
    """
    from backend.services.youtube_transcriber import traduzir_texto_gemini

    logger.info(f"Traduzindo texto para: {req.idioma_destino}")

    resultado = traduzir_texto_gemini(
        texto=req.texto,
        idioma_destino=req.idioma_destino,
    )

    if not resultado.get("sucesso", False):
        raise HTTPException(
            status_code=500, detail=resultado.get("erro", "Erro na tradução")
        )

    return resultado


@router.get("/info/{video_id}")
async def get_video_info(video_id: str):
    """
    Obtém informações sobre um vídeo do YouTube.
    """
    from backend.services.youtube_transcriber import (
        get_video_id,
        get_video_title,
        list_available_transcripts,
    )

    try:
        vid = get_video_id(f"https://www.youtube.com/watch?v={video_id}")
        title = get_video_title(vid)
        transcripts = list_available_transcripts(vid)

        return {
            "video_id": vid,
            "titulo": title,
            "transcricoes_disponiveis": transcripts,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
