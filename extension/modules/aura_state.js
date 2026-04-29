/**
 * aura_state.js
 * Modulo: AuraState
 *
 * Unica fonte de verdade para aura_mode e estado compartilhado da sessao.
 * Nenhum outro modulo deve ler ou escrever aura_mode diretamente.
 *
 * Carregado via <script> sequencial — sem bundler (world: MAIN).
 * Expoe interface publica em window.AuraState.
 */
(function (global) {
  'use strict';

  var VALID_MODES = ['assist', 'gps', 'train', 'prove'];

  /**
   * Registro de modulos indexados por nome de modo.
   * Cada entrada deve ter { init(), teardown() }.
   * Outros modulos chamam: AuraState.registerModule('assist', AuraAssistEngine)
   */
  var _moduleRegistry = {};

  /**
   * Estrutura inicial da sessao.
   * Resetada por resetSession().
   */
  function _buildInitialSession() {
    return {
      mode: 'assist',
      roteiro_id: null,
      step_index: 0,
      steps_total: 0,
      tenant_id: 'senior_default',
      xp: 0,
      hints_used: 0,
      errors_count: 0,
      session_start: null,
      mode_start: null
    };
  }

  var _mode = 'assist';
  var _session = _buildInitialSession();
  var _activeRoteiro = null;
  var _activeScoringConfig = null;

  /**
   * Retorna o modo corrente.
   * @returns {'assist'|'gps'|'train'|'prove'}
   */
  function getMode() {
    return _mode;
  }

  /**
   * Registra um modulo para um determinado nome de modo.
   * O objeto deve expor { init(), teardown() }.
   *
   * @param {'assist'|'gps'|'train'|'prove'} modeName
   * @param {{ init: function, teardown: function }} moduleObj
   */
  function registerModule(modeName, moduleObj) {
    if (VALID_MODES.indexOf(modeName) === -1) {
      console.warn('[AuraState] registerModule: nome de modo invalido ignorado:', modeName);
      return;
    }
    if (!moduleObj || typeof moduleObj.init !== 'function' || typeof moduleObj.teardown !== 'function') {
      console.warn('[AuraState] registerModule: modulo invalido para modo', modeName, '— deve ter init() e teardown()');
      return;
    }
    _moduleRegistry[modeName] = moduleObj;
  }

  /**
   * Armazena o roteiro ativo e a configuracao de scoring na sessao.
   * Deve ser chamado antes de setMode('train') ou setMode('prove').
   *
   * @param {Object} roteiro - Objeto roteiro com id e passos
   * @param {Object} scoringConfig - Configuracao de scoring (opcional)
   */
  function setActiveRoteiro(roteiro, scoringConfig) {
    _activeRoteiro = roteiro || null;
    _activeScoringConfig = scoringConfig || null;
    _session.roteiro_id = (roteiro && roteiro.id) ? roteiro.id : null;
  }

  /**
   * Retorna o roteiro ativo armazenado por setActiveRoteiro().
   * @returns {Object|null}
   */
  function getActiveRoteiro() {
    return _activeRoteiro;
  }

  /**
   * Retorna a configuracao de scoring ativa armazenada por setActiveRoteiro().
   * @returns {Object|null}
   */
  function getActiveScoringConfig() {
    return _activeScoringConfig;
  }

  /**
   * Transicao de modo.
   * 1. Valida newMode.
   * 2. Chama teardown() do modulo ativo atual (captura excecao, loga e continua).
   *    - Para modos compostos (train/prove): teardown de AuraMissionEngine e AuraGpsEngine (ordem inversa).
   *    - Para outros modos: comportamento existente via registry.
   * 3. Atualiza _mode para newMode.
   * 4. Chama init() do novo modulo.
   *    - Para modos compostos (train/prove): init de AuraGpsEngine e AuraMissionEngine (ordem correta).
   *    - Para outros modos: comportamento existente via registry.
   *
   * Garante que aura_mode sempre contem exatamente um valor valido.
   *
   * @param {'assist'|'gps'|'train'|'prove'} newMode
   * @param {{ roteiro?: Object, scoringConfig?: Object }} [options]
   */
  function setMode(newMode, options) {
    if (VALID_MODES.indexOf(newMode) === -1) {
      console.warn('[AuraState] setMode: modo invalido ignorado:', newMode);
      return;
    }

    // Teardown do modo ativo atual
    if (_mode === 'train' || _mode === 'prove') {
      // Modos compostos: teardown na ordem inversa da inicializacao (Mission primeiro, GPS depois)
      if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
        try {
          global.AuraMissionEngine.teardown();
        } catch (err) {
          console.error('[AuraState] setMode: erro no teardown do AuraMissionEngine:', err);
        }
      }
      if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
        try {
          global.AuraGpsEngine.teardown();
        } catch (err) {
          console.error('[AuraState] setMode: erro no teardown do AuraGpsEngine:', err);
        }
      }
      // Nao chama o registry generico para esses modos no teardown
    } else {
      // Comportamento existente: teardown via registry
      var currentModule = _moduleRegistry[_mode];
      if (currentModule && typeof currentModule.teardown === 'function') {
        try {
          currentModule.teardown();
        } catch (err) {
          console.error('[AuraState] setMode: erro no teardown do modo "' + _mode + '":', err);
          // Continua a transicao mesmo com erro no teardown
        }
      }
    }

    // Atualiza o modo — garante valor valido antes de chamar init()
    _mode = newMode;
    _session.mode = newMode;
    _session.mode_start = new Date().toISOString();

    // Init do novo modo
    if (newMode === 'train' || newMode === 'prove') {
      // Modos compostos: resolver roteiro e scoring, inicializar GPS + Mission
      var roteiro = (options && options.roteiro) || _activeRoteiro;
      var scoringConfig = (options && options.scoringConfig) || _activeScoringConfig || {};

      if (!roteiro) {
        console.warn('[AuraState] setMode(\'' + newMode + '\'): nenhum roteiro ativo. Chame setActiveRoteiro() antes.');
        return;
      }

      // GPS primeiro (registra listeners de passo)
      if (global.AuraGpsEngine && typeof global.AuraGpsEngine.init === 'function') {
        try {
          global.AuraGpsEngine.init(roteiro);
        } catch (err) {
          console.error('[AuraState] setMode: erro no init do AuraGpsEngine:', err);
        }
      }

      // Mission depois (escuta eventos do GPS)
      if (global.AuraMissionEngine && typeof global.AuraMissionEngine.init === 'function') {
        try {
          global.AuraMissionEngine.init(scoringConfig);
        } catch (err) {
          console.error('[AuraState] setMode: erro no init do AuraMissionEngine:', err);
        }
      }

      // Nao chama o registry generico para esses modos no init
    } else {
      // Comportamento existente: init via registry
      var newModule = _moduleRegistry[newMode];
      if (newModule && typeof newModule.init === 'function') {
        try {
          newModule.init();
        } catch (err) {
          console.error('[AuraState] setMode: erro no init do modo "' + newMode + '":', err);
          // _mode ja foi atualizado; o modulo falhou ao inicializar mas o estado e valido
        }
      }
    }
  }

  /**
   * Reinicia o estado da sessao para os valores iniciais.
   * Preserva o modo corrente.
   */
  function resetSession() {
    var currentMode = _mode;
    _session = _buildInitialSession();
    _session.mode = currentMode;
    _session.session_start = new Date().toISOString();
    _session.mode_start = new Date().toISOString();
  }

  global.AuraState = {
    /** Modo corrente: 'assist' | 'gps' | 'train' | 'prove' */
    get mode() { return _mode; },

    /** Estado da sessao corrente */
    get session() { return _session; },

    setMode: setMode,
    getMode: getMode,
    resetSession: resetSession,
    registerModule: registerModule,
    setActiveRoteiro: setActiveRoteiro,
    getActiveRoteiro: getActiveRoteiro,
    getActiveScoringConfig: getActiveScoringConfig
  };

})(window);
