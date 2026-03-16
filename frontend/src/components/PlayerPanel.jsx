import React, { useState, useEffect } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './PlayerPanel.css';

function PlayerPanel() {
  const { currentJob, jobHistory, setCurrentJob, setCurrentJobId, setJobHistory } = useJobStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [showFavorites, setShowFavorites] = useState(false);
  const [selectedPlaylist, setSelectedPlaylist] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  
  const hasAudio = currentJob && currentJob.status === 'DONE' && currentJob.audio_path;
  
  const audioUrl = hasAudio 
    ? (() => {
        // Extract the job folder (UUID) from the full path
        // Path format: /home/.../data/output/UUID/final.mp3
        const parts = currentJob.audio_path.split('/');
        const uuidFolder = parts[parts.length - 2]; // Should be UUID
        return `http://localhost:8000/audio/${uuidFolder}/final.mp3`;
      })()
    : null;
  
  const handlePlayJob = async (jobId) => {
    try {
      const response = await axios.get(`http://localhost:8000/jobs/${jobId}`);
      setCurrentJob(response.data);
      setCurrentJobId(jobId);
    } catch (error) {
      console.error('Erro ao carregar job:', error);
    }
  };
  
  const handleDeleteJob = async (jobId) => {
    if (!confirm('Tem certeza que deseja excluir?')) return;
    
    try {
      await axios.delete(`http://localhost:8000/jobs/${jobId}`);
      setJobHistory(jobHistory.filter(j => j.id !== jobId));
      if (currentJob?.id === jobId) {
        setCurrentJob(null);
        setCurrentJobId(null);
      }
    } catch (error) {
      console.error('Erro ao excluir job:', error);
    }
  };
  
  const handleToggleFavorite = async (jobId, currentFavorite) => {
    try {
      await axios.patch(`http://localhost:8000/jobs/${jobId}`, {
        is_favorite: !currentFavorite
      });
      setJobHistory(jobHistory.map(j => 
        j.id === jobId ? { ...j, is_favorite: !currentFavorite } : j
      ));
    } catch (error) {
      console.error('Erro ao favoritar:', error);
    }
  };
  
  const loadHistory = async () => {
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (showFavorites) params.append('favorites', 'true');
      if (selectedPlaylist) params.append('playlist', selectedPlaylist);
      if (selectedCategory) params.append('category', selectedCategory);
      
      const response = await axios.get(`http://localhost:8000/jobs/history?${params.toString()}`);
      setJobHistory(response.data.jobs || []);
    } catch (error) {
      console.error('Erro ao buscar histórico:', error);
    }
  };
  
  useEffect(() => {
    loadHistory();
  }, [searchQuery, showFavorites, selectedPlaylist, selectedCategory]);
  
  const formatDuration = (seconds) => {
    if (!seconds) return '—';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleDateString('pt-BR', { 
      day: '2-digit', 
      month: '2-digit', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  
  return (
    <div className="player-panel">
      <div className="panel-header">
        <h3>3. Player</h3>
        <span className="panel-subtitle">Histórico e reproduções</span>
      </div>
      
      <div className="player-section">
        {!hasAudio ? (
          <div className="empty-player">
            <div className="empty-icon">🎧</div>
            <div className="empty-title">Nenhum áudio</div>
            <div className="empty-subtitle">
              Gere áudio na coluna 2<br/>para reproduzir aqui
            </div>
          </div>
        ) : (
          <>
            <div className="current-audio">
              <div className="audio-title">{currentJob.title}</div>
              <audio 
                controls 
                src={audioUrl}
                style={{width: '100%'}}
              />
              <div className="audio-info">
                <span>Duração: {formatDuration(currentJob.duration_seconds)}</span>
                <span>•</span>
                <span>{formatDate(currentJob.created_at)}</span>
              </div>
            </div>
            
            <div className="download-buttons">
              <a 
                href={audioUrl} 
                download={`${currentJob.title || 'podcast'}.mp3`}
                className="download-btn"
              >
                ↓ Baixar MP3
              </a>
            </div>
          </>
        )}
      </div>
      
      {/* Search and Filters */}
      <div className="history-filters">
        <input 
          type="text" 
          placeholder="🔍 Buscar podcasts..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        
        <div className="filter-buttons">
          <button 
            className={`filter-btn ${showFavorites ? 'active' : ''}`}
            onClick={() => setShowFavorites(!showFavorites)}
            title="Mostrar favoritos"
          >
            ⭐ {showFavorites ? 'Favoritos' : 'Favoritos'}
          </button>
        </div>
      </div>
      
      <div className="history-section">
        <div className="history-header">
          <h4>Histórico</h4>
          <span className="history-count">{jobHistory.length} episódios</span>
        </div>
        
        <div className="history-list">
          {jobHistory.length === 0 ? (
            <div className="history-empty">Nenhum episódio encontrado</div>
          ) : (
            jobHistory.map(job => (
              <div 
                key={job.id} 
                className={`history-item ${currentJob?.id === job.id ? 'active' : ''}`}
              >
                <div className="history-item-main" onClick={() => handlePlayJob(job.id)}>
                  <div className="history-item-title">
                    {job.is_favorite && <span className="favorite-star">⭐</span>}
                    {job.title}
                  </div>
                  <div className="history-item-meta">
                    <span className={`status-badge ${job.status.toLowerCase()}`}>
                      {job.status === 'DONE' ? '✓' : job.status === 'FAILED' ? '✕' : '○'}
                    </span>
                    {job.duration_seconds && (
                      <span>{formatDuration(job.duration_seconds)}</span>
                    )}
                    {job.category && (
                      <span className="category-tag">{job.category}</span>
                    )}
                  </div>
                </div>
                <div className="history-item-actions">
                  <button 
                    className={`fav-btn ${job.is_favorite ? 'favorited' : ''}`}
                    onClick={() => handleToggleFavorite(job.id, job.is_favorite)}
                    title={job.is_favorite ? 'Remover favorito' : 'Adicionar aos favoritos'}
                  >
                    {job.is_favorite ? '⭐' : '☆'}
                  </button>
                  <button 
                    className="history-delete"
                    onClick={() => handleDeleteJob(job.id)}
                    title="Excluir"
                  >
                    🗑
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default PlayerPanel;
