import { useEffect } from 'react';
import useJobStore from '../store/jobStore';

const FALLBACK_VOICES = [
  'pm_alex',
  'pf_dora',
  'af_sarah',
  'af_bella',
  'am_michael',
];

export function useVoices() {
  const { setAvailableVoices } = useJobStore();
  
  const loadVoices = async () => {
    // Usar lista estática de vozes conhecidas
    setAvailableVoices(FALLBACK_VOICES);
  };
  
  useEffect(() => {
    loadVoices();
  }, []);
  
  return { loadVoices };
}

export default useVoices;
