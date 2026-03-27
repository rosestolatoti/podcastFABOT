const params = new URLSearchParams({
  title: autoTitle || 'Novo Podcast',
  text: data.text,
  llm_mode: llmMode,
  voice_host: 'pm_alex',
  podcast_type: 'monologue',
  target_duration: '10',
});

// ═══ MARCA-TEXTO: Enviar tópicos selecionados pelo usuário ═══
if (data.topics && data.topics.length > 0) {
  params.append('topics', JSON.stringify(data.topics));
}

const response = await axios.post(`http://localhost:8000/upload/paste?${params.toString()}`);