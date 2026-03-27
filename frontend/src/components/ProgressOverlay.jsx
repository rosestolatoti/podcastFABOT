import React, { useEffect, useState, useRef, useCallback } from 'react';
import useJobStore from '../store/jobStore';
import './ProgressOverlay.css';

function ProgressOverlay({ visible, onClose }) {
  const { currentJob, progress } = useJobStore();
  
  const [completedSteps, setCompletedSteps] = useState([]);
  const [minimized, setMinimized] = useState(false);
  const [position, setPosition] = useState({ x: null, y: null });
  const [dragging, setDragging] = useState(false);
  const dragOffset = useRef({ x: 0, y: 0 });
  const toastRef = useRef(null);
  const stepsEndRef = useRef(null);
  const lastJobIdRef = useRef(null);

  // Limpar steps quando muda de job
  useEffect(() => {
    if (currentJob?.id && currentJob.id !== lastJobIdRef.current) {
      lastJobIdRef.current = currentJob.id;
      setCompletedSteps([]);
      setMinimized(false);
    }
  }, [currentJob?.id]);

  // Acumular steps conforme current_step muda
  useEffect(() => {
    const step = currentJob?.current_step;
    if (!step || step === 'Aguardando início...' || step === 'Aguardando...') return;

    setCompletedSteps(prev => {
      // Não duplicar
      if (prev.length > 0 && prev[prev.length - 1].text === step) return prev;
      
      // Marcar anteriores como done
      const updated = prev.map(s => ({ ...s, status: 'done' }));
      
      const isFinal = currentJob?.status === 'DONE' || currentJob?.status === 'SCRIPT_DONE';
      const isError = currentJob?.status === 'FAILED';
      
      updated.push({
        text: step,
        time: new Date(),
        status: isError ? 'error' : (isFinal ? 'done' : 'active'),
        progress: currentJob?.progress || 0,
      });
      
      return updated;
    });
  }, [currentJob?.current_step, currentJob?.status, currentJob?.progress]);

  // Marcar todos como done quando finaliza
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

  // Auto-scroll
  useEffect(() => {
    if (!minimized) {
      stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [completedSteps, minimized]);

  // Drag handlers
  const handleMouseDown = useCallback((e) => {
    if (e.target.closest('button') || e.target.closest('.toast-steps') || e.target.closest('.toast-footer')) return;
    setDragging(true);
    const rect = toastRef.current?.getBoundingClientRect();
    if (rect) {
      dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }
  }, []);

  const handleMouseMove = useCallback((e) => {
    if (!dragging) return;
    setPosition({
      x: e.clientX - dragOffset.current.x,
      y: e.clientY - dragOffset.current.y,
    });
  }, [dragging]);

  const handleMouseUp = useCallback(() => setDragging(false), []);

  useEffect(() => {
    if (dragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragging, handleMouseMove, handleMouseUp]);

  if (!visible) return null;

  const isDone = currentJob?.status === 'DONE';
  const isFailed = currentJob?.status === 'FAILED';
  const isScriptDone = currentJob?.status === 'SCRIPT_DONE';
  const currentProgress = currentJob?.progress || progress || 0;
  const isProcessing = !isDone && !isFailed && !isScriptDone;

  const getStatusIcon = () => {
    if (isFailed) return '❌';
    if (isDone) return '✅';
    if (isScriptDone) return '📝';
    return '⚙️';
  };

  const getStatusText = () => {
    if (isFailed) return 'Falhou';
    if (isDone) return 'Concluído!';
    if (isScriptDone) return 'Roteiro Pronto';
    return 'Processando...';
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString('pt-BR', { 
      hour: '2-digit', minute: '2-digit', second: '2-digit' 
    });
  };

  const getStepIcon = (status) => {
    if (status === 'done') return '✅';
    if (status === 'active') return '⏳';
    if (status === 'error') return '❌';
    return '○';
  };

  // === MODO MINIMIZADO ===
  if (minimized) {
    const toastStyle = position.x !== null
      ? { position: 'fixed', left: position.x, top: position.y, bottom: 'auto', right: 'auto' }
      : {};
    return (
      <div className="progress-toast minimized" style={toastStyle} onClick={() => setMinimized(false)} onMouseDown={handleMouseDown}>
        <div className="toast-mini-content">
          <span className="toast-mini-icon">{getStatusIcon()}</span>
          <div className="toast-mini-bar">
            <div 
              className={`toast-mini-fill ${isFailed ? 'error' : ''}`}
              style={{ width: `${currentProgress}%` }} 
            />
          </div>
          <span className="toast-mini-percent">{currentProgress}%</span>
          {(isDone || isScriptDone) && (
            <button className="toast-mini-close" onClick={(e) => { e.stopPropagation(); onClose(); }}>×</button>
          )}
        </div>
      </div>
    );
  }

  // === MODO EXPANDIDO ===
  const toastStyle = position.x !== null
    ? { position: 'fixed', left: position.x, top: position.y, bottom: 'auto', right: 'auto' }
    : {};
  
  return (
    <div className="progress-toast expanded" style={toastStyle} onMouseDown={handleMouseDown}>
      {/* Header */}
      <div className="toast-header">
        <div className="toast-title">
          <span>{getStatusIcon()}</span>
          <span className="toast-title-text">{getStatusText()}</span>
          <span className="toast-percent">{currentProgress}%</span>
        </div>
        <div className="toast-actions">
          <button 
            className="toast-btn minimize" 
            onClick={() => setMinimized(true)} 
            title="Minimizar"
          >
            ─
          </button>
          {(isDone || isFailed || isScriptDone) && (
            <button 
              className="toast-btn close" 
              onClick={onClose} 
              title="Fechar"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="toast-progress-bar">
        <div 
          className={`toast-progress-fill ${isFailed ? 'error' : ''}`}
          style={{ width: `${currentProgress}%` }} 
        />
      </div>

      {/* Steps list */}
      <div className="toast-steps">
        {completedSteps.map((step, idx) => (
          <div key={idx} className={`toast-step ${step.status}`}>
            <span className="toast-step-icon">{getStepIcon(step.status)}</span>
            <span className="toast-step-text">{step.text}</span>
            <span className="toast-step-meta">
              <span className="toast-step-time">{formatTime(step.time)}</span>
              <span className="toast-step-pct">{step.progress}%</span>
            </span>
          </div>
        ))}
        {isProcessing && (
          <div className="toast-step waiting">
            <span className="toast-step-icon">⏳</span>
            <span className="toast-step-text toast-dots">Aguardando próximo passo</span>
          </div>
        )}
        <div ref={stepsEndRef} />
      </div>

      {/* Footer actions */}
      {(isDone || isScriptDone || isFailed) && (
        <div className="toast-footer">
          {isFailed && currentJob?.error_message && (
            <div className="toast-error">❌ {currentJob.error_message}</div>
          )}
          {isScriptDone && (
            <button className="toast-action-btn success" onClick={onClose}>
              📖 Ver Roteiro
            </button>
          )}
          {isDone && (
            <button className="toast-action-btn primary" onClick={onClose}>
              ▶️ Ouvir Podcast
            </button>
          )}
          {isFailed && (
            <button className="toast-action-btn secondary" onClick={onClose}>
              Fechar
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default ProgressOverlay;
