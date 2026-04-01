# Documento de Requisitos

## Introdução

Esta especificação cobre a **Fase 1 de Estabilização do Legado** do Senior Training OS — uma plataforma de automação de treinamentos para o ERP Senior X que transforma fluxos capturados em vídeos, SCORM, PDF e camadas DAP.

O pipeline central é: **captura → roteiro JSON → execução → artefatos de saída**. O roteiro JSON é o contrato entre todos os módulos.

Esta fase corrige 9 problemas identificados (P0, P1 e P2) que causam perda silenciosa de dados, efeitos colaterais na inicialização, divergência de comportamento entre módulos e degradação da memória do Brain. Nenhuma alteração de schema do roteiro JSON é permitida.

---

## Glossário

- **Sistema**: o conjunto de módulos do Senior Training OS.
- **Roteiro**: artefato JSON central que representa um fluxo de treinamento estruturado.
- **Capture_Module**: módulo `capture.py` responsável pela captura de interações do usuário.
- **Main_Module**: módulo `main.py` responsável pela execução e gravação do roteiro.
- **App_Module**: módulo `app.py`, entrypoint FastAPI e orquestrador de tarefas em background.
- **Generator_Engine**: módulo `generator_engine.py` responsável pela geração de roteiros via IA.
- **Vision_Engine**: módulo `vision_engine.py` responsável pela localização resiliente de elementos no browser.
- **DAP_Engine**: módulo `dap_engine.py` responsável pelo RAG e ingestão no Pinecone.
- **Capture_Hybrid_Shadow**: módulo `capture_hybrid_shadow.py`, variante de captura com suporte a Shadow DOM.
- **Capture_Dual_Output**: módulo `capture_dual_output.py`, variante de captura com saída dupla.
- **Utils**: módulo `utils.py`, fonte canônica de utilitários compartilhados.
- **limpar_nome**: função canônica em `utils.py` que sanitiza strings para uso como nome de arquivo ou ID vetorial, removendo acentos e caracteres proibidos, limitando a 40 caracteres.
- **validar_roteiro**: função centralizada em `utils.py` que aplica o portão de qualidade ao roteiro.
- **Brain**: banco SQLite `brain.db` que armazena memória semântica de seletores para auto-cura.
- **Aura**: IA responsável pela transformação do log de captura em roteiro estruturado.
- **Log_Mapeador**: lista de ações capturadas em memória durante a sessão de captura.
- **ids_acoes_tecnicas**: lista de IDs de ações retornada pela Aura para montar os passos do roteiro.
- **getRectComFallback**: função JavaScript injetada no browser que sobe a árvore DOM para obter coordenadas válidas quando `getBoundingClientRect()` retorna zero.
- **Pinecone**: banco vetorial usado para RAG e ingestão de roteiros.
- **ID_Vetor**: identificador único de um vetor no Pinecone, derivado do nome da aula e do número do passo.

---

## Requisitos

### Requisito 1: Validação de IDs Alucinados pelo Gemini na Mesclagem do Roteiro

**User Story:** Como desenvolvedor do pipeline, quero que IDs de ações inexistentes retornados pelo Gemini sejam detectados e registrados, para que nenhuma ação seja descartada silenciosamente durante a montagem do roteiro.

#### Critérios de Aceitação

1. WHEN `_invocar_aura_sync` itera sobre `ids_acoes_tecnicas` retornados pela Aura, THE `Capture_Module` SHALL verificar se cada `id_tec` existe no `Log_Mapeador` antes de tentar mesclar a ação.
2. IF um `id_tec` não corresponde a nenhum item do `Log_Mapeador`, THEN THE `Capture_Module` SHALL emitir um `logger.warning` contendo o valor do `id_tec` ausente e o nome da aula.
3. IF um `id_tec` não corresponde a nenhum item do `Log_Mapeador`, THEN THE `Capture_Module` SHALL omitir a ação do passo sem interromper o processamento dos demais IDs do mesmo passo.
4. THE `Capture_Module` SHALL preservar o comportamento atual de mesclagem para todos os `id_tec` válidos, sem alterar a estrutura do roteiro gerado.

---

### Requisito 2: Eliminação do Efeito Colateral de Importação de `app.py` em `main.py`

**User Story:** Como operador do sistema, quero que `main.py` não importe `app.py` ao ser executado como subprocess, para que a inicialização do motor de gravação não dispare efeitos colaterais como criação de diretórios, conexão SQLite e instanciação do WebSocket manager.

#### Critérios de Aceitação

