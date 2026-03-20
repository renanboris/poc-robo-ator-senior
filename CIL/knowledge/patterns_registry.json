[
  {
    "name": "menu_navigation",
    "version": 1,
    "description": "Navegação em menu lateral (sidebar). Cobre ícones de módulos, submenus expandíveis e itens de navegação de primeiro e segundo nível. Padrão dominante em ERPs Angular Material como o Senior X.",
    "signals": {
      "dom": ["nav", "aside", "mat-nav-list", "mat-list-item", "[role='menuitem']", "[role='navigation']"],
      "visual": ["sidebar esquerda", "ícone de módulo", "texto de menu", "item lateral"],
      "url_change": true,
      "x_pct_max": 0.35
    },
    "preconditions": [
      "sidebar visível na tela",
      "scroll da sidebar resetado para o topo antes do screenshot",
      "hover na borda esquerda da sidebar (x_hover fixo, não coords do capture) para expandir labels"
    ],
    "strategy_steps": [
      {
        "step": 1,
        "name": "brain_db",
        "desc": "Consulta Brain DB por seletor ou coords validados anteriormente",
        "timeout_ms": 1500,
        "skip_if": "validacao_ok=0 na entrada"
      },
      {
        "step": 2,
        "name": "css_direto",
        "desc": "Tenta seletor_css do roteiro (getUniqueSelector capturou id ou aria-label)",
        "timeout_ms": 800
      },
      {
        "step": 3,
        "name": "reset_scroll",
        "desc": "Reseta scrollTop da sidebar para 0 — estado anterior pode ter deixado no fundo"
      },
      {
        "step": 4,
        "name": "hover_sidebar_edge",
        "desc": "Move mouse para x=faixa.x_hover (borda da sidebar, ~40px), y limitado à faixa útil",
        "wait_ms": 1200,
        "nota": "NÃO usar coords do capture — podem ser de submenu já expandido"
      },
      {
        "step": 5,
        "name": "vision_first",
        "desc": "Screenshot HD + Gemini Vision localiza o item na sidebar expandida",
        "max_tentativas": 3,
        "scroll_entre_tentativas": 280,
        "guardrail_x_pct": 0.45
      },
      {
        "step": 6,
        "name": "sidebar_explorer",
        "desc": "Resgate: percorre sidebar page-by-page com crop focado até 8 páginas"
      },
      {
        "step": 7,
        "name": "gps_fallback",
        "desc": "Último recurso: clique nas coordenadas originais do capture"
      }
    ],
    "known_failures": [
      {
        "failure": "Scroll deslocado — sidebar no fundo após passo anterior",
        "mitigation": "_resetar_scroll_sidebar() antes do hover",
        "log_signal": "Scroll sidebar -> before:534 after:534 changed:False"
      },
      {
        "failure": "Hover nas coords do capture (submenu) sem submenu aberto",
        "mitigation": "Usar faixa.x_hover fixo (~40px) em vez de coords_relativas.x_pct",
        "log_signal": "Vision-First Hover sidebar X:323"
      },
      {
        "failure": "Brain DB com coordenadas antigas inválidas",
        "mitigation": "validacao_ok=0 invalida a entrada; Brain DB v2 descarta automaticamente",
        "log_signal": "Brain ✅ Acerto → Validador ❌ FALHA"
      },
      {
        "failure": "Angular Material propaga mousedown pai+filho (duplo clique)",
        "mitigation": "Debounce 400ms no capture_semantic.py",
        "log_signal": "Debounce ⏭ Clique ignorado"
      },
      {
        "failure": "Navegação Angular lazy-loading mata a página entre passos",
        "mitigation": "_aguardar_angular_pronto(timeout=20) após menu_navigation",
        "log_signal": "Target page, context or browser has been closed"
      }
    ],
    "validation": {
      "approach": "DOM determinístico + Gemini visual",
      "dom_check": "aria-current, aria-selected, aria-expanded, class active/selected",
      "gemini_prompt": "O item ficou ativo/destacado no menu lateral? NÃO avaliar painel central.",
      "fail_open": false
    },
    "iframe_aware": false,
    "sistema_testado": ["Senior X — Angular Material 14+"]
  },

  {
    "name": "button_click",
    "version": 1,
    "description": "Clique em botão de ação primária ou secundária. O padrão mais simples — um clique direto em um elemento interativo visível. Cobre botões de salvar, confirmar, cancelar, abrir modal, executar ação.",
    "signals": {
      "dom": ["button", "a[role='button']", "[mat-button]", "[mat-raised-button]", "[mat-flat-button]", "p-button", ".btn"],
      "visual": ["botão com texto", "botão de ícone", "link de ação"],
      "x_pct_max": 1.0
    },
    "preconditions": [
      "elemento visível e habilitado (não disabled)"
    ],
    "strategy_steps": [
      {
        "step": 1,
        "name": "brain_db",
        "desc": "Consulta Brain DB",
        "timeout_ms": 1500
      },
      {
        "step": 2,
        "name": "css_direto",
        "desc": "Seletor CSS do roteiro",
        "timeout_ms": 800
      },
      {
        "step": 3,
        "name": "vision_first",
        "desc": "Screenshot + Gemini localiza o botão",
        "max_tentativas": 3
      },
      {
        "step": 4,
        "name": "sniper_dom",
        "desc": "Candidatos por texto/aria: text='label', role=button name='label', aria-label",
        "timeout_ms": 1000
      },
      {
        "step": 5,
        "name": "gps_fallback",
        "desc": "Coordenadas do capture"
      }
    ],
    "known_failures": [
      {
        "failure": "Botão dentro de modal ou overlay — não encontrado no DOM principal",
        "mitigation": "Busca em todos os frames; Gemini com tela inteira vê o modal"
      },
      {
        "failure": "Botão desabilitado (disabled/loading) no momento da execução",
        "mitigation": "_aguardar_estabilidade antes de clicar; retry após pausa"
      }
    ],
    "validation": {
      "approach": "Gemini visual geral",
      "gemini_prompt": "Evidência esperada na tela após o clique.",
      "fail_open": true
    },
    "iframe_aware": true,
    "sistema_testado": ["Senior X — Angular Material 14+", "GED iframe"]
  },

  {
    "name": "table_selection",
    "version": 1,
    "description": "Seleção ou abertura de item em tabela, lista ou grade. Cobre: clicar numa linha de tabela, abrir uma pasta/arquivo em lista, marcar checkbox de linha, selecionar registro em grid. Frequentemente ocorre dentro de iframe no Senior X (GED).",
    "signals": {
      "dom": ["tr", ".ui-table-row", "#itemTitle", ".list-item", "p-checkbox", "[role='row']", ".file-item", ".folder-item"],
      "visual": ["linha de tabela", "item de lista", "pasta", "arquivo", "checkbox de linha"],
      "x_pct_max": 1.0
    },
    "preconditions": [
      "lista ou tabela carregada e visível",
      "se iframe: iframe carregado (wait_for attached)"
    ],
    "strategy_steps": [
      {
        "step": 1,
        "name": "brain_db",
        "desc": "Consulta Brain DB",
        "timeout_ms": 1500
      },
      {
        "step": 2,
        "name": "css_com_texto",
        "desc": "seletor_css do roteiro — deve incluir :has-text() para evitar colisão com outros itens da lista",
        "timeout_ms": 800,
        "nota": "Ex: #itemTitle:has-text('Financeiro') em vez de #itemTitle genérico"
      },
      {
        "step": 3,
        "name": "vision_first",
        "desc": "Screenshot + Gemini. Se iframe_hint: screenshot focado no iframe",
        "max_tentativas": 3
      },
      {
        "step": 4,
        "name": "sniper_dom",
        "desc": "Candidatos: text='label', tr:has-text, .list-item:has-text. Busca em frames filhos.",
        "timeout_ms": 1000
      },
      {
        "step": 5,
        "name": "iframe_explorer",
        "desc": "Resgate: DOM direto no frame + Gemini com crop do iframe",
        "ativado_por": "iframe_hint presente na validação"
      }
    ],
    "known_failures": [
      {
        "failure": "seletor_css genérico (#itemTitle) pega o primeiro item da lista em vez do alvo",
        "mitigation": "capture_semantic deve gerar seletor com :has-text('label') ou id único",
        "log_signal": "[CSS] ✅ Seletor direto funcionou — mas item errado foi aberto"
      },
      {
        "failure": "iframe_hint 'ci' não resolve — nome/src do iframe diferente",
        "mitigation": "Inspecionar page.frames no console: frame.name e frame.url[:60]",
        "log_signal": "[iFrame Explorer] Gemini não localizou no iframe"
      },
      {
        "failure": "Duplo clique necessário (abrir pasta) gravado como clique simples",
        "mitigation": "capture_semantic v2 detecta dblclick e promove o último clique",
        "log_signal": "[DblClick] ⚡ Clique anterior promovido para duplo_clique"
      },
      {
        "failure": "Lista paginada — item na página 2 não visível",
        "mitigation": "iframe_explorer percorre com scroll dentro do frame"
      }
    ],
    "validation": {
      "approach": "Gemini com crop do iframe quando iframe_hint presente",
      "iframe_prompt": "Título, breadcrumb ou conteúdo mostra o item aberto. NÃO buscar na sidebar.",
      "gemini_prompt": "Linha selecionada ou conteúdo do item visível.",
      "fail_open": true
    },
    "iframe_aware": true,
    "sistema_testado": ["Senior X GED — iframe 'ci'", "PrimeFaces p-table"]
  },

  {
    "name": "search_debounce",
    "version": 1,
    "description": "Preenchimento de campo de busca seguido de espera por resultado (debounce). O sistema dispara uma query e aguarda a lista filtrar. Cobre: campos de busca em tabelas, filtros de autocomplete, lookups de registro.",
    "signals": {
      "dom": ["input[type='search']", "input[placeholder*='busca']", "input[placeholder*='pesquisa']", "input[placeholder*='filtro']", "[aria-label*='busca']", ".search-input", "mat-autocomplete"],
      "visual": ["campo de busca", "lupa", "filtro", "autocomplete"],
      "x_pct_max": 1.0
    },
    "preconditions": [
      "campo de busca visível e focável",
      "lista/tabela associada presente na tela"
    ],
    "strategy_steps": [
      {
        "step": 1,
        "name": "brain_db",
        "desc": "Consulta Brain DB",
        "timeout_ms": 1500
      },
      {
        "step": 2,
        "name": "css_direto",
        "desc": "Seletor CSS do roteiro",
        "timeout_ms": 800
      },
      {
        "step": 3,
        "name": "preencher_e_aguardar",
        "desc": "Preenche o campo, pressiona Enter, aguarda networkidle",
        "wait_networkidle_ms": 4000,
        "nota": "Ctrl+A + Backspace antes de digitar para limpar valor anterior"
      },
      {
        "step": 4,
        "name": "sniper_dom",
        "desc": "input[type='search'], input[placeholder*='busca'], aria-label*='busca'",
        "timeout_ms": 1000
      },
      {
        "step": 5,
        "name": "vision_first",
        "desc": "Screenshot + Gemini localiza o campo de busca",
        "max_tentativas": 2
      }
    ],
    "known_failures": [
      {
        "failure": "Campo com valor anterior não limpo — busca concatenada",
        "mitigation": "Ctrl+A + Backspace antes de digitar"
      },
      {
        "failure": "Resultado demora mais que 4s (servidor lento)",
        "mitigation": "Aumentar wait_networkidle_ms para 8000 em redes lentas"
      },
      {
        "failure": "Autocomplete Angular — não dispara sem KeyDown após digitação",
        "mitigation": "page.keyboard.press('ArrowDown') após digitar + 'Enter'"
      }
    ],
    "validation": {
      "approach": "Gemini visual geral",
      "gemini_prompt": "Lista filtrada com o termo de busca visível nos resultados.",
      "fail_open": true
    },
    "iframe_aware": true,
    "sistema_testado": ["Senior X — formulários Angular"]
  },

  {
    "name": "form_fill",
    "version": 1,
    "description": "Preenchimento de campo de formulário (input, textarea, select, date picker). Não há debounce — o objetivo é apenas inserir um valor num campo, sem necessidade de aguardar resultado de rede.",
    "signals": {
      "dom": ["input[type='text']", "input[type='number']", "input[type='email']", "input[type='date']", "textarea", "select", "mat-select", "mat-datepicker", "p-inputtext", "p-dropdown"],
      "visual": ["campo de texto", "campo de data", "dropdown", "textarea"],
      "x_pct_max": 1.0
    },
    "preconditions": [
      "campo visível e não readonly",
      "formulário no estado de edição (não apenas visualização)"
    ],
    "strategy_steps": [
      {
        "step": 1,
        "name": "brain_db",
        "desc": "Consulta Brain DB",
        "timeout_ms": 1500
      },
      {
        "step": 2,
        "name": "css_direto",
        "desc": "Seletor CSS do roteiro — name, placeholder ou aria-label são mais estáveis que id Angular",
        "timeout_ms": 800
      },
      {
        "step": 3,
        "name": "preencher_campo",
        "desc": "Clica, Ctrl+A, Backspace, digita valor. Para select: select_option(value) ou select_option(label)",
        "delay_typing_ms": 40
      },
      {
        "step": 4,
        "name": "sniper_dom",
        "desc": "placeholder, aria-label, name, role=textbox",
        "timeout_ms": 1000
      },
      {
        "step": 5,
        "name": "vision_first",
        "desc": "Screenshot + Gemini localiza o campo",
        "max_tentativas": 2
      }
    ],
    "known_failures": [
      {
        "failure": "Campo mascarado (CPF, CNPJ, telefone) rejeita digitação direta",
        "mitigation": "Usar keyboard.type com delay=60ms; alguns campos precisam de clique no início"
      },
      {
        "failure": "mat-select não responde a select_option (não é <select> nativo)",
        "mitigation": "Clicar para abrir o dropdown, depois clicar na opção por texto"
      },
      {
        "failure": "Data picker Angular não aceita digitação — abre calendário",
        "mitigation": "Localizar o input interno do date picker e preencher direto"
      },
      {
        "failure": "Campo readonly em modo visualização — não abre edição",
        "mitigation": "Verificar se há botão 'Editar' antes de tentar preencher"
      }
    ],
    "validation": {
      "approach": "Gemini visual geral",
      "gemini_prompt": "O campo mostra o valor preenchido.",
      "fail_open": true
    },
    "iframe_aware": true,
    "sistema_testado": ["Senior X — Angular Reactive Forms", "PrimeFaces forms"]
  }
]