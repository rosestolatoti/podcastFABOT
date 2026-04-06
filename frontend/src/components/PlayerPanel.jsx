import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './PlayerPanel.css';

const API_BASE = 'http://localhost:8000';

function PlayerPanel() {
  const { currentJob, jobHistory, setCurrentJob, setCurrentJobId, setJobHistory } = useJobStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [showFavorites, setShowFavorites] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(0.8);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [activeEpisode, setActiveEpisode] = useState(null);
  const audioRef = useRef(null);

  const [expandedHistoryJobs, setExpandedHistoryJobs] = useState(new Set());

  const toggleHistoryJob = useCallback((jobId) => {
    setExpandedHistoryJobs(prev => {
      const next = new Set(prev);
      if (next.has(jobId)) {
        next.delete(jobId);
      } else {
        next.add(jobId);
      }
      return next;
    });
  }, []);

  const episodesMeta = useMemo(() => {
    if (!currentJob?.episodes_meta) return [];
    try {
      return typeof currentJob.episodes_meta === 'string'
        ? JSON.parse(currentJob.episodes_meta)
        : currentJob.episodes_meta;
    } catch { return []; }
  }, [currentJob?.episodes_meta]);

  const hasAudio = currentJob && currentJob.status === 'DONE' && currentJob.audio_path;

  const audioUrl = useMemo(() => {
    if (!currentJob?.audio_path) return null;
    const parts = currentJob.audio_path.split('/');
    const uuidFolder = parts[parts.length - 2];
    return `${API_BASE}/audio/${uuidFolder}/final.mp3`;
  }, [currentJob?.audio_path]);

  const downloadUrl = currentJob?.id ? `${API_BASE}/download/${currentJob.id}` : null;

  const getEpisodeAudioUrl = (epNum, jobId = currentJob?.id) => {
    if (!jobId) return null;
    return `${API_BASE}/audio/${jobId}/ep_${String(epNum).padStart(2, '0')}/final.mp3`;
  };

  const getEpisodeDownloadUrl = (epNum, jobId = currentJob?.id) => {
    if (!jobId) return null;
    return `${API_BASE}/download/${jobId}/episode/${epNum}`;
  };

  const loadJobAndPlayEpisode = useCallback(async (jobId, epNum) => {
    try {
      const response = await axios.get(`${API_BASE}/jobs/${jobId}`);
      setCurrentJob(response.data);
      setCurrentJobId(jobId);
      setCurrentTime(0);
      const url = `${API_BASE}/audio/${jobId}/ep_${String(epNum).padStart(2, '0')}/final.mp3`;
      if (audioRef.current) {
        setActiveEpisode(epNum);
        audioRef.current.src = url;
        audioRef.current.load();
        audioRef.current.play().catch(err => console.error('Play episode error:', err));
      }
    } catch (error) {
      console.error('Erro ao carregar job:', error);
    }
  }, [setCurrentJob, setCurrentJobId]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => setDuration(audio.duration || 0);
    const onEnded = () => setIsPlaying(false);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('loadedmetadata', onLoadedMetadata);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('play', onPlay);
    audio.addEventListener('pause', onPause);

    return () => {
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('loadedmetadata', onLoadedMetadata);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('play', onPlay);
      audio.removeEventListener('pause', onPause);
    };
  }, [audioUrl]);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume;
    }
  }, [volume]);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  const togglePlay = useCallback(() => {
    if (!audioRef.current || !audioUrl) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(err => console.error('Play error:', err));
    }
  }, [isPlaying, audioUrl]);

  const skipBack = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, audioRef.current.currentTime - 10);
    }
  }, []);

  const skipForward = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.min(duration, audioRef.current.currentTime + 10);
    }
  }, [duration]);

  const handleSeek = (e) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const playEpisode = (epNum) => {
    setActiveEpisode(epNum);
    const url = getEpisodeAudioUrl(epNum);
    if (audioRef.current && url) {
      audioRef.current.src = url;
      audioRef.current.load();
      audioRef.current.play().catch(err => console.error('Play episode error:', err));
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '—';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlayJob = async (jobId) => {
    try {
      const response = await axios.get(`${API_BASE}/jobs/${jobId}`);
      setCurrentJob(response.data);
      setCurrentJobId(jobId);
      setActiveEpisode(null);
      setIsPlaying(false);
      setCurrentTime(0);
    } catch (error) {
      console.error('Erro ao carregar job:', error);
    }
  };

  const handleDeleteJob = async (jobId) => {
    if (!confirm('Tem certeza que deseja excluir?')) return;
    try {
      await axios.delete(`${API_BASE}/jobs/${jobId}`);
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
      await axios.patch(`${API_BASE}/jobs/${jobId}`, {
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
      const response = await axios.get(`${API_BASE}/jobs/history?${params.toString()}`);
      setJobHistory(response.data.jobs || []);
    } catch (error) {
      console.error('Erro ao buscar histórico:', error);
    }
  };

  useEffect(() => {
    loadHistory();
  }, [searchQuery, showFavorites]);

  return (
    <div className="player-panel">
      <div className="panel-header">
        <h3>3. Player</h3>
      </div>

      {hasAudio && (
        <div className="spotify-player">
          <audio ref={audioRef} src={audioUrl} preload="metadata" />
          
          <div className="player-artwork">
            <div className="artwork-icon">🎙️</div>
          </div>
          
          <div className="player-info">
            <div className="player-title">{currentJob.title}</div>
            <div className="player-subtitle">
              {episodesMeta.length > 0 
                ? `${episodesMeta.length} episódios`
                : formatDuration(currentJob.duration_seconds)}
            </div>
          </div>

          <div className="progress-section">
            <input
              type="range"
              className="progress-bar"
              min="0"
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
            />
            <div className="time-display">
              <span>{formatTime(currentTime)}</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          <div className="controls-section">
            <button className="control-btn skip-btn" onClick={skipBack} title="Voltar 10s">
              ⏪
            </button>
            <button className="control-btn play-btn" onClick={togglePlay} title={isPlaying ? 'Pausar' : 'Reproduzir'}>
              {isPlaying ? '⏸' : '▶'}
            </button>
            <button className="control-btn skip-btn" onClick={skipForward} title="Avançar 10s">
              ⏩
            </button>
          </div>

          <div className="secondary-controls">
            <div className="speed-controls">
              {[0.75, 1, 1.25, 1.5, 2].map(rate => (
                <button
                  key={rate}
                  className={`speed-btn ${playbackRate === rate ? 'active' : ''}`}
                  onClick={() => setPlaybackRate(rate)}
                >
                  {rate}x
                </button>
              ))}
            </div>
            <div className="volume-control">
              <span>🔊</span>
              <input
                type="range"
                className="volume-slider"
                min="0"
                max="1"
                step="0.1"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
              />
            </div>
          </div>

          {episodesMeta.length > 0 && (
            <div className="episode-list">
              <div className="episode-list-header">
                <span>Episódios desta série</span>
              </div>
              {episodesMeta.map((ep) => (
                <div 
                  key={ep.episode_number}
                  className={`episode-item ${activeEpisode === ep.episode_number ? 'active' : ''}`}
                  onClick={() => playEpisode(ep.episode_number)}
                >
                  <span className="ep-number">EP {ep.episode_number}</span>
                  <span className="ep-title">{ep.title}</span>
                  <span className="ep-duration">{formatDuration(ep.duration_seconds)}</span>
                  <a 
                    href={getEpisodeDownloadUrl(ep.episode_number)}
                    className="ep-download"
                    onClick={(e) => e.stopPropagation()}
                    download
                    title="Baixar episódio"
                  >
                    ⬇
                  </a>
                </div>
              ))}
            </div>
          )}

          <div className="download-section">
            <a href={downloadUrl} download className="download-all-btn">
              ⬇ Baixar MP3 Completo
            </a>
          </div>
        </div>
      )}

      {!hasAudio && (
        <div className="empty-player">
          <div className="empty-icon">🎧</div>
          <div className="empty-title">Nenhum áudio</div>
          <div className="empty-subtitle">
            Gere áudio na coluna 2<br/>para reproduzir aqui
          </div>
        </div>
      )}

      <div className="history-filters">
        <input 
          type="text" 
          placeholder="🔍 Buscar podcasts..." 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <button 
          className={`filter-btn ${showFavorites ? 'active' : ''}`}
          onClick={() => setShowFavorites(!showFavorites)}
        >
          ⭐ Favoritos
        </button>
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
            jobHistory.map((job) => {
              const jobEpsMeta = job.episodes_meta ? 
                (typeof job.episodes_meta === 'string' 
                  ? JSON.parse(job.episodes_meta) 
                  : job.episodes_meta) 
                : [];
              const isMulti = jobEpsMeta.length > 1;
              const isExpanded = expandedHistoryJobs.has(job.id);
              
              return (
                <div 
                  key={job.id} 
                  className={`history-item ${currentJob?.id === job.id ? 'active' : ''}`}
                >
                  <div className="history-item-row">
                    <div className="history-item-main" onClick={() => isMulti ? toggleHistoryJob(job.id) : handlePlayJob(job.id)}>
                      <div className="history-item-title">
                        {job.is_favorite && <span className="favorite-star">⭐</span>}
                        {job.title}
                        {isMulti && <span className="multi-badge">{jobEpsMeta.length} eps</span>}
                      </div>
                      <div className="history-item-meta">
                        <span className={`status-badge ${job.status.toLowerCase()}`}>
                          {job.status === 'DONE' ? '🟢' : job.status === 'FAILED' ? '🔴' : '🟡'}
                        </span>
                        {job.duration_seconds && (
                          <span>{formatDuration(job.duration_seconds)}</span>
                        )}
                        {isMulti && <span className="expand-arrow">{isExpanded ? '▲' : '▼'}</span>}
                      </div>
                    </div>
                    <div className="history-item-actions">
                      <button 
                        className={`fav-btn ${job.is_favorite ? 'favorited' : ''}`}
                        onClick={() => handleToggleFavorite(job.id, job.is_favorite)}
                      >
                        {job.is_favorite ? '❤️' : '🤍'}
                      </button>
                      <button 
                        className="history-delete"
                        onClick={() => handleDeleteJob(job.id)}
                      >
                        🗑
                      </button>
                    </div>
                  </div>

                  {isMulti && isExpanded && (
                    <div className="history-episodes">
                      {jobEpsMeta.map((ep) => (
                        <div key={ep.episode_number} className="history-episode-item">
                          <span className="history-ep-badge">EP {ep.episode_number}</span>
                          <span className="history-ep-title">{ep.title}</span>
                          <span className="history-ep-duration">{formatDuration(ep.duration_seconds)}</span>
                          <div className="history-ep-actions">
                            <button
                              className="history-ep-play"
                              onClick={() => loadJobAndPlayEpisode(job.id, ep.episode_number)}
                              title="Reproduzir episódio"
                            >
                              ▶
                            </button>
                            <a
                              href={`${API_BASE}/download/${job.id}/episode/${ep.episode_number}`}
                              className="history-ep-download"
                              onClick={(e) => e.stopPropagation()}
                              download
                              title="Baixar episódio"
                            >
                              ⬇
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default PlayerPanel;