1. THE `Main_Module` SHALL importar `limpar_nome` exclusivamente de `utils.py`.
2. THE `Main_Module` SHALL remover o bloco `try/except` que importa `limpar_nome` de `app.py` com fallback local.
3. WHEN `main.py` é executado como subprocess pelo `App_Module`, THE `Main_Module` SHALL inicializar sem executar nenhum efeito colateral proveniente de `app.py`.
4. THE `Main_Module` SHALL manter comportamento funcional idêntico ao atual para todas as operações que dependem de `limpar_nome`.

---

### Requisito 3: Centralização de `limpar_nome` em `utils.py`

**User Story:** Como mantenedor do sistema, quero que todos os módulos usem uma única implementação de `limpar_nome`, para que o comportamento de sanitização de nomes seja consistente em todo o pipeline.

#### Critérios de Aceitação

1. THE `Utils` SHALL ser a única fonte de definição de `limpar_nome` entre os módulos do pipeline principal.
2. THE `Capture_Module` SHALL importar `limpar_nome` de `utils.py` e remover sua definição local.
3. THE `App_Module` SHALL importar `limpar_nome` de `utils.py` e remover sua definição local.
4. THE `Capture_Dual_Output` SHALL importar `limpar_nome` de `utils.py` e remover sua definição local.
5. THE `Capture_Hybrid_Shadow` SHALL importar `limpar_nome` de `utils.py` e remover sua definição local.
6. THE `Generator_Engine` SHALL importar `limpar_nome` de `utils.py` e remover sua definição local.
7. WHERE `limpar_nome` é usada para sanitizar nomes de arquivos ou IDs, THE `Sistema` SHALL produzir resultados com remoção de acentos e limite de 40 caracteres, conforme a implementação canônica em `utils.py`.
8. THE `Sistema` SHALL preservar compatibilidade total com roteiros existentes em `roteiros_salvos/` após a centralização.

---

### Requisito 4: Centralização de `validar_roteiro` em `utils.py`

**User Story:** Como mantenedor do sistema, quero que a lógica de portão de qualidade do roteiro exista em um único lugar, para que todos os módulos apliquem os mesmos critérios de validação sem duplicação.

#### Critérios de Aceitação

1. THE `Utils` SHALL expor uma função `validar_roteiro(roteiro: dict) -> tuple[bool, str]` com os mesmos critérios das implementações existentes em `Capture_Module` e `App_Module`.
2. THE `validar_roteiro` em `Utils` SHALL reprovar roteiros com menos de 2 passos, retornando `False` e uma mensagem descritiva.
3. THE `validar_roteiro` em `Utils` SHALL reprovar roteiros onde menos de 50% das ações técnicas válidas possuem `seletor_hint` preenchido, retornando `False` e uma mensagem descritiva.
4. THE `validar_roteiro` em `Utils` SHALL reprovar roteiros onde mais de 70% das ações técnicas válidas possuem `confianca_captura` igual a `"baixa"`, retornando `False` e uma mensagem descritiva.
5. THE `validar_roteiro` em `Utils` SHALL ignorar ações com `acao == "concluir_video"` no cálculo dos percentuais.
6. THE `Capture_Module` SHALL importar e usar `validar_roteiro` de `utils.py`, removendo sua implementação local `_validar_roteiro`.
7. THE `App_Module` SHALL importar e usar `validar_roteiro` de `utils.py`, removendo sua implementação local `_validar_roteiro_app`.
8. THE `Generator_Engine` SHALL chamar `validar_roteiro` de `utils.py` após a geração do roteiro e emitir `logger.warning` se o roteiro for reprovado.
9. FOR ALL roteiros que passavam na validação antes da centralização, THE `validar_roteiro` em `Utils` SHALL retornar `True` com os mesmos critérios.

---

### Requisito 5: Adição de `getRectComFallback` ao JS Injetado em `capture.py`

**User Story:** Como operador de captura, quero que o módulo de captura principal use `getRectComFallback` ao registrar coordenadas de elementos, para que elementos Angular em transição de layout não gerem coordenadas zeradas no roteiro.

#### Critérios de Aceitação

1. THE `Capture_Module` SHALL incluir a função JavaScript `getRectComFallback` no script injetado via `_injetar_em_contexto`, com a mesma lógica presente em `Capture_Dual_Output`.
2. WHEN `processarEvento` é chamado no script injetado de `Capture_Module`, THE `Capture_Module` SHALL usar `getRectComFallback(target)` para obter as coordenadas do elemento, em vez de `target.getBoundingClientRect()` diretamente.
3. THE `getRectComFallback` em `Capture_Module` SHALL subir a árvore DOM até encontrar um elemento com `width > 0` e `height > 0`, com limite máximo de iterações para evitar loop infinito.
4. IF nenhum elemento com dimensões válidas for encontrado após percorrer a árvore, THEN THE `getRectComFallback` SHALL retornar o resultado de `getBoundingClientRect()` do elemento original como fallback.
5. THE `Capture_Module` SHALL preservar o comportamento atual de todos os outros eventos capturados (clique, duplo clique, digitação, blur) sem alteração.

