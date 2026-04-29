# Requirements Document

## Introduction

Redesign visual e de UX do painel de chat da Aura DAP (Digital Adoption Platform), extensão Chrome que injeta um assistente de IA flutuante sobre o ERP Senior X. O escopo cobre cinco problemas identificados no painel atual: fundo translúcido ilegível sobre fundos saturados, botões de feedback com emoji amarelo quebrando a identidade visual, mensagem de loading estática em vez do componente de dots animados já existente, ausência de histórico de conversa na sessão, e auto-hide que fecha o painel enquanto o usuário ainda lê. A solução deve ser contida exclusivamente nos arquivos da extensão (`extension/`), sem novas dependências externas, sem backend e preservando a API pública `window.AuraUI` e todos os modos existentes (assist, gps, train, prove).

---

## Glossary

- **Chat_Panel**: o elemento `#aura-speech-bubble` — painel principal de interação com a Aura.
- **Chat_Stack**: o elemento `#aura-chat-stack` — área de balões sequenciais proativos.
- **Thread_Area**: área scrollável dentro do Chat_Panel que exibe o histórico de mensagens da sessão.
- **Message_Bubble**: elemento visual individual dentro da Thread_Area representando uma mensagem (da Aura ou do usuário).
- **Typing_Indicator**: componente `.aura-typing-dots` com três pontos animados, exibido como Message_Bubble da Aura durante carregamento.
- **Feedback_Bar**: barra com botões like/dislike exibida após respostas da IA.
- **Historico**: array em memória RAM (`_historico[]`) no escopo do módulo `aura_ui.js`, sem persistência em `localStorage` ou `sessionStorage`.
- **Auto_Hide**: timer de 12 segundos que fecha o Chat_Panel automaticamente quando o usuário não interage.
- **Engagement_Lock**: flag `_bubbleEngajada` que impede o Auto_Hide enquanto o usuário interage com o Chat_Panel.
- **AuraUI**: namespace público `window.AuraUI` exposto por `aura_ui.js`.
- **AuraFeedback**: namespace público `window.AuraFeedback` exposto por `aura_feedback.js`.
- **AuraAssistEngine**: namespace público `window.AuraAssistEngine` exposto por `aura_assist_engine.js`.
- **Backdrop_Filter**: propriedade CSS `backdrop-filter: blur()` usada como efeito decorativo no fundo do Chat_Panel.
- **Solid_Fallback**: regra CSS `@supports not (backdrop-filter: blur(1px))` que garante fundo sólido em browsers sem suporte a `backdrop-filter`.

---

## Requirements

### Requirement 1: Fundo do Chat_Panel com alta opacidade

**User Story:** Como usuário do ERP Senior X, quero que o painel da Aura seja legível sobre qualquer fundo da aplicação, incluindo fundos roxos e saturados, para que eu consiga ler as respostas sem esforço visual.

#### Acceptance Criteria

1. THE Chat_Panel SHALL usar `background: rgba(255, 255, 255, 0.92)` como valor base de opacidade do fundo.
2. THE Chat_Panel SHALL aplicar `backdrop-filter: blur(16px)` como efeito decorativo adicional ao fundo.
3. WHERE o browser não suporta `backdrop-filter`, THE Chat_Panel SHALL usar `background: #ffffff` como Solid_Fallback via regra `@supports not (backdrop-filter: blur(1px))`.
4. WHEN o Chat_Panel é exibido sobre qualquer cor de fundo do Senior X, THE Chat_Panel SHALL manter contraste mínimo de 4.5:1 entre o texto `#1e293b` e o fundo do painel, conforme WCAG 2.1 AA.
5. THE Chat_Stack SHALL aplicar o mesmo padrão de opacidade alta (`rgba(255, 255, 255, 0.92)`) e Solid_Fallback nos elementos `.aura-chat-bubble`.

---

### Requirement 2: Botões de feedback com SVG estilizado

**User Story:** Como usuário da Aura, quero que os botões de like e dislike sigam a identidade visual verde do sistema, para que a interface pareça coesa e profissional.

#### Acceptance Criteria

1. THE AuraFeedback SHALL substituir o `textContent` de emoji (`👍`, `👎`) por elementos SVG inline nos botões like e dislike.
2. THE AuraFeedback SHALL aplicar `color: #94a3b8` como cor padrão (repouso) nos ícones SVG dos botões.
3. WHEN o usuário passa o cursor sobre o botão like, THE AuraFeedback SHALL aplicar `color: #00ddb3` ao ícone SVG do botão like.
4. WHEN o usuário passa o cursor sobre o botão dislike, THE AuraFeedback SHALL aplicar `color: #ef4444` ao ícone SVG do botão dislike.
5. THE AuraFeedback SHALL preservar o comportamento de registro em `localStorage` e o fade-out após votação, sem alterações na lógica de negócio existente.
6. THE Chat_Panel SHALL aplicar os estilos dos botões de feedback via classes CSS em `extension/style.css`, sem estilos inline no JavaScript.

---

### Requirement 3: Typing Indicator durante carregamento

**User Story:** Como usuário da Aura, quero ver uma animação de digitação enquanto a IA processa minha pergunta, para ter feedback visual claro de que o sistema está trabalhando.

