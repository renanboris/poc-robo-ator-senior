"""Test OpenAI API connection."""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv("OPENAI_API_KEY")

print(f"API Key found: {api_key[:10]}...{api_key[-4:]}")
print(f"API Key length: {len(api_key)}")

# Initialize client
try:
    client = OpenAI(api_key=api_key)
    print("✓ OpenAI client initialized successfully")
    
    # Test embedding generation
    print("\nTesting embedding generation...")
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input="Test text for embedding",
        dimensions=3072
    )
    
    embedding = response.data[0].embedding
    print(f"✓ Embedding generated successfully")
    print(f"  Embedding dimensions: {len(embedding)}")
    print(f"  First 5 values: {embedding[:5]}")
    
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
