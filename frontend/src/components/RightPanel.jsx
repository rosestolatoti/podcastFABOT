import React from 'react';
import useJobStore from '../store/jobStore';
import './RightPanel.css';

function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-icon">○</div>
      <div className="empty-title">Nenhum roteiro ainda</div>
      <div className="empty-subtitle">
        Faça upload de um arquivo ou cole
        um texto e clique em Gerar Roteiro
      </div>
    </div>
  );
}

function ScriptTab() {
  const { currentJob } = useJobStore();
  
  if (!currentJob || !currentJob.script_json) {
    return <EmptyState />;
  }
  
  let script = currentJob.script_json;
  try {
    if (typeof script === 'string') {
      script = JSON.parse(script);
    }
  } catch (e) {
    console.error('Erro ao parsear roteiro:', e);
  }
  
  const segments = script?.segments || [];
  const estimatedDuration = Math.ceil(segments.reduce((acc, s) => acc + (s.text?.split(' ').length || 0), 0) / 140);
  
  return (
    <div className="script-tab">
      <div className="script-info">
        <span>{segments.length} falas</span>
        <span>·</span>
        <span>~{estimatedDuration} min estimados</span>
        {currentJob.script_edited && <span>· Editado</span>}
        <span className="saved-badge">Salvo ✓</span>
      </div>
      
      <div className="script-content">
        {segments.map((segment, index) => (
          <div key={index} className="script-block">
            <div className="block-header">
              <span className="speaker-badge">
                {segment.speaker?.toUpperCase()}
              </span>
              <span className="emotion">{segment.emotion || 'neutral'}</span>
              <div className="block-actions">
                <button className="play-btn">▶</button>
                <button className="menu-btn">⋮</button>
              </div>
            </div>
            <div className="block-text">
              {segment.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProgressTab() {
  const { currentJob, llmMode } = useJobStore();
  
  const isFailed = currentJob?.status === 'FAILED';
  const isProcessing = currentJob?.status === 'READING' || currentJob?.status === 'LLM_PROCESSING';
  const errorMessage = currentJob?.error_message;
  
  const steps = [
    { status: 'READING', label: 'Lendo arquivos e processando texto' },
    { status: 'LLM_PROCESSING', label: 'Gerando roteiro com IA (pode levar 30s-2min)' },
    { status: 'SCRIPT_DONE', label: 'Roteiro pronto para revisão' },
    { status: 'TTS_PROCESSING', label: 'Sintetizando áudio com Edge TTS' },
    { status: 'POST_PRODUCTION', label: 'Finalizando e mixando áudio' },
  ];
  
  const currentStatus = currentJob?.status || 'PENDING';
  const progress = currentJob?.progress || 0;
  const currentStep = currentJob?.current_step || 'Aguardando...';
  const jobCreated = currentJob?.created_at ? new Date(currentJob.created_at) : null;
  const elapsedTime = jobCreated ? Math.floor((Date.now() - jobCreated.getTime()) / 1000) : 0;
  
  const formatTime = (seconds) => {
    if (!seconds) return '0s';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };
  
  const getLlmName = () => {
    if (llmMode?.includes('glm')) return 'GLM-4.7';
    if (llmMode?.includes('gemini')) return 'Gemini';
    if (llmMode?.includes('groq')) return 'Groq';
    return llmMode?.toUpperCase() || 'GLM';
  };
  
  return (
    <div className="progress-tab">
      {isProcessing && (
        <div className="processing-indicator">
          🔄 Processando... Aguarde!
        </div>
      )}
      
      <div className="progress-header">
        <span className="progress-llm">🤖 IA: {getLlmName()}</span>
        <span className="progress-timer">⏱️ {formatTime(elapsedTime)}</span>
      </div>
      
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      
      <div className="progress-percent">{progress}%</div>
      
      <div className="progress-step">{currentStep}</div>
      
      <div className="timeline">
        {steps.map((step, index) => {
          let stepStatus = 'pending';
          const currentIndex = steps.findIndex(s => s.status === currentStatus);
          
          if (index < currentIndex) stepStatus = 'completed';
          else if (index === currentIndex) stepStatus = 'active';
          
          return (
            <div key={step.status} className={`timeline-item ${stepStatus}`}>
              <span className="timeline-icon">
                {stepStatus === 'completed' && '✓'}
                {stepStatus === 'active' && '◌'}
                {stepStatus === 'pending' && '○'}
              </span>
              <span className="timeline-label">{step.label}</span>
            </div>
          );
        })}
      </div>
      
      {currentJob?.error_message && (
        <div className="progress-error">
          ❌ Erro: {currentJob.error_message}
        </div>
      )}
    </div>
  );
}

function PlayerTab() {
  const { currentJob } = useJobStore();
  
  if (!currentJob || currentJob.status !== 'DONE') {
    return <EmptyState />;
  }
  
  // Converter data/output/xxx/xxx_final.mp3 para /audio/xxx/xxx_final.mp3
  const rawPath = currentJob?.audio_path || '';
  const audioPath = rawPath.replace('data/output/', '');
  const audioUrl = audioPath ? `http://localhost:8000/audio/${audioPath}` : null;
  const scriptUrl = `http://localhost:8000/jobs/${currentJob.id}/script`;
  
  console.log('[PlayerTab] audio_path:', currentJob.audio_path);
  console.log('[PlayerTab] audioUrl:', audioUrl);
  
  return (
    <div className="player-tab">
      <div className="player">
        {audioUrl ? (
          <audio 
            controls 
            src={audioUrl} 
            style={{width: '100%', marginBottom: '20px'}}
          />
        ) : (
          <div className="player-error">
            Áudio não disponível. Faça um novo podcast.
          </div>
        )}
        
        <div className="player-info">
          <span>Podcast gerado com sucesso!</span>
        </div>
      </div>
      
      <div className="player-info">
        <h3>{currentJob.title || 'FABOT Podcast'}</h3>
        <p>
          Duração: {currentJob.duration_seconds || '—'}s · 
          {currentJob.llm_model || 'GLM'} · 
          {new Date(currentJob.created_at).toLocaleDateString('pt-BR')}
        </p>
      </div>
      
      <div className="player-actions">
        <a href={audioUrl} className="download-btn" download={`${currentJob.id}_podcast.mp3`}>
          ↓ Baixar MP3
        </a>
        <a href={scriptUrl} className="download-btn" download={`${currentJob.id}_roteiro.txt`}>
          ↓ Baixar Roteiro TXT
        </a>
      </div>
    </div>
  );
}

function RightPanel() {
  const { activeTab, setActiveTab, currentJob } = useJobStore();
  
  return (
    <div className="right-panel">
      <div className="panel-tabs">
        <button 
          className={`panel-tab ${activeTab === 'roteiro' ? 'active' : ''}`}
          onClick={() => setActiveTab('roteiro')}
        >
          Roteiro
        </button>
        <button 
          className={`panel-tab ${activeTab === 'progresso' ? 'active' : ''}`}
          onClick={() => setActiveTab('progresso')}
        >
          Progresso
        </button>
        <button 
          className={`panel-tab ${activeTab === 'player' ? 'active' : ''}`}
          onClick={() => setActiveTab('player')}
        >
          Player
        </button>
      </div>
      
      <div className="panel-content">
        {activeTab === 'roteiro' && <ScriptTab />}
        {activeTab === 'progresso' && <ProgressTab />}
        {activeTab === 'player' && <PlayerTab />}
      </div>
    </div>
  );
}

export default RightPanel;
