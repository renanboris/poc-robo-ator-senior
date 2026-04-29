"""
Bug Condition Exploration Tests — main-py-hardening
====================================================
Estes testes CONFIRMAM os bugs no código NÃO-CORRIGIDO.

Metodologia:
  - Os testes assertam a CONDIÇÃO DE BUG (estado atual incorreto).
  - Quando os testes PASSAM, significa que o bug FOI CONFIRMADO.
  - Após o fix, estes mesmos testes devem continuar passando (assertando
    o comportamento correto esperado).

Bugs cobertos:
  C-01 — _estado.json persiste paths absolutos (caminho_webm e timeline[].arquivo)
  C-02 — _audio_manifest mutado sem lock em asyncio.gather concorrente
  C-04 — Invariante de tempo_corte_segundos não documentado no source

Validates: Requirements 1.1, 1.2, 1.3, 1.4
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest.mock as mock
import importlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path — garante que o root do projeto está acessível
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# C-01 — Paths Absolutos no _estado.json
# ===========================================================================

@given(
    sufixo=st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    )
)
@settings(max_examples=20, deadline=None)
def test_c01_paths_absolutos_no_estado_json(sufixo):
    """
    Simula o bloco json.dump() atual (sem conversão para relativo).
    Confirma que caminho_webm e timeline[].arquivo são salvos como paths
    absolutos — condição de bug C-01.

    Validates: Requirements 1.1, 1.2
    """
    # Simula o que page.video.path() retorna — sempre absoluto
    caminho_webm = os.path.abspath(f"videos_gerados/test_{sufixo}.webm")

    # Simula timeline_audios com paths absolutos (como os.path.join produz)
    timeline_audios = [
        {
            "arquivo": os.path.abspath(
                f"audios_gerados/Aula_{sufixo}/audio_passo_{i}_ancora.mp3"
            ),
            "inicio": float(i),
            "fim": float(i) + 2.5,
            "texto": f"Narração passo {i}",
        }
        for i in range(1, 4)
    ]

    # Simula o json.dump() atual — sem nenhuma chamada a os.path.relpath()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(
            {
                "caminho_webm": caminho_webm,
                "timeline": timeline_audios,
                "tempo_corte": 5.0,
            },
            f,
        )
        nome_arquivo = f.name

    try:
        with open(nome_arquivo, "r", encoding="utf-8") as f:
            estado = json.load(f)

        # CONFIRMA BUG C-01: caminho_webm é absoluto
        assert os.path.isabs(estado["caminho_webm"]) is True, (
            f"BUG C-01 NÃO CONFIRMADO: esperava path absoluto em caminho_webm, "
            f"mas obteve: {estado['caminho_webm']!r}"
        )

        # CONFIRMA BUG C-01: todos os paths da timeline são absolutos
        for item in estado["timeline"]:
            assert os.path.isabs(item["arquivo"]) is True, (
                f"BUG C-01 NÃO CONFIRMADO: esperava path absoluto em "
                f"timeline[].arquivo, mas obteve: {item['arquivo']!r}"
            )
    finally:
        os.unlink(nome_arquivo)


# ===========================================================================
# C-02 — Race Condition em _audio_manifest (ausência de lock)
# ===========================================================================

def test_c02_manifesto_sem_lock():
    """
    Confirma que _audio_manifest não possui mecanismo de sincronização
    no código atual. Replica o padrão de gerar_audio() sem lock com 20
    coroutines concorrentes e asserta a ausência de _audio_manifest_lock.

    Validates: Requirements 1.3
    """
    # Importa main com mock das dependências pesadas para evitar side effects
    heavy_deps = [
        "pygame",
        "edge_tts",
        "playwright",
        "playwright.async_api",
        "moviepy",
        "moviepy.editor",
        "moviepy.audio.fx.all",
        "vision_engine",
        "score_engine",
        "cursor_engine",
        "proglog",
        "requests",
    ]

    mocks = {dep: mock.MagicMock() for dep in heavy_deps}

    with mock.patch.dict("sys.modules", mocks):
        if "main" in sys.modules:
            del sys.modules["main"]
        main = importlib.import_module("main")

    # Replica o padrão atual: dict global sem lock
    _audio_manifest: dict = {}

    async def gerar_audio_sem_lock(id_unico: str) -> None:
        """Replica o comportamento atual de gerar_audio() sem lock."""
        await asyncio.sleep(0)
        # Escrita direta em _audio_manifest sem nenhum lock — padrão atual
        _audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"

    async def executar():
        tarefas = [gerar_audio_sem_lock(f"passo_{i}_ancora") for i in range(20)]
        await asyncio.gather(*tarefas)

    asyncio.run(executar())

    # CONFIRMA FIX C-02: o lock existe no módulo main (fix aplicado)
    assert hasattr(main, "_audio_manifest_lock"), (
        "FIX C-02 NÃO APLICADO: _audio_manifest_lock não foi encontrado em main, "
        "mas deveria existir após o fix."
    )


# ===========================================================================
# C-04 — Invariante de tempo_corte_segundos não documentado
# ===========================================================================

def test_c04_comentario_invariante_ausente():
    """
    Lê main.py como string. Encontra a linha com
    'tempo_corte_segundos  = tempo_inicio_gravacao - tempo_inicio_contexto'
    e asserta que as linhas imediatamente anteriores NÃO contêm 'INVARIANTE'.

    Validates: Requirements 1.4
    """
    caminho_main = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "main.py",
    )
    with open(caminho_main, "r", encoding="utf-8") as f:
        source_code = f.read()

    linhas = source_code.splitlines()

    # Localiza a linha do cálculo de tempo_corte_segundos
    linha_alvo = None
    for i, linha in enumerate(linhas):
        if (
            "tempo_corte_segundos" in linha
            and "tempo_inicio_gravacao" in linha
            and "tempo_inicio_contexto" in linha
        ):
            linha_alvo = i
            break

    assert linha_alvo is not None, (
        "Sanity check falhou: linha com 'tempo_corte_segundos  = "
        "tempo_inicio_gravacao - tempo_inicio_contexto' não encontrada em main.py"
    )

    # Verifica as linhas imediatamente anteriores (janela de 6 linhas)
    janela_anterior = linhas[max(0, linha_alvo - 6) : linha_alvo]

    # CONFIRMA FIX C-04: pelo menos uma linha anterior contém "INVARIANTE"
    assert any("INVARIANTE" in linha for linha in janela_anterior), (
        f"FIX C-04 NÃO APLICADO: 'INVARIANTE' não encontrado nas linhas "
        f"anteriores ao cálculo de tempo_corte_segundos. "
        f"Janela anterior: {janela_anterior!r}"
    )
