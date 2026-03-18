#!/usr/bin/env python3
"""Teste rápido das APIs GLM e Gemini"""

import asyncio
import aiohttp
import json

GLM_API_KEY = "6b754c80b0a848909600eadaa4ee5818.yRm84RBqDH7ldPxY"
GEMINI_API_KEY = "AIzaSyDmMCJv8UCfC-QPl7QkLJ1uHvvJv-LWKvI"

TEST_TEXT = "Python é uma linguagem de programação de alto nível. Ela foi criada por Guido van Rossum em 1991."


async def test_glm():
    print("\n=== Testando GLM-4.7-Flash ===")
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {GLM_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "glm-4.7-flash",
                "messages": [
                    {"role": "system", "content": "Você é um assistente útil."},
                    {
                        "role": "user",
                        "content": f"O que é Python? Responda em 1 frase.",
                    },
                ],
                "temperature": 0.7,
                "max_tokens": 200,
            }

            async with session.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ ERRO {resp.status}: {error}")
                    return False

                result = await resp.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ GLM-4.7-Flash OK!")
                print(f"   Resposta: {content[:150]}...")
                return True
    except Exception as e:
        import traceback

        print(f"❌ GLM ERRO: {e}")
        traceback.print_exc()
        return False


async def test_gemini():
    print("\n=== Testando Gemini-2.0-Flash-Lite ===")
    try:
        model = "gemini-2.0-flash-lite"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [
                        {"parts": [{"text": "O que é Python? Responda em 1 frase."}]}
                    ],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 200,
                    },
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ ERRO {resp.status}: {error}")
                    return False

                result = await resp.json()
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ Gemini-2.0-Flash OK!")
                print(f"   Resposta: {content[:150]}...")
                return True
    except Exception as e:
        print(f"❌ Gemini ERRO: {e}")
        return False


async def main():
    print("🔬 Testando APIs gratuitas...")

    glm_ok = await test_glm()
    gemini_ok = await test_gemini()

    print("\n" + "=" * 50)
    print("RESUMO:")
    print(f"  GLM-4.7-Flash:    {'✅ OK' if glm_ok else '❌ FALHOU'}")
    print(f"  Gemini-2.0-Flash: {'✅ OK' if gemini_ok else '❌ FALHOU'}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
