# Spec: HITL Step-by-Step Validation

## 📋 Visão Geral

Este spec implementa um sistema de validação assistida por humano (HITL) para o validador de roteiros do Senior Training OS. O sistema permite que um analista valide cada ação de um roteiro em tempo real, com opções para confirmar, corrigir, pular ou ativar modo automático.

## ✅ Status

**COMPLETO E TESTADO** ✅

- ✅ 7 tasks principais implementadas
- ✅ 1 task de fix de bug implementada
- ✅ 34 testes unitários passando
- ✅ 5 testes do Radar passando
- ✅ Documentação completa

## 🎯 Objetivos Alcançados

### 1. Loop Step-by-Step
- ✅ Pausa após cada ação (não só em falhas)
- ✅ Modo auto com fallback para step-by-step
- ✅ Controle granular do fluxo

### 2. Overlay Minimalista
- ✅ Canto inferior esquerdo, semi-transparente
- ✅ Progresso (Passo X/Y — Ação Z/W)
- ✅ Descrição da ação e camada que acertou
- ✅ 4 botões: Ok, Corrigir, Auto 5, Pular

### 3. Decisão do Analista
- ✅ "Ok" → reforça memória no Brain
- ✅ "Corrigir" → ativa Radar com cronômetro
- ✅ "Auto N" → modo automático por N ações
- ✅ "Pular" → avança sem registrar

### 4. Proteção HITL no Brain
- ✅ Memórias com `hitl_corrigido=1` excluídas da limpeza TTL
- ✅ Falhas não incrementam contador para memórias HITL-corrigidas
- ✅ Correções nunca são invalidadas automaticamente

### 5. Relatório Final
- ✅ Total de ações, correções, taxa de acerto
- ✅ Botão "🎬 Gravar agora" dispara gravação
- ✅ Botão "Fechar" encerra sem gravar
- ✅ Marca roteiro como `hitl_validado: true`

### 6. Dashboard Integrado
- ✅ "🔍 Validar" como botão principal se não validado
- ✅ "🎬 Gravar" como botão principal se validado
- ✅ Fluxo Validar → Gravar

### 7. Fix do Radar (Bug Fix)
- ✅ Cronômetro aparece corretamente
- ✅ Cliques em iframes são capturados via postMessage
- ✅ Botão "❌ Cancelar" funciona
- ✅ Validação e logging detalhado

## 📁 Estrutura de Arquivos

```
.kiro/specs/hitl-step-by-step-validation/
├── README.md                    ← Este arquivo
├── tasks.md                     ← Tasks implementadas
├── RADAR_FIX.md                 ← Explicação do fix
├── RADAR_TROUBLESHOOTING.md     ← Guia de troubleshooting
├── CHANGES.md                   ← Mudanças específicas
└── DEPLOYMENT.md                ← Guia de deployment

validator_hitl.py               ← Implementação principal
test_radar_fix.py               ← 5 testes do Radar

tests/
├── test_hitl_step_by_step.py           ← 19 testes
├── test_hitl_brain_protection.py       ← 11 testes
└── test_hitl_dashboard_integration.py  ← 4 testes
```

## 🧪 Testes

### Testes Implementados
- ✅ 19 testes para step-by-step (fluxo completo, Ok, Corrigir, Auto mode)
- ✅ 11 testes para proteção HITL no Brain (TTL, falhas, cleanup)
- ✅ 4 testes para integração dashboard (API, status)
- ✅ 5 testes para Radar (cronômetro, clique, cancelar, postMessage, timeout)

**Total**: 39 testes passando ✅

### Executar Testes
```bash
# Todos os testes
python -m pytest tests/test_hitl_*.py test_radar_fix.py -v

# Apenas Radar
python -m pytest test_radar_fix.py -v

# Apenas step-by-step
python -m pytest tests/test_hitl_step_by_step.py -v
```

## 🚀 Como Usar

### 1. Iniciar Validador HITL
```bash
python validator_hitl.py roteiros_salvos/seu_roteiro.json
```

