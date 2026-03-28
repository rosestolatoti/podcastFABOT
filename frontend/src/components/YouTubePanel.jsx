import React, { useState } from 'react';
import axios from 'axios';
import './YouTubePanel.css';

function YouTubePanel({ onTextExtracted }) {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [result, setResult] = useState(null);
  const [translatedText, setTranslatedText] = useState(null);
  const [error, setError] = useState(null);

  const handleTranscribe = async () => {
    if (!url.trim()) {
      setError('Cole uma URL do YouTube');
      return;
    }

    setLoading(true);
    setTranscribing(true);
    setError(null);
    setResult(null);
    setTranslatedText(null);

    try {
      const response = await axios.post('http://localhost:8000/youtube/transcribe', {
        url: url.trim(),
        idiomas: ['pt', 'pt-BR', 'en', 'en-US'],
      });

      setResult(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Erro ao transcrever';
      setError(detail);
    } finally {
      setLoading(false);
      setTranscribing(false);
    }
  };

  const handleTranslate = async () => {
    if (!result?.texto_completo) return;

    setLoading(true);
    setTranslating(true);
    setError(null);

    try {
      const response = await axios.post('http://localhost:8000/youtube/translate', {
        texto: result.texto_completo,
        idioma_destino: 'pt-BR',
      });

      setTranslatedText(response.data.texto_traduzido);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Erro ao traduzir';
      setError(detail);
    } finally {
      setLoading(false);
      setTranslating(false);
    }
  };

  const handleCopy = () => {
    const textToCopy = translatedText || result?.texto_completo;
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
    }
  };

  const handleClear = () => {
    setUrl('');
    setResult(null);
    setTranslatedText(null);
    setError(null);
  };

  const displayText = translatedText || result?.texto_completo;

  return (
    <div className="youtube-panel">
      {/* Header */}
      <div className="yt-header">
        <div className="yt-title">
          <span className="yt-icon">📺</span>
          <h3>Transcrição YouTube</h3>
        </div>
        <p className="yt-subtitle">Cole o link do vídeo para extrair o texto das legendas</p>
      </div>

      {/* Input Section */}
      <div className="yt-input-section">
        <div className="yt-input-wrapper">
          <span className="yt-input-icon">🔗</span>
          <input
            type="text"
            className="yt-url-input"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={transcribing}
          />
        </div>
        <button
          className="yt-btn yt-btn-primary"
          onClick={handleTranscribe}
          disabled={transcribing || !url.trim()}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {transcribing ? (
            <>
              <span className="yt-spinner"></span>
              Transcrevendo...
            </>
          ) : (
            <>
              <span>▶</span>
              Transcrever
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="yt-error">
          <span className="yt-error-icon">⚠️</span>
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="yt-result">
          {/* Metrics */}
          <div className="yt-metrics">
            <div className="yt-metric-card">
              <span className="yt-metric-icon">📝</span>
              <div className="yt-metric-info">
                <span className="yt-metric-value">{result.num_palavras?.toLocaleString('pt-BR')}</span>
                <span className="yt-metric-label">palavras</span>
              </div>
            </div>
            <div className="yt-metric-card">
              <span className="yt-metric-icon">⏱️</span>
              <div className="yt-metric-info">
                <span className="yt-metric-value">{result.duracao_minutos}</span>
                <span className="yt-metric-label">minutos</span>
              </div>
            </div>
            <div className="yt-metric-card">
              <span className="yt-metric-icon">🌐</span>
              <div className="yt-metric-info">
                <span className="yt-metric-value">{result.idioma}</span>
                <span className="yt-metric-label">idioma</span>
              </div>
            </div>
            {result.e_gerado && (
              <div className="yt-metric-card yt-badge-auto">
                <span className="yt-metric-icon">⚠️</span>
                <div className="yt-metric-info">
                  <span className="yt-metric-value">Auto</span>
                  <span className="yt-metric-label">legenda</span>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="yt-actions">
            <button className="yt-btn yt-btn-copy" onClick={handleCopy}>
              📋 Copiar Texto
            </button>
            
            {!translatedText ? (
              <button 
                className="yt-btn yt-btn-translate" 
                onClick={handleTranslate}
                disabled={translating}
              >
                {translating ? (
                  <>
                    <span className="yt-spinner"></span>
                    Traduzindo...
                  </>
                ) : (
                  <>
                    🔄 Traduzir para PT-BR
                  </>
                )}
              </button>
            ) : (
              <button 
                className="yt-btn yt-btn-back"
                onClick={() => setTranslatedText(null)}
              >
                ↩️ Original
              </button>
            )}
          </div>

          {/* Translated badge */}
          {translatedText && (
            <div className="yt-translated-badge">
              ✅ Texto traduzido para Português
            </div>
          )}

          {/* Preview */}
          <div className="yt-preview">
            <div className="yt-preview-header">
              <span>Preview</span>
              <span className="yt-char-count">
                {(displayText?.length || 0).toLocaleString('pt-BR')} caracteres
              </span>
            </div>
            <div className="yt-preview-content">
              {displayText?.substring(0, 800)}
              {(displayText?.length || 0) > 800 && '...'}
            </div>
            {(displayText?.length || 0) > 800 && (
              <div className="yt-preview-more">
                Texto completo será copiado ao clicar em "Copiar Texto"
              </div>
            )}
          </div>

          {/* Clear */}
          <button className="yt-btn yt-btn-clear" onClick={handleClear}>
            ✕ Limpar tudo
          </button>
        </div>
      )}
    </div>
  );
}

export default YouTubePanel;
