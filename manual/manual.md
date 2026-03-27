MARCA-TEXTO INTERATIVO — GUIA COMPLETO DE IMPLEMENTAÇÃO
CONTEXTO DO PROJETO
FABOT Podcast Studio converte texto em podcasts com episódios sequenciais. O projeto tem:

Frontend React (Vite) em frontend/
Backend FastAPI + SQLAlchemy em backend/
Worker ARQ para processamento assíncrono
Edge TTS para síntese de voz
Prompt V7 (Jinja2) para gerar roteiros com personalização (personagens, empresas, William, Cristina)
O QUE IMPLEMENTAR
Sistema de marca-texto interativo no InputPanel.jsx que permite ao usuário selecionar palavras/frases do texto colado para definir os tópicos de cada episódio. Cada tópico marcado = 1 episódio, na ordem definida pelo usuário.

REGRA MAIS IMPORTANTE
Cada episódio recebe o TEXTO ORIGINAL COMPLETO + o tópico como foco. O LLM NÃO pode inventar informações fora do texto. Se marcou "relógio" num texto sobre manutenção de relógios, o episódio é sobre manutenção, NÃO sobre história do relógio.

SEQUÊNCIA DE EXECUÇÃO (6 TASKS)
TASK 1: Criar backend/services/topic_extractor.py (ARQUIVO NOVO)
Ação: Criar arquivo novo no caminho backend/services/topic_extractor.py

Conteúdo completo do arquivo:

backend/services/topic_extractor.py
"""
FABOT Podcast Studio — topic_extractor.py

Extrai conceitos/tópicos de um texto sem usar LLM.
Usa análise local: headers Markdown, frequência de palavras, padrões.
Usado opcionalmente para sugestão automática (futuro).
TASK 2: Modificar backend/routers/upload.py
Ação: Modificar arquivo existente. Adicionar o parâmetro topics ao endpoint /paste.

O que mudar: APENAS a função upload_paste. O resto do arquivo fica igual.

Localizar a função upload_paste (começa com @router.post("/paste")).

Substituir a função inteira por esta versão (as mudanças estão marcadas com # ← NOVO):

backend/routers/upload.py
v3
@router.post("/paste")
async def upload_paste(
    title: str,
    text: str,
    llm_mode: str = "gemini-2.5-flash",
    voice_host: str = "pf_dora",
IMPORTANTE: Adicionar import json no topo do arquivo se já não tiver. Verificar os imports existentes — o arquivo já importa logging, então adicionar logger = logging.getLogger(__name__) se não existir.

TASK 3: Modificar backend/workers/podcast_worker.py
Ação: Modificar a função generate_script_only(). Adicionar um bloco no início que verifica se o job tem tópicos manuais. Se tiver, usa eles em vez do content planner automático.

O que mudar: APENAS a função generate_script_only. O resto do arquivo (process_podcast_job, start_tts_job, WorkerSettings, etc.) fica INTACTO.

Substituir a função generate_script_only inteira por:

backend/workers/podcast_worker.py
v7
async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera roteiros. Se tem tópicos manuais do marca-texto, usa eles.
    Se não tem, usa o Content Planner automático."""
    db = SessionLocal()

    try:
IMPORTANTE: NÃO mexer nas outras funções (process_podcast_job, start_tts_job, WorkerSettings, etc.). Elas ficam INTACTAS.

TASK 4: Modificar frontend/src/components/InputPanel.jsx
Ação: Substituir o arquivo INTEIRO. O novo arquivo contém todo o código anterior + a feature de marca-texto.

Conteúdo completo do arquivo:

frontend/src/components/InputPanel.jsx
v3
import React, { useState, useCallback, useRef, useEffect } from 'react';
import useJobStore from '../store/jobStore';
import PDFViewerInline from './PDFViewerInline';
import OcrPanel from './OcrPanel';
import YouTubePanel from './YouTubePanel';
import './InputPanel.css';
TASK 5: Modificar frontend/src/components/InputPanel.css
Ação: Adicionar CSS ao final do arquivo existente. NÃO substituir o arquivo — apenas acrescentar no final.

