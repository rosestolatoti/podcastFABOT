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
    job_timeout = 600
    max_concurrent_tasks = 2

    @classmethod
    def get_redis_settings(cls):
        from arq.connections import RedisSettings

        return RedisSettings(
            host="localhost",
            port=6379,
            conn_timeout=30,
            conn_retries=10,
            conn_retry_delay=5,
        )


async def process_podcast_job(ctx: dict, job_id: str) -> dict:
    """Gera roteiro + áudio com steps granulares de progresso."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        # PASSO 1 - Leitura
        job.status = "READING"
        job.progress = 5
        job.current_step = "📄 Lendo texto de entrada..."
        db.commit()

        from backend.services.ingestor import ingest_file
        from backend.services.llm import get_provider
        from backend.services.tts_orchestrator import TTSOrchestrator
        from backend.services.post_production import PostProductionPipeline

        text = job.input_text
        if not text and job.files:
            texts = []
            for f in job.files:
                result = ingest_file(Path(f.file_path))
                texts.append(result["text"])
            text = "\n\n".join(texts)

        # PASSO 2 - Dividindo
        job.progress = 8
        job.current_step = "✂️ Dividindo texto em seções..."
        db.commit()

        from backend.services.text_splitter import dividir_texto, relatorio_divisao

        secoes = dividir_texto(text)
        total_secoes = len(secoes)
        logger.info(f"\n{relatorio_divisao(secoes)}")

        if total_secoes == 0:
            from types import SimpleNamespace

            logger.warning(f"dividir_texto retornou 0 seções. Usando texto inteiro.")
            secoes = [SimpleNamespace(titulo="Episódio Único", conteudo=text or "")]
            total_secoes = 1

        # PASSO 3 - Texto dividido
        job.progress = 10
        job.current_step = f"📊 Texto dividido em {total_secoes} seção(ões)"
        db.commit()

        # PASSO 4 - Conectando LLM
        job.status = "LLM_PROCESSING"
        job.progress = 12
        job.current_step = f"🤖 Conectando ao provedor LLM ({job.llm_mode})..."
        db.commit()

        provider = get_provider(job.llm_mode)
        config = {
            "target_duration": job.target_duration,
            "depth_level": job.depth_level,
            "podcast_type": job.podcast_type,
            "voice_host": job.voice_host,
            "voice_cohost": job.voice_cohost,
        }

        # PASSO 5 - Enviando para IA
        job.progress = 15
        job.current_step = "🧠 Enviando texto para a IA..."
        db.commit()

        script = await provider.generate_script(text, config)

        # PASSO 6 - Parseando
        job.progress = 30
        job.current_step = "📝 Parseando resposta JSON da IA..."
        db.commit()

        # PASSO 7 - Validando
        job.progress = 35
        job.current_step = f"✅ Validando estrutura do roteiro..."
        db.commit()

        job.script_json = json.dumps(script, ensure_ascii=False)

        # PASSO 8 - Salvando
        job.progress = 38
        job.current_step = "💾 Salvando roteiro no banco de dados..."
        db.commit()

        job.status = "SCRIPT_DONE"
        job.progress = 40
        total_segments = (
            len(script.get("segments", [])) if isinstance(script, dict) else 0
        )
        job.current_step = f"✅ Roteiro pronto ({total_segments} falas)"
        db.commit()

        # PASSO 9 - TTS
        job.status = "TTS_PROCESSING"
        job.progress = 45
        job.current_step = "🔊 Preparando síntese de voz..."
        db.commit()

        # PASSO 10 - Configurando TTS
        job.progress = 48
        job.current_step = "🎤 Configurando Edge TTS..."
        db.commit()

        from backend.services.fabot_tts import build_episode

        output_dir = Path(settings.OUTPUT_DIR) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # PASSO 11 - Sintetizando
        job.progress = 50
        job.current_step = "🔊 Sintetizando fala..."
        db.commit()

        final_audio_path = await build_episode(
            script=script,
            output_dir=output_dir,
            job_id=job_id,
        )

        # PASSO 12 - Concatenando
        job.progress = 85
        job.current_step = "🎵 Concatenando segmentos de áudio..."
        db.commit()

        # PASSO 13 - Pós-produção
        job.progress = 88
        job.current_step = "🎚️ Aplicando pós-produção..."
        db.commit()

        # PASSO 14 - Calculando duração
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(str(final_audio_path))
        duration_seconds = len(audio) / 1000

        job.progress = 90
        job.current_step = f"📏 Calculando duração final..."
        db.commit()

        # PASSO 15 - Salvando MP3
        job.progress = 95
        job.current_step = "💾 Salvando MP3 final..."
        db.commit()

        job.audio_path = str(final_audio_path)
        job.duration_seconds = duration_seconds
        job.status = "DONE"
        job.progress = 100
        job.current_step = "✅ Podcast concluído!"
        db.commit()

        return script

    except Exception as e:
        logger.error(f"Job {job_id} falhou: {e}")
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = str(e)
            job.current_step = f"❌ Erro: {str(e)[:100]}"
            db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera roteiros. Se tem tópicos manuais do marca-texto, usa eles.
    Se não tem, usa o Content Planner automático."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        job.status = "READING"
        job.progress = 2
        job.current_step = "📄 Lendo texto de entrada..."
        db.commit()

        from backend.services.llm import get_provider

        text = job.input_text or ""
        llm_mode = job.llm_mode

        user_topics = None
        if job.content_plan:
            try:
                parsed_topics = json.loads(job.content_plan)
                if (
                    isinstance(parsed_topics, list)
                    and len(parsed_topics) > 0
                    and isinstance(parsed_topics[0], str)
                ):
                    user_topics = parsed_topics
                    logger.info(f"Tópicos manuais do usuário: {user_topics}")
            except (json.JSONDecodeError, TypeError):
                pass

        if user_topics:
            total_episodes = len(user_topics)

            job.progress = 4
            job.current_step = f"🤖 Conectando ao provedor LLM ({llm_mode})..."
            db.commit()

            provider = get_provider(str(llm_mode))

            job.status = "LLM_PROCESSING"
            job.progress = 8
            job.current_step = (
                f"📌 {total_episodes} tópico(s) selecionado(s) pelo usuário"
            )
            db.commit()

            all_scripts = []
            previous_summary = ""
            total_segments = 0

            for i, topic_text in enumerate(user_topics):
                episode_num = i + 1

                ep_progress = 10 + int((i / total_episodes) * 25)

                job.progress = ep_progress
                job.current_step = (
                    f"🧠 Gerando episódio {episode_num}/{total_episodes}: "
                    f"'{topic_text[:40]}'..."
                )
                db.commit()

                config = {
                    "target_duration": job.target_duration or 10,
                    "depth_level": job.depth_level,
                    "podcast_type": job.podcast_type,
                    "voice_host": job.voice_host,
                    "voice_cohost": job.voice_cohost,
                    "section_title": topic_text,
                    "episode_number": episode_num,
                    "total_episodes": total_episodes,
                    "previous_summary": previous_summary,
                }

                episode_input = (
                    f"TÓPICO DESTE EPISÓDIO: {topic_text}\n\n"
                    f"INSTRUÇÃO OBRIGATÓRIA: Gere um episódio de podcast focado "
                    f"EXCLUSIVAMENTE no tópico '{topic_text}' dentro do contexto "
                    f"do texto abaixo. NÃO invente informações que não estejam no "
                    f"texto fornecido. Use APENAS o que o texto diz sobre "
                    f"'{topic_text}'. Se o texto não fala sobre isso, diga que "
                    f"não há informação suficiente.\n\n"
                )

                if previous_summary:
                    episode_input += (
                        f"RESUMO DO EPISÓDIO ANTERIOR: {previous_summary}\n"
                        f"Faça referência natural ao que foi discutido antes "
                        f"para criar continuidade.\n\n"
                    )

                if episode_num < total_episodes:
                    next_topic = user_topics[episode_num]
                    episode_input += (
                        f"PRÓXIMO EPISÓDIO será sobre: '{next_topic}'\n"
                        f"Na despedida, mencione que o próximo tema será esse "
                        f"para criar expectativa.\n\n"
                    )
                elif episode_num == total_episodes:
                    episode_input += (
                        f"ESTE É O ÚLTIMO EPISÓDIO da série de {total_episodes}. "
                        f"Na despedida, faça uma recapitulação geral de todos os "
                        f"tópicos abordados na série.\n\n"
                    )

                episode_input += f"TEXTO DE REFERÊNCIA:\n{text}"

                script = await provider.generate_script(episode_input, config)

                ep_segments = (
                    len(script.get("segments", [])) if isinstance(script, dict) else 0
                )
                total_segments += ep_segments

                job.progress = 10 + int(((i + 1) / total_episodes) * 25)
                job.current_step = (
                    f"✅ Episódio {episode_num}/{total_episodes} gerado "
                    f"({ep_segments} falas): '{topic_text[:30]}'"
                )
                db.commit()

                if isinstance(script, dict):
                    segments = script.get("segments", [])
                    last_texts = [
                        s.get("text", "") for s in segments[-3:] if s.get("text")
                    ]
                    previous_summary = " ".join(last_texts)[:500]
                    script["episode_number"] = episode_num
                    script["total_episodes"] = total_episodes
                    script["section_title"] = topic_text

                all_scripts.append(script)
                logger.info(
                    f"Episódio {episode_num}/{total_episodes} gerado: {topic_text}"
                )

            job.progress = 36
            job.current_step = (
                f"✅ Validando {total_episodes} roteiro(s) ({total_segments} falas)..."
            )
            db.commit()

            job.progress = 38
            job.current_step = "💾 Salvando roteiros no banco de dados..."
            db.commit()

            if len(all_scripts) == 1:
                job.script_json = json.dumps(all_scripts[0], ensure_ascii=False)
            else:
                job.script_json = json.dumps(all_scripts, ensure_ascii=False)

            job.status = "SCRIPT_DONE"
            job.progress = 40
            job.current_step = (
                f"✅ Roteiro pronto ({total_episodes} episódios, "
                f"{total_segments} falas)"
            )
            db.commit()

            return {
                "success": True,
                "job_id": job_id,
                "total_episodes": total_episodes,
                "total_segments": total_segments,
                "script_json": job.script_json,
            }

        from backend.services.simple_content_planner import (
            create_content_plan,
            format_plan_report,
        )

        job.progress = 4
        job.current_step = f"🤖 Conectando ao provedor LLM ({llm_mode})..."
        db.commit()

        provider = get_provider(str(llm_mode))

        job.progress = 6
        job.current_step = "🧠 Analisando texto e identificando conceitos-chave..."
        db.commit()

        plan = await create_content_plan(text, provider)
        logger.info(f"\n{format_plan_report(plan)}")

        total_episodes = plan.total_episodes

        job.status = "LLM_PROCESSING"
        job.progress = 10
        job.current_step = (
            f"📊 Plano criado: {total_episodes} episódio(s) | "
            f"~{plan.estimated_total_minutes} min total"
        )
        db.commit()

        job.content_plan = json.dumps(
            {
                "total_episodes": plan.total_episodes,
                "estimated_total_minutes": plan.estimated_total_minutes,
                "episodes": [
                    {
                        "episode_number": ep.episode_number,
                        "title": ep.title,
                        "main_concept": ep.main_concept,
                        "key_topics": ep.key_topics,
                        "estimated_minutes": ep.estimated_minutes,
                    }
                    for ep in plan.episodes
                ],
            },
            ensure_ascii=False,
        )
        db.commit()

        all_scripts = []
        previous_summary = ""
        total_segments = 0

        for i, ep_plan in enumerate(plan.episodes):
            episode_num = ep_plan.episode_number
            ep_progress = 10 + int((i / total_episodes) * 25)

            job.progress = ep_progress
            job.current_step = (
                f"🧠 Gerando episódio {episode_num}/{total_episodes}: "
                f"'{ep_plan.title[:40]}'..."
            )
            db.commit()

            config = {
                "target_duration": job.target_duration or 10,
                "depth_level": job.depth_level,
                "podcast_type": job.podcast_type,
                "voice_host": job.voice_host,
                "voice_cohost": job.voice_cohost,
                "section_title": ep_plan.title,
                "episode_number": episode_num,
                "total_episodes": total_episodes,
                "previous_summary": previous_summary,
                "focus_prompt": ep_plan.focus_prompt,
                "main_concept": ep_plan.main_concept,
                "key_topics": ep_plan.key_topics,
            }

            episode_input = (
                f"CONCEITO PRINCIPAL: {ep_plan.main_concept}\n\n"
                f"TÓPICOS PARA APROFUNDAR: "
                f"{', '.join(ep_plan.key_topics)}\n\n"
                f"INSTRUÇÃO DE FOCO: {ep_plan.focus_prompt}\n\n"
                f"TEXTO DE REFERÊNCIA:\n{text[:8000]}"
            )

            script = await provider.generate_script(episode_input, config)

            ep_segments = (
                len(script.get("segments", [])) if isinstance(script, dict) else 0
            )
            total_segments += ep_segments

            job.progress = 10 + int(((i + 1) / total_episodes) * 25)
            job.current_step = (
                f"✅ Episódio {episode_num}/{total_episodes} gerado "
                f"({ep_segments} falas): '{ep_plan.title[:30]}'"
            )
            db.commit()

            if isinstance(script, dict):
                segments = script.get("segments", [])
                last_texts = [s.get("text", "") for s in segments[-3:] if s.get("text")]
                previous_summary = " ".join(last_texts)[:500]
                script["episode_number"] = episode_num
                script["total_episodes"] = total_episodes
                script["section_title"] = ep_plan.title
                script["main_concept"] = ep_plan.main_concept

            all_scripts.append(script)
            logger.info(
                f"Episódio {episode_num}/{total_episodes} gerado: {ep_plan.title}"
            )

        job.progress = 36
        job.current_step = (
            f"✅ Validando {total_episodes} roteiro(s) ({total_segments} falas)..."
        )
        db.commit()

        job.progress = 38
        job.current_step = "💾 Salvando roteiros no banco de dados..."
        db.commit()

        if len(all_scripts) == 1:
            job.script_json = json.dumps(all_scripts[0], ensure_ascii=False)
        else:
            job.script_json = json.dumps(all_scripts, ensure_ascii=False)

        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = (
            f"✅ Roteiro pronto ({total_episodes} episódios, "
            f"{total_segments} falas, "
            f"~{plan.estimated_total_minutes} min)"
        )
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "total_episodes": total_episodes,
            "total_segments": total_segments,
            "script_json": job.script_json,
        }

    except Exception as e:
        logger.error(f"Job {job_id} falhou ao gerar roteiro: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_step = f"❌ Erro: {str(e)[:100]}"
                db.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status failed: {db_err}")
        return {"success": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()


async def start_tts_job(ctx: dict, job_id: str) -> dict:
    """Gera áudio para todos os episódios do job."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        if job.status not in ("SCRIPT_DONE", "TTS_QUEUED"):
            raise ValueError(f"Status inválido para TTS: {job.status}")

        scripts_data = json.loads(job.script_json)

        # Normalizar: se for dict único, transformar em lista
        if isinstance(scripts_data, dict):
            scripts_list = [scripts_data]
        elif isinstance(scripts_data, list):
            scripts_list = scripts_data
        else:
            raise ValueError("script_json inválido")

        total_episodes = len(scripts_list)

        job.status = "TTS_PROCESSING"
        job.progress = 42
        job.current_step = f"🔊 Preparando síntese de {total_episodes} episódio(s)..."
        db.commit()

        from backend.services.fabot_tts import build_episode
        from pydub import AudioSegment

        output_dir = Path(settings.OUTPUT_DIR) / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        all_audio_paths = []
        combined_audio = AudioSegment.empty()

        for i, script in enumerate(scripts_list):
            ep_num = i + 1

            # Progresso: 42% a 90% dividido entre episódios
            ep_progress = 42 + int((i / total_episodes) * 48)

            job.progress = ep_progress
            ep_title = script.get("section_title", script.get("title", f"Ep {ep_num}"))
            job.current_step = (
                f"🎤 Sintetizando episódio {ep_num}/{total_episodes}: "
                f"'{ep_title[:35]}'..."
            )
            db.commit()

            ep_output_dir = output_dir / f"ep_{ep_num:02d}"
            ep_output_dir.mkdir(parents=True, exist_ok=True)

            audio_path = await build_episode(
                script=script,
                output_dir=ep_output_dir,
                job_id=f"{job_id}_ep{ep_num:02d}",
            )

            all_audio_paths.append(str(audio_path))

            # Carregar e concatenar
            ep_audio = AudioSegment.from_mp3(str(audio_path))
            if i > 0:
                combined_audio += AudioSegment.silent(duration=2000)
            combined_audio += ep_audio

            job.progress = 42 + int(((i + 1) / total_episodes) * 48)
            ep_duration = len(ep_audio) / 1000
            job.current_step = (
                f"✅ Episódio {ep_num}/{total_episodes} sintetizado "
                f"({ep_duration:.0f}s): '{ep_title[:30]}'"
            )
            db.commit()

        # Exportar áudio final combinado
        job.progress = 92
        job.current_step = "🎵 Concatenando todos os episódios..."
        db.commit()

        final_path = output_dir / "final.mp3"
        combined_audio.export(str(final_path), format="mp3", bitrate="192k")

        duration_seconds = len(combined_audio) / 1000

        job.progress = 95
        job.current_step = "💾 Salvando MP3 final..."
        db.commit()

        # Salvar metadados de cada episódio
        episodes_meta = []
        for i, path in enumerate(all_audio_paths):
            ep_audio = AudioSegment.from_mp3(path)
            episodes_meta.append(
                {
                    "episode_number": i + 1,
                    "audio_path": path,
                    "duration_seconds": len(ep_audio) / 1000,
                    "title": scripts_list[i].get(
                        "section_title",
                        scripts_list[i].get("title", f"Episódio {i + 1}"),
                    ),
                }
            )

        job.audio_path = str(final_path)
        job.duration_seconds = duration_seconds
        job.episodes_meta = json.dumps(episodes_meta, ensure_ascii=False)
        job.status = "DONE"
        job.progress = 100
        job.current_step = (
            f"✅ Podcast concluído! {total_episodes} episódio(s), "
            f"{duration_seconds:.0f}s total"
        )
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "audio_path": str(final_path),
            "total_episodes": total_episodes,
            "duration_seconds": duration_seconds,
        }

    except Exception as e:
        logger.error(f"Job TTS {job_id} falhou: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_step = f"❌ Erro: {str(e)[:100]}"
                db.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status failed: {db_err}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


WorkerSettings.functions = [
    process_podcast_job,
    start_tts_job,
]
