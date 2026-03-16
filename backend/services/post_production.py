import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pyloudnorm as pln
import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.scipy_effects import high_pass_filter

from backend.config import settings

logger = logging.getLogger(__name__)


class PostProductionError(Exception):
    pass


def compress_audio(
    audio: AudioSegment,
    threshold_db: float = -20.0,
    ratio: float = 2.5,
    attack_ms: float = 20,
    release_ms: float = 150,
) -> AudioSegment:
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    sample_rate = audio.frame_rate

    if audio.channels == 2:
        samples = samples.reshape((-1, 2))

    threshold_linear = 10 ** (threshold_db / 20)
    attack_coef = np.exp(-1.0 / (attack_ms * sample_rate / 1000))
    release_coef = np.exp(-1.0 / (release_ms * sample_rate / 1000))

    gain = np.ones(len(samples))
    envelope = np.zeros(len(samples))

    for i in range(1, len(samples)):
        if audio.channels == 2:
            sample_level = np.max(np.abs(samples[i]))
        else:
            sample_level = np.abs(samples[i])

        if sample_level > threshold_linear:
            target = 1.0
        else:
            target = sample_level / threshold_linear

        if target > envelope[i - 1]:
            envelope[i] = attack_coef * envelope[i - 1] + (1 - attack_coef) * target
        else:
            envelope[i] = release_coef * envelope[i - 1] + (1 - release_coef) * target

        if envelope[i] > 0:
            gain[i] = 1.0 / envelope[i]

    gain = np.clip(gain, 1.0 / ratio, ratio)

    if audio.channels == 2:
        samples = samples * gain[:, np.newaxis]
    else:
        samples = samples * gain

    samples = np.clip(samples, -32768, 32767)
    compressed = samples.astype(np.int16)

    return audio._spawn(compressed)


def apply_limiter(audio: AudioSegment, max_db: float = -1.0) -> AudioSegment:
    if audio.max_dBFS > max_db:
        gain_needed = max_db - audio.max_dBFS
        audio = audio.apply_gain(gain_needed)
    return audio


def measure_loudness(audio: AudioSegment) -> float:
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    sample_rate = audio.frame_rate

    if audio.channels == 2:
        samples = samples.reshape((-1, 2))

    meter = pln.Meter(sample_rate)
    loudness = meter.integrated_loudness(samples)

    return loudness


def normalize_loudness(audio: AudioSegment, target_lufs: float = -16.0) -> AudioSegment:
    samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
    samples = samples / 32768.0  # Normalizar para -1 a 1
    sample_rate = audio.frame_rate

    if audio.channels == 2:
        samples = samples.reshape((-1, 2))

    meter = pln.Meter(sample_rate)
    loudness = meter.integrated_loudness(samples)

    if loudness <= -70:
        logger.warning(f"Loudness muito baixo ({loudness}), pulando normalização")
        return audio

    gain_db = target_lufs - loudness
    gain_linear = 10 ** (gain_db / 20)

    samples = samples * gain_linear
    samples = np.clip(samples, -1.0, 1.0)

    normalized = (samples * 32767).astype(np.int16)
    if audio.channels == 2:
        normalized = normalized.reshape((-1,))

    return audio._spawn(normalized)


