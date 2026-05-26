// Bug 1 — GPS Race Condition Exploration Test
//
// **Validates: Requirements 1.1, 1.2, 1.3**
//
// OBJETIVO: Confirmar que o bug existe no código NÃO corrigido.
// Este teste DEVE FALHAR no código não corrigido — a falha confirma a race condition.
//
// CAUSA RAIZ: `_avancarPasso` chama `_iniciarPasso(N+1)` SINCRONAMENTE no mesmo
// tick de execução em que o evento de clique do passo N ainda está propagando.
// Quando o passo N+1 usa delegação no `document`, o novo listener captura o
// evento original ainda em bubbling e valida o passo N+1 imediatamente —
// sem ação real do usuário.
//
// NOTA SOBRE JSDOM vs BROWSER REAL:
//   Em jsdom (e em browsers conformes com a spec DOM), listeners adicionados
//   durante o processamento de um evento NÃO disparam para o mesmo evento.
//   Portanto, a race condition comportamental (dois passos validados por um
//   único clique) não se manifesta diretamente em jsdom.
//
//   O teste verifica a CONDIÇÃO ESTRUTURAL que causa a race condition em
//   browsers reais: `_iniciarPasso(N+1)` é chamado SINCRONAMENTE (não diferido
//   via setTimeout) quando o próximo passo usa delegação. Esta é a causa raiz
//   documentada no design.md.
//
// ESTRATÉGIA DO TESTE:
//   - Usar jest.useFakeTimers() para controlar setTimeout
//   - Após um clique que valida o passo 0, verificar que _stepIndex === 1
//     IMEDIATAMENTE (antes de qualquer setTimeout disparar)
//   - No código NÃO corrigido: _iniciarPasso(1) é chamado sincronamente →
//     _stepIndex === 1 imediatamente → assertion "deve ser 0" FALHA ✓
//   - No código CORRIGIDO: _iniciarPasso(1) é diferido via setTimeout →
//     _stepIndex === 0 imediatamente → assertion "deve ser 0" PASSA ✓
//
// COUNTEREXAMPLE DOCUMENTADO:
//   _stepIndex === 1 IMEDIATAMENTE após o clique (antes de setTimeout disparar)
//   quando o passo 1 usa delegação no document.
//   Causa raiz: _iniciarPasso(N+1) registra listener no document antes do
//   bubbling do evento do passo N terminar (em browsers reais).
//
// DO NOT attempt to fix the test or the code when it fails.

'use strict';

const fs   = require('fs');
const path = require('path');

// ─────────────────────────────────────────────────────────────────────────────
// Carregamento do módulo real via eval (padrão do projeto)
// ─────────────────────────────────────────────────────────────────────────────

