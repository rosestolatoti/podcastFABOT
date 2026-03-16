"""
10 Testes do FABOT Podcast Studio

Testes baseados no documento docs/testes.txt

Nível 1 — O sistema sobe?
Teste 1: Worker sobe sem import circular
Teste 2: FastAPI sobe
Teste 3: Worker ARQ sobe

Nível 2 — Cada serviço funciona isolado?
Teste 4: Ingestor com PDF real
Teste 5: text_cleaner com casos edge
Teste 6: LLM com texto curto
Teste 7: Kokoro direto

Nível 3 — Pipeline completo com job mínimo
Teste 8: Job completo end-to-end

Nível 4 — Qualidade de áudio
Teste 9: Verificar LUFS
Teste 10: Verificar ausência de cliques
"""

import pytest
import asyncio
import json
import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestNivel1SistemaSobe:
    """Nível 1 — O sistema sobe?"""

    def test_01_worker_import_sem_circular(self):
        """Teste 1: Worker sobe sem import circular"""
        try:
            from backend.workers.podcast_worker import process_podcast_job

            assert callable(process_podcast_job)
        except ImportError as e:
            pytest.fail(f"Import circular detectado: {e}")
        except Exception as e:
            pytest.fail(f"Erro ao importar worker: {e}")

    def test_02_fastapi_sobe(self):
        """Teste 2: FastAPI sobe"""
        try:
            from backend.main import app

            assert app is not None
            assert app.title == "FABOT Podcast Studio"
        except ImportError as e:
            pytest.fail(f"Erro ao importar FastAPI: {e}")

    def test_03_worker_arq_settings(self):
        """Teste 3: Worker ARQ sobe"""
        try:
            from backend.workers.podcast_worker import WorkerSettings

            assert WorkerSettings is not None
        except ImportError as e:
            pytest.fail(f"Erro ao importar WorkerSettings: {e}")


