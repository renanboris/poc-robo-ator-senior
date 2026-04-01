# Plano de Implementação: Fase 2 — Integração do Sidecar Semântico

## Visão Geral

Extração das funções de inferência semântica para `shadow_builder.py`, refatoração dos módulos de captura para importar desse módulo, e exposição do modo dual no dashboard via `/api/gravar-dual`.

A ordem de execução é obrigatória: cada tarefa depende da anterior.

## Tarefas

- [x] 1. Criar `shadow_builder.py` — módulo puro de inferência semântica
  - Criar o arquivo `shadow_builder.py` na raiz do projeto (mesmo nível de `utils.py`)
  - Imports permitidos: `json`, `os`, `logging`, `re`, `datetime`, `timezone`; importar `limpar_nome` de `utils`
  - Sem Playwright, Gemini, OpenAI, Pinecone, asyncio ou subprocess
  - Implementar `utc_now() -> str` retornando ISO 8601 UTC
  - Implementar `_infer_capture_scope(iframe_id: str | None) -> str` retornando `"shell"` ou `"module_iframe"`
  - Implementar `_infer_semantic_action_from_capture(acao, label, seletor, tag, valor_input) -> str` com vocabulário controlado: `fill`, `search`, `confirm`, `delete`, `save`, `open`, `navigate`, `select`, `close`
  - Implementar `_infer_business_entity_from_capture(label, seletor, tag, contexto_tela) -> str`
  - Implementar `_infer_pattern_from_capture(acao, label, seletor, tag, capture_scope) -> str`
  - Implementar `_is_noise_event(label, seletor, acao, tag, capture_scope, valor_input) -> bool`
  - Implementar `_montar_evento_shadow(**kwargs) -> dict` produzindo todos os campos obrigatórios do Evento_Shadow
  - Implementar `_salvar_shadow_jsonl(nome_aula, objetivo_aula, eventos) -> str | None`:
    - `os.makedirs("shadow_exports/", exist_ok=True)`
    - Ordenar eventos por `e.get("id_acao", 0)` antes de gravar
    - Gravar linha a linha com `json.dumps(evento, ensure_ascii=False)`
    - Em sucesso: `print(f"SHADOW_GERADO:{caminho}", flush=True)` e retornar `caminho`
    - Em exceção: `logger.warning(...)` e retornar `None` sem re-raise
  - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 5.1_

  - [ ]* 1.1 Escrever teste de propriedade — Propriedade 1: `_montar_evento_shadow` produz todos os campos obrigatórios
    - **Propriedade 1: `_montar_evento_shadow` produz eventos com todos os campos obrigatórios**
    - Usar `@given` com `id_acao`, `acao`, `label`, `seletor`, `tag`, `valor_input` conforme design
    - `@settings(max_examples=100)`
    - Verificar que `CAMPOS_OBRIGATORIOS.issubset(evento.keys())`
    - **Valida: Requisito 1.8**

  - [ ]* 1.2 Escrever teste de propriedade — Propriedade 2: `_salvar_shadow_jsonl` ordena por `id_acao`
    - **Propriedade 2: `_salvar_shadow_jsonl` ordena eventos por `id_acao` antes de gravar**
    - Usar `@given(st.lists(...))` com `id_acao` em ordem arbitrária, `min_size=1, max_size=50`
    - `@settings(max_examples=100)`
    - Verificar que ids lidos do arquivo estão em ordem crescente
    - **Valida: Requisito 1.5**

  - [ ]* 1.3 Escrever teste de propriedade — Propriedade 3: `_is_noise_event` para breadcrumbs e ícones
    - **Propriedade 3: `_is_noise_event` retorna `True` para breadcrumbs e ícones sem label**
    - Dois `@given`: um para seletores breadcrumb, outro para tags `i`, `svg`, `path` com label vazio
    - `@settings(max_examples=100)`
    - **Valida: Requisito 1.8**

  - [ ]* 1.4 Escrever teste de propriedade — Propriedade 4: vocabulário controlado de `_infer_semantic_action_from_capture`
    - **Propriedade 4: `_infer_semantic_action_from_capture` sempre retorna valor do vocabulário controlado**
    - `@given` com `acao`, `label`, `seletor`, `tag`, `valor_input` arbitrários
    - `@settings(max_examples=100)`
    - Verificar `resultado in {"fill", "search", "confirm", "delete", "save", "open", "navigate", "select", "close"}`
    - **Valida: Requisito 1.8**

