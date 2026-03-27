"""
FABOT Podcast Studio — fabot_tts.py v2.0
Motor de síntese de voz com Edge TTS

Palavras-chave de ênfase são DINÂMICAS — vêm do JSON gerado pelo LLM.
Nenhuma lista hardcoded. Funciona para qualquer assunto.
"""

import asyncio
import re
import logging
from pathlib import Path
import edge_tts
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DAS VOZES — baseada no GÊNERO
# Narrador = Thalita (feminina, abertura)
# Masculino = Antonio (apresentador)
# Feminino = Francisca (explicadora)
# ─────────────────────────────────────────────────────────────────

VOICES = {
    "NARRADOR": {
        "voice": "pt-BR-ThalitaMultilingualNeural",
        "rate": "-5%",
        "pitch": "+0Hz",
    },
    "MASCULINO": {
        "voice": "pt-BR-AntonioNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
    },
    "FEMININO": {
        "voice": "pt-BR-FranciscaNeural",
        "rate": "+5%",
        "pitch": "+0Hz",
    },
}

# Nomes que indicam gênero feminino (terminam com 'a' ou são conhecidos femininos)
FEMININO_NAMES = {
    "ana",
    "maria",
    "joana",
    "cristina",
    "vilma",
    "patricia",
    "fernanda",
    "suelen",
    "rebecca",
    "rebeca",
    "beatriz",
    "fernanda",
    "lucia",
    "paula",
    "julia",
    "diana",
    "carla",
    "priscila",
    "aline",
    "bruna",
    "vanessa",
    "debora",
    "roberta",
    "fatima",
    "simone",
    "tatiana",
    "livia",
    "gabriela",
}


def get_voice_for_speaker(speaker: str) -> dict:
    """
    Determina a voz baseada no nome do speaker.
    Usa o género implícito no nome para selecionar a voz correta.
    """
    speaker_upper = speaker.upper()

    # NARRADOR sempre usa Thalita
    if speaker_upper == "NARRADOR":
        return VOICES["NARRADOR"].copy()

    # Verificar por nome conhecido
    speaker_lower = speaker.lower().strip()

    # Nomes femininos conhecidos
    if speaker_lower in FEMININO_NAMES:
        return VOICES["FEMININO"].copy()

    # Nomes que terminam com 'a' são geralmente femininos em português
    if speaker_lower.endswith("a") and len(speaker_lower) > 2:
        return VOICES["FEMININO"].copy()

    # Padrões especiais para masculino
    masculino_patterns = [
        "william",
        "antonio",
        "daniel",
        "pedro",
        "marcos",
        "joao",
        "joão",
        "rafael",
        "bruno",
        "gabriel",
        "lucas",
        "matheus",
        "felipe",
        "rogerio",
        "roger",
        "rogerio",
        "jorge",
        "eduardo",
    ]

    if speaker_lower in masculino_patterns:
        return VOICES["MASCULINO"].copy()

    # Default: usa masculino para nomes que não reconhece
    # (evita silêncio se vier nome inesperado)
    return VOICES["MASCULINO"].copy()


# ─────────────────────────────────────────────────────────────────
# PAUSAS — fixo, não muda por assunto
# ─────────────────────────────────────────────────────────────────

PAUSES = {
    "same_speaker": 300,
    "between_speakers": 550,
    "after_confirm": 700,
    "block_transition": 1200,
    "after_narrador": 1800,
    "end_of_episode": 2000,
}

# ─────────────────────────────────────────────────────────────────
# SSML — constrói marcação de voz com keywords dinâmicas
# ─────────────────────────────────────────────────────────────────


def build_ssml(text: str, speaker: str, keywords: list[str]) -> dict:
    """
    Prepara o texto e configurações para o Edge TTS.
    Usa mapeamento dinâmico por gênero para escolher a voz.
    """
    config = get_voice_for_speaker(speaker)

    processed = _apply_emphasis(text, keywords)
    processed = processed.replace("...", "").strip()

    return {
        "text": processed,
        "voice": config["voice"],
        "rate": config["rate"],
        "pitch": config["pitch"],
    }


def _apply_emphasis(text: str, keywords: list[str]) -> str:
    """
    Aplica ênfase nas palavras-chave recebidas do LLM.
    Ordena do maior pro menor para evitar sobreposição.
    """
    if not keywords:
        return text

    for kw in sorted(keywords, key=len, reverse=True):
        escaped = re.escape(kw)
        # Só marca se não estiver já dentro de uma tag SSML
        pattern = r"(?<![>=])(" + escaped + r")(?![^<]*>)"
        replacement = r'<emphasis level="moderate">\1</emphasis>'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text


# ─────────────────────────────────────────────────────────────────
# LIMPEZA DE ARQUIVOS TEMPORÁRIOS
# ─────────────────────────────────────────────────────────────────


def cleanup_segments(output_dir: Path) -> int:
    """Remove arquivos temporários de segmento após concatenação."""
    import glob
    import os

    pattern = os.path.join(output_dir, "seg_*.mp3")
    files = glob.glob(pattern)

    removed = 0
    for f in files:
        try:
            os.remove(f)
            removed += 1
        except Exception as e:
            logger.warning(f"Não foi possível remover {f}: {e}")

    return removed


# ─────────────────────────────────────────────────────────────────
# SÍNTESE DE UM SEGMENTO
# ─────────────────────────────────────────────────────────────────


