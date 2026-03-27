import hashlib
import logging
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db
from backend.models import Job, File as FileModel
from backend.services.ingestor import (
    ingest_file,
    InvalidFileError,
    FileTooLargeError,
    ScannedPDFError,
)
from backend.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()
executor = ThreadPoolExecutor(max_workers=4)


def ingest_file_sync(file_path: Path) -> dict:
    return ingest_file(file_path)


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    llm_mode: str = Form(default="gemini-2.5-flash"),
    voice_host: str = Form(default="pf_dora"),
    voice_cohost: str | None = Form(default=None),
    podcast_type: str = Form(default="monologue"),
    target_duration: int = Form(default=10),
    depth_level: str = Form(default="normal"),
    db: Session = Depends(get_db),
):
    job_id = str(uuid.uuid4())

    job = Job(
        id=job_id,
        title=title,
        status="PENDING",
        progress=0,
        current_step="Arquivo enviado, aguardando processamento...",
        llm_mode=llm_mode,
        voice_host=voice_host,
        voice_cohost=voice_cohost,
        podcast_type=podcast_type,
        target_duration=target_duration,
        depth_level=depth_level,
    )
    db.add(job)
    db.commit()

    upload_dir = Path(settings.UPLOAD_DIR) / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix.lower()
    file_path = upload_dir / f"{uuid.uuid4()}{file_ext}"

    content = await file.read()

    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo muito grande")

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(executor, ingest_file_sync, file_path)

        file_record = FileModel(
            id=str(uuid.uuid4()),
            job_id=job_id,
            original_name=file.filename,
            file_type=file_ext.lstrip("."),
            file_path=str(file_path),
            extracted_text=result["text"],
            char_count=result["char_count"],
            status="extracted",
        )
        db.add(file_record)
        db.commit()

        return {
            "job_id": job_id,
            "status": "uploaded",
            "char_count": result["char_count"],
            "text_hash": result["text_hash"],
        }

    except ScannedPDFError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidFileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao processar upload: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar arquivo")


@router.post("/paste")
async def upload_paste(
    title: str,
    text: str,
    llm_mode: str = "gemini-2.5-flash",
    voice_host: str = "pf_dora",
    voice_cohost: str | None = None,
    podcast_type: str = "monologue",
    target_duration: int = 10,
    depth_level: str = "normal",
    db: Session = Depends(get_db),
):
    if not text or len(text.strip()) < 100:
        raise HTTPException(
            status_code=400, detail="Texto muito curto (mínimo 100 caracteres)"
        )

    job_id = str(uuid.uuid4())

    job = Job(
        id=job_id,
        title=title,
        status="PENDING",
        progress=0,
        current_step="Texto enviado, aguardando processamento...",
        input_text=text,
        llm_mode=llm_mode,
        voice_host=voice_host,
        voice_cohost=voice_cohost,
        podcast_type=podcast_type,
        target_duration=target_duration,
        depth_level=depth_level,
    )
    db.add(job)
    db.commit()

    try:
        from arq import create_pool
        from backend.workers.podcast_worker import WorkerSettings

        redis = await create_pool(WorkerSettings.get_redis_settings())
        await redis.enqueue_job("process_podcast_job", job_id)
        job.status = "QUEUED"
        job.current_step = "Job enfileirado para processamento"
        db.commit()
    except Exception as e:
        logger.warning(f"Erro ao enfileirar job: {e}")

    return {"job_id": job_id, "status": "uploaded", "char_count": len(text)}
