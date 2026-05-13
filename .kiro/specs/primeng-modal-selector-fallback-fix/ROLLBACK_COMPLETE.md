# ROLLBACK COMPLETO - Retorno ao Estado Funcional

## Date
2026-05-08

## Decisão
Após múltiplas tentativas de fix que introduziram novos problemas, decidi fazer um **ROLLBACK COMPLETO** para o estado funcional anterior.

## Problemas Encontrados Durante Implementação

### Tentativa #1: Duplicate Variable Declaration
- **Erro**: `const modalAncestor` declarado duas vezes
- **Fix**: Declarar uma vez e reutilizar
- **Resultado**: ❌ Captura ainda não funcionava (0 ações)

### Tentativa #2: Binding Timing
- **Erro**: `expose_binding` chamado após criação da página
- **Fix**: Mover `expose_binding` para antes de `new_page()`
- **Resultado**: ✅ Binding funcionou, mas ❌ script não foi injetado

### Tentativa #3: JavaScript Scope Error
- **Erro**: Múltiplas declarações de `const modalAncestor` em blocos diferentes
- **Fix**: Declarar uma vez no início do bloco `if (identifier)`
- **Resultado**: ❌ **PIOROU** - `SyntaxError: Invalid regular expression: missing /`

## Causa Raiz do Último Erro

**Erro**: `SyntaxError: Invalid regular expression: missing /`

**Causa**: Strings Python com barras invertidas (`\`) não estão sendo escapadas corretamente quando injetadas como JavaScript. Exemplos:

```python
# Python string literal
text.replace(/\\s+/g, ' ')  # ← Precisa de escape duplo em Python

# Quando injetado no JavaScript via triple-quoted string
text.replace(/\s+/g, ' ')   # ← Pode perder o escape
```

O problema é que estamos usando **triple-quoted strings** (`"""..."""`) em Python para conter código JavaScript, e as regras de escape ficam confusas.

## Arquivos Revertidos

```bash
git checkout HEAD -- capture_variants/capture_dual_output.py
git checkout HEAD -- vision_engine.py
```

**Status**: ✅ Sistema de captura voltou ao estado funcional (sem detecção de modal)

## Lições Aprendidas

### 1. Não Modificar JavaScript Inline em Python
- Código JavaScript embutido em strings Python é propenso a erros de escape
- Difícil de debugar e validar
- Pequenas mudanças podem quebrar regex, strings, ou sintaxe

### 2. Testar Incrementalmente
- Cada mudança deveria ser testada isoladamente
- Não fazer múltiplas mudanças ao mesmo tempo
- Ter um plano de rollback claro

### 3. Validar JavaScript Antes de Injetar
- Extrair o código JavaScript e validar com um linter
- Testar no console do navegador antes de deployar
- Usar ferramentas de validação de sintaxe

## Recomendação: Abordagem Alternativa

Ao invés de modificar o JavaScript inline, considere uma das seguintes abordagens:

### Opção 1: Arquivo JavaScript Separado
- Mover o script radar para um arquivo `.js` separado
- Carregar o arquivo e injetá-lo
- Mais fácil de editar, validar e testar

### Opção 2: Implementação Mínima
- Fazer a detecção de modal **apenas no executor Python** (`vision_engine.py`)
- Não modificar o JavaScript de captura
- Gerar candidatos com escopo de modal no executor

### Opção 3: Abordagem Incremental Segura
1. **Primeiro**: Adicionar apenas logging ao JavaScript (sem lógica nova)
2. **Testar**: Verificar que logging funciona
3. **Segundo**: Adicionar detecção de modal simples (sem modificar seletores)
4. **Testar**: Verificar que detecção funciona
5. **Terceiro**: Adicionar prefixo de modal aos seletores
6. **Testar**: Verificar que seletores são gerados corretamente

## Próximos Passos Recomendados

### Opção A: Implementar Apenas no Executor (Mais Seguro)
- ✅ Não modifica JavaScript de captura (zero risco de quebrar)
- ✅ Mais fácil de testar e debugar
- ✅ Pode ser feito incrementalmente
- ❌ Não captura o contexto de modal no momento do clique

**Implementação**:
1. Modificar apenas `vision_engine.py`
2. Detectar se `seletor_hint` parece ser de um modal (heurística)
3. Gerar candidatos com prefixos de modal
4. Testar com roteiros existentes

### Opção B: Pausar Implementação
- Aceitar que o sistema atual funciona (26% de taxa de sucesso)
- Documentar o problema para futura implementação
- Focar em outras melhorias de maior impacto

### Opção C: Contratar Especialista JavaScript
- Ter alguém com expertise em JavaScript/Playwright para revisar
- Fazer pair programming para implementar com segurança
- Validar cada mudança antes de commitar

## Decisão do Usuário

**Pergunta**: Como você gostaria de proceder?

1. **Implementar apenas no executor** (vision_engine.py) - Mais seguro, menor impacto
2. **Pausar implementação** - Aceitar estado atual, focar em outras prioridades
3. **Tentar novamente com abordagem incremental** - Mais cuidadoso, testar cada passo
4. **Outra abordagem** - Sugestões?

---

**Status**: ROLLBACK COMPLETO - Sistema funcional restaurado
**Prioridade**: AGUARDANDO DECISÃO DO USUÁRIO
**Risco**: ZERO - Sistema voltou ao estado funcional anterior