async def synthesize_segment(
    text: str,
    speaker: str,
    keywords: list[str],
    output_path: Path,
    timeout: float = 30.0,
) -> Path:
    """Gera o MP3 de um segmento com Edge TTS com timeout."""
    config = build_ssml(text, speaker, keywords)
    communicate = edge_tts.Communicate(
        config["text"], config["voice"], rate=config["rate"], pitch=config["pitch"]
    )

    audio_data = b""
    try:
        async with asyncio.timeout(timeout):
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
    except asyncio.TimeoutError:
        logger.error(f"Timeout ({timeout}s) ao sintetizar: {text[:50]}...")
        raise TimeoutError(f"Edge TTS timeout após {timeout}s no segmento: {text[:50]}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_data)
    return output_path


# ─────────────────────────────────────────────────────────────────
# MONTAGEM DO EPISÓDIO COMPLETO
# ─────────────────────────────────────────────────────────────────


async def build_episode(
    script: dict,
    output_dir: Path,
    job_id: str,
    on_progress=None,
) -> Path:
    """
    Recebe o script JSON do LLM e monta o MP3 final.

    O script deve ter:
      - title: str
      - keywords: list[str]   ← palavras-chave do assunto, geradas pelo LLM
      - segments: list[dict]

    Cada segment:
      - speaker: "NARRADOR" | "William" | "Cristina"
      - text: str
      - pause_after_ms: int
      - block_transition: bool
    """
    segments = script.get("segments", [])
    keywords = script.get("keywords", [])  # ← dinâmico, vem do LLM
    total = len(segments)

    logger.info("Assunto: %s", script.get("title", "?"))
    logger.info("Palavras-chave identificadas pelo LLM: %s", keywords)
    logger.info("Segmentos: %d", total)

    # ── Gera segmentos em PARALELO ─────────────────────────────
    # Máximo de 5 requisições simultâneas ao Edge TTS
    semaphore = asyncio.Semaphore(5)

    async def synth_with_semaphore(i: int, seg: dict) -> dict | None:
        speaker = seg.get("speaker", "William")
        text = seg.get("text", "").strip()
        if not text:
            return None

        seg_path = output_dir / f"seg_{i:03d}_{speaker.lower()}.mp3"

        async with semaphore:
            try:
                logger.info("  [%d/%d] %s: %s...", i + 1, total, speaker, text[:55])
                await synthesize_segment(text, speaker, keywords, seg_path)
            except Exception as e:
                logger.error(f"Erro ao sintetizar segmento {i}: {e}")
                raise

        return {
            "path": seg_path,
            "speaker": speaker,
            "pause_after_ms": seg.get("pause_after_ms", PAUSES["between_speakers"]),
            "block_transition": seg.get("block_transition", False),
            "index": i,
        }

    # Dispara TODOS os segmentos em paralelo
    tasks = [synth_with_semaphore(i, seg) for i, seg in enumerate(segments)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filtra resultados (remove None e exceções)
    segment_files = [
        r for r in results if r is not None and not isinstance(r, Exception)
    ]
    segment_files.sort(key=lambda x: x["index"])

    failed = [r for r in results if isinstance(r, Exception)]
    if failed:
        logger.warning(f"{len(failed)} segmentos falharam na síntese")

    # Atualiza progresso para 85% após síntese
    if on_progress:
        on_progress(85, f"Voz gerada: {len(segment_files)}/{total} segmentos")

    # ── Concatena com pausas ────────────────────────────────────
    logger.info("Montando episódio...")
    episode = AudioSegment.silent(duration=1500)

    for i, seg in enumerate(segment_files):
        audio = AudioSegment.from_mp3(str(seg["path"]))
        audio = audio.fade_in(30)  # crossfade 30ms — elimina cliques
        episode += audio

        # Calcula pausa
        if seg["block_transition"]:
            pause_ms = PAUSES["block_transition"]
        elif seg["speaker"] == "NARRADOR":
            pause_ms = PAUSES["after_narrador"]
        elif i + 1 < len(segment_files):
            next_spk = segment_files[i + 1]["speaker"]
            curr_spk = seg["speaker"]
            if next_spk == curr_spk:
                pause_ms = seg["pause_after_ms"] or PAUSES["same_speaker"]
            else:
                pause_ms = seg["pause_after_ms"] or PAUSES["between_speakers"]
        else:
            pause_ms = PAUSES["end_of_episode"]

        episode += AudioSegment.silent(duration=pause_ms)

    episode += AudioSegment.silent(duration=2000)

    # ── Normalização de loudness para -16 LUFS ──────────────────
    try:
        from backend.services.post_production import normalize_loudness, apply_limiter
        from backend.config import settings as _settings

        logger.info("Normalizando loudness para %s LUFS...", _settings.LUFS_TARGET)
        episode = normalize_loudness(episode, target_lufs=_settings.LUFS_TARGET)
        episode = apply_limiter(episode, max_db=-1.0)
        logger.info("Loudness normalizado com sucesso")
    except Exception as e:
        logger.warning(
            "Normalização de loudness falhou, exportando sem normalizar: %s", e
        )

    # ── Exporta MP3 final ───────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "final.mp3"
    episode.export(
        str(final_path),
        format="mp3",
        bitrate="192k",
        parameters=["-ar", "44100", "-ac", "2"],
    )

    dur = len(episode) / 1000
    mb = final_path.stat().st_size / 1024 / 1024
    logger.info(
        "Episódio exportado: %s | %.0fs (%.1f min) | %.1f MB",
        final_path,
        dur,
        dur / 60,
        mb,
    )

    # ── Cleanup arquivos temporários ───────────────────────────
    if final_path.exists() and final_path.stat().st_size > 0:
        removed = cleanup_segments(output_dir)
        if removed > 0:
            logger.info("Cleanup: %d arquivos temp removidos", removed)

    return final_path
