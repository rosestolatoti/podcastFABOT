import React, { useEffect, useCallback, useState } from 'react';
import axios from 'axios';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import useJobStore from './store/jobStore';
import useHealthCheck from './hooks/useHealthCheck';
import useVoices from './hooks/useVoices';
import Header from './components/Header';
import InputPanel from './components/InputPanel';
import ScriptPanel from './components/ScriptPanel';
import PlayerPanel from './components/PlayerPanel';
import ProgressOverlay from './components/ProgressOverlay';
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
  
  const [showOverlay, setShowOverlay] = useState(false);
  
  useHealthCheck();
  useVoices();
  
  // Mostrar overlay quando job está sendo processado
  useEffect(() => {
    if (currentJobId && currentJob) {
      const isProcessing = !['DONE', 'FAILED', 'SCRIPT_DONE', 'PENDING'].includes(currentJob.status);
      setShowOverlay(isProcessing);
    } else if (!currentJobId) {
      setShowOverlay(false);
    }
  }, [currentJobId, currentJob?.status]);
  
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
    
    resetCurrentJob();
    setProgress(10, '📋 Iniciando geração...');
    setShowOverlay(true);
    
    try {
      let jobId;
      
      if (data.text && data.text.trim().length >= 100) {
        // Gerar título automaticamente a partir do texto
        const titlePreview = data.text.trim().substring(0, 50).replace(/\n/g, ' ');
        const autoTitle = titlePreview.length > 45 ? titlePreview + '...' : titlePreview;
        
        const params = new URLSearchParams({
          title: autoTitle || 'Novo Podcast',
          text: data.text,
          llm_mode: llmMode,
          voice_host: 'pm_alex',
          podcast_type: 'monologue',
          target_duration: '10',
        });
        
        setProgress(20, '📤 Enviando texto para IA...');
        const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);
        jobId = response.data.job_id;
      } else if (data.files && data.files.length > 0) {
        setProgress(20, '📁 Enviando arquivo...');
        const formData = new FormData();
        formData.append('file', data.files[0]);
        formData.append('title', data.files[0].name.replace(/\.[^.]+$/, ''));
        formData.append('llm_mode', llmMode);
        formData.append('voice_host', 'pm_alex');
        
        const response = await axios.post('http://localhost:8000/upload/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        jobId = response.data.job_id;
      }
      
      if (jobId) {
        setCurrentJobId(jobId);
        setActiveTab('roteiro');
        setProgress(30, '🤖 IA gerando roteiro...');
        
        await axios.post(`http://localhost:8000/jobs/${jobId}/generate-script`);
        
        const pollScript = async () => {
          try {
            const res = await axios.get(`http://localhost:8000/jobs/${jobId}`);
            setCurrentJob(res.data);
            
            const status = res.data.status;
            if (status === 'LLM_PROCESSING') {
              setProgress(50, '⏳ Finalizando roteiro...');
            } else if (status === 'SCRIPT_DONE') {
              setProgress(100, '✅ Roteiro gerado com sucesso!');
              setTimeout(() => {
                setShowOverlay(false);
                setActiveTab('roteiro');
              }, 1500);
              return;
            } else if (status === 'FAILED') {
              setProgress(100, '❌ Erro: ' + (res.data.error_message || 'Falha ao gerar'), true);
              setShowOverlay(true);
              return;
            } else if (status === 'DONE') {
              setProgress(100, '🎉 Podcast completo!');
              setTimeout(() => {
                setShowOverlay(false);
                setActiveTab('player');
              }, 1500);
              return;
            }
            
            setTimeout(pollScript, 2000);
          } catch (e) {
            console.error('Poll error:', e);
            setTimeout(pollScript, 3000);
          }
        };
        pollScript();
      }
    } catch (error) {
      console.error('[handleGenerateScript] Erro:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Erro desconhecido';
      setProgress(100, '❌ Erro: ' + errorMsg, true);
      setShowOverlay(true);
    }
  }, [setCurrentJob, setCurrentJobId, setActiveTab, setProgress, clearProgress, resetCurrentJob, llmMode]);
  
  // Gerar áudio a partir do roteiro existente
  const handleGenerateAudio = useCallback(async () => {
    if (!currentJobId || !currentJob) return;
    
    setProgress(10, '🎧 Iniciando síntese de áudio...');
    setShowOverlay(true);
    
    try {
      await axios.post(`http://localhost:8000/jobs/${currentJobId}/start-tts`);
      
      const pollAudio = async () => {
        try {
          const res = await axios.get(`http://localhost:8000/jobs/${currentJobId}`);
          setCurrentJob(res.data);
          
          const status = res.data.status;
          if (status === 'TTS_PROCESSING' || status === 'POST_PRODUCTION') {
            const prog = res.data.progress || 50;
            setProgress(prog, '🔊 Sintetizando áudio... ' + prog + '%');
          } else if (status === 'DONE') {
            setProgress(100, '✅ Áudio gerado com sucesso!');
            setTimeout(() => {
              setShowOverlay(false);
              setActiveTab('player');
            }, 1500);
            return;
          } else if (status === 'FAILED') {
            setProgress(100, '❌ Erro: ' + (res.data.error_message || 'Falha ao gerar áudio'), true);
            setShowOverlay(true);
            return;
          }
          
          setTimeout(pollAudio, 2000);
        } catch (e) {
          console.error('Poll error:', e);
          setTimeout(pollAudio, 3000);
        }
      };
      pollAudio();
    } catch (error) {
      console.error('[handleGenerateAudio] Erro:', error);
      setProgress(100, '❌ Erro: ' + error.message, true);
      setShowOverlay(true);
    }
  }, [currentJobId, currentJob, setCurrentJob, setActiveTab, setProgress]);
  
  // Gerar podcast completo (roteiro + áudio)
  const handleGeneratePodcast = useCallback(async (data) => {
    console.log('[handleGeneratePodcast] Recebido:', data);
    
    resetCurrentJob();
    setProgress(10, '📋 Iniciando geração...');
    setShowOverlay(true);
    
    try {
      let jobId;
      
      if (data.text && data.text.trim().length >= 100) {
        const titlePreview = data.text.trim().substring(0, 50).replace(/\n/g, ' ');
        const autoTitle = titlePreview.length > 45 ? titlePreview + '...' : titlePreview;
        
        const params = new URLSearchParams({
          title: autoTitle || 'Novo Podcast',
          text: data.text,
          llm_mode: llmMode,
          voice_host: 'pm_alex',
          podcast_type: 'monologue',
          target_duration: '10',
        });
        
        setProgress(20, '📤 Enviando texto...');
        const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);
        jobId = response.data.job_id;
      } else if (data.files && data.files.length > 0) {
        setProgress(20, '📁 Enviando arquivo...');
        const formData = new FormData();
        formData.append('file', data.files[0]);
        formData.append('title', data.files[0].name.replace(/\.[^.]+$/, ''));
        formData.append('llm_mode', llmMode);
        formData.append('voice_host', 'pm_alex');
        
        const response = await axios.post('http://localhost:8000/upload/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        jobId = response.data.job_id;
      }
      
      if (jobId) {
        setCurrentJobId(jobId);
        setProgress(30, '🤖 Gerando roteiro com IA...');
        
        await axios.post(`http://localhost:8000/jobs/${jobId}/start`);
        
        const pollJob = async () => {
          try {
            const res = await axios.get(`http://localhost:8000/jobs/${jobId}`);
            setCurrentJob(res.data);
            
            const status = res.data.status;
            const progressVal = res.data.progress || 0;
            
            if (status === 'LLM_PROCESSING') {
              setProgress(30 + Math.floor(progressVal * 0.3), '📝 Gerando roteiro... ' + (30 + Math.floor(progressVal * 0.3)) + '%');
            } else if (status === 'SCRIPT_DONE' || status === 'TTS_PROCESSING') {
              setProgress(60 + Math.floor(progressVal * 0.3), '🔊 Sintetizando áudio... ' + (60 + Math.floor(progressVal * 0.3)) + '%');
            } else if (status === 'DONE') {
              setProgress(100, '🎉 Podcast completo!');
              setTimeout(() => {
                setShowOverlay(false);
                setActiveTab('player');
              }, 1500);
              return;
            } else if (status === 'FAILED') {
              setProgress(100, '❌ Erro: ' + (res.data.error_message || 'Falha ao gerar'), true);
              setShowOverlay(true);
              return;
            }
            
            setTimeout(pollJob, 2000);
          } catch (e) {
            console.error('Poll error:', e);
            setTimeout(pollJob, 3000);
          }
        };
        pollJob();
      }
    } catch (error) {
      console.error('[handleGeneratePodcast] Erro:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Erro desconhecido';
      setProgress(100, '❌ Erro: ' + errorMsg, true);
      setShowOverlay(true);
    }
  }, [setCurrentJob, setCurrentJobId, setActiveTab, setProgress, clearProgress, resetCurrentJob, llmMode]);
  
  const handleCloseOverlay = useCallback(() => {
    setShowOverlay(false);
  }, []);
  
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
      
      <ProgressOverlay visible={showOverlay} onClose={handleCloseOverlay} />
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
