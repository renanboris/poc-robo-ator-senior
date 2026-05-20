"""
contracts/capture_adapter.py — Contrato de Integração para Módulos de Captura
==============================================================================
Task 24: Implementar isolamento de módulos de captura por ERP via adaptadores.

Define o protocolo mínimo que qualquer módulo de captura deve satisfazer para
ser compatível com o Gerador (generator_engine.py) e o Executor (main.py).

Uso:
    from contracts.capture_adapter import CaptureAdapter, SeniorXAdapter, GenericAdapter

Configuração via variável de ambiente:
    CAPTURE_ADAPTER=senior_x  → usa SeniorXAdapter (padrão)
    CAPTURE_ADAPTER=generic   → usa GenericAdapter (sites genéricos)
    CAPTURE_ADAPTER=mock      → usa MockAdapter (testes)

Requisitos: 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5
"""

import os
import sys
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
# Adaptador Genérico (sites web genéricos)
# ──────────────────────────────────────────────────────────────

class GenericAdapter:
    """
    Adaptador para sites web genéricos.

    Lê toda configuração de variáveis de ambiente. Suporta modo sem login
    (LOGIN_REQUIRED=false) e login genérico (LOGIN_REQUIRED=true).

    Variáveis de ambiente consumidas:
        TARGET_URL            — URL do site alvo (obrigatória, http:// ou https://)
        TARGET_SYSTEM_NAME    — Nome do sistema para prompts (fallback: "Site Genérico")
        LOGIN_REQUIRED        — "true" ou "false" (default: "false")
        LOGIN_USER            — Usuário para login (obrigatório se LOGIN_REQUIRED=true)
        LOGIN_PASS            — Senha para login (obrigatório se LOGIN_REQUIRED=true)
        LOGIN_SELECTOR_USER   — Seletor CSS do campo de usuário (obrigatório se LOGIN_REQUIRED=true)
        LOGIN_SELECTOR_PASS   — Seletor CSS do campo de senha (obrigatório se LOGIN_REQUIRED=true)
        LOGIN_SELECTOR_SUBMIT — Seletor CSS do botão de submit (obrigatório se LOGIN_REQUIRED=true)

    Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 6.1, 6.6, 6.7
    """

    def __init__(self) -> None:
        """Inicializa o adapter e executa validação fail-fast."""
        self._validar_configuracao()

    def _validar_configuracao(self) -> None:
        """
        Valida todas as variáveis obrigatórias.
        Encerra o processo com sys.exit(1) e mensagem descritiva se inválida.
        Chamado no __init__ para falha rápida antes de abrir o navegador.
        """
        erros: list[str] = []

        # TARGET_URL obrigatória e válida
        url = os.getenv("TARGET_URL", "").strip()
        if not url:
            erros.append("TARGET_URL não definida no .env")
        elif not (url.startswith("http://") or url.startswith("https://")):
            erros.append(
                f"TARGET_URL inválida: '{url}' (deve iniciar com http:// ou https://)"
            )

        # LOGIN_REQUIRED deve ser true ou false (case-insensitive)
        login_req_raw = os.getenv("LOGIN_REQUIRED", "false").strip().lower()
        if login_req_raw not in ("true", "false"):
            erros.append(
                f"LOGIN_REQUIRED inválido: '{login_req_raw}' "
                "(valores aceitos: 'true' ou 'false')"
            )

        # Seletores e credenciais obrigatórios quando LOGIN_REQUIRED=true
        if login_req_raw == "true":
            for var in ("LOGIN_SELECTOR_USER", "LOGIN_SELECTOR_PASS", "LOGIN_SELECTOR_SUBMIT"):
                if not os.getenv(var, "").strip():
                    erros.append(
                        f"{var} não definida (obrigatória quando LOGIN_REQUIRED=true)"
                    )
            for var in ("LOGIN_USER", "LOGIN_PASS"):
                if not os.getenv(var, "").strip():
                    erros.append(
                        f"{var} não definida (obrigatória quando LOGIN_REQUIRED=true)"
                    )

        if erros:
            msg = "Configuração inválida para CAPTURE_ADAPTER=generic:\n" + "\n".join(
                f"  - {e}" for e in erros
            )
            print(msg, flush=True)
            sys.exit(1)

    @property
    def nome_sistema(self) -> str:
        """Retorna TARGET_SYSTEM_NAME ou 'Site Genérico' como fallback."""
        name = os.getenv("TARGET_SYSTEM_NAME", "").strip()
        return name if name else "Site Genérico"

    @property
    def url_base(self) -> str:
        """Retorna TARGET_URL. Validação já feita no __init__."""
        return os.getenv("TARGET_URL", "").strip()

    def obter_credenciais(self) -> dict:
        """
        Retorna {'usuario': LOGIN_USER, 'senha': LOGIN_PASS}.
        Retorna strings vazias se LOGIN_REQUIRED=false.
        """
        if not self.login_requerido():
            return {"usuario": "", "senha": ""}
        return {
            "usuario": os.getenv("LOGIN_USER", "").strip(),
            "senha": os.getenv("LOGIN_PASS", "").strip(),
        }

    def obter_seletores_login(self) -> dict:
        """
        Retorna seletores de LOGIN_SELECTOR_USER, _PASS, _SUBMIT.
        Retorna strings vazias se LOGIN_REQUIRED=false.
        """
        if not self.login_requerido():
            return {"campo_usuario": "", "campo_senha": "", "botao_proximo": ""}
        return {
            "campo_usuario": os.getenv("LOGIN_SELECTOR_USER", "").strip(),
            "campo_senha": os.getenv("LOGIN_SELECTOR_PASS", "").strip(),
            "botao_proximo": os.getenv("LOGIN_SELECTOR_SUBMIT", "").strip(),
        }

    def obter_configuracao_browser(self) -> dict:
        """Retorna configuração padrão sem flags específicas do Senior X."""
        return {
            "args": [
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            "locale": "pt-BR",
            "headless": False,
        }

    def login_requerido(self) -> bool:
        """Retorna True se LOGIN_REQUIRED=true (case-insensitive). Default: False."""
        return os.getenv("LOGIN_REQUIRED", "false").strip().lower() == "true"


# ──────────────────────────────────────────────────────────────
# Factory: get_capture_adapter()
# ──────────────────────────────────────────────────────────────

def get_capture_adapter() -> CaptureAdapter:
    """
    Retorna o adaptador de captura configurado via CAPTURE_ADAPTER.

    - CAPTURE_ADAPTER não definida ou 'senior_x': SeniorXAdapter (padrão)
    - CAPTURE_ADAPTER='generic' ou 'generico': GenericAdapter (sites genéricos)
    - CAPTURE_ADAPTER='mock': MockAdapter (para testes)
    - Qualquer outro valor: SeniorXAdapter com WARNING

    Requisitos: 1.2, 3.4.2, 3.4.3, 9.1, 9.2, 9.3
    """
    import logging
    logger = logging.getLogger(__name__)

    adapter_name = os.getenv("CAPTURE_ADAPTER", "senior_x").lower().strip()

    if adapter_name in ("senior_x", "seniorx", "senior"):
        return SeniorXAdapter()

    if adapter_name in ("generic", "generico"):
        return GenericAdapter()

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