#### Acceptance Criteria

1. WHEN `AuraAssistEngine.dispararAnalise()` é chamado, THE AuraUI SHALL exibir o Typing_Indicator como Message_Bubble da Aura na Thread_Area, em vez do texto estático `'Já estou analisando... Só um momento! 🔍'`.
2. THE Typing_Indicator SHALL usar o componente `.aura-typing-dots` já definido em `extension/style.css`, com três elementos `<span>` animados.
3. WHEN a resposta da IA é recebida via `AURA_RESPONSE`, THE AuraUI SHALL remover o Typing_Indicator e exibir a Message_Bubble com o texto da resposta.
4. IF a resposta da IA não chegar em 30 segundos após o disparo, THE AuraUI SHALL remover o Typing_Indicator e exibir a mensagem `'Não consegui processar a resposta. Tente novamente.'`.
5. THE Typing_Indicator SHALL ser acessível com `aria-label="Aura está digitando"` no elemento contêiner.

---

### Requirement 4: Histórico de conversa na sessão

**User Story:** Como usuário da Aura, quero ver o histórico das mensagens trocadas durante a sessão atual, para manter o contexto da conversa sem precisar lembrar o que foi dito anteriormente.

#### Acceptance Criteria

1. THE AuraUI SHALL manter um array `_historico` em memória no escopo do módulo, armazenando cada mensagem com os campos `{ role: 'aura' | 'user', texto: string, timestamp: number }`.
2. WHEN o usuário envia uma pergunta via `dispararAnalise()`, THE AuraUI SHALL adicionar a mensagem do usuário ao `_historico` antes de exibir o Typing_Indicator.
3. WHEN a resposta da IA é recebida, THE AuraUI SHALL adicionar a mensagem da Aura ao `_historico` e renderizá-la na Thread_Area.
4. THE Thread_Area SHALL exibir todas as mensagens do `_historico` como Message_Bubbles, com mensagens da Aura alinhadas à esquerda (fundo `rgba(0, 221, 179, 0.10)`) e mensagens do usuário alinhadas à direita (fundo `#00ddb3`, texto branco).
5. THE Thread_Area SHALL ter `max-height: 260px` e `overflow-y: auto`, com scroll automático para a mensagem mais recente após cada nova mensagem.
6. WHEN o usuário fecha a aba do browser ou recarrega a página, THE AuraUI SHALL descartar o `_historico` sem persistir em `localStorage` ou `sessionStorage`.
7. WHEN `AuraUI.esconderBalao()` é chamado, THE AuraUI SHALL preservar o `_historico` em memória para que o histórico seja exibido ao reabrir o Chat_Panel na mesma sessão.
8. THE AuraUI SHALL preservar a assinatura pública de `exibirBalao(texto, opcoes, mostrarFeedback)` sem alterações, para compatibilidade com os módulos dependentes.

---

### Requirement 5: Auto-hide pausado durante leitura

**User Story:** Como usuário da Aura, quero que o painel não feche automaticamente enquanto estou lendo ou rolando o conteúdo, para que eu possa ler respostas longas sem interrupção.

#### Acceptance Criteria

1. WHEN o usuário realiza scroll na Thread_Area, THE AuraUI SHALL ativar o Engagement_Lock (`_bubbleEngajada = true`) e cancelar o timer do Auto_Hide.
2. WHILE o Engagement_Lock está ativo, THE AuraUI SHALL não fechar o Chat_Panel pelo Auto_Hide.
3. WHEN o usuário para de interagir com o Chat_Panel por mais de 12 segundos após o último evento de scroll, mouseenter ou focus no input, THE AuraUI SHALL reiniciar o timer do Auto_Hide.
4. THE AuraUI SHALL registrar o listener de scroll na Thread_Area durante `init()`, sem duplicar registros em chamadas subsequentes a `exibirBalao()`.
5. IF o Chat_Panel está exibindo o Typing_Indicator, THE AuraUI SHALL manter o Engagement_Lock ativo e não fechar o painel pelo Auto_Hide.

---

### Requirement 6: Preservação da API pública e dos modos existentes

**User Story:** Como desenvolvedor dos módulos da Aura, quero que o redesign não quebre nenhuma chamada existente à API pública `window.AuraUI`, para que os modos assist, gps, train e prove continuem funcionando sem alterações.

#### Acceptance Criteria

1. THE AuraUI SHALL preservar todos os métodos públicos existentes: `init`, `exibirBalao`, `exibirBaloesSequenciais`, `esconderBalao`, `ativarBadge`, `desativarBadge`, `tocarAnimacao`, `setLastPrompt`, `wasPlayerDragged`, `resetDragFlag`.
2. THE AuraUI SHALL preservar as assinaturas de parâmetros de todos os métodos públicos sem alterações de tipo ou ordem.
3. WHEN `AuraState.setMode()` alterna entre os modos assist, gps, train e prove, THE AuraUI SHALL continuar respondendo corretamente às chamadas de `exibirBalao` e `exibirBaloesSequenciais` de cada modo.
4. THE Chat_Panel SHALL não introduzir novos arquivos JavaScript externos ou dependências de bibliotecas além das já presentes na extensão.
5. THE Chat_Panel SHALL não modificar arquivos fora do diretório `extension/`.
