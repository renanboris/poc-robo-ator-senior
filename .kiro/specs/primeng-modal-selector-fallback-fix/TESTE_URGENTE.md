# 🚨 TESTE URGENTE - Cache do Playwright Detectado

## Problema Identificado

A captura ainda está gerando `ui-btn` sem prefixo de modal, o que indica que:

1. ✅ **Implementação está correta** (código JavaScript modificado)
2. ❌ **Playwright está usando cache** (script antigo sendo executado)

## Mudanças Aplicadas Agora

### 1. Versão do Script Atualizada
- **Antes**: `Version 2.1.0`
- **Depois**: `Version 2.1.1-FIXED`

### 2. Cache do Playwright Desabilitado
Adicionei flags no `capture_dual_output.py`:
```python
context = await browser.new_context(
    no_viewport=True,
    bypass_csp=True,           # ✅ NOVO
    ignore_https_errors=True   # ✅ NOVO
)
```

## 🧪 Como Testar (URGENTE)

### PASSO 1: Limpar TUDO

**Opção A - Limpar cache do Playwright (RECOMENDADO)**:
```bash
# No terminal, executar:
cd C:\Users\<seu_usuario>\AppData\Local\ms-playwright
# Deletar a pasta 'chromium-*' manualmente
```

**Opção B - Reiniciar o servidor**:
```bash
# Parar o servidor (Ctrl+C)
# Iniciar novamente
python app.py
```

### PASSO 2: Rodar Nova Captura COM CONSOLE ABERTO

1. **Iniciar captura normalmente**
2. **IMEDIATAMENTE** pressionar **F12** para abrir DevTools
3. Ir para a aba **Console**
4. **VERIFICAR A VERSÃO DO SCRIPT**:
   ```
   [RADAR] Script loading - Version 2.1.1-FIXED  ✅ DEVE SER 2.1.1-FIXED!
   ```

**Se aparecer `Version 2.1.0`**: Cache ainda ativo, precisa limpar mais agressivamente.

**Se aparecer `Version 2.1.1-FIXED`**: Script novo carregado, prosseguir para PASSO 3.

### PASSO 3: Clicar em Elemento DENTRO do Modal

1. Clicar em "Incluir títulos" para abrir modal
2. **Aguardar modal abrir completamente**
3. Clicar em um botão dentro do modal (ex: botão de busca)
4. **VERIFICAR LOGS DO CONSOLE**:
   ```javascript
   [RADAR] processarEvento called { action: 'clique', tag: 'BUTTON', ... }
   [RADAR] resolvePrimeNGComponent called { tag: 'BUTTON', ... }
   [MODAL DEBUG] { hasModal: true, modalType: 'DIV', modalRole: 'dialog', ... }
   [RADAR] PrimeNG result: null
   [RADAR] Final selector: [role="dialog"] button  ✅ DEVE TER PREFIXO!
   [RADAR] Modal context: { type: 'div', role: 'dialog', visible: true }
   ```

**Resultado esperado**:
- ✅ `hasModal: true`
- ✅ `Final selector` com prefixo `[role="dialog"]`
- ✅ `modal_context` não-nulo

### PASSO 4: Verificar Roteiro Gerado

1. Após finalizar captura, abrir o roteiro JSON
2. Buscar por `"label_curto"` de elementos clicados dentro do modal
3. **VERIFICAR SE TEM PREFIXO**:
   ```json
   "label_curto": "[role=\"dialog\"] button"  ✅ CORRETO!
   ```

**Se ainda aparecer `"label_curto": "ui-btn"`**: Cache ainda ativo.

## 🔥 Solução Alternativa (Se Cache Persistir)

Se o cache do Playwright for muito agressivo, podemos:

### Opção 1: Adicionar Timestamp no Script
Modificar `capture_dual_output.py` para adicionar timestamp único:
```python
script_content = f"""
// CACHE BUSTER: {datetime.now().timestamp()}
{script_content}
"""
```

### Opção 2: Usar User Data Dir Temporário
Modificar `capture_dual_output.py` para usar diretório temporário:
```python
import tempfile
user_data_dir = tempfile.mkdtemp()
browser = await p.chromium.launch_persistent_context(
    user_data_dir=user_data_dir,
    headless=False,
    ...
)
```

## 📊 Resultado Esperado

### ✅ Se Tudo Funcionar:

**Console logs**:
```
[RADAR] Script loading - Version 2.1.1-FIXED
[MODAL DEBUG] { hasModal: true, ... }
[RADAR] Final selector: [role="dialog"] button
```

**Roteiro JSON**:
```json
"label_curto": "[role=\"dialog\"] button"
"label_curto": "[role=\"dialog\"] tr:has-text(\"1\")"
```

**Taxa de sucesso**: >90% (vs. 0% atual)

### ❌ Se Ainda Falhar:

**Console logs**:
```
[RADAR] Script loading - Version 2.1.0  ❌ VERSÃO ANTIGA!
[RADAR] Final selector: ui-btn  ❌ SEM PREFIXO!
```

**Ação**: Implementar Opção 1 ou 2 acima para forçar reload.

## 🚀 Próximos Passos

1. **Testar AGORA** com as mudanças aplicadas
2. **Reportar versão do script** que aparece no console
3. **Copiar logs completos** se ainda falhar
4. **Verificar roteiro gerado** para confirmar prefixos

**CRÍTICO**: A versão do script no console é o indicador definitivo se o cache foi limpo ou não.

---

**Aguardando teste urgente! 🔥**
