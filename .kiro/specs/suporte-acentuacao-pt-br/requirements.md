# Documento de Requisitos: Suporte à Acentuação pt-BR

## Introdução

O Senior Training OS é uma plataforma de autoria de treinamentos que captura workflows de especialistas no ERP Senior X e gera múltiplos artefatos de treinamento (vídeos MP4, pacotes SCORM, PDFs, suporte DAP). Atualmente, o sistema apresenta falhas pontuais ao processar caracteres acentuados do português brasileiro em diferentes etapas do pipeline.

Este documento especifica os requisitos para garantir suporte completo e robusto à acentuação pt-BR em todos os módulos do sistema, eliminando falhas de digitação, renderização, serialização e armazenamento de caracteres especiais como á, é, í, ó, ú, â, ê, ô, ã, õ, ç e suas variantes maiúsculas.

## Glossário

- **Sistema**: Senior Training OS — plataforma completa de captura, geração e renderização de treinamentos
- **Pipeline**: Sequência de estágios do sistema (captura → geração → execução → renderização → exportação)
- **Roteiro**: Artefato JSON central que representa o workflow estruturado, usado por todos os módulos
- **Captura**: Módulo `capture.py` que registra interações do usuário no Senior X via Playwright
- **Gerador**: Módulo `generator_engine.py` que transforma capturas em roteiros estruturados usando IA
- **Executor**: Módulo `main.py` que reproduz roteiros para gravação de vídeo
- **Vision_Engine**: Módulo de localização resiliente de elementos UI com fallback visual
- **Renderizador_Video**: Componente de `main.py` que gera MP4 final com narração e legendas
- **Renderizador_PDF**: Módulo `pdf_builder.py` que gera playbooks em PDF
- **Renderizador_SCORM**: Módulo `scorm_builder.py` que gera pacotes SCORM interativos
- **TTS**: Text-to-Speech — edge-tts para narração de áudio
- **Caracteres_Acentuados_ptBR**: Conjunto {á, à, â, ã, é, ê, í, ó, ô, õ, ú, ç, Á, À, Â, Ã, É, Ê, Í, Ó, Ô, Õ, Ú, Ç}
- **Sanitizador**: Função `limpar_nome()` em `utils.py` que converte strings para nomes de arquivo seguros
- **Brain**: Banco SQLite (`brain.db`) que armazena memória semântica de seletores para self-healing

## Requisitos

### Requisito 1: Digitação de Caracteres Acentuados no Playwright

**User Story:** Como robô de execução, eu quero digitar corretamente caracteres acentuados em campos de texto do Senior X, para que workflows com nomes como "Padrão", "Criação" e "Relatório" sejam executados sem falhas.

#### Acceptance Criteria

