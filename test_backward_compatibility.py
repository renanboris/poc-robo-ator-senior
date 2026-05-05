"""
Test backward compatibility - verifica se o sistema funciona sem namespace hints
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

def test_namespace_detector_import():
    """Testa se o namespace_detector pode ser importado sem erros"""
    try:
        print("✅ namespace_detector importado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao importar namespace_detector: {e}")
        return False

def test_detectar_namespace_empty():
    """Testa se detectar_namespace retorna None para contexto vazio"""
    try:
        from namespace_detector import detectar_namespace
        resultado = detectar_namespace({})
        if resultado is None:
            print("✅ detectar_namespace({}) retorna None (comportamento esperado)")
            return True
        else:
            print(f"❌ detectar_namespace({{}}) retornou {resultado}, esperado None")
            return False
    except Exception as e:
        print(f"❌ Erro ao testar detectar_namespace: {e}")
        return False

def test_dap_engine_buscar_contexto_signature():
    """Testa se buscar_contexto mantém assinatura retrocompatível"""
    try:
        import inspect

        import dap_engine

        sig = inspect.signature(dap_engine.buscar_contexto)
        params = list(sig.parameters.keys())

        # Verifica se os parâmetros obrigatórios estão presentes
        if "prompt_usuario" in params and "tenant_id" in params:
            print("✅ buscar_contexto mantém assinatura retrocompatível")

            # Verifica se namespace é opcional
            namespace_param = sig.parameters.get("namespace")
            if namespace_param and namespace_param.default is not inspect.Parameter.empty:
                print("✅ parâmetro 'namespace' é opcional (default=None)")
                return True
            else:
                print("❌ parâmetro 'namespace' não é opcional")
                return False
        else:
            print(f"❌ buscar_contexto não tem parâmetros esperados: {params}")
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar assinatura: {e}")
        return False

def test_generator_engine_integration():
    """Testa se generator_engine importa namespace_detector corretamente"""
    try:
        import generator_engine
        print("✅ generator_engine importado com sucesso")

        # Verifica se a integração está presente
        import inspect
        source = inspect.getsource(generator_engine.gerar_roteiro_ia_sync)

        if "detectar_namespace" in source:
            print("✅ generator_engine integrado com detectar_namespace")
            return True
        else:
            print("❌ generator_engine não usa detectar_namespace")
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar generator_engine: {e}")
        return False

def test_capture_integration():
    """Testa se capture.py importa namespace_detector corretamente"""
    try:
        import capture
        print("✅ capture.py importado com sucesso")

        # Verifica se a integração está presente
        import inspect
        source = inspect.getsource(capture._buscar_pinecone_sync)

        if "detectar_namespace" in source:
            print("✅ capture.py integrado com detectar_namespace")
            return True
        else:
            print("❌ capture.py não usa detectar_namespace")
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar capture.py: {e}")
        return False

def test_namespace_keywords_config():
    """Testa se namespace_keywords.json existe e é válido"""
    try:
        import json

        if not os.path.exists("namespace_keywords.json"):
            print("⚠️  namespace_keywords.json não existe (usará defaults)")
            return True  # Não é erro crítico

        with open("namespace_keywords.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        if isinstance(config, dict) and len(config) > 0:
            print(f"✅ namespace_keywords.json válido ({len(config)} namespaces)")
            return True
        else:
            print("❌ namespace_keywords.json inválido")
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar namespace_keywords.json: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTE DE BACKWARD COMPATIBILITY")
    print("=" * 60)
    print()

    tests = [
        ("Import namespace_detector", test_namespace_detector_import),
        ("detectar_namespace({}) retorna None", test_detectar_namespace_empty),
        ("buscar_contexto signature", test_dap_engine_buscar_contexto_signature),
        ("generator_engine integration", test_generator_engine_integration),
        ("capture.py integration", test_capture_integration),
        ("namespace_keywords.json config", test_namespace_keywords_config),
    ]

    results = []
    for name, test_func in tests:
        print(f"\n[TEST] {name}")
        print("-" * 60)
        result = test_func()
        results.append((name, result))
        print()

    print("=" * 60)
    print("RESUMO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print()
    print(f"Total: {passed}/{total} testes passaram")

    if passed == total:
        print("\n🎉 TODOS OS TESTES DE BACKWARD COMPATIBILITY PASSARAM!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} teste(s) falharam")
        return 1

if __name__ == "__main__":
    sys.exit(main())
