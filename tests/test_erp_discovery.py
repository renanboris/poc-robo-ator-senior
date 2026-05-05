#!/usr/bin/env python3
"""
Teste rápido da descoberta aprimorada do ERP.
"""

from ingestion_pipeline.crawler import SitemapCrawler
from ingestion_pipeline.extractor import SemanticExtractor
from ingestion_pipeline.validator import ContentValidator


def test_erp_discovery():
    """Testa a descoberta aprimorada do ERP."""

    print("🔍 TESTE DA DESCOBERTA APRIMORADA DO ERP")
    print("=" * 50)

    # 1. Testar descoberta de URLs
    crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")

    print("📡 Executando descoberta completa...")
    urls = crawler.crawl()

    # Filtrar URLs do ERP
    erp_urls = [url for url in urls if 'erp' in url and '#' in url]

    print("\n📊 RESULTADOS DA DESCOBERTA:")
    print(f"Total de URLs descobertas: {len(urls)}")
    print(f"URLs do ERP com fragmentos: {len(erp_urls)}")

    # Agrupar por módulo
    modules = {}
    for url in erp_urls:
        if '#suprimentos' in url:
            modules.setdefault('Suprimentos', []).append(url)
        elif '#financas' in url:
            modules.setdefault('Finanças', []).append(url)
        elif '#controladoria' in url:
            modules.setdefault('Controladoria', []).append(url)
        elif '#custos' in url:
            modules.setdefault('Custos', []).append(url)
        elif '#Subsystems' in url:
            modules.setdefault('Industrial', []).append(url)
        elif '#inteligencia-tributaria' in url:
            modules.setdefault('Inteligência Tributária', []).append(url)
        elif '#Banking' in url:
            modules.setdefault('Banking', []).append(url)
        elif '#analytics' in url:
            modules.setdefault('Analytics', []).append(url)
        elif '#integracoes' in url:
            modules.setdefault('Integrações', []).append(url)
        else:
            modules.setdefault('Outros', []).append(url)

    print("\n📂 URLs por módulo:")
    for module, module_urls in modules.items():
        print(f"  {module}: {len(module_urls)} URLs")

    # 2. Testar extração de conteúdo em algumas URLs
    print("\n🧪 TESTE DE EXTRAÇÃO DE CONTEÚDO:")

    extractor = SemanticExtractor()
    validator = ContentValidator()

    # Testar 3 URLs diferentes
    test_urls = [
        erp_urls[0] if erp_urls else None,
        next((url for url in erp_urls if 'financas' in url), None),
        next((url for url in erp_urls if 'custos' in url), None),
    ]

    successful_extractions = 0

    for i, url in enumerate(test_urls):
        if not url:
            continue

        try:
            print(f"\n  Testando URL {i+1}: {url[:80]}...")

            # Extrair conteúdo
            content = extractor.extract_content(url)

            # Validar conteúdo
            is_valid = validator.validate_content(content)

            if is_valid:
                successful_extractions += 1
                print(f"    ✅ Sucesso - Título: {content['titulo'][:50]}...")
                print(f"    📄 Conteúdo: {len(content['markdown'])} caracteres")
                print(f"    🏷️ Namespace: {content['nivel_2']}")
            else:
                print("    ❌ Conteúdo inválido")

        except Exception as e:
            print(f"    ⚠️ Erro: {e}")

    print("\n✅ RESUMO DO TESTE:")
    print(f"URLs do ERP descobertas: {len(erp_urls)} (vs 46 anteriores)")
    print(f"Melhoria: +{len(erp_urls) - 46} URLs ({((len(erp_urls) - 46) / 46 * 100):.1f}% de aumento)")
    print(f"Extrações bem-sucedidas: {successful_extractions}/{len([u for u in test_urls if u])}")

    return len(erp_urls)

if __name__ == "__main__":
    test_erp_discovery()
