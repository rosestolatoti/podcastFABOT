#!/usr/bin/env python3
"""Quick test of GLM"""

import asyncio
import aiohttp


async def test_glm():
    api_key = "6b754c80b0a848909600eadaa4ee5818.yRm84RBqDH7ldPxY"
    print("=== Testando GLM-4.7-Flash ===", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "glm-4-flash",
                "messages": [
                    {"role": "system", "content": "Você é um assistente útil."},
                    {
                        "role": "user",
                        "content": "O que é Python? Responda em 2 frases.",
                    },
                ],
                "max_tokens": 100,
            }
            async with session.post(
                "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status != 200:
                    print(f"❌ ERRO {resp.status}: {await resp.text()}", flush=True)
                    return
                result = await resp.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ GLM-4-Flash FUNCIONANDO!", flush=True)
                print(f"   Resposta: {content}", flush=True)
    except Exception as e:
        print(f"❌ ERRO: {e}", flush=True)


asyncio.run(test_glm())
