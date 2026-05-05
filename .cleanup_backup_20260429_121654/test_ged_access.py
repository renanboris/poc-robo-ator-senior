"""Test accessing GED content to understand the structure."""

from urllib.parse import unquote, urljoin

import requests

# Base URL do GED
base_url = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/"

print("=" * 100)
print("TESTE DE ACESSO AO GED")
print("=" * 100)

# URLs dos fragmentos que você encontrou
ged_fragments = [
    "#utilizando%20o%20ged/conceito.htm",
    "#checklist/checklist-digitalizacao.htm",
    "#checklist/checklist-implantacao.htm",
    "#utilizando%20o%20ged/utilizando-o-ged.htm",
    "#utilizando%20o%20ged/coleta-de-assinatura.htm",
    "#utilizando%20o%20ged/copia-pastas-arquivos.htm",
    "#utilizando%20o%20ged/fluxo-de-assinatura.htm",
    "#utilizando%20o%20ged/gerenciar-documentos.htm",
    "#utilizando%20o%20ged/informacoes-apis.htm",
    "#utilizando%20o%20ged/recursos.htm",
    "#utilizando%20o%20ged/permissoes.htm",
]

print("\n1. Testando acesso à URL base...")
print(f"URL: {base_url}")

try:
    response = requests.get(base_url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    print(f"   Tamanho: {len(response.content)} bytes")
    print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")

    # Verificar se é uma SPA (contém JavaScript)
    content = response.text.lower()
    has_js = 'javascript' in content or '<script' in content
    has_angular = 'angular' in content or 'ng-' in content
    has_react = 'react' in content
    has_vue = 'vue' in content

    print("\n   Análise do conteúdo:")
    print(f"   • Contém JavaScript: {has_js}")
    print(f"   • Angular: {has_angular}")
    print(f"   • React: {has_react}")
    print(f"   • Vue: {has_vue}")

except Exception as e:
    print(f"❌ Erro: {e}")

print("\n2. Testando acesso direto aos fragmentos...")
print("-" * 100)

# Tentar acessar os arquivos .htm diretamente (sem #)
for fragment in ged_fragments[:5]:  # Testar apenas os primeiros 5
    # Remover # e decodificar URL
    file_path = fragment[1:]  # Remove #
    file_path = unquote(file_path)  # Decodifica %20 -> espaço

    # Construir URL direta
    direct_url = urljoin(base_url, file_path)

    print(f"\nFragmento: {fragment}")
    print(f"URL direta: {direct_url}")

    try:
        response = requests.get(direct_url, timeout=5)
        if response.status_code == 200:
            print(f"✅ Acessível diretamente (Status: {response.status_code})")
            print(f"   Tamanho: {len(response.content)} bytes")

            # Verificar se tem conteúdo útil
            if len(response.content) > 1000:
                print("   ✅ Conteúdo substancial")
            else:
                print("   ⚠️  Conteúdo pequeno")
        else:
            print(f"❌ Não acessível (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Erro: {str(e)[:100]}")

print("\n" + "=" * 100)
print("CONCLUSÕES")
print("=" * 100)

print("""
DESCOBERTAS:

1. Se a URL base retorna conteúdo com JavaScript → É uma SPA
2. Se os fragmentos são acessíveis diretamente → Podemos crawlear
3. Se não são acessíveis → Precisamos de JavaScript/Playwright

PRÓXIMOS PASSOS:

Opção A: Crawler Direto
- Se os arquivos .htm são acessíveis diretamente
- Modificar o crawler para descobrir esses arquivos

Opção B: Crawler com JavaScript  
- Se precisar executar JavaScript
- Usar Playwright para renderizar e extrair conteúdo

Opção C: Lista Manual
- Criar lista das URLs importantes manualmente
- Processar apenas essas URLs específicas
""")
