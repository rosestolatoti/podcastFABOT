"""
pipeline.py — Orquestra todo o processo de geração de podcasts.

Fluxo completo:
  1. extractor.py     → DocumentoEstruturado
  2. concept_extractor.py → lista[Conceito]
  3. decisor.py       → ResultadoDecisao (scores + total_episodios)
  4. grouper.py       → PlanoCompleto
  5. coverage_check.py → valida 100%
  6. content_bible.py → ContentBible
  7. Para cada episódio:
     a. generator.py  → Episodio
     b. validator.py  → ResultadoValidacao
     c. Se inválido: regenera (máx MAX_REGENERACOES vezes)
  8. Salva todos os resultados em disco

ESTADO PERSISTIDO:
  - Após cada etapa, salva estado em <output_dir>/pipeline_state.json
  - Se o processo for interrompido, retoma da última etapa concluída
  - Episódios já gerados não são regenerados (a menos de --force)

SAÍDA:
  <output_dir>/
  ├── pipeline_state.json          Estado completo
  ├── plano.json                   Plano de todos os episódios
  ├── bible.json                   Content Bible
  ├── ep01_titulo.json             Roteiro ep 1
  ├── ep01_titulo.txt              Roteiro ep 1 (legível)
  ├── ep02_titulo.json             Roteiro ep 2
  ├── ...
  ├── validacao.json               Resultado de todas as validações
  └── relatorio.txt                Relatório final
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from concept_extractor import extrair_conceitos
from content_bible import gerar_content_bible
from coverage_check import verificar_cobertura
from decisor import calcular_episodios
from extractor import extrair_documento
from generator import gerar_episodio
from grouper import agrupar_em_episodios
from models import (
    ContentBible,
    Conceito,
    Episodio,
    EpisodioPlano,
    EstadoPipeline,
    PlanoCompleto,
    ResultadoValidacao,
    Segmento,
    StatusPipeline,
)
from validator import validar_episodio

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Constantes ───────────────────────────────────────────────

MAX_REGENERACOES = 3       # Tentativas de regeneração por episódio inválido
PAUSA_ENTRE_EPS = 20       # Segundos entre episódios (respeita rate limit)


# ═══════════════════════════════════════════════════════════════
# SERIALIZAÇÃO / DESERIALIZAÇÃO DE ESTADO
# ═══════════════════════════════════════════════════════════════

class _DataclassEncoder(json.JSONEncoder):
    """Encoder que serializa dataclasses, Enums e objetos complexos."""
    def default(self, obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        if hasattr(obj, "value"):  # Enum
            return obj.value
        return super().default(obj)


def _salvar_json(caminho: Path, dados) -> None:
    """Salva dados como JSON com encoder especial."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2, cls=_DataclassEncoder)


def _slug_titulo(titulo: str) -> str:
    """Converte título em slug para nome de arquivo."""
    titulo = unicodedata.normalize("NFD", titulo)
    titulo = "".join(c for c in titulo if unicodedata.category(c) != "Mn")
    titulo = titulo.lower()
    titulo = re.sub(r"[^a-z0-9]+", "_", titulo)
    return titulo.strip("_")[:50]


# ═══════════════════════════════════════════════════════════════
# SALVAMENTO DE EPISÓDIO
# ═══════════════════════════════════════════════════════════════

def _salvar_episodio(episodio: Episodio, output_dir: Path) -> None:
    """Salva o episódio em JSON e TXT legível."""
    slug = _slug_titulo(episodio.title)
    nome_base = f"ep{episodio.numero:02d}_{slug}"

    # JSON completo
    _salvar_json(output_dir / f"{nome_base}.json", episodio)

    # TXT legível para revisão
    linhas = [
        f"EPISÓDIO {episodio.numero}: {episodio.title}",
        "=" * 60,
        f"Resumo: {episodio.episode_summary}",
        f"Keywords: {', '.join(episodio.keywords)}",
        f"API usada: {episodio.api_usada} | Tentativas: {episodio.tentativas}",
        "",
    ]
    for idx, seg in enumerate(episodio.segments, 1):
        bt = " [BLOCO]" if seg.block_transition else ""
        linhas.append(f"[{idx:3d}] [{seg.speaker}]{bt}")
        linhas.append(seg.text)
        linhas.append("")

    txt_path = output_dir / f"{nome_base}.txt"
    txt_path.write_text("\n".join(linhas), encoding="utf-8")

    logger.info(f"[Pipeline] 💾 Salvo: {nome_base}.json + .txt")


