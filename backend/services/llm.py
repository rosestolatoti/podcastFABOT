import asyncio
import hashlib
import json
import logging
import os
from typing import Any
from datetime import datetime, timezone
from functools import lru_cache

import aiohttp
import redis
from jinja2 import Template
from pydantic import BaseModel, ValidationError, field_validator

from backend.prompts.script_template_v5 import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from backend.config import settings

logger = logging.getLogger(__name__)


class SegmentSchema(BaseModel):
    speaker: str
    text: str
    emotion: str = "neutral"
    pause_after_ms: int = 600

    @field_validator("emotion")
    @classmethod
    def validate_emotion(cls, v):
        allowed = ["neutral", "animated", "calm", "serious", "enthusiastic"]
        if v not in allowed:
            return "neutral"
        return v

    @field_validator("text")
    @classmethod
    def validate_text(cls, v):
        words = v.split()
        if len(words) > 25:
            logger.warning(f"Fala com {len(words)} palavras, máximo 25")
        return v


class ScriptSchema(BaseModel):
    title: str = "Sem título"
    segments: list[SegmentSchema]
    generated_at: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None

    @field_validator("segments", mode="before")
    @classmethod
    def validate_segments(cls, v):
        if not v:
            raise ValueError("Segments não pode estar vazio")
        if len(v) > 200:
            raise ValueError("Muito segmentos (max 200)")
        return v


class RedisCacheManager:
    def __init__(self):
        self._client = None
        self.prefix = "fabot:llm_cache:"
        self.ttl = 86400 * 7

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = redis.Redis.from_url(
                    settings.REDIS_URL, decode_responses=True
                )
                self._client.ping()
            except Exception as e:
                logger.warning(f"Redis não disponível: {e}. Usando cache em memória.")
                self._client = None
        return self._client

    def _make_key(self, text_hash: str, config_hash: str) -> str:
        return f"{self.prefix}{text_hash[:16]}:{config_hash[:16]}"

    def get(self, text_hash: str, config_hash: str) -> dict | None:
        if self.client is None:
            return None

        try:
            key = self._make_key(text_hash, config_hash)
            data = self.client.get(key)
            if data:
                logger.info(f"Cache hit: {key}")
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Erro ao ler cache: {e}")
        return None

    def set(self, text_hash: str, config_hash: str, result: dict) -> None:
        if self.client is None:
            return

        try:
            key = self._make_key(text_hash, config_hash)
            self.client.setex(key, self.ttl, json.dumps(result))
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")


cache_manager = RedisCacheManager()


def compute_config_hash(config: dict) -> str:
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()


def validate_script_response(data: dict) -> ScriptSchema:
    try:
        return ScriptSchema(**data)
    except ValidationError as e:
        logger.error(f"Validação do script falhou: {e}")

        if "segments" in data and isinstance(data.get("segments"), list):
            cleaned_segments = []
            for seg in data["segments"]:
                if isinstance(seg, dict):
                    cleaned = {
                        "speaker": seg.get("speaker", "Host"),
                        "text": seg.get("text", "")[:200],
                        "emotion": seg.get("emotion", "neutral"),
                        "pause_after_ms": seg.get("pause_after_ms", 600),
                    }
                    if cleaned["text"]:
                        cleaned_segments.append(cleaned)

            if cleaned_segments:
                return ScriptSchema(
                    title=data.get("title", "Sem título"), segments=cleaned_segments
                )

        raise ValueError(f"Não foi possível validar o script: {e}")


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LLMProvider:
    async def generate_script(self, text: str, config: dict) -> dict:
        raise NotImplementedError

    async def health_check(self) -> bool:
        raise NotImplementedError


class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = "llama-3.3-70b-versatile"
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.max_retries = 3
        self.retry_delays = [1, 2, 4]

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def generate_script(self, text: str, config: dict) -> dict:
        text_hash = compute_text_hash(text)
        config_hash = compute_config_hash(config)

        cached = cache_manager.get(text_hash, config_hash)
        if cached:
            logger.info("Usando resultado em cache para este texto")
            return cached

        user_prompt = USER_PROMPT_TEMPLATE.render(
            text=text[:15000],
            target_duration=config.get("target_duration", 10),
            depth_level=config.get("depth_level", "normal"),
            podcast_type=config.get("podcast_type", "monologue"),
            voice_host=config.get("voice_host", ""),
            voice_cohost=config.get("voice_cohost", ""),
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 8000,
                            "response_format": {"type": "json_object"},
                        },
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status == 429:
                            delay = self.retry_delays[
                                min(attempt, len(self.retry_delays) - 1)
                            ]
                            logger.warning(
                                f"Rate limit. Tentando novamente em {delay}s"
                            )
                            await asyncio.sleep(delay)
                            continue

                        if resp.status != 200:
                            body = await resp.text()
                            raise Exception(f"Groq API error: {resp.status} - {body}")

                        result = await resp.json()
                        content = result["choices"][0]["message"]["content"]

                        try:
                            script_data = json.loads(content)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON inválido retornado: {e}")
                            raise ValueError(f"Resposta do LLM não é JSON válido")

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "groq"
                        script_dict["llm_model"] = self.model

                        cache_manager.set(text_hash, config_hash, script_dict)
                        logger.info(
                            f"Roteiro gerado com Groq: {len(script_dict.get('segments', []))} segmentos"
                        )
                        return script_dict

            except Exception as e:
                last_error = e
                delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                logger.warning(
                    f"Tentativa {attempt + 1} falhou: {e}. Retry em {delay}s"
                )
                await asyncio.sleep(delay)

        raise Exception(f"Falha após {self.max_retries} tentativas: {last_error}")


class GeminiProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-1.5-flash"
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}",
                    params={"key": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def generate_script(self, text: str, config: dict) -> dict:
        text_hash = compute_text_hash(text)
        config_hash = compute_config_hash(config)

        cached = cache_manager.get(text_hash, config_hash)
        if cached:
            logger.info("Usando resultado em cache para este texto")
            return cached

        user_prompt = USER_PROMPT_TEMPLATE.render(
            text=text[:15000],
            target_duration=config.get("target_duration", 10),
            depth_level=config.get("depth_level", "normal"),
            podcast_type=config.get("podcast_type", "monologue"),
            voice_host=config.get("voice_host", ""),
            voice_cohost=config.get("voice_cohost", ""),
        )

        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        params={"key": self.api_key},
                        json={
                            "contents": [{"parts": [{"text": full_prompt}]}],
                            "generationConfig": {
                                "temperature": 0.7,
                                "maxOutputTokens": 8000,
                                "responseMimeType": "application/json",
                            },
                        },
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            raise Exception(f"Gemini API error: {resp.status} - {body}")

                        result = await resp.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]

                        try:
                            script_data = json.loads(content)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON inválido retornado: {e}")
                            continue

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "gemini"
                        script_dict["llm_model"] = self.model

                        cache_manager.set(text_hash, config_hash, script_dict)
                        logger.info(
                            f"Roteiro gerado com Gemini: {len(script_dict.get('segments', []))} segmentos"
                        )
                        return script_dict

            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
                await asyncio.sleep(2)

        raise Exception(f"Falha após 3 tentativas com Gemini")


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = "llama3.1"

    async def health_check(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def generate_script(self, text: str, config: dict) -> dict:
        text_hash = compute_text_hash(text)
        config_hash = compute_config_hash(config)

        cached = cache_manager.get(text_hash, config_hash)
        if cached:
            logger.info("Usando resultado em cache para este texto")
            return cached

        user_prompt = USER_PROMPT_TEMPLATE.render(
            text=text[:15000],
            target_duration=config.get("target_duration", 10),
            depth_level=config.get("depth_level", "normal"),
            podcast_type=config.get("podcast_type", "monologue"),
            voice_host=config.get("voice_host", ""),
            voice_cohost=config.get("voice_cohost", ""),
            section_title=config.get("section_title", "Seção Principal"),
            episode_number=config.get("episode_number", 1),
            total_episodes=config.get("total_episodes", 1),
        )

        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}\n\nRetorne APENAS o JSON."

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/api/generate",
                        json={
                            "model": self.model,
                            "prompt": full_prompt,
                            "format": "json",
                            "stream": False,
                            "options": {"temperature": 0.7},
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            raise Exception(f"Ollama error: {resp.status} - {body}")

                        result = await resp.json()
                        content = result.get("response", "")

                        try:
                            script_data = json.loads(content)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON inválido retornado: {e}")
                            continue

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "ollama"
                        script_dict["llm_model"] = self.model

                        cache_manager.set(text_hash, config_hash, script_dict)
                        logger.info(
                            f"Roteiro gerado com Ollama: {len(script_dict.get('segments', []))} segmentos"
                        )
                        return script_dict

            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
                await asyncio.sleep(2)

        raise Exception(f"Falha após 3 tentativas com Ollama")


class GLMProvider(LLMProvider):
    """Provedor GLM (ChatGLM) - Modelos gratuitos"""

    def __init__(self):
        self.api_key = settings.GLM_API_KEY or "6b754c80b0a848909600eadaa4ee5818"
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self.model = "glm-4-flash"  # Modelo gratuito principal

    async def generate_script(self, text: str, config: dict) -> dict:
        """Gera roteiro usando GLM"""
        template = Template(USER_PROMPT_TEMPLATE)
        user_prompt = template.render(
            text=text,
            target_duration=config.get("target_duration", 10),
            depth_level=config.get("depth_level", "normal"),
            voice_host=config.get("voice_host", "pm_alex"),
            voice_cohost=config.get("voice_cohost", "pm_emily"),
            podcast_type=config.get("podcast_type", "dialogue"),
            section_title=config.get("section_title", ""),
            episode_number=config.get("episode_number", 1),
            total_episodes=config.get("total_episodes", 1),
        )

        cache_key = self._get_cache_key(text, config)
        cached = cache_manager.get(cache_key, config.get("depth_level", "normal"))
        if cached:
            logger.info("Usando cache GLM")
            return cached

        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }

                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 8000,
                    }

                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.warning(f"GLM API erro {resp.status}: {error_text}")
                            await asyncio.sleep(2)
                            continue

                        result = await resp.json()
                        content = result["choices"][0]["message"]["content"]

                        script_data = self._extract_json(content)
                        if not script_data:
                            logger.warning("GLM não retornou JSON válido")
                            continue

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "glm"
                        script_dict["llm_model"] = self.model

                        cache_manager.set(
                            cache_key, config.get("depth_level", "normal"), script_dict
                        )
                        logger.info(
                            f"Roteiro gerado com GLM: {len(script_dict.get('segments', []))} segmentos"
                        )
                        return script_dict

            except Exception as e:
                logger.warning(f"Tentativa GLM {attempt + 1} falhou: {e}")
                await asyncio.sleep(2)

        raise Exception("Falha ao gerar com GLM")


def get_provider(mode: str = "groq") -> LLMProvider:
    providers = {
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "glm": GLMProvider,
        "glm-4-flash": GLMProvider,
        "glm-4": GLMProvider,
    }

    provider_class = providers.get(mode.lower())
    if not provider_class:
        raise ValueError(f"Modo LLM desconhecido: {mode}")

    return provider_class()