def apply_fade(
    audio: AudioSegment, fade_in_ms: int = 1500, fade_out_ms: int = 3000
) -> AudioSegment:
    if len(audio) > fade_in_ms:
        audio = audio.fade_in(fade_in_ms)
    else:
        audio = audio.fade_in(len(audio) // 2)

    if len(audio) > fade_out_ms:
        audio = audio.fade_out(fade_out_ms)
    else:
        audio = audio.fade_out(len(audio) // 2)

    return audio


def apply_vinheta_with_ducking(
    audio: AudioSegment,
    vinheta_path: str,
    ducking_db: float = -12.0,
    vinheta_duration_ms: int = 5000,
) -> AudioSegment:
    try:
        vinheta = AudioSegment.from_mp3(vinheta_path)
        vinheta = vinheta[:vinheta_duration_ms]

        main_audio_start = audio[:vinheta_duration_ms].apply_gain(ducking_db)
        audio = main_audio_start + audio[vinheta_duration_ms:]

        audio = vinheta.overlay(audio, position=0)

        logger.info(f"Vinheta aplicada com ducking {ducking_db}dB")
    except Exception as e:
        logger.warning(f"Falha ao aplicar vinheta: {e}")

    return audio


class PostProductionPipeline:
    def __init__(self):
        self.lufs_target = settings.LUFS_TARGET
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.bitrate = settings.AUDIO_BITRATE
        self.channels = settings.AUDIO_CHANNELS

    def process(
        self,
        input_segments: list,
        output_path: Path,
        job_id: str,
        include_vinheta: bool = False,
        vinheta_path: str = None,
    ) -> dict:
        logger.info(f"Iniciando pós-produção para job {job_id}")

        if not input_segments:
            raise PostProductionError("Nenhum segmento para processar")

        audio = AudioSegment.empty()

        for i, segment in enumerate(input_segments):
            if not segment.get("success", False):
                logger.warning(f"Segmento {i} marcado como falha, pulando")
                continue

            seg_path = Path(segment["output_path"])
            if not seg_path.exists():
                logger.warning(f"Arquivo de segmento não encontrado: {seg_path}")
                continue

            seg_audio = AudioSegment.from_mp3(str(seg_path))

            pause_ms = segment.get("pause_after_ms", 600)
            pause = AudioSegment.silent(duration=pause_ms)

            audio += seg_audio + pause
            logger.debug(
                f"Segmento {i} adicionado: {len(seg_audio)}ms + {pause_ms}ms pause"
            )

        if len(audio) == 0:
            raise PostProductionError("Nenhum áudio válido após processamento")

        logger.info("Etapa 1: Normalização loudness (LUFS true)")
        audio = normalize_loudness(audio, target_lufs=self.lufs_target)

        logger.info("Etapa 2: Compressão dinâmica (attack 20ms, release 150ms)")
        audio = compress_audio(
            audio, threshold_db=-20.0, ratio=2.5, attack_ms=20, release_ms=150
        )

        logger.info("Etapa 3: High-pass filter 80Hz")
        audio = high_pass_filter(audio, cutoff_freq=80)

        logger.info("Etapa 4: Limiter -1dBFS")
        audio = apply_limiter(audio, max_db=-1.0)

        logger.info("Etapa 5: Fade in/out")
        audio = apply_fade(audio, fade_in_ms=1500, fade_out_ms=3000)

        if include_vinheta and vinheta_path:
            logger.info("Etapa 6: Vinheta com ducking")
            audio = apply_vinheta_with_ducking(audio, vinheta_path)

        logger.info(f"Etapa 7: Export MP3 {self.bitrate}, {self.sample_rate}Hz, stereo")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio.export(
            str(output_path),
            format="mp3",
            bitrate=self.bitrate,
            parameters=["-ar", str(self.sample_rate), "-ac", str(self.channels)],
        )

        final_lufs = measure_loudness(audio)
        duration_seconds = len(audio) / 1000

        metadata = {
            "job_id": job_id,
            "output_path": str(output_path),
            "duration_seconds": duration_seconds,
            "duration_formatted": f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}",
            "lufs_measured": round(final_lufs, 2),
            "target_lufs": self.lufs_target,
            "num_segments": len(input_segments),
            "num_successful": sum(1 for s in input_segments if s.get("success", False)),
            "bitrate": self.bitrate,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

        metadata_path = output_path.parent / f"{job_id}_production.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Pós-produção concluída: {duration_seconds:.1f}s, LUFS {final_lufs:.1f}"
        )

        return metadata