### 2. Fluxo de Validação
1. Cada ação é executada
2. Overlay step-by-step aparece
3. Analista escolhe uma ação:
   - **✅ Ok** → Confirma e avança
   - **✏️ Corrigir** → Ativa Radar para corrigir seletor
   - **⏩ Auto 5** → Próximas 5 ações sem pausa
   - **⏭ Pular** → Pula sem registrar

### 3. Corrigir com Radar
1. Clique em "✏️ Corrigir"
2. Cronômetro aparece (120s)
3. Clique no elemento correto
4. Seletor é capturado e salvo no Brain

### 4. Relatório Final
1. Ao final, relatório com estatísticas
2. Clique em "🎬 Gravar agora" para gravar
3. Ou "Fechar" para encerrar

## 📊 Fluxo Completo

```
┌─────────────────────────────────────────────────────────┐
│ Iniciar Validador HITL                                  │
│ python validator_hitl.py roteiro.json                   │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Executar Ação 1                                         │
│ Overlay step-by-step aparece                            │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┬────────────┬────────────┐
        │                 │            │            │
        ▼                 ▼            ▼            ▼
    ✅ Ok          ✏️ Corrigir    ⏩ Auto 5    ⏭ Pular
        │                 │            │            │
        │                 ▼            │            │
        │          Radar ativo         │            │
        │          Cronômetro 120s     │            │
        │          Clique elemento     │            │
        │          Seletor capturado   │            │
        │                 │            │            │
        └────────────────┬┴────────────┴────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │ Próxima Ação                           │
        │ (Repetir até final)                    │
        └────────────────┬───────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────┐
        │ Relatório Final                        │
        │ Total: 10 ações                        │
        │ Correções: 2                           │
        │ Taxa de acerto: 80%                    │
        └────────────────┬───────────────────────┘
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
        🎬 Gravar agora      Fechar
                │                 │
                ▼                 ▼
        Gravação iniciada   Encerrado
```

## 🔧 Configuração

### Timeout do Radar
Padrão: 120 segundos
Editar em `validator_hitl.py` linha ~1890

### Modo Auto Padrão
Padrão: Step-by-step (não auto-play)
Editar em `validator_hitl.py` linha ~2300

### Cores do Overlay
Editar em `validator_hitl.py` linhas ~600-700

## 📚 Documentação

- **RADAR_FIX.md** — Explicação detalhada do fix do Radar
- **RADAR_TROUBLESHOOTING.md** — Guia de troubleshooting
- **CHANGES.md** — Mudanças específicas no código
- **DEPLOYMENT.md** — Guia de deployment
- **tasks.md** — Tasks implementadas

## 🐛 Problemas Conhecidos

Nenhum problema conhecido no momento.

Se encontrar um problema:
1. Consulte **RADAR_TROUBLESHOOTING.md**
2. Verifique os logs em `validator_hitl.py`
3. Execute os testes: `python -m pytest test_radar_fix.py -v`

## 🎓 Aprendizados

### Desafios Resolvidos
1. **Binding em iframes**: Resolvido com postMessage
2. **CSS de animação**: Injetar antes de usar a classe
3. **Timeout do Radar**: Implementado com countdown visual
4. **Proteção HITL**: Excluir da limpeza TTL

### Boas Práticas Implementadas
- ✅ Logging detalhado para diagnosticar problemas
- ✅ Validação de entrada (seletor capturado)
- ✅ Tratamento de erro robusto
- ✅ Testes unitários abrangentes
- ✅ Documentação completa

## 🚀 Próximos Passos

1. Testar em produção com roteiros reais
2. Monitorar logs para validar captura de cliques
3. Coletar feedback do analista sobre UX
4. Considerar aumentar timeout se necessário (atualmente 120s)
5. Adicionar métricas ao dashboard

## 📞 Suporte

Para dúvidas ou problemas:
1. Consulte a documentação em `.kiro/specs/hitl-step-by-step-validation/`
2. Verifique os logs em `validator_hitl.py`
3. Execute os testes: `python -m pytest test_radar_fix.py -v`
4. Crie uma issue com os detalhes

---

**Spec Status**: ✅ COMPLETO E TESTADO
**Confiança**: Alta (39/39 testes passando)
**Pronto para Produção**: Sim
