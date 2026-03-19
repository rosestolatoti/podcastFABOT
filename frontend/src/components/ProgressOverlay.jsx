import React, { useEffect, useState } from 'react';
import useJobStore from '../store/jobStore';
import './ProgressOverlay.css';

function ProgressOverlay({ visible, onClose }) {
  const { 
    currentJob, 
    progress, 
    progressMessage, 
    progressError,
    currentStep 
  } = useJobStore();
  
  const [logs, setLogs] = useState([]);
  const [showScript, setShowScript] = useState(false);
  const [scriptData, setScriptData] = useState(null);
  
  useEffect(() => {
    if (progressMessage && !logs.includes(progressMessage)) {
      setLogs(prev => [...prev, { time: new Date(), message: progressMessage, type: progressError ? 'error' : 'info' }]);
    }
  }, [progressMessage, progressError]);
  
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
  
  const handleViewScript = () => {
    onClose();
  };
  
  return (
    <div className="progress-overlay">
      <div className="progress-modal">
        <div className="progress-header">
          <h2>{getStatusIcon()} {getStatusText()}</h2>
          {(isDone || isFailed) && (
            <button className="close-btn" onClick={onClose}>×</button>
          )}
        </div>
        
        <div className="progress-body">
          {!isDone && !isFailed && (
            <div className="progress-visual">
              <div className="progress-ring">
                <svg viewBox="0 0 100 100">
                  <circle className="progress-bg" cx="50" cy="50" r="45" />
                  <circle 
                    className="progress-value" 
                    cx="50" cy="50" r="45" 
                    strokeDasharray={`${progress * 2.83} 283`}
                  />
                </svg>
                <span className="progress-percent">{progress}%</span>
              </div>
            </div>
          )}
          
          <div className="progress-steps">
            <div className={`step ${['PENDING', 'READING', 'LLM_PROCESSING', 'SCRIPT_DONE', 'DONE'].includes(currentJob?.status) ? 'done' : ''}`}>
              <span className="step-icon">{['LLM_PROCESSING', 'SCRIPT_DONE', 'DONE'].includes(currentJob?.status) ? '✓' : '1'}</span>
              <span className="step-text">Gerando Roteiro</span>
            </div>
            <div className={`step ${['TTS_PROCESSING', 'POST_PRODUCTION', 'DONE'].includes(currentJob?.status) ? 'done' : ''}`}>
              <span className="step-icon">{currentJob?.status === 'DONE' ? '✓' : '2'}</span>
              <span className="step-text">Sintetizando Áudio</span>
            </div>
            <div className={`step ${currentJob?.status === 'DONE' ? 'done' : ''}`}>
              <span className="step-icon">{currentJob?.status === 'DONE' ? '✓' : '3'}</span>
              <span className="step-text">Finalizando</span>
            </div>
          </div>
          
          <div className="progress-logs">
            <h4>📋 Log de Atividades</h4>
            <div className="logs-container">
              {logs.map((log, idx) => (
                <div key={idx} className={`log-entry ${log.type}`}>
                  <span className="log-time">{formatTime(log.time)}</span>
                  <span className="log-message">{log.message}</span>
                </div>
              ))}
              {!isDone && !isFailed && (
                <div className="log-entry loading">
                  <span className="log-time">{formatTime(new Date())}</span>
                  <span className="log-message log-dots">Aguardando...</span>
                </div>
              )}
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
              <p className="script-preview-text">
                {(scriptData?.segments?.[0]?.text || '').substring(0, 200)}...
              </p>
              <button className="btn btn-primary" onClick={handleViewScript}>
                📖 Ver Roteiro Completo
              </button>
            </div>
          )}
        </div>
        
        <div className="progress-footer">
          {isFailed && (
            <button className="btn btn-secondary" onClick={onClose}>
              Fechar
            </button>
          )}
          {isDone && (
            <button className="btn btn-primary" onClick={onClose}>
              ▶️ Ouvir Podcast
            </button>
          )}
          {isScriptDone && (
            <button className="btn btn-success" onClick={onClose}>
              🎧 Gerar Áudio
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProgressOverlay;
