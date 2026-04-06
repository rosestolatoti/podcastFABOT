import React, { useEffect, useCallback, useState } from 'react';
import axios from 'axios';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import useJobStore from './store/jobStore';
import useHealthCheck from './hooks/useHealthCheck';
import useVoices from './hooks/useVoices';
import Header from './components/Header';
import ConfigPanel from './components/ConfigPanel';
import InputPanel from './components/InputPanel';
import ScriptPanel from './components/ScriptPanel';
import PlayerPanel from './components/PlayerPanel';
import ActiveJobsBar from './components/ActiveJobsBar';
import ProgressOverlay from './components/ProgressOverlay';
import './styles/tokens.css';
import './App.css';

const queryClient = new QueryClient();

const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark');
} else {
  document.documentElement.setAttribute('data-theme', 'light');
  localStorage.setItem('theme', 'light');
}

function AppContent() {
  const { 
    currentJob,
    currentJobId,
    setCurrentJob,
    setCurrentJobId,
    setJobHistory,
    activeTab,
    setActiveTab,
    llmMode,
    addActiveJob,
    updateActiveJob,
    removeActiveJob
  } = useJobStore();
  
  const [showConfig, setShowConfig] = useState(false);
  const [showProgress, setShowProgress] = useState(false);
  
  useHealthCheck();
  useVoices();
  
  useEffect(() => {
    const loadCurrentJob = async () => {
      if (!currentJobId) return;
      
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
        if (error.response?.status === 404) {
          console.warn('[loadCurrentJob] Job não existe mais, limpando estado...');
          setCurrentJobId(null);
          setCurrentJob(null);
        }
      }
    };
    loadCurrentJob();
  }, [currentJobId, setCurrentJob, setCurrentJobId, setActiveTab]);
  
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
  
  const MAX_POLL_TIME = 10 * 60 * 1000;

  const handleGenerateScript = useCallback(async (data) => {
    console.log('[handleGenerateScript] Recebido:', data);
    
    let jobId = null;
    const pollStartTime = Date.now();
    
    try {
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
        
        if (data.topics && data.topics.length > 0) {
          params.append('topics', JSON.stringify(data.topics));
        }
        
        const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);
        jobId = response.data.job_id;
      } else if (data.files && data.files.length > 0) {
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
        const jobData = {
          id: jobId,
          title: data.text?.trim().substring(0, 50) || 'Novo Podcast',
          status: 'PENDING',
          progress: 10,
          current_step: 'Iniciando...'
        };
        addActiveJob(jobData);
        setCurrentJobId(jobId);
        setCurrentJob(jobData);
        setShowProgress(true);
        setActiveTab('roteiro');
        
        await axios.post(`http://localhost:8000/jobs/${jobId}/generate-script`);
        
        const pollScript = async () => {
          try {
            if (Date.now() - pollStartTime > MAX_POLL_TIME) {
              updateActiveJob(jobId, { 
                status: 'FAILED', 
                current_step: 'Tempo limite excedido (10 min). Verifique o Worker e tente novamente.' 
              });
              return;
            }
            
            const res = await axios.get(`http://localhost:8000/jobs/${jobId}`);
            updateActiveJob(jobId, {
              status: res.data.status,
              progress: res.data.progress || 50,
              current_step: res.data.current_step || 'Processando...',
              script_json: res.data.script_json
            });
            setCurrentJob(res.data);
            
            const status = res.data.status;
            if (status === 'SCRIPT_DONE') {
              updateActiveJob(jobId, { progress: 100, current_step: 'Roteiro pronto!' });
            } else if (status === 'FAILED') {
              updateActiveJob(jobId, { current_step: 'Erro: ' + (res.data.error_message || 'Falha') });
            } else if (status !== 'DONE' && !['SCRIPT_DONE', 'FAILED', 'CANCELLED'].includes(status)) {
              setTimeout(pollScript, 2000);
            }
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
      if (jobId) {
        updateActiveJob(jobId, { status: 'FAILED', current_step: errorMsg });
      }
    } finally {
      if (!jobId) {
        console.warn('[handleGenerateScript] Job não foi criado, limpando estado...');
      }
    }
  }, [setCurrentJob, setCurrentJobId, setActiveTab, addActiveJob, updateActiveJob, llmMode]);
  
  const handleGenerateAudio = useCallback(async () => {
    if (!currentJobId || !currentJob) return;
    
    const pollStartTime = Date.now();
    const jobData = {
      id: currentJobId,
      title: currentJob.title || 'Novo Podcast',
      status: 'TTS_PROCESSING',
      progress: 10,
      current_step: 'Iniciando síntese...'
    };
    addActiveJob(jobData);
    
    try {
      await axios.post(`http://localhost:8000/jobs/${currentJobId}/start-tts`);
      
      const pollAudio = async () => {
        try {
          if (Date.now() - pollStartTime > MAX_POLL_TIME) {
            updateActiveJob(currentJobId, { 
              status: 'FAILED', 
              current_step: 'Tempo limite excedido (10 min). Verifique o Worker e tente novamente.' 
            });
            return;
          }
          
          const res = await axios.get(`http://localhost:8000/jobs/${currentJobId}`);
          updateActiveJob(currentJobId, {
            status: res.data.status,
            progress: res.data.progress || 50,
            current_step: res.data.current_step || 'Sintetizando...'
          });
          setCurrentJob(res.data);
          
          const status = res.data.status;
          if (status === 'DONE') {
            updateActiveJob(currentJobId, { progress: 100, current_step: 'Áudio pronto!' });
            setActiveTab('player');
          } else if (status === 'FAILED') {
            updateActiveJob(currentJobId, { current_step: 'Erro: ' + (res.data.error_message || 'Falha') });
          } else if (!['DONE', 'FAILED', 'CANCELLED'].includes(status)) {
            setTimeout(pollAudio, 2000);
          }
        } catch (e) {
          console.error('Poll error:', e);
          setTimeout(pollAudio, 3000);
        }
      };
      pollAudio();
    } catch (error) {
      console.error('[handleGenerateAudio] Erro:', error);
      updateActiveJob(currentJobId, { status: 'FAILED', current_step: error.message });
    }
  }, [currentJobId, currentJob, setCurrentJob, addActiveJob, updateActiveJob, setActiveTab]);
  
  return (
    <div className="app">
      <Header onConfigClick={() => setShowConfig(true)} />
      
      <div className="main-layout three-columns">
        <div className="column column-input">
          <InputPanel 
            onGenerateScript={handleGenerateScript}
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
      
      <ActiveJobsBar />
      
      {showConfig && <ConfigPanel onClose={() => setShowConfig(false)} />}
      
      <ProgressOverlay 
        visible={showProgress || (currentJob && ['READING', 'LLM_PROCESSING', 'TTS_PROCESSING', 'PLANNING'].includes(currentJob.status))}
        onClose={() => setShowProgress(false)}
      />
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
