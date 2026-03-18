#!/usr/bin/env python3
"""List available Gemini models"""

import asyncio
import aiohttp

GEMINI_API_KEY = "AIzaSyDmMCJv8UCfC-QPl7QkLJ1uHvvJv-LWKvI"


async def list_models():
    print("=== Listando modelos Gemini disponíveis ===")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": GEMINI_API_KEY},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    print(f"❌ ERRO {resp.status}: {error}")
                    return

                result = await resp.json()
                models = result.get("models", [])
                print(f"Modelos disponíveis ({len(models)}):")
                for m in models[:20]:
                    print(f"  - {m['name']}")
    except Exception as e:
        print(f"❌ ERRO: {e}")


if __name__ == "__main__":
    asyncio.run(list_models())