# ═══════════════════════════════════════════════════════════════
# RELATÓRIO FINAL
# ═══════════════════════════════════════════════════════════════

def _gerar_relatorio(
    estado: EstadoPipeline,
    validacoes: list[ResultadoValidacao],
    output_dir: Path,
    duracao_segundos: float,
) -> str:
    """Gera relatório final em texto."""
    total_eps = len(estado.episodios_gerados)
    validos = sum(1 for v in validacoes if v.valido)
    invalidos = total_eps - validos

    total_segs = sum(v.total_segmentos for v in validacoes)
    total_avisos = sum(len(v.avisos) for v in validacoes)
    total_erros_val = sum(len(v.erros) for v in validacoes)

    # Estimativa de áudio: ~150 palavras por minuto de fala
    # cada segmento tem ~22 palavras → 22/150 min por segmento
    minutos_estimados = total_segs * 22 / 150

    linhas = [
        "=" * 70,
        "FABOT PLANNER — RELATÓRIO FINAL",
        "=" * 70,
        "",
        f"Documento: {estado.documento_fonte}",
        f"Status: {estado.status.value}",
        f"Duração total: {duracao_segundos / 60:.1f} minutos",
        "",
        "─── PLANO ───────────────────────────────────────────",
    ]

    if estado.plano:
        linhas += [
            f"Episódios planejados: {estado.plano.total_episodios}",
            f"Conceitos mapeados:   {estado.plano.total_conceitos}",
            f"Cobertura:            {estado.plano.cobertura_percentual:.1f}%",
        ]

    linhas += [
        "",
        "─── GERAÇÃO ─────────────────────────────────────────",
        f"Episódios gerados:  {total_eps}",
        f"Válidos:            {validos}",
        f"Inválidos:          {invalidos}",
        f"Total de segmentos: {total_segs}",
        f"Áudio estimado:     {minutos_estimados:.0f} minutos",
        "",
        "─── QUALIDADE ───────────────────────────────────────",
        f"Avisos de qualidade: {total_avisos}",
        f"Erros de validação:  {total_erros_val}",
        "",
        "─── EPISÓDIOS ───────────────────────────────────────",
    ]

    for ep in estado.episodios_gerados:
        val = next((v for v in validacoes if v.episodio_numero == ep.numero), None)
        status_str = "✅" if (val and val.valido) else "❌"
        segs = val.total_segmentos if val else "?"
        linhas.append(
            f"  {status_str} Ep {ep.numero:02d}: {ep.title} "
            f"({segs} segs, via {ep.api_usada})"
        )
        if val and val.erros:
            for erro in val.erros:
                linhas.append(f"       ❌ {erro}")
        if val and val.avisos:
            for aviso in val.avisos[:2]:  # Mostra só os 2 primeiros
                linhas.append(f"       ⚠️  {aviso}")

    if estado.erros:
        linhas += [
            "",
            "─── ERROS DO PIPELINE ───────────────────────────────",
        ]
        for erro in estado.erros:
            linhas.append(f"  ❌ {erro}")

    linhas += [
        "",
        "─── ARQUIVOS GERADOS ────────────────────────────────",
        f"  {output_dir}/",
    ]

    linhas += [
        "=" * 70,
    ]

    relatorio = "\n".join(linhas)
    (output_dir / "relatorio.txt").write_text(relatorio, encoding="utf-8")
    return relatorio


