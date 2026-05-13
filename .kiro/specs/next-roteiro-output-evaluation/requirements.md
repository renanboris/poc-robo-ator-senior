# Requirements Document: Avaliação do Output Dual (Roteiro + Shadow)

## Introduction

Este documento especifica os dois artefatos gerados pelo `capture_dual_output.py` do Senior Training OS (legado) que alimentam o repositório NEXT:

1. **Roteiro JSON** (`roteiros_salvos/`) - Artefato executável para geração de vídeos, SCORM e PDF
2. **Shadow JSONL** (`shadow_exports/`) - Dados semânticos enriquecidos para consumo do NEXT

O objetivo é documentar a estrutura atual dos outputs para que o time do NEXT possa desenvolver a partir desses dados.

## Glossary

- **Roteiro**: JSON estruturado com passos pedagógicos e ações técnicas para execução automatizada
- **Shadow**: JSONL com eventos semânticos enriquecidos (intenção, entidade de negócio, padrões de interação)
- **Dual_Output**: Modo de captura que gera roteiro + shadow simultaneamente
- **Semantic_Action**: Classificação da intenção do usuário (fill, search, confirm, delete, save, open, navigate, select, close)
- **Business_Entity**: Entidade de negócio envolvida (pasta, documento, cliente, pedido, menu, campo, selecao, elemento)
- **Pattern_Detectado**: Padrão de interação UI (breadcrumb_navigation, menu_navigation, toolbar_action, table_selection, form_fill, button_click, modal_action, tree_item_open, search_debounce)
- **Capture_Scope**: Contexto da captura (shell ou module_iframe)
- **Is_Noise**: Flag indicando se o evento é ruído (navegação utilitária que não vira passo de treinamento)

## Requirements

### Requirement 1: Estrutura do Roteiro JSON

**User Story:** Como desenvolvedor do NEXT, eu quero entender a estrutura do roteiro JSON gerado, para que eu possa consumir os dados técnicos de execução.

#### Acceptance Criteria

1. THE Roteiro SHALL ser salvo em `roteiros_salvos/{nome_aula}.json`
2. THE Roteiro SHALL conter 3 campos de primeiro nível: `metadata`, `configuracao_gravacao`, `passos`
3. THE campo `metadata` SHALL conter: `id_treinamento`, `nome_aula`, `gerado_por_ia`, `validado_hitl`
4. THE campo `configuracao_gravacao` SHALL conter: `gravar_video`, `pasta_destino`, `voz_ia`
5. THE campo `passos` SHALL ser um array de objetos com: `id_passo`, `tipo_passo`, `peso_narrativo`, `pause_sugerida`, `pedagogia`, `is_conclusao`, `acoes_tecnicas`
6. THE campo `acoes_tecnicas` SHALL conter: `acao`, `intencao_semantica`, `elemento_alvo`, `valor_input`, `micro_narracao`, `is_context_menu_item`
7. THE campo `elemento_alvo` SHALL conter: `descricao_visual`, `contexto_tela`, `tipo_elemento`, `confianca_captura`, `label_curto`, `coordenadas_relativas`, `seletor_hint`, `iframe_hint`, `html_hint`, `screenshot_referencia`
8. THE último passo SHALL ter `is_conclusao: true` e conter uma ação `concluir_video`

### Requirement 2: Estrutura do Shadow JSONL

**User Story:** Como desenvolvedor do NEXT, eu quero entender a estrutura do shadow JSONL gerado, para que eu possa consumir os dados semânticos enriquecidos.

#### Acceptance Criteria

