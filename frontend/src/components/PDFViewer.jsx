import React, { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import './PDFViewer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function PDFViewer({ file, onClose }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }) => {
    setNumPages(numPages);
    setLoading(false);
  }, []);

  const onDocumentLoadError = useCallback((err) => {
    setError('Erro ao carregar PDF: ' + err.message);
    setLoading(false);
  }, []);

  const handleZoomIn = () => setScale(s => Math.min(s + 0.25, 3.0));
  const handleZoomOut = () => setScale(s => Math.max(s - 0.25, 0.5));
  const handleZoomReset = () => setScale(1.0);

  const handlePrevPage = () => setPageNumber(p => Math.max(p - 1, 1));
  const handleNextPage = () => setPageNumber(p => Math.min(p + 1, numPages));

  const fileUrl = URL.createObjectURL(file);

  return (
    <div className="pdf-viewer-overlay" onClick={onClose}>
      <div className="pdf-viewer-container" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="pdf-viewer-header">
          <span className="pdf-viewer-title">{file.name}</span>
          <button className="pdf-viewer-close" onClick={onClose}>×</button>
        </div>

        {/* Toolbar */}
        <div className="pdf-viewer-toolbar">
          <div className="pdf-toolbar-group">
            <button onClick={handleZoomOut} title="Zoom -" className="pdf-toolbar-btn">−</button>
            <span className="pdf-zoom-level">{Math.round(scale * 100)}%</span>
            <button onClick={handleZoomIn} title="Zoom +" className="pdf-toolbar-btn">+</button>
            <button onClick={handleZoomReset} title="Zoom Padrão" className="pdf-toolbar-btn">⟲</button>
          </div>

          <div className="pdf-toolbar-group">
            <button 
              onClick={handlePrevPage} 
              disabled={pageNumber <= 1}
              title="Página Anterior"
              className="pdf-toolbar-btn"
            >
              ◀
            </button>
            <span className="pdf-page-info">
              {pageNumber} / {numPages || '?'}
            </span>
            <button 
              onClick={handleNextPage} 
              disabled={pageNumber >= (numPages || 1)}
              title="Próxima Página"
              className="pdf-toolbar-btn"
            >
              ▶
            </button>
          </div>

          <div className="pdf-toolbar-group">
            <input
              type="number"
              min={1}
              max={numPages || 1}
              value={pageNumber}
              onChange={(e) => {
                const p = parseInt(e.target.value, 10);
                if (p >= 1 && p <= (numPages || 1)) setPageNumber(p);
              }}
              className="pdf-page-input"
            />
          </div>
        </div>

        {/* PDF Content */}
        <div className="pdf-viewer-content">
          {error && <div className="pdf-error">{error}</div>}
          
          {loading && !error && (
            <div className="pdf-loading">Carregando PDF...</div>
          )}

          <Document
            file={fileUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={null}
          >
            <Page
              pageNumber={pageNumber}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </Document>
        </div>
      </div>
    </div>
  );
}

export default PDFViewer;
