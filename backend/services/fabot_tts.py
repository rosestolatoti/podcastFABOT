"""
FABOT Podcast Studio — fabot_tts.py v2.0
Motor de síntese de voz com Edge TTS

Palavras-chave de ênfase são DINÂMICAS — vêm do JSON gerado pelo LLM.
Nenhuma lista hardcoded. Funciona para qualquer assunto.
"""

import asyncio
import re
from pathlib import Path
import edge_tts
from pydub import AudioSegment

# ─────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO DAS VOZES — 3 vozes diferentes
# Narrador/Introdução = Thalita (feminina, abertura)
# William = Antonio (masculino, apresentador)
# Cristina = Francisca (feminina, explicadora)
# ─────────────────────────────────────────────────────────────────

VOICES = {
    "NARRADOR": {
        "voice": "pt-BR-ThalitaMultilingualNeural",
        "rate": "-5%",
        "pitch": "+0Hz",
    },
    "William": {
        "voice": "pt-BR-AntonioNeural",
        "rate": "+10%",
        "pitch": "+0Hz",
    },
    "Cristina": {
        "voice": "pt-BR-FranciscaNeural",
        "rate": "+5%",
        "pitch": "+0Hz",
    },
}

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


def build_ssml(text: str, speaker: str, keywords: list[str]) -> str:
    """
    Monta o SSML para o Edge TTS.
    Keywords são passadas dinamicamente — vêm do JSON do LLM.
    Funciona para qualquer assunto.
    """
    config = VOICES.get(speaker, VOICES["William"])

    processed = _apply_emphasis(text, keywords)
    processed = processed.replace("...", '<break time="500ms"/>')

    return f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="pt-BR">
  <voice name="{config["voice"]}">
    <prosody rate="{config["rate"]}" pitch="{config["pitch"]}">
      {processed}
    </prosody>
  </voice>
</speak>"""


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
# SÍNTESE DE UM SEGMENTO
# ─────────────────────────────────────────────────────────────────


async def synthesize_segment(
    text: str,
    speaker: str,
    keywords: list[str],
    output_path: Path,
) -> Path:
    """Gera o MP3 de um segmento com Edge TTS."""
    ssml = build_ssml(text, speaker, keywords)
    communicate = edge_tts.Communicate(ssml, VOICES[speaker]["voice"])

    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]

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

    print(f"🎙️  Assunto: {script.get('title', '?')}")
    print(f"📌  Palavras-chave identificadas pelo LLM: {keywords}")
    print(f"🔢  Segmentos: {total}")
    print()

    # ── Gera segmentos ──────────────────────────────────────────
    segment_files = []
    for i, seg in enumerate(segments):
        speaker = seg.get("speaker", "William")
        text = seg.get("text", "").strip()
        if not text:
            continue

        seg_path = output_dir / f"seg_{i:03d}_{speaker.lower()}.mp3"
        print(f"  [{i + 1}/{total}] {speaker}: {text[:55]}...")

        await synthesize_segment(text, speaker, keywords, seg_path)

        segment_files.append(
            {
                "path": seg_path,
                "speaker": speaker,
                "pause_after_ms": seg.get("pause_after_ms", PAUSES["between_speakers"]),
                "block_transition": seg.get("block_transition", False),
                "index": i,
            }
        )

        if on_progress:
            on_progress(int(40 + (i / total) * 45), f"Gerando voz: {i + 1}/{total}")

    # ── Concatena com pausas ────────────────────────────────────
    print("\n🔧  Montando episódio...")
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

    # ── Exporta MP3 final ───────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"{job_id}_final.mp3"
    episode.export(
        str(final_path),
        format="mp3",
        bitrate="192k",
        parameters=["-ar", "44100", "-ac", "2"],
    )

    dur = len(episode) / 1000
    mb = final_path.stat().st_size / 1024 / 1024
    print(f"\n✅  {final_path}")
    print(f"    Duração: {dur:.0f}s ({dur / 60:.1f} min) | {mb:.1f} MB")

    return final_path
