DIAGNÓSTICO DO PROBLEMA
O progresso trava em 5% porque:

Backend → O worker (podcast_worker.py) atualiza current_step com mensagens granulares no banco, MAS os sub-passos dentro de cada fase principal (ex: "Conectando à LLM", "Enviando prompt", "Parseando resposta JSON") não são reportados — ele pula direto de 5% para 10% para 40%.

Frontend → O polling em App.jsx busca o job via GET /jobs/{id} a cada 2s, mas o ProgressOverlay.jsx e o RightPanel.jsx mostram apenas a % numérica e 3 steps genéricos. O current_step do backend é exibido, mas como o backend não envia steps granulares, o usuário vê "5%" parado e não sabe o que está acontecendo.

Steps insuficientes → O backend só tem ~4 atualizações de current_step durante todo o processo de geração. Precisa ter 12+ atualizações granulares.

🎯 PLANO DE EXECUÇÃO — 3 ARQUIVOS
ARQUIVO 1: backend/workers/podcast_worker.py
Objetivo: Adicionar sub-steps granulares em CADA função, com mensagens descritivas e progressão de % distribuída uniformemente.

Mudanças na função generate_script_only() (linha 148-251):
Substituir a função inteira. A nova versão deve ter estes checkpoints de progresso com db.commit() após cada um:

Code
Passo 1  → progress=5,   current_step="📄 Lendo texto de entrada..."           status="READING"
Passo 2  → progress=8,   current_step="✂️ Dividindo texto em seções..."         status="READING"
Passo 3  → progress=10,  current_step="📊 Texto dividido em {N} seção(ões)"     status="READING"
Passo 4  → progress=12,  current_step="🤖 Conectando ao provedor LLM ({nome_provedor})..."  status="LLM_PROCESSING"
Passo 5  → progress=15,  current_step="🧠 Enviando texto para a IA (episódio {i}/{N})..."    status="LLM_PROCESSING"
Passo 6  → progress=15+(i/N*20), current_step="⏳ Aguardando resposta da IA (episódio {i}/{N})..." status="LLM_PROCESSING"
   (este step se repete para cada episódio)
Passo 7  → progress=35,  current_step="📝 Parseando resposta JSON da IA..."     status="LLM_PROCESSING"
Passo 8  → progress=38,  current_step="✅ Validando estrutura do roteiro..."     status="LLM_PROCESSING"
Passo 9  → progress=40,  current_step="💾 Salvando roteiro no banco de dados..." status="LLM_PROCESSING"
Passo 10 → progress=40,  current_step="✅ Roteiro pronto ({N} episódios, {M} falas)" status="SCRIPT_DONE"
Código concreto da nova generate_script_only:

