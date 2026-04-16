/**
 * aura_config.js — Configuração da extensão Aura DAP
 *
 * Este arquivo define o objeto AURA_CONFIG que é lido pelo background.js.
 * Deve ser declarado ANTES de background.js no manifest.json.
 *
 * ─── PARA DESENVOLVIMENTO LOCAL ───────────────────────────────────────────────
 * Deixe os valores abaixo como estão. O token vazio fará o backend retornar 401
 * se a autenticação estiver habilitada — configure AURA_API_SECRET no .env do
 * servidor e preencha authToken aqui apenas localmente (nunca commite tokens).
 *
 * ─── PARA PRODUÇÃO ────────────────────────────────────────────────────────────
 * Substitua este arquivo durante o build pipeline (CI/CD) com os valores reais,
 * ou gere-o dinamicamente antes de empacotar a extensão.
 * Nunca commite tokens reais neste arquivo.
 *
 * ─── INJEÇÃO VIA MANIFEST ─────────────────────────────────────────────────────
 * manifest.json deve declarar:
 *   "background": {
 *     "scripts": ["aura_config.js", "background.js"]
 *   }
 * Isso garante que AURA_CONFIG esteja definido antes de background.js executar.
 */
var AURA_CONFIG = {
  /**
   * Token de autenticação para o backend Senior Training OS.
   * Deve corresponder ao valor de AURA_API_SECRET no .env do servidor.
   * Deixe vazio para desenvolvimento sem autenticação.
   */
  authToken: '',

  /**
   * Endpoints do backend.
   * Troque para URLs de produção no build pipeline.
   */
  endpoints: {
    analyze:   'http://localhost:8000/analyze',
    missions:  'http://localhost:8000/api/missoes',
    gps:       'http://localhost:8000/api/gps-roteiro',
    analytics: 'http://localhost:8000/api/analytics/evento'
  }
};
