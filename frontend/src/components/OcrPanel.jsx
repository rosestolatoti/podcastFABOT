import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './OcrPanel.css';

function OcrPanel({ onUseText }) {
  const [file, setFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [result, setResult] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [savedText, setSavedText] = useState('');
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (result?.success && result.result?.text) {
      setSavedText(result.result.text);
    }
  }, [result]);

  const handleFileSelect = async (selectedFile) => {
    if (!selectedFile) return;
    
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/tiff', 'image/webp', 'application/pdf'];
    
    if (!validTypes.includes(selectedFile.type) && !selectedFile.name.match(/\.(jpg|jpeg|png|gif|bmp|tiff|webp|pdf)$/i)) {
      alert('Tipo de arquivo não suportado. Use: JPG, PNG, GIF, BMP, TIFF, WebP ou PDF');
      return;
    }

    setFile(selectedFile);
    setResult(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const extractText = async () => {
    if (!file) return;

    setExtracting(true);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/ocr/extract', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });

      setResult(response.data);
    } catch (error) {
      console.error('Erro ao extrair texto:', error);
      setResult({
        success: false,
        error: error.response?.data?.detail || error.message || 'Erro ao processar arquivo'
      });
    } finally {
      setExtracting(false);
    }
  };

  const copyToClipboard = () => {
    if (result?.result?.text) {
      navigator.clipboard.writeText(result.result.text);
      alert('Texto copiado para a área de transferência!');
    }
  };

  const useAsSource = () => {
    if (result?.result?.text) {
      onUseText(result.result.text);
    }
  };

  const clearAll = () => {
    setFile(null);
    setResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const clearSavedText = () => {
    setSavedText('');
  };

  return (
    <div className="ocr-panel">
      <div className="ocr-header">
        <h3>📷 OCR - Extrair Texto</h3>
        <p className="ocr-description">
          Extraia texto de fotos e PDFs. Depois use na aba "Texto" para gerar podcasts.
        </p>
      </div>

      {!file ? (
        <div
          className={`ocr-dropzone ${dragOver ? 'drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="dropzone-content">
            <span className="dropzone-icon">📷</span>
            <p>Arraste uma imagem ou PDF aqui</p>
            <p className="dropzone-hint">ou clique para selecionar</p>
            <p className="dropzone-formats">JPG, PNG, GIF, BMP, TIFF, WebP, PDF</p>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.gif,.bmp,.tiff,.webp,.pdf"
            onChange={(e) => handleFileSelect(e.target.files[0])}
            style={{ display: 'none' }}
          />
        </div>
      ) : (
        <div className="ocr-file-info">
          <div className="file-preview">
            <span className="file-icon">
              {file.type.includes('image') ? '🖼️' : '📄'}
            </span>
            <div className="file-details">
              <p className="file-name">{file.name}</p>
              <p className="file-size">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <button className="clear-btn" onClick={clearAll} title="Remover arquivo">
              ✕
            </button>
          </div>

          <button
            className="btn btn-primary ocr-extract-btn"
            onClick={extractText}
            disabled={extracting}
          >
            {extracting ? (
              <>
                <span className="spinner"></span>
                Extraindo texto...
              </>
            ) : (
              <>
                🔍 Extrair Texto
              </>
            )}
          </button>
        </div>
      )}

      {extracting && (
        <div className="ocr-loading">
          <div className="loading-spinner"></div>
          <p>Processando imagem/PDF...</p>
          <p className="loading-hint">Isso pode levar alguns segundos</p>
        </div>
      )}

      {result && (
        <div className={`ocr-result ${result.success ? 'success' : 'error'}`}>
          {result.success ? (
            <>
              <div className="result-header">
                <h4>✅ Texto Extraído</h4>
                <div className="result-stats">
                  <span>📝 {result.result.char_count} caracteres</span>
                  <span>📖 {result.result.word_count} palavras</span>
                  {result.result.confidence && (
                    <span>🎯 {result.result.confidence}% confiança</span>
                  )}
                </div>
              </div>

              <div className="result-text-container">
                <textarea
                  className="result-text"
                  value={result.result.text}
                  readOnly
                  rows={10}
                />
              </div>

              <div className="result-actions">
                <button className="btn btn-secondary" onClick={copyToClipboard}>
                  📋 Copiar Texto
                </button>
                <button className="btn btn-success" onClick={useAsSource}>
                  ➡️ Usar como Fonte
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="result-header">
                <h4>❌ Erro</h4>
              </div>
              <p className="error-message">{result.error || 'Erro ao processar arquivo'}</p>
              <button className="btn btn-secondary" onClick={clearAll}>
                Tentar Novamente
              </button>
            </>
          )}
        </div>
      )}

      {savedText && !result && (
        <div className="ocr-saved-text">
          <div className="saved-header">
            <h4>📋 Texto Salvo</h4>
            <button className="clear-saved-btn" onClick={clearSavedText} title="Limpar texto salvo">
              🗑️
            </button>
          </div>
          <div className="result-text-container">
            <textarea
              className="result-text"
              value={savedText}
              readOnly
              rows={10}
            />
          </div>
          <div className="result-actions">
            <button className="btn btn-secondary" onClick={() => {
              navigator.clipboard.writeText(savedText);
              alert('Texto copiado!');
            }}>
              📋 Copiar Texto
            </button>
            <button className="btn btn-success" onClick={() => onUseText(savedText)}>
              ➡️ Usar como Fonte
            </button>
          </div>
        </div>
      )}

      {!file && !result && savedText && (
        <div className="ocr-saved-text">
          <div className="saved-header">
            <h4>📋 Texto Salvo</h4>
            <button className="clear-saved-btn" onClick={clearSavedText} title="Limpar texto salvo">
              🗑️
            </button>
          </div>
          <div className="result-text-container">
            <textarea
              className="result-text"
              value={savedText}
              readOnly
              rows={10}
            />
          </div>
          <div className="result-actions">
            <button className="btn btn-secondary" onClick={() => {
              navigator.clipboard.writeText(savedText);
              alert('Texto copiado!');
            }}>
              📋 Copiar Texto
            </button>
            <button className="btn btn-success" onClick={() => onUseText(savedText)}>
              ➡️ Usar como Fonte
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default OcrPanel;
