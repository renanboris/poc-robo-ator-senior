// Feature: aura-dap-hardening
// Testes de integração

/**
 * Testes de integração para os módulos Aura DAP após o hardening.
 *
 * Cobre:
 *  - Transições de modo via AuraState (6 transições)
 *  - Proteção contra reentrada do AuraGpsEngine
 *  - element_absent com delay mínimo de 500ms
 *  - Penalidades distintas em modo prove
 *  - Ciclo completo de missão em modo train
 *  - Fluxo GPS fim a fim via Magic Link
 *  - step_error não duplicado entre GPS e Mission
 *
 * Framework: Jest com jsdom (configurado no package.json)
 */

const fs   = require('fs');
const path = require('path');

/**
 * Carrega e executa um módulo IIFE no contexto do jsdom (window disponível).
 * Os módulos usam (function(global){ ... })(window) — eval no contexto global
 * do jsdom faz window ser o global correto.
 */
function loadModule(filename) {
  const code = fs.readFileSync(
    path.join(__dirname, '..', 'modules', filename),
    'utf8'
  );
  // eslint-disable-next-line no-eval
  eval(code);
}

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 1 — Transições de Modo (task 8.1)
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraState — Transições de Modo', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    // Mock AuraGpsEngine
    global.AuraGpsEngine = {
      init:          jest.fn(),
      teardown:      jest.fn(),
      isActive:      jest.fn().mockReturnValue(false),
      normalizeStep: jest.fn(s => s),
    };

    // Mock AuraMissionEngine
    global.AuraMissionEngine = {
      init:     jest.fn(),
      teardown: jest.fn(),
      getScore: jest.fn().mockReturnValue({ xp: 0, hintsUsed: 0, errorsCount: 0, durationSec: 0 }),
    };

    // Mock AuraUI
    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    // Mock AuraSpotlight
    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // Mock AuraAssistEngine (registrado no registry do AuraState)
    global.AuraAssistEngine = {
      init:     jest.fn(),
      teardown: jest.fn(),
    };

    // Carrega o AuraState real (IIFE que usa window)
    loadModule('aura_state.js');

    // Registra os mocks no registry do AuraState
    global.AuraState.registerModule('assist', global.AuraAssistEngine);
    global.AuraState.registerModule('gps',    global.AuraGpsEngine);
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllMocks();
    // Limpa o AuraState do window para o próximo teste
    delete global.AuraState;
  });

  // ── Roteiro de teste reutilizável ──────────────────────────────────────────
  const roteiroTeste = {
    id: 'roteiro_teste',
    passos: [
      { intent: 'Clique no botão', target_selector: '#btn', validation_type: 'click' }
    ]
  };

  const scoringTeste = { base_xp: 100, error_penalty: 15, timeout_penalty: 10 };

  // ── assist → gps ──────────────────────────────────────────────────────────
  // Validates: Requirements 1.1, 7.2, 7.3

  test('assist → gps: teardown do assist chamado, init do gps chamado', () => {
    // Arrange: modo inicial é assist
    expect(global.AuraState.getMode()).toBe('assist');

    // Act
    global.AuraState.setMode('gps');

    // Assert: teardown do assist foi chamado
    expect(global.AuraAssistEngine.teardown).toHaveBeenCalledTimes(1);
    // Assert: init do gps foi chamado via registry
    expect(global.AuraGpsEngine.init).toHaveBeenCalledTimes(1);
    // Assert: modo atualizado
    expect(global.AuraState.getMode()).toBe('gps');
  });

  // ── assist → train ────────────────────────────────────────────────────────
  // Validates: Requirements 1.1, 7.2, 7.3

  test('assist → train: teardown do assist, init do GPS + Mission na ordem correta', () => {
    // Arrange: define roteiro ativo antes de setMode
    global.AuraState.setActiveRoteiro(roteiroTeste, scoringTeste);

    const callOrder = [];
    global.AuraGpsEngine.init.mockImplementation(() => callOrder.push('gps:init'));
    global.AuraMissionEngine.init.mockImplementation(() => callOrder.push('mission:init'));
    global.AuraAssistEngine.teardown.mockImplementation(() => callOrder.push('assist:teardown'));

    // Act
    global.AuraState.setMode('train');

    // Assert: teardown do assist chamado
    expect(global.AuraAssistEngine.teardown).toHaveBeenCalledTimes(1);
    // Assert: GPS init chamado antes de Mission init
    expect(global.AuraGpsEngine.init).toHaveBeenCalledTimes(1);
    expect(global.AuraMissionEngine.init).toHaveBeenCalledTimes(1);
    expect(callOrder).toEqual(['assist:teardown', 'gps:init', 'mission:init']);
    expect(global.AuraState.getMode()).toBe('train');
  });

  // ── assist → prove ────────────────────────────────────────────────────────
  // Validates: Requirements 1.2, 7.2, 7.3

  test('assist → prove: teardown do assist, init do GPS + Mission na ordem correta', () => {
    // Arrange
    global.AuraState.setActiveRoteiro(roteiroTeste, scoringTeste);

    const callOrder = [];
    global.AuraGpsEngine.init.mockImplementation(() => callOrder.push('gps:init'));
    global.AuraMissionEngine.init.mockImplementation(() => callOrder.push('mission:init'));
    global.AuraAssistEngine.teardown.mockImplementation(() => callOrder.push('assist:teardown'));

    // Act
    global.AuraState.setMode('prove');

    // Assert
    expect(callOrder).toEqual(['assist:teardown', 'gps:init', 'mission:init']);
    expect(global.AuraState.getMode()).toBe('prove');
  });

  // ── gps → assist ──────────────────────────────────────────────────────────
  // Validates: Requirements 1.3, 7.2, 7.3

  test('gps → assist: teardown do gps chamado, init do assist chamado', () => {
    // Arrange: vai para gps primeiro
    global.AuraState.setMode('gps');
    global.AuraGpsEngine.init.mockClear();
    global.AuraGpsEngine.teardown.mockClear();
    global.AuraAssistEngine.init.mockClear();

    const callOrder = [];
    global.AuraGpsEngine.teardown.mockImplementation(() => callOrder.push('gps:teardown'));
    global.AuraAssistEngine.init.mockImplementation(() => callOrder.push('assist:init'));

    // Act
    global.AuraState.setMode('assist');

    // Assert
    expect(global.AuraGpsEngine.teardown).toHaveBeenCalledTimes(1);
    expect(global.AuraAssistEngine.init).toHaveBeenCalledTimes(1);
    expect(callOrder).toEqual(['gps:teardown', 'assist:init']);
    expect(global.AuraState.getMode()).toBe('assist');
  });

  // ── train → assist ────────────────────────────────────────────────────────
  // Validates: Requirements 1.3, 7.2, 7.3

  test('train → assist: teardown de Mission + GPS (ordem inversa), init do assist', () => {
    // Arrange: vai para train primeiro
    global.AuraState.setActiveRoteiro(roteiroTeste, scoringTeste);
    global.AuraState.setMode('train');
    // Limpa mocks após a transição inicial
    jest.clearAllMocks();

    const callOrder = [];
    global.AuraMissionEngine.teardown.mockImplementation(() => callOrder.push('mission:teardown'));
    global.AuraGpsEngine.teardown.mockImplementation(() => callOrder.push('gps:teardown'));
    global.AuraAssistEngine.init.mockImplementation(() => callOrder.push('assist:init'));

    // Act
    global.AuraState.setMode('assist');

    // Assert: Mission teardown antes de GPS teardown (ordem inversa da init)
    expect(global.AuraMissionEngine.teardown).toHaveBeenCalledTimes(1);
    expect(global.AuraGpsEngine.teardown).toHaveBeenCalledTimes(1);
    expect(global.AuraAssistEngine.init).toHaveBeenCalledTimes(1);
    expect(callOrder).toEqual(['mission:teardown', 'gps:teardown', 'assist:init']);
    expect(global.AuraState.getMode()).toBe('assist');
  });

  // ── prove → assist ────────────────────────────────────────────────────────
  // Validates: Requirements 1.3, 7.2, 7.3

  test('prove → assist: teardown de Mission + GPS (ordem inversa), init do assist', () => {
    // Arrange
    global.AuraState.setActiveRoteiro(roteiroTeste, scoringTeste);
    global.AuraState.setMode('prove');
    jest.clearAllMocks();

    const callOrder = [];
    global.AuraMissionEngine.teardown.mockImplementation(() => callOrder.push('mission:teardown'));
    global.AuraGpsEngine.teardown.mockImplementation(() => callOrder.push('gps:teardown'));
    global.AuraAssistEngine.init.mockImplementation(() => callOrder.push('assist:init'));

    // Act
    global.AuraState.setMode('assist');

    // Assert
    expect(callOrder).toEqual(['mission:teardown', 'gps:teardown', 'assist:init']);
    expect(global.AuraState.getMode()).toBe('assist');
  });

  // ── setActiveRoteiro + getActiveRoteiro ───────────────────────────────────
  // Validates: Requirement 1.6

  test('setActiveRoteiro armazena roteiro e scoring; getActiveRoteiro retorna o roteiro', () => {
    global.AuraState.setActiveRoteiro(roteiroTeste, scoringTeste);

    expect(global.AuraState.getActiveRoteiro()).toEqual(roteiroTeste);
    expect(global.AuraState.getActiveScoringConfig()).toEqual(scoringTeste);
    expect(global.AuraState.session.roteiro_id).toBe('roteiro_teste');
  });

  // ── tenant_id default ─────────────────────────────────────────────────────
  // Validates: Requirement 5.4

  test('session.tenant_id tem valor padrão "senior_default"', () => {
    expect(global.AuraState.session.tenant_id).toBe('senior_default');
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 2 — Proteção contra Reentrada do GPS (task 8.2)
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraGpsEngine — Proteção contra Reentrada', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    // Mock AuraUI
    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    // Mock AuraSpotlight
    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // Mock AuraState com session
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('gps'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session: {
        steps_total: 0,
        tenant_id:   'senior_default',
        roteiro_id:  null,
      },
    };

    // Carrega o AuraGpsEngine real
    loadModule('aura_gps_engine.js');
  });

  afterEach(() => {
    // Garante teardown para limpar timers e listeners
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraGpsEngine;
  });

  const roteiroSimples = {
    id: 'roteiro_reentrada',
    passos: [
      { intent: 'Passo 1', target_selector: '#btn1', validation_type: 'click', timeout_sec: 30 }
    ]
  };

  // Validates: Requirements 3.1, 7.6

  test('init() chamado duas vezes sem teardown executa teardown preventivo', () => {
    // Arrange: espia o teardown
    const teardownSpy = jest.spyOn(global.AuraGpsEngine, 'teardown');

    // Act: primeira chamada
    global.AuraGpsEngine.init(roteiroSimples);
    expect(global.AuraGpsEngine.isActive()).toBe(true);

    // Act: segunda chamada sem teardown
    global.AuraGpsEngine.init(roteiroSimples);

    // Assert: teardown preventivo foi chamado antes da segunda inicialização
    expect(teardownSpy).toHaveBeenCalledTimes(1);
    // Assert: ainda está ativo após a segunda init
    expect(global.AuraGpsEngine.isActive()).toBe(true);
  });

  test('isActive() retorna false antes do init e true após o init', () => {
    expect(global.AuraGpsEngine.isActive()).toBe(false);
    global.AuraGpsEngine.init(roteiroSimples);
    expect(global.AuraGpsEngine.isActive()).toBe(true);
  });

  test('isActive() retorna false após teardown', () => {
    global.AuraGpsEngine.init(roteiroSimples);
    expect(global.AuraGpsEngine.isActive()).toBe(true);
    global.AuraGpsEngine.teardown();
    expect(global.AuraGpsEngine.isActive()).toBe(false);
  });

  test('init() duplo não duplica o painel GPS no DOM', () => {
    global.AuraGpsEngine.init(roteiroSimples);
    global.AuraGpsEngine.init(roteiroSimples);

    const paineis = document.querySelectorAll('#aura-gps-panel');
    expect(paineis.length).toBe(1);
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 3 — element_absent com delay mínimo (task 8.3)
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraGpsEngine — element_absent com delay', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('gps'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session: {
        steps_total: 0,
        tenant_id:   'senior_default',
        roteiro_id:  null,
      },
    };

    loadModule('aura_gps_engine.js');
  });

  afterEach(() => {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraGpsEngine;
  });

  // Validates: Requirements 3.5, 7.7

  test('gps:step_validated NÃO é emitido antes de 500ms para element_absent com seletor ausente', () => {
    // Arrange: seletor que não existe no DOM
    const seletorAusente = '#elemento-que-nao-existe';
    expect(document.querySelector(seletorAusente)).toBeNull();

    const roteiro = {
      id: 'roteiro_absent',
      passos: [
        {
          intent:          'Aguardar elemento sumir',
          target_selector: seletorAusente,
          validation_type: 'element_absent',
          expected_state:  { selector: seletorAusente },
          timeout_sec:     30,
        }
      ]
    };

    const stepValidatedHandler = jest.fn();
    document.addEventListener('gps:step_validated', stepValidatedHandler);

    // Act: inicia o GPS
    global.AuraGpsEngine.init(roteiro);

    // Assert: antes de 500ms, gps:step_validated NÃO deve ter sido emitido
    jest.advanceTimersByTime(499);
    expect(stepValidatedHandler).not.toHaveBeenCalled();

    // Assert: após 500ms, gps:step_validated DEVE ser emitido
    jest.advanceTimersByTime(1);
    expect(stepValidatedHandler).toHaveBeenCalledTimes(1);

    // Cleanup
    document.removeEventListener('gps:step_validated', stepValidatedHandler);
  });

  test('gps:step_validated não é emitido se elemento aparece durante o delay de 500ms', () => {
    // Arrange: cria o elemento no DOM (presente)
    const el = document.createElement('div');
    el.id = 'elemento-presente';
    document.body.appendChild(el);

    const seletor = '#elemento-presente';

    const roteiro = {
      id: 'roteiro_absent_presente',
      passos: [
        {
          intent:          'Aguardar elemento sumir',
          target_selector: seletor,
          validation_type: 'element_absent',
          expected_state:  { selector: seletor },
          timeout_sec:     30,
        }
      ]
    };

    const stepValidatedHandler = jest.fn();
    document.addEventListener('gps:step_validated', stepValidatedHandler);

    // Act: inicia o GPS — elemento está presente, então não deve iniciar o delay
    global.AuraGpsEngine.init(roteiro);

    // Avança 600ms — como o elemento está presente, não deve validar
    jest.advanceTimersByTime(600);
    expect(stepValidatedHandler).not.toHaveBeenCalled();

    // Cleanup
    document.removeEventListener('gps:step_validated', stepValidatedHandler);
    document.body.removeChild(el);
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 4 — Penalidades Distintas em Modo prove (task 8.4)
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraMissionEngine — Penalidades Distintas', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // AuraState em modo prove
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('prove'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session: {
        steps_total: 3,
        tenant_id:   'senior_default',
        roteiro_id:  'roteiro_prove',
      },
    };

    // Carrega o AuraMissionEngine real
    loadModule('aura_mission_engine.js');
  });

  afterEach(() => {
    if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
      global.AuraMissionEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraMissionEngine;
  });

  const scoringProve = {
    base_xp:        100,
    error_penalty:  15,
    timeout_penalty: 10,
    no_help_bonus:  50,
  };

  // Validates: Requirements 4.4, 7.5

  test('gps:step_timeout em modo prove aplica timeout_penalty (10), não error_penalty (15)', () => {
    // Arrange
    global.AuraMissionEngine.init(scoringProve);
    const xpInicial = global.AuraMissionEngine.getScore().xp;
    expect(xpInicial).toBe(100); // base_xp

    // Act: simula evento gps:step_timeout
    document.dispatchEvent(new CustomEvent('gps:step_timeout', {
      detail: { step: { id: 'passo_1' }, stepIndex: 0, timeout_sec: 30 }
    }));

    // Assert: penalidade de timeout (10) aplicada
    const scoreApos = global.AuraMissionEngine.getScore();
    expect(scoreApos.xp).toBe(90); // 100 - 10
  });

  test('gps:step_failed em modo prove aplica error_penalty (15)', () => {
    // Arrange
    global.AuraMissionEngine.init(scoringProve);
    const xpInicial = global.AuraMissionEngine.getScore().xp;
    expect(xpInicial).toBe(100);

    // Act: simula evento gps:step_failed
    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'passo_1' }, stepIndex: 0 }
    }));

    // Assert: penalidade de erro (15) aplicada
    const scoreApos = global.AuraMissionEngine.getScore();
    expect(scoreApos.xp).toBe(85); // 100 - 15
  });

  test('penalidade de timeout (10) é estritamente menor que penalidade de erro (15)', () => {
    // Arrange
    global.AuraMissionEngine.init(scoringProve);

    // Simula timeout
    document.dispatchEvent(new CustomEvent('gps:step_timeout', {
      detail: { step: { id: 'passo_1' }, stepIndex: 0, timeout_sec: 30 }
    }));
    const xpAposTimeout = global.AuraMissionEngine.getScore().xp; // 90

    // Reinicia para comparar erro
    global.AuraMissionEngine.teardown();
    global.AuraMissionEngine.init(scoringProve);

    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'passo_1' }, stepIndex: 0 }
    }));
    const xpAposErro = global.AuraMissionEngine.getScore().xp; // 85

    // Assert: XP após timeout > XP após erro (penalidade de timeout menor)
    expect(xpAposTimeout).toBeGreaterThan(xpAposErro);
  });

  test('gps:step_timeout em modo train exibe encorajamento sem penalidade de XP', () => {
    // Arrange: muda para modo train
    global.AuraState.getMode.mockReturnValue('train');
    global.AuraMissionEngine.teardown();
    global.AuraMissionEngine.init(scoringProve);
    const xpInicial = global.AuraMissionEngine.getScore().xp;

    // Act: simula timeout em modo train
    document.dispatchEvent(new CustomEvent('gps:step_timeout', {
      detail: { step: { id: 'passo_1' }, stepIndex: 0, timeout_sec: 30 }
    }));

    // Assert: XP não mudou (sem penalidade em train)
    expect(global.AuraMissionEngine.getScore().xp).toBe(xpInicial);
    // Assert: mensagem de encorajamento exibida
    expect(global.AuraUI.exibirBalao).toHaveBeenCalledWith(
      expect.stringContaining('Tente novamente'),
      []
    );
  });

  test('getScore() retorna objeto com xp, hintsUsed, errorsCount, durationSec', () => {
    global.AuraMissionEngine.init(scoringProve);
    const score = global.AuraMissionEngine.getScore();

    expect(score).toHaveProperty('xp');
    expect(score).toHaveProperty('hintsUsed');
    expect(score).toHaveProperty('errorsCount');
    expect(score).toHaveProperty('durationSec');
    expect(typeof score.xp).toBe('number');
    expect(typeof score.hintsUsed).toBe('number');
    expect(typeof score.errorsCount).toBe('number');
    expect(typeof score.durationSec).toBe('number');
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 5 — Ciclo Completo de Missão em Modo train (task 8.5)
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraMissionEngine — Ciclo Completo de Missão (train)', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // AuraState em modo train
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('train'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session: {
        steps_total: 2,
        tenant_id:   'senior_default',
        roteiro_id:  'roteiro_train',
      },
    };

    loadModule('aura_mission_engine.js');
  });

  afterEach(() => {
    if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
      global.AuraMissionEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraMissionEngine;
  });

  const scoringTrain = {
    base_xp:       0,
    error_penalty: 15,
    no_help_bonus: 50,
  };

  // Validates: Requirement 7.4

  test('init() cria o HUD no DOM', () => {
    global.AuraMissionEngine.init(scoringTrain);

    const hud = document.getElementById('aura-mission-hud');
    expect(hud).not.toBeNull();
  });

  test('gps:step_started atualiza o HUD com o intent do passo', () => {
    global.AuraMissionEngine.init(scoringTrain);

    const passo = { id: 'p1', intent: 'Clique no menu', xp_value: 10 };
    document.dispatchEvent(new CustomEvent('gps:step_started', {
      detail: { step: passo, stepIndex: 0 }
    }));

    const intentEl = document.getElementById('aura-hud-intent');
    expect(intentEl).not.toBeNull();
    expect(intentEl.textContent).toBe('Clique no menu');
  });

  test('gps:step_validated incrementa XP', () => {
    global.AuraMissionEngine.init(scoringTrain);
    const xpInicial = global.AuraMissionEngine.getScore().xp;

    const passo = { id: 'p1', intent: 'Passo 1', xp_value: 10 };
    document.dispatchEvent(new CustomEvent('gps:step_validated', {
      detail: { step: passo, stepIndex: 0 }
    }));

    expect(global.AuraMissionEngine.getScore().xp).toBe(xpInicial + 10);
  });

  test('gps:completed exibe resumo via AuraUI.exibirBalao e remove o HUD', () => {
    global.AuraMissionEngine.init(scoringTrain);

    // Verifica que HUD existe antes
    expect(document.getElementById('aura-mission-hud')).not.toBeNull();

    // Simula conclusão
    document.dispatchEvent(new CustomEvent('gps:completed', {
      detail: { roteiro_id: 'roteiro_train', steps_total: 2 }
    }));

    // Assert: resumo exibido
    expect(global.AuraUI.exibirBalao).toHaveBeenCalled();
    const [mensagem] = global.AuraUI.exibirBalao.mock.calls[0];
    expect(typeof mensagem).toBe('string');
    expect(mensagem.length).toBeGreaterThan(0);

    // Assert: HUD removido
    expect(document.getElementById('aura-mission-hud')).toBeNull();
  });

  test('errorsCount incrementa a cada gps:step_failed', () => {
    global.AuraMissionEngine.init(scoringTrain);
    expect(global.AuraMissionEngine.getScore().errorsCount).toBe(0);

    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'p1' }, stepIndex: 0 }
    }));
    expect(global.AuraMissionEngine.getScore().errorsCount).toBe(1);

    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'p1' }, stepIndex: 0 }
    }));
    expect(global.AuraMissionEngine.getScore().errorsCount).toBe(2);
  });

  test('teardown() remove o HUD do DOM', () => {
    global.AuraMissionEngine.init(scoringTrain);
    expect(document.getElementById('aura-mission-hud')).not.toBeNull();

    global.AuraMissionEngine.teardown();
    expect(document.getElementById('aura-mission-hud')).toBeNull();
  });

  test('botão Abandonar chama AuraState.setMode("assist"), não GPS.teardown()', () => {
    // Arrange: mock do AuraGpsEngine para verificar que teardown NÃO é chamado diretamente
    global.AuraGpsEngine = {
      init:     jest.fn(),
      teardown: jest.fn(),
      isActive: jest.fn().mockReturnValue(true),
    };

    global.AuraMissionEngine.init(scoringTrain);

    const btnAbandonar = document.getElementById('aura-hud-btn-abandonar');
    expect(btnAbandonar).not.toBeNull();

    // Act: clica no botão Abandonar
    btnAbandonar.click();

    // Assert: AuraState.setMode('assist') foi chamado
    expect(global.AuraState.setMode).toHaveBeenCalledWith('assist');
    // Assert: AuraGpsEngine.teardown() NÃO foi chamado diretamente
    expect(global.AuraGpsEngine.teardown).not.toHaveBeenCalled();
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 6 — Fluxo GPS Fim a Fim via Magic Link (task 8.6)
// ─────────────────────────────────────────────────────────────────────────────

describe('Fluxo GPS Fim a Fim', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // Mock AuraAssistEngine
    global.AuraAssistEngine = {
      init:     jest.fn(),
      teardown: jest.fn(),
    };

    // Carrega AuraState real
    loadModule('aura_state.js');
    global.AuraState.registerModule('assist', global.AuraAssistEngine);
    global.AuraState.registerModule('gps',    global.AuraGpsEngine || {
      init: jest.fn(), teardown: jest.fn()
    });

    // Carrega AuraGpsEngine real
    loadModule('aura_gps_engine.js');
    global.AuraState.registerModule('gps', global.AuraGpsEngine);
  });

  afterEach(() => {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraState;
    delete global.AuraGpsEngine;
  });

  // Validates: Requirement 7.1

  test('Magic Link: AURA_GPS_EXPLICIT_RESPONSE → setMode("gps") → init → gps:completed → setMode("assist")', () => {
    // Arrange: roteiro que será retornado pela resposta GPS
    const roteiroGps = {
      id: 'gps_magic_link',
      passos: [
        {
          intent:          'Clique no botão de teste',
          target_selector: '#btn-teste-gps',
          validation_type: 'click',
          timeout_sec:     30,
        }
      ]
    };

    // Cria o elemento alvo no DOM
    const btnTeste = document.createElement('button');
    btnTeste.id = 'btn-teste-gps';
    document.body.appendChild(btnTeste);

    // Registra listener para capturar gps:completed
    const completedHandler = jest.fn();
    document.addEventListener('gps:completed', completedHandler);

    // Simula o fluxo do Magic Link:
    // 1. Recebe AURA_GPS_EXPLICIT_RESPONSE (simulado como se o background tivesse respondido)
    // 2. Chama setMode('gps') + AuraGpsEngine.init(roteiro)
    global.AuraState.setMode('gps');
    global.AuraGpsEngine.init(roteiroGps);

    // Assert: GPS está ativo
    expect(global.AuraGpsEngine.isActive()).toBe(true);
    expect(global.AuraState.getMode()).toBe('gps');

    // Simula o usuário clicando no elemento alvo (valida o passo)
    btnTeste.click();

    // Assert: gps:completed foi emitido (GPS concluiu)
    expect(completedHandler).toHaveBeenCalledTimes(1);

    // Assert: AuraState.setMode('assist') foi chamado pelo GPS ao concluir
    // (o GPS chama setMode('assist') internamente em _concluir())
    expect(global.AuraState.getMode()).toBe('assist');

    // Cleanup
    document.removeEventListener('gps:completed', completedHandler);
    document.body.removeChild(btnTeste);
  });

  test('setMode("gps") sem roteiro: GPS não inicia (sem crash)', () => {
    // Arrange: não define roteiro ativo
    // Act: chama setMode('gps') — o GPS será iniciado via registry mas sem roteiro
    expect(() => {
      global.AuraState.setMode('gps');
    }).not.toThrow();

    // Assert: modo atualizado mesmo sem roteiro
    expect(global.AuraState.getMode()).toBe('gps');
  });

  test('gps:step_timeout emite step_timeout ANTES de step_failed', () => {
    // Arrange
    const roteiroTimeout = {
      id: 'roteiro_timeout',
      passos: [
        {
          intent:          'Passo com timeout curto',
          target_selector: '#btn-timeout',
          validation_type: 'click',
          timeout_sec:     5,
        }
      ]
    };

    const eventOrder = [];
    document.addEventListener('gps:step_timeout', () => eventOrder.push('timeout'));
    document.addEventListener('gps:step_failed',  () => eventOrder.push('failed'));

    global.AuraState.setMode('gps');
    global.AuraGpsEngine.init(roteiroTimeout);

    // Act: avança o tempo para expirar o timeout (5s = 5000ms)
    jest.advanceTimersByTime(5001);

    // Assert: step_timeout emitido ANTES de step_failed
    expect(eventOrder[0]).toBe('timeout');
    expect(eventOrder[1]).toBe('failed');

    // Cleanup
    document.removeEventListener('gps:step_timeout', () => {});
    document.removeEventListener('gps:step_failed',  () => {});
  });

});

