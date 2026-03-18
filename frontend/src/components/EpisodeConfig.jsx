import React, { useState, useEffect } from 'react';
import useJobStore from '../store/jobStore';
import './EpisodeConfig.css';

const PODCAST_TYPES = ['monologue', 'cohost', 'interview'];
const DURATIONS = [5, 10, 15, 20, 30];
const DEPTH_LEVELS = [
  { value: 'quick', label: 'Resumo rápido' },
  { value: 'normal', label: 'Normal' },
  { value: 'detailed', label: 'Detalhado' },
];
const SPEECH_STYLES = [
  'Normal',
  'Explicativo / Professor',
  'Motivacional',
  'Formal',
  'Descontraído',
];
const LLM_MODES = [
  { value: 'gemini-2.5-flash', label: '🟢 Gemini 2.5 Flash (Recomendado)' },
  { value: 'gemini-2.5-flash-lite', label: '🟢 Gemini 2.5 Flash-Lite' },
  { value: 'gemini-2.5-pro', label: '🟢 Gemini 2.5 Pro' },
  { value: 'glm-4.7-flash', label: '🔵 GLM-4.7-Flash' },
  { value: 'glm-4-flash', label: '🔵 GLM-4-Flash' },
  { value: 'groq', label: '🟠 Llama 3.3 (Groq)' },
  { value: 'ollama', label: '🐳 Ollama Local' },
];

function EpisodeConfig() {
  const { ptbrVoices, services, setServices } = useJobStore();
  const [podcastType, setPodcastType] = useState('monologue');
  const [duration, setDuration] = useState(10);
  const [depthLevel, setDepthLevel] = useState('normal');
  const [llmMode, setLlmMode] = useState('groq');
  const [hostVoice, setHostVoice] = useState('pm_alex');
  const [cohostVoice, setCohostVoice] = useState('');
  const [speechStyle, setSpeechStyle] = useState('Normal');
  const [introMusic, setIntroMusic] = useState(null);
  
  // Atualizar voz quando vozes carregarem
  useEffect(() => {
    if (ptbrVoices.length > 0 && !ptbrVoices.includes(hostVoice)) {
      setHostVoice(ptbrVoices[0]);
    }
  }, [ptbrVoices, hostVoice]);
  
  const handleRemoveMusic = () => {
    setIntroMusic(null);
  };
  
  return (
    <div className="episode-config">
      <h3 className="section-title">CONFIGURAÇÃO DO EPISÓDIO</h3>
      
      {/* Tipo de podcast */}
      <div className="config-group">
        <label className="config-label">Tipo de podcast</label>
        <div className="radio-group">
          {PODCAST_TYPES.map(type => (
            <label key={type} className="radio-option">
              <input
                type="radio"
                name="podcastType"
                value={type}
                checked={podcastType === type}
                onChange={(e) => setPodcastType(e.target.value)}
              />
              <span className="radio-text">
                {type === 'monologue' && 'Monólogo'}
                {type === 'cohost' && 'Co-hosts'}
                {type === 'interview' && 'Entrevista'}
              </span>
            </label>
          ))}
        </div>
      </div>
      
      {/* Duração alvo */}
      <div className="config-group">
        <label className="config-label">Duração alvo</label>
        <div className="segmented-control">
          {DURATIONS.map(d => (
            <button
              key={d}
              className={`segment ${duration === d ? 'active' : ''}`}
              onClick={() => setDuration(d)}
            >
              {d}
            </button>
          ))}
          <span className="segment-label">min</span>
        </div>
      </div>
      
      {/* Profundidade */}
      <div className="config-group">
        <label className="config-label">Profundidade</label>
        <div className="radio-group">
          {DEPTH_LEVELS.map(level => (
            <label key={level.value} className="radio-option">
              <input
                type="radio"
                name="depthLevel"
                value={level.value}
                checked={depthLevel === level.value}
                onChange={(e) => setDepthLevel(e.target.value)}
              />
              <span className="radio-text">{level.label}</span>
            </label>
          ))}
        </div>
      </div>
      
      {/* Modo IA */}
      <div className="config-group">
        <label className="config-label">Modo IA</label>
        <div className="select-wrapper">
          <select 
            value={llmMode} 
            onChange={(e) => setLlmMode(e.target.value)}
            className="config-select"
          >
            {LLM_MODES.map(mode => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </select>
          <span className={`status-badge ${services.groq === 'up' ? 'up' : 'down'}`}>
            ● {services.groq === 'up' ? 'UP' : 'DOWN'}
          </span>
        </div>
      </div>
      
      {/* Voz do Host */}
      <div className="config-group">
        <label className="config-label">Voz do Host</label>
        {ptbrVoices.length > 0 ? (
          <select 
            value={hostVoice}
            onChange={(e) => setHostVoice(e.target.value)}
            className="config-select"
          >
            {ptbrVoices.map(voice => (
              <option key={voice} value={voice}>
                {voice} — {voice.startsWith('pm_') ? 'Masculino' : 'Feminino'} PT-BR
              </option>
            ))}
          </select>
        ) : (
          <div className="warning">
            ⚠ Nenhuma voz PT-BR disponível
          </div>
        )}
      </div>
      
      {/* Voz do Co-host */}
      {podcastType !== 'monologue' && (
        <div className="config-group">
          <label className="config-label">Voz do Co-host</label>
          <select 
            value={cohostVoice}
            onChange={(e) => setCohostVoice(e.target.value)}
            className="config-select"
          >
            <option value="">Selecione...</option>
            {ptbrVoices
              .filter(v => v !== hostVoice)
              .map(voice => (
                <option key={voice} value={voice}>
                  {voice} — {voice.startsWith('pm_') ? 'Masculino' : 'Feminino'} PT-BR
                </option>
              ))
            }
          </select>
        </div>
      )}
      
      {/* Estilo de fala */}
      <div className="config-group">
        <label className="config-label">Estilo de fala</label>
        <select 
          value={speechStyle}
          onChange={(e) => setSpeechStyle(e.target.value)}
          className="config-select"
        >
          {SPEECH_STYLES.map(style => (
            <option key={style} value={style}>{style}</option>
          ))}
        </select>
      </div>
      
      {/* Música de introdução */}
      <div className="config-group">
        <label className="config-label">Música de introdução</label>
        {introMusic ? (
          <div className="music-selected">
            <span className="music-name">{introMusic.name}</span>
            <button className="music-remove" onClick={handleRemoveMusic}>×</button>
          </div>
        ) : (
          <div className="music-options">
            <label className="music-btn">
              Selecionar arquivo MP3
              <input 
                type="file" 
                accept=".mp3,.wav"
                hidden
                onChange={(e) => setIntroMusic(e.target.files[0])}
              />
            </label>
            <span className="music-or">ou</span>
            <button className="music-none">Sem música</button>
          </div>
        )}
      </div>
    </div>
  );
}

export default EpisodeConfig;