- [x] 2. Checkpoint — Verificar `shadow_builder.py` isolado
  - Garantir que `python -c "import shadow_builder"` não levanta exceção
  - Garantir que todos os testes de propriedade da tarefa 1 passam
  - Perguntar ao usuário se há ajustes antes de prosseguir com as refatorações

- [x] 3. Refatorar `capture_dual_output.py` para importar de `shadow_builder`
  - Adicionar bloco de import no topo de `capture_dual_output.py`:
    ```python
    from shadow_builder import (
        utc_now,
        _infer_capture_scope,
        _infer_semantic_action_from_capture,
        _infer_business_entity_from_capture,
        _infer_pattern_from_capture,
        _is_noise_event,
        _montar_evento_shadow,
        _salvar_shadow_jsonl,
    )
    ```
  - Remover as 8 definições locais dessas funções após confirmar que o import funciona
  - Preservar intactos: Playwright, Gemini, OpenAI, Pinecone, `cliques_capturados`, `shadow_capturado`, `_id_acao_global`, `_lock_id`, e toda lógica de captura
  - Verificar que `ROTEIRO_GERADO:` e `SHADOW_GERADO:` continuam sendo emitidos no stdout com comportamento idêntico
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 3.1 Escrever teste unitário — imports de `shadow_builder` em `capture_dual_output`
    - Verificar que as 8 funções são importadas de `shadow_builder` e não definidas localmente
    - Usar `inspect.getmodule()` ou verificar `capture_dual_output.__dict__` vs `shadow_builder.__dict__`
    - _Requisitos: 2.1, 2.2_

- [x] 4. Refatorar `capture_hybrid_shadow.py` — migrar apenas `utc_now`
  - Localizar a definição local de `utc_now` em `capture_hybrid_shadow.py`
  - Substituir por `from shadow_builder import utc_now` e remover a definição local
  - Manter sem alteração: `infer_semantic_action_from_hints`, `infer_pattern_from_hints`, `is_noise_event`, `infer_business_entity_from_hints` (lógica genuinamente diferente — suporte a `tecla`, `selecionar_opcao`, `aria_hint`, `title_hint`, `modal_action`, `tree_item_open`, `search_debounce`, `cliente`, `pedido`)
  - Preservar intacta a integração com Gemini em `analisar_semantica_hibrida`
  - Preservar o comportamento funcional completo de `capturar_hibrido`
  - _Requisitos: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 4.1 Escrever testes unitários para `capture_hybrid_shadow` após refatoração
    - `test_utc_now_importado_de_shadow_builder`: verificar que `utc_now` não está definido localmente no módulo
    - `test_infer_semantic_action_tecla`: `acao == "tecla"` com `Ctrl+S` retorna `"save"`
    - `test_infer_semantic_action_selecionar_opcao`: `acao == "selecionar_opcao"` retorna `"select"`
    - _Requisitos: 3.1, 3.3_

