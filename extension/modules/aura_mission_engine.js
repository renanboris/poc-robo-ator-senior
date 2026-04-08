/**
 * aura_mission_engine.js
 * Modulo: AuraMissionEngine
 *
 * Motor de gamificacao que INSTRUMENTA o GPS (nao o substitui).
 * Escuta eventos do AuraGpsEngine e gerencia HUD, XP, hints, penalidades
 * e resumo de performance.
 *
 * Dependencias (carregadas antes via <script> sequencial):
 *   - window.AuraState      (getMode, session)
 *   - window.AuraUI         (exibirBalao)
 *   - window.AuraSpotlight  (aplicar)
 *   - window.AuraGpsEngine  (getCurrentStep, getCurrentStepIndex)
 *
 * Carregado via <script> sequencial — sem bundler (world: MAIN).
 * Expoe interface publica em window.AuraMissionEngine.
 */
(function (global) {
  'use strict';

  // ─── ESTADO PRIVADO ──────────────────────────────────────────────────────────

  var _scoringConfig  = {};     // configuracao de scoring passada no init
  var _xp             = 0;     // XP acumulado na sessao
  var _hintsUsed      = 0;     // total de hints usados na sessao
  var _errorsCount    = 0;     // total de erros na sessao
  var _sessionStart   = null;  // timestamp de inicio (ms)
  var _currentStep    = null;  // referencia ao passo atual (via gps:step_started)
  var _currentStepIdx = 0;     // indice do passo atual
  var _hud            = null;  // elemento #aura-mission-hud
  var _active         = false; // motor ativo?

  // Listeners registrados (para remocao no teardown)
  var _listeners = [];

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

  // ─── HUD ─────────────────────────────────────────────────────────────────────

  function _criarHud() {
    _removerHud();

    var hud = document.createElement('div');
    hud.id = 'aura-mission-hud';
    hud.style.cssText = [
      'position: fixed',
      'top: 20px',
      'left: 50%',
      'transform: translateX(-50%)',
      'background: rgba(15, 23, 42, 0.95)',
      'backdrop-filter: blur(10px)',
      'border: 1px solid rgba(255, 255, 255, 0.1)',
      'border-radius: 12px',
      'padding: 14px 24px',
      'z-index: 2147483647',
      'color: white',
      'font-family: sans-serif',
      'box-shadow: 0 10px 40px rgba(0,0,0,0.5)',
      'display: flex',
      'flex-direction: column',
      'gap: 8px',
      'min-width: 350px',
      'transition: all 0.3s'
    ].join('; ');

    var mode = global.AuraState ? global.AuraState.getMode() : 'train';
    var modeLabel = mode === 'prove' ? 'Modo Certificação' : 'Modo Treino';
    var modeLabelColor = mode === 'prove' ? '#f59e0b' : '#0ea5e9';

    hud.innerHTML = [
      '<div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#94a3b8;">',
        '<span id="aura-hud-mode-label" style="text-transform:uppercase; font-weight:bold; letter-spacing:1px; color:' + modeLabelColor + ';">' + modeLabel + '</span>',
        '<span id="aura-hud-xp" style="font-weight:bold; color:#22c55e;">XP: 0</span>',
      '</div>',
      '<div id="aura-hud-intent" style="font-size:16px; font-weight:500;">Aguarde...</div>',
      '<div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">',
        '<div id="aura-hud-dots" style="display:flex; gap:4px;"></div>',
        '<button id="aura-hud-btn-ajuda" style="background:rgba(245,158,11,0.2); border:1px solid #f59e0b; color:#fbbf24; border-radius:6px; padding:4px 8px; font-size:11px; cursor:pointer; transition:all 0.2s;">',
          'Preciso de Ajuda',
        '</button>',
        '<button id="aura-hud-btn-abandonar" style="background:none; border:none; color:#ef4444; font-size:11px; cursor:pointer;">Abandonar</button>',
      '</div>'
    ].join('');

    document.documentElement.appendChild(hud);
    _hud = hud;

    // Botao abandonar
    var btnAbandonar = document.getElementById('aura-hud-btn-abandonar');
    if (btnAbandonar) {
      btnAbandonar.addEventListener('click', function () {
        if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
          global.AuraGpsEngine.teardown();
        }
        if (global.AuraState && typeof global.AuraState.setMode === 'function') {
          global.AuraState.setMode('assist');
        }
      });
    }

    // Botao ajuda
    var btnAjuda = document.getElementById('aura-hud-btn-ajuda');
    if (btnAjuda) {
      btnAjuda.addEventListener('click', _solicitarHint);
    }
  }

  function _atualizarHud(totalPassos) {
    if (!_hud) return;

    var step = _currentStep;

    // Intent
    var intentEl = document.getElementById('aura-hud-intent');
    if (intentEl && step) {
      intentEl.textContent = step.intent || '';
    }

    // XP
    var xpEl = document.getElementById('aura-hud-xp');
    if (xpEl) {
      xpEl.textContent = 'XP: ' + _xp;
      xpEl.style.transform = 'scale(1.1)';
      setTimeout(function () { xpEl.style.transform = 'scale(1)'; }, 300);
    }

    // Dots de progresso
    var dotsEl = document.getElementById('aura-hud-dots');
    if (dotsEl && totalPassos > 0) {
      var html = '';
      for (var i = 0; i < totalPassos; i++) {
        var bg, shadow;
        if (i < _currentStepIdx) {
          bg = '#22c55e'; shadow = 'none';
        } else if (i === _currentStepIdx) {
          bg = '#0ea5e9'; shadow = '0 0 8px #0ea5e9';
        } else {
          bg = 'rgba(255,255,255,0.2)'; shadow = 'none';
        }
        html += '<div style="width:8px; height:8px; border-radius:50%; background:' + bg + '; box-shadow:' + shadow + '; transition:all 0.3s;"></div>';
      }
      dotsEl.innerHTML = html;
    }

    // Botao ajuda: desabilitar em prove apos 1 hint
    var mode = global.AuraState ? global.AuraState.getMode() : 'train';
    var btnAjuda = document.getElementById('aura-hud-btn-ajuda');
    if (btnAjuda && mode === 'prove' && _hintsUsed >= 1) {
      btnAjuda.disabled = true;
      btnAjuda.style.opacity = '0.4';
      btnAjuda.style.cursor = 'not-allowed';
    }
  }

  function _removerHud() {
    var existing = document.getElementById('aura-mission-hud');
    if (existing) existing.remove();
    _hud = null;
  }

  // ─── HINTS ───────────────────────────────────────────────────────────────────

  function _solicitarHint() {
    if (!_active) return;

    var mode = global.AuraState ? global.AuraState.getMode() : 'train';

    // Modo prove: maximo 1 hint por sessao
    if (mode === 'prove' && _hintsUsed >= 1) {
      return;
    }

    var step = _currentStep;
    if (!step) return;

    _hintsUsed++;

    // Custo de XP
    var custo = step.xp_penalty_per_hint !== undefined ? step.xp_penalty_per_hint : 5;
    _xp = Math.max(0, _xp - custo);

    // Atualiza HUD
    var totalPassos = global.AuraGpsEngine ? _getTotalPassos() : 0;
    _atualizarHud(totalPassos);

    // Aplica spotlight no target_selector do passo atual
    if (global.AuraSpotlight && step.target_selector) {
      global.AuraSpotlight.aplicar(step.target_selector, true);
    }

    // Exibe mensagem de ajuda
    if (global.AuraUI && typeof global.AuraUI.exibirBalao === 'function') {
      global.AuraUI.exibirBalao('Sem problemas, eu mostro o caminho!', []);
    }

    // Analytics: hint_requested
    _emitAnalytics('hint_requested', {
      step_id:             step.id || null,
      step_index:          _currentStepIdx,
      hints_total_session: _hintsUsed
    });

    // Desabilita botao em modo prove apos usar o hint
    if (mode === 'prove') {
      var btnAjuda = document.getElementById('aura-hud-btn-ajuda');
      if (btnAjuda) {
        btnAjuda.disabled = true;
        btnAjuda.style.opacity = '0.4';
        btnAjuda.style.cursor = 'not-allowed';
      }
    }
  }

  // ─── HELPERS ─────────────────────────────────────────────────────────────────

  function _getTotalPassos() {
    // Tenta inferir total de passos via AuraState.session ou via GPS
    if (global.AuraState && global.AuraState.session && global.AuraState.session.steps_total) {
      return global.AuraState.session.steps_total;
    }
    return 0;
  }

  function _addListener(eventName, handler) {
    document.addEventListener(eventName, handler);
    _listeners.push({ eventName: eventName, handler: handler });
  }

  // ─── HANDLERS DE EVENTOS GPS ─────────────────────────────────────────────────

  function _onStepStarted(e) {
    if (!_active) return;
    var detail = e.detail || {};
    _currentStep    = detail.step    || null;
    _currentStepIdx = detail.stepIndex !== undefined ? detail.stepIndex : 0;

    var totalPassos = _getTotalPassos();
    _atualizarHud(totalPassos);
  }

  function _onStepValidated(e) {
    if (!_active) return;
    var detail = e.detail || {};
    var step = detail.step || _currentStep;

    // Adiciona XP do passo
    var xpGanho = (step && step.xp_value !== undefined) ? step.xp_value : 10;
    _xp += xpGanho;

    // Atualiza referencia ao passo (pode ter avancado)
    if (detail.step)       _currentStep    = detail.step;
    if (detail.stepIndex !== undefined) _currentStepIdx = detail.stepIndex;

    var totalPassos = _getTotalPassos();
    _atualizarHud(totalPassos);
  }

  function _onStepFailed(e) {
    if (!_active) return;
    var detail = e.detail || {};
    var step = detail.step || _currentStep;

    // Penalidade de XP por erro
    var penalidade = (_scoringConfig && _scoringConfig.error_penalty !== undefined)
      ? _scoringConfig.error_penalty
      : 15;
    _xp = Math.max(0, _xp - penalidade);
    _errorsCount++;

    var totalPassos = _getTotalPassos();
    _atualizarHud(totalPassos);

    // Analytics: step_error (emitido pelo GPS, mas registramos aqui tambem para missao)
    _emitAnalytics('step_error', {
      step_id:    step ? step.id : null,
      step_index: detail.stepIndex !== undefined ? detail.stepIndex : _currentStepIdx
    });
  }

  function _onCompleted(e) {
    if (!_active) return;
    var detail = e.detail || {};

    var mode = global.AuraState ? global.AuraState.getMode() : 'train';

    // Bonus de autonomia: sem hints
    var bonusAutonomia = (_hintsUsed === 0)
      ? ((_scoringConfig && _scoringConfig.no_help_bonus !== undefined) ? _scoringConfig.no_help_bonus : 50)
      : 0;

    var scoreFinal = _xp + bonusAutonomia;
    var duracao = _sessionStart ? Math.round((Date.now() - _sessionStart) / 1000) : 0;

    // Monta mensagem de resumo diferenciada por modo
    var msg;
    if (mode === 'prove') {
      if (bonusAutonomia > 0) {
        msg = '🏆 Certificação concluída com autonomia total! Bônus de ' + bonusAutonomia + ' XP aplicado. Score final: ' + scoreFinal + ' XP.';
      } else {
        msg = '✅ Certificação concluída! Você demonstrou domínio do fluxo. Score final: ' + scoreFinal + ' XP.';
      }
    } else {
      // train
      if (bonusAutonomia > 0) {
        msg = '🏆 Incrível! Você completou o treino com 100% de autonomia e ganhou um bônus! Score final: ' + scoreFinal + ' XP.';
      } else {
        msg = '✅ Treino concluído! Você praticou o fluxo e conquistou ' + scoreFinal + ' XP.';
      }
    }

    // Exibe resumo
    if (global.AuraUI && typeof global.AuraUI.exibirBalao === 'function') {
      global.AuraUI.exibirBalao(msg, [
        { label: 'Fechar', action: function () {
          var bubble = document.getElementById('aura-speech-bubble');
          if (bubble) bubble.classList.remove('active');
        }}
      ]);
    }

    // Analytics: mission_complete
    _emitAnalytics('mission_complete', {
      roteiro_id:  detail.roteiro_id || null,
      mode:        mode,
      score_final: scoreFinal,
      xp_final:    _xp,
      hints_used:  _hintsUsed,
      errors_count: _errorsCount,
      duration_sec: duracao
    });

    // Remove HUD
    _removerHud();
    _active = false;
  }

  // ─── INTERFACE PÚBLICA ───────────────────────────────────────────────────────

  /**
   * Inicializa o motor de gamificacao.
   * Deve ser chamado apenas quando aura_mode for 'train' ou 'prove'.
   *
   * @param {object} scoringConfig — { error_penalty, no_help_bonus, base_xp }
   */
  function init(scoringConfig) {
    teardown();

    var mode = global.AuraState ? global.AuraState.getMode() : null;
    if (mode !== 'train' && mode !== 'prove') {
      // Nao exibe HUD fora dos modos de missao
      return;
    }

    _scoringConfig  = scoringConfig || {};
    _xp             = _scoringConfig.base_xp || 0;
    _hintsUsed      = 0;
    _errorsCount    = 0;
    _sessionStart   = Date.now();
    _currentStep    = null;
    _currentStepIdx = 0;
    _active         = true;

    // Cria HUD
    _criarHud();

    // Registra listeners de eventos GPS
    _addListener('gps:step_started',   _onStepStarted);
    _addListener('gps:step_validated', _onStepValidated);
    _addListener('gps:step_failed',    _onStepFailed);
    _addListener('gps:completed',      _onCompleted);
  }

  /**
   * Encerra o motor de gamificacao: remove HUD e listeners.
   */
  function teardown() {
    _active = false;

    // Remove todos os listeners registrados
    for (var i = 0; i < _listeners.length; i++) {
      document.removeEventListener(_listeners[i].eventName, _listeners[i].handler);
    }
    _listeners = [];

    _removerHud();

    _scoringConfig  = {};
    _xp             = 0;
    _hintsUsed      = 0;
    _errorsCount    = 0;
    _sessionStart   = null;
    _currentStep    = null;
    _currentStepIdx = 0;
  }

  global.AuraMissionEngine = {
    init:     init,
    teardown: teardown
  };

}(window));
