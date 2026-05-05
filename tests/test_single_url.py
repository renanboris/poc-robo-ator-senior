"""Test processing a single URL through the full pipeline."""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from ingestion_pipeline.extractor import SemanticExtractor
from ingestion_pipeline.validator import ContentValidator
from ingestion_pipeline.chunker import Chunker
from ingestion_pipeline.embedder import EmbeddingGenerator

# Test URL (one that should have good content)
test_url = "https://documentacao.senior.com.br/seniorxplatform/hcm/admissao-digital/index.htm"

print(f"Testing URL: {test_url}\n")

# Stage 1: Extraction
print("Stage 1: Extraction...")
extractor = SemanticExtractor(extraction_backend="crawl4ai")
content = extractor.extract_content(test_url)

if not content:
    print("✗ Extraction failed")
    sys.exit(1)

print(f"✓ Extraction successful")
print(f"  Title: {content['titulo']}")
print(f"  Markdown length: {len(content['markdown'])} chars")
print(f"  Breadcrumbs: {content['nivel_1']} / {content['nivel_2']} / {content.get('nivel_3', '')}")

# Stage 2: Validation
print("\nStage 2: Validation...")
validator = ContentValidator()
is_valid, reason = validator.validate(content)

if not is_valid:
    print(f"✗ Validation failed: {reason}")
    sys.exit(1)

print(f"✓ Validation successful")

# Stage 3: Chunking
print("\nStage 3: Chunking...")
chunker = Chunker(chunk_size=800, chunk_overlap=100)
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

print(f"✓ Chunking successful: {len(chunks)} chunks created")

# Stage 4: Embedding (test first chunk only)
print("\nStage 4: Embedding...")
embedder = EmbeddingGenerator(model="text-embedding-3-large", dimensions=3072)

try:
    embedding = embedder.generate_embedding(chunks[0].text)
    print(f"✓ Embedding successful")
    print(f"  Dimensions: {len(embedding)}")
    print(f"  First 5 values: {embedding[:5]}")
except Exception as e:
    print(f"✗ Embedding failed: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All stages completed successfully!")
