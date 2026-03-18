import React, { useEffect, useCallback } from 'react';
import axios from 'axios';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import useJobStore from './store/jobStore';
import useHealthCheck from './hooks/useHealthCheck';
import useVoices from './hooks/useVoices';
import Header from './components/Header';
import InputPanel from './components/InputPanel';
import ScriptPanel from './components/ScriptPanel';
import PlayerPanel from './components/PlayerPanel';
import './styles/tokens.css';
import './App.css';

const queryClient = new QueryClient();

// Initialize theme on load
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark');
}

function AppContent() {
  const { 
    historyOpen, 
    setHistoryOpen,
    currentJob,
    currentJobId,
    setCurrentJob,
    setCurrentJobId,
    setJobHistory,
    activeTab,
    setActiveTab,
    llmMode,
    setProgress,
    clearProgress,
    resetCurrentJob
  } = useJobStore();
  
  useHealthCheck();
  useVoices();
  
  // Carregar job atual do backend quando a página carrega
  useEffect(() => {
    const loadCurrentJob = async () => {
      if (currentJobId) {
        try {
          const response = await axios.get(`http://localhost:8000/jobs/${currentJobId}`);
          setCurrentJob(response.data);
          if (response.data.status === 'DONE') {
            setActiveTab('player');
          } else if (response.data.status === 'SCRIPT_DONE') {
            setActiveTab('roteiro');
          }
        } catch (error) {
          console.error('[loadCurrentJob] Erro:', error);
        }
      }
    };
    loadCurrentJob();
  }, [currentJobId, setCurrentJob, setActiveTab]);
  
  // Carregar histórico
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const response = await axios.get('http://localhost:8000/jobs/history');
        setJobHistory(response.data.jobs || []);
      } catch (error) {
        console.error('[loadHistory] Erro:', error);
      }
    };
    loadHistory();
  }, [setJobHistory]);
  
  // Gerar apenas roteiro (texto) - não gera áudio
  const handleGenerateScript = useCallback(async (data) => {
    console.log('[handleGenerateScript] Recebido:', data);
    
    // Limpar job anterior antes de criar novo
    resetCurrentJob();
    
    try {
      let jobId;
      
      // Iniciar progresso
      setProgress(20, 'Criando job...');
      
      if (data.text && data.text.trim().length >= 100) {
        const params = new URLSearchParams({
          title: data.title || 'Novo Podcast',
          text: data.text,
          llm_mode: llmMode,
          voice_host: 'pm_alex',
          podcast_type: 'monologue',
          target_duration: '10',
        });
        
        const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);
        jobId = response.data.job_id;
      } else if (data.files && data.files.length > 0) {
        const formData = new FormData();
        formData.append('file', data.files[0]);
        formData.append('title', data.files[0].name);
        formData.append('llm_mode', llmMode);
        formData.append('voice_host', 'pm_alex');
        
        const response = await axios.post('http://localhost:8000/upload/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        jobId = response.data.job_id;
      }
      
      if (jobId) {
        setCurrentJobId(jobId);
        setActiveTab('progresso');
        setProgress(40, 'Gerando roteiro com IA...');
        
        // Gera apenas roteiro (LLM), sem áudio
        await axios.post(`http://localhost:8000/jobs/${jobId}/generate-script`);
        
        // Poll até ter roteiro pronto
        const pollScript = async () => {
          const res = await axios.get(`http://localhost:8000/jobs/${jobId}`);
          setCurrentJob(res.data);
          
          // Atualizar progresso baseado no status
          const status = res.data.status;
          if (status === 'LLM_PROCESSING') {
            setProgress(60, 'Finalizando roteiro...');
          } else if (status === 'SCRIPT_DONE') {
            setProgress(100, 'Roteiro pronto!');
            setTimeout(() => {
              clearProgress();
              setActiveTab('roteiro');
            }, 1000);
            return;
          } else if (status === 'FAILED') {
            setProgress(100, 'Erro: ' + (res.data.error_message || 'Falha ao gerar'), true);
            return;
          } else if (status === 'DONE') {
            setProgress(100, 'Podcast completo!');
            setTimeout(() => {
              clearProgress();
              setActiveTab('player');
            }, 1000);
            return;
          }
          
          setTimeout(pollScript, 2000);
        };
        pollScript();
      }
    } catch (error) {
      console.error('[handleGenerateScript] Erro:', error);
      setProgress(100, 'Erro: ' + error.message, true);
    }
  }, [setCurrentJob, setCurrentJobId, setActiveTab, setProgress, clearProgress]);
  
  // Gerar áudio a partir do roteiro existente
  const handleGenerateAudio = useCallback(async () => {
    if (!currentJobId || !currentJob) return;
    
    try {
      // Já tem roteiro, só gerar áudio
      await axios.post(`http://localhost:8000/jobs/${currentJobId}/start-tts`);
      
      setActiveTab('player');
      
      const pollAudio = async () => {
        const res = await axios.get(`http://localhost:8000/jobs/${currentJobId}`);
        setCurrentJob(res.data);
        
        if (res.data.status === 'DONE') {
          setActiveTab('player');
          return;
        }
        if (res.data.status === 'FAILED') {
          alert('Erro ao gerar áudio: ' + res.data.error_message);
          return;
        }
        
        setTimeout(pollAudio, 2000);
      };
      pollAudio();
    } catch (error) {
      console.error('[handleGenerateAudio] Erro:', error);
      alert('Erro ao gerar áudio: ' + error.message);
    }
  }, [currentJobId, currentJob, setCurrentJob, setActiveTab]);
  
  // Gerar podcast completo (roteiro + áudio)
  const handleGeneratePodcast = useCallback(async (data) => {
    console.log('[handleGeneratePodcast] Recebido:', data);
    
    // Limpar job anterior antes de criar novo
    resetCurrentJob();
    
    try {
      let jobId;
      
      // Iniciar progresso
      setProgress(10, 'Criando job...');
      
      if (data.text && data.text.trim().length >= 100) {
        const params = new URLSearchParams({
          title: data.title || 'Novo Podcast',
          text: data.text,
          llm_mode: llmMode,
          voice_host: 'pm_alex',
          podcast_type: 'monologue',
          target_duration: '10',
        });
        
        const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);
        jobId = response.data.job_id;
      } else if (data.files && data.files.length > 0) {
        const formData = new FormData();
        formData.append('file', data.files[0]);
        formData.append('title', data.files[0].name);
        formData.append('llm_mode', llmMode);
        formData.append('voice_host', 'pm_alex');
        
        const response = await axios.post('http://localhost:8000/upload/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        jobId = response.data.job_id;
      }
      
      if (jobId) {
        setCurrentJobId(jobId);
        setActiveTab('progresso');
        setProgress(30, 'Gerando roteiro com IA...');
        
        // Gera tudo (roteiro + áudio)
        await axios.post(`http://localhost:8000/jobs/${jobId}/start`);
        
        const pollJob = async () => {
          const res = await axios.get(`http://localhost:8000/jobs/${jobId}`);
          setCurrentJob(res.data);
          
          // Atualizar progresso baseado no status
          const status = res.data.status;
          const progressVal = res.data.progress || 0;
          
          if (status === 'LLM_PROCESSING') {
            setProgress(40 + Math.floor(progressVal * 0.3), 'Gerando roteiro... ' + Math.floor(40 + progressVal * 0.3) + '%');
          } else if (status === 'SCRIPT_DONE' || status === 'TTS_PROCESSING') {
            setProgress(70 + Math.floor(progressVal * 0.2), 'Gerando áudio... ' + Math.floor(70 + progressVal * 0.2) + '%');
          } else if (status === 'DONE') {
            setProgress(100, 'Podcast completo!');
            setTimeout(() => {
              clearProgress();
              setActiveTab('player');
            }, 1000);
            return;
          } else if (status === 'FAILED') {
            setProgress(100, 'Erro: ' + (res.data.error_message || 'Falha ao gerar'), true);
            return;
          }
          
          setTimeout(pollJob, 2000);
        };
        pollJob();
      }
    } catch (error) {
      console.error('[handleGeneratePodcast] Erro:', error);
      setProgress(100, 'Erro: ' + error.message, true);
    }
  }, [setCurrentJob, setCurrentJobId, setActiveTab, setProgress, clearProgress]);
  
  return (
    <div className="app">
      <Header />
      
      <div className="main-layout three-columns">
        <div className="column column-input">
          <InputPanel 
            onGenerateScript={handleGenerateScript}
            onGeneratePodcast={handleGeneratePodcast}
          />
        </div>
        
        <div className="column column-script">
          <ScriptPanel 
            onGenerateAudio={handleGenerateAudio}
          />
        </div>
        
        <div className="column column-player">
          <PlayerPanel />
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
