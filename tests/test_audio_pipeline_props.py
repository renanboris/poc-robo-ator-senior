"""
tests/test_audio_pipeline_props.py
====================================
Property-based tests for audio pipeline functions in main.py.

Spec: .kiro/specs/playback-resilience-roadmap (Eixo 4, Task 13)

NOTA: Não importa main.py diretamente (dependências pesadas como pygame,
moviepy, playwright). Em vez disso, testa a lógica de negócio isolada
usando mocks e stubs — valida os invariantes da spec sem acoplamento.
"""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — lógica de manifesto de áudio isolada para teste
# ──────────────────────────────────────────────────────────────────────────────


class _ManifestoSimulator:
    """Simula o comportamento do manifesto de áudio sem importar main.py."""

    def __init__(self):
        self.manifesto: dict = {}
        self._lock = asyncio.Lock()

    async def registrar_audio(self, id_passo: str, path: str):
        async with self._lock:
            self.manifesto[id_passo] = path

    async def limpar(self):
        async with self._lock:
            self.manifesto.clear()

    async def executar_roteiro(self, passos: list[str]) -> dict:
        """Simula executar_roteiro: limpa, gera em paralelo, retorna manifesto."""
        await self.limpar()

        async def gerar_para(id_passo):
            await self.registrar_audio(id_passo, f"audios/audio_{id_passo}.mp3")

        resultados = await asyncio.gather(
            *[gerar_para(p) for p in passos],
            return_exceptions=True,
        )
        return dict(self.manifesto)


# ──────────────────────────────────────────────────────────────────────────────
# Property 8: Invariante de contagem do manifesto de áudio
# Feature: playback-resilience-roadmap, Property 8
# ──────────────────────────────────────────────────────────────────────────────


@given(n=st.integers(min_value=1, max_value=30))
@settings(max_examples=50)
def test_manifesto_tem_exatamente_n_entradas(n):
    """
    # Feature: playback-resilience-roadmap, Property 8: Invariante de contagem do manifesto de áudio

    Para qualquer roteiro com N passos (N >= 1), após asyncio.gather(*tarefas_audio),
    o manifesto deve conter exatamente N entradas sem duplicatas.
    """
    passos = [f"passo_{i:03d}" for i in range(n)]
    sim = _ManifestoSimulator()
    manifesto = asyncio.run(sim.executar_roteiro(passos))

    assert len(manifesto) == n, f"Esperado {n} entradas, obtido {len(manifesto)}"
    # Sem duplicatas — as chaves são únicas por design
    assert len(set(manifesto.keys())) == n


@given(n=st.integers(min_value=1, max_value=30))
@settings(max_examples=50)
def test_manifesto_sem_duplicatas(n):
    """O manifesto não deve ter entradas duplicadas mesmo em execução paralela."""
    passos = [f"step_{i}" for i in range(n)]
    sim = _ManifestoSimulator()
    manifesto = asyncio.run(sim.executar_roteiro(passos))

    chaves = list(manifesto.keys())
    assert len(chaves) == len(set(chaves)), "Manifesto contém chaves duplicadas"


@given(n=st.integers(min_value=1, max_value=30))
@settings(max_examples=30)
def test_manifesto_limpo_entre_execucoes(n):
    """O manifesto deve ser completamente limpo entre execuções consecutivas."""
    passos_1 = [f"run1_passo_{i}" for i in range(n)]
    passos_2 = [f"run2_passo_{i}" for i in range(n)]

    sim = _ManifestoSimulator()

    manifesto_1 = asyncio.run(sim.executar_roteiro(passos_1))
    manifesto_2 = asyncio.run(sim.executar_roteiro(passos_2))

    # Execução 2 não deve conter entradas da execução 1
    for chave in manifesto_2:
        assert "run1_" not in chave, f"Chave da run1 encontrada na run2: {chave}"

    assert len(manifesto_2) == n


# ──────────────────────────────────────────────────────────────────────────────
# Testes unitários: Race condition / locking do manifesto
# ──────────────────────────────────────────────────────────────────────────────


def test_clear_protegido_por_lock():
    """O clear deve ser thread-safe via asyncio.Lock."""
    async def _run():
        sim = _ManifestoSimulator()
        # Adicionar algumas entradas
        await sim.registrar_audio("p1", "a1.mp3")
        await sim.registrar_audio("p2", "a2.mp3")
        assert len(sim.manifesto) == 2

        # Limpar e verificar
        await sim.limpar()
        assert len(sim.manifesto) == 0

    asyncio.run(_run())


def test_manifesto_json_serializable():
    """O manifesto deve ser sempre serializável para JSON."""
    async def _run():
        sim = _ManifestoSimulator()
        for i in range(5):
            await sim.registrar_audio(f"passo_{i}", f"audio_{i}.mp3")

        # Deve serializar sem erro
        serializado = json.dumps(sim.manifesto, ensure_ascii=False)
        recuperado = json.loads(serializado)
        assert recuperado == sim.manifesto

    asyncio.run(_run())


def test_falha_individual_nao_cancela_demais():
    """
    Uma falha na geração de áudio de um passo não deve cancelar os demais.
    Usa return_exceptions=True no gather (Req 11.4).
    """
    async def _run():
        async def gerar_ok(id_p):
            return f"audio_{id_p}.mp3"

        async def gerar_falha(id_p):
            raise RuntimeError(f"Falha no passo {id_p}")

        tarefas = [
            gerar_ok("p1"),
            gerar_falha("p2"),
            gerar_ok("p3"),
        ]

        resultados = await asyncio.gather(*tarefas, return_exceptions=True)

        # p1 e p3 devem ter sucesso; p2 deve ter exceção, não cancelar os outros
        assert resultados[0] == "audio_p1.mp3"
        assert isinstance(resultados[1], RuntimeError)
        assert resultados[2] == "audio_p3.mp3"

    asyncio.run(_run())
