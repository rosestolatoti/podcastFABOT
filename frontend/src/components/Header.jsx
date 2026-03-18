import React, { useState } from 'react';
import useJobStore from '../store/jobStore';
import './Header.css';

function ServiceBadge({ name, status }) {
  const statusClass = status === 'up' ? 'up' : status === 'down' ? 'down' : 'unknown';
  
  return (
    <span className={`service-badge ${statusClass}`}>
      {name}
      {status === 'up' && <span className="dot"></span>}
    </span>
  );
}

function Header({ onHistoryClick }) {
  const { services, currentJob, setHistoryOpen, llmMode, setLlmMode } = useJobStore();
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem('theme') === 'dark';
  });

  const toggleDarkMode = () => {
    const newMode = !darkMode;
    setDarkMode(newMode);
    localStorage.setItem('theme', newMode ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', newMode ? 'dark' : 'light');
  };
  
  return (
    <header className="header">
      <div className="header-left">
        <span className="logo">
          🎤 PODCAST DO FABOT
        </span>
      </div>
      
      <div className="header-center">
        <ServiceBadge name="Edge TTS" status={services.kokoro} />
        <ServiceBadge name="Redis" status={services.redis} />
        <ServiceBadge name="Groq" status={services.groq} />
        <ServiceBadge name="SQLite" status={services.backend} />
      </div>
      
      <div className="header-right">
        <select className="llm-select" value={llmMode} onChange={(e) => setLlmMode(e.target.value)}>
          <optgroup label="🟢 Gemini (Grátis)">
            <option value="gemini-2.5-flash">Gemini 2.5 Flash (Recomendado)</option>
            <option value="gemini-2.5-flash-lite">Gemini 2.5 Flash-Lite</option>
            <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
          </optgroup>
          <optgroup label="🔵 GLM (Grátis)">
            <option value="glm-4.7-flash">GLM-4.7-Flash</option>
            <option value="glm-4-flash">GLM-4-Flash</option>
          </optgroup>
          <optgroup label="🟠 Groq (Grátis)">
            <option value="groq">Llama 3.3 (Groq)</option>
          </optgroup>
        </select>
        
        {currentJob && (
          <span className="current-job">
            Job: {currentJob.title}
          </span>
        )}
        
        <button 
          className="theme-toggle" 
          onClick={toggleDarkMode}
          title={darkMode ? 'Modo Claro' : 'Modo Escuro'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
        
        <button className="history-btn" onClick={() => setHistoryOpen(true)}>
          Histórico
        </button>
      </div>
    </header>
  );
}

export default Header;
