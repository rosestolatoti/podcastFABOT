import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone

import aiohttp
import redis
from jinja2 import Template
from pydantic import BaseModel, ValidationError, field_validator

from backend.prompts.script_template_v7 import (
    SYSTEM_PROMPT_TEMPLATE as SYSTEM_PROMPT_TEMPLATE_V7,
    USER_PROMPT_TEMPLATE as USER_PROMPT_TEMPLATE_V7,
)
from backend.prompts.prompt_variator import gerar_variacoes

SYSTEM_PROMPT_V7 = Template(SYSTEM_PROMPT_TEMPLATE_V7)
USER_PROMPT_V7 = Template(USER_PROMPT_TEMPLATE_V7)
from backend.config import settings

logger = logging.getLogger(__name__)


def load_config_variables() -> dict:
    """Carrega variáveis do ConfigPanel para injetar no prompt"""
    try:
        from backend.database import SessionLocal
        from backend.models import UserConfig
        import json

        db = SessionLocal()
        try:
            config = db.query(UserConfig).filter(UserConfig.is_active == True).first()
        finally:
            db.close()

        if not config:
            return {}

        pessoas = []
        if config.pessoas_proximas:
            try:
                pessoas_data = json.loads(str(config.pessoas_proximas))
                pessoas = pessoas_data if isinstance(pessoas_data, list) else []
            except Exception:
                pessoas = []

        personagens = []
        if config.personagens:
            try:
                personagens_data = json.loads(str(config.personagens))
                personagens = (
                    personagens_data if isinstance(personagens_data, list) else []
                )
            except Exception:
                personagens = []

        empresas = []
        if config.empresas:
            try:
                empresas = json.loads(str(config.empresas))
                empresas = empresas if isinstance(empresas, list) else []
            except Exception:
                empresas = []

        host_nome = config.apresentador_nome or ""
        cohost_nome = config.apresentadora_nome or ""

        # Gênero vem EXPLICITAMENTE do banco — sem inferência por nome
        host_genero = config.apresentador_genero or "M"
        cohost_genero = config.apresentadora_genero or "F"

        return {
            "usuario_nome": config.usuario_nome or "",
            "pessoas_proximas": pessoas,
            "pessoas_proximas_str": ", ".join(
                [f"{p.get('nome', '')} ({p.get('relacao', '')})" for p in pessoas[:3]]
            )
            if pessoas
            else "",
            "host_nome": host_nome,
            "host_genero": host_genero,
            "cohost_nome": cohost_nome,
            "cohost_genero": cohost_genero,
            "personagens": personagens,
            "empresas": empresas,
            "saudar_nome": config.saudar_nome
            if config.saudar_nome is not None
            else True,
            "mencionar_pessoas": config.mencionar_pessoas
            if config.mencionar_pessoas is not None
            else True,
            "despedida_personalizada": config.despedida_personalizada
            if config.despedida_personalizada is not None
            else True,
        }
    except Exception as e:
        logger.warning(f"Erro ao carregar config: {e}")
        return {}


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
        if len(words) > 40:
            logger.warning(f"Fala com {len(words)} palavras, máximo 40")
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
        if len(v) > 500:
            raise ValueError("Muito segmentos (max 500)")
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


def parse_llm_json(response_text: str) -> dict:
    """
    Parse JSON da resposta do LLM com limpeza automática.
    LLMs às vezes retornam JSON com markdown ou texto antes/depois.
    """
    if not response_text:
        raise ValueError("Resposta do LLM está vazia")

    text = response_text.strip()

    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
        if "segments" in data and len(data.get("segments", [])) > 0:
            return data
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if "segments" in data and len(data.get("segments", [])) > 0:
                logger.info("JSON extraído com regex — resposta tinha texto extra")
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível extrair JSON válido da resposta do LLM")


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


