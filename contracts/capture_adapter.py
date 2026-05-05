"""
contracts/capture_adapter.py — Contrato de Integração para Módulos de Captura
==============================================================================
Task 24: Implementar isolamento de módulos de captura por ERP via adaptadores.

Define o protocolo mínimo que qualquer módulo de captura deve satisfazer para
ser compatível com o Gerador (generator_engine.py) e o Executor (main.py).

Uso:
    from contracts.capture_adapter import CaptureAdapter, SeniorXAdapter

Configuração via variável de ambiente:
    CAPTURE_ADAPTER=senior_x  → usa SeniorXAdapter (padrão)
    CAPTURE_ADAPTER=mock      → usa MockAdapter (testes)

Requisitos: 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5
"""

import os
from typing import Protocol, runtime_checkable

# ──────────────────────────────────────────────────────────────
# Protocolo CaptureAdapter
# ──────────────────────────────────────────────────────────────

@runtime_checkable
class CaptureAdapter(Protocol):
    """
    Interface mínima que qualquer módulo de captura deve implementar.

    Independente do ERP ou sistema alvo — o pipeline central (Gerador e Executor)
    depende apenas desta interface, nunca de implementações específicas.

    Requisito 3.4.1: contrato independente de qualquer ERP específico.
    """

    @property
    def nome_sistema(self) -> str:
        """Nome do sistema alvo (ex: 'Senior X', 'SAP', 'TOTVS')."""
        ...

    @property
    def url_base(self) -> str:
        """URL base do sistema alvo, lida do ambiente."""
        ...

    def obter_credenciais(self) -> dict:
        """
        Retorna as credenciais necessárias para autenticação no sistema.

        Retorna dict com pelo menos: {'usuario': str, 'senha': str}
        Credenciais devem vir de variáveis de ambiente, nunca hardcoded.
        """
        ...

    def obter_seletores_login(self) -> dict:
        """
        Retorna os seletores CSS/Playwright para o fluxo de login.

        Retorna dict com: {'campo_usuario': str, 'campo_senha': str, 'botao_proximo': str}
        """
        ...

    def obter_configuracao_browser(self) -> dict:
        """
        Retorna as configurações do browser para este sistema.

        Retorna dict com: {'args': list, 'locale': str, 'headless': bool}
        """
        ...


# ──────────────────────────────────────────────────────────────
# Adaptador Senior X (implementação de referência)
# ──────────────────────────────────────────────────────────────

class SeniorXAdapter:
    """
    Adaptador para o sistema Senior X ERP.

    Isola toda referência específica ao Senior X fora dos módulos centrais
    do pipeline (Requisito 3.4.4).
    """

    @property
    def nome_sistema(self) -> str:
        return "Senior X"

    @property
    def url_base(self) -> str:
        return os.getenv(
            "SENIOR_URL",
            "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/",
        )

    def obter_credenciais(self) -> dict:
        return {
            "usuario": os.getenv("SENIOR_USER_CAPTURE", ""),
            "senha":   os.getenv("SENIOR_PASS_CAPTURE", ""),
        }

    def obter_seletores_login(self) -> dict:
        return {
            "campo_usuario":  "input[type='text'], input[type='email'], [placeholder*='usuario']",
            "campo_senha":    "input[type='password']",
            "botao_proximo":  "button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')",
        }

    def obter_configuracao_browser(self) -> dict:
        return {
            "args": [
                "--start-maximized",
                "--disable-features=Translate",
                "--lang=pt-BR",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            "locale":   "pt-BR",
            "headless": False,
        }


# ──────────────────────────────────────────────────────────────
# Factory: get_capture_adapter()
# ──────────────────────────────────────────────────────────────

def get_capture_adapter() -> CaptureAdapter:
    """
    Retorna o adaptador de captura configurado via CAPTURE_ADAPTER.

    - CAPTURE_ADAPTER não definida ou 'senior_x': SeniorXAdapter (padrão)
    - CAPTURE_ADAPTER='mock': MockAdapter (para testes)
    - Qualquer outro valor: SeniorXAdapter com WARNING

    Requisitos: 3.4.2, 3.4.3
    """
    import logging
    logger = logging.getLogger(__name__)

    adapter_name = os.getenv("CAPTURE_ADAPTER", "senior_x").lower().strip()

    if adapter_name in ("senior_x", "seniorx", "senior"):
        return SeniorXAdapter()

    if adapter_name == "mock":
        return MockAdapter()

    logger.warning(
        f"[capture_adapter] CAPTURE_ADAPTER='{adapter_name}' desconhecido. "
        "Usando SeniorXAdapter como padrão."
    )
    return SeniorXAdapter()


# ──────────────────────────────────────────────────────────────
# MockAdapter (para testes e desenvolvimento)
# ──────────────────────────────────────────────────────────────

class MockAdapter:
    """
    Adaptador mock para testes e desenvolvimento.
    Não requer credenciais reais nem conexão com ERP.
    """

    @property
    def nome_sistema(self) -> str:
        return "Mock ERP"

    @property
    def url_base(self) -> str:
        return "http://localhost:9999/mock-erp"

    def obter_credenciais(self) -> dict:
        return {"usuario": "mock_user", "senha": "mock_pass"}

    def obter_seletores_login(self) -> dict:
        return {
            "campo_usuario": "input[name='username']",
            "campo_senha":   "input[name='password']",
            "botao_proximo": "button[type='submit']",
        }

    def obter_configuracao_browser(self) -> dict:
        return {
            "args":     ["--no-sandbox"],
            "locale":   "pt-BR",
            "headless": True,
        }
