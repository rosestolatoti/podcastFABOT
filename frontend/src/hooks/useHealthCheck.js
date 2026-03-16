import { useEffect } from 'react';
import axios from 'axios';
import useJobStore from '../store/jobStore';

const API_URL = 'http://localhost:8000';

export function useHealthCheck() {
  const { setServices, updateService } = useJobStore();
  
  const checkHealth = async () => {
    try {
      const response = await axios.get(`${API_URL}/health/`, {
        timeout: 5000
      });
      
      const services = response.data.services || [];
      const newServices = {
        kokoro: 'unknown',
        redis: 'unknown',
        groq: 'unknown',
        backend: 'up',
      };
      
      services.forEach(s => {
        const name = s.service?.toLowerCase();
        if (name === 'kokoro') {
          newServices.kokoro = s.status === 'UP' ? 'up' : 'down';
        } else if (name === 'redis') {
          newServices.redis = s.status === 'UP' ? 'up' : 'down';
        } else if (name === 'ollama') {
          newServices.groq = s.status === 'UP' ? 'up' : 'down';
        }
      });
      
      setServices(newServices);
    } catch (error) {
      console.error('Health check failed:', error);
      setServices({
        kokoro: 'down',
        redis: 'down',
        groq: 'down',
        backend: 'down',
      });
    }
  };
  
  useEffect(() => {
    checkHealth();
    
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, []);
  
  return { checkHealth };
}

export default useHealthCheck;
