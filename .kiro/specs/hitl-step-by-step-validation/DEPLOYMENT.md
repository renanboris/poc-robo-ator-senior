# Guia de Deployment: Fix do Radar

## ✅ Pré-requisitos

- [ ] Python 3.11+
- [ ] Playwright instalado
- [ ] Google Gemini API key configurada
- [ ] Roteiros salvos em `roteiros_salvos/`

## 📦 Arquivos Modificados

```
validator_hitl.py          ← Modificado (fix do Radar)
test_radar_fix.py          ← Novo (5 testes)
.kiro/specs/hitl-step-by-step-validation/
├── RADAR_FIX.md           ← Novo (documentação detalhada)
├── RADAR_TROUBLESHOOTING.md ← Novo (guia de troubleshooting)
├── CHANGES.md             ← Novo (mudanças específicas)
└── tasks.md               ← Atualizado (task adicionada)
```

## 🚀 Deployment Steps

### 1. Backup (Segurança)
```bash
# Backup do arquivo original
cp validator_hitl.py validator_hitl.py.backup
```

### 2. Validar Sintaxe
```bash
# Verificar se o arquivo Python está correto
python -m py_compile validator_hitl.py
# Deve retornar sem erros
```

### 3. Executar Testes
```bash
# Executar todos os testes do Radar
python -m pytest test_radar_fix.py -v

# Resultado esperado: 5/5 testes passando ✅
```

### 4. Testar Manualmente
```bash
# Iniciar o validador HITL
python validator_hitl.py roteiros_salvos/seu_roteiro.json

# Quando o overlay aparecer:
# 1. Clique em "✏️ Corrigir"
# 2. Verifique se o cronômetro aparece
# 3. Clique no elemento correto
# 4. Verifique se o seletor é capturado
```

### 5. Monitorar Logs
```bash
# Procure por estes logs em validator_hitl.py:
# [STEP] Radar step ativado — aguardando clique do analista
# [STEP] Seletor capturado via radar: [id='...']
# [STEP] Radar cancelado pelo analista
# [STEP] Timeout de 120s no radar step — cancelando captura
```

## 🔍 Validação Pós-Deployment

### Checklist
- [ ] Arquivo `validator_hitl.py` foi atualizado
- [ ] Testes passam: `python -m pytest test_radar_fix.py -v`
- [ ] Cronômetro aparece quando "Corrigir" é clicado
- [ ] Clique é capturado no frame principal
- [ ] Clique é capturado em iframes
- [ ] Botão "❌ Cancelar" funciona
- [ ] Timeout de 120s funciona
- [ ] Seletor é salvo no Brain com `hitl_corrigido=1`

### Testes de Regressão
```bash
# Executar testes existentes para garantir que nada quebrou
python -m pytest tests/test_hitl_step_by_step.py -v
python -m pytest tests/test_hitl_brain_protection.py -v
python -m pytest tests/test_hitl_dashboard_integration.py -v

# Resultado esperado: Todos os testes passando ✅
```

## 🐛 Rollback (Se Necessário)

```bash
# Restaurar arquivo original
cp validator_hitl.py.backup validator_hitl.py

# Verificar sintaxe
python -m py_compile validator_hitl.py

# Reiniciar o serviço
# (depende da sua configuração de deployment)
```

## 📊 Monitoramento

### Logs Importantes
```
[STEP] Radar step ativado — aguardando clique do analista
[STEP] Seletor capturado via radar: [id='btn-acoes']
[STEP] Radar cancelado pelo analista
[STEP] Timeout de 120s no radar step — cancelando captura
[STEP] Radar: nenhum seletor foi capturado
```

### Métricas
- **Taxa de sucesso do Radar**: Quantos cliques foram capturados com sucesso
- **Taxa de timeout**: Quantos radares atingiram timeout
- **Taxa de cancelamento**: Quantos radares foram cancelados pelo analista

### Dashboard
Adicione estas métricas ao dashboard:
```python
# Em app.py ou metrics.py
radar_captures_total = 0
radar_timeouts_total = 0
radar_cancellations_total = 0
```

## 🔧 Configuração

### Timeout do Radar
Se necessário aumentar o timeout (padrão: 120s):

**Arquivo**: `validator_hitl.py`
**Linha**: ~1890
```python
# Antes
await asyncio.wait_for(self._evento_humano.wait(), timeout=120)

# Depois (180s = 3 minutos)
await asyncio.wait_for(self._evento_humano.wait(), timeout=180)
```

### Cores do Cronômetro
Se necessário customizar as cores:

**Arquivo**: `validator_hitl.py`
**Linha**: ~1750
```javascript
// Antes
'<span id="hitl-radar-countdown" style="font-weight:700;color:#f87171;">⏱ 120s</span>'

// Depois (cor diferente)
'<span id="hitl-radar-countdown" style="font-weight:700;color:#60a5fa;">⏱ 120s</span>'
```

## 📝 Documentação

Consulte os seguintes documentos para mais informações:

1. **RADAR_FIX.md** — Explicação detalhada do fix
2. **RADAR_TROUBLESHOOTING.md** — Guia de troubleshooting
3. **CHANGES.md** — Mudanças específicas no código
4. **tasks.md** — Tasks implementadas

## 🆘 Suporte

Se encontrar problemas:

1. Consulte **RADAR_TROUBLESHOOTING.md**
2. Verifique os logs em `validator_hitl.py`
3. Execute os testes: `python -m pytest test_radar_fix.py -v`
4. Faça rollback se necessário

## ✨ Próximos Passos

1. Testar em produção com roteiros reais
2. Monitorar logs para validar captura de cliques
3. Coletar feedback do analista sobre UX
4. Considerar aumentar timeout se necessário (atualmente 120s)
5. Adicionar métricas ao dashboard

---

**Status**: ✅ Pronto para deployment
**Confiança**: Alta (5/5 testes passando)
**Impacto**: Crítico (Radar agora funciona em iframes)
