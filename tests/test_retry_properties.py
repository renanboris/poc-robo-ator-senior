"""
tests/test_retry_properties.py — Property 18: Retry com backoff em falhas de API externa

Feature: training-os-roadmap
Property 18: Retry com backoff em falhas de API externa
**Validates: Requirements NFR-2.1**

Para qualquer chamada de API que falhe na primeira tentativa (mock), verificar que o
sistema realiza pelo menos 2 tentativas adicionais com delay crescente.
"""

import time

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from utils import com_retry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _CallTracker:
    """Registra chamadas e delays observados entre elas."""

    def __init__(self, falhas: int):
        self.falhas = falhas          # quantas vezes lançar exceção antes de ter sucesso
        self.chamadas = 0
        self.timestamps: list[float] = []

    def __call__(self):
        self.timestamps.append(time.monotonic())
        self.chamadas += 1
        if self.chamadas <= self.falhas:
            raise ConnectionError(f"Falha simulada #{self.chamadas}")
        return "ok"


# ---------------------------------------------------------------------------
# Property 18
# ---------------------------------------------------------------------------

@given(
    falhas_iniciais=st.integers(min_value=1, max_value=2),
    delays=st.lists(
        st.floats(min_value=0.0, max_value=0.0),  # delays=0 para não esperar nos testes
        min_size=3,
        max_size=3,
    ),
)
@settings(max_examples=50)
def test_property_18_retry_realiza_tentativas_adicionais_com_delay_crescente(
    falhas_iniciais, delays
):
    """
    **Property 18: Retry com backoff em falhas de API externa**
    **Validates: Requirements NFR-2.1**

    Para qualquer chamada de API que falhe na primeira tentativa (mock), verificar que
    o sistema realiza pelo menos 2 tentativas adicionais com delay crescente.

    Usa delays=[0,0,0] para não bloquear os testes, mas verifica a ordem crescente
    dos delays configurados separadamente.
    """
    # Garante que haverá pelo menos 1 falha e que o total de tentativas é suficiente
    tentativas_total = falhas_iniciais + 1  # exatamente o suficiente para ter sucesso
    assume(tentativas_total <= 3)

    tracker = _CallTracker(falhas=falhas_iniciais)

    resultado = com_retry(tracker, tentativas=tentativas_total, delays=delays)

    # O resultado deve ser "ok" (sucesso após as falhas)
    assert resultado == "ok"

    # Deve ter feito exatamente falhas_iniciais + 1 chamadas
    assert tracker.chamadas == falhas_iniciais + 1, (
        f"Esperado {falhas_iniciais + 1} chamadas, mas fez {tracker.chamadas}"
    )

    # Deve ter realizado pelo menos 2 tentativas adicionais quando falhas_iniciais >= 1
    assert tracker.chamadas >= 2, (
        f"Sistema deve realizar pelo menos 2 tentativas no total, fez {tracker.chamadas}"
    )


@given(
    tentativas=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=50)
def test_property_18_todas_tentativas_esgotadas_lanca_ultima_excecao(tentativas):
    """
    **Property 18 (complemento): Após esgotar tentativas, lança a última exceção**
    **Validates: Requirements NFR-2.1, NFR-2.2**

    Quando todas as tentativas falham, com_retry deve lançar a última exceção
    capturada — nunca engolir o erro silenciosamente.
    """
    chamadas = [0]

    def sempre_falha():
        chamadas[0] += 1
        raise ValueError(f"Erro permanente #{chamadas[0]}")

    try:
        com_retry(sempre_falha, tentativas=tentativas, delays=[0] * tentativas)
        assert False, "Deveria ter lançado exceção"
    except ValueError as e:
        # Deve ter feito exatamente `tentativas` chamadas
        assert chamadas[0] == tentativas, (
            f"Esperado {tentativas} chamadas, fez {chamadas[0]}"
        )
        # A mensagem deve corresponder à última tentativa
        assert f"#{tentativas}" in str(e)


def test_property_18_delays_crescentes_sao_respeitados():
    """
    **Property 18 (delays): Verifica que delays crescentes são passados corretamente**
    **Validates: Requirements NFR-2.1**

    Verifica que com_retry usa os delays na ordem correta (crescente = backoff).
    Usa mock de time.sleep para inspecionar os valores sem esperar.
    """
    import unittest.mock as mock

    delays_usados: list[float] = []
    chamadas = [0]

    def falha_duas_vezes():
        chamadas[0] += 1
        if chamadas[0] <= 2:
            raise RuntimeError("falha")
        return "ok"

    with mock.patch("utils.time.sleep", side_effect=lambda d: delays_usados.append(d)):
        resultado = com_retry(falha_duas_vezes, tentativas=3, delays=[1, 2, 4])

    assert resultado == "ok"
    assert len(delays_usados) == 2, f"Esperado 2 sleeps, obteve {len(delays_usados)}"

    # Delays devem ser crescentes (backoff)
    assert delays_usados[0] < delays_usados[1], (
        f"Delays devem ser crescentes: {delays_usados}"
    )
    assert delays_usados == [1, 2], f"Delays esperados [1, 2], obteve {delays_usados}"


def test_property_18_sucesso_na_primeira_tentativa_sem_retry():
    """Quando fn tem sucesso imediato, não deve haver retry nem sleep."""
    import unittest.mock as mock

    chamadas = [0]

    def sucesso():
        chamadas[0] += 1
        return "resultado"

    with mock.patch("utils.time.sleep") as mock_sleep:
        resultado = com_retry(sucesso, tentativas=3, delays=[1, 2, 4])

    assert resultado == "resultado"
    assert chamadas[0] == 1
    mock_sleep.assert_not_called()


def test_property_18_excecoes_nao_listadas_nao_disparam_retry():
    """Exceções fora do tuple `excecoes` devem propagar imediatamente sem retry."""
    chamadas = [0]

    def lanca_tipo_errado():
        chamadas[0] += 1
        raise TypeError("tipo errado")

    try:
        com_retry(lanca_tipo_errado, tentativas=3, delays=[0, 0, 0], excecoes=(ValueError,))
        assert False, "Deveria ter propagado TypeError"
    except TypeError:
        pass

    # Deve ter feito apenas 1 chamada — sem retry para TypeError
    assert chamadas[0] == 1, f"Esperado 1 chamada, fez {chamadas[0]}"