---

### Requisito 6: Expansão do Filtro de Seletores Válidos no Brain

**User Story:** Como operador do sistema, quero que o Brain aprenda seletores válidos de componentes Angular e PrimeNG, para que a memória semântica não descarte seletores funcionais que não seguem os prefixos tradicionais.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL expandir o filtro de `_registrar_sucesso_cache` para aceitar seletores que começam com `[role=`, `button.`, `p-`, `mat-`, além dos prefixos já aceitos (`text=`, `[`, `#`).
2. THE `Vision_Engine` SHALL aceitar seletores que contêm `:has-text(` como válidos para armazenamento no Brain, independentemente do prefixo.
3. WHEN um seletor válido é identificado por qualquer camada do orquestrador, THE `Vision_Engine` SHALL armazená-lo no Brain sem descarte silencioso.
4. THE `Vision_Engine` SHALL preservar o comportamento atual de descarte para seletores genuinamente vagos que não se enquadrem nos critérios expandidos.
5. THE `Vision_Engine` SHALL não alterar nenhuma das 7 camadas de resiliência além do filtro de `_registrar_sucesso_cache`.

---

### Requisito 7: Remoção do `return fallback` Duplicado em `capture_hybrid_shadow.py`

**User Story:** Como mantenedor do sistema, quero que `analisar_semantica_hibrida` não tenha instruções de retorno duplicadas, para que o código seja legível e não cause confusão em análises estáticas ou futuras manutenções.

#### Critérios de Aceitação

1. THE `Capture_Hybrid_Shadow` SHALL conter exatamente um `return fallback` no bloco de guarda que verifica `gemini_client` ou `HYBRID_DISABLE_GEMINI`.
2. THE `Capture_Hybrid_Shadow` SHALL preservar o comportamento funcional de `analisar_semantica_hibrida` após a remoção da linha duplicada.

---

### Requisito 8: Sanitização do ID do Vetor Pinecone em `dap_engine.py`

**User Story:** Como operador do pipeline de ingestão, quero que os IDs dos vetores no Pinecone sejam sanitizados antes da inserção, para que nomes de aula com espaços ou caracteres especiais não gerem IDs inválidos que causem falhas silenciosas na ingestão.

#### Critérios de Aceitação

1. THE `DAP_Engine` SHALL importar `limpar_nome` de `utils.py`.
2. WHEN `ingestar_para_pinecone` constrói o `id_vetor` para cada passo, THE `DAP_Engine` SHALL aplicar `limpar_nome` ao componente derivado do nome da aula antes de concatenar com o número do passo.
3. THE `DAP_Engine` SHALL garantir que o `id_vetor` resultante contenha apenas caracteres ASCII seguros, sem espaços ou caracteres proibidos pelo Pinecone.
4. THE `DAP_Engine` SHALL preservar o formato `{nome_sanitizado}_passo_{id_passo}` para o `id_vetor`.
5. FOR ALL nomes de aula que já produziam IDs válidos antes da correção, THE `DAP_Engine` SHALL produzir IDs equivalentes ou idênticos após a sanitização.

---

### Requisito 9: Portão de Qualidade Pós-Geração em `generator_engine.py`

**User Story:** Como operador do pipeline de geração, quero que roteiros gerados pela IA com qualidade insuficiente sejam identificados e registrados, para que roteiros com `elemento_alvo: {}` em todos os passos não passem silenciosamente pelo pipeline.

#### Critérios de Aceitação

1. THE `Generator_Engine` SHALL chamar `validar_roteiro` de `utils.py` após a geração bem-sucedida do roteiro e antes da persistência final.
2. IF `validar_roteiro` reprovar o roteiro gerado, THEN THE `Generator_Engine` SHALL emitir `logger.warning` com o motivo da reprovação.
3. THE `Generator_Engine` SHALL persistir o roteiro em `roteiros_salvos/` independentemente do resultado do portão de qualidade, para permitir revisão manual.
4. THE `Generator_Engine` SHALL não interromper o fluxo de retorno ao chamador quando o portão de qualidade reprovar o roteiro — o retorno de `{"status": "sucesso", ...}` deve ser preservado.
5. THE `Generator_Engine` SHALL remover sua implementação local `_validar_estrutura_roteiro` e usar `validar_roteiro` de `utils.py` como portão de qualidade semântico, mantendo a validação estrutural mínima existente como verificação prévia separada se necessário.
