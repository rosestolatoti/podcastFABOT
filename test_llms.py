"""
Teste das 4 LLMs - FABOT Studio v2.0
FASE 1: Verificar se todas as LLMs estão gerando roteiros

Uso:
    python test_llms.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Adicionar backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


TEXTO_TESTE = """
Estatística é um ramo da matemática que estuda a forma como obter e organizar dados,
relacioná-los entre si, entender o que aconteceu e prever o que vai acontecer em fenômenos
e eventos. A estatística é dividida em três grandes áreas: estatística descritiva,
que apresenta os dados de forma organizada; estatística inferencial, que interpreta
os dados e faz estimativas; e estatística probabilística, que analisa a possibilidade
de um evento ocorrer. Dado estatístico é uma informação numérica obtida a partir de
uma amostragem ou coleta. Conjunto de dados é o total de informações coletadas.
"""


async def testar_llm(nome: str, modo: str):
    """Testa uma LLM específica."""
    print(f"\n{'=' * 60}")
    print(f"TESTANDO: {nome}")
    print(f"{'=' * 60}")

    try:
        from backend.services.llm import get_provider

        provider = get_provider(modo)
        print(f"Provider: {provider}")

        # Health check
        print(f"Health check...", end=" ")
        health = await provider.health_check()
        if health:
            print("✅ OK")
        else:
            print("⚠️ Falhou (continuando...)")

        # Gerar roteiro
        print(f"Gerando roteiro...", end=" ", flush=True)

        config = {
            "episode_number": 1,
            "total_episodes": 1,
            "target_duration": 3,
            "depth_level": "normal",
            "podcast_type": "dialogue",
            "voice_host": "pt-BR-AntonioNeural",
            "voice_cohost": "pt-BR-FranciscaNeural",
            "section_title": "Teste",
        }

        resultado = await provider.generate_script(TEXTO_TESTE, config)

        # Analisar resultado
        segmentos = len(resultado.get("segments", []))
        provider_info = resultado.get("llm_provider", "desconhecido")
        modelo_info = resultado.get("llm_model", "desconhecido")
        api_nvidia = resultado.get("nvidia_api_usada", "n/a")

        print(f"\n✅ SUCESSO!")
        print(f"   Segmentos: {segmentos}")
        print(f"   Provider: {provider_info}")
        print(f"   Modelo: {modelo_info}")
        if api_nvidia != "n/a":
            print(f"   API NVIDIA: {api_nvidia}")

        # Mostrar primeiro segmento
        if resultado.get("segments"):
            primeiro = resultado["segments"][0]
            texto_preview = primeiro.get("text", "")[:100]
            print(f"   Primeiros chars: {texto_preview}...")

        return True, segmentos, resultado

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        return False, 0, None


async def main():
    print("=" * 60)
    print("FABOT STUDIO v2.0 - TESTE DAS 4 LLMs")
    print("=" * 60)

    # Definir LLMs para testar
    llms = [
        ("GLM-5 (NVIDIA)", "nvidia-glm5"),
        ("Kimi 2.5 (NVIDIA)", "nvidia-kimi25"),
        ("MiniMax 2.5 (NVIDIA)", "nvidia-minimax25"),
        ("Gemini 2.5 Flash", "gemini-2.5-flash"),
    ]

    resultados = []

    for nome, modo in llms:
        sucesso, segmentos, _ = await testar_llm(nome, modo)
        resultados.append(
            {
                "nome": nome,
                "modo": modo,
                "sucesso": sucesso,
                "segmentos": segmentos,
            }
        )

        # Pausa entre testes
        if modo != llms[-1][1]:  # Não pausar no último
            print("\nPausando 10 segundos entre testes...")
            await asyncio.sleep(10)

    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)

    for r in resultados:
        status = "✅" if r["sucesso"] else "❌"
        seg_info = f"{r['segmentos']} segmentos" if r["sucesso"] else "falhou"
        print(f"  {status} {r['nome']}: {seg_info}")

    sucesso_count = sum(1 for r in resultados if r["sucesso"])
    print(f"\nTotal: {sucesso_count}/{len(resultados)} LLMs funcionando")

    return sucesso_count == len(resultados)


if __name__ == "__main__":
    sucesso = asyncio.run(main())
    sys.exit(0 if sucesso else 1)