1. THE Shadow SHALL ser salvo em `shadow_exports/{nome_aula}_shadow.jsonl`
2. THE Shadow SHALL ser um arquivo JSONL (um JSON por linha, ordenado por `id_acao`)
3. THE cada evento Shadow SHALL conter os seguintes campos obrigatórios:
   - `id_acao` (int): ID sequencial da ação
   - `captured_at` (string ISO 8601): Timestamp UTC da captura
   - `acao` (string): Ação bruta capturada (clique, preencher_campo, digitar_e_enter, etc)
   - `capture_scope` (string): "shell" ou "module_iframe"
   - `is_noise` (bool): Flag de ruído (eventos utilitários que não viram passo)
   - `intencao_semantica` (string): Descrição em linguagem natural da intenção
   - `semantic_action` (string): Classificação semântica (fill, search, confirm, delete, save, open, navigate, select, close)
   - `business_entity` (string): Entidade de negócio (pasta, documento, cliente, pedido, menu, campo, selecao, elemento)
   - `business_target` (string): Label do elemento alvo
   - `pattern_detectado` (string): Padrão de interação UI
   - `valor_input` (string): Valor digitado (vazio para cliques)
   - `micro_narracao` (string): Narração curta (máximo 60 caracteres)
   - `contexto_semantico` (object): Contexto da tela atual
   - `validacao_esperada` (object): Validação esperada após a ação
   - `expected_effect` (string): Efeito esperado (top-level para integração NEXT)
   - `elemento_alvo` (object): Metadados do elemento UI
   - `technical` (object): Dados técnicos brutos de captura

4. THE campo `contexto_semantico` SHALL conter:
   - `tela_atual.tela_id` (string): Título da página
   - `tela_atual.url` (string): URL da página
   - `tela_atual.iframe` (string | null): ID do iframe (null se shell)
   - `tela_atual.scope` (string): "shell" ou "module_iframe"

5. THE campo `validacao_esperada` SHALL conter:
   - `alvo` (string): Descrição da validação esperada

6. THE campo `elemento_alvo` SHALL conter os mesmos campos do roteiro (ver Requirement 1.7)

7. THE campo `technical` SHALL conter dados brutos de captura:
   - `acao`, `tag`, `text_hint`, `iframe_hint`, `seletor_css`, `html_snapshot`
   - `x_pct`, `y_pct`, `w_pct`, `h_pct` (coordenadas relativas)
   - `viewport_w`, `viewport_h` (dimensões da viewport)
   - `page_title`, `url_hint`

### Requirement 3: Enriquecimento Semântico com Gemini Vision

**User Story:** Como desenvolvedor do NEXT, eu quero entender como os eventos são enriquecidos semanticamente, para que eu possa confiar na qualidade dos dados.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL enriquecer eventos com Gemini Vision APÓS o encerramento da sessão de captura
2. THE enriquecimento SHALL ser seletivo: eventos com label descritivo usam fallback heurístico, eventos ambíguos usam Gemini
3. THE enriquecimento SHALL processar eventos em lotes paralelos de até 8 chamadas simultâneas
4. THE Sistema_Legado SHALL emitir `CAPTURA_SEM_GEMINI:{total}` no stdout quando Gemini não está configurado
5. THE Sistema_Legado SHALL usar fallback heurístico quando Gemini falha (sem bloquear a captura)
6. THE enriquecimento SHALL preencher os campos: `intencao_semantica`, `descricao_visual`, `contexto_tela`, `tipo_elemento`, `confianca_captura`

### Requirement 4: Inferência Semântica (Vocabulário Controlado)

**User Story:** Como desenvolvedor do NEXT, eu quero entender o vocabulário controlado de classificações semânticas, para que eu possa implementar lógica de negócio consistente.

#### Acceptance Criteria

1. THE campo `semantic_action` SHALL usar apenas os seguintes valores:
   - `fill`: Preencher campo de formulário
   - `search`: Buscar/filtrar dados
   - `confirm`: Confirmar operação
   - `delete`: Excluir/remover item
   - `save`: Salvar/gravar dados
   - `open`: Abrir modal/pasta/menu
   - `navigate`: Navegar entre telas
   - `select`: Selecionar item de lista
   - `close`: Fechar modal/janela

2. THE campo `business_entity` SHALL usar apenas os seguintes valores:
   - `pasta`: Pasta/diretório
   - `documento`: Documento/arquivo
   - `cliente`: Cliente/fornecedor
   - `pedido`: Pedido/nota fiscal
   - `menu`: Item de menu
   - `campo`: Campo de formulário
   - `selecao`: Checkbox/radio
   - `elemento`: Elemento genérico

3. THE campo `pattern_detectado` SHALL usar apenas os seguintes valores:
   - `breadcrumb_navigation`: Navegação por breadcrumb
   - `menu_navigation`: Navegação por menu
   - `toolbar_action`: Ação de toolbar
   - `table_selection`: Seleção em tabela/lista
   - `form_fill`: Preenchimento de formulário
   - `button_click`: Clique em botão
   - `modal_action`: Ação em modal/dialog
   - `tree_item_open`: Abertura de nó de árvore
   - `search_debounce`: Input de busca com debounce
   - `unknown`: Padrão desconhecido

