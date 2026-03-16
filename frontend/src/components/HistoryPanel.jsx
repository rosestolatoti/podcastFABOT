import React, { useState } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './HistoryPanel.css';

function HistoryPanel({ onClose }) {
  const { jobHistory, setCurrentJob, setCurrentJobId, setActiveTab, removeFromHistory } = useJobStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(null);
  
  const filteredJobs = jobHistory.filter(job => 
    job.title?.toLowerCase().includes(searchTerm.toLowerCase())
  );
  
  const handleJobClick = async (job) => {
    try {
      const response = await axios.get(`http://localhost:8000/jobs/${job.id}`);
      setCurrentJob(response.data);
      setCurrentJobId(job.id);
      
      if (job.status === 'DONE') {
        setActiveTab('player');
      } else if (job.status === 'SCRIPT_DONE') {
        setActiveTab('roteiro');
      } else {
        setActiveTab('progresso');
      }
      
      onClose();
    } catch (error) {
      console.error('Erro ao carregar job:', error);
    }
  };
  
  const handleDelete = async (jobId) => {
    try {
      await axios.delete(`http://localhost:8000/jobs/${jobId}`);
      removeFromHistory(jobId);
      setConfirmDelete(null);
    } catch (error) {
      console.error('Erro ao deletar job:', error);
    }
  };
  
  const getStatusLabel = (status) => {
    switch (status) {
      case 'DONE': return 'PRONTO';
      case 'FAILED': return 'FALHOU';
      case 'PENDING':
      case 'READING':
      case 'LLM_PROCESSING':
      case 'TTS_PROCESSING':
      case 'POST_PRODUCTION':
        return 'GERANDO';
      default: return 'PENDENTE';
    }
  };
  
  const getStatusClass = (status) => {
    switch (status) {
      case 'DONE': return 'ready';
      case 'FAILED': return 'failed';
      case 'PENDING':
      case 'READING':
      case 'LLM_PROCESSING':
      case 'TTS_PROCESSING':
      case 'POST_PRODUCTION':
        return 'generating';
      default: return 'pending';
    }
  };
  
  return (
    <div className="history-panel">
      <div className="history-header">
        <h3 className="history-title">EPISÓDIOS</h3>
        <button className="close-btn" onClick={onClose}>×</button>
      </div>
      
      <div className="history-search">
        <input
          type="text"
          placeholder="Buscar..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>
      
      <div className="history-list">
        {filteredJobs.slice(0, 50).map(job => (
          <div key={job.id} className="history-item">
            <div className="item-header">
              <span className="item-title">{job.title || 'Sem título'}</span>
              <span className={`item-status ${getStatusClass(job.status)}`}>
                {getStatusLabel(job.status)}
              </span>
            </div>
            
            <div className="item-meta">
              {job.created_at && new Date(job.created_at).toLocaleDateString('pt-BR')}
              {job.duration_seconds && ` · ${job.duration_seconds}s`}
              {' · Groq'}
              {job.audio_path && ` · ${Math.round(job.audio_path.size / 1024 / 1024 * 10) / 10 || '—'} MB`}
            </div>
            
            <div className="item-actions">
              {job.status === 'DONE' && (
                <>
                  <button className="item-btn" onClick={() => handleJobClick(job)}>
                    ▶ Ouvir
                  </button>
                  <button className="item-btn">
                    ↓ Baixar
                  </button>
                </>
              )}
              
              {job.status === 'FAILED' && (
                <button className="item-btn">↺ Tentar novamente</button>
              )}
              
              {['PENDING', 'READING', 'LLM_PROCESSING', 'TTS_PROCESSING', 'POST_PRODUCTION'].includes(job.status) && (
                <div className="item-progress">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${job.progress || 0}%` }} 
                  />
                </div>
              )}
              
              {confirmDelete === job.id ? (
                <div className="delete-confirm">
                  <button 
                    className="confirm-yes"
                    onClick={() => handleDelete(job.id)}
                  >
                    Confirmar
                  </button>
                  <button 
                    className="confirm-no"
                    onClick={() => setConfirmDelete(null)}
                  >
                    Cancelar
                  </button>
                </div>
              ) : (
                <button 
                  className="item-btn delete"
                  onClick={() => setConfirmDelete(job.id)}
                >
                  🗑
                </button>
              )}
            </div>
          </div>
        ))}
        
        {filteredJobs.length === 0 && (
          <div className="history-empty">
            Nenhum episódio encontrado
          </div>
        )}
      </div>
      
      {jobHistory.length > 50 && (
        <div className="history-footer">
          <button className="load-more">Carregar mais</button>
        </div>
      )}
    </div>
  );
}

export default HistoryPanel;
