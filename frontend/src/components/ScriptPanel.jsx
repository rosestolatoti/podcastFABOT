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
  
  useEffect(() => {
    console.log('Current job:', currentJob?.id, 'script_json:', currentJob?.script_json ? 'YES' : 'NO');
    if (currentJob?.script_json) {
      try {
        let script;
        if (typeof currentJob.script_json === 'string') {
          script = JSON.parse(currentJob.script_json);
        } else {
          script = currentJob.script_json;
        }
        console.log('Parsed script, segments:', script.segments?.length);
        setScriptData(script);
        setEditedSegments(script.segments || []);
      } catch (e) {
        console.error('Parse error:', e);
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
    if (speaker.toUpperCase() === 'NARRADOR') return 'narrador';
    if (speaker.toUpperCase() === 'WILLIAM') return 'william';
    return 'cristina';
  };
  
  const getSpeakerName = (speaker) => {
    if (!speaker) return '???';
    if (speaker.toUpperCase() === 'NARRADOR') return 'NARRADORA';
    if (speaker.toUpperCase() === 'WILLIAM') return 'WILLIAM';
    return 'CRISTINA';
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
      </div>
      
      {!hasScript ? (
        <div className="empty-state">
          <div className="empty-icon">📝</div>
          <div className="empty-title">Nenhum roteiro ainda</div>
          <div className="empty-subtitle">
            Cole texto na aba de entrada e clique em "Gerar Roteiro"
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
