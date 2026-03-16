import { useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';

const API_URL = 'http://localhost:8000';
const MAX_RETRIES = 5;

export function useJobStream(jobId) {
  const eventSourceRef = useRef(null);
  const retriesRef = useRef(0);
  
  const { 
    setCurrentJob, 
    setSSEConnected, 
    setSSEError, 
    setActiveTab,
    addToHistory
  } = useJobStore();
  
  const connect = useCallback(() => {
    if (!jobId) return;
    
    setSSEConnected(true);
    setSSEError(null);
    
    const eventSource = new EventSource(`${API_URL}/jobs/${jobId}/stream`);
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Atualizar job
        setCurrentJob(data);
        
        // Adicionar ao histórico
        if (data.status === 'DONE' || data.status === 'FAILED') {
          addToHistory(data);
        }
        
        // Mudar aba automaticamente
        switch (data.status) {
          case 'LLM_PROCESSING':
          case 'TTS_PROCESSING':
          case 'POST_PRODUCTION':
            setActiveTab('progresso');
            break;
          case 'SCRIPT_DONE':
            setActiveTab('roteiro');
            break;
          case 'DONE':
            setActiveTab('player');
            break;
          case 'FAILED':
            setActiveTab('progresso');
            break;
          default:
            break;
        }
        
        retriesRef.current = 0;
      } catch (error) {
        console.error('Erro ao processar mensagem SSE:', error);
      }
    };
    
    eventSource.onerror = (error) => {
      console.error('SSE error:', error);
      setSSEConnected(false);
      
      // Retry logic
      if (retriesRef.current < MAX_RETRIES) {
        const delay = Math.pow(2, retriesRef.current) * 1000;
        retriesRef.current++;
        console.log(`Reconectando em ${delay}ms (tentativa ${retriesRef.current})`);
        
        setTimeout(() => {
          eventSource.close();
          connect();
        }, delay);
      } else {
        setSSEError('Conexão perdida após várias tentativas');
      }
    };
    
    eventSource.onopen = () => {
      console.log('SSE conectado');
      setSSEConnected(true);
      retriesRef.current = 0;
    };
    
  }, [jobId, setCurrentJob, setSSEConnected, setSSEError, setActiveTab, addToHistory]);
  
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setSSEConnected(false);
  }, [setSSEConnected]);
  
  useEffect(() => {
    if (jobId) {
      connect();
    }
    
    return () => disconnect();
  }, [jobId, connect, disconnect]);
  
  return { connect, disconnect };
}

export default useJobStream;
