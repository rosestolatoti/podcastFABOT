import React, { useState } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './MiniJobCard.css';

function MiniJobCard({ job: activeJob, onClose }) {
  const { updateActiveJob, removeActiveJob, addToHistory, setCurrentJobId, setCurrentJob, setActiveTab } = useJobStore();
  const [cancelling, setCancelling] = useState(false);
  
  const isProcessing = !['DONE', 'FAILED', 'CANCELLED'].includes(activeJob.status);
  
  const getStatusIcon = () => {
    switch (activeJob.status) {
      case 'DONE': return '✅';
      case 'FAILED': return '❌';
      case 'CANCELLED': return '🚫';
      case 'SCRIPT_DONE': return '📝';
      case 'LLM_PROCESSING': return '🤖';
      case 'TTS_PROCESSING': return '🔊';
      case 'POST_PRODUCTION': return '🎬';
      default: return '⚙️';
    }
  };
  
  const getStatusText = () => {
    switch (activeJob.status) {
      case 'DONE': return 'Completo';
      case 'FAILED': return 'Falhou';
      case 'CANCELLED': return 'Cancelado';
      case 'SCRIPT_DONE': return 'Roteiro Pronto';
      case 'LLM_PROCESSING': return 'Gerando Roteiro';
      case 'TTS_PROCESSING': return 'Sintetizando';
      case 'POST_PRODUCTION': return 'Finalizando';
      default: return 'Processando';
    }
  };
  
  const handleCancel = async () => {
    if (!cancelling) {
      setCancelling(true);
      try {
        await axios.post(`http://localhost:8000/jobs/${activeJob.id}/cancel`);
        updateActiveJob(activeJob.id, { status: 'CANCELLED', current_step: 'Cancelado pelo usuário' });
      } catch (error) {
        console.error('Erro ao cancelar job:', error);
        setCancelling(false);
      }
    }
  };
  
  const handleClick = () => {
    if (activeJob.status === 'DONE' || activeJob.status === 'SCRIPT_DONE') {
      setCurrentJobId(activeJob.id);
      setCurrentJob(activeJob);
      if (activeJob.status === 'DONE') {
        setActiveTab('player');
      } else {
        setActiveTab('roteiro');
      }
    }
  };
  
  const handleRemove = () => {
    if (['DONE', 'FAILED', 'CANCELLED'].includes(activeJob.status)) {
      removeActiveJob(activeJob.id);
      if (activeJob.status === 'DONE') {
        addToHistory(activeJob);
      }
    }
  };
  
  const title = activeJob.title || 'Novo Podcast';
  const shortTitle = title.length > 25 ? title.substring(0, 25) + '...' : title;
  
  return (
    <div className={`mini-job-card ${activeJob.status.toLowerCase()}`}>
      <div className="mini-job-header">
        <span className="mini-job-icon">{getStatusIcon()}</span>
        <span className="mini-job-title" title={title}>{shortTitle}</span>
        {isProcessing && (
          <button 
            className="mini-job-cancel" 
            onClick={handleCancel}
            disabled={cancelling}
            title="Cancelar"
          >
            {cancelling ? '⏳' : '✕'}
          </button>
        )}
        {!isProcessing && (
          <button 
            className="mini-job-close" 
            onClick={handleRemove}
            title="Fechar"
          >
            ✕
          </button>
        )}
      </div>
      
      <div className="mini-job-progress">
        <div className="mini-job-bar">
          <div 
            className="mini-job-fill" 
            style={{ width: `${activeJob.progress || 0}%` }}
          />
        </div>
        <span className="mini-job-percent">{activeJob.progress || 0}%</span>
      </div>
      
      <div className="mini-job-footer">
        <span className="mini-job-status">{getStatusText()}</span>
        {(activeJob.status === 'DONE' || activeJob.status === 'SCRIPT_DONE') && (
          <button className="mini-job-action" onClick={handleClick}>
            {activeJob.status === 'DONE' ? '▶️' : '📖'}
          </button>
        )}
      </div>
    </div>
  );
}

export default MiniJobCard;
