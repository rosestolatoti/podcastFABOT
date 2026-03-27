from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from backend.database import Base


class JobStatus:
    PENDING = "PENDING"
    READING = "READING"
    LLM_PROCESSING = "LLM_PROCESSING"
    SCRIPT_DONE = "SCRIPT_DONE"
    TTS_QUEUED = "TTS_QUEUED"
    TTS_PROCESSING = "TTS_PROCESSING"
    POST_PRODUCTION = "POST_PRODUCTION"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    QUEUED = "QUEUED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    status = Column(String(20), default="PENDING")
    progress = Column(Integer, default=0)
    current_step = Column(String(255), default="Aguardando...")

    input_text = Column(Text, nullable=True)
    script_json = Column(Text, nullable=True)
    script_edited = Column(Boolean, default=False)

    audio_path = Column(String(500), nullable=True)
    script_path = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    llm_mode = Column(String(20), default="gemini-2.5-flash")
    voice_host = Column(String(50))
    voice_cohost = Column(String(50), nullable=True)
    podcast_type = Column(String(20), default="monologue")
    target_duration = Column(Integer, default=10)
    depth_level = Column(String(20), default="normal")

    category = Column(String(100), nullable=True)
    tags = Column(String(500), nullable=True)
    is_favorite = Column(Boolean, default=False)
    playlist = Column(String(100), nullable=True)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    files = relationship("File", back_populates="job", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )

    original_name = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_path = Column(String(500), nullable=False)

    extracted_text = Column(Text, nullable=True)
    char_count = Column(Integer, default=0)
    status = Column(String(20), default="pending")

    job = relationship("Job", back_populates="files")


class UserConfig(Base):
    __tablename__ = "user_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    is_active = Column(Boolean, default=True)

    usuario_nome = Column(String(100), nullable=True)

    pessoas_proximas = Column(Text, nullable=True)

    apresentador_nome = Column(String(100), nullable=True)
    apresentador_voz = Column(String(50), nullable=True)

    apresentadora_nome = Column(String(100), nullable=True)
    apresentadora_voz = Column(String(50), nullable=True)

    personagens = Column(Text, nullable=True)
    empresas = Column(Text, nullable=True)

    saudar_nome = Column(Boolean, default=True)
    mencionar_pessoas = Column(Boolean, default=True)
    despedida_personalizada = Column(Boolean, default=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