- [x] 5. Corrigir `app.py` — 3 mudanças cirúrgicas + auto-rebuild
  - [x] 5.1 Adicionar `shadow_path: None` ao `estado_servidor`
    - Localizar o dict `estado_servidor` em `app.py`
    - Adicionar o campo `"shadow_path": None` ao dict de inicialização
    - _Requisitos: 4.9_

  - [x] 5.2 Resetar `shadow_path` no início de cada tarefa em `executar_processo_bg`
    - Localizar a chamada `_set_estado(ocupado=True, ...)` no início de `executar_processo_bg`
    - Adicionar `shadow_path=None` aos kwargs dessa chamada
    - _Requisitos: 4.10_

  - [x] 5.3 Monitorar `SHADOW_GERADO:` no loop de stdout de `executar_processo_bg`
    - Localizar o loop de leitura de stdout em `executar_processo_bg`
    - Após o bloco `if "PROGRESSO:" in linha_limpa:`, adicionar:
      ```python
      if linha_limpa.startswith("SHADOW_GERADO:"):
          shadow_path = linha_limpa.split("SHADOW_GERADO:", 1)[1].strip()
          _set_estado(shadow_path=shadow_path)
      ```
    - _Requisitos: 4.5, 4.6, 4.7_

  - [x] 5.4 Expandir condição de auto-rebuild para incluir `capture_dual_output.py`
    - Localizar `if "capture.py" in " ".join(comando):` em `executar_processo_bg`
    - Substituir por:
      ```python
      _cmd_str = " ".join(comando)
      if "capture.py" in _cmd_str or "capture_dual_output.py" in _cmd_str:
      ```
    - _Requisitos: 4.8_

  - [x] 5.5 Adicionar rota `POST /api/gravar-dual`
    - Adicionar após a rota `/api/gravar` existente:
      ```python
      @app.post("/api/gravar-dual")
      async def gravar_aula_dual(req: NovaAulaReq):
          ok = _iniciar_bg(
              [sys.executable, "capture_dual_output.py", req.nome_aula, req.objetivo, "--auto"],
              "🔍 Captura Dual ativa — gerando roteiro + shadow semântico...",
              "🎯 Captura dual concluída. Roteiro e shadow prontos."
          )
          return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
      ```
    - Reutilizar `NovaAulaReq`, `_iniciar_bg`, `JSONResponse` — zero novas dependências
    - _Requisitos: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.6 Escrever testes unitários para as mudanças em `app.py`
    - `test_estado_inicial_tem_shadow_path_none`: verificar `estado_servidor["shadow_path"] is None`
    - `test_gravar_dual_sistema_ocupado`: POST `/api/gravar-dual` com estado ocupado retorna HTTP 400 com `{"erro": "Sistema ocupado"}`
    - `test_gravar_dual_sistema_livre`: POST `/api/gravar-dual` com estado livre retorna `{"status": "iniciado"}`
    - _Requisitos: 4.1, 4.2, 4.9_

  - [ ]* 5.7 Escrever teste de propriedade — Propriedade 5: `shadow_path` é `None` no início de cada tarefa
    - **Propriedade 5: `shadow_path` no estado é sempre `None` no início de uma nova tarefa**
    - Usar `monkeypatch` para capturar o estado no momento em que `Popen` seria chamado
    - Forçar `shadow_path` para valor não-`None` antes de chamar `executar_processo_bg`
    - Verificar que o valor capturado é `None`
    - **Valida: Requisito 4.10**

  - [ ]* 5.8 Escrever teste de propriedade — Propriedade 6: `SHADOW_GERADO:` após `ROTEIRO_GERADO:` no stdout
    - **Propriedade 6: `SHADOW_GERADO:` é emitido após `ROTEIRO_GERADO:` na sequência de stdout**
    - Simular lista de linhas de stdout com ambas as linhas presentes
    - Verificar que `idx_shadow > idx_roteiro`
    - **Valida: Requisito 5.2**

- [x] 6. Checkpoint final — Garantir que todos os testes passam
  - Garantir que todos os testes de propriedade e unitários passam
  - Verificar que `python -c "import shadow_builder; import capture_dual_output"` não levanta exceção
  - Verificar que `app.py` inicializa sem erro e `estado_servidor["shadow_path"]` é `None`
  - Perguntar ao usuário se há ajustes antes de encerrar

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- A ordem das tarefas é obrigatória: `shadow_builder` deve existir antes de qualquer refatoração
- Cada tarefa referencia requisitos específicos para rastreabilidade
- Os testes de propriedade usam `hypothesis` (já presente no projeto via `.hypothesis/`)
- Configuração mínima: `@settings(max_examples=100)` por propriedade
