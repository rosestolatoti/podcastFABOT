from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from backend.config import settings
from backend.database import init_db
from backend.routers import jobs, upload, health

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(settings.LOG_FILE), logging.StreamHandler()],
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(health.router, prefix="/health", tags=["health"])


@app.get("/")
async def root():
    return {"message": "FABOT Podcast Studio API", "version": settings.VERSION}


@app.get("/audio/{filepath:path}")
async def serve_audio(filepath: str):
    from pathlib import Path

    base_dir = Path(__file__).resolve().parent.parent
    audio_path = base_dir / "data" / "output" / filepath
    if not audio_path.exists():
        return {"error": "Arquivo não encontrado", "path": str(audio_path)}
    return FileResponse(
        audio_path, media_type="audio/mpeg", filename=filepath.split("/")[-1]
    )
