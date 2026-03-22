import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useJobStore = create(
  persist(
    (set, get) => ({
      currentJobId: null,
      currentJob: null,
      
      sseConnected: false,
      sseError: null,
      
      services: {
        kokoro: 'unknown',
        redis: 'unknown',
        groq: 'unknown',
        backend: 'up',
      },
      
      availableVoices: [],
      ptbrVoices: [],
      
      jobHistory: [],
      
      activeTab: 'roteiro',
      historyOpen: false,
      inputTab: 'arquivos',
      llmMode: 'gemini-2.5-flash',
      
      progress: 0,
      progressMessage: '',
      progressError: false,
      
      activeJobs: [],
      
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
      setLlmMode: (mode) => set({ llmMode: mode }),
      
      setProgress: (progress, message = '', error = false) => set({ 
        progress, 
        progressMessage: message,
        progressError: error 
      }),
      clearProgress: () => set({ 
        progress: 0, 
        progressMessage: '',
        progressError: false 
      }),
      
      addActiveJob: (job) => set((state) => ({
        activeJobs: [...state.activeJobs.filter(j => j.id !== job.id), job]
      })),
      
      updateActiveJob: (jobId, updates) => set((state) => ({
        activeJobs: state.activeJobs.map(j => 
          j.id === jobId ? { ...j, ...updates } : j
        )
      })),
      
      removeActiveJob: (jobId) => set((state) => ({
        activeJobs: state.activeJobs.filter(j => j.id !== jobId)
      })),
      
      reset: () => set({
        currentJobId: null,
        currentJob: null,
        sseConnected: false,
        sseError: null,
        activeTab: 'roteiro',
        historyOpen: false,
      }),
      
      resetCurrentJob: () => set({
        currentJobId: null,
        currentJob: null,
        progress: 0,
        progressMessage: '',
        progressError: false,
      }),
    }),
    {
      name: 'fabot-storage',
      partialize: (state) => ({ 
        currentJobId: state.currentJobId,
        jobHistory: state.jobHistory,
        activeTab: state.activeTab,
      }),
    }
  )
);

export default useJobStore;