4. THE Sistema_Legado SHALL inferir `semantic_action` a partir de: ação bruta, label, seletor, tag, valor_input
5. THE Sistema_Legado SHALL inferir `business_entity` a partir de: label, seletor, tag, contexto_tela
6. THE Sistema_Legado SHALL inferir `pattern_detectado` a partir de: ação, label, seletor, tag, capture_scope

### Requirement 5: Classificação de Ruído

**User Story:** Como desenvolvedor do NEXT, eu quero entender quais eventos são classificados como ruído, para que eu possa filtrar eventos utilitários.

#### Acceptance Criteria

1. THE campo `is_noise` SHALL ser `true` para os seguintes casos:
   - Clique em breadcrumb/home (navegação utilitária)
   - Enter isolado sem valor de input
   - Clique em ícone utilitário sem label semântico (tag: i, svg, path)

2. THE NEXT SHALL filtrar eventos com `is_noise: true` ao gerar passos de treinamento
3. THE NEXT SHALL preservar eventos com `is_noise: true` para análise de comportamento do usuário

### Requirement 6: Portão de Qualidade do Roteiro

**User Story:** Como desenvolvedor do NEXT, eu quero entender os critérios de qualidade do roteiro, para que eu possa priorizar roteiros confiáveis.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL validar cada roteiro usando `_validar_roteiro()`
2. THE roteiro SHALL ser aprovado WHEN:
   - Possui >= 2 passos (1 real + 1 conclusão)
   - >= 50% das ações têm `seletor_hint` preenchido
   - <= 70% das ações têm `confianca_captura == 'baixa'`

3. WHEN roteiro é aprovado, THE Sistema_Legado SHALL iniciar auto-rebuild da biblioteca de ações em background
4. WHEN roteiro é reprovado, THE Sistema_Legado SHALL salvar o roteiro mas NÃO indexar na biblioteca
5. THE Sistema_Legado SHALL emitir no log: `Portão de qualidade: APROVADO/REPROVADO — {motivo}`

### Requirement 7: Localização de Arquivos

**User Story:** Como desenvolvedor do NEXT, eu quero saber onde os arquivos são salvos, para que eu possa implementar lógica de leitura.

#### Acceptance Criteria

1. THE Roteiro SHALL ser salvo em: `roteiros_salvos/{limpar_nome(nome_aula)}.json`
2. THE Shadow SHALL ser salvo em: `shadow_exports/{limpar_nome(nome_aula)}_shadow.jsonl`
3. THE Screenshots SHALL ser salvos em: `audios_gerados/{id_treinamento}/screenshots/`
4. THE Screenshots de tela completa SHALL usar o padrão: `acao_{id_acao}.jpg`
5. THE Screenshots de elemento SHALL usar o padrão: `elemento_acao_{id_acao}.jpg`
6. THE Sistema_Legado SHALL emitir no stdout:
   - `ROTEIRO_GERADO:{caminho}` quando roteiro é salvo
   - `SHADOW_GERADO:{caminho}` quando shadow é salvo

### Requirement 8: Marcadores de Status no Stdout

**User Story:** Como desenvolvedor do NEXT, eu quero entender os marcadores de status emitidos no stdout, para que eu possa monitorar o progresso da captura.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL emitir os seguintes marcadores no stdout (flush=True):
   - `CAPTURA_SEM_GEMINI:{total}` - Gemini não configurado, usou fallback heurístico
   - `ALERTA_GEMINI_FALHOU:true` - Gemini falhou após retries, tentando OpenAI
   - `IA_USADA:gemini` - Roteiro gerado com Gemini
   - `IA_USADA:openai-fallback` - Roteiro gerado com OpenAI (fallback)
   - `ROTEIRO_GERADO:{caminho}` - Roteiro salvo com sucesso
   - `SHADOW_GERADO:{caminho}` - Shadow salvo com sucesso

2. THE NEXT SHALL parsear esses marcadores para atualizar o dashboard em tempo real

### Requirement 9: Fallback OpenAI

