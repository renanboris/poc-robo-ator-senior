"""Manual list of important URLs discovered by user exploration."""

# URLs importantes descobertas manualmente
IMPORTANT_URLS = {
    # Senior Flow - Manual do Usuário
    "senior-flow-manual": [
        "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/index.htm",
        # Adicionar mais URLs específicas conforme descobertas
    ],
    
    # Senior Flow - Notas de Versão  
    "senior-flow-notas": [
        "https://documentacao.senior.com.br/senior-flow/notas-da-versao/index.htm",
        # Adicionar mais URLs específicas conforme descobertas
    ],
    
    # GED - URLs descobertas pelo usuário
    "ged": [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/index.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/conceito.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/checklist/checklist-digitalizacao.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/checklist/checklist-implantacao.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/utilizando-o-ged.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/coleta-de-assinatura.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/copia-pastas-arquivos.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/fluxo-de-assinatura.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/gerenciar-documentos.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/informacoes-apis.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/recursos.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/permissoes.htm",
    ],
    
    # SIGN Studio
    "sign": [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/index.htm",
        # Adicionar URLs específicas do SIGN conforme descobertas
    ],
    
    # BPM
    "bpm": [
        "https://documentacao.senior.com.br/bpm/7.0.0/index.htm",
        # Adicionar URLs específicas do BPM conforme descobertas
    ],
    
    # Senior Connect
    "connect": [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/index.htm",
        # Adicionar URLs específicas do Connect conforme descobertas
    ],
    
    # ERP Senior X
    "erp": [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/index.htm",
        # Adicionar URLs específicas do ERP conforme descobertas
    ],
}

def get_all_important_urls():
    """Get flattened list of all important URLs."""
    all_urls = []
    for category, urls in IMPORTANT_URLS.items():
        all_urls.extend(urls)
    return all_urls

def get_urls_by_category(category):
    """Get URLs for a specific category."""
    return IMPORTANT_URLS.get(category, [])

# Test function
if __name__ == "__main__":
    print("=" * 100)
    print("URLS IMPORTANTES MANUAIS")
    print("=" * 100)
    
    for category, urls in IMPORTANT_URLS.items():
        print(f"\n📁 {category.upper()}: {len(urls)} URLs")
        for url in urls:
            print(f"   • {url}")
    
    all_urls = get_all_important_urls()
    print(f"\n📊 TOTAL: {len(all_urls)} URLs importantes")
    
    # Test accessibility
    print(f"\n🔍 TESTANDO ACESSIBILIDADE...")
    import requests
    
    accessible = 0
    for url in all_urls[:5]:  # Test first 5
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {url}")
                accessible += 1
            else:
                print(f"❌ {url} (Status: {response.status_code})")
        except Exception as e:
            print(f"❌ {url} (Erro: {str(e)[:50]})")
    
    print(f"\n📈 {accessible}/{min(5, len(all_urls))} URLs testadas são acessíveis")