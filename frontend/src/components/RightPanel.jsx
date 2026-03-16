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
  const { currentJob } = useJobStore();
  
  const steps = [
    { status: 'READING', label: 'Lendo arquivos' },
    { status: 'LLM_PROCESSING', label: 'Processando com IA (Groq)' },
    { status: 'SCRIPT_DONE', label: 'Gerando roteiro' },
    { status: 'TTS_PROCESSING', label: 'Sintetizando áudio (Kokoro)' },
    { status: 'POST_PRODUCTION', label: 'Pós-produção' },
  ];
  
  const currentStatus = currentJob?.status || 'PENDING';
  const progress = currentJob?.progress || 0;
  
  return (
    <div className="progress-tab">
      <div className="timeline">
        {steps.map((step, index) => {
          let stepStatus = 'pending';
          const currentIndex = steps.findIndex(s => s.status === currentStatus);
          
          if (index < currentIndex) stepStatus = 'completed';
          else if (index === currentIndex) stepStatus = 'active';
          
          return (
            <div key={step.status} className={`timeline-item ${stepStatus}`}>
              <span className="timeline-icon">
                {stepStatus === 'completed' && '●'}
                {stepStatus === 'active' && '◌'}
                {stepStatus === 'pending' && '○'}
              </span>
              <span className="timeline-label">{step.label}</span>
            </div>
          );
        })}
      </div>
      
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      
      <div className="progress-status">
        {currentJob?.current_step || 'Aguardando...'}
      </div>
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
          Groq · 
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
