import React, { useState, useEffect } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './ScriptPanel.css';

function ScriptPanel({ onGenerateAudio }) {
  const { currentJob, setCurrentJob } = useJobStore();
  const [scriptData, setScriptData] = useState(null);
  const [editedSegments, setEditedSegments] = useState([]);
  const [saving, setSaving] = useState(false);
  const [editingIndex, setEditingIndex] = useState(null);
  const [config, setConfig] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [pipelineProgress, setPipelineProgress] = useState(null);
  const [showMetricsDashboard, setShowMetricsDashboard] = useState(false);

  const PIPELINE_STEPS = [
    { id: 'PENDENTE', label: 'Pendente', icon: '⏳' },
    { id: 'PLANNING', label: 'Planejando', icon: '📋' },
    { id: 'EXTRACAO_OK', label: 'Extraindo Conceitos', icon: '🔍' },
    { id: 'CONCEITOS_OK', label: 'Conceitos Mapeados', icon: '📊' },
    { id: 'PLANO_OK', label: 'Plano Gerado', icon: '📝' },
    { id: 'COBERTURA_OK', label: 'Cobertura Validada', icon: '✅' },
    { id: 'BIBLE_OK', label: 'Bible Criada', icon: '📖' },
    { id: 'GERANDO', label: 'Gerando Episódios', icon: '🎙️' },
    { id: 'EPISODES_DONE', label: 'Episódios Prontos', icon: '🎉' },
    { id: 'TTS_QUEUED', label: 'TTS na Fila', icon: '🔊' },
    { id: 'DONE', label: 'Concluído', icon: '✅' },
  ];

  const getCurrentStepIndex = (status) => {
    const index = PIPELINE_STEPS.findIndex(s => s.id === status);
    return index >= 0 ? index : 0;
  };

  const loadEpisodes = async (jobId) => {
    try {
      const response = await axios.get(`http://localhost:8000/jobs/${jobId}/episodes`);
      if (response.data.episodios) {
        setEpisodes(response.data.episodios);
      }
      setPipelineProgress(response.data);
    } catch (error) {
      console.error('Erro ao carregar episódios:', error);
    }
  };

  useEffect(() => {
    if (currentJob?.pipeline_mode && currentJob?.id) {
      loadEpisodes(currentJob.id);
    }
  }, [currentJob?.id, currentJob?.status]);

  const loadConfig = async () => {
    try {
      const response = await axios.get('http://localhost:8000/config/');
      setConfig(response.data);
    } catch (error) {
      console.error('Erro ao carregar config:', error);
    }
  };
  
  useEffect(() => {
    loadConfig();
  }, []);
  
  useEffect(() => {
    const handleConfigSaved = () => {
      loadConfig();
    };
    window.addEventListener('config-saved', handleConfigSaved);
    return () => window.removeEventListener('config-saved', handleConfigSaved);
  }, []);
  
  const getSpeakerNames = () => {
    return {
      narrador: 'NARRADORA',
      host: config?.apresentador?.nome?.toUpperCase() || 'WILLIAM',
      cohost: config?.apresentadora?.nome?.toUpperCase() || 'CRISTINA'
    };
  };
  
  useEffect(() => {
    console.log('Current job:', currentJob?.id, 'script_json:', currentJob?.script_json ? 'YES' : 'NO');
    const raw = currentJob?.script_json;
    // Valid JSON must be a string starting with '{' or '['
    const isValidJson = raw && typeof raw === 'string' && /^\s*[\[{]/.test(raw);
    
    if (isValidJson) {
      try {
        const script = JSON.parse(raw);
        console.log('Parsed script, segments:', script.segments?.length);
        setScriptData(script);
        setEditedSegments(script.segments || []);
      } catch (e) {
        console.error('Parse error:', e);
        setScriptData(null);
        setEditedSegments([]);
      }
    } else {
      setScriptData(null);
      setEditedSegments([]);
    }
  }, [currentJob?.id, currentJob?.script_json]);
  
  const hasScript = editedSegments.length > 0;
  const hasAudio = currentJob && currentJob.status === 'DONE' && currentJob.audio_path;
  const canGenerateAudio = currentJob && currentJob.status === 'SCRIPT_DONE' && hasScript;
  const isProcessing = currentJob && !['DONE', 'FAILED', 'SCRIPT_DONE', 'PENDING'].includes(currentJob.status);
  
  const getSpeakerClass = (speaker) => {
    if (!speaker) return '';
    const upper = speaker.toUpperCase();
    const names = getSpeakerNames();
    if (upper === 'NARRADOR') return 'narrador';
    if (upper === names.host) return 'william';
    if (upper === names.cohost) return 'cristina';
    return 'cristina';
  };
  
  const getSpeakerName = (speaker) => {
    if (!speaker) return '???';
    const upper = speaker.toUpperCase();
    const names = getSpeakerNames();
    if (upper === 'NARRADOR') return 'NARRADORA';
    return speaker.toUpperCase();
  };
  
  const handleTextChange = (index, newText) => {
    const newSegments = [...editedSegments];
    newSegments[index] = { ...newSegments[index], text: newText };
    setEditedSegments(newSegments);
  };
  
  const handleSave = async () => {
    if (!currentJob || !scriptData) return;
    setSaving(true);
    try {
      const updated = { ...scriptData, segments: editedSegments };
      await axios.put(`http://localhost:8000/jobs/${currentJob.id}/script`, {
        script_json: JSON.stringify(updated)
      });
      alert('Roteiro salvo!');
    } catch (error) {
      console.error('Erro:', error);
      alert('Erro ao salvar');
    }
    setSaving(false);
  };
  
  const handleExport = () => {
    if (!scriptData) return;
    let md = `# ${scriptData.title || 'Podcast'}\n\n`;
    editedSegments.forEach(seg => {
      md += `**${getSpeakerName(seg.speaker)}:** ${seg.text}\n\n`;
    });
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'roteiro.md';
    a.click();
  };

  return (
    <div className="script-panel">
      <div className="panel-header">
        <h3>2. Roteiro</h3>
        {hasScript && (
          <span className="panel-subtitle">
            {scriptData?.title || 'Roteiro'} • {editedSegments.length} falas
          </span>
        )}
        {currentJob?.pipeline_mode && episodes.length > 0 && (
          <button 
            className={`metrics-btn ${showMetricsDashboard ? 'active' : ''}`}
            onClick={() => setShowMetricsDashboard(!showMetricsDashboard)}
            title="Ver métricas dos episódios"
          >
            📊
          </button>
        )}
      </div>

      {currentJob?.pipeline_mode && showMetricsDashboard && episodes.length > 0 && (
        <div className="metrics-dashboard">
          <div className="metrics-header">
            <span className="metrics-title">📈 Métricas</span>
            <span className="metrics-count">{episodes.length} episódio{episodes.length !== 1 ? 's' : ''}</span>
          </div>
          <div className="metrics-summary">
            <div className="metric-item">
              <span className="metric-icon">⏱️</span>
              <span className="metric-value">
                {episodes.reduce((acc, ep) => acc + (ep.duracao_minutos || 0), 0).toFixed(0)} min
              </span>
              <span className="metric-label">total</span>
            </div>
            <div className="metric-item">
              <span className="metric-icon">⭐</span>
              <span className="metric-value">
                {(episodes.reduce((acc, ep) => acc + (ep.qualidade_score || 0), 0) / episodes.length).toFixed(1)}
              </span>
              <span className="metric-label">qualidade</span>
            </div>
            <div className="metric-item">
              <span className="metric-icon">🎙️</span>
              <span className="metric-value">
                {episodes.reduce((acc, ep) => acc + (ep.segments_count || 0), 0)}
              </span>
              <span className="metric-label">segmentos</span>
            </div>
          </div>
          <div className="episodes-vertical-list">
            {episodes.map((ep, idx) => (
              <div key={idx} className="episode-vertical-item">
                <div className="episode-vertical-header">
                  <span className="episode-badge">Ep {ep.numero}</span>
                  <span className="episode-time">{ep.duracao_minutos ? `${ep.duracao_minutos.toFixed(1)} min` : '-'}</span>
                  <span className={`episode-quality-badge ${ep.qualidade_score >= 8 ? 'good' : ep.qualidade_score >= 6 ? 'medium' : 'low'}`}>
                    ★{ep.qualidade_score || '-'}
                  </span>
                </div>
                <div className="episode-vertical-title">{ep.title}</div>
                {ep.keywords && ep.keywords.length > 0 && (
                  <div className="episode-vertical-keywords">
                    {ep.keywords.slice(0, 2).map((kw, i) => (
                      <span key={i} className="kw-chip">{kw}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {currentJob?.pipeline_mode && currentJob?.status !== 'DONE' && (
        <div className="pipeline-progress">
          <div className="pipeline-steps">
            {PIPELINE_STEPS.slice(1, 9).map((step, idx) => {
              const currentIdx = getCurrentStepIndex(currentJob?.status);
              const isActive = idx < currentIdx;
              const isCurrent = idx === currentIdx;
              return (
                <div
                  key={step.id}
                  className={`pipeline-step ${isActive ? 'done' : ''} ${isCurrent ? 'current' : ''}`}
                >
                  <div className="step-icon">{step.icon}</div>
                  <div className="step-label">{step.label}</div>
                </div>
              );
            })}
          </div>
          {currentJob?.current_step && (
            <div className="pipeline-status">{currentJob.current_step}</div>
          )}
          {episodes.length > 0 && (
            <div className="episodes-count">
              {episodes.length} episódio{episodes.length !== 1 ? 's' : ''} planejado{episodes.length !== 1 ? 's' : ''}
            </div>
          )}
        </div>
      )}
      
      {!hasScript ? (
        <div className="empty-state">
          <div className="empty-icon">🎙️</div>
          <div className="empty-title">Aguardando roteiro...</div>
          <div className="empty-subtitle">
            Cole texto na aba de entrada e clique em "Gerar Roteiro"
          </div>
          <div className="presenter-preview">
            <div className="presenter-card narrador">
              <div className="presenter-icon">🎤</div>
              <div className="presenter-name">{getSpeakerNames().narrador}</div>
              <div className="presenter-role">Voz de abertura</div>
            </div>
            <div className="presenter-card host">
              <div className="presenter-icon">🎙️</div>
              <div className="presenter-name">{getSpeakerNames().host}</div>
              <div className="presenter-role">Apresentador</div>
            </div>
            <div className="presenter-card cohost">
              <div className="presenter-icon">🎙️</div>
              <div className="presenter-name">{getSpeakerNames().cohost}</div>
              <div className="presenter-role">Apresentadora</div>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="script-status">
            <span className="status-badge">✓ Pronto</span>
            {hasAudio && <span className="status-badge audio-ready">✓ Com Áudio</span>}
          </div>
          
          <div className="segments-list">
            {editedSegments.map((seg, idx) => (
              <div key={idx} className={`segment ${getSpeakerClass(seg.speaker)}`}>
                <div className="segment-label">
                  <span className="segment-name">{getSpeakerName(seg.speaker)}</span>
                </div>
                <textarea
                  className="segment-input"
                  value={seg.text || ''}
                  onChange={(e) => handleTextChange(idx, e.target.value)}
                  rows={3}
                />
              </div>
            ))}
          </div>
          
          <div className="script-actions">
            <button className="btn btn-secondary" onClick={handleExport}>
              📄 Exportar
            </button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Salvando...' : '💾 Salvar'}
            </button>
            {!hasAudio && (
              <button className="btn btn-success" onClick={onGenerateAudio} disabled={!canGenerateAudio || isProcessing}>
                {isProcessing ? '◌ Gerando...' : '🎧 Gerar Áudio'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default ScriptPanel;
