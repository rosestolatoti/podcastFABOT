import React, { useState, useCallback, useRef, useEffect } from 'react';
import useJobStore from '../store/jobStore';
import PDFViewerInline from './PDFViewerInline';
import OcrPanel from './OcrPanel';
import YouTubePanel from './YouTubePanel';
import './InputPanel.css';

const MAX_TOPICS = 10;

function InputPanel({ onGenerateScript }) {
  const { inputTab, setInputTab, currentJob, progress, progressMessage, progressError, setProgress, clearProgress } = useJobStore();
  const [files, setFiles] = useState([]);
  const [text, setText] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [previewPdf, setPreviewPdf] = useState(null);
  const [viewMode, setViewMode] = useState('input');

  // ═══ MARCA-TEXTO: Estados ═══
  const [topics, setTopics] = useState([]);
  const [showPin, setShowPin] = useState(false);
  const [pinPosition, setPinPosition] = useState({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState('');
  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const textareaRef = useRef(null);
  const pinTimeoutRef = useRef(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charCount = text.length;
  const estimatedMinutes = Math.ceil(wordCount / 140);

  const hasPdf = files.length > 0 && files.some(f =>
    f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
  );

  // ═══ MARCA-TEXTO: Detectar seleção de texto ═══
  const handleTextMouseUp = useCallback((e) => {
    // Limpar timeout anterior
    if (pinTimeoutRef.current) {
      clearTimeout(pinTimeoutRef.current);
    }

    const selection = window.getSelection();
    const selected = selection?.toString().trim();

    if (!selected || selected.length < 2 || selected.length > 100) {
      // Esconder pin após delay (permite clicar no pin)
      pinTimeoutRef.current = setTimeout(() => {
        setShowPin(false);
        setSelectedText('');
      }, 200);
      return;
    }

    if (topics.length >= MAX_TOPICS) {
      setShowPin(false);
      return;
    }

    // Calcular posição do pin perto da seleção
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    setPinPosition({
      x: rect.right + 8,
      y: rect.top - 4,
    });
    setSelectedText(selected);
    setShowPin(true);
  }, [topics.length]);

  // ═══ MARCA-TEXTO: Adicionar tópico ═══
  const handleAddTopic = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (!selectedText || topics.length >= MAX_TOPICS) return;

    // Verificar se já existe
    const exists = topics.some(
      t => t.text.toLowerCase() === selectedText.toLowerCase()
    );
    if (exists) {
      setShowPin(false);
      setSelectedText('');
      return;
    }

    setTopics(prev => [
      ...prev,
      { text: selectedText, order: prev.length + 1 }
    ]);
    setShowPin(false);
    setSelectedText('');

    // Limpar seleção do textarea
    window.getSelection()?.removeAllRanges();
  }, [selectedText, topics]);

  // ═══ MARCA-TEXTO: Remover tópico ═══
  const handleRemoveTopic = useCallback((index) => {
    setTopics(prev => {
      const updated = prev.filter((_, i) => i !== index);
      // Renumerar
      return updated.map((t, i) => ({ ...t, order: i + 1 }));
    });
  }, []);

  // ═══ MARCA-TEXTO: Limpar todos os tópicos ═══
  const handleClearTopics = useCallback(() => {
    setTopics([]);
  }, []);

  // ═══ MARCA-TEXTO: Drag & Drop para reordenar ═══
  const handleDragStart = useCallback((e, index) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    // Imagem de drag transparente (para manter visual do chip)
    const dragImage = e.target.cloneNode(true);
    dragImage.style.opacity = '0.8';
    dragImage.style.position = 'absolute';
    dragImage.style.top = '-1000px';
    document.body.appendChild(dragImage);
    e.dataTransfer.setDragImage(dragImage, 0, 0);
    setTimeout(() => document.body.removeChild(dragImage), 0);
  }, []);

  const handleDragOver = useCallback((e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDragIndex(null);
    setDragOverIndex(null);
  }, []);

  const handleDrop = useCallback((e, dropIndex) => {
    e.preventDefault();
    if (dragIndex === null || dragIndex === dropIndex) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }

    setTopics(prev => {
      const updated = [...prev];
      const [moved] = updated.splice(dragIndex, 1);
      updated.splice(dropIndex, 0, moved);
      // Renumerar
      return updated.map((t, i) => ({ ...t, order: i + 1 }));
    });

    setDragIndex(null);
    setDragOverIndex(null);
  }, [dragIndex]);

  // ═══ ESCONDER PIN quando clica fora ═══
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (e.target.closest('.pin-button')) return;
      // Delay para permitir clicar no pin
      pinTimeoutRef.current = setTimeout(() => {
        setShowPin(false);
      }, 150);
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // ═══ HANDLERS EXISTENTES (sem mudanças) ═══
  const handleDragOverFile = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeaveFile = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDropFile = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => {
      const ext = f.name.split('.').pop().toLowerCase();
      return ['pdf', 'docx', 'txt'].includes(ext);
    });

    setFiles(prev => [...prev, ...droppedFiles]);

    if (droppedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'))) {
      setPreviewPdf(droppedFiles.find(f => f.name.toLowerCase().endsWith('.pdf')));
      setViewMode('preview');
    }
  }, []);

  const handleFileInput = useCallback((e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(prev => [...prev, ...selectedFiles]);

    if (selectedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'))) {
      setPreviewPdf(selectedFiles.find(f => f.name.toLowerCase().endsWith('.pdf')));
      setViewMode('preview');
    }
  }, []);

  const removeFile = useCallback((index) => {
    const removed = files[index];
    setFiles(prev => prev.filter((_, i) => i !== index));

    if (previewPdf && removed === previewPdf) {
      setPreviewPdf(null);
      setViewMode('input');
    }
  }, [files, previewPdf]);

  const showPdfPreview = useCallback((file) => {
    setPreviewPdf(file);
    setViewMode('preview');
  }, []);

  const showInput = useCallback(() => {
    setViewMode('input');
  }, []);

  const handleOcrTextExtracted = useCallback((extractedText) => {
    setText(extractedText);
    setInputTab('texto');
  }, []);

  const handleClear = useCallback(() => {
    setText('');
    setFiles([]);
    setPreviewPdf(null);
    setViewMode('input');
    setTopics([]);  // ← NOVO: Limpar tópicos também
  }, []);

  // ═══ GERAR ROTEIRO (modificado para enviar topics) ═══
  const handleGenerateScriptClick = useCallback(() => {
    if (text.trim().length < 100 && files.length === 0) return;
    onGenerateScript({
      text,
      files,
      topics: topics.map(t => t.text),  // ← NOVO: Enviar array de strings
    });
  }, [text, files, topics, onGenerateScript]);

  const isDisabled = text.trim().length < 100 && files.length === 0;

  const activeStatuses = ['READING', 'LLM_PROCESSING', 'TTS_PROCESSING', 'PENDING'];
  const isProcessing = currentJob &&
    currentJob.status &&
    activeStatuses.includes(currentJob.status);

  // ═══ TEXTO DO BOTÃO (dinâmico) ═══
  const getButtonText = () => {
    if (isProcessing) return '⏳ Gerando...';
    if (topics.length > 0) {
      return `Gerar ${topics.length} Episódio${topics.length > 1 ? 's' : ''} Sequencia${topics.length > 1 ? 'is' : 'l'} 📝`;
    }
    return 'Gerar Roteiro 📝';
  };

  return (
    <div className="input-panel">
      <div className="panel-header">
        <h3>1. Entrada</h3>
        <span className="panel-subtitle">Upload arquivo ou cole texto</span>
      </div>

      <div className="input-content-area">
        {hasPdf && viewMode === 'preview' && previewPdf ? (
          <div className="pdf-preview-container">
            <div className="pdf-preview-header">
              <button className="back-btn" onClick={showInput}>
                ← Voltar
              </button>
              <span className="pdf-name">{previewPdf.name}</span>
            </div>
            <PDFViewerInline file={previewPdf} onClose={() => {}} />
          </div>
        ) : (
          <>
            <div className="tabs">
              <button
                className={`tab ${inputTab === 'arquivos' ? 'active' : ''}`}
                onClick={() => setInputTab('arquivos')}
              >
                Arquivos
              </button>
              <button
                className={`tab ${inputTab === 'texto' ? 'active' : ''}`}
                onClick={() => setInputTab('texto')}
              >
                Texto
              </button>
              <button
                className={`tab ${inputTab === 'ocr' ? 'active' : ''}`}
                onClick={() => setInputTab('ocr')}
              >
                OCR
              </button>
              <button
                className={`tab ${inputTab === 'youtube' ? 'active' : ''}`}
                onClick={() => setInputTab('youtube')}
              >
                YouTube
              </button>
            </div>

            <div className="tab-content">
              {inputTab === 'arquivos' ? (
                <div className="files-tab">
                  <div
                    className={`dropzone ${isDragging ? 'dragging' : ''}`}
                    onDragOver={handleDragOverFile}
                    onDragLeave={handleDragLeaveFile}
                    onDrop={handleDropFile}
                  >
                    <svg className="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    <span className="dropzone-text">Arraste PDF, DOCX ou TXT</span>
                    <label className="dropzone-btn">
                      Selecionar arquivo
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.docx,.txt"
                        onChange={handleFileInput}
                        hidden
                      />
                    </label>
                  </div>

                  {files.length > 0 && (
                    <div className="file-list">
                      {files.map((file, index) => (
                        <div key={index} className="file-item">
                          <span className="file-icon">📄</span>
                          <span className="file-name">{file.name}</span>
                          <span className="file-size">{Math.round(file.size / 1024)} KB</span>
                          {(file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) && (
                            <button
                              className="file-view"
                              onClick={() => showPdfPreview(file)}
                              title="Visualizar PDF"
                            >
                              👁
                            </button>
                          )}
                          <button className="file-remove" onClick={() => removeFile(index)}>×</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : inputTab === 'ocr' ? (
                <div className="ocr-tab">
                  <OcrPanel onUseText={handleOcrTextExtracted} />
                </div>
              ) : inputTab === 'youtube' ? (
                <div className="youtube-tab">
                  <YouTubePanel />
                </div>
              ) : (
                <div className="text-tab">
                  {/* ═══ TEXTAREA COM MARCA-TEXTO ═══ */}
                  <textarea
                    ref={textareaRef}
                    className={`text-input ${text.length > 0 ? 'highlighter-mode' : ''}`}
                    placeholder="Cole seu texto aqui — artigo, anotações, PDF convertido...

💡 Dica: Selecione palavras/frases para definir os tópicos de cada episódio do podcast."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    onMouseUp={handleTextMouseUp}
                  />

                  {/* ═══ BOTÃO 📌 FLUTUANTE ═══ */}
                  {showPin && (
                    <button
                      className="pin-button"
                      style={{
                        left: `${pinPosition.x}px`,
                        top: `${pinPosition.y}px`,
                      }}
                      onClick={handleAddTopic}
                      onMouseDown={(e) => e.preventDefault()}
                      title={`Marcar "${selectedText.substring(0, 30)}${selectedText.length > 30 ? '...' : ''}" como tópico`}
                    >
                      📌
                    </button>
                  )}

                  {/* ═══ LISTA DE TÓPICOS MARCADOS ═══ */}
                  {topics.length > 0 && (
                    <div className="topics-container">
                      <div className="topics-header">
                        <span className="topics-title">
                          📌 Tópicos dos Episódios
                        </span>
                        <span className="topics-counter">
                          {topics.length} de {MAX_TOPICS}
                          <button
                            className="topics-clear-btn"
                            onClick={handleClearTopics}
                            title="Limpar todos"
                          >
                            🗑
                          </button>
                        </span>
                      </div>

                      <div className="topics-list">
                        {topics.map((topic, idx) => (
                          <div
                            key={`${topic.text}-${idx}`}
                            className={`topic-chip ${
                              dragIndex === idx ? 'dragging' : ''
                            } ${dragOverIndex === idx ? 'drag-over' : ''}`}
                            draggable
                            onDragStart={(e) => handleDragStart(e, idx)}
                            onDragOver={(e) => handleDragOver(e, idx)}
                            onDragEnd={handleDragEnd}
                            onDrop={(e) => handleDrop(e, idx)}
                          >
                            <span className="topic-number">{idx + 1}</span>
                            <span className="topic-text" title={topic.text}>
                              {topic.text}
                            </span>
                            <button
                              className="topic-remove"
                              onClick={() => handleRemoveTopic(idx)}
                              title="Remover tópico"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="topics-hint">
                        ↕ Arraste para reordenar • ✕ Clique para remover
                        • Cada tópico = 1 episódio sequencial
                      </div>
                    </div>
                  )}

                  {/* ═══ INDICADOR DE MARCA-TEXTO (quando não tem tópicos) ═══ */}
                  {topics.length === 0 && text.length > 100 && (
                    <div className="highlighter-hint">
                      <span className="highlighter-hint-icon">🖍️</span>
                      <span>
                        Selecione palavras no texto acima para definir os
                        episódios do podcast, ou clique em Gerar Roteiro
                        para geração automática.
                      </span>
                    </div>
                  )}

                  <div className="text-footer">
                    <span className="text-stats">
                      {charCount} caracteres · {wordCount} palavras · ~{estimatedMinutes} min
                    </span>
                    <button className="clear-btn" onClick={handleClear}>
                      Limpar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="action-buttons">
        <button
          className="btn btn-primary btn-generate-script"
          disabled={isDisabled || isProcessing}
          onClick={handleGenerateScriptClick}
        >
          {getButtonText()}
        </button>
      </div>
    </div>
  );
}

export default InputPanel;