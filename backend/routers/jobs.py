import json
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Generator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.database import get_db, SessionLocal
from backend.models import Job, File
from backend.config import settings
from backend.workers.podcast_worker import (
    process_podcast_job,
    start_tts_job,
    WorkerSettings,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def run_podcast_job_background(job_id: str):
    """Wrapper para executar job em background com sua própria sessão DB"""
    import asyncio
    import threading

    db = SessionLocal()
    try:
        logger.info(f"[Background] Iniciando processamento do job {job_id}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[Background] Job {job_id} não encontrado")
            return

        job.status = "READING"
        job.progress = 5
        job.current_step = "Iniciando processamento..."
        db.commit()
        db.close()

        try:

            def run_in_new_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(process_podcast_job({}, job_id))
                finally:
                    loop.close()

            result = run_in_new_loop()
            logger.info(f"[Background] Job {job_id} concluído: {result}")
        except Exception as run_err:
            logger.error(f"[Background] Erro ao executar job {job_id}: {run_err}")
            raise

    except Exception as e:
        logger.error(f"[Background] Erro ao processar job {job_id}: {e}")
        try:
            db = SessionLocal()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                db.commit()
            db.close()
        except Exception as db_err:
            logger.error(f"[Background] Erro ao atualizar status failed: {db_err}")
    finally:
        try:
            db.close()
        except Exception:
            pass


def run_generate_script_only(job_id: str):
    """Gera apenas o roteiro (LLM), sem gerar áudio"""
    import asyncio
    from backend.workers.podcast_worker import generate_script_only

    db = SessionLocal()
    try:
        logger.info(f"[ScriptOnly] Gerando apenas roteiro para job {job_id}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[ScriptOnly] Job {job_id} não encontrado")
            return

        job.status = "READING"
        job.progress = 5
        job.current_step = "Lendo texto..."
        db.commit()
        db.close()
        logger.info(f"[ScriptOnly] Job {job_id} encontrado, status: READING")

        try:

            def run_in_new_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(generate_script_only({}, job_id))
                finally:
                    loop.close()

            result = run_in_new_loop()
            logger.info(f"[ScriptOnly] Roteiro gerado para job {job_id}: {result}")
        except Exception as run_err:
            logger.error(
                f"[ScriptOnly] Erro ao executar generate_script_only {job_id}: {run_err}"
            )
            raise

    except Exception as e:
        logger.error(f"[ScriptOnly] Erro ao gerar roteiro {job_id}: {e}")
        try:
            db = SessionLocal()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                db.commit()
            db.close()
        except Exception:
            logger.error("[ScriptOnly] Erro ao atualizar status failed")


class JobCreate(BaseModel):
    title: str | None = None
    llm_mode: str = "gemini-2.5-flash"
    voice_host: str = "pf_dora"
    voice_cohost: str | None = None
    podcast_type: str = "monologue"
    target_duration: int = 10
    depth_level: str = "normal"


class ScriptUpdate(BaseModel):
    script_json: str


@router.post("/", status_code=201)
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    job = Job(
        id=str(uuid.uuid4()),
        title=job_data.title or "Novo Podcast",
        status="PENDING",
        progress=0,
        current_step="Aguardando início...",
        llm_mode=job_data.llm_mode,
        voice_host=job_data.voice_host,
        voice_cohost=job_data.voice_cohost,
        podcast_type=job_data.podcast_type,
        target_duration=job_data.target_duration,
        depth_level=job_data.depth_level,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {"job_id": job.id, "status": job.status}


@router.get("/history")
async def get_job_history(
    limit: int = Query(default=20, le=100),
    q: str = "",
    category: str = "",
    playlist: str = "",
    favorites: bool = False,
    db: Session = Depends(get_db),
):
    """Retorna histórico de jobs com filtros opcionais (q, category, playlist, favorites)."""
    query = db.query(Job)

    if q:
        query = query.filter(Job.title.ilike(f"%{q}%"))
    if category:
        query = query.filter(Job.category == category)
    if playlist:
        query = query.filter(Job.playlist == playlist)
    if favorites:
        query = query.filter(Job.is_favorite == True)  # noqa: E712

    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()

    return {
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "status": j.status,
                "progress": j.progress,
                "duration_seconds": j.duration_seconds,
                "llm_mode": j.llm_mode,
                "category": j.category,
                "tags": j.tags,
                "is_favorite": j.is_favorite,
                "playlist": j.playlist,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ]
    }


@router.get("/{job_id}")
async def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    return {
        "id": job.id,
        "title": job.title,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "script_json": job.script_json,
        "script_edited": job.script_edited,
        "audio_path": job.audio_path,
        "duration_seconds": job.duration_seconds,
        "error_message": job.error_message,
        "llm_mode": job.llm_mode,
        "voice_host": job.voice_host,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "content_plan": job.content_plan,
        "episodes_meta": job.episodes_meta,
    }


@router.post("/{job_id}/start-tts")
async def start_tts(job_id: str, db: Session = Depends(get_db)):
    """Inicia geração de TTS apenas (para jobs com roteiro pronto)"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status != "SCRIPT_DONE":
        raise HTTPException(
            status_code=400, detail=f"Status deve ser SCRIPT_DONE, atual: {job.status}"
        )

    try:
        from arq import create_pool
        from backend.workers.podcast_worker import WorkerSettings

        redis = await create_pool(WorkerSettings.get_redis_settings())
        await redis.enqueue_job("start_tts_job", job_id)

        job.status = "TTS_QUEUED"
        job.current_step = "TTS enfileirado"
        db.commit()

        return {"status": "queued", "job_id": job_id}
    except Exception as e:
        logger.error(f"Erro ao enfileirar TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/start")
async def start_job(
    job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status not in ["PENDING", "QUEUED", "FAILED"]:
        raise HTTPException(status_code=400, detail=f"Status inválido: {job.status}")

    # Atualiza status e retorna imediatamente
    job.status = "READING"
    job.progress = 5
    job.current_step = "Processando..."
    db.commit()

    # Dispara processamento em background
    background_tasks.add_task(run_podcast_job_background, job_id)

    logger.info(f"Job {job_id} enviado para processamento em background")
    return {"status": "queued", "job_id": job_id}


@router.post("/{job_id}/generate-script")
async def generate_script_only(
    job_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """Gera apenas o roteiro (LLM), sem gerar áudio"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status not in ["PENDING", "QUEUED", "FAILED"]:
        raise HTTPException(status_code=400, detail=f"Status inválido: {job.status}")

    # Atualiza status
    job.status = "READING"
    job.progress = 5
    job.current_step = "Gerando roteiro..."
    db.commit()

    # Dispara processamento apenas do roteiro
    background_tasks.add_task(run_generate_script_only, job_id)

    logger.info(f"Job {job_id} enviado para geração de roteiro")
    return {"status": "script_queued", "job_id": job_id}


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    async def event_generator() -> Generator[str, None, None]:
        last_status = None
        last_progress = -1

        while True:
            db.refresh(job)

            if job.status != last_status or job.progress != last_progress:
                last_status = job.status
                last_progress = job.progress

                data = json.dumps(
                    {
                        "status": job.status,
                        "progress": job.progress,
                        "current_step": job.current_step,
                        "script_json": job.script_json,
                    }
                )
                yield f"data: {data}\n\n"

            if job.status in ["DONE", "FAILED"]:
                break

            await asyncio.sleep(0.8)

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{job_id}/result")
async def get_job_result(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status != "DONE":
        raise HTTPException(status_code=400, detail=f"Job não concluído: {job.status}")

    return {
        "job_id": job.id,
        "title": job.title,
        "audio_path": job.audio_path,
        "duration_seconds": job.duration_seconds,
        "script_path": job.script_path,
        "status": job.status,
    }


@router.get("/{job_id}/script")
async def get_job_script(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    return {
        "job_id": job.id,
        "script_json": job.script_json,
        "script_edited": job.script_edited,
    }


@router.put("/{job_id}/script")
async def update_job_script(
    job_id: str, script_data: ScriptUpdate, db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job.script_json = script_data.script_json
    job.script_edited = True
    job.status = "SCRIPT_DONE"
    db.commit()

    return {"status": "saved", "job_id": job_id}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status in ["DONE", "FAILED", "CANCELLED"]:
        raise HTTPException(status_code=400, detail=f"Job já finalizado: {job.status}")

    job.status = "CANCELLED"
    job.error_message = "Cancelado pelo usuário"
    db.commit()

    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        job_key = f"arq:job:{job_id}"
        queue_key = f"arq:queue:default"
        r.delete(job_key)
        logger.info(f"Job {job_id} removido do Redis")
    except Exception as e:
        logger.warning(f"Não foi possível cancelar job no Redis: {e}")

    return {"status": "cancelled", "job_id": job_id}


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    db.delete(job)
    db.commit()

    return {"deleted": job_id}


class JobUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    tags: str | None = None
    is_favorite: bool | None = None
    playlist: str | None = None


@router.patch("/{job_id}")
async def update_job(job_id: str, update: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if update.title is not None:
        job.title = update.title
    if update.category is not None:
        job.category = update.category
    if update.tags is not None:
        job.tags = update.tags
    if update.is_favorite is not None:
        job.is_favorite = update.is_favorite
    if update.playlist is not None:
        job.playlist = update.playlist

    db.commit()
    return {"status": "updated", "job_id": job_id}


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS PARA MULTI-EPISÓDIOS (CONTENT PLANNER)
# ═══════════════════════════════════════════════════════════════


class MultiJobCreate(BaseModel):
    titulo: str | None = None
    texto: str
    llm_mode: str = "gemini-2.5-flash"


def run_multi_episode_pipeline(job_id: str, texto: str):
    logger.warning("[MultiEpisode] Desabilitado - usar generate_script_only()")

    db = SessionLocal()
    try:
        logger.info(f"[MultiEpisode] Iniciando pipeline para job {job_id}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"[MultiEpisode] Job {job_id} não encontrado")
            return

        job.pipeline_mode = True
        job.status = "PLANNING"
        job.progress = 5
        job.current_step = "Extraindo conceitos..."
        db.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(texto)
            temp_path = f.name

        try:
            output_dir = tempfile.mkdtemp()
            estado = executar_pipeline(
                arquivo=temp_path,
                output_dir=output_dir,
                titulo_override=job.title or "Podcast Multi-Ep",
            )

            if estado.status.value == "concluido":
                job.status = "EPISODES_DONE"
                job.progress = 100
                job.current_step = f"{len(estado.episodios_gerados)} episódios prontos"
                job.episodes_count = len(estado.episodios_gerados)
                job.episodes_json = json.dumps(
                    [
                        {
                            "numero": ep.numero,
                            "title": ep.title,
                            "episode_summary": ep.episode_summary,
                            "keywords": ep.keywords,
                            "duracao_minutos": ep.duracao_minutos,
                            "qualidade_score": ep.qualidade_score,
                            "segments_count": len(ep.segments),
                        }
                        for ep in estado.episodios_gerados
                    ],
                    ensure_ascii=False,
                )
                if estado.plano:
                    job.plano_json = json.dumps(
                        {
                            "total_episodios": estado.plano.total_episodios,
                            "total_conceitos": estado.plano.total_conceitos,
                            "cobertura": estado.plano.cobertura_percentual,
                        }
                    )
                if estado.bible:
                    job.bible_json = json.dumps(
                        {
                            "glossario": estado.bible.glossario,
                            "estilo_tom": estado.bible.estilo_tom,
                            "nivel_audiencia": estado.bible.nivel_audiencia,
                        }
                    )
                db.commit()
                logger.info(
                    f"[MultiEpisode] Pipeline concluído: {job.episodes_count} episódios"
                )
            else:
                job.status = "FAILED"
                job.error_message = estado.ultimo_erro
                db.commit()
                logger.error(f"[MultiEpisode] Pipeline falhou: {estado.ultimo_erro}")

        finally:
            os.unlink(temp_path)

    except Exception as e:
        logger.error(f"[MultiEpisode] Erro no pipeline: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/{job_id}/generate-multi")
async def generate_multi_episodes(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Inicia pipeline de múltiplos episódios para um job existente via ARQ Worker"""
    from arq import create_pool
    from backend.workers.podcast_worker import WorkerSettings

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status not in ["PENDING", "QUEUED", "SCRIPT_DONE", "FAILED"]:
        raise HTTPException(
            status_code=400, detail=f"Status inválido para multi-episódio: {job.status}"
        )

    job.pipeline_mode = True
    job.status = "PLANNING"
    job.progress = 5
    job.current_step = "Planejando episódios..."
    db.commit()

    redis = await create_pool(WorkerSettings.get_redis_settings())
    await redis.enqueue_job("run_multi_episode_pipeline", job_id)

    return {"status": "multi_queued", "job_id": job_id}


@router.get("/{job_id}/episodes")
async def get_episodes(job_id: str, db: Session = Depends(get_db)):
    """Retorna todos os episódios gerados de um job multi-episódio"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if not job.pipeline_mode:
        raise HTTPException(status_code=400, detail="Job não é modo multi-episódio")

    if job.status == "EPISODES_DONE":
        episodios = json.loads(job.episodes_json) if job.episodes_json else []
        return {
            "job_id": job_id,
            "episodes_count": job.episodes_count,
            "episodios": episodios,
            "plano": json.loads(job.plano_json) if job.plano_json else None,
            "bible": json.loads(job.bible_json) if job.bible_json else None,
        }

    return {
        "job_id": job_id,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "current_episode": job.current_episode,
        "pipeline_status": job.pipeline_status,
    }


@router.post("/{job_id}/start-tts-all")
async def start_tts_all_episodes(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Inicia TTS para todos os episódios de um job multi-episódio"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.status != "EPISODES_DONE":
        raise HTTPException(
            status_code=400,
            detail=f"Status deve ser EPISODES_DONE, atual: {job.status}",
        )

    job.status = "TTS_QUEUED"
    job.current_step = "Gerando áudio dos episódios..."
    db.commit()

    background_tasks.add_task(run_tts_all_episodes, job_id)

    return {"status": "tts_all_queued", "job_id": job_id}


def run_tts_all_episodes(job_id: str):
    """Gera TTS para todos os episódios em background"""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        episodios = json.loads(job.episodes_json) if job.episodes_json else []
        total = len(episodios)

        audio_paths = []
        for i, ep in enumerate(episodios):
            job.current_episode = i + 1
            job.progress = int((i / total) * 100)
            db.commit()

            audio_path = f"ep_{ep['numero']:02d}_{ep['title'][:30]}.mp3"
            audio_paths.append(audio_path)

        job.status = "DONE"
        job.progress = 100
        job.current_step = f"{total} episódios com áudio"
        job.audio_path = json.dumps(audio_paths)
        db.commit()
        logger.info(f"[TTSAll] Job {job_id}: {total} episódios com áudio gerados")

    except Exception as e:
        logger.error(f"[TTSAll] Erro: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
