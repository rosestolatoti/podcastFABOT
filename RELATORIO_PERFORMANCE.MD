# FABOT Studio — Relatório de Performance e Qualidade
**Data:** 20/03/2026 — 20:41h  
**Modelo LLM:** Gemini 2.5 Flash (Recomendado)  
**Testado via:** Playwright MCP (navegador real)

---

## TEXTO DE ENTRADA

**Tema:** Inteligência Artificial e Machine Learning: Como as Máquinas Aprendem  
**Tamanho:** 2.683 caracteres · 413 palavras · ~3 min de leitura  
**Tipo:** Texto médio — artigo técnico-didático com exemplos práticos  
**Conteúdo coberto:** IA, ML supervisionado/não supervisionado/por reforço, redes neurais, deep learning, exemplos reais (Netflix, Gmail, Tesla, AlphaGo)

---

## FASE 1 — GERAÇÃO DO ROTEIRO (LLM)

### Cronometria
| Evento | Timestamp |
|--------|-----------|
| Clique em "Gerar Roteiro" | 20:41:47 |
| Roteiro exibido na tela | 20:43:06 |
| **Tempo total** | **79.1 segundos** |

### Detalhes do Processo
- Upload via `POST /upload/paste` → criação do job
- `POST /jobs/{id}/generate-script` → BackgroundTask
- LLM: Gemini 2.5 Flash via API Google AI
- Poll a cada 2s pelo frontend até status `SCRIPT_DONE`

### Resultado
- **102 segmentos** gerados na primeira versão do roteiro
- **91 segmentos** na versão salva para TTS (LLM reagenerou ao clicar em Gerar Áudio)
- Título gerado: *"IA e Machine Learning: Como Máquinas Aprendem para o Seu Negócio"*
- Estrutura: NARRADORA (abertura) → diálogo WILLIAM/CRISTINA → perguntas a "Fábio" → fechamento

---

## ANÁLISE DE QUALIDADE DO ROTEIRO — NOTA: 8.5/10

### Pontos Fortes

**Estrutura pedagógica clara (9/10)**  
O roteiro seguiu exatamente o padrão do sistema: problema → contexto empresarial → como antigamente → como não escala → solução conceitual → detalhe técnico → analogia → aplicação em código → pergunta para fixar → fechamento. Didatismo de alto nível.

**Personalização contextual (9/10)**  
O LLM incorporou corretamente os dados de configuração do usuário:
- Mencionou "Fábio" e "Fabricio" como personagens reais do ouvinte
- Usou empresas reais brasileiras como exemplos: Havan (Luciano Hang), BTG (Andre Esteves), ALFAPARF (Thiago Pizoti), ELY FOTOS (Patrick Toro), Nubank, Magazine Luiza
- Tom adequado ao perfil: empresário, linguagem de negócios, não puramente técnica

**Cobertura do conteúdo (9/10)**  
Cobriu todos os tópicos do texto: IA geral, ML, supervisionado, não supervisionado, por reforço, redes neurais, deep learning. Nenhum tópico importante foi omitido.

**Analogias (8/10)**  
Analogias criativas e memoráveis:
- ML = enxadrista aprendendo com partidas
- Supervisionado = ensinar criança a reconhecer frutas
- Não supervisionado = criança separando brinquedos sozinha
- Por reforço = cachorro aprendendo truques / jogo de videogame
- Deep learning = artista desenhando em camadas

**Fluidez do diálogo (8/10)**  
Troca entre William e Cristina natural, com perguntas que avançam organicamente. Não parece roteiro de chatbot.

### Pontos Negativos / Descontos

**Fórmula repetitiva (-0.5)**  
A tag de encerramento de cada bloco — *"Viu um sistema aprendendo com dados: é Machine Learning"* — é repetida literalmente em todos os 5 blocos temáticos. Funciona como âncora didática, mas torna o ritmo previsível e mecânico na segunda metade.