**User Story:** Como desenvolvedor do NEXT, eu quero entender o comportamento de fallback quando Gemini falha, para que eu possa confiar na resiliência do sistema.

#### Acceptance Criteria

1. WHEN Gemini falha após 5 tentativas com backoff exponencial, THE Sistema_Legado SHALL tentar OpenAI como fallback
2. THE fallback OpenAI SHALL usar o mesmo prompt e formato JSON do Gemini
3. THE fallback OpenAI SHALL usar o modelo `gpt-4o` com `response_format: json_object`
4. WHEN OpenAI também falha, THE Sistema_Legado SHALL retornar `None` e emitir erro no log
5. THE Sistema_Legado SHALL emitir `IA_USADA:openai-fallback` no stdout quando fallback é usado

### Requirement 10: Exemplo de Evento Shadow Completo

**User Story:** Como desenvolvedor do NEXT, eu quero ver um exemplo completo de evento shadow, para que eu possa implementar o parser corretamente.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL fornecer um exemplo anotado de evento shadow no formato:

```json
{
  "id_acao": 1,
  "captured_at": "2026-05-06T14:30:00.123456+00:00",
  "acao": "clique",
  "capture_scope": "module_iframe",
  "is_noise": false,
  "intencao_semantica": "Criar nova pasta no GED",
  "semantic_action": "open",
  "business_entity": "pasta",
  "business_target": "Nova Pasta",
  "pattern_detectado": "toolbar_action",
  "valor_input": "",
  "micro_narracao": "Criar nova pasta no GED",
  "contexto_semantico": {
    "tela_atual": {
      "tela_id": "Gestão Eletrônica de Documentos",
      "url": "https://platform.senior.com.br/ged/documentos",
      "iframe": "ged-module-frame",
      "scope": "module_iframe"
    }
  },
  "validacao_esperada": {
    "alvo": "Conteúdo ou modal aberto"
  },
  "expected_effect": "Conteúdo ou modal aberto",
  "elemento_alvo": {
    "descricao_visual": "Botão azul com ícone de pasta e texto 'Nova Pasta'",
    "contexto_tela": "Gestão Eletrônica de Documentos",
    "tipo_elemento": "button",
    "confianca_captura": "alta",
    "label_curto": "Nova Pasta",
    "coordenadas_relativas": {
      "x_pct": 0.1234,
      "y_pct": 0.0567,
      "w_pct": 0.0890,
      "h_pct": 0.0234
    },
    "seletor_hint": "[data-testid='new-folder-button']",
    "iframe_hint": "ged-module-frame",
    "html_hint": "<button data-testid=\"new-folder-button\" class=\"btn btn-primary\"><i class=\"fa fa-folder\"></i> Nova Pasta</button>",
    "screenshot_referencia": "base64_encoded_jpeg_string..."
  },
  "technical": {
    "acao": "clique",
    "tag": "button",
    "text_hint": "Nova Pasta",
    "iframe_hint": "ged-module-frame",
    "seletor_css": "[data-testid='new-folder-button']",
    "html_snapshot": "<button data-testid=\"new-folder-button\" class=\"btn btn-primary\"><i class=\"fa fa-folder\"></i> Nova Pasta</button>",
    "x_pct": 0.1234,
    "y_pct": 0.0567,
    "w_pct": 0.0890,
    "h_pct": 0.0234,
    "viewport_w": 1920,
    "viewport_h": 1080,
    "page_title": "Gestão Eletrônica de Documentos",
    "url_hint": "https://platform.senior.com.br/ged/documentos"
  }
}
```

### Requirement 11: Diferenças entre Roteiro e Shadow

**User Story:** Como desenvolvedor do NEXT, eu quero entender as diferenças entre roteiro e shadow, para que eu possa escolher qual artefato consumir para cada caso de uso.

#### Acceptance Criteria

1. THE Roteiro SHALL ser usado para:
   - Execução automatizada (replay do workflow)
   - Geração de vídeos, SCORM e PDF
   - Validação de seletores e coordenadas

2. THE Shadow SHALL ser usado para:
   - Análise semântica de comportamento do usuário
   - Treinamento de modelos de IA
   - Geração de documentação inteligente
   - Detecção de padrões de interação
   - Classificação de entidades de negócio

