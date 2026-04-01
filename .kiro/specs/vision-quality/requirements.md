# Documento de Requisitos

## Introdução

Esta especificação cobre a **Fase 3 — Melhoria de Vision e Seletores** do Senior Training OS.

As Fases 1 (`legacy-stabilization`) e 2 (`semantic-sidecar`) estabilizaram o pipeline e extraíram a camada semântica. A Fase 3 resolve três problemas independentes de qualidade e resiliência que afetam o desempenho do pipeline em produção:

1. **Screenshots base64 embutidos no roteiro** — roteiros com 30 ações podem ter 10MB+ de base64 inline, degradando leitura, geração de IA e processamento downstream.
2. **Validator fora de contexto de navegação** — o `validator.py` testa seletores na tela inicial, gerando falsos positivos para seletores que só existem após navegar para um módulo.
3. **Portão de qualidade inadequado para roteiros gerados por IA** — o `validar_roteiro` existente reprova todos os roteiros gerados por IA porque verifica `seletor_hint`, que nunca está presente em roteiros de IA.

**Restrições absolutas:**
- O schema do roteiro JSON não pode ser alterado (campos existentes permanecem).
- Roteiros existentes em `roteiros_salvos/` devem continuar funcionando sem modificação.
- O campo `screenshot_referencia` pode ser path string, base64 string ou None — todos os formatos são válidos.
- O fluxo legado de produção (`capture.py` + `/api/gravar`) deve ser preservado intacto.
- Nenhuma nova dependência de biblioteca deve ser introduzida.

---

## Glossário

- **Sistema**: conjunto de módulos do Senior Training OS.
- **Roteiro**: artefato JSON central que representa um fluxo de treinamento estruturado.
- **Capture_Module**: módulo `capture.py`, responsável pela captura de interações e geração do roteiro.
- **Vision_Engine**: módulo `vision_engine.py`, responsável pela localização resiliente de elementos no browser durante a execução.
- **Validator**: módulo `validator.py`, responsável pela validação de seletores do roteiro em ambiente real.
- **Generator_Engine**: módulo `generator_engine.py`, responsável pela geração de roteiros via IA.
- **Utils**: módulo `utils.py`, fonte canônica de utilitários compartilhados.
- **Lego_Builder**: módulo `lego_builder.py`, responsável por construir a `biblioteca_acoes.json` a partir dos roteiros salvos.
- **screenshot_referencia**: campo em `elemento_alvo` de cada ação técnica capturada. Pode conter: (a) string base64 JPEG, (b) path relativo para arquivo em disco, ou (c) None/ausente.
- **screenshot_path**: path relativo no formato `audios_gerados/{nome_aula}/screenshots/acao_{id}.jpg` onde o screenshot é externalizado.
- **validar_roteiro**: função em `utils.py` que aplica o portão de qualidade para roteiros capturados (verifica `seletor_hint` e `confianca_captura`).
- **validar_roteiro_ia**: nova função em `utils.py` que aplica o portão de qualidade específico para roteiros gerados por IA (verifica `ancora` e `elemento_alvo`).
- **acao_navegacao**: ação técnica cujo propósito é navegar para um contexto diferente (clique em menu, breadcrumb, aba de módulo). Identificada por heurística de label/seletor.
- **acao_validavel**: ação técnica que representa uma interação com um elemento de formulário ou botão de ação, cujo seletor deve ser verificado no contexto correto.
- **modo_dry_run**: modo de execução do Validator que verifica visibilidade dos elementos sem executar cliques reais.
- **Brain**: banco SQLite `brain.db` que armazena memória semântica de seletores para auto-cura.

---

## Requisitos

### Requisito 1: Externalização de Screenshots Base64 para Disco

**User Story:** Como operador do pipeline, quero que os screenshots de referência sejam salvos em disco em vez de embutidos como base64 no roteiro JSON, para que roteiros com muitas ações não degradem a leitura, a geração de IA e o processamento downstream.

#### Critérios de Aceitação

1. WHEN `on_capturar_elemento` salva uma ação no `cliques_capturados`, THE `Capture_Module` SHALL salvar o screenshot JPEG em `audios_gerados/{nome_aula}/screenshots/acao_{id_acao}.jpg` e armazenar o path relativo no campo `screenshot_referencia` em vez do base64.
2. WHEN o diretório `audios_gerados/{nome_aula}/screenshots/` não existir, THE `Capture_Module` SHALL criá-lo antes de salvar o arquivo.
3. IF a escrita do arquivo de screenshot falhar, THEN THE `Capture_Module` SHALL armazenar o base64 diretamente no campo `screenshot_referencia` como fallback, sem interromper a captura.
4. THE `Capture_Module` SHALL passar o `nome_aula` para `on_capturar_elemento` para que o path de destino possa ser construído corretamente.
5. THE `Lego_Builder` SHALL continuar removendo `screenshot_referencia` via `pop` ao construir a biblioteca, independentemente de o valor ser path ou base64.
6. FOR ALL roteiros existentes em `roteiros_salvos/` com `screenshot_referencia` contendo base64 inline, THE `Vision_Engine` SHALL continuar funcionando sem alteração de comportamento.
7. FOR ALL roteiros novos com `screenshot_referencia` contendo um path relativo, THE `Vision_Engine` SHALL ler o arquivo do disco e usar os bytes como referência para o Gemini Vision.
8. IF o arquivo referenciado pelo path não existir em disco, THEN THE `Vision_Engine` SHALL prosseguir sem a imagem de referência, sem lançar exceção.
9. THE `Vision_Engine` SHALL detectar automaticamente se `screenshot_referencia` é base64 ou path, sem necessidade de campo adicional no roteiro.