**Regeneração inconsistente (-0.5)**  
O LLM gerou 102 segmentos no primeiro roteiro e 91 na segunda geração (ao iniciar TTS). O conteúdo é diferente entre as duas versões — a segunda é mais densa e mais focada em exemplos de negócios. Isso indica que o sistema não persiste o roteiro aprovado entre as fases: ao clicar em "Gerar Áudio", ele regera o script em vez de usar o salvo. **Bug de fluxo.**

**Segmento de abertura longo (-0.5)**  
A fala da NARRADORA abre com lista longa de palavras-chave para repetição — válido pedagogicamente mas pesado para áudio: *"Repita: IA, ML, supervisionado, não supervisionado, por reforço, redes neurais e deep learning"*. Em texto funciona, em áudio soa mecânico.

### Resumo Roteiro
| Critério | Nota |
|----------|------|
| Estrutura pedagógica | 9.0 |
| Personalização | 9.0 |
| Cobertura do conteúdo | 9.0 |
| Qualidade das analogias | 8.0 |
| Fluidez do diálogo | 8.0 |
| Variedade de formato | 7.0 |
| **MÉDIA FINAL** | **8.5/10** |

---

## FASE 2 — GERAÇÃO DE ÁUDIO (TTS)

### Cronometria
| Evento | Timestamp |
|--------|-----------|
| Clique em "Gerar Áudio" | 20:43:09 |
| Status: Sintetizando (45%) | ~20:43:45 |
| Status: Completo (100%) | 20:44:50 |
| **Tempo total** | **100.9 segundos** |

### Throughput
- **91 segmentos** processados em paralelo (Semaphore 5)
- **1.1 segundos por segmento** em média (paralelo real)
- Sequencial estimado: ~182s → ganho real de **1.8x** com paralelismo

### Especificações Técnicas do Áudio
| Propriedade | Valor |
|-------------|-------|
| Duração | 18:07 (1.088 segundos) |
| Tamanho do arquivo | 25 MB |
| Bitrate | 192 kbps |
| Sample rate | 44.100 Hz |
| Canais | Estéreo (2) |
| Loudness médio | -23.6 dBFS |
| Pico máximo | -4.5 dBFS |
| Engine TTS | Microsoft Edge TTS (Azure Neural) |
| Vozes usadas | pt-BR-ThalitaMultilingualNeural (Narradora), pt-BR-AntonioNeural (William), pt-BR-FranciscaNeural (Cristina) |

---

## ANÁLISE DE QUALIDADE DO ÁUDIO — NOTA: 8.0/10

### Pontos Fortes

**Naturalidade das vozes (8/10)**  
As vozes neurais Azure (Thalita, Antonio, Francisca) são de alta qualidade — notavelmente acima de TTS sintético tradicional. Prosódia razoável, entonação de frase funcional, sem o robotismo das gerações anteriores de TTS.

**Diferenciação entre personagens (9/10)**  
Três vozes distintas e bem diferenciadas: Thalita (Narradora — feminina, cadenciada), Antonio (William — masculino, mais dinâmico), Francisca (Cristina — feminina, levemente diferente da narradora). O ouvinte identifica quem fala sem ambiguidade.

**Produção final (8/10)**  
Duração de 18 minutos para ~413 palavras de entrada é uma expansão excelente — o LLM gerou muito mais conteúdo. Sem ruídos, cliques ou artefatos audíveis. Fade-in de 30ms entre segmentos elimina cortes bruscos. Bitrate 192kbps/44.1kHz estéreo — qualidade de podcast profissional.

**Pausas e ritmo (7/10)**  
O sistema de pausas (300ms mesma voz, 550ms troca de voz, 1.8s após narradora) funciona bem na maioria das trocas. O ritmo global é razoável para um formato educativo.

### Pontos Negativos / Descontos

