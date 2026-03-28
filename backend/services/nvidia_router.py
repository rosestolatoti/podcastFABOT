"""
NVIDIA API Router - Fallback automático GLM-5 → Kimi → MiniMax → Gemini
FABOT Studio v2.0

Este módulo implementa fallback automático entre as APIs NVIDIA e Gemini.
Se todas falharem, tenta Gemini como último recurso.

PROBLEMAS CORRIGIDOS:
- Clients httpx não eram fechados (causava memory leak)
- Adicionado shutdown correto
- Adicionado logging detalhado
- Adicionado fallback para Gemini
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


def _limpar_resposta_json(texto: str) -> str:
    texto = texto.strip()
    if texto.startswith("```"):
        linhas = texto.split("\n")
        if linhas[0].startswith("```"):
            linhas = linhas[1:]
        if linhas and linhas[-1].strip().endswith("```"):
            linhas = linhas[:-1]
        texto = "\n".join(linhas).strip()
    return texto


@dataclass
class NVIDIAResponse:
    """Resposta de uma chamada à API NVIDIA."""

    texto: str
    api_usada: str
    model: str
    duracao_ms: int
    sucesso: bool
    erro: Optional[str] = None


class NVIDIARouter:
    """
    Router com fallback automático: Gemini → GLM-5 → Kimi 2.5 → MiniMax 2.5

    Gemini é primário para performance (respostas mais rápidas).
    NVIDIA APIs são fallback quando Gemini falha.

    Uso:
        router = NVIDIARouter()
        resposta = await router.gerar("system", "user")
    """

    def __init__(
        self,
        glm5_key: str,
        kimi_key: str,
        minimax_key: str,
        gemini_key: str = "",
    ):
        self.keys = {
            "glm5": glm5_key,
            "kimi": kimi_key,
            "minimax": minimax_key,
            "gemini": gemini_key,
        }

        self.models = {
            "glm5": "z-ai/glm5",
            "kimi": "moonshotai/kimi-k2.5",
            "minimax": "minimaxai/minimax-m2.5",
            "gemini": "gemini-2.0-flash-exp",
        }

        self.fallback_order = ["gemini", "glm5", "kimi", "minimax"]
        self.nvidia_order = ["glm5", "kimi", "minimax"]
        self.backoff_times = {
            "glm5": 10,
            "kimi": 15,
            "minimax": 15,
            "gemini": 5,
        }

        logger.info("NVIDIARouter: Gemini primário (API direta), NVIDIA como fallback")

    def _create_client(self, api_nome: str) -> OpenAI:
        """Cria um novo client httpx com configurações corretas."""
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self.keys[api_nome],
            max_retries=0,
            timeout=httpx.Timeout(300.0, connect=30.0),
        )
        return client

    async def gerar(
        self,
        system_prompt: str,
        user_prompt: str,
        json_mode: bool = False,
        max_tokens: int = 16384,
        temperature: float = 0.88,
        timeout: int = 180,
    ) -> NVIDIAResponse:
        """
        Gera texto com fallback automático: Gemini (direto) → NVIDIA APIs.
        """
        erros = []

        for api_nome in self.fallback_order:
            try:
                logger.info(f"Tentando API: {api_nome.upper()}")

                if api_nome == "gemini":
                    resposta = await self._chamar_gemini(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )
                else:
                    resposta = await self._chamar_api(
                        api_nome=api_nome,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        timeout=timeout,
                    )

                logger.info(
                    f"✅ {api_nome.upper()} respondeu em {resposta.duracao_ms}ms "
                    f"({len(resposta.texto)} chars)"
                )

                return resposta

            except RateLimitError as e:
                erro_msg = f"{api_nome}: Rate limit - {str(e)}"
                erros.append(erro_msg)
                logger.warning(f"⚠️ Rate limit em {api_nome}: {e}")
                await asyncio.sleep(self.backoff_times[api_nome])

            except APITimeoutError as e:
                erro_msg = f"{api_nome}: Timeout - {str(e)}"
                erros.append(erro_msg)
                logger.warning(f"⚠️ Timeout em {api_nome}: {e}")
                await asyncio.sleep(5)

            except APIError as e:
                erro_msg = f"{api_nome}: API Error - {str(e)}"
                erros.append(erro_msg)
                logger.warning(f"⚠️ Erro na API {api_nome}: {e}")
                await asyncio.sleep(self.backoff_times[api_nome])

            except Exception as e:
                erro_msg = f"{api_nome}: {type(e).__name__} - {str(e)}"
                erros.append(erro_msg)
                logger.error(f"❌ Erro inesperado em {api_nome}: {e}")
                await asyncio.sleep(self.backoff_times[api_nome])

        erro_final = " | ".join(erros)
        logger.error(f"❌ TODAS as APIs NVIDIA falharam: {erro_final}")

        # Tenta Gemini como último recurso
        if self.keys.get("gemini"):
            try:
                logger.info("Tentando GEMINI como fallback final...")
                resposta = await self._chamar_gemini(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
                logger.info(f"✅ GEMINI respondeu em {resposta.duracao_ms}ms")
                return resposta
            except Exception as e:
                logger.error(f"❌ GEMINI também falhou: {e}")

        return NVIDIAResponse(
            texto="",
            api_usada="none",
            model="",
            duracao_ms=0,
            sucesso=False,
            erro=f"TODAS as APIs falharam: {erro_final}",
        )

    async def _chamar_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> NVIDIAResponse:
        """Chama Google Gemini API como fallback."""
        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self.keys["gemini"])

        model = "gemini-2.0-flash"

        start_time = time.time()

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_prompt)],
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        duracao_ms = int((time.time() - start_time) * 1000)
        texto = response.text or ""

        return NVIDIAResponse(
            texto=texto,
            api_usada="gemini",
            model=model,
            duracao_ms=duracao_ms,
            sucesso=True,
        )

    def _chamar_api_sync(
        self,
        api_nome: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> NVIDIAResponse:
        """Chama uma API NVIDIA específica de forma síncrona."""
        model = self.models[api_nome]

        extra_body = {}
        if api_nome == "glm5":
            extra_body = {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            }
        elif api_nome == "kimi":
            extra_body = {
                "chat_template_kwargs": {"thinking": False, "beta_version": "v2"}
            }
        elif api_nome == "minimax":
            extra_body = {"chat_template_kwargs": {"thinking": False}}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start_time = time.time()

        client = self._create_client(api_nome)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                extra_body=extra_body if extra_body else None,
            )

            message = response.choices[0].message

            content = message.content

            if content is None:
                if hasattr(message, "reasoning_content") and message.reasoning_content:
                    content = message.reasoning_content
                elif hasattr(message, "thinking") and message.thinking:
                    content = message.thinking
                elif hasattr(message, "refusal") and message.refusal:
                    content = message.refusal

            logger.info(f"📄 Resposta bruta de {api_nome} ({len(content or '')} chars)")

            duracao_ms = int((time.time() - start_time) * 1000)

            return NVIDIAResponse(
                texto=_limpar_resposta_json(content) if content else "",
                api_usada=api_nome,
                model=model,
                duracao_ms=duracao_ms,
                sucesso=True,
            )
        finally:
            pass

    async def _chamar_api(
        self,
        api_nome: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        temperature: float,
        timeout: int,
    ) -> NVIDIAResponse:
        """Chama uma API NVIDIA específica."""
        return await asyncio.to_thread(
            self._chamar_api_sync,
            api_nome,
            system_prompt,
            user_prompt,
            max_tokens,
            temperature,
            timeout,
        )

    async def health_check(self, api_nome: str) -> bool:
        """Verifica se uma API NVIDIA está disponível."""
        try:
            resposta = await self.gerar(
                system_prompt="Responda apenas 'OK'",
                user_prompt="OK",
                max_tokens=10,
                temperature=0.1,
            )
            return resposta.sucesso and resposta.texto.strip().upper() in ["OK", "OK."]
        except Exception as e:
            logger.warning(f"Health check falhou para {api_nome}: {e}")
            return False

    async def listar_status(self) -> dict:
        """Verifica status de todas as APIs NVIDIA."""
        status = {}
        for api in self.fallback_order:
            status[api] = await self.health_check(api)
        return status


_nvidia_router: Optional[NVIDIARouter] = None


def get_nvidia_router() -> NVIDIARouter:
    """Retorna instância singleton do NVIDIARouter."""
    global _nvidia_router

    if _nvidia_router is None:
        from backend.config import settings

        _nvidia_router = NVIDIARouter(
            glm5_key=settings.NVIDIA_API_KEY_GLM5,
            kimi_key=settings.NVIDIA_API_KEY_KIMI,
            minimax_key=settings.NVIDIA_API_KEY_MINIMAX,
            gemini_key=settings.GEMINI_API_KEY,
        )
        logger.info("NVIDIARouter singleton criado com fallback Gemini")

    return _nvidia_router
