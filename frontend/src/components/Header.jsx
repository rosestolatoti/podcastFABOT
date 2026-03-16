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
  const { services, currentJob, setHistoryOpen } = useJobStore();
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
        <select className="llm-select" defaultValue="glm">
          <option value="glm">GLM-4-Flash ( Gratuito)</option>
          <option value="groq">llama-3.3-70b (Groq)</option>
          <option value="gemini">Gemini Flash</option>
          <option value="ollama">Ollama Local</option>
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
