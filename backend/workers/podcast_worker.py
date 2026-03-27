import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from arq import create_pool
from arq.worker import Worker
from pydantic import BaseModel

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Job

logger = logging.getLogger(__name__)


class JobConfig(BaseModel):
    job_id: str
    text: str
    llm_mode: str = "gemini-2.5-flash"
    voice_host: str = "pf_dora"
    voice_cohost: str | None = None
    podcast_type: str = "monologue"
    target_duration: int = 10
    depth_level: str = "normal"


class WorkerSettings:
    functions = ["process_podcast_job", "start_tts_job"]
    redis_settings = None
    max_jobs = 5
    timeout = 3600

    @classmethod
    def get_redis_settings(cls):
        from arq.connections import RedisSettings

        return RedisSettings(
            host="localhost",
            port=6379,
            conn_timeout=10,
            conn_retries=5,
            conn_retry_delay=1,
        )


async def process_podcast_job(ctx: dict, job_id: str) -> dict:
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        job.status = "READING"
        job.progress = 5
        job.current_step = "Processando arquivos..."
        db.commit()

        from backend.services.ingestor import ingest_file
        from backend.services.llm import get_provider
        from backend.services.text_splitter import dividir_texto, relatorio_divisao
        from backend.services.tts_orchestrator import TTSOrchestrator
        from backend.services.post_production import PostProductionPipeline

        text = job.input_text
        if not text and job.files:
            texts = []
            for f in job.files:
                result = ingest_file(Path(f.file_path))
                texts.append(result["text"])
            text = "\n\n".join(texts)

        job.status = "READING"
        job.progress = 8
        job.current_step = "Dividindo texto em seções..."
        db.commit()

        secoes = dividir_texto(text or "")
        logger.info(f"\n{relatorio_divisao(secoes)}")

        job.status = "LLM_PROCESSING"
        job.progress = 20
        job.current_step = f"Gerando roteiro (episódio 1 de {len(secoes)})..."
        db.commit()

        provider = get_provider(str(job.llm_mode))

        all_segments = []
        first_script = None
        for i, secao in enumerate(secoes):
            if i > 0:
                job.current_step = f"Gerando roteiro (episódio {i + 1} de {len(secoes)})..."
                job.progress = 20 + int(20 * i / len(secoes))
                db.commit()

            config = {
                "target_duration": job.target_duration,
                "depth_level": job.depth_level,
                "podcast_type": job.podcast_type,
                "voice_host": job.voice_host,
                "voice_cohost": job.voice_cohost,
                "section_title": secao.titulo,
                "episode_number": i + 1,
                "total_episodes": len(secoes),
            }

            script = await provider.generate_script(secao.conteudo, config)
            if first_script is None:
                first_script = script
            all_segments.extend(script.get("segments", []))

        combined_script = {
            "title": job.title,
            "segments": all_segments,
            "generated_at": first_script.get("generated_at") if first_script else None,
            "llm_provider": first_script.get("llm_provider") if first_script else None,
            "llm_model": first_script.get("llm_model") if first_script else None,
            "total_episodes": len(secoes),
        }

        job.script_json = json.dumps(combined_script, ensure_ascii=False)
        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = "Roteiro pronto para revisão"
        db.commit()

        return combined_script

    except Exception as e:
        logger.error(f"Job {job_id} falhou: {e}")
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = str(e)
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera apenas o roteiro (LLM), sem gerar áudio"""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        job.status = "READING"
        job.progress = 5
        job.current_step = "Dividindo texto em seções..."
        db.commit()

        from backend.services.text_splitter import dividir_texto, relatorio_divisao
        from backend.services.llm import get_provider

        text = job.input_text or "Texto não fornecido"

        secoes = dividir_texto(text)
        logger.info(f"\n{relatorio_divisao(secoes)}")

        job.status = "LLM_PROCESSING"
        job.progress = 10
        job.current_step = f"Gerando roteiro (episódio 1 de {len(secoes)})..."
        db.commit()

        provider = get_provider(str(job.llm_mode))

        config = {
            "target_duration": job.target_duration or 10,
            "depth_level": job.depth_level,
            "podcast_type": job.podcast_type,
            "voice_host": job.voice_host,
            "voice_cohost": job.voice_cohost,
            "section_title": secoes[0].titulo,
            "episode_number": 1,
            "total_episodes": len(secoes),
        }

        script = await provider.generate_script(secoes[0].conteudo, config)

        job.script_json = json.dumps(script, ensure_ascii=False)
        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = "Roteiro pronto para revisão"
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "script": str(script),
            "total_episodes": len(secoes),
        }

    except Exception as e:
        logger.error(f"Job {job_id} falhou ao gerar roteiro: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = str(e)
            db.commit()
        return {"success": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()


async def start_tts_job(ctx: dict, job_id: str) -> dict:
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        if job.status not in ("SCRIPT_DONE", "TTS_QUEUED"):
            raise ValueError(f"Status inválido para TTS: {job.status}")

        import json

        script = json.loads(job.script_json)

        job.status = "TTS_PROCESSING"
        job.progress = 45
        job.current_step = "Gerando áudio com Edge TTS..."
        db.commit()

        from backend.services.fabot_tts import build_episode
        from pydub import AudioSegment

        output_dir = Path(settings.OUTPUT_DIR) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        final_audio_path = await build_episode(
            script=script,
            output_dir=output_dir,
            job_id=job_id,
        )

        job.progress = 90
        db.commit()

        audio = AudioSegment.from_mp3(str(final_audio_path))
        duration_seconds = len(audio) / 1000

        job.audio_path = str(final_audio_path)
        job.duration_seconds = duration_seconds
        job.status = "DONE"
        job.progress = 100
        job.current_step = "Podcast concluído!"
        db.commit()

        return {"success": True, "job_id": job_id, "audio_path": str(final_audio_path)}

    except Exception as e:
        logger.error(f"Job TTS {job_id} falhou: {e}")

        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = str(e)
            db.commit()

        return {"success": False, "error": str(e)}

    finally:
        db.close()


WorkerSettings.functions = [process_podcast_job, start_tts_job]