class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = model
        self.base_url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:generateContent"

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
            logger.info("Usando roteiro do cache (Gemini)")
            return cached

        config_vars = load_config_variables()

        episode_number = config.get("episode_number", 1)
        variacoes = gerar_variacoes(
            personagens=config_vars.get("personagens", []),
            empresas=config_vars.get("empresas", []),
            episode_number=episode_number,
        )

        config_vars.update(variacoes)

        for attempt in range(3):
            try:
                system_prompt = SYSTEM_PROMPT_V7.render(**config_vars)

                user_prompt = USER_PROMPT_V7.render(
                    text=text[:15000],
                    target_duration=config.get("target_duration", 10),
                    depth_level=config.get("depth_level", "normal"),
                    podcast_type=config.get("podcast_type", "monologue"),
                    voice_host=config.get("voice_host", ""),
                    voice_cohost=config.get("voice_cohost", ""),
                    episode_number=episode_number,
                    total_episodes=config.get("total_episodes", 1),
                    section_title=config.get("section_title", "Introdução"),
                    context=None,
                    **config_vars,
                )

                full_prompt = f"{system_prompt}\n\n{user_prompt}\n\nRetorne APENAS o JSON válido, sem markdown ou outros textos."

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.base_url,
                        params={"key": self.api_key},
                        json={
                            "contents": [{"parts": [{"text": full_prompt}]}],
                            "generationConfig": {
                                "temperature": 0.88,
                                "topP": 0.92,
                                "maxOutputTokens": 32000,
                            },
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            raise Exception(f"Gemini API error: {resp.status} - {body}")

                        result = await resp.json()
                        content = result["candidates"][0]["content"]["parts"][0]["text"]

                        try:
                            script_data = parse_llm_json(content)
                        except ValueError as e:
                            logger.warning(f"JSON inválido: {e}")
                            continue

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "gemini"
                        script_dict["llm_model"] = self.model
                        script_dict["variacao_id"] = variacoes.get("abertura", {}).get(
                            "id", "unknown"
                        )

                        logger.info(
                            f"Roteiro gerado com Gemini (V7): {len(script_dict.get('segments', []))} segmentos - abertura: {variacoes.get('abertura', {}).get('id', 'unknown')}"
                        )
                        cache_manager.set(text_hash, config_hash, script_dict)
                        return script_dict

            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
                await asyncio.sleep(2)

        raise Exception(f"Falha após 3 tentativas com Gemini")


class GLMProvider(LLMProvider):
    """Provedor GLM (ChatGLM) - Modelos gratuitos"""

    def __init__(self, model: str = "glm-4.7-flash"):
        self.api_key = settings.GLM_API_KEY
        if not self.api_key:
            raise ValueError("GLM_API_KEY não configurada no arquivo .env")
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
        self.model = model

    async def generate_script(self, text: str, config: dict) -> dict:
        text_hash = compute_text_hash(text)
        config_hash = compute_config_hash(config)

        cached = cache_manager.get(text_hash, config_hash)
        if cached:
            logger.info("Usando roteiro do cache (GLM)")
            return cached

        config_vars = load_config_variables()

        episode_number = config.get("episode_number", 1)
        variacoes = gerar_variacoes(
            personagens=config_vars.get("personagens", []),
            empresas=config_vars.get("empresas", []),
            episode_number=episode_number,
        )

        config_vars.update(variacoes)

        for attempt in range(3):
            try:
                system_prompt = SYSTEM_PROMPT_V7.render(**config_vars)

                user_prompt = USER_PROMPT_V7.render(
                    text=text[:15000],
                    target_duration=config.get("target_duration", 10),
                    depth_level=config.get("depth_level", "normal"),
                    voice_host=config.get("voice_host", ""),
                    voice_cohost=config.get("voice_cohost", ""),
                    podcast_type=config.get("podcast_type", "dialogue"),
                    episode_number=episode_number,
                    total_episodes=config.get("total_episodes", 1),
                    section_title=config.get("section_title", "Introdução"),
                    context=None,
                    **config_vars,
                )

                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }

                    payload = {
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.88,
                        "frequency_penalty": 0.4,
                        "presence_penalty": 0.3,
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

                        try:
                            script_data = parse_llm_json(content)
                        except ValueError as e:
                            logger.warning(f"JSON inválido: {e}")
                            continue

                        script = validate_script_response(script_data)
                        script_dict = script.model_dump()
                        script_dict["generated_at"] = datetime.now(
                            timezone.utc
                        ).isoformat()
                        script_dict["llm_provider"] = "glm"
                        script_dict["llm_model"] = self.model
                        script_dict["variacao_id"] = variacoes.get("abertura", {}).get(
                            "id", "unknown"
                        )

                        logger.info(
                            f"Roteiro gerado com GLM (V7): {len(script_dict.get('segments', []))} segmentos - abertura: {variacoes.get('abertura', {}).get('id', 'unknown')}"
                        )
                        cache_manager.set(text_hash, config_hash, script_dict)
                        return script_dict

            except Exception as e:
                logger.warning(f"Tentativa GLM {attempt + 1} falhou: {e}")
                await asyncio.sleep(10)

        raise Exception("Falha ao gerar com GLM")


def get_provider(mode: str = "gemini-2.5-flash") -> LLMProvider:
    mode = mode.lower()
    providers = {
        "gemini": lambda: GeminiProvider("gemini-2.5-flash"),
        "gemini-2.0-flash": lambda: GeminiProvider("gemini-2.0-flash"),
        "gemini-2.0-flash-lite": lambda: GeminiProvider("gemini-2.0-flash-lite"),
        "gemini-2.5-flash": lambda: GeminiProvider("gemini-2.5-flash"),
        "gemini-2.5-flash-lite": lambda: GeminiProvider("gemini-2.5-flash-lite"),
        "gemini-2.5-pro": lambda: GeminiProvider("gemini-2.5-pro"),
        "gemini-1.5-flash": lambda: GeminiProvider("gemini-1.5-flash"),
        "glm": lambda: GLMProvider("glm-4.7-flash"),
        "glm-4-flash": lambda: GLMProvider("glm-4-flash"),
        "glm-4.7-flash": lambda: GLMProvider("glm-4.7-flash"),
        "glm-4": lambda: GLMProvider("glm-4"),
    }

    provider_fn = providers.get(mode)
    if not provider_fn:
        raise ValueError(f"Modo LLM desconhecido: {mode}")

    return provider_fn()
