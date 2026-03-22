"""
Script para popular o banco com config de teste para Vanda.
Executar: python -m backend.scripts.seed_config
"""

import json
from backend.database import SessionLocal, init_db
from backend.models import UserConfig


def seed_config_vanda():
    init_db()
    db = SessionLocal()

    try:
        config = db.query(UserConfig).filter(UserConfig.is_active == True).first()

        if not config:
            config = UserConfig(id="default", is_active=True)
            db.add(config)

        config.usuario_nome = "Vanda"
        config.pessoas_proximas = json.dumps(
            [{"nome": "Célia", "relacao": "mãe"}], ensure_ascii=False
        )
        config.apresentador_nome = "William"
        config.apresentador_voz = "pt-BR-AntonioNeural"
        config.apresentadora_nome = "Vilma"
        config.apresentadora_voz = "pt-BR-FranciscaNeural"
        config.personagens = json.dumps(
            [
                {"nome": "Luciano Hang", "cargo": "CEO", "empresa": "Havan"},
                {
                    "nome": "Roberto Justus",
                    "cargo": "Empresário",
                    "empresa": "Grupo R! Justus",
                },
            ],
            ensure_ascii=False,
        )
        config.empresas = json.dumps(
            [
                "Havan",
                "Magazine Luiza",
                "Nubank",
                "Itaú",
                "Ambev",
                "Totvs",
                "Stone",
                "XP Investimentos",
                "Renner",
                "Carrefour",
            ],
            ensure_ascii=False,
        )
        config.saudar_nome = True
        config.mencionar_pessoas = True
        config.despedida_personalizada = True

        db.commit()
        print("✅ Config de Vanda salva com sucesso!")
        print(f"   - Usuário: {config.usuario_nome}")
        print(f"   - Mãe: Célia")
        print(f"   - Host: {config.apresentador_nome}")
        print(f"   - Co-host: {config.apresentadora_nome}")

    except Exception as e:
        print(f"❌ Erro: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_config_vanda()