function loadGpsEngine() {
  const code = fs.readFileSync(
    path.join(__dirname, '..', 'modules', 'aura_gps_engine.js'),
    'utf8'
  );
  // eslint-disable-next-line no-eval
  (0, eval)(code);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers de setup
// ─────────────────────────────────────────────────────────────────────────────

function makeAuraSpotlightStub() {
  return {
    aplicar:           jest.fn(),
    remover:           jest.fn(),
    // Sempre retorna null → força delegação no document para todos os passos
    encontrarElemento: jest.fn().mockReturnValue(null)
  };
}

function makeAuraStateStub() {
  return {
    getMode:        jest.fn().mockReturnValue('gps'),
    setMode:        jest.fn(),
    registerModule: jest.fn(),
    session:        { steps_total: 0, tenant_id: 'senior_default', roteiro_id: null }
  };
}

function makeAuraUIStub() {
  return {
    exibirBalao:             jest.fn(),
    exibirBaloesSequenciais: jest.fn(),
    esconderBalao:           jest.fn()
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Suite principal
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 1 — GPS Race Condition Exploration (código NÃO corrigido)', () => {

  beforeEach(() => {
    // Stubs mínimos das dependências
    global.AuraState     = makeAuraStateStub();
    global.AuraSpotlight = makeAuraSpotlightStub();
    global.AuraUI        = makeAuraUIStub();

    // Silencia logs do módulo
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});

    // Carrega o módulo real
    loadGpsEngine();
  });

  afterEach(() => {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    delete global.AuraGpsEngine;
    delete global.AuraState;
    delete global.AuraSpotlight;
    delete global.AuraUI;
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 1 — BUG CONDITION PRINCIPAL (deve FALHAR no código não corrigido)
  //
  // Verifica a condição estrutural da race condition:
  // _iniciarPasso(N+1) é chamado SINCRONAMENTE quando o próximo passo usa
  // delegação no document.
  //
  // Com jest.useFakeTimers(), o setTimeout do fix (se presente) não dispara.
  // No código NÃO corrigido: _iniciarPasso(1) é chamado sincronamente →
  //   _stepIndex === 1 imediatamente após o clique
  // No código CORRIGIDO: _iniciarPasso(1) é diferido via setTimeout →
  //   _stepIndex === 0 imediatamente após o clique (antes do setTimeout)
  //
  // ASSERTION: _stepIndex deve ser 0 imediatamente após o clique
  // FALHA no código não corrigido (_stepIndex === 1) ✓
  //
  // COUNTEREXAMPLE: _stepIndex === 1 imediatamente após o clique
  // (antes de qualquer setTimeout disparar) quando passo 1 usa delegação.
  // ───────────────────────────────────────────────────────────────────────────
  test('BUG CONDITION: _iniciarPasso(N+1) NÃO deve ser chamado sincronamente quando próximo passo usa delegação', () => {
    // Usa fake timers para impedir que setTimeout dispare
    jest.useFakeTimers();

    const btn = document.createElement('button');
    btn.id = 'btn';
    document.body.appendChild(btn);

    try {
      // Roteiro: passo 0 com '#btn' (delegação, pois AuraSpotlight retorna null),
      // passo 1 com '#btn' (delegação, pois AuraSpotlight retorna null)
      const roteiro = {
        id: 'roteiro_bug_condition',
        passos: [
          { target_selector: '#btn', intent: 'Passo 0 — clique em #btn' },
          { target_selector: '#btn', intent: 'Passo 1 — deve aguardar segundo clique' }
        ]
      };

      global.AuraGpsEngine.init(roteiro);

      // Verifica que o GPS iniciou no passo 0
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(0);

      // Dispara um único clique em #btn
      // O evento borbulha: btn → body → html → document
      // O handler de delegação do passo 0 (capture no document) dispara,
      // valida o passo 0, e chama _avancarPasso()
      btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      // ASSERTION QUE DEVE FALHAR NO CÓDIGO NÃO CORRIGIDO:
      //
      // Imediatamente após o clique (antes de qualquer setTimeout disparar),
      // _stepIndex deve ser 0 — o passo 0 foi validado mas _iniciarPasso(1)
      // ainda não foi chamado (está diferido via setTimeout no código corrigido).
      //
      // No código NÃO corrigido: _iniciarPasso(1) é chamado sincronamente →
      //   getCurrentStepIndex() === 1 → esta assertion FALHA ✓
      //
      // COUNTEREXAMPLE: getCurrentStepIndex() === 1 imediatamente após o clique
      // Causa raiz: _avancarPasso() chama _iniciarPasso(1) no mesmo tick síncrono,
      // registrando o listener do passo 1 no document antes do bubbling terminar.
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(0);

    } finally {
      btn.remove();
    }
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 2 — BUG CONDITION: passo 1 com delegação, passo 0 com seletor direto
  //
  // Cenário: passo 0 tem '#btn' com AuraSpotlight retornando elemento (direto),
  // passo 1 tem '#btn' com AuraSpotlight retornando null (delegação).
  //
  // Após o clique em #btn que valida o passo 0, _iniciarPasso(1) é chamado
  // sincronamente no código não corrigido. Com fake timers, verificamos que
  // _stepIndex === 1 imediatamente (antes do setTimeout do fix disparar).
  //
  // ASSERTION: _stepIndex deve ser 0 imediatamente após o clique
  // FALHA no código não corrigido (_stepIndex === 1) ✓
  // ───────────────────────────────────────────────────────────────────────────
  test('BUG CONDITION: passo 0 com seletor direto, passo 1 com delegação — _iniciarPasso(1) não deve ser síncrono', () => {
    jest.useFakeTimers();

    const btn = document.createElement('button');
    btn.id = 'btn';
    document.body.appendChild(btn);

    try {
      // Passo 0: AuraSpotlight retorna o elemento (listener direto no btn)
      // Passo 1: AuraSpotlight retorna null (delegação no document)
      global.AuraSpotlight.encontrarElemento
        .mockImplementationOnce(() => ({ elemento: btn }))  // passo 0: direto
        .mockReturnValue(null);                              // passo 1+: delegação

      const roteiro = {
        id: 'roteiro_misto',
        passos: [
          { target_selector: '#btn', intent: 'Passo 0 — direto' },
          { target_selector: '#btn', intent: 'Passo 1 — delegação' }
        ]
      };

      global.AuraGpsEngine.init(roteiro);
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(0);

      // Clica em #btn — valida passo 0 via listener direto
      btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      // ASSERTION: _stepIndex deve ser 0 imediatamente (passo 1 não iniciado ainda)
      // FALHA no código não corrigido (_stepIndex === 1) ✓
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(0);

    } finally {
      btn.remove();
    }
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 3 — CONTROLE NEGATIVO: dois seletores DIFERENTES não devem falhar
  //
  // Roteiro: passo 0 com "#btn1", passo 1 com "#btn2".
  // AuraSpotlight retorna null para ambos → delegação para ambos.
  //
  // Clicar em #btn1 valida passo 0. O listener do passo 1 aguarda clique em
  // #btn2. O evento original (em #btn1) não corresponde a "#btn2" → passo 1
  // NÃO é validado imediatamente.
  //
  // Este caso NÃO deve falhar — confirma que o bug é específico ao cenário
  // onde o seletor do passo N+1 corresponde ao elemento clicado no passo N.
  //
  // EXPECTED: _stepIndex === 1 após clicar em #btn1 (passo 0 validado,
  // passo 1 iniciado mas aguardando clique em #btn2)
  //
  // NOTA: Com o fix aplicado, _iniciarPasso(1) é diferido via setTimeout(fn, 0)
  // porque AuraSpotlight retorna null para #btn2 (delegação). Para verificar
  // o estado após o setTimeout disparar, usamos fake timers + runAllTimers().
  // ───────────────────────────────────────────────────────────────────────────
  test('CONTROLE NEGATIVO: seletores diferentes — passo 1 aguarda clique em #btn2 (não falha)', () => {
    // Usa fake timers para controlar o setTimeout do fix
    jest.useFakeTimers();

    const btn1 = document.createElement('button');
    btn1.id = 'btn1';
    document.body.appendChild(btn1);

    const btn2 = document.createElement('button');
    btn2.id = 'btn2';
    document.body.appendChild(btn2);

    try {
      const roteiro = {
        id: 'roteiro_controle_negativo',
        passos: [
          { target_selector: '#btn1', intent: 'Passo 0 — clique em #btn1' },
          { target_selector: '#btn2', intent: 'Passo 1 — clique em #btn2' }
        ]
      };

      global.AuraGpsEngine.init(roteiro);
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(0);

      // Clica em #btn1 — valida passo 0, agenda _iniciarPasso(1) via setTimeout
      btn1.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      // Avança apenas os timers com delay 0 (dispara o setTimeout do fix)
      // Não usa runAllTimers() para evitar disparar o timeout de 30s do passo
      jest.advanceTimersByTime(0);

      // Após o setTimeout disparar, passo 1 deve estar iniciado (_stepIndex === 1)
      // O evento de #btn1 não corresponde ao seletor "#btn2" do passo 1 →
      // passo 1 aguarda clique em #btn2 (não validado imediatamente)
      // Este caso NÃO deve falhar — confirma que o bug é específico à delegação
      // com o mesmo seletor (ou seletor que corresponde ao elemento clicado)
      expect(global.AuraGpsEngine.getCurrentStepIndex()).toBe(1);

    } finally {
      btn1.remove();
      btn2.remove();
    }
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 4 — DOCUMENTAÇÃO DO COUNTEREXAMPLE
  //
  // Documenta explicitamente o counterexample da race condition:
  //   Input:  roteiro com 2 passos, target_selector: "#btn" para ambos,
  //           AuraSpotlight retorna null (delegação para ambos)
  //   Action: um único clique em #btn
  //   Bug:    _iniciarPasso(1) chamado sincronamente → _stepIndex === 1
  //           imediatamente (antes de qualquer setTimeout disparar)
  //   Fix:    _iniciarPasso(1) diferido via setTimeout → _stepIndex === 0
  //           imediatamente (antes do setTimeout disparar)
  //
  // Em browsers reais, a race condition manifesta-se como:
  //   _stepIndex === 2 após um único clique (dois passos validados)
  //   porque o listener do passo 1 captura o mesmo evento de clique
  //   que validou o passo 0 (evento ainda em bubbling quando o listener
  //   é registrado no document).
  //
  // ASSERTION: _stepIndex deve ser 0 imediatamente após o clique
  // FALHA no código não corrigido (_stepIndex === 1) ✓
  // ───────────────────────────────────────────────────────────────────────────
  test('COUNTEREXAMPLE: documenta _iniciarPasso(1) síncrono — _stepIndex === 1 imediatamente após clique', () => {
    jest.useFakeTimers();

    const btn = document.createElement('button');
    btn.id = 'btn';
    document.body.appendChild(btn);

    try {
      const roteiro = {
        id: 'roteiro_counterexample',
        passos: [
          { target_selector: '#btn', intent: 'Passo 0' },
          { target_selector: '#btn', intent: 'Passo 1' }
        ]
      };

      global.AuraGpsEngine.init(roteiro);

      // Captura o stepIndex antes do clique
      const stepIndexBefore = global.AuraGpsEngine.getCurrentStepIndex();
      expect(stepIndexBefore).toBe(0);

      // Único clique
      btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

      // Captura o stepIndex imediatamente após o clique (antes de setTimeout disparar)
      const stepIndexAfterClick = global.AuraGpsEngine.getCurrentStepIndex();

      // DOCUMENTAÇÃO DO COUNTEREXAMPLE:
      // No código NÃO corrigido: stepIndexAfterClick === 1
      //   (porque _iniciarPasso(1) é chamado sincronamente em _avancarPasso)
      // No código CORRIGIDO: stepIndexAfterClick === 0
      //   (porque _iniciarPasso(1) é diferido via setTimeout)
      //
      // A assertion abaixo FALHA no código não corrigido (confirma o bug):
      // _stepIndex deve ser 0 imediatamente após o clique (passo 1 não iniciado)
      expect(stepIndexAfterClick).toBe(0);

    } finally {
      btn.remove();
    }
  });

});
