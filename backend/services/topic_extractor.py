"""
FABOT Podcast Studio — topic_extractor.py

Extrai conceitos/tópicos de um texto sem usar LLM.
Usa análise local: headers Markdown, frequência de palavras, padrões.
Usado opcionalmente para sugestão automática (futuro).
O core da feature é seleção manual pelo usuário.
"""

import re
from collections import Counter
from dataclasses import dataclass


# Stop words em português + inglês comuns
STOP_WORDS = {
    "de",
    "a",
    "o",
    "que",
    "e",
    "do",
    "da",
    "em",
    "um",
    "para",
    "é",
    "com",
    "não",
    "uma",
    "os",
    "no",
    "se",
    "na",
    "por",
    "mais",
    "as",
    "dos",
    "como",
    "mas",
    "foi",
    "ao",
    "ele",
    "das",
    "tem",
    "à",
    "seu",
    "sua",
    "ou",
    "ser",
    "quando",
    "muito",
    "há",
    "nos",
    "já",
    "está",
    "eu",
    "também",
    "só",
    "pelo",
    "pela",
    "até",
    "isso",
    "ela",
    "entre",
    "era",
    "depois",
    "sem",
    "mesmo",
    "aos",
    "ter",
    "seus",
    "quem",
    "nas",
    "me",
    "esse",
    "eles",
    "estão",
    "você",
    "tinha",
    "foram",
    "essa",
    "num",
    "nem",
    "suas",
    "meu",
    "às",
    "minha",
    "têm",
    "numa",
    "pelos",
    "elas",
    "havia",
    "seja",
    "qual",
    "será",
    "nós",
    "tenho",
    "lhe",
    "deles",
    "essas",
    "esses",
    "pelas",
    "este",
    "fosse",
    "pode",
    "bem",
    "cada",
    "então",
    "sobre",
    "ainda",
    "todo",
    "toda",
    "todos",
    "todas",
    "outro",
    "outra",
    "outros",
    "outras",
    "aqui",
    "onde",
    "assim",
    "the",
    "is",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "into",
    "through",
    "during",
    "before",
    "after",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "you",
    "we",
    "they",
}


@dataclass
class TopicSuggestion:
    """Sugestão de tópico extraída do texto."""

    text: str  # texto do tópico
    source: str  # "header", "frequency", "pattern"
    score: float  # 0-1, maior = mais relevante
    position: int  # posição no texto (char index) para manter ordem


def extract_topics(text: str, max_topics: int = 10) -> list[TopicSuggestion]:
    """
    Extrai tópicos sugeridos de um texto.
    Retorna lista ordenada por posição no texto (sequencial).

    Prioridade:
      1. Headers Markdown (## e ###) — são divisores naturais
      2. Palavras capitalizadas frequentes — conceitos técnicos
      3. Padrões tipo "O que é X", "Definição de X"
    """
    topics = []
    seen = set()

    # ── 1. Headers Markdown (##, ###) ──
    for match in re.finditer(r"^(#{1,3})\s+(.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        title = match.group(2).strip()
        title_lower = title.lower()

        if title_lower not in seen and len(title) > 2:
            topics.append(
                TopicSuggestion(
                    text=title,
                    source="header",
                    score=1.0 if level <= 2 else 0.8,
                    position=match.start(),
                )
            )
            seen.add(title_lower)

    # ── 2. Palavras capitalizadas frequentes (se poucos headers) ──
    if len(topics) < 3:
        # Pega palavras que começam com maiúscula e têm 4+ letras
        words = re.findall(r"\b[A-ZÀ-Ú][a-zà-ú]{3,}\b", text)
        word_counts = Counter(w for w in words if w.lower() not in STOP_WORDS)

        for word, count in word_counts.most_common(max_topics):
            if word.lower() not in seen and count >= 3:
                # Posição da primeira ocorrência
                first_pos = text.index(word)
                topics.append(
                    TopicSuggestion(
                        text=word,
                        source="frequency",
                        score=min(count / 10, 0.9),
                        position=first_pos,
                    )
                )
                seen.add(word.lower())

    # ── 3. Padrões semânticos ──
    patterns = [
        r"[Oo]\s+que\s+(?:é|são)\s+(.+?)[\.?\n]",
        r"[Dd]efini(?:ção|r)\s+(?:de|do|da)\s+(.+?)[\.?\n]",
        r"[Cc]omo\s+funciona\s+(?:o|a|os|as)?\s*(.+?)[\.?\n]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            concept = match.group(1).strip()[:50]
            if concept.lower() not in seen and len(concept) > 2:
                topics.append(
                    TopicSuggestion(
                        text=concept,
                        source="pattern",
                        score=0.7,
                        position=match.start(),
                    )
                )
                seen.add(concept.lower())

    # Ordenar por posição no texto (manter ordem sequencial)
    topics.sort(key=lambda t: t.position)
    return topics[:max_topics]


def format_suggestions_report(topics: list[TopicSuggestion]) -> str:
    """Relatório legível das sugestões (para debug/log)."""
    if not topics:
        return "Nenhum tópico sugerido."

    lines = [
        f"{'=' * 50}",
        f"TÓPICOS SUGERIDOS — {len(topics)} encontrados",
        f"{'=' * 50}",
    ]
    for i, t in enumerate(topics, 1):
        lines.append(
            f"  {i:2d}. [{t.source:10s}] score={t.score:.1f} | pos={t.position:5d} | {t.text}"
        )
    lines.append(f"{'=' * 50}")
    return "\n".join(lines)
