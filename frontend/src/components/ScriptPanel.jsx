import React, { useState, useMemo, useCallback } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';
import './ScriptPanel.css';

function ScriptPanel({ onGenerateAudio }) {
  const { currentJob } = useJobStore();
  const [saving, setSaving] = useState(false);
  const [expandedEpisode, setExpandedEpisode] = useState(null);

  const { scripts, totalSegments, totalWords, estimatedMinutes } = useMemo(() => {
    let scripts = [];
    let totalSegments = 0;
    let totalWords = 0;

    if (currentJob?.script_json) {
      try {
        const parsed = typeof currentJob.script_json === 'string'
          ? JSON.parse(currentJob.script_json)
          : currentJob.script_json;
        scripts = Array.isArray(parsed) ? parsed : [parsed];
      } catch (e) {
        console.error('Erro ao parsear script_json:', e);
      }
    }

    scripts.forEach(script => {
      (script?.segments || []).forEach(seg => {
        totalSegments++;
        totalWords += (seg.text?.split(' ').length || 0);
      });
    });

    return { scripts, totalSegments, totalWords, estimatedMinutes: Math.ceil(totalWords / 140) };
  }, [currentJob?.script_json]);

  const hasScript = scripts.length > 0;
  const hasAudio = currentJob?.status === 'DONE' && currentJob?.audio_path;
  const isTtsProcessing = currentJob?.status === 'TTS_PROCESSING';

  const getSpeakerName = (speaker) => {
    const names = {
      narrador: 'NARRADORA',
      narradora: 'NARRADORA',
      host: 'WILLIAM',
      william: 'WILLIAM',
      cohost: 'CRISTINA',
      cristina: 'CRISTINA',
    };
    return names[speaker?.toLowerCase()] || speaker;
  };

  const handleSave = useCallback(async () => {
    if (!currentJob?.id) return;
    setSaving(true);
    try {
      const scriptData = scripts.length === 1 ? scripts[0] : scripts;
      await axios.put(`http://localhost:8000/jobs/${currentJob.id}/script`, {
        script_json: JSON.stringify(scriptData),
      });
    } catch (error) {
      console.error('Erro ao salvar:', error);
    } finally {
      setSaving(false);
    }
  }, [currentJob?.id, scripts]);

  const handleExport = useCallback(() => {
    let md = '';
    scripts.forEach((script, idx) => {
      const title = script?.section_title || script?.title || `Episódio ${idx + 1}`;
      md += `# ${title}\n\n`;
      (script?.segments || []).forEach(seg => {
        md += `**${getSpeakerName(seg.speaker)}:** ${seg.text}\n\n`;
      });
      md += '\n---\n\n';
    });
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'roteiro.md';
    a.click();
  }, [scripts]);

  if (!hasScript) {
    return (
      <div className="script-panel">
        <div className="panel-header">
          <h3>2. Roteiro</h3>
        </div>
        <div className="empty-state">
          <div className="empty-icon">🎙️</div>
          <div className="empty-title">Aguardando roteiro...</div>
          <div className="empty-subtitle">
            Cole texto na aba de entrada e clique em "Gerar Roteiro"
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="script-panel">
      <div className="panel-header">
        <h3>2. Roteiro</h3>
        <div className="header-actions">
          <button className="btn btn-outline" onClick={handleExport}>
            📄 Exportar
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Salvando...' : '💾 Salvar'}
          </button>
          {!hasAudio && (
            <button
              className="btn btn-generate-audio"
              onClick={onGenerateAudio}
              disabled={isTtsProcessing}
            >
              {isTtsProcessing ? '⏳ Gerando...' : '🎧 Gerar Áudio'}
            </button>
          )}
        </div>
      </div>

      <div className="episodes-dashboard">
        <div className="dashboard-card">
          <div className="card-value">{scripts.length}</div>
          <div className="card-label">Episódios</div>
        </div>
        <div className="dashboard-card">
          <div className="card-value">{totalSegments}</div>
          <div className="card-label">Falas</div>
        </div>
        <div className="dashboard-card">
          <div className="card-value">~{estimatedMinutes}</div>
          <div className="card-label">Min. Total</div>
        </div>
        <div className="dashboard-card">
          <div className="card-value">
            {currentJob?.duration_seconds 
              ? `${Math.floor(currentJob.duration_seconds / 60)}:${String(Math.floor(currentJob.duration_seconds % 60)).padStart(2, '0')}`
              : '—'}
          </div>
          <div className="card-label">Duração Real</div>
        </div>
      </div>

      <div className="episodes-list">
        {scripts.map((script, idx) => {
          const epNum = idx + 1;
          const title = script?.section_title || script?.title || `Episódio ${epNum}`;
          const segments = script?.segments || [];
          const epWords = segments.reduce((a, s) => a + (s.text?.split(' ').length || 0), 0);
          const epMinutes = Math.ceil(epWords / 140);
          const isExpanded = expandedEpisode === idx;

          return (
            <div key={idx} className={`episode-card ${isExpanded ? 'expanded' : ''}`}>
              <div 
                className="episode-header" 
                onClick={() => setExpandedEpisode(isExpanded ? null : idx)}
              >
                <div className="ep-badge">EP {epNum}</div>
                <div className="episode-info">
                  <h4 className="episode-title">{title}</h4>
                </div>
                <div className="episode-stats">
                  <span className="stat">{segments.length} falas</span>
                  <span className="stat">~{epMinutes} min</span>
                </div>
                <span className="expand-icon">{isExpanded ? '▲' : '▼'}</span>
              </div>

              {isExpanded && (
                <div className="episode-content">
                  {segments.map((seg, segIdx) => {
                    const speakerLower = (seg.speaker || '').toLowerCase();
                    const isNarrator = speakerLower.includes('narrad');
                    const isWilliam = speakerLower.includes('host') || speakerLower.includes('william');
                    
                    return (
                      <div key={segIdx} className={`segment-row ${isNarrator ? 'speaker-narrator' : isWilliam ? 'speaker-william' : 'speaker-cristina'}`}>
                        <span className="segment-speaker">
                          {getSpeakerName(seg.speaker)}
                        </span>
                        <p className="segment-text">{seg.text}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default ScriptPanel;
