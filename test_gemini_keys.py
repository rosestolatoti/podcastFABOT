#!/usr/bin/env python3
"""Test Gemini API keys"""

import asyncio
import aiohttp

KEYS = [
    "AIzaSyC6XDLEMio-q0-boT44RVfccJljI18m7e8",
    "AIzaSyA5KX3zy-0fYIN7RhOsIQX2Cz7sgtR0K4Q",
]


async def test_key(api_key: str):
    print(f"\n=== Testando {api_key[:20]}... ===", flush=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": "Hi"}]}],
                    "generationConfig": {"maxOutputTokens": 10},
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ ERRO {resp.status}: {error[:150]}", flush=True)
                    return False

                result = await resp.json()
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ OK! Resposta: {content}", flush=True)
                return True
    except Exception as e:
        print(f"❌ ERRO: {e}", flush=True)
        return False


async def main():
    results = []
    for key in KEYS:
        ok = await test_key(key)
        results.append((key, ok))
        await asyncio.sleep(1)

    print("\n" + "=" * 50)
    print("RESUMO:")
    for key, ok in results:
        status = "✅ FUNCIONANDO" if ok else "❌ FALHOU"
        print(f"  {key[:25]}... - {status}")
    print("=" * 50)


asyncio.run(main())
