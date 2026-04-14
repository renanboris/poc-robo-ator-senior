/**
 * checklist_widget.js — Widget de Checklist de Onboarding Aura
 *
 * Expõe window.AuraChecklistWidget com:
 *   mostrar(checklist, roteiroId) — renderiza widget flutuante
 *   esconder()                    — remove widget do DOM
 *   marcarConcluido(passoId)      — marca item e atualiza progresso
 *
 * Sem dependências externas. Usa textContent para todos os textos.
 * Escuta eventos window.message do tipo aura_analytics/completou_passo.
 *
 * Requisitos: 7.2, 7.3, 7.6
 */
(function () {
    'use strict';

    var WIDGET_ID      = 'aura-checklist-widget';
    var STYLE_ID       = 'aura-checklist-style';
    var _checklist     = [];
    var _roteiroId     = null;
    var _celebrando    = false;

    // ── Estilos ───────────────────────────────────────────────────────────────

    function _injetarEstilos() {
        if (document.getElementById(STYLE_ID)) return;
        var style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = [
            '#aura-checklist-widget {',
            '  position: fixed;',
            '  bottom: 24px;',
            '  left: 24px;',
            '  width: 280px;',
            '  background: #1e293b;',
            '  border-radius: 16px;',
            '  padding: 16px;',
            '  z-index: 2147483645;',
            '  box-shadow: 0 8px 32px rgba(0,0,0,0.45);',
            '  font-family: "Segoe UI", system-ui, sans-serif;',
            '  color: #f1f5f9;',
            '  box-sizing: border-box;',
            '}',
            '#aura-checklist-widget .acw-titulo {',
            '  font-size: 13px;',
            '  font-weight: 700;',
            '  color: #94a3b8;',
            '  text-transform: uppercase;',
            '  letter-spacing: 0.08em;',
            '  margin-bottom: 12px;',
            '}',
            '#aura-checklist-widget .acw-lista {',
            '  list-style: none;',
            '  margin: 0 0 12px 0;',
            '  padding: 0;',
            '  max-height: 220px;',
            '  overflow-y: auto;',
            '}',
            '#aura-checklist-widget .acw-item {',
            '  display: flex;',
            '  align-items: flex-start;',
            '  gap: 8px;',
            '  padding: 6px 0;',
            '  font-size: 13px;',
            '  line-height: 1.4;',
            '  border-bottom: 1px solid rgba(255,255,255,0.06);',
            '}',
            '#aura-checklist-widget .acw-item:last-child { border-bottom: none; }',
            '#aura-checklist-widget .acw-icone {',
            '  flex-shrink: 0;',
            '  font-size: 15px;',
            '  margin-top: 1px;',
            '}',
            '#aura-checklist-widget .acw-item.concluido .acw-icone { color: #22c55e; }',
            '#aura-checklist-widget .acw-item.pendente  .acw-icone { color: #64748b; }',
            '#aura-checklist-widget .acw-item.concluido .acw-texto {',
            '  text-decoration: line-through;',
            '  color: #64748b;',
            '}',
            '#aura-checklist-widget .acw-barra-wrap {',
            '  height: 6px;',
            '  background: rgba(255,255,255,0.1);',
            '  border-radius: 99px;',
            '  overflow: hidden;',
            '}',
            '#aura-checklist-widget .acw-barra-fill {',
            '  height: 100%;',
            '  border-radius: 99px;',
            '  background: linear-gradient(90deg, #00e5e5, #7c3aed);',
            '  transition: width 0.4s ease;',
            '}',
            '#aura-checklist-widget .acw-pct {',
            '  font-size: 11px;',
            '  color: #94a3b8;',
            '  text-align: right;',
            '  margin-top: 4px;',
            '}',
            '#aura-checklist-widget .acw-celebracao {',
            '  text-align: center;',
            '  font-size: 28px;',
            '  margin: 8px 0 4px;',
            '  animation: acw-pulse 0.6s ease-in-out infinite alternate;',
            '}',
            '@keyframes acw-pulse {',
            '  from { transform: scale(1);   opacity: 1; }',
            '  to   { transform: scale(1.2); opacity: 0.8; }',
            '}',
        ].join('\n');
        (document.head || document.documentElement).appendChild(style);
    }

    // ── Construção do DOM ─────────────────────────────────────────────────────

    function _criarWidget() {
        var el = document.createElement('div');
        el.id = WIDGET_ID;

        var titulo = document.createElement('div');
        titulo.className = 'acw-titulo';
        titulo.textContent = 'Seu progresso';
        el.appendChild(titulo);

        var lista = document.createElement('ul');
        lista.className = 'acw-lista';
        _checklist.forEach(function (item) {
            lista.appendChild(_criarItem(item));
        });
        el.appendChild(lista);

        var barraWrap = document.createElement('div');
        barraWrap.className = 'acw-barra-wrap';
        var barraFill = document.createElement('div');
        barraFill.className = 'acw-barra-fill';
        barraFill.style.width = _calcularPct() + '%';
        barraWrap.appendChild(barraFill);
        el.appendChild(barraWrap);

        var pct = document.createElement('div');
        pct.className = 'acw-pct';
        pct.textContent = _calcularPct() + '% concluído';
        el.appendChild(pct);

        return el;
    }

    function _criarItem(item) {
        var li = document.createElement('li');
        li.className = 'acw-item ' + (item.completado ? 'concluido' : 'pendente');
        li.dataset.id = String(item.id);

        var icone = document.createElement('span');
        icone.className = 'acw-icone';
        icone.textContent = item.completado ? '✓' : '○';

        var texto = document.createElement('span');
        texto.className = 'acw-texto';
        texto.textContent = item.titulo;

        li.appendChild(icone);
        li.appendChild(texto);
        return li;
    }

    // ── Cálculo de progresso ──────────────────────────────────────────────────

    function _calcularPct() {
        if (!_checklist.length) return 0;
        var concluidos = _checklist.filter(function (i) { return i.completado; }).length;
        return Math.round((concluidos / _checklist.length) * 100);
    }

    function _todosCompletos() {
        return _checklist.length > 0 && _checklist.every(function (i) { return i.completado; });
    }

    // ── Atualização do DOM ────────────────────────────────────────────────────

    function _atualizarWidget() {
        var widget = document.getElementById(WIDGET_ID);
        if (!widget) return;

        // Atualiza cada item
        _checklist.forEach(function (item) {
            var li = widget.querySelector('[data-id="' + item.id + '"]');
            if (!li) return;
            li.className = 'acw-item ' + (item.completado ? 'concluido' : 'pendente');
            var icone = li.querySelector('.acw-icone');
            if (icone) icone.textContent = item.completado ? '✓' : '○';
        });

        // Atualiza barra
        var pct = _calcularPct();
        var fill = widget.querySelector('.acw-barra-fill');
        if (fill) fill.style.width = pct + '%';
        var pctEl = widget.querySelector('.acw-pct');
        if (pctEl) pctEl.textContent = pct + '% concluído';
    }

    // ── Celebração ────────────────────────────────────────────────────────────

    function _celebrar() {
        if (_celebrando) return;
        _celebrando = true;

        var widget = document.getElementById(WIDGET_ID);
        if (!widget) return;

        var cel = document.createElement('div');
        cel.className = 'acw-celebracao';
        cel.textContent = '🎉 🎉 🎉';
        widget.appendChild(cel);

        setTimeout(function () {
            window.AuraChecklistWidget.esconder();
            _celebrando = false;
        }, 3000);
    }

    // ── API pública ───────────────────────────────────────────────────────────

    window.AuraChecklistWidget = {

        mostrar: function (checklist, roteiroId) {
            // Remove instância anterior se existir
            this.esconder();

            _checklist = (checklist || []).map(function (item) {
                return { id: item.id, titulo: item.titulo, completado: !!item.completado };
            });
            _roteiroId = roteiroId || null;
            _celebrando = false;

            _injetarEstilos();
            var widget = _criarWidget();
            document.documentElement.appendChild(widget);
        },

        esconder: function () {
            var widget = document.getElementById(WIDGET_ID);
            if (widget && widget.parentNode) {
                widget.parentNode.removeChild(widget);
            }
            _checklist = [];
            _roteiroId = null;
        },

        marcarConcluido: function (passoId) {
            var id = Number(passoId);
            var item = null;
            for (var i = 0; i < _checklist.length; i++) {
                if (_checklist[i].id === id) { item = _checklist[i]; break; }
            }
            if (!item || item.completado) return;

            item.completado = true;
            _atualizarWidget();

            if (_todosCompletos()) {
                _celebrar();
            }
        },
    };

    // ── Escuta eventos de analytics do guided execution ───────────────────────

    window.addEventListener('message', function (event) {
        if (!event.data) return;
        var d = event.data;
        if (d.type === 'aura_analytics' && d.evento === 'completou_passo' && d.passo_id != null) {
            window.AuraChecklistWidget.marcarConcluido(d.passo_id);
        }
    });

})();
