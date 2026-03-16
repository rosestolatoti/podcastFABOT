import asyncio
import logging
import hashlib
import io
from pathlib import Path
from datetime import datetime, timezone

import aiohttp
from pydub import AudioSegment

from backend.config import settings
from backend.utils.text_cleaner import clean_for_tts

logger = logging.getLogger(__name__)


class TTSError(Exception):
    pass


class KokoroTTS:
    def __init__(self):
        self.base_url = settings.KOKORO_URL
        self.max_retries = settings.TTS_MAX_RETRIES
        self.retry_delays = settings.TTS_RETRY_DELAYS
        self.semaphore = asyncio.Semaphore(settings.TTS_MAX_CONCURRENT)

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def generate_speech(
        self,
        text: str,
        voice: str = "pf_dora",
        speed: float = 1.0,
        sample_rate: int = 44100,
    ) -> bytes:
        cleaned_text = clean_for_tts(text)

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/v1/audio/speech",
                        json={
                            "input": cleaned_text,
                            "voice": voice,
                            "model": "kokoro",
                            "response_format": "mp3",
                        },
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            raise TTSError(f"Kokoro error: {resp.status} - {body}")

                        audio_data = await resp.read()
                        logger.debug(f"TTS gerado: {len(audio_data)} bytes")
                        return audio_data

            except asyncio.TimeoutError:
                logger.warning(f"Tentativa {attempt + 1} timeout")
            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")

            if attempt < self.max_retries - 1:
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                await asyncio.sleep(delay)

        raise TTSError(f"Falha após {self.max_retries} tentativas")

    def _split_into_chunks(self, text: str, max_chars: int = 300) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        chunks = []
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) + 1 > max_chars:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text[:max_chars]]

    def apply_crossfade(
        self, audio1: AudioSegment, audio2: AudioSegment, ms: int = 30
    ) -> AudioSegment:
        return audio1.append(audio2, crossfade=ms)


class TTSOrchestrator:
    def __init__(self):
        self.kokoro = KokoroTTS()
        self.sample_rate = settings.AUDIO_SAMPLE_RATE

    def _estimate_duration_ms(self, text: str) -> int:
        words_per_second = 2.5
        word_count = len(text.split())
        estimated_seconds = word_count / words_per_second
        return int(estimated_seconds * 1000)

    async def generate_speech_with_retry(
        self, text: str, voice: str, speed: float = 1.0
    ) -> AudioSegment:
        chunks = self.kokoro._split_into_chunks(text)

        if len(chunks) == 1:
            audio_data = await self.kokoro.generate_speech(
                text, voice, speed, self.sample_rate
            )
            return AudioSegment.from_mp3(io.BytesIO(audio_data))

        segments = []
        for i, chunk in enumerate(chunks):
            logger.debug(f"Gerando chunk {i + 1}/{len(chunks)}")
            audio_data = await self.kokoro.generate_speech(
                chunk, voice, speed, self.sample_rate
            )
            segment = AudioSegment.from_mp3(io.BytesIO(audio_data))
            segments.append(segment)

        result = segments[0]
        for segment in segments[1:]:
            result = self.kokoro.apply_crossfade(result, segment, settings.CROSSFADE_MS)

        return result

    async def process_script(self, script: dict, output_dir: Path, job_id: str) -> dict:
        segments = script.get("segments", [])
        total_segments = len(segments)

        if total_segments == 0:
            raise ValueError("Script sem segmentos")

        output_dir.mkdir(parents=True, exist_ok=True)

        default_voice = "pm_alex"

        tasks = []
        for i, segment in enumerate(segments):
            speaker = segment.get("speaker", "Host").lower()
            voice = None

            if speaker != "host" and script.get("voice_cohost"):
                voice = script.get("voice_cohost")
            elif script.get("voice_host"):
                voice = script.get("voice_host")

            if not voice:
                voice = default_voice

            logger.info(f"Segmento {i}: speaker={speaker}, voice={voice}")

            task = self._process_segment(
                segment=segment,
                voice=voice,
                index=i,
                output_dir=output_dir,
                job_id=job_id,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_segments = []
        failed_segments = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Segmento {i} falhou: {result}")
                estimated_duration = self._estimate_duration_ms(
                    segments[i].get("text", "")
                )

                failed_segments.append(
                    {
                        "index": i,
                        "error": str(result),
                        "speaker": segments[i].get("speaker"),
                        "text": segments[i].get("text", "")[:100],
                        "estimated_duration_ms": estimated_duration,
                        "used_silence_fallback": True,
                    }
                )

                silence_path = output_dir / f"{job_id}_segment_{i:03d}.mp3"
                silence = AudioSegment.silent(duration=estimated_duration)
                silence.export(
                    str(silence_path), format="mp3", bitrate=settings.AUDIO_BITRATE
                )

                processed_segments.append(
                    {
                        "index": i,
                        "success": True,
                        "output_path": str(silence_path),
                        "duration_ms": estimated_duration,
                        "speaker": segments[i].get("speaker"),
                        "pause_after_ms": segments[i].get("pause_after_ms", 600),
                        "silence_fallback": True,
                    }
                )
            else:
                processed_segments.append(result)

        processed_segments.sort(key=lambda x: x["index"])

        logger.info(f"Processados {len(processed_segments)}/{total_segments} segmentos")

        return {
            "processed_segments": processed_segments,
            "failed_segments": failed_segments,
            "total_segments": total_segments,
            "success": len(processed_segments) > 0,
        }

    async def _process_segment(
        self, segment: dict, voice: str, index: int, output_dir: Path, job_id: str
    ) -> dict:
        async with self.kokoro.semaphore:
            text = segment.get("text", "")
            if not text:
                return {"index": index, "success": False, "error": "Texto vazio"}

            start_time = datetime.now(timezone.utc)

            try:
                audio = await self.generate_speech_with_retry(text=text, voice=voice)

                output_path = output_dir / f"{job_id}_segment_{index:03d}.mp3"
                audio.export(
                    str(output_path), format="mp3", bitrate=settings.AUDIO_BITRATE
                )

                duration_ms = len(audio)
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

                logger.info(
                    f"Segmento {index} gerado em {elapsed:.2f}s ({duration_ms}ms)"
                )

                return {
                    "index": index,
                    "success": True,
                    "output_path": str(output_path),
                    "duration_ms": duration_ms,
                    "generation_time_seconds": elapsed,
                    "speaker": segment.get("speaker"),
                    "pause_after_ms": segment.get("pause_after_ms", 600),
                }

            except Exception as e:
                logger.error(f"Segmento {index} falhou: {e}")
                return {"index": index, "success": False, "error": str(e)}


def get_pause_duration(segment: dict, prev_segment: dict | None) -> int:
    if prev_segment is None:
        return 2000

    current_speaker = segment.get("speaker", "").lower()
    prev_speaker = prev_segment.get("speaker", "").lower()

    if current_speaker != prev_speaker:
        return settings.PAUSE_DIFFERENT_SPEAKER_MS

    pause_marker = segment.get("pause_marker", "")
    if pause_marker == "PAUSA_LONGA":
        return settings.PAUSE_LONG_MS
    elif pause_marker == "PAUSA_CURTA":
        return settings.PAUSE_SHORT_MS

    return settings.PAUSE_SAME_SPEAKER_MS
