/**
 * aura_gps_engine.js
 * Modulo: AuraGpsEngine
 *
 * Motor GPS independente: carregamento de roteiro, execucao de passos,
 * validacao por validation_type, painel de navegacao, eventos de ciclo de vida
 * e analytics.
 *
 * Dependencias (carregadas antes via <script> sequencial):
 *   - window.AuraState    (getMode, setMode, registerModule, session)
 *   - window.AuraSpotlight (aplicar, remover, encontrarElemento)
 *   - window.AuraUI       (exibirBalao)
 *
 * Carregado via <script> sequencial — sem bundler (world: MAIN).
 * Expoe interface publica em window.AuraGpsEngine.
 */
(function (global) {
  'use strict';

  // ─── DEFAULTS DO STEP_MODEL ──────────────────────────────────────────────────
  var STEP_DEFAULTS = {
    validation_type:      'click',
    timeout_sec:          30,
    xp_value:             10,
    xp_penalty_per_hint:  5,
    difficulty:           'medium',
    hint:                 ''
  };

  // ─── ESTADO PRIVADO ──────────────────────────────────────────────────────────
  var _roteiro       = null;   // roteiro completo { id, passos: [] }
  var _passos        = [];     // array de passos normalizados
  var _stepIndex     = 0;      // indice do passo corrente
  var _stepStartTime = null;   // timestamp de inicio do passo corrente (ms)
  var _timeoutHandle = null;   // handle do setTimeout de timeout do passo
  var _panel         = null;   // elemento #aura-gps-panel
  var _isActive      = false;  // true enquanto uma sessão GPS está em execução
  var _options       = {};     // opções passadas ao init() (ex: onBranchDecision)

  // Cleanup do validador ativo (listener ou observer)
  var _cleanupValidator = null;

  // ─── HELPERS DE ANALYTICS ────────────────────────────────────────────────────

  function _emitAnalytics(event_type, payload) {
    global.postMessage({
      type: 'AURA_ANALYTICS_EVENT',
      payload: {
        event_type: event_type,
        timestamp:  new Date().toISOString(),
        payload:    payload || {}
      }
    }, global.location.origin);
  }

  // ─── HELPERS DE EVENTOS ──────────────────────────────────────────────────────

  function _emitCustomEvent(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
  }

  // ─── NORMALIZE STEP ─────────────────────────────────────────────────────────

  /**
   * Aplica defaults do Step_Model para campos ausentes.
   * Emite console.warn para cada campo com default aplicado.
   *
   * @param {object} step — passo recebido do backend (pode ter campos ausentes)
   * @returns {object} passo com todos os campos de default preenchidos
   */
  function normalizeStep(step) {
    var normalized = Object.assign({}, step);
    var campos = Object.keys(STEP_DEFAULTS);
    for (var i = 0; i < campos.length; i++) {
      var campo = campos[i];
      if (normalized[campo] === undefined || normalized[campo] === null) {
        console.warn(
          '[AuraGpsEngine] normalizeStep: campo ausente, aplicando default:',
          campo,
          STEP_DEFAULTS[campo]
        );
        normalized[campo] = STEP_DEFAULTS[campo];
      }
    }
    return normalized;
  }

  // ─── PAINEL GPS ──────────────────────────────────────────────────────────────

  function _criarPainel() {
    _removerPainel();

    var panel = document.createElement('div');
    panel.id = 'aura-gps-panel';
    panel.style.cssText = [
      'position: fixed',
      'top: 0',
      'left: 0',
      'right: 0',
      'z-index: 1000000',
      'background: #1a1a2e',
      'color: #e0e0e0',
      'font-family: sans-serif',
      'font-size: 14px',
      'padding: 10px 16px',
      'display: flex',
      'align-items: center',
      'justify-content: space-between',
      'gap: 12px',
      'box-shadow: 0 2px 8px rgba(0,0,0,0.5)',
      'border-bottom: 2px solid #00E676'
    ].join(';');

    // Conteudo esquerdo: intent + progresso
    var info = document.createElement('div');
    info.id = 'aura-gps-info';
    info.style.cssText = 'flex: 1; overflow: hidden;';

    var intentEl = document.createElement('div');
    intentEl.id = 'aura-gps-intent';
    intentEl.style.cssText = 'font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';

    var progressEl = document.createElement('div');
    progressEl.id = 'aura-gps-progress';
    progressEl.style.cssText = 'font-size: 12px; color: #aaa; margin-top: 2px;';

    info.appendChild(intentEl);
    info.appendChild(progressEl);

    // Botao abandonar
    var btnAbandonar = document.createElement('button');
    btnAbandonar.id = 'aura-gps-btn-abandonar';
    btnAbandonar.textContent = 'Abandonar GPS';
    btnAbandonar.style.cssText = [
      'background: transparent',
      'border: 1px solid #ff5252',
      'color: #ff5252',
      'padding: 4px 10px',
      'border-radius: 4px',
      'cursor: pointer',
      'font-size: 12px',
      'white-space: nowrap',
      'flex-shrink: 0'
    ].join(';');
    btnAbandonar.addEventListener('click', function () {
      _abandonar();
    });

    panel.appendChild(info);
    panel.appendChild(btnAbandonar);
    document.body.appendChild(panel);
    _panel = panel;
  }

  function _atualizarPainel() {
    if (!_panel) return;
    var step = _passos[_stepIndex];
    if (!step) return;

    var intentEl   = document.getElementById('aura-gps-intent');
    var progressEl = document.getElementById('aura-gps-progress');

    if (intentEl)   intentEl.textContent   = step.intent || step.title || '';
    if (progressEl) progressEl.textContent = 'Passo ' + (_stepIndex + 1) + ' de ' + _passos.length;
  }

  function _removerPainel() {
    var existing = document.getElementById('aura-gps-panel');
    if (existing) existing.remove();
    _panel = null;
  }

  // ─── VALIDADORES ─────────────────────────────────────────────────────────────

  /**
   * Registra o validador para o passo corrente de acordo com validation_type.
   * Retorna uma funcao de cleanup que remove o listener/observer.
   */
  function _registrarValidador(step, stepIndex) {
    var tipo     = step.validation_type;
    var seletor  = step.target_selector;
    var expected = step.expected_state || {};

    function _onValidado() {
      _emitCustomEvent('gps:step_validated', { step: step, stepIndex: stepIndex });
      _avancarPasso();
    }

    // ── click ──────────────────────────────────────────────────────────────────
    if (tipo === 'click') {
      return _validadorClick(seletor, 'click', _onValidado);
    }

    // ── right_click ────────────────────────────────────────────────────────────
    if (tipo === 'right_click') {
      return _validadorClick(seletor, 'contextmenu', _onValidado);
    }

    // ── double_click ───────────────────────────────────────────────────────────
    if (tipo === 'double_click') {
      return _validadorClick(seletor, 'dblclick', _onValidado);
    }

    // ── type ───────────────────────────────────────────────────────────────────
    if (tipo === 'type') {
      return _validadorType(seletor, expected.value, _onValidado);
    }

    // ── enter ──────────────────────────────────────────────────────────────────
    if (tipo === 'enter') {
      return _validadorEnter(seletor, _onValidado);
    }

    // ── url_change ─────────────────────────────────────────────────────────────
    if (tipo === 'url_change') {
      return _validadorUrlChange(expected.url_pattern, _onValidado);
    }

    // ── element_present ────────────────────────────────────────────────────────
    if (tipo === 'element_present') {
      return _validadorElementPresent(expected.selector, _onValidado);
    }

    // ── element_absent ─────────────────────────────────────────────────────────
    if (tipo === 'element_absent') {
      return _validadorElementAbsent(expected.selector, _onValidado);
    }

    // ── visual_state — fallback para click ─────────────────────────────────────
    if (tipo === 'visual_state') {
      console.warn('[AuraGpsEngine] visual_state não suportado, usando click como fallback');
      return _validadorClick(seletor, 'click', _onValidado);
    }

    // ── tipo desconhecido — fallback para click ────────────────────────────────
    console.warn('[AuraGpsEngine] validation_type desconhecido, usando click como fallback:', tipo);
    return _validadorClick(seletor, 'click', _onValidado);
  }

  // ── Helpers de validadores ───────────────────────────────────────────────────

  /**
   * Validador baseado em evento de clique (click / contextmenu / dblclick).
   * Usa AuraSpotlight.encontrarElemento para suportar iframes.
   */
  function _validadorClick(seletor, eventName, onValidado) {
    var match = global.AuraSpotlight ? global.AuraSpotlight.encontrarElemento(seletor) : null;
    if (!match || !match.elemento) {
      // Fallback: listener no document com delegacao
      function _handler(e) {
        if (!seletor) return; // seletor vazio não pode ser validado
        var el = e.target;
        while (el) {
          try {
            if (el.matches && el.matches(seletor)) {
              document.removeEventListener(eventName, _handler, true);
              onValidado();
              return;
            }
          } catch (_) {}
          el = el.parentElement;
        }
      }
      document.addEventListener(eventName, _handler, true);
      return function () { document.removeEventListener(eventName, _handler, true); };
    }

    var elemento = match.elemento;
    function _handler() {
      elemento.removeEventListener(eventName, _handler, true);
      onValidado();
    }
    elemento.addEventListener(eventName, _handler, true);
    return function () { elemento.removeEventListener(eventName, _handler, true); };
  }

  /**
   * Validador type: escuta evento 'input' e compara com expected value.
   */
  function _validadorType(seletor, expectedValue, onValidado) {
    var match = global.AuraSpotlight ? global.AuraSpotlight.encontrarElemento(seletor) : null;
    var elemento = match && match.elemento ? match.elemento : document.querySelector(seletor);

    if (!elemento) {
      // Aguarda elemento aparecer via MutationObserver
      var obs = new MutationObserver(function () {
        var found = global.AuraSpotlight
          ? global.AuraSpotlight.encontrarElemento(seletor)
          : { elemento: document.querySelector(seletor) };
        if (found && found.elemento) {
          obs.disconnect();
          _attachTypeListener(found.elemento, expectedValue, onValidado);
        }
      });
      obs.observe(document.body, { childList: true, subtree: true });
      return function () { obs.disconnect(); };
    }

    return _attachTypeListener(elemento, expectedValue, onValidado);
  }

  function _attachTypeListener(elemento, expectedValue, onValidado) {
    function _handler() {
      var val = elemento.value !== undefined ? elemento.value : elemento.textContent;
      if (expectedValue === undefined || expectedValue === null || val === expectedValue) {
        elemento.removeEventListener('input', _handler);
        onValidado();
      }
    }
    elemento.addEventListener('input', _handler);
    return function () { elemento.removeEventListener('input', _handler); };
  }

  /**
   * Validador enter: escuta keydown Enter com foco no target_selector.
   */
  function _validadorEnter(seletor, onValidado) {
    function _handler(e) {
      if (e.key !== 'Enter') return;
      var focused = document.activeElement;
      var match = global.AuraSpotlight ? global.AuraSpotlight.encontrarElemento(seletor) : null;
      var alvo = match && match.elemento ? match.elemento : document.querySelector(seletor);
      if (focused && alvo && (focused === alvo || alvo.contains(focused))) {
        document.removeEventListener('keydown', _handler, true);
        onValidado();
      }
    }
    document.addEventListener('keydown', _handler, true);
    return function () { document.removeEventListener('keydown', _handler, true); };
  }

  /**
   * Validador url_change: MutationObserver no body + comparacao com url_pattern.
   */
  function _validadorUrlChange(urlPattern, onValidado) {
    var _validado = false;

    function _verificar() {
      if (_validado) return;
      var url = global.location.href;
      var match = false;
      if (urlPattern) {
        try {
          match = new RegExp(urlPattern).test(url);
        } catch (_) {
          match = url.includes(urlPattern);
        }
      }
      if (match) {
        _validado = true;
        obs.disconnect();
        onValidado();
      }
    }

    var obs = new MutationObserver(_verificar);
    obs.observe(document.body, { childList: true, subtree: true, attributes: true });

    // Verifica imediatamente caso a URL ja corresponda
    _verificar();

    return function () { obs.disconnect(); };
  }

  /**
   * Validador element_present: MutationObserver + querySelector.
   */
  function _validadorElementPresent(selector, onValidado) {
    var _validado = false;

    function _verificar() {
      if (_validado) return;
      if (selector && document.querySelector(selector)) {
        _validado = true;
        obs.disconnect();
        onValidado();
      }
    }

    var obs = new MutationObserver(_verificar);
    obs.observe(document.body, { childList: true, subtree: true });
    _verificar();

    return function () { obs.disconnect(); };
  }

  /**
   * Validador element_absent: MutationObserver + ausencia de querySelector com delay mínimo de 500ms.
   */
  function _validadorElementAbsent(selector, onValidado) {
    var _validado = false;
    var _delayHandle = null;

    function _verificar() {
      if (_validado) return;
      if (selector && !document.querySelector(selector)) {
        // Delay mínimo de 500ms para evitar falso positivo em carregamentos lentos
        if (_delayHandle) return;
        _delayHandle = setTimeout(function () {
          _delayHandle = null;
          // Verifica novamente após o delay
          if (!document.querySelector(selector)) {
            _validado = true;
            obs.disconnect();
            onValidado();
          }
          // Se o elemento apareceu durante o delay, continua observando
        }, 500);
      }
    }

    var obs = new MutationObserver(_verificar);
    obs.observe(document.body, { childList: true, subtree: true });
    _verificar();

    return function () {
      obs.disconnect();
      if (_delayHandle) {
        clearTimeout(_delayHandle);
        _delayHandle = null;
      }
    };
  }

  // ─── CICLO DE VIDA DOS PASSOS ────────────────────────────────────────────────

  function _iniciarPasso(index) {
    _stepIndex    = index;
    _stepStartTime = Date.now();

    // Limpa validador anterior
    if (typeof _cleanupValidator === 'function') {
      _cleanupValidator();
      _cleanupValidator = null;
    }

    // Limpa timeout anterior
    if (_timeoutHandle !== null) {
      clearTimeout(_timeoutHandle);
      _timeoutHandle = null;
    }

    var step = _passos[index];
    if (!step) return;

    // Atualiza painel
    _atualizarPainel();

    // Emite evento de inicio do passo (usado pelo AuraMissionEngine)
    _emitCustomEvent('gps:step_started', { step: step, stepIndex: index });

    // Analytics: gps_step_started
    _emitAnalytics('gps_step_started', {
      step_id:    step.id || null,
      step_index: index,
      roteiro_id: _roteiro ? (_roteiro.id || null) : null,
      tenant_id:  (global.AuraState && global.AuraState.session && global.AuraState.session.tenant_id)
                    ? global.AuraState.session.tenant_id
                    : 'senior_default',
      timestamp:  new Date().toISOString()
    });

    // Aplica spotlight
    if (global.AuraSpotlight && step.target_selector) {
      global.AuraSpotlight.aplicar(step.target_selector, true);
    }

    // Registra validador
    _cleanupValidator = _registrarValidador(step, index);

    // Timeout do passo
    var timeoutMs = (step.timeout_sec || 30) * 1000;
    _timeoutHandle = setTimeout(function () {
      _timeoutPasso(index);
    }, timeoutMs);
  }

  /**
   * Retorna true se o passo usa delegação no document:
   *   - step é falsy
   *   - step.target_selector está vazio/ausente
   *   - AuraSpotlight.encontrarElemento não encontra o elemento no DOM
   *
   * Função pura de consulta — não modifica nenhum estado.
   *
   * @param {object} step — passo normalizado
   * @returns {boolean}
   */
  function _usaDelegacao(step) {
    if (!step || !step.target_selector) return true;
    var match = global.AuraSpotlight
      ? global.AuraSpotlight.encontrarElemento(step.target_selector)
      : null;
    return !match || !match.elemento;
  }

  function _avancarPasso() {
    // Limpa timeout
    if (_timeoutHandle !== null) {
      clearTimeout(_timeoutHandle);
      _timeoutHandle = null;
    }

    // Limpa validador
    if (typeof _cleanupValidator === 'function') {
      _cleanupValidator();
      _cleanupValidator = null;
    }

    var step = _passos[_stepIndex];
    var duracao = _stepStartTime ? Math.round((Date.now() - _stepStartTime) / 1000) : 0;

    // Analytics: step_complete
    _emitAnalytics('step_complete', {
      step_id:         step ? step.id : null,
      step_index:      _stepIndex,
      validation_type: step ? step.validation_type : null,
      duration_sec:    duracao
    });

    var proximo = _stepIndex + 1;

    // Verifica branch_id para roleplay futuro
    if (step && step.branch_id) {
      _emitCustomEvent('gps:branch_point', {
        step:        step,
        stepIndex:   _stepIndex,
        branch_id:   step.branch_id,
        scenario_id: step.scenario_id || null
      });
      // Aguarda um tick para listeners externos redirecionarem
      var proximoDefault = proximo;
      setTimeout(function () {
        var proximoFinal = proximoDefault;
        if (typeof _options.onBranchDecision === 'function') {
          try {
            var redirect = _options.onBranchDecision(step, proximoDefault);
            if (typeof redirect === 'number') proximoFinal = redirect;
          } catch (err) {
            console.error('[AuraGpsEngine] onBranchDecision lançou exceção, usando fluxo sequencial:', err);
          }
        }
        if (proximoFinal >= _passos.length) { _concluir(); }
        else { _iniciarPasso(proximoFinal); }
      }, 0);
      return;
    }

    if (proximo >= _passos.length) {
      _concluir();
    } else if (_usaDelegacao(_passos[proximo])) {
      setTimeout(function () { _iniciarPasso(proximo); }, 0);
    } else {
      _iniciarPasso(proximo);
    }
  }

  function _timeoutPasso(index) {
    var step = _passos[index];

    // Limpa validador atual
    if (typeof _cleanupValidator === 'function') {
      _cleanupValidator();
      _cleanupValidator = null;
    }

    // Emite step_timeout ANTES de step_failed
    _emitCustomEvent('gps:step_timeout', {
      step:        step,
      stepIndex:   index,
      timeout_sec: step ? step.timeout_sec : 30
    });

    // Analytics: step_error (timeout é um tipo de erro)
    _emitAnalytics('step_error', {
      step_id:         step ? step.id : null,
      step_index:      index,
      validation_type: step ? step.validation_type : null
    });

    _emitCustomEvent('gps:step_failed', { step: step, stepIndex: index });

    // Reinicia o validador para permitir nova tentativa
    _cleanupValidator = _registrarValidador(step, index);

    // Reinicia o timeout
    var timeoutMs = (step ? (step.timeout_sec || 30) : 30) * 1000;
    _timeoutHandle = setTimeout(function () {
      _timeoutPasso(index);
    }, timeoutMs);
  }

  function _concluir() {
    // Remove spotlight
    if (global.AuraSpotlight) global.AuraSpotlight.remover();

    _emitCustomEvent('gps:completed', {
      roteiro_id: _roteiro ? _roteiro.id : null,
      steps_total: _passos.length
    });

    // Exibe mensagem de conclusao
    if (global.AuraUI && typeof global.AuraUI.exibirBalao === 'function') {
      global.AuraUI.exibirBalao('GPS concluído! Você completou todos os passos.');
    }

    // Retorna para modo assist
    if (global.AuraState && typeof global.AuraState.setMode === 'function') {
      global.AuraState.setMode('assist');
    }
  }

  function _abandonar() {
    // Limpa timeout e validador
    if (_timeoutHandle !== null) {
      clearTimeout(_timeoutHandle);
      _timeoutHandle = null;
    }
    if (typeof _cleanupValidator === 'function') {
      _cleanupValidator();
      _cleanupValidator = null;
    }

    // Analytics: session_abandoned
    _emitAnalytics('session_abandoned', {
      step_index_at_abandon: _stepIndex,
      steps_total:           _passos.length
    });

    _emitCustomEvent('gps:abandoned', {
      step_index_at_abandon: _stepIndex,
      steps_total:           _passos.length
    });

    // Remove spotlight e painel
    if (global.AuraSpotlight) global.AuraSpotlight.remover();
    _removerPainel();

    // Retorna para modo assist
    if (global.AuraState && typeof global.AuraState.setMode === 'function') {
      global.AuraState.setMode('assist');
    }
  }

  // ─── INTERFACE PÚBLICA ───────────────────────────────────────────────────────

  /**
   * Inicializa o motor GPS com um roteiro.
   * Normaliza todos os passos, cria o painel, inicia o passo 0 e emite analytics.
   *
   * @param {{ id: string, passos: object[] }} roteiro
   */
  function init(roteiro, options) {
    if (_isActive) {
      console.warn('[AuraGpsEngine] init() chamado com sessão ativa — executando teardown preventivo.');
      // Chama via global para permitir que spies de teste interceptem a chamada
      if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
        global.AuraGpsEngine.teardown();
      } else {
        teardown();
      }
    }

    _options = options || {};
    _roteiro   = roteiro || {};
    _passos    = (_roteiro.passos || []).map(normalizeStep);
    _stepIndex = 0;

    // Propaga steps_total para AuraState.session (usado pelo AuraMissionEngine para dots de progresso)
    if (global.AuraState && global.AuraState.session) {
      global.AuraState.session.steps_total = _passos.length;
    }

    if (_passos.length === 0) {
      console.warn('[AuraGpsEngine] init: roteiro sem passos.');
      return;
    }

    // Cria painel
    _criarPainel();

    // Analytics: gps_start
    _emitAnalytics('gps_start', {
      roteiro_id: _roteiro.id || null,
      timestamp:  new Date().toISOString(),
      mode:       global.AuraState ? global.AuraState.getMode() : 'gps',
      tenant_id:  (global.AuraState && global.AuraState.session && global.AuraState.session.tenant_id)
                    ? global.AuraState.session.tenant_id
                    : 'senior_default'
    });

    // Registra nos modos gps, train e prove
    if (global.AuraState && typeof global.AuraState.registerModule === 'function') {
      global.AuraState.registerModule('gps',   global.AuraGpsEngine);
      global.AuraState.registerModule('train', global.AuraGpsEngine);
      global.AuraState.registerModule('prove', global.AuraGpsEngine);
    }

    // Inicia passo 0
    _isActive = true;
    _iniciarPasso(0);
  }

  /**
   * Encerra o motor GPS: remove painel, listeners e observers.
   */
  function teardown() {
    _isActive = false;

    if (_timeoutHandle !== null) {
      clearTimeout(_timeoutHandle);
      _timeoutHandle = null;
    }

    if (typeof _cleanupValidator === 'function') {
      _cleanupValidator();
      _cleanupValidator = null;
    }

    if (global.AuraSpotlight) global.AuraSpotlight.remover();

    _removerPainel();

    _roteiro       = null;
    _passos        = [];
    _stepIndex     = 0;
    _stepStartTime = null;
  }

  /**
   * Retorna o passo atual normalizado, ou null se nenhum roteiro ativo.
   * Usado pelo AuraMissionEngine para acessar campos de scoring do passo corrente.
   *
   * @returns {object|null}
   */
  function getCurrentStep() {
    return _passos[_stepIndex] || null;
  }

  /**
   * Retorna o índice do passo atual.
   *
   * @returns {number}
   */
  function getCurrentStepIndex() {
    return _stepIndex;
  }

  function isActive() {
    return _isActive;
  }

  global.AuraGpsEngine = {
    init:              init,
    teardown:          teardown,
    normalizeStep:     normalizeStep,
    getCurrentStep:    getCurrentStep,
    getCurrentStepIndex: getCurrentStepIndex,
    isActive:          isActive
  };

  console.log('AuraGpsEngine: módulo carregado.');

})(window);
