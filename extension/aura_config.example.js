/**
 * aura_config.example.js — Modelo de configuração da extensão Aura DAP
 *
 * INSTRUÇÕES:
 * 1. Copie este arquivo para extension/aura_config.js
 * 2. Preencha authToken com o valor de AURA_API_SECRET do seu .env
 * 3. Nunca commite o aura_config.js com tokens reais
 *
 * O aura_config.js está no .gitignore — apenas este exemplo é versionado.
 */
var AURA_CONFIG = {
  /**
   * Token de autenticação para o backend Senior Training OS.
   * Deve corresponder ao valor de AURA_API_SECRET no .env do servidor.
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
    analytics: 'http://localhost:8000/api/analytics/extensao'
  }
};
