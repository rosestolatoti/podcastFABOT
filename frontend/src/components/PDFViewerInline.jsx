import React, { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

function PDFViewerInline({ file, onClose }) {
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

  const handleZoomIn = () => setScale(s => Math.min(s + 0.25, 2.5));
  const handleZoomOut = () => setScale(s => Math.max(s - 0.25, 0.5));
  const handleZoomReset = () => setScale(1.0);

  const handlePrevPage = () => setPageNumber(p => Math.max(p - 1, 1));
  const handleNextPage = () => setPageNumber(p => Math.min(p + 1, numPages || 1));

  const handlePageInput = (e) => {
    const p = parseInt(e.target.value, 10);
    if (p >= 1 && p <= (numPages || 1)) setPageNumber(p);
  };

  const fileUrl = URL.createObjectURL(file);

  return (
    <div className="pdf-viewer-wrapper">
      <div className="pdf-toolbar-inline">
        <button onClick={handleZoomOut} className="pdf-tool-btn" title="Zoom -">−</button>
        <span className="pdf-zoom">{Math.round(scale * 100)}%</span>
        <button onClick={handleZoomIn} className="pdf-tool-btn" title="Zoom +">+</button>
        <button onClick={handleZoomReset} className="pdf-tool-btn" title="Zoom Padrão">⟲</button>
        
        <span className="pdf-divider">|</span>
        
        <button onClick={handlePrevPage} disabled={pageNumber <= 1} className="pdf-tool-btn" title="Página Anterior">◀</button>
        <input
          type="number"
          min={1}
          max={numPages || 1}
          value={pageNumber}
          onChange={handlePageInput}
          className="pdf-page-input"
        />
        <span className="pdf-page">/ {numPages || '?'}</span>
        <button onClick={handleNextPage} disabled={pageNumber >= (numPages || 1)} className="pdf-tool-btn" title="Próxima Página">▶</button>
      </div>
      
      <div className="pdf-scroll-area">
        {error && <div className="pdf-error">{error}</div>}
        {loading && !error && <div className="pdf-loading">Carregando PDF...</div>}
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
  );
}

export default PDFViewerInline;
