"""
Script para importar podcasts prontos para o banco de dados do FABOT
"""

import json
import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime

# Configuração
FABOT_DIR = Path("/home/fabiorjvr/Área de trabalho/ELEVENLABS2/fabot-studio")
OUTPUT_DIR = FABOT_DIR / "data" / "output"
DB_PATH = FABOT_DIR / "backend" / "db" / "fabot.db"

# Podcasts ML (tem roteiros em txt)
PODCASTS_ML = [
    {
        "title": "Machine Learning - 01 - O que é Machine Learning?",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/01_o_que_e_ml/01_o_que_e_ml.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/01_o_que_e_ml.txt",
        "category": "Machine Learning",
    },
    {
        "title": "Machine Learning - 02 - Dados",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/02_dados/02_dados.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/02_dados.txt",
        "category": "Machine Learning",
    },
    {
        "title": "Machine Learning - 03 - Regressão",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/03_regressao/03_regressao.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/03_regressao.txt",
        "category": "Machine Learning",
    },
    {
        "title": "Machine Learning - 04 - Classificação",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/04_classificacao/04_classificacao.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/04_classificacao.txt",
        "category": "Machine Learning",
    },
    {
        "title": "Machine Learning - 05 - Árvores de Decisão",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/05_arvores/05_arvores.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/05_arvores.txt",
        "category": "Machine Learning",
    },
    {
        "title": "Machine Learning - 06 - Deep Learning",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml_audio/06_deep_learning/06_deep_learning.mp3",
        "roteiro_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_ml/06_deep_learning.txt",
        "category": "Machine Learning",
    },
]

# Podcasts Python (não tem roteiro em txt)
PODCASTS_PYTHON = [
    {
        "title": "Python - 01 - Variáveis",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/01_variaveis.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 02 - Listas",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/02_listas.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 03 - Loops",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/03_loops.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 04 - If/Else",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/04_if_else.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 05 - Vetores",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/05_vetores.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 06 - Matrizes",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/06_matrizes.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 07 - Funções",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/07_funcoes.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 08 - Dicionários",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/08_dicionarios.mp3",
        "category": "Python",
    },
    {
        "title": "Python - 09 - Erros",
        "audio_src": "/home/fabiorjvr/Área de trabalho/ELEVENLABS2/podcasts_audio/09_erros.mp3",
        "category": "Python",
    },
]


def parse_roteiro_to_json(texto_path: Path) -> dict:
    """Converte roteiro de texto para JSON no formato do FABOT"""
    if not texto_path.exists():
        return None

    texto = texto_path.read_text(encoding="utf-8")
    linhas = texto.strip().split("\n")
    falas = []

    i = 0
    while i < len(linhas):
        linha = linhas[i].strip()

        speaker = None
        for sp in ["NARRADOR", "WILLIAM", "CRISTINA"]:
            if linha == f"[{sp}]":
                speaker = sp
                break

        if speaker:
            i += 1
            text_lines = []
            while i < len(linhas):
                next_linha = linhas[i].strip()
                if not next_linha:
                    i += 1
                    continue
                is_speaker = False
                for sp in ["NARRADOR", "WILLIAM", "CRISTINA"]:
                    if next_linha == f"[{sp}]":
                        is_speaker = True
                        break
                if is_speaker:
                    break
                text_lines.append(next_linha)
                i += 1

            text = " ".join(text_lines).strip()
            if text:
                falas.append({"speaker": speaker, "text": text, "pause_after_ms": 700})
        else:
            i += 1

    # Extrair título do roteiro
    title = "Podcast"
    for linha in linhas:
        if linha.startswith("Episódio"):
            title = linha.replace("Episódio", "Episódio").strip()
            break

    return {"title": title, "keywords": [], "segments": falas}


def get_audio_duration(audio_path: Path) -> int:
    """Get duration in seconds using pydub"""
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_mp3(str(audio_path))
        return len(audio) // 1000
    except:
        return 0


def import_podcasts():
    """Import all podcasts to the database"""
    import sqlite3

    # Conectar ao banco
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Verificar se a tabela existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    if not cursor.fetchone():
        print("❌ Tabela 'jobs' não existe!")
        return

    total_imported = 0

    # Importar ML Podcasts
    print("\n📚 Importando Machine Learning Podcasts...")
    for podcast in PODCASTS_ML:
        audio_src = Path(podcast["audio_src"])
        roteiro_src = Path(podcast["roteiro_src"])

        if not audio_src.exists():
            print(f"  ❌ Áudio não encontrado: {audio_src}")
            continue

        # Criar pasta de output
        job_id = str(uuid.uuid4())
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Copiar áudio
        dest_audio = job_dir / "final.mp3"
        shutil.copy2(audio_src, dest_audio)

        # Parse roteiro
        roteiro_json = parse_roteiro_to_json(roteiro_src)

        # Get duration
        duration = get_audio_duration(dest_audio)

        # Inserir no banco
        cursor.execute(
            """
            INSERT INTO jobs (id, title, status, progress, current_step, script_json, audio_path, duration_seconds, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job_id,
                podcast["title"],
                "DONE",
                100,
                "Podcast importado",
                json.dumps(roteiro_json) if roteiro_json else None,
                str(dest_audio),
                duration,
                podcast["category"],
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )

        print(f"  ✅ {podcast['title']}")
        total_imported += 1

    # Importar Python Podcasts
    print("\n🐍 Importando Python Podcasts...")
    for podcast in PODCASTS_PYTHON:
        audio_src = Path(podcast["audio_src"])

        if not audio_src.exists():
            print(f"  ❌ Áudio não encontrado: {audio_src}")
            continue

        # Criar pasta de output
        job_id = str(uuid.uuid4())
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Copiar áudio
        dest_audio = job_dir / "final.mp3"
        shutil.copy2(audio_src, dest_audio)

        # Get duration
        duration = get_audio_duration(dest_audio)

        # Inserir no banco (sem roteiro)
        cursor.execute(
            """
            INSERT INTO jobs (id, title, status, progress, current_step, audio_path, duration_seconds, category, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                job_id,
                podcast["title"],
                "DONE",
                100,
                "Podcast importado",
                str(dest_audio),
                duration,
                podcast["category"],
                datetime.now().isoformat(),
                datetime.now().isoformat(),
            ),
        )

        print(f"  ✅ {podcast['title']}")
        total_imported += 1

    conn.commit()
    conn.close()

    print(f"\n🎉 Total importado: {total_imported} podcasts!")
    print(f"📁 Áudios salvos em: {OUTPUT_DIR}")


if __name__ == "__main__":
    import_podcasts()
