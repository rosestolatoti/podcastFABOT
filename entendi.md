# RELATÓRIO DE ANÁLISE — divisao.md

## 1. O QUE ENTENDI

### 1.1 Resumo das 4 Mudanças

| # | Mudança | Arquivos | Impacto |
|---|---------|----------|---------|
| **1** | Toast de progresso profissional (drag + minimize + checklist) | ProgressOverlay.jsx, ProgressOverlay.css, App.jsx | Frontend |
| **2** | Botão "Gerar Áudio MP3" no ScriptPanel | ScriptPanel.jsx, ScriptPanel.css | Frontend |
| **3** | Card expande sem scroll interno | ScriptPanel.css | Frontend |
| **4** | Steps granulares no backend | podcast_worker.py | Backend |

---

## 2. ANÁLISE DE CADA MUDANÇA

### MUDANÇA 1: Toast de Progresso

**O que pede:**
- Substituir overlay full-screen por toast flutuante (bottom-right)
- Lista cada passo com ✅/⏳
- Minimizável (─/□)
- Arrastável (drag)
- NÃO bloqueia interface

**O que já existe no código atual:**
- ProgressOverlay.jsx JÁ tem: `position`, `dragging`, `dragOffset` (linhas 10-12)
- JÁ tem: `handleMouseDown`, `handleMouseMove`, `handleMouseUp` (linhas 74-100)
- JÁ tem: `.progress-toast` com `cursor: grab` no CSS
- JÁ tem: `.minimized` state

**QUESTÃO 1:** O código atual já tem drag/minimize implementados. O que EXATAMENTE está faltando?

### MUDANÇA 2: Botão Gerar Áudio

**O que pede:**
- Botão com gradiente `linear-gradient(135deg, #667eea 0%, #764ba2 100%)`
- Visível quando `status === 'SCRIPT_DONE'` e `!hasAudio`
- Chama `onGenerateAudio`

**QUESTÃO 2:** O ScriptPanel.jsx atual já tem esse botão? Se sim, onde está posicionado?

### MUDANÇA 3: Card Expande Sem Scroll

**O que pede:**
```css
.episode-card.expanded .episode-segments {
  max-height: none !important;
  overflow: visible !important;
}
```

**O que já existe no código:**
- Linha 863-866 do ScriptPanel.css já tem:
```css
.episode-card.expanded .episode-content {
  max-height: none;
  overflow-y: visible;
}
```

**QUESTÃO 3:** O seletor `.episode-segments` é diferente de `.episode-content`? Qual é o correto?

### MUDANÇA 4: Backend Granular Steps

**O que pede:**
- Em `generate_script_only()`: steps de 5% a 40%
- Em `start_tts_job()`: steps de 45% a 100%
- Cada step com emoji e `db.commit()`

**O que já existe no código atual (podcast_worker.py):**

Linhas 440-532 de `start_tts_job()` já tem:
- 42%: "Preparando síntese..."
- 85%: "Concatenando..."
- 90%: "Calculando duração..."
- 95%: "Salvando MP3..."
- 100%: "Podcast concluído!"

---

## 3. ESTADO ATUAL DO CÓDIGO

Verificando arquivos antes de planejar:

| Arquivo | Status | Observação |
|---------|--------|------------|
| `ProgressOverlay.jsx` | ⚠️ Verificar | JÁ tem drag handlers? |
| `ProgressOverlay.css` | ⚠️ Verificar | JÁ tem toast styles? |
| `ScriptPanel.jsx` | ⚠️ Verificar | JÁ tem botão áudio? |
| `ScriptPanel.css` | ⚠️ Verificar | JÁ tem expand CSS? |
| `podcast_worker.py` | ⚠️ Verificar | JÁ tem steps granulares? |

---

## 4. PLANO DE EXECUÇÃO (QUANDO APROVADO)

### Ordem sugerida:

**FASE 1 — Backend (MUDANÇA 4)**
1. Verificar se `generate_script_only()` já tem steps 5%-40%
2. Verificar se `start_tts_job()` já tem steps 45%-100%
3. Se faltando, adicionar os `db.commit()` nos pontos estratégicos

**FASE 2 — Frontend (MUDANÇA 1)**
1. Verificar ProgressOverlay.jsx atual vs código do divisao.md
2. Se JÁ tem drag/minimize → marcar como ✅
3. Se não → substituir/complementar

