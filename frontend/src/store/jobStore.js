import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useJobStore = create(
  persist(
    (set, get) => ({
      // Job atual
      currentJobId: null,
      currentJob: null,
      
      // SSE
      sseConnected: false,
      sseError: null,
      
      // Serviços (health check)
      services: {
        kokoro: 'unknown',
        redis: 'unknown',
        groq: 'unknown',
        backend: 'up',
      },
      
      // Vozes disponíveis
      availableVoices: [],
      ptbrVoices: [],
      
      // Histórico
      jobHistory: [],
      
      // UI state
      activeTab: 'roteiro',
      historyOpen: false,
      inputTab: 'arquivos',
      
      // Actions
      setCurrentJob: (job) => set({ currentJob: job }),
      setCurrentJobId: (id) => set({ currentJobId: id }),
      
      setSSEConnected: (connected) => set({ sseConnected: connected }),
      setSSEError: (error) => set({ sseError: error }),
      
      setServices: (services) => set({ services }),
      updateService: (service, status) => set((state) => ({
        services: { ...state.services, [service]: status }
      })),
      
      setAvailableVoices: (voices) => {
        const ptbr = voices.filter(v => v.startsWith('pm_') || v.startsWith('pf_'));
        set({ availableVoices: voices, ptbrVoices: ptbr });
      },
      
      setJobHistory: (history) => set({ jobHistory: history }),
      addToHistory: (job) => set((state) => ({
        jobHistory: [job, ...state.jobHistory.filter(j => j.id !== job.id)]
      })),
      removeFromHistory: (jobId) => set((state) => ({
        jobHistory: state.jobHistory.filter(j => j.id !== jobId)
      })),
      
      setActiveTab: (tab) => set({ activeTab: tab }),
      setHistoryOpen: (open) => set({ historyOpen: open }),
      setInputTab: (tab) => set({ inputTab: tab }),
      
      reset: () => set({
        currentJobId: null,
        currentJob: null,
        sseConnected: false,
        sseError: null,
        activeTab: 'roteiro',
        historyOpen: false,
      }),
    }),
    {
      name: 'fabot-storage',
      partialize: (state) => ({ 
        currentJob: state.currentJob,
        currentJobId: state.currentJobId,
        jobHistory: state.jobHistory,
        activeTab: state.activeTab,
      }),
    }
  )
);

export default useJobStore;
