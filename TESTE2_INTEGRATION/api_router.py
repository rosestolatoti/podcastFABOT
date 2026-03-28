"""
api_router.py — Roteador de APIs com fallback automático.

Ordem: GLM-5 (NVIDIA) → Kimi K2.5 (NVIDIA) → MiniMax M2.5 (NVIDIA)

Responsabilidades:
  - Tentar cada API em sequência quando a anterior falha
  - Backoff exponencial entre tentativas
  - Retornar a resposta e qual API foi usada
  - Logar falhas sem interromper o fluxo
  - Validar que a resposta é JSON quando solicitado

NÃO faz:
  - Parse do JSON de negócio (responsabilidade do chamador)
  - Lógica de prompt (responsabilidade do chamador)
  - Salvamento em disco
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DAS APIs
# ═══════════════════════════════════════════════════════════════

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

API_CONFIGS = [
    {
        "nome": "GLM-5",
        "model": "z-ai/glm5",
        "api_key": os.getenv(
            "NVIDIA_KEY_GLM",
            "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",
        ),
        "max_tokens": 12000,
        "temperature": 0.88,
        "timeout": 240,
    },
    {
        "nome": "Kimi-K2.5",
        "model": "moonshotai/kimi-k2.5",
        "api_key": os.getenv(
            "NVIDIA_KEY_KIMI",
            "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",
        ),
        "max_tokens": 12000,
        "temperature": 0.88,
        "timeout": 240,
    },
    {
        "nome": "MiniMax-M2.5",
        "model": "minimaxai/minimax-m2.5",
        "api_key": os.getenv(
            "NVIDIA_KEY_MINIMAX",
            "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",
        ),
        "max_tokens": 8000,
        "temperature": 0.88,
        "timeout": 180,
    },
]

# Backoff em segundos entre tentativas: [primeira, segunda, terceira]
BACKOFF_SEGUNDOS = [5, 15, 30]

# Máximo de tentativas por API antes de desistir e trocar
MAX_TENTATIVAS_POR_API = 2


# ═══════════════════════════════════════════════════════════════
# RESULTADO
# ═══════════════════════════════════════════════════════════════

@dataclass
class RespostaAPI:
    texto: str
    api_nome: str
    model: str
    tokens_estimados: int = 0
    tentativas_total: int = 1


# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def _extrair_json(texto: str) -> str:
    """
    Remove markdown code fences e retorna o JSON limpo.
    Tenta também encontrar o primeiro objeto/array JSON na string.
    """
    texto = texto.strip()

    # Remove ```json ... ``` ou ``` ... ```
    if "```json" in texto:
        partes = texto.split("```json")
        if len(partes) > 1:
            texto = partes[1].split("```")[0].strip()
            return texto
    if "```" in texto:
        partes = texto.split("```")
        if len(partes) > 1:
            texto = partes[1].strip()
            return texto

    # Tenta encontrar { ... } ou [ ... ] mais externo
    for inicio_char, fim_char in [('{', '}'), ('[', ']')]:
        inicio = texto.find(inicio_char)
        fim = texto.rfind(fim_char)
        if inicio != -1 and fim != -1 and fim > inicio:
            candidato = texto[inicio:fim + 1]
            try:
                json.loads(candidato)
                return candidato
            except json.JSONDecodeError:
                pass

    return texto


def _validar_json(texto: str) -> Optional[dict | list]:
    """Tenta parsear o texto como JSON. Retorna None se falhar."""
    limpo = _extrair_json(texto)
    try:
        return json.loads(limpo)
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def chamar_llm(
    system_prompt: str,
    user_prompt: str,
    esperar_json: bool = True,
    temperature_override: Optional[float] = None,
    max_tokens_override: Optional[int] = None,
) -> RespostaAPI:
    """
    Chama o LLM com fallback automático entre as 3 APIs configuradas.

    Args:
        system_prompt: Instrução de sistema (o papel do LLM).
        user_prompt: A tarefa específica desta chamada.
        esperar_json: Se True, valida que a resposta é JSON válido.
                      Se a resposta não for JSON, trata como falha e tenta próxima API.
        temperature_override: Sobrescreve temperatura de todas as APIs.
        max_tokens_override: Sobrescreve max_tokens de todas as APIs.

    Returns:
        RespostaAPI com o texto da resposta e metadados.

    Raises:
        RuntimeError: Se todas as APIs falharem após todas as tentativas.
    """
    tentativas_total = 0
    falhas: list[str] = []

    for idx_api, config in enumerate(API_CONFIGS):
        nome_api = config["nome"]
        client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=config["api_key"],
        )

        temperature = temperature_override or config["temperature"]
        max_tokens = max_tokens_override or config["max_tokens"]

        for tentativa in range(1, MAX_TENTATIVAS_POR_API + 1):
            tentativas_total += 1
            logger.info(
                f"[API] Tentativa {tentativa}/{MAX_TENTATIVAS_POR_API} "
                f"via {nome_api} (total: {tentativas_total})"
            )

            try:
                completion = client.chat.completions.create(
                    model=config["model"],
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=config["timeout"],
                )

                texto = completion.choices[0].message.content or ""
                tokens = completion.usage.total_tokens if completion.usage else 0

                if not texto.strip():
                    raise ValueError("Resposta vazia recebida da API")

                # Valida JSON se necessário
                if esperar_json:
                    parsed = _validar_json(texto)
                    if parsed is None:
                        raise ValueError(
                            f"Resposta não é JSON válido. "
                            f"Preview: {texto[:200]}"
                        )
                    # Retorna o JSON limpo (sem fences)
                    texto = _extrair_json(texto)

                logger.info(
                    f"[API] ✅ Sucesso via {nome_api} "
                    f"({tokens} tokens, tentativas: {tentativas_total})"
                )
                return RespostaAPI(
                    texto=texto,
                    api_nome=nome_api,
                    model=config["model"],
                    tokens_estimados=tokens,
                    tentativas_total=tentativas_total,
                )

            except (APITimeoutError, APIConnectionError) as e:
                msg = f"{nome_api} tentativa {tentativa}: timeout/conexão — {e}"
                logger.warning(f"[API] ⚠️ {msg}")
                falhas.append(msg)

            except RateLimitError as e:
                msg = f"{nome_api} tentativa {tentativa}: rate limit — {e}"
                logger.warning(f"[API] ⚠️ {msg}")
                falhas.append(msg)
                # Rate limit: esperar mais antes de trocar de API
                time.sleep(30)
                break  # Vai direto para próxima API

            except ValueError as e:
                msg = f"{nome_api} tentativa {tentativa}: resposta inválida — {e}"
                logger.warning(f"[API] ⚠️ {msg}")
                falhas.append(msg)

            except Exception as e:
                msg = f"{nome_api} tentativa {tentativa}: erro inesperado — {type(e).__name__}: {e}"
                logger.error(f"[API] ❌ {msg}")
                falhas.append(msg)

            # Backoff antes de repetir ou trocar API
            backoff = BACKOFF_SEGUNDOS[min(tentativa - 1, len(BACKOFF_SEGUNDOS) - 1)]
            if tentativa < MAX_TENTATIVAS_POR_API:
                logger.info(f"[API] Aguardando {backoff}s antes de tentar novamente...")
                time.sleep(backoff)

        # Backoff entre APIs diferentes
        if idx_api < len(API_CONFIGS) - 1:
            prox_api = API_CONFIGS[idx_api + 1]["nome"]
            logger.info(f"[API] Trocando para {prox_api}...")
            time.sleep(10)

    # Todas as APIs falharam
    resumo_falhas = "\n  ".join(falhas)
    raise RuntimeError(
        f"Todas as APIs falharam após {tentativas_total} tentativas.\n"
        f"Falhas:\n  {resumo_falhas}"
    )


def chamar_llm_simples(prompt: str, temperature: float = 0.3) -> RespostaAPI:
    """
    Versão simplificada para chamadas que não precisam de system prompt.
    Útil para tarefas simples como classificação ou extração rápida.
    """
    return chamar_llm(
        system_prompt="Você é um assistente preciso que segue instruções exatamente.",
        user_prompt=prompt,
        esperar_json=False,
        temperature_override=temperature,
    )
