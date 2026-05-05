"""Test Aura DAP search with the new web knowledge."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dap_engine import buscar_contexto

# Test queries
test_queries = [
    ("Como funciona o PCVV?", "pcvv"),
    ("Quais são as novidades de 2025?", "2025"),
    ("Como habilitar e usar?", "como_habilitar_e_usar"),
    ("Perguntas frequentes sobre Senior", "faq"),
    ("Documentação geral", "senior_default"),
]

print("=" * 80)
print("TESTE DE BUSCA - AURA DAP COM WEB KNOWLEDGE")
print("=" * 80)

for pergunta, namespace in test_queries:
    print(f"\n📝 Pergunta: {pergunta}")
    print(f"🔍 Namespace: {namespace}")
    print("-" * 80)
    
    try:
        resultado = buscar_contexto(pergunta, namespace=namespace)
        
        if resultado:
            print(f"✅ Resultado encontrado!")
            print(f"   Score: {resultado.get('score', 0):.4f}")
            print(f"   Melhor aula/título: {resultado.get('melhor_aula', 'N/A')}")
            if resultado.get('source_url'):
                print(f"   URL: {resultado['source_url']}")
            print(f"\n   Contexto RAG (primeiros 300 chars):")
            print(f"   {resultado.get('texto_rag', 'N/A')[:300]}...")
        else:
            print("❌ Nenhum resultado encontrado")
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    print("-" * 80)

print("\n" + "=" * 80)
print("TESTE CONCLUÍDO")
print("=" * 80)