// ─────────────────────────────────────────────────────────────────────────────
// Grupo 7 — step_error não duplicado (task 8.7)
// ─────────────────────────────────────────────────────────────────────────────

describe('Analytics — step_error não duplicado', () => {

  beforeEach(() => {
    jest.useFakeTimers();

    global.AuraUI = {
      exibirBalao:           jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:         jest.fn(),
    };

    global.AuraSpotlight = {
      aplicar:          jest.fn(),
      remover:          jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // AuraState em modo prove (para que Mission esteja ativa)
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('prove'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session: {
        steps_total: 1,
        tenant_id:   'senior_default',
        roteiro_id:  'roteiro_analytics',
      },
    };

    // Carrega AuraMissionEngine real
    loadModule('aura_mission_engine.js');
  });

  afterEach(() => {
    if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
      global.AuraMissionEngine.teardown();
    }
    jest.useRealTimers();
    jest.clearAllMocks();
    delete global.AuraMissionEngine;
  });

  // Validates: Requirements 4.6, 5.6, 5.8

  test('gps:step_failed NÃO emite step_error via postMessage (Mission não duplica o evento do GPS)', () => {
    // Arrange: inicializa Mission
    global.AuraMissionEngine.init({ base_xp: 100, error_penalty: 15 });

    // Espia postMessage para capturar eventos de analytics
    const postMessageSpy = jest.spyOn(window, 'postMessage');

    // Act: simula gps:step_failed (como se o GPS tivesse emitido)
    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'passo_1', validation_type: 'click' }, stepIndex: 0 }
    }));

    // Filtra apenas eventos de analytics com event_type = 'step_error'
    const stepErrorCalls = postMessageSpy.mock.calls.filter(call => {
      const msg = call[0];
      return msg &&
             msg.type === 'AURA_ANALYTICS_EVENT' &&
             msg.payload &&
             msg.payload.event_type === 'step_error';
    });

    // Assert: AuraMissionEngine NÃO deve ter emitido step_error
    // (apenas o AuraGpsEngine emite step_error, e ele não está carregado aqui)
    expect(stepErrorCalls.length).toBe(0);

    // Assert: penalidade de XP foi aplicada (Mission ainda processa o evento)
    expect(global.AuraMissionEngine.getScore().xp).toBe(85); // 100 - 15

    postMessageSpy.mockRestore();
  });

  test('gps:step_failed incrementa errorsCount sem emitir step_error', () => {
    global.AuraMissionEngine.init({ base_xp: 0, error_penalty: 15 });

    const postMessageSpy = jest.spyOn(window, 'postMessage');

    document.dispatchEvent(new CustomEvent('gps:step_failed', {
      detail: { step: { id: 'p1' }, stepIndex: 0 }
    }));

    // Assert: errorsCount incrementado
    expect(global.AuraMissionEngine.getScore().errorsCount).toBe(1);

    // Assert: nenhum step_error emitido pela Mission
    const stepErrorCalls = postMessageSpy.mock.calls.filter(call => {
      const msg = call[0];
      return msg &&
             msg.type === 'AURA_ANALYTICS_EVENT' &&
             msg.payload &&
             msg.payload.event_type === 'step_error';
    });
    expect(stepErrorCalls.length).toBe(0);

    postMessageSpy.mockRestore();
  });

  test('mission_start é emitido via postMessage ao inicializar AuraMissionEngine', () => {
    const postMessageSpy = jest.spyOn(window, 'postMessage');

    global.AuraMissionEngine.init({ base_xp: 50 });

    const missionStartCalls = postMessageSpy.mock.calls.filter(call => {
      const msg = call[0];
      return msg &&
             msg.type === 'AURA_ANALYTICS_EVENT' &&
             msg.payload &&
             msg.payload.event_type === 'mission_start';
    });

    // Assert: mission_start emitido exatamente uma vez
    expect(missionStartCalls.length).toBe(1);

    const payload = missionStartCalls[0][0].payload.payload;
    expect(payload).toHaveProperty('mode');
    expect(payload).toHaveProperty('steps_total');
    expect(payload).toHaveProperty('timestamp');

    postMessageSpy.mockRestore();
  });

});
