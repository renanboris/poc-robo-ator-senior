# Requirements Document

## Introduction

Esta feature integra e estabiliza dois novos builders no Senior Training OS:
`pdf_builder_playbook_v3.py` e `scorm_builder_playbook_v2.py`. Esses builders
evoluem a camada de entrega do produto — PDF e SCORM — para compartilhar uma
identidade visual e pedagógica unificada, tratando cada passo do roteiro como
uma "cena" editorial em vez de um export técnico.

O PDF passa a funcionar como um digital playbook premium (capa editorial,
mapa de cenas, spotlight cinematográfico nas screenshots, cards de contexto e
fechamento com sensação de "habilidade desbloqueada"). O SCORM passa a operar
como uma prática guiada com painel narrativo, badge de cena, suporte a tooltip
e alerta por cena, e feedback de erro orientador em vez de punitivo.

O roteiro JSON permanece o contrato central. Nenhuma mudança estrutural no
roteiro é introduzida por esta feature. O objetivo é substituir os builders
antigos preservando a API pública esperada por `app.py` e garantindo
compatibilidade total com roteiros existentes.

---

## Glossary

- **Roteiro**: artefato JSON central do Training OS. Contém `metadata`,
  `configuracao_gravacao` e `passos`. É o contrato entre captura, geração e
  entrega.
- **PDF_Builder**: módulo responsável por gerar o playbook PDF a partir de um
  roteiro. Versão nova: `pdf_builder_playbook_v3.py`.
- **SCORM_Builder**: módulo responsável por gerar o pacote SCORM a partir de um
  roteiro. Versão nova: `scorm_builder_playbook_v2.py`.
- **Pipeline**: sequência capture → generator → executor → PDF/SCORM/video.
- **Cena**: representação de um passo do roteiro no contexto editorial dos novos
  builders (equivale a `passo` no roteiro).
- **Spotlight**: efeito visual cinematográfico aplicado sobre a screenshot para
  destacar a área de interação, substituindo o retângulo vermelho simples.
- **Painel Narrativo**: painel lateral/recolhível do SCORM que exibe contexto
  pedagógico (âncora, tooltip, alerta) por cena.
- **limpar_nome**: função canônica de sanitização de nomes de arquivo, definida
  em `utils.py`. Única fonte de verdade para geração de nomes de artefatos.
- **base**: resultado de `limpar_nome(id_treinamento)`, usado como prefixo dos
  artefatos gerados (`{base}_Playbook.pdf`, `{base}_SCORM.zip`).
- **app.py**: entrypoint FastAPI. Invoca os builders via subprocess e espera
  artefatos nos caminhos `documentacao_pdf/{base}_Playbook.pdf` e
  `scorm_exports/{base}_SCORM.zip`.
- **_set_estado**: função de app.py que gerencia o estado do servidor. Não deve
  ser contornada.
- **SCORM 1.2**: padrão de empacotamento de conteúdo e-learning suportado pelo
  LMS alvo.

---

## Requirements

### Requirement 1: Integração dos novos builders ao pipeline

**User Story:** Como desenvolvedor do Training OS, quero que os novos builders
sejam invocáveis pelo mesmo contrato de linha de comando dos builders atuais,
para que `app.py` continue funcionando sem alterações.

#### Acceptance Criteria

1. WHEN `app.py` invoca `pdf_builder.py <caminho_roteiro>` via subprocess, THE
   PDF_Builder SHALL gerar o arquivo `documentacao_pdf/{base}_Playbook.pdf` e
   encerrar com código de saída 0.

2. WHEN `app.py` invoca `scorm_builder.py <caminho_roteiro>` via subprocess, THE
   SCORM_Builder SHALL gerar o arquivo `scorm_exports/{base}_SCORM.zip` e
   encerrar com código de saída 0.

3. THE PDF_Builder SHALL usar `limpar_nome` importada de `utils.py` para derivar
   o nome do arquivo de saída, sem definir cópia local da função.

4. THE SCORM_Builder SHALL usar `limpar_nome` importada de `utils.py` para
   derivar o nome do arquivo de saída, sem definir cópia local da função.

5. WHEN o roteiro contém `metadata.id_treinamento`, THE PDF_Builder SHALL usar
   esse campo como base do nome do arquivo de saída.

6. WHEN o roteiro contém `metadata.id_treinamento`, THE SCORM_Builder SHALL usar
   esse campo como base do nome do arquivo de saída.

