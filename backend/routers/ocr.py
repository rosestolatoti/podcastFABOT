"""
FABOT Podcast Studio — OCR Router
Endpoint para extrair texto de imagens e PDFs
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import tempfile
import shutil
import logging

from backend.services.ocr_extractor import (
    extract_text_from_image,
    extract_text_from_pdf,
    get_file_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["ocr"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    """
    Extrai texto de uma imagem ou PDF.

    Suporta:
    - Imagens: JPG, PNG, BMP, TIFF, WebP
    - Documentos: PDF

    Retorna o texto extraído com metadados.
    """
    try:
        # Verificar tamanho do arquivo
        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, detail=f"Arquivo muito grande. Máximo: 50MB"
            )

        # Verificar tipo de arquivo
        file_type = get_file_type(file.filename)
        if file_type == "unknown":
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de arquivo não suportado: {file.filename}",
            )

        # Salvar temporariamente
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=Path(file.filename).suffix
        ) as tmp:
            tmp.write(contents)
            tmp_path = Path(tmp.name)

        try:
            # Extrair texto baseado no tipo
            if file_type == "image":
                result = extract_text_from_image(tmp_path)
            elif file_type == "pdf":
                result = extract_text_from_pdf(tmp_path)
            else:
                raise HTTPException(status_code=400, detail=f"Tipo não suportado")

            return JSONResponse(
                {
                    "success": True,
                    "filename": file.filename,
                    "file_type": file_type,
                    "result": result,
                }
            )

        finally:
            # Limpar arquivo temporário
            tmp_path.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no OCR: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-batch")
async def extract_text_batch(files: list[UploadFile] = File(...)):
    """
    Extrai texto de múltiplos arquivos de uma vez.
    Limite: 10 arquivos por vez.
    """
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Máximo de 10 arquivos por vez")

    results = []

    for file in files:
        try:
            contents = await file.read()

            if len(contents) > MAX_FILE_SIZE:
                results.append(
                    {
                        "filename": file.filename,
                        "success": False,
                        "error": "Arquivo muito grande",
                    }
                )
                continue

            file_type = get_file_type(file.filename)
            if file_type == "unknown":
                results.append(
                    {
                        "filename": file.filename,
                        "success": False,
                        "error": "Tipo não suportado",
                    }
                )
                continue

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(file.filename).suffix
            ) as tmp:
                tmp.write(contents)
                tmp_path = Path(tmp.name)

            try:
                if file_type == "image":
                    result = extract_text_from_image(tmp_path)
                elif file_type == "pdf":
                    result = extract_text_from_pdf(tmp_path)
                else:
                    result = {"text": "", "error": "Tipo não suportado"}

                results.append(
                    {
                        "filename": file.filename,
                        "file_type": file_type,
                        "success": True,
                        **result,
                    }
                )
            finally:
                tmp_path.unlink(missing_ok=True)

        except Exception as e:
            results.append(
                {"filename": file.filename, "success": False, "error": str(e)}
            )

    # Contar sucessos
    success_count = sum(1 for r in results if r.get("success", False))

    return JSONResponse(
        {
            "success": True,
            "total_files": len(files),
            "success_count": success_count,
            "results": results,
        }
    )