Adicionar ao final do InputPanel.css:

frontend/src/components/InputPanel.css
v3

/* ═══════════════════════════════════════════════════
   MARCA-TEXTO — Feature de seleção de tópicos
   ═══════════════════════════════════════════════════ */

/* Efeito marca-texto amarelo na seleção do textarea */
TASK 6: Modificar frontend/src/App.jsx
Ação: Modificar apenas a função handleGenerateScript. Uma única mudança: adicionar topics ao URLSearchParams.

Localizar este trecho dentro de handleGenerateScript (por volta da linha 89-96):

JavaScript
const params = new URLSearchParams({
  title: autoTitle || 'Novo Podcast',
  text: data.text,
  llm_mode: llmMode,
  voice_host: 'pm_alex',
  podcast_type: 'monologue',
  target_duration: '10',
});
Adicionar LOGO DEPOIS dessas linhas (antes do const response = await axios.post):

JavaScript
// ═══ MARCA-TEXTO: Enviar tópicos selecionados pelo usuário ═══
if (data.topics && data.topics.length > 0) {
  params.append('topics', JSON.stringify(data.topics));
}
Resultado final desse trecho:

frontend/src/App.jsx
v3
const params = new URLSearchParams({
  title: autoTitle || 'Novo Podcast',
  text: data.text,
  llm_mode: llmMode,
  voice_host: 'pm_alex',
  podcast_type: 'monologue',
NADA MAIS muda no App.jsx. Todo o resto fica intacto.

CHECKLIST DE TESTES
Depois de aplicar todas as 6 tasks, testar nesta ordem:

Teste 1: Visual do marca-texto
Abrir a aplicação no navegador
Ir na aba "Texto"
Colar um texto com mais de 100 caracteres
Verificar que aparece a dica amarela: "🖍️ Selecione palavras..."
Selecionar uma palavra com o mouse → verificar que aparece o botão 📌
Clicar no 📌 → verificar que aparece o chip [1] PalavraX ✕
Selecionar outra palavra → clicar 📌 → chip [2] PalavraY ✕
Verificar que o botão mudou para "Gerar 2 Episódios Sequenciais 📝"
Teste 2: Reordenação e remoção
Com 3+ tópicos marcados, arrastar o chip 3 para a posição 1
Verificar que os números se atualizam: [1] [2] [3]
Clicar ✕ no chip do meio → verificar que some e renumera
Clicar 🗑 → verificar que todos somem
Verificar que o botão volta para "Gerar Roteiro 📝"
Teste 3: Limite de 10
Marcar 10 tópicos
Verificar que mostra "10 de 10"
Selecionar mais texto → 📌 NÃO deve aparecer
Teste 4: Integração com backend
Marcar 2-3 tópicos
Clicar "Gerar 3 Episódios Sequenciais 📝"
Abrir DevTools → Network → verificar que a URL do POST contém topics=["...", "...", "..."]
Verificar no toast de progresso que mostra: "📌 3 tópico(s) selecionado(s) pelo usuário"
Verificar que gera 3 episódios separados no ScriptPanel
Teste 5: Sem tópicos (backwards compatible)
Colar texto SEM marcar nenhum tópico
Clicar "Gerar Roteiro 📝"
Verificar que funciona como antes (content planner automático decide)
Teste 6: Limpar
Clicar "Limpar" no footer do textarea
Verificar que texto E tópicos são apagados
RESUMO FINAL
Arquivo	Ação	Linhas estimadas
backend/services/topic_extractor.py	CRIAR	~120 linhas
backend/routers/upload.py	MODIFICAR (1 função)	+15 linhas
backend/workers/podcast_worker.py	MODIFICAR (1 função)	+90 linhas (modo manual)
frontend/src/components/InputPanel.jsx	SUBSTITUIR	~310 linhas
frontend/src/components/InputPanel.css	ADICIONAR ao final	+200 linhas
frontend/src/App.jsx	MODIFICAR (3 linhas)	+3 linhas
NÃO mexe em: models.py, llm.py, script_template_v7.py, `ScriptPanel.