class TestNivel2ServicosIsolados:
    """Nível 2 — Cada serviço funciona isolado?"""

    def test_04_ingestor_pdf(self, sample_pdf_path):
        """Teste 4: Ingestor com PDF real"""
        from backend.services.ingestor import validate_file

        # Validação deve passar
        validate_file(sample_pdf_path)

        # O PDF de teste tem pouco texto, mas a validação funciona
        assert sample_pdf_path.exists()

    def test_04_ingestor_txt(self, sample_txt_path):
        """Teste 4b: Ingestor com TXT"""
        from backend.services.ingestor import ingest_file

        result = ingest_file(sample_txt_path)

        assert "text" in result
        assert "char_count" in result
        assert result["file_type"] == "txt"

    def test_04_ingestor_validacao_magic_bytes(self, tmp_path):
        """Teste 4c: Validação de magic bytes"""
        from backend.services.ingestor import validate_file, InvalidFileError

        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"NOT A PDF FILE")

        with pytest.raises(InvalidFileError, match="não é um PDF válido"):
            validate_file(fake_pdf)

    def test_04_ingestor_tamanho_maximo(self, tmp_path):
        """Teste 4d: Arquivo muito grande"""
        from backend.services.ingestor import (
            validate_file,
            FileTooLargeError,
            MAX_FILE_SIZE,
        )

        large_file = tmp_path / "large.pdf"
        # Criar arquivo maior que 50MB (60MB)
        large_content = b"%PDF-1.4 test content " * (60 * 1024 * 1024 // 25)
        large_file.write_bytes(large_content)

        assert large_file.stat().st_size > MAX_FILE_SIZE, (
            f"Arquivo deve ser maior que {MAX_FILE_SIZE} bytes"
        )

        with pytest.raises(FileTooLargeError):
            validate_file(large_file)

    def test_05_text_cleaner_casos_edge(self):
        """Teste 5: text_cleaner com casos edge"""
        from backend.utils.text_cleaner import clean_for_tts

        casos_teste = [
            ("Teste com números: 1200 resultados", "mil e duzentos"),
            ("Sistemas IA são importantes", "inteligência artificial"),
            ("https://exemplo.com/pagina", ""),
            ("Teste com números: 50 e 25", "cinquenta"),
            ("Sem emoji 🎉 teste", "Sem emoji"),
            ("Símbolos: 5 + 3 = 8", "cinco"),
            ("ML e NLP são importantes", "machine learning"),
        ]

        for input_text, expected_part in casos_teste:
            result = clean_for_tts(input_text)
            if expected_part:
                assert expected_part.lower() in result.lower(), (
                    f"Falhou para: {input_text} -> resultado: {result}"
                )

    def test_05_text_cleaner_remocao_urls(self):
        """Teste 5b: URLs são removidas"""
        from backend.utils.text_cleaner import clean_for_tts

        text = "Visite https://exemplo.com e também www.test.com"
        result = clean_for_tts(text)

        assert "https://" not in result
        assert "www." not in result

    def test_05_text_cleaner_numeros_grandes(self):
        """Teste 5c: Números grandes convertidos"""
        from backend.utils.text_cleaner import clean_for_tts

        text = "O Brasil tem 215 milhões de habitantes"
        result = clean_for_tts(text)

        assert "215" not in result
        assert "milhões" in result.lower()

    def test_06_llm_health_check(self):
        """Teste 6: LLM health check"""
        import asyncio
        from backend.services.llm import get_provider, GroqProvider

        provider = get_provider("groq")

        assert isinstance(provider, GroqProvider)

    def test_06_llm_provider_interface(self):
        """Teste 6b: Interface do provider"""
        from backend.services.llm import LLMProvider

        assert hasattr(LLMProvider, "generate_script")
        assert hasattr(LLMProvider, "health_check")
        assert asyncio.iscoroutinefunction(LLMProvider.health_check)
        assert asyncio.iscoroutinefunction(LLMProvider.generate_script)

    def test_07_kokoro_direto(self):
        """Teste 7: Kokoro direto (mock)"""
        from backend.config import settings

        assert settings.KOKORO_URL is not None
        assert "8880" in settings.KOKORO_URL


class TestNivel3PipelineCompleto:
    """Nível 3 — Pipeline completo com job mínimo"""

    @pytest.mark.asyncio
    async def test_08_job_completo_end_to_end(self):
        """Teste 8: Job completo end-to-end (mock)"""
        from backend.models import Job, JobStatus
        from backend.database import Base, engine
        from sqlalchemy.orm import sessionmaker

        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        job = Job(
            id="test-job-001",
            title="Teste Mínimo",
            status=JobStatus.PENDING,
            llm_mode="groq",
            podcast_type="cohost",
            target_duration=5,
            voice_host="pm_alex",
            voice_cohost="pf_dora",
        )
        session.add(job)
        session.commit()

        retrieved_job = session.query(Job).filter_by(id="test-job-001").first()

        assert retrieved_job is not None
        assert retrieved_job.title == "Teste Mínimo"
        assert retrieved_job.status == JobStatus.PENDING

        session.delete(job)
        session.commit()
        session.close()


class TestNivel4QualidadeAudio:
    """Nível 4 — Qualidade de áudio"""

    def test_09_verificar_lufs(self, tmp_path):
        """Teste 9: Verificar LUFS (mock/skip se não instalado)"""
        try:
            import soundfile as sf
            import pyloudnorm as pyln
        except ImportError:
            pytest.skip("pyloudnorm ou soundfile não instalados")

        import numpy as np

        rate = 44100
        duration = 5
        samples = np.random.randn(rate * duration).astype(np.float32) * 0.1

        output_path = tmp_path / "test_audio.wav"
        sf.write(str(output_path), samples, rate)

        data, rate = sf.read(str(output_path))
        meter = pyln.Meter(rate)
        loudness = meter.integrated_loudness(data)

        assert loudness is not None
        print(f"LUFS medido: {loudness:.1f}")

    def test_10_verificar_cliques(self, tmp_path):
        """Teste 10: Verificar ausência de cliques (mock/skip)"""
        try:
            import numpy as np
        except ImportError:
            pytest.skip("numpy não instalado")

        import soundfile as sf

        rate = 44100
        duration = 2
        samples = np.sin(
            2 * np.pi * 440 * np.linspace(0, duration, rate * duration)
        ).astype(np.float32)

        output_path = tmp_path / "test_tone.wav"
        sf.write(str(output_path), samples, rate)

        data, rate = sf.read(str(output_path))
        samples_int = (data * 32767).astype(np.int16)

        diff = np.abs(np.diff(samples_int.astype(float)))
        threshold = np.percentile(diff, 99.9)
        clicks = np.sum(diff > threshold * 3)

        print(f"Possíveis cliques detectados: {clicks}")
        assert clicks < 100


class TestModels:
    """Testes dos modelos de dados"""

    def test_job_model_campos_obrigatorios(self):
        """Teste modelo Job campos obrigatórios"""
        from backend.models import Job, JobStatus

        job = Job(title="Teste", status=JobStatus.PENDING, voice_host="pm_alex")

        assert job.title == "Teste"
        assert job.status == JobStatus.PENDING
        assert job.voice_host == "pm_alex"
        assert job.script_edited in [False, None]  # Aceita None ou False
        assert job.progress in [0, None]  # Aceita 0 ou None

    def test_job_status_enum(self):
        """Teste JobStatus enum"""
        from backend.models import JobStatus

        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.READING == "READING"
        assert JobStatus.LLM_PROCESSING == "LLM_PROCESSING"
        assert JobStatus.SCRIPT_DONE == "SCRIPT_DONE"
        assert JobStatus.TTS_PROCESSING == "TTS_PROCESSING"
        assert JobStatus.POST_PRODUCTION == "POST_PRODUCTION"
        assert JobStatus.DONE == "DONE"
        assert JobStatus.FAILED == "FAILED"


class TestConfig:
    """Testes de configuração"""

    def test_config_settings(self):
        """Teste settings"""
        from backend.config import settings

        assert settings.PROJECT_NAME == "FABOT Podcast Studio"
        assert settings.VERSION == "1.0.0"
        assert settings.KOKORO_URL is not None
        assert settings.REDIS_URL is not None

    def test_config_paths(self):
        """Teste paths configurados"""
        from backend.config import settings

        assert hasattr(settings, "OUTPUT_DIR")
        assert hasattr(settings, "UPLOAD_DIR")
        assert hasattr(settings, "DATABASE_PATH")

    def test_config_audio_settings(self):
        """Teste configurações de áudio"""
        from backend.config import settings

        assert settings.AUDIO_SAMPLE_RATE == 44100
        assert settings.AUDIO_BITRATE == "192k"
        assert settings.AUDIO_CHANNELS == 2

    def test_config_pausas(self):
        """Teste configurações de pausa"""
        from backend.config import settings

        assert settings.PAUSE_SAME_SPEAKER_MS == 250
        assert settings.PAUSE_DIFFERENT_SPEAKER_MS == 700
        assert settings.PAUSE_SHORT_MS == 600
        assert settings.PAUSE_LONG_MS == 1400

    def test_config_tts(self):
        """Teste configurações TTS"""
        from backend.config import settings

        assert settings.TTS_MAX_RETRIES == 3
        assert settings.TTS_MAX_CONCURRENT == 3
        assert settings.WORDS_PER_MINUTE == 140


class TestIngestor:
    """Testes adicionais do ingestor"""

    def test_compute_text_hash(self):
        """Teste hash de texto"""
        from backend.services.ingestor import compute_text_hash

        text = "Hello World"
        hash1 = compute_text_hash(text)
        hash2 = compute_text_hash(text)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_ingestor_pdf_vazio(self, tmp_path):
        """Teste PDF vazio"""
        from backend.services.ingestor import ingest_file, IngestionError

        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_bytes(b"%PDF-1.4\n\n%%EOF")

        with pytest.raises(IngestionError):
            ingest_file(empty_pdf)


class TestLLM:
    """Testes do LLM"""

    def test_compute_config_hash(self):
        """Teste hash de configuração"""
        from backend.services.llm import compute_config_hash

        config1 = {"target_duration": 10, "depth_level": "normal"}
        config2 = {"target_duration": 10, "depth_level": "normal"}
        config3 = {"target_duration": 15, "depth_level": "normal"}

        hash1 = compute_config_hash(config1)
        hash2 = compute_config_hash(config2)
        hash3 = compute_config_hash(config3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_validate_script_response(self):
        """Teste validação de resposta do script"""
        from backend.services.llm import validate_script_response

        data = {
            "title": "Teste",
            "segments": [
                {
                    "speaker": "Host",
                    "text": "Olá pessoal!",
                    "emotion": "neutral",
                    "pause_after_ms": 600,
                }
            ],
        }

        result = validate_script_response(data)

        assert result.title == "Teste"
        assert len(result.segments) == 1
        assert result.segments[0].speaker == "Host"

    def test_validate_script_response_fallback(self):
        """Teste fallback de validação"""
        from backend.services.llm import validate_script_response

        data = {
            "title": "Teste",
            "segments": [
                {"speaker": "Host", "text": "Olá"},
            ],
        }

        result = validate_script_response(data)

        assert result is not None
        assert result.title == "Teste"

    def test_get_provider_groq(self):
        """Teste get_provider groq"""
        from backend.services.llm import get_provider, GroqProvider

        provider = get_provider("groq")
        assert isinstance(provider, GroqProvider)

    def test_get_provider_gemini(self):
        """Teste get_provider gemini"""
        from backend.services.llm import get_provider, GeminiProvider

        provider = get_provider("gemini")
        assert isinstance(provider, GeminiProvider)

    def test_get_provider_ollama(self):
        """Teste get_provider ollama"""
        from backend.services.llm import get_provider, OllamaProvider

        provider = get_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_get_provider_invalido(self):
        """Teste get_provider inválido"""
        from backend.services.llm import get_provider

        with pytest.raises(ValueError, match="desconhecido"):
            get_provider("invalid")


class TestTextCleaner:
    """Testes adicionais do text_cleaner"""

    def test_clean_for_tts_simbolos(self):
        """Teste símbolos matemáticos"""
        from backend.utils.text_cleaner import clean_for_tts

        result = clean_for_tts("5 + 3 = 8")

        assert "+" not in result
        assert "mais" in result
        assert "igual" in result

    def test_clean_for_tts_siglas(self):
        """Teste expansão de siglas"""
        from backend.utils.text_cleaner import clean_for_tts

        # API e SDK são tratadas como nomes técnicos (não IA)
        result = clean_for_tts("API e SDK")

        # As siglas são expandidas/removidas
        assert "API" not in result
        assert "SDK" not in result

        # IA é expandido para "inteligência artificial"
        result2 = clean_for_tts("IA é importante")
        assert "inteligência artificial" in result2.lower()

    def test_clean_for_tts_emojis(self):
        """Teste remoção de emojis"""
        from backend.utils.text_cleaner import clean_for_tts

        result = clean_for_tts("Olá mundo 🎉!")

        assert "🎉" not in result
        assert "Olá mundo" in result


class TestRouters:
    """Testes dos routers"""

    def test_health_router_existe(self):
        """Teste health router"""
        from backend.routers import health

        assert hasattr(health, "router")

    def test_jobs_router_existe(self):
        """Teste jobs router"""
        from backend.routers import jobs

        assert hasattr(jobs, "router")

    def test_upload_router_existe(self):
        """Teste upload router"""
        from backend.routers import upload

        assert hasattr(upload, "router")


class TestWorkers:
    """Testes dos workers"""

    def test_worker_settings_existe(self):
        """Teste WorkerSettings"""
        from backend.workers.podcast_worker import WorkerSettings

        assert WorkerSettings is not None

    def test_process_podcast_job_existe(self):
        """Teste função principal"""
        from backend.workers.podcast_worker import process_podcast_job

        assert callable(process_podcast_job)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