**Entonação artificial em listas (-1.0)**  
Na abertura da NARRADORA, a lista de palavras-chave — *"Repita: IA, ML, supervisionado, não supervisionado..."* — é lida de forma plana, sem a entonação de lista que um locutor humano daria. Soa mecânico neste trecho específico.

**Falta de ênfase semântica real (-0.5)**  
O sistema usa `<emphasis level="moderate">` via SSML nas palavras-chave, mas o Edge TTS aplica a ênfase de forma tênue — quase imperceptível na reprodução final. Palavras marcadas como importantes soam iguais às demais.

**Loudness ligeiramente baixo (-0.5)**  
-23.6 dBFS está abaixo do padrão broadcast de -16 LUFS (Spotify/Apple Podcasts). O podcast tocará mais baixo que conteúdo profissional nas plataformas. Seria resolvido com normalização pós-produção (o pipeline tem `LUFS_TARGET = -16.0` em config mas não está sendo aplicado).

**Micro-pausas inconsistentes (-0.5)**  
Em alguns trechos onde Cristina responde imediatamente após William com frases muito curtas (*"Perfeita."*, *"Isso mesmo."*), a pausa de 550ms soa longa demais. Em outros trechos mais longos, a mesma pausa é insuficiente.

**Ausência de trilha/efeitos (-0.5)**  
O áudio entrega apenas as vozes, sem intro musical, trilha de fundo ou efeitos de transição entre blocos. Para um podcast profissional seria esperado. É uma limitação de design do sistema, não um bug.

### Resumo Áudio
| Critério | Nota |
|----------|------|
| Naturalidade das vozes | 8.0 |
| Diferenciação de personagens | 9.0 |
| Qualidade técnica (bitrate/sample) | 9.0 |
| Ritmo e pausas | 7.0 |
| Ênfase e prosódia | 6.5 |
| Loudness/normalização | 7.0 |
| Produção geral | 8.0 |
| **MÉDIA FINAL** | **8.0/10** |

---

## RESUMO EXECUTIVO DE PERFORMANCE

```
┌─────────────────────────────────────────────────────┐
│         FABOT STUDIO — TESTE DE PERFORMANCE          │
│                   20/03/2026                         │
├─────────────────────────────────────────────────────┤
│  ENTRADA                                             │
│  Texto: 2.683 chars · 413 palavras · tema: IA/ML    │
│  LLM: Gemini 2.5 Flash                              │
├─────────────────────────────────────────────────────┤
│  FASE 1 — ROTEIRO (LLM)                             │
│  Tempo: 79.1 segundos                               │
│  Segmentos gerados: 91–102                          │
│  Qualidade: 8.5/10                                  │
├─────────────────────────────────────────────────────┤
│  FASE 2 — ÁUDIO (TTS Edge)                          │
│  Tempo: 100.9 segundos                              │
│  Duração do podcast: 18:07 min                      │
│  Tamanho: 25 MB · 192kbps · 44.1kHz estéreo        │
│  Loudness: -23.6 dBFS (pico -4.5 dBFS)             │
│  Qualidade: 8.0/10                                  │
├─────────────────────────────────────────────────────┤
│  TOTAL END-TO-END                                   │
│  Tempo: 180 segundos (3 minutos)                    │
│  Entrada: ~3min leitura → Saída: 18min podcast      │
│  Ratio de expansão: 6x                              │
│  Nota geral do sistema: 8.2/10                      │
└─────────────────────────────────────────────────────┘
```

---

## CONCLUSÃO

O FABOT Studio entregou um podcast de **18 minutos** a partir de texto de **3 minutos de leitura** em apenas **3 minutos de processamento** — ratio de **6x de expansão de conteúdo** com qualidade técnica sólida.

**O sistema funciona.** Para uso pessoal e educativo, os resultados são impressionantes. Os principais pontos a evoluir são: normalização de loudness para -16 LUFS (já configurada mas não aplicada), controle de ênfase SSML mais agressivo, e correção do bug de regeneração de roteiro no fluxo LLM → TTS.