Python
async def generate_script_only(ctx: dict, job_id: str) -> dict:
    """Gera roteiros para TODOS os episódios (todas as seções do texto)."""
    db = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job não encontrado: {job_id}")

        # PASSO 1
        job.status = "READING"
        job.progress = 5
        job.current_step = "📄 Lendo texto de entrada..."
        db.commit()

        from backend.services.text_splitter import dividir_texto, relatorio_divisao
        from backend.services.llm import get_provider

        text = job.input_text or "Texto não fornecido"

        # PASSO 2
        job.progress = 8
        job.current_step = "✂️ Dividindo texto em seções..."
        db.commit()

        secoes = dividir_texto(text)
        total_episodes = len(secoes)
        logger.info(f"\n{relatorio_divisao(secoes)}")

        # PASSO 3
        job.progress = 10
        job.current_step = f"📊 Texto dividido em {total_episodes} seção(ões)"
        db.commit()

        # PASSO 4
        job.status = "LLM_PROCESSING"
        job.progress = 12
        job.current_step = f"🤖 Conectando ao provedor LLM ({job.llm_mode})..."
        db.commit()

        provider = get_provider(str(job.llm_mode))

        # PASSO 4b
        job.progress = 14
        job.current_step = f"✅ Provedor {job.llm_mode} conectado com sucesso"
        db.commit()

        all_scripts = []
        previous_summary = ""
        total_segments = 0

        for i, secao in enumerate(secoes):
            episode_num = i + 1

            # PASSO 5 (por episódio)
            job.progress = 15 + int((episode_num / total_episodes) * 10)
            job.current_step = f"🧠 Enviando texto para a IA (episódio {episode_num}/{total_episodes}: {secao.titulo[:40]})..."
            db.commit()

            config = {
                "target_duration": job.target_duration or 10,
                "depth_level": job.depth_level,
                "podcast_type": job.podcast_type,
                "voice_host": job.voice_host,
                "voice_cohost": job.voice_cohost,
                "section_title": secao.titulo,
                "episode_number": episode_num,
                "total_episodes": total_episodes,
                "previous_summary": previous_summary,
            }

            # PASSO 6 (por episódio)
            job.progress = 25 + int((episode_num / total_episodes) * 8)
            job.current_step = f"⏳ Aguardando resposta da IA (episódio {episode_num}/{total_episodes})..."
            db.commit()

            script = await provider.generate_script(secao.conteudo, config)

            # PASSO 6b (por episódio - concluído)
            ep_segments = len(script.get("segments", [])) if isinstance(script, dict) else 0
            total_segments += ep_segments
            job.progress = 25 + int(((episode_num) / total_episodes) * 10)
            job.current_step = f"✅ Episódio {episode_num}/{total_episodes} gerado ({ep_segments} falas)"
            db.commit()

            if isinstance(script, dict):
                segments = script.get("segments", [])
                last_texts = [s.get("text", "") for s in segments[-3:] if s.get("text")]
                previous_summary = " ".join(last_texts)[:500]
                script["episode_number"] = episode_num
                script["total_episodes"] = total_episodes
                script["section_title"] = secao.titulo

            all_scripts.append(script)
            logger.info(f"Episódio {episode_num}/{total_episodes} gerado: {secao.titulo}")

        # PASSO 7
        job.progress = 35
        job.current_step = f"📝 Parseando e combinando {total_episodes} roteiro(s)..."
        db.commit()

        # PASSO 8
        job.progress = 38
        job.current_step = f"✅ Validando estrutura ({total_segments} falas no total)..."
        db.commit()

        if len(all_scripts) == 1:
            job.script_json = json.dumps(all_scripts[0], ensure_ascii=False)
        else:
            job.script_json = json.dumps(all_scripts, ensure_ascii=False)

        # PASSO 9
        job.progress = 39
        job.current_step = "💾 Salvando roteiro no banco de dados..."
        db.commit()

        # PASSO 10
        job.status = "SCRIPT_DONE"
        job.progress = 40
        job.current_step = f"✅ Roteiro pronto ({total_episodes} episódios, {total_segments} falas)"
        db.commit()

        return {
            "success": True,
            "job_id": job_id,
            "total_episodes": total_episodes,
            "episodes": [
                {"episode": i + 1, "title": s.titulo}
                for i, s in enumerate(secoes)
            ],
        }

    except Exception as e:
        logger.error(f"Job {job_id} falhou ao gerar roteiro: {e}")
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.error_message = str(e)
                job.current_step = f"❌ Erro: {str(e)[:100]}"
                db.commit()
        except Exception as db_err:
            logger.error(f"Erro ao atualizar status failed: {db_err}")
        return {"success": False, "job_id": job_id, "error": str(e)}
    finally:
        db.close()
Mudanças na função process_podcast_job() (linha 49-145):
Mesma lógica — adicionar sub-steps entre cada operação. A progressão vai de 5% a 40% (roteiro) e depois continua no TTS. Aplicar o mesmo padrão de steps granulares descrito acima.

Mudanças na função start_tts_job() (linha 254-316):
Adicionar sub-steps na fase TTS:

Code
progress=45, current_step="🔊 Preparando síntese de voz..."         status="TTS_PROCESSING"
progress=48, current_step="🎤 Configurando Edge TTS..."               status="TTS_PROCESSING"
progress=50, current_step="🔊 Sintetizando fala {i}/{N}..."           status="TTS_PROCESSING"
  (repete para cada segmento em lotes, progresso de 50 a 85)
progress=85, current_step="🎵 Concatenando segmentos de áudio..."     status="TTS_PROCESSING"
progress=88, current_step="🎚️ Aplicando pós-produção..."              status="TTS_PROCESSING"
progress=90, current_step="📏 Calculando duração final..."            status="TTS_PROCESSING"
progress=95, current_step="💾 Salvando MP3 final..."                  status="TTS_PROCESSING"
progress=100, current_step="✅ Podcast concluído!"                    status="DONE"
ARQUIVO 2: frontend/src/components/ProgressOverlay.jsx
Objetivo: Substituir a visualização por uma lista vertical de steps com checks, mostrando cada passo que o backend reporta.

Substituir o componente inteiro pelo código abaixo:

jsx
import React, { useEffect, useState, useRef } from 'react';
import useJobStore from '../store/jobStore';
import './ProgressOverlay.css';

