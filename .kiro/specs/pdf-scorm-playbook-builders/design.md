# Design Document — pdf-scorm-playbook-builders

## Overview

Esta feature integra dois novos builders ao pipeline do Senior Training OS,
substituindo `pdf_builder.py` e `scorm_builder.py` pelos seus sucessores
`pdf_builder_playbook_v3.py` e `scorm_builder_playbook_v2.py`.

A substituição é cirúrgica: o contrato externo (linha de comando, caminhos de
saída, nomes de artefatos) permanece idêntico ao que `app.py` já espera. O que
muda é o conteúdo gerado — um PDF editorial premium e um SCORM com painel
narrativo por cena — e a eliminação das cópias locais de `limpar_nome`, que
passam a ser importadas de `utils.py`.

Nenhuma mudança estrutural no roteiro JSON é introduzida. O roteiro continua
sendo o contrato central entre captura, geração e entrega.

### Decisões de design

| Decisão | Escolha | Justificativa |
|---|---|---|
| Estratégia de substituição | Renomear arquivos, não alterar `app.py` | Menor risco de regressão; `app.py` já invoca `pdf_builder.py` e `scorm_builder.py` por nome |
| `limpar_nome` | Importar de `utils.py`, remover cópias locais | Elimina Bug #DRY-01; garante comportamento ASCII puro consistente |
| Compatibilidade de campos opcionais | Defaults defensivos em todos os `.get()` | Roteiros antigos não têm `tooltip_dap`, `alerta_instrutor`, `peso_narrativo` |
| Fontes customizadas | Tentativa com fallback para Helvetica | `assets/fonts/` pode não existir em todos os ambientes |
| Temp dir SCORM | `temp_scorm_{base}/` com cleanup garantido | Evita lixo em disco se o processo for interrompido |

---

## Architecture

O pipeline de geração de artefatos permanece inalterado:

```
app.py
  └─ POST /api/gerar-pdf/{arquivo}
       └─ subprocess: python pdf_builder.py <caminho_roteiro>
            └─ lê roteiro JSON
            └─ gera documentacao_pdf/{base}_Playbook.pdf
            └─ exit(0) em sucesso, exit(1) em falha

  └─ POST /api/gerar-scorm/{arquivo}
       └─ subprocess: python scorm_builder.py <caminho_roteiro>
            └─ lê roteiro JSON
            └─ gera scorm_exports/{base}_SCORM.zip
            └─ exit(0) em sucesso, exit(1) em falha
```

A substituição ocorre no nível de arquivo: os novos builders passam a ser os
arquivos `pdf_builder.py` e `scorm_builder.py` (os antigos são arquivados em
`old_but_gold/`).

```
Antes:
  pdf_builder.py          ← v2.2 (builder atual)
  scorm_builder.py        ← v1 (builder atual)
  pdf_builder_playbook_v3.py   ← novo (isolado)
  scorm_builder_playbook_v2.py ← novo (isolado)

Depois:
  pdf_builder.py          ← conteúdo de pdf_builder_playbook_v3.py (corrigido)
  scorm_builder.py        ← conteúdo de scorm_builder_playbook_v2.py (corrigido)
  old_but_gold/pdf_builder_v2.2.py
  old_but_gold/scorm_builder_v1.py
```

### Diagrama de fluxo de dados

```mermaid
flowchart TD
    A[app.py\nPOST /api/gerar-pdf] -->|subprocess| B[pdf_builder.py]
    A2[app.py\nPOST /api/gerar-scorm] -->|subprocess| C[scorm_builder.py]

    B --> D[roteiro JSON\nroteiros_salvos/]
    C --> D

    D --> E[utils.py\nlimpar_nome]
    E --> F[base = limpar_nome\nid_treinamento]

    B --> G[documentacao_pdf/\n{base}_Playbook.pdf]
    C --> H[scorm_exports/\n{base}_SCORM.zip]

    G --> I[app.py\n/api/download-pdf/{base}]
    H --> J[app.py\n/api/download-scorm/{base}]
```

---

## Components and Interfaces

### pdf_builder.py (v3)

