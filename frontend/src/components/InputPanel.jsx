import React, { useState, useCallback } from 'react';
import useJobStore from '../store/jobStore';
import PDFViewerInline from './PDFViewerInline';
import OcrPanel from './OcrPanel';
import './InputPanel.css';

function InputPanel({ onGenerateScript, onGeneratePodcast }) {
  const { inputTab, setInputTab, currentJob, progress, progressMessage, progressError, setProgress, clearProgress } = useJobStore();
  const [files, setFiles] = useState([]);
  const [text, setText] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [previewPdf, setPreviewPdf] = useState(null);
  const [viewMode, setViewMode] = useState('input'); // 'input' ou 'preview'
  
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charCount = text.length;
  const estimatedMinutes = Math.ceil(wordCount / 140);
  
  const hasPdf = files.length > 0 && files.some(f => 
    f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
  );
  
  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);
  
  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);
  
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => {
      const ext = f.name.split('.').pop().toLowerCase();
      return ['pdf', 'docx', 'txt'].includes(ext);
    });
    
    setFiles(prev => [...prev, ...droppedFiles]);
    
    // Se for PDF, mostrar automaticamente
    if (droppedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'))) {
      setPreviewPdf(droppedFiles.find(f => f.name.toLowerCase().endsWith('.pdf')));
      setViewMode('preview');
    }
  }, []);
  
  const handleFileInput = useCallback((e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(prev => [...prev, ...selectedFiles]);
    
    // Se for PDF, mostrar automaticamente
    if (selectedFiles.some(f => f.name.toLowerCase().endsWith('.pdf'))) {
      setPreviewPdf(selectedFiles.find(f => f.name.toLowerCase().endsWith('.pdf')));
      setViewMode('preview');
    }
  }, []);
  
  const removeFile = useCallback((index) => {
    const removed = files[index];
    setFiles(prev => prev.filter((_, i) => i !== index));
    
    // Se removemos o PDF que está em preview, limpar preview
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
  }, []);
  
  const generateTitleFromText = (text) => {
    if (!text || text.trim().length < 50) return 'Novo Podcast';
    
    const cleanText = text.trim();
    const firstLines = cleanText.split('\n').slice(0, 3).join(' ');
    const words = firstLines.split(/\s+/).slice(0, 15).join(' ');
    
    if (words.length > 60) return words.substring(0, 60) + '...';
    return words || 'Novo Podcast';
  };
  
  const handleGenerateScriptClick = useCallback(() => {
    if (text.trim().length < 100 && files.length === 0) return;
    onGenerateScript({ text, files });
  }, [text, files, onGenerateScript]);
  
  const handleGeneratePodcastClick = useCallback(() => {
    if (text.trim().length < 100 && files.length === 0) return;
    onGeneratePodcast({ text, files });
  }, [text, files, onGeneratePodcast]);

  const isDisabled = text.trim().length < 100 && files.length === 0;
  
  // Verifica se há um job em processamento ativo
  const activeStatuses = ['READING', 'LLM_PROCESSING', 'TTS_PROCESSING', 'PENDING'];
  const isProcessing = currentJob && 
    currentJob.status && 
    activeStatuses.includes(currentJob.status);

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
            </div>
            
            <div className="tab-content">
              {inputTab === 'arquivos' ? (
                <div className="files-tab">
                  <div 
                    className={`dropzone ${isDragging ? 'dragging' : ''}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
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
              ) : (
                <div className="text-tab">
                  <textarea
                    className="text-input"
                    placeholder="Cole seu texto aqui — artigo, anotações, PDF convertido..."
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                  />
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
          className="btn btn-secondary"
          disabled={isDisabled || isProcessing}
          onClick={handleGenerateScriptClick}
        >
          {isProcessing ? '◌ Gerando...' : 'Gerar Roteiro 📝'}
        </button>
        <button 
          className="btn btn-primary"
          disabled={isDisabled || isProcessing}
          onClick={handleGeneratePodcastClick}
        >
          {isProcessing ? '◌ Gerando...' : 'Gerar Podcast Completo ▶'}
        </button>
      </div>
    </div>
  );
}

export default InputPanel;
