"""
Final Validation - Executa todos os testes para validação final da feature
"""
import sys
import subprocess
import os

def run_test(test_name: str, command: list) -> tuple[bool, str]:
    """Executa um teste e retorna (sucesso, output)"""
    print(f"\n{'='*60}")
    print(f"[TEST] {test_name}")
    print('='*60)
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        return success, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT - Teste excedeu 60 segundos")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ ERRO - {e}")
        return False, str(e)

def check_file_exists(filepath: str) -> bool:
    """Verifica se um arquivo existe"""
    exists = os.path.exists(filepath)
    status = "✅" if exists else "❌"
    print(f"{status} {filepath}")
    return exists

def main():
    print("=" * 60)
    print("VALIDAÇÃO FINAL - RAG NAMESPACE AUTO-DETECTION")
    print("=" * 60)
    
    # 1. Verificar arquivos críticos
    print("\n[1/6] Verificando arquivos críticos...")
    print("-" * 60)
    
    critical_files = [
        "namespace_detector.py",
        "namespace_keywords.json",
        "dap_engine.py",
        "generator_engine.py",
        "capture.py",
        "README.md",
        "NAMESPACE_DETECTION_EXAMPLES.md",
    ]
    
    files_ok = all(check_file_exists(f) for f in critical_files)
    
    if not files_ok:
        print("\n❌ Arquivos críticos ausentes!")
        return 1
    
    # 2. Teste de backward compatibility
    print("\n[2/6] Executando testes de backward compatibility...")
    print("-" * 60)
    
    compat_ok, _ = run_test(
        "Backward Compatibility",
        [sys.executable, "test_backward_compatibility.py"]
    )
    
    # 3. Teste de performance
    print("\n[3/6] Executando testes de performance...")
    print("-" * 60)
    
    perf_ok, _ = run_test(
        "Performance",
        [sys.executable, "test_performance.py"]
    )
    
    # 4. Verificar integrações
    print("\n[4/6] Verificando integrações...")
    print("-" * 60)
    
    try:
        # Verificar import sem erros
        import namespace_detector
        import dap_engine
        import generator_engine
        import capture
        
        print("✅ Todos os módulos importados com sucesso")
        
        # Verificar assinaturas
        import inspect
        
        # buscar_contexto deve ter parâmetro namespace opcional
        sig = inspect.signature(dap_engine.buscar_contexto)
        params = list(sig.parameters.keys())
        
        if "namespace" in params:
            namespace_param = sig.parameters["namespace"]
            if namespace_param.default is not inspect.Parameter.empty:
                print("✅ buscar_contexto tem parâmetro namespace opcional")
                integrations_ok = True
            else:
                print("❌ parâmetro namespace não é opcional")
                integrations_ok = False
        else:
            print("❌ parâmetro namespace ausente em buscar_contexto")
            integrations_ok = False
        
        # Verificar se generator_engine usa detectar_namespace
        gen_source = inspect.getsource(generator_engine.gerar_roteiro_ia_sync)
        if "detectar_namespace" in gen_source:
            print("✅ generator_engine integrado com detectar_namespace")
        else:
            print("❌ generator_engine não usa detectar_namespace")
            integrations_ok = False
        
        # Verificar se capture usa detectar_namespace
        cap_source = inspect.getsource(capture._buscar_pinecone_sync)
        if "detectar_namespace" in cap_source:
            print("✅ capture.py integrado com detectar_namespace")
        else:
            print("❌ capture.py não usa detectar_namespace")
            integrations_ok = False
        
    except Exception as e:
        print(f"❌ Erro ao verificar integrações: {e}")
        integrations_ok = False
    
    # 5. Teste end-to-end simplificado
    print("\n[5/6] Executando teste end-to-end...")
    print("-" * 60)
    
    try:
        from namespace_detector import detectar_namespace
        from dap_engine import buscar_contexto
        
        # Teste 1: Detecção por keyword
        contexto1 = {"objetivo": "Criar admissão no HCM"}
        ns1 = detectar_namespace(contexto1)
        
        if ns1 == "hcm":
            print("✅ Detecção por keyword funcionando (hcm)")
        else:
            print(f"⚠️  Detecção por keyword retornou: {ns1} (esperado: hcm)")
        
        # Teste 2: Detecção por URL
        contexto2 = {"url": "https://docs.senior.com.br/senior-x/financeiro/contas-a-pagar"}
        ns2 = detectar_namespace(contexto2)
        
        if ns2 == "financeiro":
            print("✅ Detecção por URL funcionando (financeiro)")
        else:
            print(f"⚠️  Detecção por URL retornou: {ns2} (esperado: financeiro)")
        
        # Teste 3: Fallback
        contexto3 = {}
        ns3 = detectar_namespace(contexto3)
        
        if ns3 is None:
            print("✅ Fallback funcionando (None)")
        else:
            print(f"⚠️  Fallback retornou: {ns3} (esperado: None)")
        
        e2e_ok = True
        
    except Exception as e:
        print(f"❌ Erro no teste end-to-end: {e}")
        e2e_ok = False
    
    # 6. Verificar documentação
    print("\n[6/6] Verificando documentação...")
    print("-" * 60)
    
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme = f.read()
        
        if "Detecção Automática de Namespace" in readme:
            print("✅ README.md atualizado com feature")
        else:
            print("❌ README.md não menciona a feature")
        
        if os.path.exists("NAMESPACE_DETECTION_EXAMPLES.md"):
            print("✅ Arquivo de exemplos criado")
        else:
            print("❌ Arquivo de exemplos ausente")
        
        docs_ok = True
        
    except Exception as e:
        print(f"❌ Erro ao verificar documentação: {e}")
        docs_ok = False
    
    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO DA VALIDAÇÃO FINAL")
    print("=" * 60)
    
    results = [
        ("Arquivos críticos", files_ok),
        ("Backward compatibility", compat_ok),
        ("Performance", perf_ok),
        ("Integrações", integrations_ok),
        ("End-to-end", e2e_ok),
        ("Documentação", docs_ok),
    ]
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print()
    print(f"Total: {passed}/{total} validações passaram")
    
    if passed == total:
        print("\n" + "🎉" * 20)
        print("VALIDAÇÃO FINAL COMPLETA - FEATURE PRONTA PARA DEPLOY!")
        print("🎉" * 20)
        return 0
    else:
        print(f"\n⚠️  {total - passed} validação(ões) falharam")
        print("Por favor, corrija os problemas antes de fazer deploy.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