**Entrypoint CLI:**
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python pdf_builder.py <caminho_roteiro.json>")
        sys.exit(1)
    try:
        builder = PDFBuilder(json.load(open(sys.argv[1])))
        builder.build()
    except FileNotFoundError:
        print(f"ERRO: arquivo não encontrado: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
```

**Classe principal:**
```python
class PDFBuilder:
    def __init__(self, roteiro: dict, pasta: str = "documentacao_pdf")
    def build(self) -> str  # retorna caminho do PDF gerado
```

**Dependências externas:**
- `from utils import limpar_nome` — sanitização canônica
- `reportlab` — geração PDF
- `Pillow` — processamento de imagens / spotlight

**Artefato de saída:** `documentacao_pdf/{base}_Playbook.pdf`

---

### scorm_builder.py (v2)

**Entrypoint CLI:**
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python scorm_builder.py <caminho_roteiro.json>")
        sys.exit(1)
    try:
        criar_pacote_scorm(sys.argv[1])
    except FileNotFoundError:
        print(f"ERRO: arquivo não encontrado: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
```

**Função principal:**
```python
def criar_pacote_scorm(caminho_json: str, pasta_destino: str = "scorm_exports") -> str
```

**Dependências externas:**
- `from utils import limpar_nome` — sanitização canônica
- `zipfile`, `shutil`, `json` — empacotamento SCORM

**Artefato de saída:** `scorm_exports/{base}_SCORM.zip`

---

### utils.py (sem alteração)

`limpar_nome` permanece a única fonte de verdade para sanitização de nomes.
Nenhuma cópia local deve existir nos builders após a integração.

---

### app.py (sem alteração)

As rotas `/api/gerar-pdf/{arquivo}` e `/api/gerar-scorm/{arquivo}` invocam
`pdf_builder.py` e `scorm_builder.py` por nome via subprocess. Nenhuma mudança
é necessária em `app.py`.

---

## Data Models

### Roteiro JSON (contrato de entrada — sem alteração)

```json
{
  "metadata": {
    "nome_aula": "string",
    "id_treinamento": "string",
    "titulo": "string (opcional)",
    "modulo": "string (opcional)",
    "nivel": "string (opcional)",
    "descricao_curta": "string (opcional)"
  },
  "configuracao_gravacao": { ... },
  "passos": [
    {
      "id_passo": 1,
      "tipo_passo": "navigation | form_fill | confirmation | creation | deletion",
      "peso_narrativo": 1 | 2 | 3,
      "is_conclusao": false,
      "alerta_instrutor": "string | null",
      "pedagogia": {
        "ancora": "string",
        "tooltip_dap": "string (opcional)"
      },
      "acoes_tecnicas": [
        {
          "acao": "clique | duplo_clique | digitar_e_enter | preencher_campo | scroll | concluir_video",
          "micro_narracao": "string (opcional)",
          "valor_input": "string (opcional)",
          "elemento_alvo": {
            "label_curto": "string",
            "screenshot_referencia": "base64 string | null",
            "coordenadas_relativas": {
              "x_pct": 0.0,
              "y_pct": 0.0,
              "w_pct": 0.0,
              "h_pct": 0.0
            }
          }
        }
      ]
    }
  ]
}
```

### Campos opcionais e defaults defensivos

| Campo | Default quando ausente |
|---|---|
| `peso_narrativo` | `2` (Guia) |
| `tooltip_dap` | `""` (omite chip) |
| `alerta_instrutor` | `None` (omite bloco) |
| `screenshot_referencia` | `None` (renderiza placeholder) |
| `coordenadas_relativas` | `{}` (sem spotlight) |
| `id_treinamento` | fallback para `nome_aula` |

### Slides SCORM (estrutura interna do index.html)

```json
[
  {
    "tipo": "ancora",
    "scene_id": 1,
    "scene_kind": "navigation",
    "scene_weight": 2,
    "texto": "string",
    "tooltip": "string",
    "alerta": "string",
    "audio_id": "1_ancora",
    "imagem_b64": "base64 | null"
  },
  {
    "tipo": "interacao",
    "scene_id": 1,
    "scene_kind": "navigation",
    "scene_weight": 2,
    "acao": "clique",
    "valor_input": "",
    "texto": "string",
    "tooltip": "string",
    "alerta": "string",
    "label": "string",
    "audio_id": "1_micro_0",
    "imagem_b64": "base64",
    "x_pct": 0.5,
    "y_pct": 0.5,
    "w_pct": 0.05,
    "h_pct": 0.05
  }
]
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Artefato PDF gerado para todo roteiro válido

*Para todo* roteiro que passa em `validar_roteiro(roteiro)` de `utils.py`, invocar
`PDFBuilder(roteiro).build()` deve produzir um arquivo cujos primeiros 4 bytes
são `%PDF` e encerrar sem lançar exceção.

**Validates: Requirements 2.8, 3.1**

---

### Property 2: Artefato SCORM gerado para todo roteiro válido

*Para todo* roteiro que passa em `validar_roteiro(roteiro)` de `utils.py`, invocar
`criar_pacote_scorm(caminho_json)` deve produzir um arquivo ZIP que contém
`imsmanifest.xml` e `index.html` na raiz, e encerrar sem lançar exceção.

**Validates: Requirements 2.9, 3.2**

---

### Property 3: Nome do artefato derivado de `limpar_nome`

*Para todo* roteiro com `metadata.id_treinamento` preenchido, o nome base do
artefato gerado (PDF ou SCORM) deve ser igual a
`limpar_nome(roteiro["metadata"]["id_treinamento"])` — sem divergência entre
os dois builders.

**Validates: Requirements 1.3, 1.4, 1.5, 1.6**

---

### Property 4: Campos opcionais ausentes não causam exceção

*Para todo* roteiro válido onde qualquer combinação de campos opcionais
(`tooltip_dap`, `alerta_instrutor`, `peso_narrativo`, `screenshot_referencia`)
está ausente ou nula, ambos os builders devem concluir a geração sem lançar
exceção.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7**

---

### Property 5: Contagem mínima de páginas do PDF

*Para todo* roteiro com N passos regulares (não-conclusão), o PDF gerado deve
conter pelo menos N + 2 páginas (capa + mapa + N cenas).

**Validates: Requirements 3.4**

---

### Property 6: Slides SCORM são JSON válido

*Para todo* roteiro processado pelo SCORM builder, o array de slides embutido
no `index.html` deve ser deserializável por `json.loads()` sem erro.

**Validates: Requirements 3.5**

---

### Property 7: Título do treinamento preservado no imsmanifest.xml

*Para todo* roteiro com `metadata.nome_aula` preenchido, o conteúdo do
`imsmanifest.xml` dentro do ZIP gerado deve conter o valor de `nome_aula`
como texto do elemento `<title>`.

**Validates: Requirements 3.3**

---

## Error Handling

### Arquivo de roteiro não encontrado

Ambos os builders devem capturar `FileNotFoundError`, imprimir mensagem
descritiva no stdout (para que `app.py` capture via `executar_processo_bg`) e
encerrar com `sys.exit(1)`.

```python
# Padrão esperado
except FileNotFoundError:
    print(f"ERRO: arquivo de roteiro não encontrado: {caminho}")
    sys.exit(1)
```

### Erro interno durante geração

Qualquer exceção não tratada deve ser capturada no bloco `__main__`, impressa
no stdout e resultar em `sys.exit(1)`. Isso garante que `app.py` detecte o
`returncode != 0` e chame `_set_estado(erro=...)`.

### Imagem base64 inválida

`processar_imagem_com_zoom` já possui try/except com fallback para a imagem
original. Se a imagem original também falhar, retorna `None` e o builder
renderiza o placeholder visual — nunca propaga a exceção.

### Temp dir SCORM

O diretório temporário `temp_scorm_{base}/` deve ser removido via
`shutil.rmtree` em bloco `finally` para garantir limpeza mesmo em caso de
erro durante o empacotamento.

```python
try:
    # ... gera conteúdo no temp_dir ...
    # ... cria ZIP ...
finally:
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
```

### Fontes customizadas ausentes

`register_brand_fonts()` já trata a ausência de fontes silenciosamente. O
fallback para Helvetica é automático via `F(weight)`.

---

## Testing Strategy

### Abordagem dual

A estratégia combina testes unitários (exemplos concretos e casos de borda) com
testes baseados em propriedades (cobertura ampla via geração aleatória de
roteiros).

**Testes unitários** focam em:
- Exemplos de integração end-to-end com roteiros reais de `roteiros_salvos/`
- Casos de borda: roteiro mínimo (2 passos), roteiro sem screenshots, roteiro
  sem campos opcionais
- Verificação de assinatura de arquivo (`%PDF`, ZIP com `imsmanifest.xml`)
- Verificação de código de saída do processo

**Testes de propriedade** focam em:
- Geração bem-sucedida para qualquer roteiro válido (Properties 1, 2, 4)
- Consistência do nome de artefato (Property 3)
- Contagem de páginas (Property 5)
- Validade do JSON de slides (Property 6)
- Preservação do título no manifest (Property 7)

### Biblioteca de property-based testing

Usar **Hypothesis** (já presente no projeto — evidenciado por `.hypothesis/`
no workspace).

```python
from hypothesis import given, settings
from hypothesis import strategies as st
```

### Configuração dos testes de propriedade

- Mínimo de **100 iterações** por teste de propriedade
- Cada teste deve referenciar a propriedade do design com comentário:
  `# Feature: pdf-scorm-playbook-builders, Property N: <texto>`

### Gerador de roteiros para Hypothesis

```python
# Estratégia base para gerar roteiros válidos
@st.composite
def roteiros_validos(draw):
    n_passos = draw(st.integers(min_value=2, max_value=8))
    passos = []
    for i in range(1, n_passos + 1):
        passos.append({
            "id_passo": i,
            "tipo_passo": draw(st.sampled_from(
                ["navigation", "form_fill", "confirmation", "creation", "deletion"]
            )),
            "peso_narrativo": draw(st.integers(min_value=1, max_value=3)),
            "is_conclusao": False,
            "alerta_instrutor": draw(st.one_of(st.none(), st.text(max_size=80))),
            "pedagogia": {
                "ancora": draw(st.text(min_size=5, max_size=120)),
                "tooltip_dap": draw(st.one_of(st.just(""), st.text(max_size=60))),
            },
            "acoes_tecnicas": [
                {
                    "acao": draw(st.sampled_from(["clique", "duplo_clique", "digitar_e_enter"])),
                    "micro_narracao": draw(st.text(max_size=80)),
                    "valor_input": "",
                    "elemento_alvo": {
                        "label_curto": draw(st.text(min_size=1, max_size=30)),
                        "screenshot_referencia": None,
                        "seletor_hint": draw(st.text(min_size=5, max_size=40)),
                        "confianca_captura": draw(st.sampled_from(["alta", "media"])),
                        "coordenadas_relativas": {
                            "x_pct": draw(st.floats(min_value=0.1, max_value=0.9)),
                            "y_pct": draw(st.floats(min_value=0.1, max_value=0.9)),
                            "w_pct": draw(st.floats(min_value=0.02, max_value=0.2)),
                            "h_pct": draw(st.floats(min_value=0.02, max_value=0.2)),
                        },
                    },
                }
            ],
        })
    return {
        "metadata": {
            "nome_aula": draw(st.text(min_size=3, max_size=40)),
            "id_treinamento": draw(st.text(min_size=3, max_size=40)),
        },
        "configuracao_gravacao": {},
        "passos": passos,
    }
```

### Exemplo de teste de propriedade

```python
@given(roteiros_validos())
@settings(max_examples=100)
def test_pdf_gerado_para_roteiro_valido(roteiro):
    # Feature: pdf-scorm-playbook-builders, Property 1: PDF gerado para todo roteiro válido
    aprovado, _ = validar_roteiro(roteiro)
    assume(aprovado)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        builder = PDFBuilder(roteiro, pasta=tmpdir)
        path = builder.build()
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert f.read(4) == b"%PDF"
```

### Plano de testes unitários

| Teste | Tipo | Requisito |
|---|---|---|
| PDF com roteiro mínimo (2 passos, sem screenshots) | unitário | 2.6, 2.8 |
| PDF com roteiro sem `tooltip_dap` | unitário | 2.1 |
| PDF com roteiro sem `alerta_instrutor` | unitário | 2.2 |
| PDF com `peso_narrativo` ausente | unitário | 2.3 |
| SCORM contém `imsmanifest.xml` e `index.html` | unitário | 3.2 |
| SCORM `imsmanifest.xml` contém `nome_aula` | unitário | 3.3 |
| SCORM `index.html` contém JSON de slides válido | unitário | 3.5 |
| Builder PDF encerra com exit(1) se arquivo não existe | unitário | 6.4 |
| Builder SCORM encerra com exit(1) se arquivo não existe | unitário | 6.5 |
| Nome do PDF usa `limpar_nome(id_treinamento)` | unitário | 1.3, 1.5 |
| Nome do SCORM usa `limpar_nome(id_treinamento)` | unitário | 1.4, 1.6 |
