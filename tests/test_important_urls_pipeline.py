"""Test processing important URLs through the pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion_pipeline.extractor import SemanticExtractor
from ingestion_pipeline.validator import ContentValidator
from ingestion_pipeline.chunker import Chunker
from ingestion_pipeline.embedder import EmbeddingGenerator

# URLs importantes para testar
test_urls = [
    "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/index.htm",
    "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/index.htm",
    "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/utilizando o ged/conceito.htm",
    "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/index.htm",
    "https://documentacao.senior.com.br/bpm/7.0.0/index.htm",
]

print("=" * 100)
print("TESTE DAS URLs IMPORTANTES NO PIPELINE")
print("=" * 100)

# Initialize components
extractor = SemanticExtractor(extraction_backend="crawl4ai")
validator = ContentValidator()
chunker = Chunker(chunk_size=800, chunk_overlap=100)
embedder = EmbeddingGenerator(model="text-embedding-3-large", dimensions=3072)

results = []

for i, url in enumerate(test_urls, 1):
    print(f"\n{i}. Testando: {url}")
    print("-" * 100)
    
    try:
        # Stage 1: Extraction
        print("   🔄 Extraindo conteúdo...")
        content = extractor.extract_content(url)
        
        if not content:
            print("   ❌ Falha na extração")
            continue
        
        print(f"   ✅ Extraído: {len(content['markdown'])} chars")
        print(f"      Título: {content['titulo']}")
        print(f"      Breadcrumbs: {content['nivel_1']} / {content['nivel_2']} / {content.get('nivel_3', '')}")
        
        # Stage 2: Validation
        print("   🔄 Validando qualidade...")
        is_valid, reason = validator.validate(content)
        
        if not is_valid:
            print(f"   ❌ Validação falhou: {reason}")
            continue
        
        print("   ✅ Validação passou")
        
        # Stage 3: Chunking
        print("   🔄 Criando chunks...")
        chunks = chunker.chunk_content(
            markdown=content["markdown"],
            metadata={
                "url": content["url"],
                "titulo": content["titulo"],
                "nivel_1": content["nivel_1"],
                "nivel_2": content["nivel_2"],
                "nivel_3": content.get("nivel_3", ""),
            }
        )
        
        print(f"   ✅ Criados {len(chunks)} chunks")
        
        # Stage 4: Embedding (test first chunk only)
        if chunks:
            print("   🔄 Gerando embedding...")
            embedding = embedder.generate_embedding(chunks[0].text)
            print(f"   ✅ Embedding gerado: {len(embedding)} dimensões")
        
        results.append({
            "url": url,
            "status": "success",
            "titulo": content["titulo"],
            "namespace": content["nivel_2"],
            "chunks": len(chunks),
        })
        
    except Exception as e:
        print(f"   ❌ Erro: {type(e).__name__}: {e}")
        results.append({
            "url": url,
            "status": "error",
            "error": str(e),
        })

# Summary
print("\n" + "=" * 100)
print("RESUMO DOS TESTES")
print("=" * 100)

successful = [r for r in results if r["status"] == "success"]
failed = [r for r in results if r["status"] == "error"]

print(f"\n✅ Sucessos: {len(successful)}")
for result in successful:
    print(f"   • {result['titulo']} → namespace: {result['namespace']} ({result['chunks']} chunks)")

print(f"\n❌ Falhas: {len(failed)}")
for result in failed:
    print(f"   • {result['url']}")
    print(f"     Erro: {result['error']}")

print(f"\n📊 Taxa de sucesso: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")

if successful:
    print(f"\n🎯 NAMESPACES ESPERADOS:")
    namespaces = set(r["namespace"] for r in successful)
    for ns in sorted(namespaces):
        count = sum(1 for r in successful if r["namespace"] == ns)
        print(f"   • {ns}: {count} URLs")