---

### Requirement 2: Compatibilidade com roteiros existentes

**User Story:** Como operador do Training OS, quero que os novos builders
processem roteiros antigos sem erros, para que nenhum treinamento já mapeado
quebre após a troca dos builders.

#### Acceptance Criteria

1. WHEN um roteiro válido não contém o campo `tooltip_dap` em nenhum passo, THE
   PDF_Builder SHALL gerar o playbook sem lançar exceção, omitindo o chip de
   tooltip.

2. WHEN um roteiro válido não contém o campo `alerta_instrutor` em nenhum passo,
   THE PDF_Builder SHALL gerar o playbook sem lançar exceção, omitindo o bloco
   de alerta.

3. WHEN um roteiro válido não contém o campo `peso_narrativo` em um passo, THE
   PDF_Builder SHALL tratar o valor ausente como `2` (Guia) sem lançar exceção.

4. WHEN um roteiro válido não contém o campo `tooltip_dap` em nenhum passo, THE
   SCORM_Builder SHALL gerar o pacote sem lançar exceção, omitindo o tooltip por
   cena.

5. WHEN um roteiro válido não contém o campo `alerta_instrutor` em nenhum passo,
   THE SCORM_Builder SHALL gerar o pacote sem lançar exceção, omitindo o alerta
   por cena.

6. WHEN um passo do roteiro não contém `screenshot_referencia` em nenhuma ação
   técnica, THE PDF_Builder SHALL renderizar um placeholder visual no lugar da
   screenshot sem lançar exceção.

7. WHEN um passo do roteiro não contém `screenshot_referencia` em nenhuma ação
   técnica, THE SCORM_Builder SHALL exibir a cena sem imagem de fundo sem lançar
   exceção.

8. FOR ALL roteiros válidos segundo `validar_roteiro` de `utils.py`, THE
   PDF_Builder SHALL produzir um arquivo PDF sem lançar exceção (propriedade de
   round-trip: roteiro válido → artefato gerado).

9. FOR ALL roteiros válidos segundo `validar_roteiro` de `utils.py`, THE
   SCORM_Builder SHALL produzir um arquivo ZIP sem lançar exceção (propriedade
   de round-trip: roteiro válido → artefato gerado).

---

### Requirement 3: Integridade dos artefatos gerados

**User Story:** Como instrutor, quero que o PDF e o SCORM gerados sejam
arquivos válidos e abríveis, para que eu possa distribuí-los sem retrabalho.

#### Acceptance Criteria

1. WHEN o PDF_Builder conclui a geração, THE PDF_Builder SHALL produzir um
   arquivo cujos primeiros bytes correspondem à assinatura `%PDF` (arquivo PDF
   válido).

2. WHEN o SCORM_Builder conclui a geração, THE SCORM_Builder SHALL produzir um
   arquivo ZIP que contém `imsmanifest.xml` e `index.html` na raiz do pacote.

3. WHEN o SCORM_Builder conclui a geração, THE SCORM_Builder SHALL incluir no
   `imsmanifest.xml` o título do treinamento extraído de
   `metadata.nome_aula` do roteiro.

4. WHEN o PDF_Builder conclui a geração com um roteiro de N passos regulares
   (não-conclusão), THE PDF_Builder SHALL gerar um PDF com pelo menos N + 2
   páginas (capa + mapa + cenas).

5. WHEN o SCORM_Builder conclui a geração, THE SCORM_Builder SHALL incluir no
   `index.html` o array de slides serializado como JSON válido.

---

### Requirement 4: Novo conceito visual do PDF — Playbook Premium

**User Story:** Como designer instrucional, quero que o PDF gerado tenha
identidade visual editorial premium, para que o material entregue ao aprendiz
reflita a qualidade do produto Senior.

#### Acceptance Criteria

1. THE PDF_Builder SHALL gerar uma página de capa com título do treinamento,
   módulo, nível, contagem de cenas e data de geração.

2. THE PDF_Builder SHALL gerar uma página de mapa (TOC) listando todos os passos
   do roteiro com número, âncora pedagógica e tipo de passo.

3. WHEN uma ação técnica do passo contém `screenshot_referencia` e
   `coordenadas_relativas`, THE PDF_Builder SHALL aplicar efeito de spotlight
   cinematográfico na imagem, escurecendo a área fora da região de interesse.

