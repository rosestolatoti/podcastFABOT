import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const urls = {
  jobs: {
    get: (id) => `${API_BASE}/jobs/${id}`,
    history: `${API_BASE}/jobs/history`,
    start: (id) => `${API_BASE}/jobs/${id}/start`,
    generateScript: (id) => `${API_BASE}/jobs/${id}/generate-script`,
    generatePodcast: (id) => `${API_BASE}/jobs/${id}/generate-podcast`,
    startTTS: (id) => `${API_BASE}/jobs/${id}/start-tts`,
    cancel: (id) => `${API_BASE}/jobs/${id}/cancel`,
    stream: (id) => `${API_BASE}/jobs/${id}/stream`,
    upload: `${API_BASE}/upload/`,
    uploadPaste: `${API_BASE}/upload/paste`,
    // Multi-episódio
    generateMulti: (id) => `${API_BASE}/jobs/${id}/generate-multi`,
    episodes: (id) => `${API_BASE}/jobs/${id}/episodes`,
    startTTSAll: (id) => `${API_BASE}/jobs/${id}/start-tts-all`,
  },
  audio: (folder) => `${API_BASE}/audio/${folder}/final.mp3`,
  download: (id) => `${API_BASE}/download/${id}`,
  config: {
    get: `${API_BASE}/config/`,
    save: `${API_BASE}/config/save`,
  },
  health: `${API_BASE}/health/`,
};

export default api;