**FASE 3 — Frontend (MUDANÇA 2)**
1. Verificar ScriptPanel.jsx para botão "Gerar Áudio"
2. Adicionar se não existir
3. Adicionar CSS de gradiente

**FASE 4 — Frontend (MUDANÇA 3)**
1. Verificar CSS do card expandido
2. Corrigir seletor se necessário

**FASE 5 — Testes**
1. Criar job de teste
2. Verificar toast aparece e arrasta
3. Verificar steps aparecem no toast
4. Verificar botão áudio aparece
5. Verificar card expande completo

---

## 5. DÚVIDAS A CLARIFICAR

### DÚVIDA 1: O código atual já está parcialmente implementado?

O divisao.md menciona:
- "O botão 'Gerar Áudio MP3' não existe no ScriptPanel.jsx atual"
- "O ProgressOverlay.jsx é um overlay full-screen que bloqueia"

**MAS** nas minhas verificações anteriores vi:
- ProgressOverlay.jsx JÁ tem `position`, `dragging`, `dragOffset`
- ScriptPanel.jsx aparentemente JÁ tem botão de áudio

**Isso significa que o código JÁ FOI MODIFICADO antes ou o Diagnóstico do divisao.md está desatualizado?**

### DÚVIDA 2: Qual o seletor correto para MUDANÇA 3?

O divisao.md diz:
```css
.episode-card.expanded .episode-segments { ... }
```

Mas o código atual tem:
```css
.episode-card.expanded .episode-content { ... }
```

Qual é o correto? Preciso verificar a estrutura HTML do ScriptPanel.

### DÚVIDA 3: App.jsx precisa ser modificado?

O divisao.md pede adicionar:
```jsx
<ProgressOverlay
  visible={showProgress || (currentJob && ['READING', 'LLM_PROCESSING', ...])}
  onClose={() => setShowProgress(false)}
/>
```

Mas se já existe um ProgressOverlay no App.jsx, isso seria duplicação?

### DÚVIDA 4: Worker está dando erro de import

Nas últimas execuções vi:
```
cannot import name 'create_content_plan' from 'backend.services.content_'
```

Isso indica que o `simple_content_planner.py` não está sendo encontrado corretamente pelo worker. Preciso resolver isso ANTES de testar as mudanças.

---

## 6. POSSÍVEIS PROBLEMAS NO PLANO

### PROBLEMA 1: Conflito de imports
Se o código atual já tem implementação parcial e o divisao.md pede substituição TOTAL, pode haver conflito.

### PROBLEMA 2: CSS existente vs novo
O CSS atual pode ter estilos conflitantes com os novos. Preciso verificar se `!important` é necessário.

### PROBLEMA 3: Worker quebrado
O import error precisa ser resolvido antes de qualquer teste. Pode ser problema de:
- Caminho do módulo
- Arquivo não existe
- Erro de digitação

### PROBLEMA 4: API do LLM com quota esgotada
Vi no log: "429 RESOURCE_EXHAUSTED" para Gemini. Pode impedir testes.

---

## 7. MINHAS SUGESTÕES

### SUGESTÃO 1: Verificação antes de implementação
Antes de mexer no código, fazer uma "auditoria" comparando:
- Código atual vs código do divisao.md
- Marcar o que JÁ existe vs o que FALTA

### SUGESTÃO 2: Corrigir worker primeiro
O import error é crítico - sem worker funcionando, não dá para testar nada.

### SUGESTÃO 3: Teste incremental
Após cada mudança, rodar um job de teste para verificar que não quebrou.

### SUGESTÃO 4: Backup antes de substituir arquivos
O divisao.md pede "Substituir TUDO" para ProgressOverlay.jsx e ProgressOverlay.css. Fazer backup antes.

---

## 8. PRÓXIMOS PASSOS (aguardo aprovação)

1. **Verificar estado real** de cada arquivo mencionado
2. **Confirmar** o que já existe vs o que falta
3. **Decidir** se substituímos ou complementamos
4. **Corrigir** o import error do worker
5. **Implementar** mudanças uma a uma
6. **Testar** após cada uma

---

## 9. PEDIDO DE APROVAÇÃO

Antes de executar, preciso que você confirme:

1. **Está correto** o resumo das 4 mudanças?
2. **Pode prosseguir** com a auditoria dos arquivos?
3. **Quer que eu substitua** os arquivos completamente (como pede o divisao.md) ou **complemente** o que já existe?
4. **A ordem de execução** (Backend → Frontend → Testes) está OK?

Aguardo seu OK para prosseguir com a auditoria e implementação.
