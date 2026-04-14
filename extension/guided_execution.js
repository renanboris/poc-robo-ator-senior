/**
 * guided_execution.js — Modo Copiloto In-App do Senior Training OS
 *
 * Injeta tooltips sequenciais sobre os elementos alvo do roteiro,
 * guiando o usuário passo a passo dentro do Senior X.
 *
 * Requisitos: 6.1, 6.2, 6.3, 6.4, 6.6, 6.7
 *
 * Expõe: window.AuraGuidedExecution
 *   - iniciar(roteiroId, apiBase)  — carrega roteiro (cache ou API), inicia guia
 *   - parar()                      — remove tooltips e limpa estado
 *   - avancar()                    — avança para o próximo passo manualmente
 */
(function (global) {
  'use strict';

  // ─── CONSTANTES ──────────────────────────────────────────────────────────────

  var TOOLTIP_ID        = 'aura-guided-tooltip';
  var CACHE_TTL_MS      = 86400000; // 24h
  var WRONG_CLICK_MS    = 600;      // duração do flash vermelho
  var CONCLUIR_VIDEO    = 'concluir_video';

  // ─── ESTADO PRIVADO ──────────────────────────────────────────────────────────

  var _roteiroId        = null;
  var _apiBase          = 'http://localhost:8000';
  var _passos           = [];
  var _stepIndex        = 0;
  var _elementoAlvo     = null;
  var _cleanupClick     = null;   // remove listener de clique correto
  var _cleanupDoc       = null;   // remove listener de clique errado no document
  var _wrongClickTimer  = null;

  // ─── CACHE (Tarefa 19) ───────────────────────────────────────────────────────

  /**
   * Tenta ler o roteiro do chrome.storage.local.
   * Retorna o objeto do roteiro se existir e não estiver expirado; null caso contrário.
   */
  function _lerCache(roteiroId, callback) {
    var chave = 'guided_roteiro_' + roteiroId;
    try {
      chrome.storage.local.get([chave], function (resultado) {
        var entrada = resultado[chave];
        if (entrada && entrada.ts && entrada.dados) {
          if (Date.now() - entrada.ts < CACHE_TTL_MS) {
            callback(entrada.dados);
            return;
          }
        }
        callback(null);
      });
    } catch (e) {
      // chrome.storage não disponível (ex: fora da extensão)
      callback(null);
    }
  }

  /**
   * Salva o roteiro no chrome.storage.local com timestamp.
   */
  function _salvarCache(roteiroId, dados) {
    var chave = 'guided_roteiro_' + roteiroId;
    try {
      var entrada = { ts: Date.now(), dados: dados };
      chrome.storage.local.set({ [chave]: entrada });
    } catch (e) {
      // silencioso — cache é best-effort
    }
  }

  // ─── FETCH DO ROTEIRO ────────────────────────────────────────────────────────

  /**
   * Carrega o roteiro: primeiro tenta cache, depois API.
   * Salva no cache após fetch bem-sucedido.
   */
  function _carregarRoteiro(roteiroId, apiBase, callback) {
    _lerCache(roteiroId, function (cached) {
      if (cached) {
        callback(cached);
        return;
      }
      var url = apiBase + '/api/roteiros/' + encodeURIComponent(roteiroId);
      fetch(url)
        .then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status);
          return res.json();
        })
        .then(function (dados) {
          _salvarCache(roteiroId, dados);
          callback(dados);
        })
        .catch(function (err) {
          console.warn('[AuraGuidedExecution] Falha ao carregar roteiro:', err);
          callback(null);
        });
    });
  }

  // ─── EXTRAÇÃO DE PASSOS ──────────────────────────────────────────────────────

  /**
   * Filtra passos válidos para o guia:
   * - acao != "concluir_video"
   * - tem micro_narracao OU elemento_alvo.seletor_hint
   */
  function _extrairPassos(roteiro) {
    var passos = (roteiro && roteiro.passos) ? roteiro.passos : [];
    return passos.filter(function (p) {
      if (p.acao === CONCLUIR_VIDEO) return false;
      var temNarracao = p.micro_narracao && p.micro_narracao.trim().length > 0;
      var temSeletor  = p.elemento_alvo && p.elemento_alvo.seletor_hint;
      return temNarracao || temSeletor;
    });
  }

  // ─── LOCALIZAÇÃO DO ELEMENTO ALVO ────────────────────────────────────────────

  /**
   * Tenta localizar o elemento alvo do passo.
   * 1. document.querySelector(seletor_hint)
   * 2. document.elementFromPoint via coordenadas_relativas
   * Retorna o elemento ou null.
   */
  function _localizarElemento(passo) {
    var ea = passo.elemento_alvo;
    if (!ea) return null;

    // Tentativa 1: seletor CSS
    if (ea.seletor_hint) {
      try {
        var el = document.querySelector(ea.seletor_hint);
        if (el) return el;
      } catch (e) {
        console.warn('[AuraGuidedExecution] seletor_hint inválido:', ea.seletor_hint);
      }
    }

    // Tentativa 2: coordenadas relativas
    if (ea.coordenadas_relativas) {
      var xPct = ea.coordenadas_relativas.x_pct;
      var yPct = ea.coordenadas_relativas.y_pct;
      if (typeof xPct === 'number' && typeof yPct === 'number') {
        var x = xPct * global.innerWidth;
        var y = yPct * global.innerHeight;
        var el2 = document.elementFromPoint(x, y);
        if (el2 && el2 !== document.documentElement && el2 !== document.body) {
          return el2;
        }
      }
    }

    return null;
  }

  // ─── TOOLTIP ─────────────────────────────────────────────────────────────────

  /**
   * Remove o tooltip existente do DOM.
   */
  function _removerTooltip() {
    var existente = document.getElementById(TOOLTIP_ID);
    if (existente && existente.parentNode) {
      existente.parentNode.removeChild(existente);
    }
  }

  /**
   * Cria e posiciona o tooltip próximo ao elemento alvo.
   * Usa textContent para evitar XSS.
   */
  function _criarTooltip(passo, elemento, stepIndex, totalPassos) {
    _removerTooltip();

    var tooltip = document.createElement('div');
    tooltip.id = TOOLTIP_ID;

    // Estilo base
    tooltip.style.cssText = [
      'position: fixed',
      'background: #1e293b',
      'color: #ffffff',
      'border-radius: 12px',
      'padding: 14px 16px',
      'max-width: 320px',
      'min-width: 220px',
      'z-index: 2147483646',
      'box-shadow: 0 8px 32px rgba(0,0,0,0.45)',
      'font-family: system-ui, -apple-system, sans-serif',
      'font-size: 14px',
      'line-height: 1.5',
      'pointer-events: auto',
      'user-select: none'
    ].join(';');

    // Contador de passo
    var contador = document.createElement('div');
    contador.style.cssText = 'font-size:11px;color:#94a3b8;margin-bottom:6px;font-weight:600;letter-spacing:0.05em;text-transform:uppercase';
    contador.textContent = 'Passo ' + (stepIndex + 1) + ' de ' + totalPassos;
    tooltip.appendChild(contador);

    // Texto da narração
    var texto = document.createElement('div');
    texto.style.cssText = 'margin-bottom:12px';
    texto.textContent = passo.micro_narracao || (passo.elemento_alvo && passo.elemento_alvo.seletor_hint) || 'Clique no elemento destacado.';
    tooltip.appendChild(texto);

    // Botões
    var btnRow = document.createElement('div');
    btnRow.style.cssText = 'display:flex;gap:8px;justify-content:flex-end';

    var btnPular = document.createElement('button');
    btnPular.style.cssText = 'background:transparent;border:1px solid #475569;color:#94a3b8;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px';
    btnPular.textContent = 'Pular';
    btnPular.addEventListener('click', function (e) {
      e.stopPropagation();
      _avancarInterno();
    });

    var btnParar = document.createElement('button');
    btnParar.style.cssText = 'background:transparent;border:1px solid #ef4444;color:#ef4444;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px';
    btnParar.textContent = 'Parar guia';
    btnParar.addEventListener('click', function (e) {
      e.stopPropagation();
      parar();
    });

    btnRow.appendChild(btnPular);
    btnRow.appendChild(btnParar);
    tooltip.appendChild(btnRow);

    document.documentElement.appendChild(tooltip);

    // Posicionamento próximo ao elemento alvo
    _posicionarTooltip(tooltip, elemento);

    return tooltip;
  }

  /**
   * Posiciona o tooltip próximo ao elemento alvo usando getBoundingClientRect.
   * Prefere posição abaixo; se não couber, posiciona acima.
   */
  function _posicionarTooltip(tooltip, elemento) {
    if (!elemento) {
      // Sem elemento: canto inferior direito
      tooltip.style.bottom = '24px';
      tooltip.style.right  = '24px';
      return;
    }

    var rect = elemento.getBoundingClientRect();
    var tw   = tooltip.offsetWidth  || 280;
    var th   = tooltip.offsetHeight || 120;
    var vw   = global.innerWidth;
    var vh   = global.innerHeight;
    var GAP  = 10;

    var top  = rect.bottom + GAP;
    var left = rect.left;

    // Não sair pela direita
    if (left + tw > vw - GAP) left = vw - tw - GAP;
    if (left < GAP) left = GAP;

    // Se não couber abaixo, posicionar acima
    if (top + th > vh - GAP) top = rect.top - th - GAP;
    if (top < GAP) top = GAP;

    tooltip.style.top  = top  + 'px';
    tooltip.style.left = left + 'px';
  }

  // ─── HIGHLIGHT DO ELEMENTO ───────────────────────────────────────────────────

  /**
   * Aplica outline ciano no elemento alvo.
   */
  function _aplicarHighlight(elemento) {
    if (!elemento) return;
    elemento.dataset.auraOutlineOriginal = elemento.style.outline || '';
    elemento.style.outline = '2px solid #00e5e5';
    elemento.style.outlineOffset = '2px';
  }

  /**
   * Remove o outline do elemento alvo.
   */
  function _removerHighlight(elemento) {
    if (!elemento) return;
    elemento.style.outline = elemento.dataset.auraOutlineOriginal || '';
    elemento.style.outlineOffset = '';
    delete elemento.dataset.auraOutlineOriginal;
  }

  /**
   * Pisca outline vermelho por WRONG_CLICK_MS ms (clique errado).
   */
  function _flashErro(elemento) {
    if (!elemento) return;
    if (_wrongClickTimer) clearTimeout(_wrongClickTimer);
    var outlineAnterior = elemento.style.outline;
    elemento.style.outline = '2px solid #ef4444';
    elemento.style.outlineOffset = '2px';
    _wrongClickTimer = setTimeout(function () {
      _wrongClickTimer = null;
      // Restaura o highlight ciano se ainda for o elemento ativo
      if (elemento === _elementoAlvo) {
        elemento.style.outline = '2px solid #00e5e5';
      } else {
        elemento.style.outline = outlineAnterior;
      }
    }, WRONG_CLICK_MS);
  }

  // ─── ANALYTICS ───────────────────────────────────────────────────────────────

  /**
   * Emite evento de analytics via POST silencioso.
   */
  function _emitirEvento(evento, roteiroId, passoId) {
    try {
      fetch(_apiBase + '/api/analytics/evento', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          roteiro_id: roteiroId,
          passo_id:   passoId !== undefined ? passoId : null,
          usuario_id: null,
          evento:     evento
        })
      }).catch(function () { /* silencioso */ });
    } catch (e) {
      // silencioso — não quebrar a extensão
    }
  }

  // ─── LIMPEZA DE LISTENERS ────────────────────────────────────────────────────

  function _limparListeners() {
    if (typeof _cleanupClick === 'function') {
      _cleanupClick();
      _cleanupClick = null;
    }
    if (typeof _cleanupDoc === 'function') {
      _cleanupDoc();
      _cleanupDoc = null;
    }
    if (_wrongClickTimer) {
      clearTimeout(_wrongClickTimer);
      _wrongClickTimer = null;
    }
  }

  // ─── LÓGICA DE PASSO ─────────────────────────────────────────────────────────

  /**
   * Inicia o passo no índice dado.
   */
  function _iniciarPasso(index) {
    _limparListeners();

    if (index >= _passos.length) {
      _concluirGuia();
      return;
    }

    _stepIndex    = index;
    var passo     = _passos[index];
    _elementoAlvo = _localizarElemento(passo);

    // Highlight no elemento alvo
    if (_elementoAlvo) _aplicarHighlight(_elementoAlvo);

    // Criar tooltip
    _criarTooltip(passo, _elementoAlvo, index, _passos.length);

    // Listener de clique correto no elemento alvo
    if (_elementoAlvo) {
      var onClickCorreto = function (e) {
        e.stopPropagation();
        _emitirEvento('completou_passo', _roteiroId, passo.id || index);
        _avancarInterno();
      };
      _elementoAlvo.addEventListener('click', onClickCorreto, { once: true });
      _cleanupClick = function () {
        if (_elementoAlvo) {
          _elementoAlvo.removeEventListener('click', onClickCorreto);
        }
      };
    }

    // Listener de clique errado no document
    var onClickDoc = function (e) {
      if (_elementoAlvo && _elementoAlvo.contains(e.target)) return;
      // Ignorar cliques nos botões do tooltip
      var tooltipEl = document.getElementById(TOOLTIP_ID);
      if (tooltipEl && tooltipEl.contains(e.target)) return;
      _flashErro(_elementoAlvo);
    };
    document.addEventListener('click', onClickDoc, true);
    _cleanupDoc = function () {
      document.removeEventListener('click', onClickDoc, true);
    };
  }

  /**
   * Avança para o próximo passo (interno — limpa estado do passo atual).
   */
  function _avancarInterno() {
    _limparListeners();
    if (_elementoAlvo) {
      _removerHighlight(_elementoAlvo);
      _elementoAlvo = null;
    }
    _removerTooltip();
    _iniciarPasso(_stepIndex + 1);
  }

  /**
   * Exibe mensagem de conclusão e encerra o guia após 3 segundos.
   */
  function _concluirGuia() {
    _removerTooltip();

    var msg = document.createElement('div');
    msg.id = TOOLTIP_ID;
    msg.style.cssText = [
      'position: fixed',
      'bottom: 32px',
      'left: 50%',
      'transform: translateX(-50%)',
      'background: #1e293b',
      'color: #ffffff',
      'border-radius: 12px',
      'padding: 18px 28px',
      'z-index: 2147483646',
      'box-shadow: 0 8px 32px rgba(0,0,0,0.45)',
      'font-family: system-ui, -apple-system, sans-serif',
      'font-size: 15px',
      'text-align: center',
      'pointer-events: none'
    ].join(';');
    msg.textContent = '🎉 Parabéns! Você concluiu o guia com sucesso.';
    document.documentElement.appendChild(msg);

    setTimeout(function () {
      _removerTooltip();
    }, 3000);
  }

  // ─── INTERFACE PÚBLICA ───────────────────────────────────────────────────────

  /**
   * Inicia o guia para o roteiro informado.
   * Idempotente: para o guia anterior se já estiver ativo.
   *
   * @param {string} roteiroId  — ID do roteiro
   * @param {string} [apiBase]  — base URL da API (padrão: http://localhost:8000)
   */
  function iniciar(roteiroId, apiBase) {
    // Idempotência: para guia anterior
    parar();

    _roteiroId = roteiroId;
    _apiBase   = apiBase || 'http://localhost:8000';

    _carregarRoteiro(roteiroId, _apiBase, function (roteiro) {
      if (!roteiro) {
        console.warn('[AuraGuidedExecution] Roteiro não encontrado:', roteiroId);
        return;
      }

      _passos    = _extrairPassos(roteiro);
      _stepIndex = 0;

      if (_passos.length === 0) {
        console.warn('[AuraGuidedExecution] Nenhum passo válido no roteiro:', roteiroId);
        return;
      }

      // Req 6.6 — emitir evento "iniciou_guia"
      _emitirEvento('iniciou_guia', roteiroId, null);

      _iniciarPasso(0);
    });
  }

  /**
   * Para o guia: remove tooltip, highlights e listeners.
   */
  function parar() {
    _limparListeners();
    if (_elementoAlvo) {
      _removerHighlight(_elementoAlvo);
      _elementoAlvo = null;
    }
    _removerTooltip();
    _passos    = [];
    _stepIndex = 0;
    _roteiroId = null;
  }

  /**
   * Avança manualmente para o próximo passo.
   */
  function avancar() {
    if (_passos.length === 0) return;
    _avancarInterno();
  }

  // ─── REGISTRO NO WINDOW ──────────────────────────────────────────────────────

  global.AuraGuidedExecution = {
    iniciar: iniciar,
    parar:   parar,
    avancar: avancar
  };

  console.log('[AuraGuidedExecution] Módulo carregado.');

})(window);
