# Bugfix Requirements Document

## Introduction

A AURA (assistente virtual) não está capturando elementos dentro de iframes, especialmente o iframe principal do GED (ecm_sign) no Senior X. Isso resulta em respostas incorretas da IA, pois o DOM context enviado ao backend contém apenas elementos do documento principal (header/sidebar) mas não o conteúdo real da tela onde o usuário está trabalhando.

Este é um bug de regressão — o usuário confirmou que **"nas versões passadas ele já analisava o iframe normalmente"**.

**Impacto**: A AURA não consegue identificar corretamente onde o usuário está nem interagir com elementos dentro de iframes, comprometendo a experiência de assistência contextual.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `AuraDomMapper.capturar()` é executado em uma página com iframe THEN o sistema captura apenas elementos do documento principal (header, sidebar) e ignora completamente os elementos dentro do iframe

1.2 WHEN o usuário pergunta "onde estou?" enquanto está dentro do iframe do GED (ecm_sign) THEN a AURA responde incorretamente baseada apenas nos elementos do documento principal (ex: "Você está na tela de Novidades e atualizações")

1.3 WHEN o DOM context é enviado ao backend (`dap_engine.py`) THEN o contexto não inclui elementos interativos dentro de iframes, resultando em análise incompleta pela IA

1.4 WHEN `AuraSpotlight.encontrarElemento()` tenta aplicar highlight em um elemento dentro de iframe THEN funciona corretamente (pois já tem lógica de iteração sobre iframes), mas o elemento nunca foi capturado no DOM context inicial

### Expected Behavior (Correct)

2.1 WHEN `AuraDomMapper.capturar()` é executado em uma página com iframe acessível (same-origin ou com permissões) THEN o sistema SHALL iterar sobre iframes e capturar elementos interativos dentro deles, incluindo-os no DOM context

2.2 WHEN o usuário pergunta "onde estou?" enquanto está dentro do iframe do GED (ecm_sign) THEN a AURA SHALL identificar corretamente a localização baseada nos elementos visíveis dentro do iframe

2.3 WHEN o DOM context é enviado ao backend (`dap_engine.py`) THEN o contexto SHALL incluir elementos interativos de iframes acessíveis, permitindo análise completa pela IA

2.4 WHEN elementos dentro de iframes são capturados THEN o sistema SHALL preservar a informação de qual iframe contém cada elemento para permitir highlight e interação corretos

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `AuraDomMapper.capturar()` encontra elementos no documento principal THEN o sistema SHALL CONTINUE TO capturar e mapear esses elementos corretamente

3.2 WHEN `AuraSpotlight.aplicar()` recebe um elemento_id ou seletor_css THEN o sistema SHALL CONTINUE TO aplicar highlight corretamente, tanto em elementos do documento principal quanto em iframes

3.3 WHEN um iframe não é acessível (cross-origin sem permissões) THEN o sistema SHALL CONTINUE TO capturar elementos do documento principal sem falhar ou lançar exceções

3.4 WHEN o container da própria extensão AURA está presente na página THEN o sistema SHALL CONTINUE TO ignorar elementos dentro dele durante a captura

3.5 WHEN elementos são mapeados com `data-aura-map` THEN o sistema SHALL CONTINUE TO usar índices únicos e evitar duplicatas baseadas em texto

## Bug Condition Derivation

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type DOMCaptureContext
  OUTPUT: boolean
  
  // Retorna true quando há iframes acessíveis na página
  // mas o DOM context não inclui elementos deles
  RETURN (X.page_has_accessible_iframes = true) AND 
         (X.dom_context_includes_iframe_elements = false)
END FUNCTION
```

### Property Specification

```pascal
// Property: Fix Checking - Iframe Element Capture
FOR ALL X WHERE isBugCondition(X) DO
  dom_context ← AuraDomMapper.capturar'(X)
  ASSERT dom_context.includes_iframe_elements = true AND
         dom_context.iframe_element_count > 0 AND
         no_exceptions_thrown(dom_context)
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  // Para páginas sem iframes ou com iframes inacessíveis
  ASSERT AuraDomMapper.capturar(X) = AuraDomMapper.capturar'(X)
END FOR
```

**Key Definitions:**
- **F**: `AuraDomMapper.capturar()` original (sem iteração sobre iframes)
- **F'**: `AuraDomMapper.capturar()` corrigido (com iteração sobre iframes)

## Counterexample

**Cenário concreto que demonstra o bug:**

```javascript
// Página: Senior X GED (iframe ecm_sign presente)
// Usuário pergunta: "onde estou?"

// Comportamento atual (buggy):
dom_context = AuraDomMapper.capturar()
// Resultado: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
//            [ID: 201] TIPO: div | TEXTO: 'Novidades e atualizações'
//            [ID: 264] TIPO: section | TEXTO: 'Notificações'"
// ❌ Elementos do iframe ecm_sign NÃO estão presentes

// Comportamento esperado (fixed):
dom_context = AuraDomMapper.capturar'()
// Resultado: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:
//            [ID: 201] TIPO: div | TEXTO: 'Novidades e atualizações'
//            [ID: 264] TIPO: section | TEXTO: 'Notificações'
//            [ID: 300] TIPO: button | TEXTO: 'Novo Documento' (iframe: ecm_sign)
//            [ID: 301] TIPO: input | TEXTO: 'Buscar documentos' (iframe: ecm_sign)"
// ✅ Elementos do iframe ecm_sign estão incluídos
```
