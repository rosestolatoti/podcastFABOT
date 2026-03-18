#!/usr/bin/env python3
"""Test Gemini API keys"""

import asyncio
import aiohttp

KEYS = [
    "AIzaSyC6XDLEMio-q0-boT44RVfccJljI18m7e8",
    "AIzaSyA5KX3zy-0fYIN7RhOsIQX2Cz7sgtR0K4Q",
]


async def test_key(api_key: str):
    print(f"\n=== Testando {api_key[:20]}... ===")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
                params={"key": api_key},
                json={
                    "contents": [
                        {"parts": [{"text": "O que é Python? Responda em 1 frase."}]}
                    ],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 100},
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ ERRO {resp.status}: {error[:200]}")
                    return False

                result = await resp.json()
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                print(f"✅ OK! Resposta: {content[:100]}...")
                return True
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False


async def main():
    results = []
    for key in KEYS:
        ok = await test_key(key)
        results.append((key, ok))
        await asyncio.sleep(2)

    print("\n" + "=" * 50)
    print("RESUMO:")
    for key, ok in results:
        status = "✅ FUNCIONANDO" if ok else "❌ FALHOU"
        print(f"  {key[:25]}... - {status}")
    print("=" * 50)


asyncio.run(main())