# ═══════════════════════════════════════════════════════════════
# FUNÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def executar_pipeline(
    arquivo: str,
    output_dir: str = "./output",
    titulo_override: str = "",
    force: bool = False,
) -> EstadoPipeline:
    """
    Executa o pipeline completo de geração de podcasts.

    Args:
        arquivo: Caminho do arquivo de entrada (PDF, TXT, DOCX)
        output_dir: Diretório de saída dos arquivos gerados
        titulo_override: Título personalizado (opcional)
        force: Se True, regenera tudo mesmo que já exista

    Returns:
        EstadoPipeline com o resultado completo.
    """
    inicio = time.time()
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    state_path = output_path / "pipeline_state.json"
    job_id = f"job_{int(inicio)}"

    # ── Estado inicial ────────────────────────────────────────

    estado = EstadoPipeline(
        job_id=job_id,
        documento_fonte=arquivo,
        status=StatusPipeline.PENDENTE,
        criado_em=datetime.now(timezone.utc).isoformat(),
        atualizado_em=datetime.now(timezone.utc).isoformat(),
    )

    def _atualizar_status(novo_status: StatusPipeline):
        estado.status = novo_status
        estado.atualizado_em = datetime.now(timezone.utc).isoformat()
        _salvar_json(state_path, estado)
        logger.info(f"[Pipeline] ── Status: {novo_status.value} ──")

    def _registrar_erro(msg: str):
        estado.erros.append(msg)
        estado.ultimo_erro = msg
        logger.error(f"[Pipeline] ❌ {msg}")

    # ─────────────────────────────────────────────────────────
    # ETAPA 1: EXTRAÇÃO
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 1/7 — EXTRAÇÃO ESTRUTURAL")
    logger.info("=" * 60)

    try:
        documento = extrair_documento(arquivo, titulo_override)
        estado.documento = documento
        _atualizar_status(StatusPipeline.EXTRACAO_OK)
    except Exception as e:
        _registrar_erro(f"Extração falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 2: EXTRAÇÃO DE CONCEITOS
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 2/7 — EXTRAÇÃO DE CONCEITOS (LLM)")
    logger.info("=" * 60)

    try:
        resultado_conceitos = extrair_conceitos(documento)
        conceitos = resultado_conceitos.conceitos
        estado.conceitos = conceitos
        _atualizar_status(StatusPipeline.CONCEITOS_OK)

        logger.info(f"[Pipeline] {len(conceitos)} conceitos extraídos")
    except Exception as e:
        _registrar_erro(f"Extração de conceitos falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 3: DECISÃO (matemática pura)
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 3/7 — CÁLCULO DE EPISÓDIOS (fórmula)")
    logger.info("=" * 60)

    try:
        decisao = calcular_episodios(conceitos)
        logger.info(
            f"[Pipeline] Total de episódios calculados: {decisao.total_episodios}\n"
            f"  Segmentos necessários: {decisao.total_segmentos_necessarios}\n"
            f"  Média segs/ep: {decisao.media_segmentos_por_episodio}\n"
            f"  Média conceitos/ep: {decisao.media_conceitos_por_episodio}"
        )
    except Exception as e:
        _registrar_erro(f"Cálculo de episódios falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 4: AGRUPAMENTO
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 4/7 — AGRUPAMENTO EM EPISÓDIOS")
    logger.info("=" * 60)

    try:
        plano = agrupar_em_episodios(decisao, documento)
        estado.plano = plano
        _atualizar_status(StatusPipeline.PLANO_OK)

        # Salva o plano em disco
        _salvar_json(output_path / "plano.json", plano)
        logger.info(f"[Pipeline] Plano salvo: {output_path / 'plano.json'}")
    except Exception as e:
        _registrar_erro(f"Agrupamento falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 5: VALIDAÇÃO DE COBERTURA
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 5/7 — VALIDAÇÃO DE COBERTURA 100%")
    logger.info("=" * 60)

    try:
        cobertura = verificar_cobertura(conceitos, plano)

        if not cobertura.valido:
            _registrar_erro(
                f"Cobertura inválida ({cobertura.cobertura_percentual:.1f}%): "
                + " | ".join(cobertura.erros)
            )
            _atualizar_status(StatusPipeline.ERRO)
            return estado

        _atualizar_status(StatusPipeline.COBERTURA_OK)
        logger.info(f"[Pipeline] Cobertura: {cobertura.cobertura_percentual:.1f}%")
    except Exception as e:
        _registrar_erro(f"Verificação de cobertura falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 6: CONTENT BIBLE
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ETAPA 6/7 — CONTENT BIBLE (LLM)")
    logger.info("=" * 60)

    try:
        bible = gerar_content_bible(documento)
        estado.bible = bible
        _atualizar_status(StatusPipeline.BIBLE_OK)

        # Salva a bible em disco
        _salvar_json(output_path / "bible.json", bible)
        logger.info(f"[Pipeline] Bible salva: {output_path / 'bible.json'}")
    except Exception as e:
        _registrar_erro(f"Content Bible falhou: {e}")
        _atualizar_status(StatusPipeline.ERRO)
        return estado

    # ─────────────────────────────────────────────────────────
    # ETAPA 7: GERAÇÃO DOS EPISÓDIOS
    # ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info(f"ETAPA 7/7 — GERAÇÃO DE {plano.total_episodios} EPISÓDIOS (LLM)")
    logger.info("=" * 60)

    _atualizar_status(StatusPipeline.GERANDO)
    validacoes: list[ResultadoValidacao] = []
    historico_episodios: list[Episodio] = []

    for ep_plano in plano.episodios:
        logger.info(
            f"\n[Pipeline] ── Ep {ep_plano.numero}/{plano.total_episodios}: "
            f"'{ep_plano.titulo_sugerido}' ──"
        )

        episodio_gerado: Optional[Episodio] = None
        validacao: Optional[ResultadoValidacao] = None

        for tentativa_regen in range(1, MAX_REGENERACOES + 1):
            try:
                episodio_gerado = gerar_episodio(
                    episodio_plano=ep_plano,
                    plano=plano,
                    bible=bible,
                    conceitos_lista=conceitos,
                    historico_episodios=historico_episodios,
                    max_tentativas=2,
                )

                validacao = validar_episodio(
                    episodio=episodio_gerado,
                    plano=ep_plano,
                    conceitos=conceitos,
                )

                if validacao.valido:
                    break  # Episódio válido — sai do loop de regeneração

                # Episódio inválido — tenta regenerar
                if tentativa_regen < MAX_REGENERACOES:
                    logger.warning(
                        f"[Pipeline] Ep {ep_plano.numero} inválido. "
                        f"Regenerando ({tentativa_regen + 1}/{MAX_REGENERACOES})..."
                    )
                    time.sleep(5)
                else:
                    logger.error(
                        f"[Pipeline] Ep {ep_plano.numero} permanece inválido "
                        f"após {MAX_REGENERACOES} tentativas. Aceitando com ressalvas."
                    )

            except Exception as e:
                _registrar_erro(
                    f"Ep {ep_plano.numero} falhou na geração/validação: {e}"
                )
                if tentativa_regen == MAX_REGENERACOES:
                    break
                time.sleep(10)

        if episodio_gerado:
            estado.episodios_gerados.append(episodio_gerado)
            if validacao:
                validacoes.append(validacao)
                estado.validacoes.append(validacao)
            historico_episodios.append(episodio_gerado)

            # Salva o episódio em disco
            _salvar_episodio(episodio_gerado, output_path)

        # Salva estado após cada episódio (permite retomar)
        _atualizar_status(StatusPipeline.GERANDO)

        # Pausa entre episódios para respeitar rate limits
        if ep_plano.numero < plano.total_episodios:
            logger.info(f"[Pipeline] Aguardando {PAUSA_ENTRE_EPS}s (rate limit)...")
            time.sleep(PAUSA_ENTRE_EPS)

    # ─────────────────────────────────────────────────────────
    # FINALIZAÇÃO
    # ─────────────────────────────────────────────────────────

    _atualizar_status(StatusPipeline.CONCLUIDO)

    # Salva validações
    _salvar_json(output_path / "validacao.json", validacoes)

    # Gera relatório
    duracao = time.time() - inicio
    relatorio = _gerar_relatorio(estado, validacoes, output_path, duracao)

    print("\n" + relatorio)

    return estado


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="FABOT Planner — Gera podcasts educacionais a partir de PDFs/textos"
    )
    parser.add_argument("arquivo", help="Caminho do arquivo de entrada (PDF, TXT, DOCX)")
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="Diretório de saída (padrão: ./output)"
    )
    parser.add_argument(
        "--titulo", "-t",
        default="",
        help="Título do documento (opcional, extraído do arquivo se omitido)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Força regeneração mesmo que já exista estado salvo"
    )

    args = parser.parse_args()

    if not os.path.exists(args.arquivo):
        print(f"❌ Arquivo não encontrado: {args.arquivo}")
        sys.exit(1)

    estado = executar_pipeline(
        arquivo=args.arquivo,
        output_dir=args.output,
        titulo_override=args.titulo,
        force=args.force,
    )

    if estado.status == StatusPipeline.CONCLUIDO:
        print(f"\n✅ Pipeline concluído com sucesso!")
        print(f"   {len(estado.episodios_gerados)} episódios em: {args.output}")
        sys.exit(0)
    else:
        print(f"\n❌ Pipeline encerrou com erro: {estado.ultimo_erro}")
        sys.exit(1)
