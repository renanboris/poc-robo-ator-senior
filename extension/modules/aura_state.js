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
      xp: 0,
      hints_used: 0,
      errors_count: 0,
      session_start: null,
      mode_start: null
    };
  }

  var _mode = 'assist';
  var _session = _buildInitialSession();

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
   * Transicao de modo.
   * 1. Valida newMode.
   * 2. Chama teardown() do modulo ativo atual (captura excecao, loga e continua).
   * 3. Atualiza _mode para newMode.
   * 4. Chama init() do novo modulo (se registrado).
   *
   * Garante que aura_mode sempre contem exatamente um valor valido.
   *
   * @param {'assist'|'gps'|'train'|'prove'} newMode
   */
  function setMode(newMode) {
    if (VALID_MODES.indexOf(newMode) === -1) {
      console.warn('[AuraState] setMode: modo invalido ignorado:', newMode);
      return;
    }

    // Teardown do modulo ativo atual
    var currentModule = _moduleRegistry[_mode];
    if (currentModule && typeof currentModule.teardown === 'function') {
      try {
        currentModule.teardown();
      } catch (err) {
        console.error('[AuraState] setMode: erro no teardown do modo "' + _mode + '":', err);
        // Continua a transicao mesmo com erro no teardown
      }
    }

    // Atualiza o modo — garante valor valido antes de chamar init()
    _mode = newMode;
    _session.mode = newMode;
    _session.mode_start = new Date().toISOString();

    // Init do novo modulo
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
    registerModule: registerModule
  };

})(window);
