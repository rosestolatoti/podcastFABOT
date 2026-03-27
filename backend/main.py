from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import logging.handlers
import json
import re
from pathlib import Path
from backend.config import settings
from backend.database import init_db
from backend.routers import jobs, upload, health, ocr, config, youtube

# Garante que o diretório de logs existe
Path(settings.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB por arquivo
            backupCount=5,  # mantém até 5 arquivos antigos
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}")
    init_db()
    logger.info("Banco de dados inicializado")
    yield
    logger.info("Encerrando aplicação")


app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(ocr.router, prefix="/ocr", tags=["ocr"])
app.include_router(config.router, tags=["config"])
app.include_router(youtube.router, prefix="/youtube", tags=["youtube"])

# Servir frontend estático em produção
from fastapi.staticfiles import StaticFiles

base_dir = Path(__file__).resolve().parent.parent
dist_dir = base_dir / "frontend" / "dist"
if dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")


@app.get("/")
async def root():
    return {"message": "FABOT Podcast Studio API", "version": settings.VERSION}


@app.get("/audio/{filepath:path}")
async def serve_audio(filepath: str):
    base_dir = Path(__file__).resolve().parent.parent
    output_dir = (base_dir / "data" / "output").resolve()
    audio_path = (output_dir / filepath).resolve()

    # Proteção contra path traversal: garante que o arquivo está dentro de output/
    if not str(audio_path).startswith(str(output_dir)):
        raise HTTPException(status_code=403, detail="Acesso negado")

    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(audio_path, media_type="audio/mpeg", filename=audio_path.name)


@app.get("/download/{job_id}")
async def download_audio(job_id: str):
    from backend.database import SessionLocal
    from backend.models import Job

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Job não encontrado")

        if not job.audio_path:
            raise HTTPException(status_code=400, detail="Áudio não gerado ainda")

        audio_path = Path(job.audio_path)
        if not audio_path.exists():
            raise HTTPException(
                status_code=404, detail="Arquivo de áudio não encontrado"
            )

        safe_title = re.sub(r"[^\w\s\-]", "", job.title or "podcast")
        safe_title = re.sub(r"[\s]+", "_", safe_title)[:50]

        episodes_meta = []
        if job.episodes_meta:
            try:
                episodes_meta = json.loads(job.episodes_meta)
            except:
                pass

        if len(episodes_meta) > 1:
            download_filename = f"{safe_title}_completo_{len(episodes_meta)}eps.mp3"
        else:
            download_filename = f"{safe_title}.mp3"

        return FileResponse(
            audio_path, media_type="audio/mpeg", filename=download_filename
        )
    finally:
        db.close()


@app.get("/download/{job_id}/episode/{episode_num}")
async def download_episode(job_id: str, episode_num: int):
    from backend.database import SessionLocal
    from backend.models import Job

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job não encontrado")

        output_dir = Path(settings.OUTPUT_DIR) / job_id
        ep_dir = output_dir / f"ep_{episode_num:02d}"
        ep_audio = ep_dir / "final.mp3"

        if not ep_audio.exists():
            raise HTTPException(status_code=404, detail="Episódio não encontrado")

        safe_title = re.sub(r"[^\w\s\-]", "", job.title or "podcast")
        safe_title = re.sub(r"[\s]+", "_", safe_title)[:40]

        filename = f"{safe_title}_ep{episode_num:02d}.mp3"

        return FileResponse(ep_audio, media_type="audio/mpeg", filename=filename)
    finally:
        db.close()