1. WHEN O Executor digita texto contendo caracteres acentuados pt-BR em um campo de entrada, THE Vision_Engine SHALL usar `page.keyboard.type()` com encoding UTF-8
2. WHEN O Executor digita texto contendo caracteres acentuados pt-BR em um campo de entrada, THE Sistema SHALL preservar todos os caracteres acentuados sem substituição ou corrupção
3. THE Executor SHALL suportar digitação de todos os caracteres do conjunto Caracteres_Acentuados_ptBR em campos `<input>`, `<textarea>` e elementos `contenteditable`
4. WHEN O Executor digita "Padrão" em um campo de texto, THE Sistema SHALL produzir exatamente "Padrão" no campo (não "Padro", "Padr?o" ou "PadrÃ£o")
5. THE Executor SHALL aplicar a mesma estratégia de digitação Unicode tanto em `vision_engine.py` quanto em `main.py` (DRY — Don't Repeat Yourself)

### Requisito 2: Captura de Texto Acentuado via Playwright

**User Story:** Como módulo de captura, eu quero extrair corretamente labels e textos acentuados de elementos UI, para que o roteiro gerado preserve a nomenclatura original do Senior X.

#### Acceptance Criteria

1. WHEN A Captura extrai `innerText` ou `textContent` de um elemento contendo caracteres acentuados, THE Sistema SHALL preservar o encoding UTF-8 original
2. WHEN A Captura serializa dados de elementos para JSON, THE Sistema SHALL usar `ensure_ascii=False` para preservar caracteres Unicode
3. THE Captura SHALL armazenar labels como "Configuração", "Ações" e "Relatórios" sem corrupção no campo `label_curto` do roteiro
4. WHEN A Captura extrai atributos HTML (`aria-label`, `placeholder`, `title`) contendo acentos, THE Sistema SHALL preservar os caracteres originais
5. THE Captura SHALL validar que screenshots de elementos com labels acentuados sejam corretamente associados aos metadados textuais

### Requisito 3: Geração de Roteiros com IA (Gemini)

**User Story:** Como gerador de roteiros, eu quero que a IA processe e gere textos pedagógicos em português correto, para que âncoras e micro-narrações contenham acentuação adequada.

#### Acceptance Criteria

1. WHEN O Gerador envia prompts ao Gemini contendo caracteres acentuados, THE Sistema SHALL usar encoding UTF-8 na requisição HTTP
2. WHEN O Gemini retorna JSON com campos textuais acentuados (`ancora`, `micro_narracao`, `tooltip_dap`), THE Sistema SHALL preservar os caracteres originais ao parsear a resposta
3. THE Gerador SHALL validar que textos gerados pela IA contenham acentuação correta segundo as regras ortográficas do português brasileiro
4. WHEN O Gerador salva o roteiro em disco, THE Sistema SHALL usar `encoding="utf-8"` e `ensure_ascii=False` no `json.dump()`
5. THE Gerador SHALL suportar contexto RAG (Pinecone) contendo documentação em português com acentuação, sem corrupção na recuperação

### Requisito 4: Armazenamento de Roteiros em JSON

**User Story:** Como sistema de persistência, eu quero armazenar roteiros com caracteres acentuados de forma atômica e segura, para que leituras posteriores recuperem os dados originais sem corrupção.

#### Acceptance Criteria

1. THE Sistema SHALL usar `encoding="utf-8"` em todas as operações de leitura e escrita de arquivos JSON
2. THE Sistema SHALL usar `ensure_ascii=False` em todas as chamadas `json.dump()` para preservar caracteres Unicode nativos
3. WHEN O Sistema salva um roteiro contendo "Criação de Relatório", THE arquivo JSON resultante SHALL conter a string literal "Criação de Relatório" (não escape Unicode `\u00e7`)
4. THE Sistema SHALL usar `safe_write_json()` de `utils.py` para escrita atômica, garantindo que falhas não corrompam arquivos com caracteres acentuados
5. THE Sistema SHALL validar integridade de roteiros após escrita, verificando que campos textuais acentuados sejam recuperáveis via `json.load()`

### Requisito 5: Geração de Áudio com edge-tts

**User Story:** Como gerador de narração, eu quero que o edge-tts pronuncie corretamente palavras acentuadas, para que o áudio final tenha prosódia natural em português brasileiro.

#### Acceptance Criteria

1. WHEN O Sistema gera áudio para texto contendo caracteres acentuados, THE edge-tts SHALL receber a string em encoding UTF-8
2. THE Sistema SHALL usar a voz `pt-BR-FranciscaNeural` como padrão para garantir pronúncia correta de acentos
3. WHEN O Sistema gera áudio para "Configuração de Relatórios", THE edge-tts SHALL produzir pronúncia correta de "ção" e "tórios"
4. THE Sistema SHALL aplicar correções de pronúncia (regex) ANTES de enviar ao TTS, preservando caracteres acentuados no texto original
5. THE Sistema SHALL salvar arquivos MP3 com nomes sanitizados (via `limpar_nome()`), mas preservar metadados textuais acentuados no manifesto JSON

### Requisito 6: Renderização de Vídeo com moviepy

**User Story:** Como renderizador de vídeo, eu quero gerar legendas SRT com caracteres acentuados, para que o vídeo final exiba corretamente textos em português.

#### Acceptance Criteria

1. WHEN O Sistema gera arquivo SRT, THE Sistema SHALL usar `encoding="utf-8"` na escrita do arquivo
2. THE Sistema SHALL preservar caracteres acentuados em todas as linhas de legenda do arquivo SRT
3. WHEN O Sistema renderiza vídeo MP4 com legendas contendo "Ações", THE arquivo SRT SHALL conter a string literal "Ações" (não "A��es" ou "Acoes")
4. THE Sistema SHALL validar que o codec de vídeo (libx264) e o container MP4 suportem metadados UTF-8 para legendas
5. THE Sistema SHALL testar renderização de vídeo com timeline contendo pelo menos 5 legendas acentuadas diferentes

### Requisito 7: Geração de PDF com ReportLab

**User Story:** Como gerador de playbooks, eu quero renderizar textos acentuados em PDF sem substituição de caracteres, para que documentos impressos sejam legíveis em português correto.

#### Acceptance Criteria

1. THE Sistema SHALL registrar fontes TrueType (Inter/Geist) que suportem o conjunto completo de caracteres acentuados pt-BR
2. WHEN O Sistema renderiza texto acentuado em PDF, THE ReportLab SHALL usar encoding UTF-8 e fontes com suporte Unicode
3. WHEN O Sistema gera PDF contendo "Configuração", "Ações" e "Relatórios", THE PDF resultante SHALL exibir todos os caracteres corretamente (não "Configura��o")
4. THE Sistema SHALL validar que fallback para Helvetica (quando fontes customizadas ausentes) preserve caracteres acentuados
5. THE Sistema SHALL testar geração de PDF com pelo menos 10 ocorrências de caracteres acentuados diferentes em títulos, corpo e tooltips

### Requisito 8: Geração de SCORM com HTML/JavaScript

**User Story:** Como gerador de pacotes SCORM, eu quero que o player HTML exiba corretamente textos acentuados, para que alunos vejam instruções em português correto.

#### Acceptance Criteria

1. WHEN O Sistema gera `index.html` do SCORM, THE Sistema SHALL declarar `<meta charset="UTF-8">` no `<head>`
2. WHEN O Sistema injeta JSON de slides no HTML, THE Sistema SHALL usar `json.dumps(..., ensure_ascii=False)` para preservar caracteres Unicode
3. WHEN O Sistema escreve `index.html` em disco, THE Sistema SHALL usar `encoding="utf-8"` no `open()`
4. THE Sistema SHALL validar que textos acentuados em `ancora`, `micro_narracao` e `tooltip` sejam renderizados corretamente no navegador
5. THE Sistema SHALL testar SCORM em navegadores Chrome, Firefox e Edge, validando exibição correta de pelo menos 5 textos acentuados diferentes

### Requisito 9: Sanitização de Nomes de Arquivo

**User Story:** Como utilitário de sanitização, eu quero converter caracteres acentuados para ASCII seguro em nomes de arquivo, para que o sistema funcione em Windows, macOS e Linux sem erros de filesystem.

#### Acceptance Criteria

1. THE Sistema SHALL usar `limpar_nome()` de `utils.py` como única fonte de verdade para sanitização de nomes de arquivo
2. WHEN `limpar_nome()` recebe "Criação de Pasta", THE função SHALL retornar "Criacao_de_Pasta" (normalização NFKD + remoção de acentos)
3. THE Sistema SHALL aplicar `limpar_nome()` em TODOS os pontos onde strings do usuário são usadas como nomes de arquivo ou pasta
4. THE Sistema SHALL preservar caracteres acentuados em metadados JSON (campo `nome_aula`), aplicando sanitização APENAS em caminhos de filesystem
5. THE Sistema SHALL validar que `limpar_nome()` produza nomes compatíveis com Windows (sem `<>:"/\|?*`), macOS (sem `:`) e Linux (sem `/`)

### Requisito 10: Armazenamento no Brain (SQLite)

**User Story:** Como sistema de memória semântica, eu quero armazenar intenções e seletores com caracteres acentuados, para que o self-healing funcione com workflows em português.

#### Acceptance Criteria

1. THE Sistema SHALL criar banco SQLite com encoding UTF-8 (padrão do Python 3)
2. WHEN O Brain armazena intenção "Clicar em Configurações", THE Sistema SHALL preservar o caractere "ç" na coluna `intencao`
3. WHEN O Brain recupera memória semântica, THE Sistema SHALL retornar strings com caracteres acentuados originais
4. THE Sistema SHALL validar que queries SQL com `LIKE` funcionem corretamente com caracteres acentuados (ex: `WHERE intencao LIKE '%Configuração%'`)
5. THE Sistema SHALL testar ciclo completo de escrita e leitura no Brain com pelo menos 5 intenções contendo caracteres acentuados diferentes

### Requisito 11: Interface Web (Jinja2 Templates)

**User Story:** Como interface web, eu quero exibir nomes de treinamentos e metadados acentuados corretamente, para que usuários vejam informações em português correto no dashboard.

#### Acceptance Criteria

1. WHEN O Sistema renderiza templates Jinja2, THE FastAPI SHALL declarar `charset=utf-8` no Content-Type HTTP
2. THE Sistema SHALL declarar `<meta charset="UTF-8">` em todos os templates HTML
3. WHEN O Sistema exibe lista de roteiros no dashboard, THE interface SHALL renderizar nomes como "Configuração de Relatórios" sem corrupção
4. THE Sistema SHALL validar que dados JSON retornados por APIs REST contenham `Content-Type: application/json; charset=utf-8`
5. THE Sistema SHALL testar renderização de pelo menos 3 páginas diferentes (dashboard, editor, visualizador) com textos acentuados

### Requisito 12: Validação de Roteiros

**User Story:** Como validador de qualidade, eu quero verificar que roteiros contenham textos acentuados válidos, para que erros de encoding sejam detectados antes da renderização.

#### Acceptance Criteria

1. WHEN O Sistema valida um roteiro, THE validador SHALL verificar que campos textuais não contenham sequências de escape Unicode malformadas (ex: `\ufffd`)
2. WHEN O Sistema valida um roteiro, THE validador SHALL verificar que campos textuais não contenham mojibake (ex: "Ã§Ã£o" ao invés de "ção")
3. THE Sistema SHALL adicionar regra de validação que detecte caracteres de substituição Unicode (U+FFFD �)
4. WHEN O Sistema detecta corrupção de encoding em um roteiro, THE validador SHALL retornar erro descritivo indicando o campo e o valor corrompido
5. THE Sistema SHALL fornecer ferramenta de correção automática que normalize strings corrompidas para UTF-8 válido

### Requisito 13: Testes de Integração

**User Story:** Como suite de testes, eu quero validar o pipeline completo com dados acentuados, para que regressões de encoding sejam detectadas automaticamente.

#### Acceptance Criteria

1. THE Sistema SHALL incluir teste de integração que execute captura → geração → execução → renderização com workflow contendo "Criação de Relatório Padrão"
2. THE Sistema SHALL validar que o roteiro JSON final contenha todos os caracteres acentuados preservados
3. THE Sistema SHALL validar que o vídeo MP4 gerado contenha legendas SRT com caracteres acentuados corretos
4. THE Sistema SHALL validar que o PDF gerado exiba todos os caracteres acentuados sem substituição
5. THE Sistema SHALL validar que o pacote SCORM gerado exiba textos acentuados corretamente no player HTML

### Requisito 14: Documentação e Convenções

**User Story:** Como desenvolvedor, eu quero seguir convenções claras de encoding, para que novos módulos não introduzam regressões de acentuação.

#### Acceptance Criteria

1. THE Sistema SHALL documentar convenção obrigatória: `open(..., encoding="utf-8")` em TODAS as operações de I/O de texto
2. THE Sistema SHALL documentar convenção obrigatória: `json.dump(..., ensure_ascii=False)` em TODAS as serializações JSON
3. THE Sistema SHALL documentar convenção obrigatória: usar `limpar_nome()` para nomes de arquivo, preservar acentos em metadados
4. THE Sistema SHALL adicionar regra de linting (ruff/pylint) que detecte `open()` sem `encoding=` explícito
5. THE Sistema SHALL adicionar seção no README explicando suporte a acentuação pt-BR e como testar

### Requisito 15: Retrocompatibilidade

**User Story:** Como sistema legado, eu quero migrar roteiros antigos com encoding corrompido, para que treinamentos existentes sejam recuperáveis.

#### Acceptance Criteria

1. THE Sistema SHALL fornecer script `scripts/fix_encoding.py` que detecte e corrija roteiros com mojibake
2. WHEN O script detecta "Configura\u00e7\u00e3o" (escape Unicode), THE script SHALL converter para "Configuração" (UTF-8 nativo)
3. WHEN O script detecta "CriaÃ§Ã£o" (mojibake Latin-1→UTF-8), THE script SHALL converter para "Criação"
4. THE Sistema SHALL criar backup automático antes de aplicar correções de encoding
5. THE Sistema SHALL gerar relatório listando todos os arquivos corrigidos e as transformações aplicadas

