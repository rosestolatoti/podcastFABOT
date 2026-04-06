"""
NVIDIA LLM Providers - Para usar com llm.py
FABOT Studio v2.0

Cada LLM NVIDIA como provider separado para o sistema de providers.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from jinja2 import Template

from jinja2 import Template

from backend.prompts.script_template_v8 import (
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)
from backend.prompts.prompt_variator import gerar_variacoes
from backend.services.llm import (
    LLMProvider,
    load_config_variables,
    parse_llm_json,
    validate_script_response,
)
from backend.services.nvidia_router import get_nvidia_router

logger = logging.getLogger(__name__)

# Templates Jinja2
SYSTEM_PROMPT_V8_TEMPLATE = Template(SYSTEM_PROMPT_TEMPLATE)
USER_PROMPT_V8_TEMPLATE = Template(USER_PROMPT_TEMPLATE)


class NVIDIABaseProvider(LLMProvider):
    """Base class para providers NVIDIA."""

    def __init__(self, api_nome: str):
        self.router = get_nvidia_router()
        self.api_nome = api_nome
        self.model = f"nvidia-{api_nome}"

    async def health_check(self) -> bool:
        """Verifica se o provider está disponível."""
        try:
            return await self.router.health_check(self.api_nome)
        except Exception as e:
            logger.warning(f"Health check falhou para {self.api_nome}: {e}")
            return False

    def _parse_json_response(self, texto: str) -> dict:
        """Parse JSON da resposta do LLM."""
        return parse_llm_json(texto)

    def _validate_script(self, data: dict) -> Any:
        """Valida e retorna ScriptSchema."""
        return validate_script_response(data)

    def _render_prompts(self, text: str, config: dict) -> tuple:
        """Renderiza system e user prompts."""
        config_vars = load_config_variables()

        episode_number = config.get("episode_number", 1)
        variacoes = gerar_variacoes(
            personagens=config_vars.get("personagens", []),
            empresas=config_vars.get("empresas", []),
            episode_number=episode_number,
        )
        config_vars.update(variacoes)

        system_prompt = SYSTEM_PROMPT_V8_TEMPLATE.render(**config_vars)

        user_prompt = USER_PROMPT_V8_TEMPLATE.render(
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

        return system_prompt, user_prompt

    async def generate_script(self, text: str, config: dict) -> dict:
        """Gera roteiro usando a API NVIDIA selecionada."""
        system_prompt, user_prompt = self._render_prompts(text, config)

        config_vars = load_config_variables()
        episode_number = config.get("episode_number", 1)
        variacoes = gerar_variacoes(
            personagens=config_vars.get("personagens", []),
            empresas=config_vars.get("empresas", []),
            episode_number=episode_number,
        )

        for attempt in range(3):
            try:
                resposta = await self.router.gerar(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_mode=True,
                    max_tokens=16000,
                    temperature=0.88,
                )

                if not resposta.sucesso:
                    logger.warning(f"Tentativa {attempt + 1} falhou: {resposta.erro}")
                    await asyncio.sleep(5)
                    continue

                try:
                    script_data = self._parse_json_response(resposta.texto)
                except ValueError as e:
                    logger.warning(f"JSON inválido: {e}")
                    await asyncio.sleep(5)
                    continue

                script = self._validate_script(script_data)
                script_dict = script.model_dump()
                script_dict["generated_at"] = datetime.now(timezone.utc).isoformat()
                script_dict["llm_provider"] = "nvidia"
                script_dict["llm_model"] = self.model
                script_dict["nvidia_api_usada"] = resposta.api_usada
                script_dict["variacao_id"] = variacoes.get("abertura", {}).get(
                    "id", "unknown"
                )

                logger.info(
                    f"Roteiro gerado com {self.model} ({resposta.api_usada}): "
                    f"{len(script_dict.get('segments', []))} segmentos - "
                    f"abertura: {variacoes.get('abertura', {}).get('id', 'unknown')}"
                )
                return script_dict

            except Exception as e:
                logger.warning(f"Tentativa {attempt + 1} falhou: {e}")
                await asyncio.sleep(10)

        raise Exception(f"Falha ao gerar com {self.model} após 3 tentativas")

    async def raw_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Chamada simples ao LLM via NVIDIA para content_planner."""
        for attempt in range(3):
            try:
                resposta = await self.router.gerar(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_mode=False,
                    max_tokens=2000,
                    temperature=0.3,
                )

                if not resposta.sucesso:
                    logger.warning(
                        f"Tentativa raw_completion {attempt + 1} falhou: {resposta.erro}"
                    )
                    await asyncio.sleep(5)
                    continue

                return resposta.texto

            except Exception as e:
                logger.warning(f"Tentativa raw_completion {attempt + 1} falhou: {e}")
                await asyncio.sleep(5)

        raise Exception(f"Falha após 3 tentativas no raw_completion {self.model}")


class NVIDIAGLM5Provider(NVIDIABaseProvider):
    """Provider para GLM-5 via NVIDIA API."""

    def __init__(self):
        super().__init__(api_nome="glm5")

    def __repr__(self):
        return f"NVIDIAGLM5Provider(model={self.model})"


class NVIDIAKimi25Provider(NVIDIABaseProvider):
    """Provider para Kimi 2.5 via NVIDIA API."""

    def __init__(self):
        super().__init__(api_nome="kimi")

    def __repr__(self):
        return f"NVIDIAKimi25Provider(model={self.model})"


class NVIDIAMiniMax25Provider(NVIDIABaseProvider):
    """Provider para MiniMax 2.5 via NVIDIA API."""

    def __init__(self):
        super().__init__(api_nome="minimax")

    def __repr__(self):
        return f"NVIDIAMiniMax25Provider(model={self.model})"


# Alias para uso direto
NVIDIAGLMProvider = NVIDIAGLM5Provider
NVIDIAKimiProvider = NVIDIAKimi25Provider
NVIDIAMiniMaxProvider = NVIDIAMiniMax25Provider