function ProgressOverlay({ visible, onClose }) {
  const { 
    currentJob, 
    progress, 
    progressMessage, 
    progressError 
  } = useJobStore();
  
  const [completedSteps, setCompletedSteps] = useState([]);
  const [showScript, setShowScript] = useState(false);
  const [scriptData, setScriptData] = useState(null);
  const stepsEndRef = useRef(null);
  
  // Acumular steps conforme current_step muda
  useEffect(() => {
    const step = currentJob?.current_step;
    if (step && step !== 'Aguardando início...') {
      setCompletedSteps(prev => {
        // Não duplicar o mesmo step
        if (prev.length > 0 && prev[prev.length - 1].text === step) {
          return prev;
        }
        // Marcar o anterior como concluído
        const updated = prev.map(s => ({ ...s, status: 'done' }));
        // Adicionar o novo como ativo
        const isFinal = currentJob?.status === 'DONE' || currentJob?.status === 'SCRIPT_DONE';
        updated.push({
          text: step,
          time: new Date(),
          status: isFinal ? 'done' : 'active',
          progress: currentJob?.progress || 0,
        });
        return updated;
      });
    }
  }, [currentJob?.current_step, currentJob?.status, currentJob?.progress]);
  
  // Marcar todos como done quando finalizar
  useEffect(() => {
    if (currentJob?.status === 'DONE' || currentJob?.status === 'SCRIPT_DONE') {
      setCompletedSteps(prev => prev.map(s => ({ ...s, status: 'done' })));
    }
    if (currentJob?.status === 'FAILED') {
      setCompletedSteps(prev => {
        if (prev.length === 0) return prev;
        const updated = [...prev];
        updated[updated.length - 1] = { ...updated[updated.length - 1], status: 'error' };
        return updated;
      });
    }
  }, [currentJob?.status]);

  // Auto-scroll para o último step
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [completedSteps]);
  
  // Resetar steps quando um novo job começa
  useEffect(() => {
    if (currentJob?.status === 'READING' && (currentJob?.progress || 0) <= 5) {
      setCompletedSteps([]);
    }
  }, [currentJob?.id]);
  
  useEffect(() => {
    if (currentJob?.script_json && currentJob?.status === 'SCRIPT_DONE') {
      try {
        const script = typeof currentJob.script_json === 'string' 
          ? JSON.parse(currentJob.script_json) 
          : currentJob.script_json;
        setScriptData(script);
        setShowScript(true);
      } catch (e) {
        console.error('Parse error:', e);
      }
    }
  }, [currentJob?.script_json, currentJob?.status]);
  
  if (!visible) return null;
  
  const isDone = currentJob?.status === 'DONE';
  const isFailed = currentJob?.status === 'FAILED' || progressError;
  const isScriptDone = currentJob?.status === 'SCRIPT_DONE';
  const currentProgress = currentJob?.progress || progress || 0;
  
  const getStatusIcon = () => {
    if (isFailed) return '❌';
    if (isDone) return '✅';
    if (isScriptDone) return '📝';
    return '⚙️';
  };
  
  const getStatusText = () => {
    if (isFailed) return 'Processo Falhou';
    if (isDone) return 'Podcast Completo!';
    if (isScriptDone) return 'Roteiro Pronto';
    return 'Processando...';
  };
  
  const formatTime = (date) => {
    return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  
  const getStepIcon = (status) => {
    if (status === 'done') return '✅';
    if (status === 'active') return '⏳';
    if (status === 'error') return '❌';
    return '○';
  };
  
  return (
    <div className="progress-overlay">
      <div className="progress-modal">
        <div className="progress-header">
          <h2>{getStatusIcon()} {getStatusText()}</h2>
          <span className="progress-percent-header">{currentProgress}%</span>
          {(isDone || isFailed || isScriptDone) && (
            <button className="close-btn" onClick={onClose}>×</button>
          )}
        </div>
        
        <div className="progress-body">
          {/* Barra de progresso compacta */}
          <div className="progress-bar-compact">
            <div 
              className={`progress-bar-fill ${isFailed ? 'error' : ''}`} 
              style={{ width: `${currentProgress}%` }} 
            />
          </div>
          
          {/* Lista de steps com checks */}
          <div className="steps-checklist">
            <h4>📋 Etapas do Processo</h4>
            <div className="steps-list">
              {completedSteps.map((step, idx) => (
                <div key={idx} className={`step-item ${step.status}`}>
                  <span className="step-check">{getStepIcon(step.status)}</span>
                  <div className="step-content">
                    <span className="step-text">{step.text}</span>
                    <span className="step-time">{formatTime(step.time)}</span>
                  </div>
                  <span className="step-progress">{step.progress}%</span>
                </div>
              ))}
              {!isDone && !isFailed && !isScriptDone && (
                <div className="step-item waiting">
                  <span className="step-check">⏳</span>
                  <div className="step-content">
                    <span className="step-text step-dots">Aguardando próximo passo...</span>
                  </div>
                </div>
              )}
              <div ref={stepsEndRef} />
            </div>
          </div>
          
          {isFailed && (
            <div className="error-details">
              <h4>❌ Erro:</h4>
              <p>{currentJob?.error_message || progressMessage}</p>
            </div>
          )}
          
          {isScriptDone && showScript && (
            <div className="script-preview">
              <h4>📝 Roteiro Gerado</h4>
              <div className="script-info">
                <span className="script-title">{scriptData?.title || 'Roteiro'}</span>
                <span className="script-segments">{scriptData?.segments?.length || 0} falas</span>
              </div>
              <button className="btn btn-primary" onClick={onClose}>
                📖 Ver Roteiro Completo
              </button>
            </div>
          )}
        </div>
        
        <div className="progress-footer">
          {isFailed && (
            <button className="btn btn-secondary" onClick={onClose}>Fechar</button>
          )}
          {isDone && (
            <button className="btn btn-primary" onClick={onClose}>▶️ Ouvir Podcast</button>
          )}
          {isScriptDone && (
            <button className="btn btn-success" onClick={onClose}>🎧 Gerar Áudio</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProgressOverlay;
ARQUIVO 3: frontend/src/components/ProgressOverlay.css
Adicionar estes estilos ao final do arquivo existente (não remover os existentes, apenas adicionar):

CSS
/* === STEPS CHECKLIST === */
.progress-bar-compact {
  width: 100%;
  height: 6px;
  background: #e0e0e0;
  border-radius: 3px;
  margin-bottom: 16px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #667eea, #764ba2);
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progress-bar-fill.error {
  background: linear-gradient(90deg, #dc2626, #b91c1c);
}

.progress-percent-header {
  font-size: 14px;
  font-weight: bold;
  color: #667eea;
  margin-left: auto;
  margin-right: 12px;
}

.steps-checklist {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.steps-checklist h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #333;
}

.steps-list {
  flex: 1;
  overflow-y: auto;
  max-height: 300px;
  padding-right: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 4px;
  font-size: 13px;
  transition: background 0.2s;
}

.step-item.done {
  background: #f0fdf4;
  color: #166534;
}

.step-item.active {
  background: #eff6ff;
  color: #1e40af;
  font-weight: 500;
}

.step-item.error {
  background: #fef2f2;
  color: #dc2626;
}

.step-item.waiting {
  background: #f9fafb;
  color: #9ca3af;
}

.step-check {
  font-size: 16px;
  flex-shrink: 0;
  width: 24px;
  text-align: center;
}

.step-content {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.step-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.step-time {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
}

.step-progress {
  font-size: 11px;
  color: #6b7280;
  flex-shrink: 0;
  min-width: 30px;
  text-align: right;
}

.step-dots::after {
  content: '';
  animation: dots 1.5s steps(3, end) infinite;
}

@keyframes dots {
  0% { content: ''; }
  33% { content: '.'; }
  66% { content: '..'; }
  100% { content: '...'; }
}
ARQUIVO 4 (OPCIONAL MAS RECOMENDADO): frontend/src/components/RightPanel.jsx
A ProgressTab dentro do RightPanel também deve mostrar os mesmos steps detalhados. Substituir a função ProgressTab (linhas 70-154) para usar currentJob.current_step como fonte da lista, com a mesma lógica de acumular steps.

A lógica é idêntica à do ProgressOverlay.jsx — usar um useState para acumular os current_step e mostrar como lista com checks. Copiar a mesma abordagem.

📊 RELATÓRIO QUE ESPERO DO EXECUTANTE
Após implementar, quero:

Print/screenshot do ProgressOverlay durante uma geração de roteiro — deve mostrar a lista de steps com ✅ nos concluídos e ⏳ no ativo
Verificar no console do backend (logs) que cada step está sendo logado com a mensagem correta
Testar os 3 fluxos:
"Gerar Roteiro" → deve mostrar ~10 steps de 5% a 40%
"Gerar Podcast Completo" → deve mostrar ~15 steps de 5% a 100%
Multi-episódios (texto longo) → deve mostrar "Episódio 1/3", "Episódio 2/3", etc.
Confirmar que NÃO trava mais em 5% — agora mesmo se demorar, o usuário vê a mensagem mudar
Se travar, o último step visível indica EXATAMENTE onde parou (ex: "⏳ Aguardando resposta da IA" = a LLM está demorando)
