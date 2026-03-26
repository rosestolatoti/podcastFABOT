from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import UserConfig
from typing import Optional, List
import json

router = APIRouter(prefix="/config", tags=["config"])


class PessoaProximaSchema(BaseModel):
    nome: str
    relacao: str


class PersonagemSchema(BaseModel):
    nome: str
    cargo: str
    empresa: str


class ApresentadorSchema(BaseModel):
    nome: str
    voz: Optional[str] = None
    genero: Optional[str] = "M"  # "M" ou "F"

    @field_validator("genero")
    @classmethod
    def validate_genero(cls, v):
        if v is not None and v not in ("M", "F"):
            raise ValueError("genero deve ser 'M' ou 'F'")
        return v


class ConfigUpdateSchema(BaseModel):
    usuario_nome: Optional[str] = None
    pessoas_proximas: Optional[List[PessoaProximaSchema]] = None
    apresentador: Optional[ApresentadorSchema] = None
    apresentadora: Optional[ApresentadorSchema] = None
    personagens: Optional[List[PersonagemSchema]] = None
    empresas: Optional[List[str]] = None
    saudar_nome: Optional[bool] = True
    mencionar_pessoas: Optional[bool] = True
    despedida_personalizada: Optional[bool] = True


@router.get("/")
async def get_config(db: Session = Depends(get_db)):
    """Retorna a configuração ativa do usuário"""
    config = db.query(UserConfig).filter(UserConfig.is_active == True).first()

    if not config:
        config = UserConfig(id="default", is_active=True)
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "usuario_nome": config.usuario_nome,
        "pessoas_proximas": json.loads(config.pessoas_proximas)
        if config.pessoas_proximas
        else [],
        "apresentador": {
            "nome": config.apresentador_nome,
            "voz": config.apresentador_voz,
            "genero": config.apresentador_genero or "M",
        }
        if config.apresentador_nome
        else None,
        "apresentadora": {
            "nome": config.apresentadora_nome,
            "voz": config.apresentadora_voz,
            "genero": config.apresentadora_genero or "F",
        }
        if config.apresentadora_nome
        else None,
        "personagens": json.loads(config.personagens) if config.personagens else [],
        "empresas": json.loads(config.empresas) if config.empresas else [],
        "saudar_nome": config.saudar_nome,
        "mencionar_pessoas": config.mencionar_pessoas,
        "despedida_personalizada": config.despedida_personalizada,
    }


@router.post("/")
async def save_config(data: ConfigUpdateSchema, db: Session = Depends(get_db)):
    """Salva a configuração do usuário"""
    config = db.query(UserConfig).filter(UserConfig.is_active == True).first()

    if not config:
        config = UserConfig(id="default", is_active=True)
        db.add(config)

    if data.usuario_nome is not None:
        config.usuario_nome = data.usuario_nome

    if data.pessoas_proximas is not None:
        config.pessoas_proximas = json.dumps(
            [p.model_dump() for p in data.pessoas_proximas], ensure_ascii=False
        )

    if data.apresentador is not None:
        config.apresentador_nome = data.apresentador.nome
        config.apresentador_voz = data.apresentador.voz
        config.apresentador_genero = data.apresentador.genero or "M"

    if data.apresentadora is not None:
        config.apresentadora_nome = data.apresentadora.nome
        config.apresentadora_voz = data.apresentadora.voz
        config.apresentadora_genero = data.apresentadora.genero or "F"

    if data.personagens is not None:
        config.personagens = json.dumps(
            [p.model_dump() for p in data.personagens], ensure_ascii=False
        )

    if data.empresas is not None:
        config.empresas = json.dumps(data.empresas, ensure_ascii=False)

    if data.saudar_nome is not None:
        config.saudar_nome = data.saudar_nome

    if data.mencionar_pessoas is not None:
        config.mencionar_pessoas = data.mencionar_pessoas

    if data.despedida_personalizada is not None:
        config.despedida_personalizada = data.despedida_personalizada

    db.commit()

    return {"success": True, "message": "Configuração salva com sucesso!"}


@router.get("/variables")
async def get_prompt_variables(db: Session = Depends(get_db)):
    """Retorna variáveis para injeção no prompt"""
    config = db.query(UserConfig).filter(UserConfig.is_active == True).first()

    if not config:
        return {
            "USUARIO": None,
            "PESSOAS": None,
            "HOST_NOME": None,
            "HOST_VOZ": None,
            "COHOST_NOME": None,
            "COHOST_VOZ": None,
            "PERSONAGENS_EXEMPLOS": None,
            "EMPRESAS_EXEMPLOS": None,
        }

    pessoas = []
    if config.pessoas_proximas:
        try:
            pessoas_data = json.loads(config.pessoas_proximas)
            pessoas = [f"{p['nome']} ({p['relacao']})" for p in pessoas_data]
        except Exception:
            pessoas = []

    personagens = []
    if config.personagens:
        try:
            personagens_data = json.loads(config.personagens)
            personagens = [
                f"{p['nome']} - {p['cargo']} - {p['empresa']}" for p in personagens_data
            ]
        except Exception:
            personagens = []

    empresas = []
    if config.empresas:
        try:
            empresas = json.loads(config.empresas)
        except Exception:
            empresas = []

    return {
        "USUARIO": config.usuario_nome,
        "PESSOAS": ", ".join(pessoas) if pessoas else None,
        "HOST_NOME": config.apresentador_nome,
        "HOST_VOZ": config.apresentador_voz,
        "HOST_GENERO": config.apresentador_genero or "M",
        "COHOST_NOME": config.apresentadora_nome,
        "COHOST_VOZ": config.apresentadora_voz,
        "COHOST_GENERO": config.apresentadora_genero or "F",
        "PERSONAGENS_EXEMPLOS": "\n".join([f"- {p}" for p in personagens])
        if personagens
        else None,
        "EMPRESAS_EXEMPLOS": ", ".join(empresas) if empresas else None,
        "OPTS": {
            "SAUDAR": config.saudar_nome,
            "MENCIONAR": config.mencionar_pessoas,
            "DESPEDIDA": config.despedida_personalizada,
        },
    }
