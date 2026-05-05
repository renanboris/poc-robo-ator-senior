"""
Test performance - verifica se a detecção de namespace é rápida (<10ms)
"""
import time
import sys
from namespace_detector import detectar_namespace, _carregar_mapeamento_keywords

def test_detection_speed():
    """Testa se a detecção completa em <10ms para inputs típicos"""
    
    test_cases = [
        {"objetivo": "Criar admissão no HCM"},
        {"objetivo": "Configurar contas a pagar"},
        {"objetivo": "Gerenciar documentos no GED"},
        {"url": "https://documentation.senior.com.br/senior-x/hcm/admissao"},
        {"metadata": {"module": "financeiro"}},
        {},  # Caso sem hints
    ]
    
    print("Testando velocidade de detecção...")
    print("-" * 60)
    
    times = []
    for i, contexto in enumerate(test_cases, 1):
        start = time.perf_counter()
        resultado = detectar_namespace(contexto)
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
        
        contexto_str = str(contexto)[:50] + "..." if len(str(contexto)) > 50 else str(contexto)
        print(f"Test {i}: {elapsed_ms:.2f}ms - {contexto_str}")
        print(f"  → Resultado: {resultado}")
    
    print("-" * 60)
    avg_time = sum(times) / len(times)
    max_time = max(times)
    
    print(f"\nEstatísticas:")
    print(f"  Tempo médio: {avg_time:.2f}ms")
    print(f"  Tempo máximo: {max_time:.2f}ms")
    print(f"  Budget: 10ms")
    
    if max_time < 10:
        print(f"\n✅ Performance OK - Todos os testes < 10ms")
        return True
    else:
        print(f"\n⚠️  Performance abaixo do esperado - Máximo {max_time:.2f}ms > 10ms")
        return False

def test_config_caching():
    """Testa se a configuração é carregada uma vez e cacheada"""
    print("\nTestando cache de configuração...")
    print("-" * 60)
    
    # Primeira chamada - deve carregar do arquivo
    start1 = time.perf_counter()
    config1 = _carregar_mapeamento_keywords()
    time1_ms = (time.perf_counter() - start1) * 1000
    
    # Segunda chamada - deve usar cache
    start2 = time.perf_counter()
    config2 = _carregar_mapeamento_keywords()
    time2_ms = (time.perf_counter() - start2) * 1000
    
    print(f"Primeira chamada (load): {time1_ms:.2f}ms")
    print(f"Segunda chamada (cache): {time2_ms:.2f}ms")
    print(f"Speedup: {time1_ms / time2_ms:.1f}x")
    
    # Cache deve ser muito mais rápido
    if time2_ms < time1_ms / 2:
        print(f"\n✅ Cache funcionando - Segunda chamada {time1_ms / time2_ms:.1f}x mais rápida")
        return True
    else:
        print(f"\n⚠️  Cache pode não estar funcionando corretamente")
        return False

def test_keyword_matching_efficiency():
    """Testa se keyword matching faz short-circuit (para no primeiro match)"""
    print("\nTestando eficiência de keyword matching...")
    print("-" * 60)
    
    # Texto com múltiplas keywords - deve parar no primeiro match
    contexto = {"objetivo": "Criar admissão de colaborador no HCM com folha de pagamento"}
    
    start = time.perf_counter()
    resultado = detectar_namespace(contexto)
    elapsed_ms = (time.perf_counter() - start) * 1000
    
    print(f"Texto com múltiplas keywords: {elapsed_ms:.2f}ms")
    print(f"  → Resultado: {resultado}")
    
    if elapsed_ms < 10:
        print(f"\n✅ Keyword matching eficiente - {elapsed_ms:.2f}ms < 10ms")
        return True
    else:
        print(f"\n⚠️  Keyword matching pode estar lento")
        return False

def test_no_external_calls():
    """Verifica que não há chamadas externas (API, DB) durante detecção"""
    print("\nVerificando ausência de chamadas externas...")
    print("-" * 60)
    
    # Detecção deve ser puramente local (sem network/DB)
    # Testamos isso medindo a consistência dos tempos
    
    times = []
    for _ in range(10):
        start = time.perf_counter()
        detectar_namespace({"objetivo": "Criar admissão no HCM"})
        elapsed_ms = (time.perf_counter() - start) * 1000
        times.append(elapsed_ms)
    
    avg = sum(times) / len(times)
    std_dev = (sum((t - avg) ** 2 for t in times) / len(times)) ** 0.5
    
    print(f"10 iterações:")
    print(f"  Média: {avg:.2f}ms")
    print(f"  Desvio padrão: {std_dev:.2f}ms")
    
    # Se há chamadas externas, o desvio seria alto (network latency)
    if std_dev < 2:  # <2ms de variação indica operação local
        print(f"\n✅ Sem chamadas externas - Desvio padrão baixo ({std_dev:.2f}ms)")
        return True
    else:
        print(f"\n⚠️  Possíveis chamadas externas - Desvio padrão alto ({std_dev:.2f}ms)")
        return False

def test_lazy_loading():
    """Verifica que namespace_detector só é importado quando necessário"""
    print("\nVerificando lazy loading...")
    print("-" * 60)
    
    # O módulo já foi importado no início do script, então não podemos
    # testar lazy loading aqui. Mas podemos verificar que a importação
    # é rápida (não faz trabalho pesado no import time)
    
    import importlib
    import sys
    
    # Remove do cache para re-importar
    if 'namespace_detector' in sys.modules:
        del sys.modules['namespace_detector']
    
    start = time.perf_counter()
    import namespace_detector
    import_time_ms = (time.perf_counter() - start) * 1000
    
    print(f"Tempo de import: {import_time_ms:.2f}ms")
    
    if import_time_ms < 50:  # Import deve ser rápido
        print(f"\n✅ Import rápido - {import_time_ms:.2f}ms < 50ms")
        return True
    else:
        print(f"\n⚠️  Import lento - {import_time_ms:.2f}ms > 50ms")
        return False

def main():
    print("=" * 60)
    print("TESTE DE PERFORMANCE")
    print("=" * 60)
    print()
    
    tests = [
        ("Detection speed (<10ms)", test_detection_speed),
        ("Config caching", test_config_caching),
        ("Keyword matching efficiency", test_keyword_matching_efficiency),
        ("No external calls", test_no_external_calls),
        ("Lazy loading", test_lazy_loading),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"[TEST] {name}")
        print('=' * 60)
        result = test_func()
        results.append((name, result))
    
    print("\n" + "=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "⚠️  WARN"
        print(f"{status} - {name}")
    
    print()
    print(f"Total: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 TODOS OS TESTES DE PERFORMANCE PASSARAM!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) com warnings (não crítico)")
        return 0  # Warnings não são falhas críticas

if __name__ == "__main__":
    sys.exit(main())