3. THE Roteiro SHALL conter:
   - Passos pedagógicos agrupados (múltiplas ações por passo)
   - Âncoras pedagógicas e tooltips DAP
   - Micro narrações por ação
   - Flag `is_conclusao` para o último passo

4. THE Shadow SHALL conter:
   - Eventos atômicos (um evento por ação)
   - Classificações semânticas (semantic_action, business_entity, pattern_detectado)
   - Flag `is_noise` para filtrar eventos utilitários
   - Campo `expected_effect` para validação

5. THE NEXT SHALL consumir ambos os artefatos de forma complementar

### Requirement 12: Módulo shadow_builder.py (API Pública)

**User Story:** Como desenvolvedor do NEXT, eu quero entender a API pública do shadow_builder.py, para que eu possa reutilizar as funções de inferência semântica.

#### Acceptance Criteria

1. THE módulo `shadow_builder.py` SHALL exportar as seguintes funções públicas:
   - `utc_now()` - Retorna timestamp ISO 8601 UTC
   - `inferir_acao_semantica(acao, label, seletor, tag, valor_input, hints)` - Retorna semantic_action
   - `inferir_entidade_negocio(label, seletor, tag, contexto_tela, hints)` - Retorna business_entity
   - `inferir_padrao_interacao(acao, label, seletor, tag, capture_scope, hints)` - Retorna pattern_detectado
   - `classificar_ruido(label, seletor, acao, tag, capture_scope, valor_input, hints)` - Retorna is_noise

2. THE módulo `shadow_builder.py` SHALL ser PURO (sem Playwright, Gemini, OpenAI, Pinecone, asyncio)
3. THE NEXT SHALL poder importar e testar o módulo isoladamente
4. THE funções públicas SHALL aceitar um parâmetro opcional `hints: dict` para compatibilidade com capture_hybrid_shadow.py

### Requirement 13: Coordenadas Relativas vs Absolutas

**User Story:** Como desenvolvedor do NEXT, eu quero entender o sistema de coordenadas, para que eu possa implementar lógica de localização de elementos.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL sempre calcular coordenadas relativas (x_pct, y_pct, w_pct, h_pct) como floats de 0.0 a 1.0
2. THE coordenadas relativas SHALL ser calculadas a partir do centro do elemento: `cx = x + w/2`, `cy = y + h/2`
3. WHEN `getBoundingClientRect()` retorna dimensões zeradas, THE Sistema_Legado SHALL subir na árvore DOM até encontrar ancestral com dimensões válidas
4. WHEN nenhum ancestral tem dimensões válidas, THE Sistema_Legado SHALL usar valores padrão: `{x_pct: 0.5, y_pct: 0.5, w_pct: 0.05, h_pct: 0.05}`
5. THE Sistema_Legado SHALL emitir warning no log quando coordenadas padrão são usadas
6. THE NEXT SHALL interpretar coordenadas padrão (0.5, 0.5) como "centro da viewport" (fallback de último recurso)

### Requirement 14: Flag is_context_menu_item

**User Story:** Como desenvolvedor do NEXT, eu quero entender a flag `is_context_menu_item`, para que eu possa implementar lógica de localização de itens de menu de contexto.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL marcar `is_context_menu_item: true` quando:
   - A ação atual é `clique`
   - A ação anterior foi `clique_direito`

2. THE flag `is_context_menu_item` SHALL indicar que o elemento está dentro de um menu de contexto (overlay)
3. THE NEXT SHALL buscar o elemento dentro do overlay do menu em vez de varrer o DOM geral
4. THE flag SHALL estar presente no campo `acoes_tecnicas` do roteiro

### Requirement 15: Versionamento e Retrocompatibilidade

**User Story:** Como desenvolvedor do NEXT, eu quero entender a política de versionamento dos artefatos, para que eu possa implementar lógica de migração.

#### Acceptance Criteria

1. THE Sistema_Legado SHALL manter retrocompatibilidade de leitura para roteiros gerados em versões anteriores
2. WHEN novos campos são adicionados ao schema, THE Sistema_Legado SHALL torná-los opcionais
3. THE NEXT SHALL implementar detecção de versão baseada na presença/ausência de campos específicos
4. THE NEXT SHALL tratar campos ausentes com valores padrão seguros
5. THE Sistema_Legado SHALL documentar mudanças de schema em CHANGELOG.md (quando criado)