4. THE PDF_Builder SHALL renderizar cada passo como uma cena com painel esquerdo
   (screenshot com spotlight) e painel direito (contexto pedagógico: âncora,
   tooltip, alerta, lista de ações).

5. WHERE `peso_narrativo` do passo for `3`, THE PDF_Builder SHALL renderizar a
   âncora pedagógica com fonte em negrito-itálico e tamanho maior que os demais
   pesos.

6. THE PDF_Builder SHALL gerar uma página de fechamento com título "Habilidade
   desbloqueada", cards de métricas (cenas, ações, status) e lista de próximos
   movimentos.

7. THE PDF_Builder SHALL tentar registrar fontes customizadas do diretório
   `assets/fonts` e, IF as fontes não forem encontradas, THE PDF_Builder SHALL
   usar Helvetica como fallback sem lançar exceção.

---

### Requirement 5: Novo conceito visual do SCORM — Prática Guiada

**User Story:** Como aprendiz, quero que o simulador SCORM tenha uma experiência
de prática guiada com contexto pedagógico por cena, para que eu entenda o
porquê de cada ação e não apenas onde clicar.

#### Acceptance Criteria

1. THE SCORM_Builder SHALL gerar um `index.html` com painel narrativo que exibe
   a âncora pedagógica (`ancora`) de cada cena antes das interações.

2. WHEN um slide do tipo `ancora` é exibido, THE SCORM_Builder SHALL mostrar o
   texto da âncora e um botão de avanço, sem exigir interação com a tela.

3. WHEN um slide do tipo `interacao` é exibido, THE SCORM_Builder SHALL aplicar
   spotlight sobre a área de interação usando as coordenadas relativas do
   elemento alvo.

4. WHEN o campo `tooltip` de um slide está preenchido, THE SCORM_Builder SHALL
   exibir o tooltip contextual associado à cena.

5. WHEN o campo `alerta` de um slide está preenchido, THE SCORM_Builder SHALL
   exibir o alerta de instrutor associado à cena.

6. WHEN o aprendiz clica em área incorreta durante uma interação, THE
   SCORM_Builder SHALL exibir mensagem orientadora (não punitiva) sem encerrar
   a cena.

7. THE SCORM_Builder SHALL incluir badge de cena identificando o número e tipo
   do passo (`scene_id`, `scene_kind`) no painel narrativo.

8. THE SCORM_Builder SHALL gerar tela de abertura com título do treinamento e
   botão de início, e tela de encerramento com percentual de acertos e botão de
   finalização SCORM.

9. WHEN o aprendiz conclui todas as interações, THE SCORM_Builder SHALL reportar
   ao LMS via API SCORM 1.2 o status `completed` e o score calculado como
   percentual de acertos sobre total de interações.

---

### Requirement 6: Preservação do pipeline e ausência de regressão

**User Story:** Como operador do Training OS, quero que a troca dos builders não
quebre nenhuma outra parte do pipeline, para que vídeo, captura e DAP continuem
funcionando normalmente.

#### Acceptance Criteria

1. THE Pipeline SHALL continuar gerando vídeos MP4 sem alteração após a
   substituição dos builders.

2. THE Pipeline SHALL continuar executando capturas via `capture.py` sem
   alteração após a substituição dos builders.

3. WHEN `app.py` verifica a existência de artefatos para exibir badges no
   dashboard (`tem_pdf`, `tem_scorm`), THE PDF_Builder e THE SCORM_Builder SHALL
   gerar os artefatos nos caminhos e com os nomes exatos esperados por `app.py`.

4. THE PDF_Builder SHALL encerrar o processo com código de saída diferente de 0
   e imprimir mensagem de erro descritiva no stdout WHEN o arquivo de roteiro
   informado não existir.

5. THE SCORM_Builder SHALL encerrar o processo com código de saída diferente de
   0 e imprimir mensagem de erro descritiva no stdout WHEN o arquivo de roteiro
   informado não existir.

6. IF a geração do PDF falhar por erro interno, THEN THE PDF_Builder SHALL
   imprimir a causa do erro no stdout para que `app.py` possa capturá-la e
   exibi-la no dashboard via `_set_estado`.

7. IF a geração do SCORM falhar por erro interno, THEN THE SCORM_Builder SHALL
   imprimir a causa do erro no stdout para que `app.py` possa capturá-la e
   exibi-la no dashboard via `_set_estado`.