---

### Requisito 2: Validator com Navegação Contextual

**User Story:** Como operador de qualidade, quero que o validator execute as ações de navegação do roteiro antes de validar os seletores dependentes, para que seletores de módulos específicos não gerem falsos positivos por serem testados fora de contexto.

#### Critérios de Aceitação

1. WHEN o Validator processa um roteiro, THE `Validator` SHALL percorrer os passos em ordem sequencial, executando ações de navegação antes de validar seletores do mesmo passo ou de passos subsequentes.
2. THE `Validator` SHALL classificar uma ação técnica como `acao_navegacao` quando o `label_curto` ou `seletor_hint` indicar interação com menu principal, breadcrumb, aba de módulo ou link de navegação entre telas.
3. THE `Validator` SHALL classificar uma ação técnica como `acao_validavel` quando não for classificada como `acao_navegacao` e possuir `seletor_hint` preenchido.
4. WHEN o Validator encontra uma `acao_navegacao`, THE `Validator` SHALL executar o clique real no elemento e aguardar estabilidade da página antes de continuar.
5. WHEN o Validator encontra uma `acao_validavel` em modo padrão, THE `Validator` SHALL verificar visibilidade e estado habilitado do elemento sem executar o clique.
6. WHEN o Validator é executado com o argumento `--dry-run`, THE `Validator` SHALL verificar apenas visibilidade dos elementos sem executar nenhum clique, incluindo ações de navegação.
7. IF uma `acao_navegacao` falhar durante a execução, THEN THE `Validator` SHALL emitir aviso e continuar para o próximo passo, sem interromper a validação completa.
8. IF uma `acao_validavel` não for encontrada, THEN THE `Validator` SHALL registrar a falha com o id do passo, o label e o seletor, e continuar para a próxima ação.
9. THE `Validator` SHALL aceitar roteiros sem o campo `tipo_passo` ou sem campos de classificação de navegação, usando heurística de label/seletor como critério de classificação.
10. WHEN a validação é concluída, THE `Validator` SHALL exibir um resumo com total de ações validadas, total de falhas e lista de seletores com problema.

---

### Requisito 3: Portão de Qualidade Semântico para Roteiros Gerados por IA

**User Story:** Como operador do pipeline de geração, quero que roteiros gerados por IA sejam avaliados por critérios adequados ao seu formato, para que o portão de qualidade produza avisos úteis em vez de reprovar todos os roteiros por ausência de `seletor_hint`.

#### Critérios de Aceitação

1. THE `Utils` SHALL expor uma função `validar_roteiro_ia(roteiro: dict) -> tuple[bool, str]` com critérios específicos para roteiros gerados por IA.
2. THE `validar_roteiro_ia` em `Utils` SHALL reprovar roteiros com menos de 2 passos, retornando `False` e mensagem descritiva.
3. THE `validar_roteiro_ia` em `Utils` SHALL reprovar roteiros onde nenhum passo possui `ancora` não vazia no campo `pedagogia`, retornando `False` e mensagem descritiva.
4. THE `validar_roteiro_ia` em `Utils` SHALL reprovar roteiros onde nenhuma ação técnica possui `elemento_alvo` não vazio (excluindo ações `concluir_video`), retornando `False` e mensagem descritiva.
5. THE `validar_roteiro_ia` em `Utils` SHALL reprovar roteiros onde algum passo não-conclusão possui lista `acoes_tecnicas` completamente vazia, retornando `False` e mensagem descritiva.
6. THE `validar_roteiro_ia` em `Utils` SHALL ignorar o passo com `is_conclusao: true` nos critérios dos itens 4 e 5.
7. WHEN `gerar_roteiro_ia_sync` gera um roteiro com `gerado_por_ia: true`, THE `Generator_Engine` SHALL chamar `validar_roteiro_ia` em vez de `validar_roteiro` para o portão de qualidade semântico.
8. IF `validar_roteiro_ia` reprovar o roteiro gerado, THEN THE `Generator_Engine` SHALL emitir `logger.warning` com o motivo da reprovação, sem interromper o retorno ao chamador.
9. THE `Generator_Engine` SHALL persistir o roteiro em `roteiros_salvos/` independentemente do resultado de `validar_roteiro_ia`, para permitir revisão manual.
10. THE `validar_roteiro` existente em `Utils` SHALL permanecer inalterado e continuar sendo usado para roteiros capturados (com `seletor_hint`).
11. FOR ALL roteiros capturados que passavam em `validar_roteiro` antes desta fase, THE `validar_roteiro` SHALL continuar retornando `True` com os mesmos critérios.
