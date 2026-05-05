"""Clean up Pinecone index and reprocess with fixed breadcrumbs."""

import os

from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# Connect to Pinecone
api_key = os.getenv("PINECONE_API_KEY")
index_name = os.getenv("PINECONE_INDEX_NAME")

pc = Pinecone(api_key=api_key)
index = pc.Index(index_name)

# Get all namespaces
stats = index.describe_index_stats()
namespaces = stats.get('namespaces', {})

print(f"Found {len(namespaces)} namespaces to delete")
print("Deleting all namespaces...")

# Delete all vectors in each namespace
for namespace in namespaces.keys():
    print(f"  Deleting namespace: {namespace}")
    index.delete(delete_all=True, namespace=namespace)

print("\n✓ All namespaces deleted successfully!")
print("\nNow run the pipeline again:")
print("  py -m ingestion_pipeline https://documentacao.senior.com.br/sitemap.xml --backend crawl4ai")
