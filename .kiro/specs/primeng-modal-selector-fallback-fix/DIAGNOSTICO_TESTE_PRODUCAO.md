# 🔴 DIAGNÓSTICO - TESTE EM PRODUÇÃO FALHOU

## **Data**: 2026-05-08 18:18
## **Versão Testada**: 2.1.2-VISIBILITY-FIX
## **Status**: ❌ **FALHOU - Seletores genéricos persistem**

---

## 📊 **Evidências do Problema**

### **1. Log do Sistema**
```
[ROBÔ BASTIDORES]: INFO: [FOTO 5] | CLIQUE | ui-btn
[ROBÔ BASTIDORES]: INFO: [FOTO 8] | CLIQUE | ui-btn
[ROBÔ BASTIDORES]: INFO: [FOTO 11] | CLIQUE | ui-btn
[ROBÔ BASTIDORES]: INFO: [FOTO 13] | CLIQUE | ui-btn
[ROBÔ BASTIDORES]: INFO: [FOTO 16] | CLIQUE | ui-btn
```

### **2. Roteiro Gerado**
```json
{
  "label_curto": "ui-btn",  // ❌ Seletor genérico
  "seletor_hint": "..."     // ❌ Sem prefixo de modal
}
```

### **3. Erro de Injeção**
```
[ROBÔ BASTIDORES]: ERROR: [DEBUG] ERRO ao injetar script radar: Frame.evaluate: Frame was detached
```

---

## 🔍 **Análise da Causa Raiz**

### **Hipótese Inicial (INCORRETA)**
- ❌ Pensamos que o problema era cache do Playwright
- ❌ Pensamos que o problema era verificação de visibilidade

### **Causa Raiz Real (IDENTIFICADA)**
Os botões "Selecionar" nos modais PrimeNG têm uma estrutura HTML que **NÃO corresponde a nenhum padrão** em `resolvePrimeNGComponent()`:

1. **Botões têm classe `ui-btn`** (genérica)
2. **Não correspondem aos padrões PrimeNG** específicos (autocomplete, calendar, etc.)
3. **`resolvePrimeNGComponent()` retorna `null`**
4. **Cai no fallback genérico** de `getBestSelector()`
5. **Fallback gera seletor sem contexto específico**

### **Por que o fix anterior não funcionou?**
- ✅ Modal detection está funcionando (`modalAncestor` é detectado)
- ✅ Funções `addModalScope()` e `addModalScopeToFallback()` estão corretas
- ❌ **MAS** os botões genéricos em modais não passam por `resolvePrimeNGComponent()`
- ❌ Eles caem direto no fallback genérico que não tem contexto suficiente

---

## 🛠️ **Solução Implementada**

### **Versão**: 2.1.3-MODAL-BUTTON-FIX

### **Mudança**:
Adicionado padrão específico para capturar **botões genéricos dentro de modais**:

```javascript
} else if (modalAncestor && (el.tagName.toLowerCase() === 'button' || el.closest('button'))) {
    // BUGFIX: Captura botões genéricos dentro de modais (ex: botões "Selecionar")
    // Estes botões não têm padrões PrimeNG específicos, mas precisam de escopo de modal
    suffix = 'button'; partName = 'modal_button'; hostId = 'p-dialog';
}
```

### **Lógica**:
1. Se o elemento está dentro de um modal (`modalAncestor`)
2. E é um botão (`button` tag)
3. E não corresponde a nenhum padrão PrimeNG específico
4. Então trata como `modal_button` e aplica escopo de modal

---

## 📋 **Instruções de Teste**

### **1. Limpar Cache do Navegador**
```bash
# Fechar completamente o navegador Chromium do Playwright
# Reiniciar o sistema se necessário
```

### **2. Executar Captura**
1. Iniciar o Training OS
2. Clicar em "Gravar Nova Aula"
3. Executar o mesmo fluxo:
   - Gestão Empresarial > Finanças > Contas a Receber > Incluir Títulos
   - Clicar nos botões de busca (autocomplete) que abrem modais
   - Clicar nos botões "Selecionar" dentro dos modais

### **3. Verificar Console do Navegador (F12)**
**CRÍTICO**: Abrir o console ANTES de iniciar a captura!

#### **Verificações Obrigatórias**:
```javascript
// 1. Versão do script
[RADAR] Script loading - Version 2.1.3-MODAL-BUTTON-FIX  // ✅ Deve ser 2.1.3

// 2. Modal detection
[MODAL DEBUG] {hasModal: true, modalType: 'DIV', modalRole: 'dialog'}  // ✅ Deve detectar modal

// 3. Seletores gerados
[RADAR] Final selector: [role="dialog"] button  // ✅ Deve ter prefixo de modal
// OU
[RADAR] Final selector: [role="dialog"] [id='...']  // ✅ Deve ter prefixo de modal

// ❌ NÃO DEVE APARECER:
[RADAR] Final selector: ui-btn  // ❌ Seletor genérico sem prefixo
```

### **4. Verificar Log do Sistema**
```
[ROBÔ BASTIDORES]: INFO: [FOTO X] | CLIQUE | [role="dialog"] button  // ✅ Correto
[ROBÔ BASTIDORES]: INFO: [FOTO X] | CLIQUE | [role="dialog"] [id='...']  // ✅ Correto

// ❌ NÃO DEVE APARECER:
[ROBÔ BASTIDORES]: INFO: [FOTO X] | CLIQUE | ui-btn  // ❌ Incorreto
```

### **5. Verificar Roteiro Gerado**
Abrir o arquivo JSON gerado e verificar:

```json
{
  "seletor_hint": "[role=\"dialog\"] button",  // ✅ Deve ter prefixo
  "primeng_component": "p-dialog:modal_button"  // ✅ Deve ter tipo
}
```

---

## ✅ **Critérios de Sucesso**

### **Taxa de Sucesso Esperada**: >95%

1. ✅ **Versão correta carregada**: `2.1.3-MODAL-BUTTON-FIX`
2. ✅ **Modal detection funcionando**: `hasModal: true`
3. ✅ **Seletores com prefixo**: `[role="dialog"] ...`
4. ✅ **Zero seletores `ui-btn`** genéricos
5. ✅ **Preservação**: Elementos fora de modais sem prefixo

---

## 📝 **Próximos Passos**

### **Se o teste PASSAR**:
1. Marcar Task 3.4 como completa
2. Marcar Task 3.5 como completa
3. Executar Task 4 (Integration testing)

### **Se o teste FALHAR**:
1. Capturar logs completos do console
2. Capturar HTML dos botões problemáticos
3. Analisar por que o padrão não está sendo aplicado
4. Iterar na solução

---

## 🔬 **Debug Adicional (se necessário)**

### **Verificar HTML do Botão**
No console do navegador, quando clicar no botão:

```javascript
// Inspecionar o botão clicado
$0  // Elemento selecionado no DevTools

// Verificar ancestral de modal
$0.closest('[role="dialog"]')  // Deve retornar o modal

// Verificar classes
$0.className  // Ver classes CSS do botão

// Verificar ID
$0.id  // Ver se tem ID
```

---

**Autor**: Kiro AI  
**Data**: 2026-05-08  
**Versão do Fix**: 2.1.3-MODAL-BUTTON-FIX
